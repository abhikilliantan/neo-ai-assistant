"""Document ingest + retrieval (Phase 8b) — runs against the REAL Alembic
migration (pgvector + HNSW + RLS on BOTH tables) with the deterministic mock
parser + mock embedding provider.

Citation is the constraint, so the load-bearing tests prove provenance survives
the DB round trip (especially a boundary-spanning chunk), char offsets index
into the STORED full_text, cross-tenant isolation holds at the CHUNK level, and
a failed ingest leaves NO partial state.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.documents import DocumentIngestService, validate_chunk_size_within_token_cap
from app.ai.documents.chunker import FixedSizeChunker
from app.ai.documents.mock import MockDocumentParser
from app.ai.providers.embeddings.mock import MockEmbeddingProvider
from app.application.ports.embeddings import EmbeddingResult, InputType
from app.infrastructure.db.models import Document, DocumentChunk, Organization, User
from app.infrastructure.db.repositories import DocumentRepository
from app.shared.exceptions.documents import DocumentConfigError

_MODEL = "mock-embed-1"


def _service(
    chunk_size: int = 100, embedding_provider: object | None = None
) -> DocumentIngestService:
    """Ingest service with a SMALL chunk_size so the mock's ~409-char document
    yields several chunks, including page-boundary-spanning ones.
    """
    return DocumentIngestService(
        parser=MockDocumentParser(max_bytes=1_000_000),
        chunker=FixedSizeChunker(chunk_size=chunk_size, overlap=0),
        embedding_provider=embedding_provider or MockEmbeddingProvider(),
        chunk_size=chunk_size,
        embedding_model="voyage-3.5",  # config target for the guard
    )


async def _seed_two_tenants(db_session: AsyncSession) -> tuple[UUID, UUID, UUID, UUID]:
    """As neo (bypasses RLS): orgs A+B, one user each. Returns
    (org_a, org_b, user_a, user_b).
    """
    org_a = Organization(name="Org A", slug="doc-a")
    org_b = Organization(name="Org B", slug="doc-b")
    user_a = User(email="alice@doc-a.example", password_hash="x")
    user_b = User(email="bob@doc-b.example", password_hash="x")
    db_session.add_all([org_a, org_b, user_a, user_b])
    await db_session.commit()
    return org_a.id, org_b.id, user_a.id, user_b.id


# --- token-cap guard (pure, no DB) ------------------------------------------


def test_token_cap_guard_passes_for_default_config() -> None:
    # 1000 chars * 4 tokens/char = 4000 <= 32000 (voyage-3.5).
    validate_chunk_size_within_token_cap(chunk_size=1000, embedding_model="voyage-3.5")


def test_token_cap_guard_fails_loudly_when_chunk_could_exceed_model_cap() -> None:
    # 10000 chars * 4 = 40000 > 32000 → must raise, not silently truncate later.
    with pytest.raises(DocumentConfigError, match="exceeding"):
        validate_chunk_size_within_token_cap(chunk_size=10_000, embedding_model="voyage-3.5")


def test_ingest_service_construction_runs_the_guard() -> None:
    with pytest.raises(DocumentConfigError):
        DocumentIngestService(
            parser=MockDocumentParser(max_bytes=1),
            chunker=FixedSizeChunker(chunk_size=10_000, overlap=0),
            embedding_provider=MockEmbeddingProvider(),
            chunk_size=10_000,
            embedding_model="voyage-3.5",
        )


# --- ingest end-to-end ------------------------------------------------------


@pytest.mark.asyncio
async def test_ingest_persists_document_and_all_chunks_with_provenance(
    db_session: AsyncSession, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    org_a, _ob, user_a, _ub = await _seed_two_tenants(db_session)
    service = _service(chunk_size=100)

    s = await app_session_factory(org_a)
    try:
        doc = await service.ingest(
            s,
            organization_id=org_a,
            uploaded_by_user_id=user_a,
            filename="paper.pdf",
            content_type="application/pdf",
            data=b"anything",
        )
        repo = DocumentRepository(s)
        chunks = await repo.list_chunks(doc.id)

        # Multi-page mock → several chunks, dense 0-based ordinals.
        assert len(chunks) >= 4
        assert [c.ordinal for c in chunks] == list(range(len(chunks)))
        # Every chunk stored the model the provider actually reported.
        assert {c.embedding_model for c in chunks} == {_MODEL}
        # Embeddings persisted at full dimension.
        assert all(len(c.embedding) == 1024 for c in chunks)
        # Document metadata; full_text is the canonical anchor (tiling proven in
        # test_char_offsets_index_into_the_stored_full_text).
        assert doc.status == "ready"
        assert doc.byte_size == len(b"anything")
        assert len(doc.full_text) == chunks[-1].char_end
        await s.commit()
    finally:
        await s.close()


@pytest.mark.asyncio
async def test_provenance_survives_round_trip_for_boundary_spanning_chunk(
    db_session: AsyncSession, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    """The whole citation design is worthless if provenance degrades on
    persistence. Assert the page RANGE of a chunk that straddles two pages.
    """
    org_a, _ob, user_a, _ub = await _seed_two_tenants(db_session)
    service = _service(chunk_size=100)

    s = await app_session_factory(org_a)
    try:
        doc = await service.ingest(
            s,
            organization_id=org_a,
            uploaded_by_user_id=user_a,
            filename="paper.pdf",
            content_type="application/pdf",
            data=b"anything",
        )
        chunks = await DocumentRepository(s).list_chunks(doc.id)

        # chunk[0] is wholly on page 1; chunk[1] straddles pages 1-2.
        assert (chunks[0].page_start, chunks[0].page_end) == (1, 1)
        boundary = chunks[1]
        assert (boundary.page_start, boundary.page_end) == (1, 2)
        assert (boundary.char_start, boundary.char_end) == (100, 200)
        assert boundary.section is None  # PDF: page, never a fabricated section
        await s.commit()
    finally:
        await s.close()


@pytest.mark.asyncio
async def test_char_offsets_index_into_the_stored_full_text(
    db_session: AsyncSession, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    """Proves full_text is the genuine canonical anchor: slicing the STORED
    string by each chunk's stored offsets reproduces the stored chunk text.
    """
    org_a, _ob, user_a, _ub = await _seed_two_tenants(db_session)
    service = _service(chunk_size=100)

    s = await app_session_factory(org_a)
    try:
        doc = await service.ingest(
            s,
            organization_id=org_a,
            uploaded_by_user_id=user_a,
            filename="paper.pdf",
            content_type="application/pdf",
            data=b"anything",
        )
        stored = await DocumentRepository(s).get_document(doc.id)
        assert stored is not None
        chunks = await DocumentRepository(s).list_chunks(doc.id)
        for c in chunks:
            assert stored.full_text[c.char_start : c.char_end] == c.text
        # And the chunks tile the whole document.
        assert chunks[0].char_start == 0
        assert chunks[-1].char_end == len(stored.full_text)
        await s.commit()
    finally:
        await s.close()


# --- similarity search + embedding_model guard ------------------------------


@pytest.mark.asyncio
async def test_search_chunks_returns_provenance_and_respects_embedding_model_filter(
    db_session: AsyncSession, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    org_a, _ob, user_a, _ub = await _seed_two_tenants(db_session)
    service = _service(chunk_size=100)

    # Ingest under tenant A and commit.
    sa = await app_session_factory(org_a)
    try:
        doc = await service.ingest(
            sa,
            organization_id=org_a,
            uploaded_by_user_id=user_a,
            filename="paper.pdf",
            content_type="application/pdf",
            data=b"anything",
        )
        chunk0 = (await DocumentRepository(sa).list_chunks(doc.id))[0]
        query = await MockEmbeddingProvider().embed(texts=[chunk0.text])
        query_vec = query.vectors[0]
        await sa.commit()
    finally:
        await sa.close()

    # As neo, plant a FOREIGN-model chunk whose vector == the query (would rank
    # #1 if not filtered) — the 5d guard must exclude it.
    db_session.add(
        DocumentChunk(
            document_id=doc.id,
            organization_id=org_a,
            ordinal=999,
            text="foreign vector-space row",
            embedding=query_vec,
            embedding_model="foreign-model-1",
            char_start=0,
            char_end=1,
        )
    )
    await db_session.commit()

    s = await app_session_factory(org_a)
    try:
        results = await DocumentRepository(s).search_chunks(
            organization_id=org_a,
            query_embedding=query_vec,
            limit=10,
            embedding_model=_MODEL,
        )
        models = {c.embedding_model for c, _ in results}
        assert models == {_MODEL}  # foreign-model row never returned
        assert "foreign-model-1" not in models
        # Provenance survives into search results (top hit carries page info).
        top_chunk, top_sim = results[0]
        assert top_chunk.page_start is not None
        assert abs(top_sim - 1.0) < 1e-6  # chunk0's own vector == query
    finally:
        await s.close()


# --- ingest failure semantic: all-or-nothing, no partial state --------------


class _BoomEmbeddingProvider:
    """Fails at embed — simulates a provider outage MID-INGEST, after the
    document row has already been created + flushed in the same transaction.
    """

    @property
    def dimension(self) -> int:
        return 1024

    async def embed(
        self, *, texts: list[str], input_type: InputType = "document"
    ) -> EmbeddingResult:
        raise RuntimeError("embed boom")


@pytest.mark.asyncio
async def test_failed_ingest_leaves_no_partial_state(
    db_session: AsyncSession, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    org_a, _ob, user_a, _ub = await _seed_two_tenants(db_session)
    service = _service(chunk_size=100, embedding_provider=_BoomEmbeddingProvider())

    s = await app_session_factory(org_a)
    try:
        with pytest.raises(RuntimeError, match="embed boom"):
            await service.ingest(
                s,
                organization_id=org_a,
                uploaded_by_user_id=user_a,
                filename="paper.pdf",
                content_type="application/pdf",
                data=b"anything",
            )
    finally:
        await s.rollback()  # caller rolls back the failed unit of work
        await s.close()

    # As neo (bypasses RLS): NOTHING persisted — not even the document row that
    # was created before the embed call. All-or-nothing held.
    doc_count = (await db_session.execute(select(func.count()).select_from(Document))).scalar_one()
    chunk_count = (
        await db_session.execute(select(func.count()).select_from(DocumentChunk))
    ).scalar_one()
    assert doc_count == 0
    assert chunk_count == 0


# --- soft-deleted document excludes its chunks from search ------------------


@pytest.mark.asyncio
async def test_soft_deleted_document_chunks_excluded_from_search(
    db_session: AsyncSession, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    org_a, _ob, user_a, _ub = await _seed_two_tenants(db_session)
    service = _service(chunk_size=100)

    sa = await app_session_factory(org_a)
    try:
        doc = await service.ingest(
            sa,
            organization_id=org_a,
            uploaded_by_user_id=user_a,
            filename="paper.pdf",
            content_type="application/pdf",
            data=b"anything",
        )
        chunk0 = (await DocumentRepository(sa).list_chunks(doc.id))[0]
        query_vec = (await MockEmbeddingProvider().embed(texts=[chunk0.text])).vectors[0]
        repo = DocumentRepository(sa)
        before = await repo.search_chunks(
            organization_id=org_a, query_embedding=query_vec, limit=10, embedding_model=_MODEL
        )
        assert len(before) > 0
        await repo.soft_delete(doc.id)
        after = await repo.search_chunks(
            organization_id=org_a, query_embedding=query_vec, limit=10, embedding_model=_MODEL
        )
        assert after == []  # one row soft-deleted → all its chunks gone from search
        await sa.commit()
    finally:
        await sa.close()


# --- documents outlive their uploader (SET NULL, not CASCADE) ---------------


@pytest.mark.asyncio
async def test_document_survives_deletion_of_its_uploader(
    db_session: AsyncSession,
) -> None:
    """Documents belong to the ORG, not the uploader. Deleting a user must leave
    the org's documents intact, with uploaded_by_user_id going NULL — never a
    cascade delete of org content triggered by an unrelated user removal.
    """
    org_a, _ob, user_a, _ub = await _seed_two_tenants(db_session)
    doc = Document(
        organization_id=org_a,
        uploaded_by_user_id=user_a,
        filename="contract.pdf",
        content_type="application/pdf",
        byte_size=8,
        full_text="signed",
    )
    db_session.add(doc)
    await db_session.commit()
    doc_id = doc.id

    uploader = await db_session.get(User, user_a)
    assert uploader is not None
    await db_session.delete(uploader)
    await db_session.commit()

    db_session.expire_all()  # force a fresh read, not the identity-map copy
    survivor = await db_session.get(Document, doc_id)
    assert survivor is not None  # document outlived its uploader
    assert survivor.uploaded_by_user_id is None  # FK went NULL, org content kept


# --- cross-tenant isolation on BOTH tables (chunk level directly) -----------


@pytest.mark.asyncio
async def test_no_tenant_context_hides_documents_and_chunks(
    db_session: AsyncSession, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    # Seed as neo (bypasses RLS) and open ONLY the no-tenant app session on the
    # fresh pool: current_setting('app.current_tenant', true) is then NULL, not
    # the placeholder-GUC reset value '' (which would ::uuid-error). This mirrors
    # test_no_tenant_context_hides_memories_and_prefs exactly.
    org_a, _ob, user_a, _ub = await _seed_two_tenants(db_session)
    doc = Document(
        organization_id=org_a,
        uploaded_by_user_id=user_a,
        filename="paper.pdf",
        content_type="application/pdf",
        byte_size=8,
        full_text="hello world",
    )
    db_session.add(doc)
    await db_session.flush()
    db_session.add(
        DocumentChunk(
            document_id=doc.id,
            organization_id=org_a,
            ordinal=0,
            text="hello world",
            embedding=[0.0] * 1024,
            embedding_model=_MODEL,
            char_start=0,
            char_end=11,
        )
    )
    await db_session.commit()

    s = await app_session_factory(None)
    try:
        assert (await s.execute(select(Document))).scalars().all() == []
        assert (await s.execute(select(DocumentChunk))).scalars().all() == []
    finally:
        await s.close()


@pytest.mark.asyncio
async def test_tenant_B_cannot_see_tenant_A_documents_or_chunks(
    db_session: AsyncSession, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    org_a, org_b, user_a, _ub = await _seed_two_tenants(db_session)
    sa = await app_session_factory(org_a)
    try:
        await _service(chunk_size=100).ingest(
            sa,
            organization_id=org_a,
            uploaded_by_user_id=user_a,
            filename="paper.pdf",
            content_type="application/pdf",
            data=b"anything",
        )
        await sa.commit()
    finally:
        await sa.close()

    sb = await app_session_factory(org_b)
    try:
        # Chunk-level assertion DIRECTLY — not only via the document join, since
        # the chunk table carries its own organization_id and its own policy.
        assert (await sb.execute(select(DocumentChunk))).scalars().all() == []
        # Even a targeted cross-tenant WHERE is filtered by RLS.
        stmt = select(DocumentChunk).where(DocumentChunk.organization_id == org_a)
        assert (await sb.execute(stmt)).scalars().all() == []
        assert (await sb.execute(select(Document))).scalars().all() == []
    finally:
        await sb.close()


@pytest.mark.asyncio
async def test_insert_chunk_into_other_tenant_rejected(
    db_session: AsyncSession, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    """WITH CHECK on the chunk table: writing a chunk tagged with another
    tenant's org_id is rejected even from a valid session."""
    org_a, org_b, user_a, _ub = await _seed_two_tenants(db_session)
    # Give A a document to attach the sneaky chunk to.
    sa = await app_session_factory(org_a)
    try:
        doc = await _service(chunk_size=100).ingest(
            sa,
            organization_id=org_a,
            uploaded_by_user_id=user_a,
            filename="paper.pdf",
            content_type="application/pdf",
            data=b"anything",
        )
        await sa.commit()
    finally:
        await sa.close()

    s = await app_session_factory(org_a)
    try:
        s.add(
            DocumentChunk(
                document_id=doc.id,
                organization_id=org_b,  # foreign tenant → WITH CHECK rejects
                ordinal=0,
                text="sneaky",
                embedding=[0.0] * 1024,
                embedding_model=_MODEL,
                char_start=0,
                char_end=6,
            )
        )
        with pytest.raises(DBAPIError):
            await s.flush()
    finally:
        await s.rollback()
        await s.close()
