"""Phase 8e-1 — POST /api/v1/documents/search.

The JSON surface behind 8d's model-facing tool. Load-bearing properties:
  - CITATION: a result carries filename, chunk text, similarity, the STRUCTURED
    position AND the server-rendered citation string, asserted on a
    BOUNDARY-SPANNING chunk so "pp. N-M" is exercised.
  - FLOOR: a below-floor hit is ABSENT (not present-and-flagged) — proven with a
    planted weak match at a controlled cosine.
  - SCOPE: tenant-only. Tenant B can't see A's chunks; a colleague in the SAME
    org CAN (the deliberate 8d asymmetry with memory).
  - embedding_model guard, soft-delete exclusion, whitelist (no full_text / no
    vector), 401 without a token.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.documents.chunker import FixedSizeChunker
from app.ai.documents.ingest import DocumentIngestService
from app.ai.documents.mock import MockDocumentParser
from app.ai.providers.embeddings.mock import MockEmbeddingProvider
from app.application.ports.documents import DocumentPosition
from app.infrastructure.db.models import DocumentChunk, Membership, Role
from app.infrastructure.db.repositories import DocumentRepository

_PDF = "application/pdf"


# --- helpers -----------------------------------------------------------------


async def _register(client: AsyncClient, email: str) -> dict[str, Any]:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password12345"},
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def _auth(reg: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {reg['access_token']}"}


def _ingest_service(chunk_size: int = 100) -> DocumentIngestService:
    return DocumentIngestService(
        parser=MockDocumentParser(max_bytes=1_000_000),
        chunker=FixedSizeChunker(chunk_size=chunk_size, overlap=0),
        embedding_provider=MockEmbeddingProvider(),
        chunk_size=chunk_size,
        embedding_model="voyage-3.5",
    )


async def _ingest(app_session_factory: Any, *, tenant: UUID, user: UUID, filename: str) -> UUID:
    s = await app_session_factory(tenant)
    try:
        doc = await _ingest_service().ingest(
            s,
            organization_id=tenant,
            uploaded_by_user_id=user,
            filename=filename,
            content_type=_PDF,
            data=b"anything",
        )
        await s.commit()
        return doc.id
    finally:
        await s.close()


async def _query_vector(query: str) -> list[float]:
    return (await MockEmbeddingProvider().embed(texts=[query], input_type="query")).vectors[0]


def _vec_at_cosine(q: list[float], cosine: float) -> list[float]:
    """A unit vector whose cosine similarity to unit vector `q` is exactly
    `cosine` — lets a test plant a match at a KNOWN closeness relative to the
    floor. Build an orthonormal companion `e ⟂ q`, then c·q + √(1-c²)·e."""
    a = [0.0] * len(q)
    a[0] = 1.0
    dot = sum(a[i] * q[i] for i in range(len(q)))
    e = [a[i] - dot * q[i] for i in range(len(q))]
    norm = math.sqrt(sum(x * x for x in e))
    e = [x / norm for x in e]
    s = math.sqrt(1.0 - cosine * cosine)
    return [cosine * q[i] + s * e[i] for i in range(len(q))]


def _plant_chunk(
    db_session: AsyncSession,
    *,
    document_id: UUID,
    tenant: UUID,
    ordinal: int,
    text: str,
    embedding: list[float],
    model: str = "mock-embed-1",
) -> None:
    db_session.add(
        DocumentChunk(
            document_id=document_id,
            organization_id=tenant,
            ordinal=ordinal,
            text=text,
            embedding=embedding,
            embedding_model=model,
            char_start=0,
            char_end=1,
        )
    )


async def _make_second_user_in_org(
    client: AsyncClient, db_session: AsyncSession, *, email: str, organization_id: UUID
) -> dict[str, Any]:
    """Register a second user, move them into `organization_id`, and log in so
    their active tenant is the shared org (mirrors test_search_documents_tool)."""
    reg = await _register(client, email)
    user_id = UUID(reg["user_id"])
    role = (await db_session.execute(select(Role).where(Role.name == "owner"))).scalar_one()
    db_session.add(
        Membership(
            user_id=user_id,
            organization_id=organization_id,
            role_id=role.id,
            status="active",
            created_at=datetime.now(UTC),
        )
    )
    await db_session.commit()
    stmt = (
        select(Membership)
        .where(Membership.user_id == user_id)
        .where(Membership.organization_id != organization_id)
    )
    for m in (await db_session.execute(stmt)).scalars().all():
        await db_session.delete(m)
    await db_session.commit()
    login = await client.post(
        "/api/v1/auth/login", json={"email": email, "password": "password12345"}
    )
    assert login.status_code == 200, login.text
    return login.json()  # type: ignore[no-any-return]


# --- citation: filename + boundary-spanning position -------------------------


@pytest.mark.asyncio
async def test_result_carries_structured_position_and_rendered_citation(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "8e1-cite@example.com")
        tenant = UUID(reg["active_tenant_id"])
        user = UUID(reg["user_id"])
        doc_id = await _ingest(app_session_factory, tenant=tenant, user=user, filename="paper.pdf")

        s = await app_session_factory(tenant)
        try:
            chunks = await DocumentRepository(s).list_chunks(doc_id)
        finally:
            await s.close()
        # A boundary-spanning chunk straddles two pages → render() gives "pp. N-M".
        boundary = next(ch for ch in chunks if ch.page_start != ch.page_end)
        expected = DocumentPosition(
            char_start=boundary.char_start,
            char_end=boundary.char_end,
            page_start=boundary.page_start,
            page_end=boundary.page_end,
            section=boundary.section,
        ).render()
        assert expected.startswith("pp. ")  # the case citations exist for

        r = await c.post(
            "/api/v1/documents/search",
            headers=_auth(reg),
            json={"query": boundary.text},  # exact text → this chunk ranks #1
        )
        assert r.status_code == 200, r.text
        results = r.json()
        hit = next(h for h in results if h["text"] == boundary.text)

        assert hit["document_id"] == str(doc_id)
        assert hit["filename"] == "paper.pdf"
        assert hit["similarity"] >= 0.99  # queried its own text
        # Structured position for linking/highlighting.
        assert hit["position"]["char_start"] == boundary.char_start
        assert hit["position"]["char_end"] == boundary.char_end
        assert hit["position"]["page_start"] == boundary.page_start
        assert hit["position"]["page_end"] == boundary.page_end
        # AND the server-rendered citation string, matching DocumentPosition.render().
        assert hit["citation"] == expected
        assert hit["citation"].startswith("pp. ")


# --- floor: a below-floor match is ABSENT (not flagged) ----------------------


@pytest.mark.asyncio
async def test_below_floor_result_is_omitted_entirely(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
    db_session: AsyncSession,
) -> None:
    db_app.state.settings.document_search_min_similarity = 0.5
    query = "floor-probe distinctive phrase"
    q = await _query_vector(query)

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "8e1-floor@example.com")
        tenant = UUID(reg["active_tenant_id"])
        user = UUID(reg["user_id"])
        doc_id = await _ingest(app_session_factory, tenant=tenant, user=user, filename="f.pdf")

        # STRONG (cosine 1.0 ≥ floor) and WEAK (cosine 0.3 < floor) planted matches.
        _plant_chunk(
            db_session,
            document_id=doc_id,
            tenant=tenant,
            ordinal=900,
            text="STRONG floor match",
            embedding=q,
        )
        _plant_chunk(
            db_session,
            document_id=doc_id,
            tenant=tenant,
            ordinal=901,
            text="WEAK floor match",
            embedding=_vec_at_cosine(q, 0.3),
        )
        await db_session.commit()

        r = await c.post("/api/v1/documents/search", headers=_auth(reg), json={"query": query})
        assert r.status_code == 200, r.text
        texts = [h["text"] for h in r.json()]
        assert "STRONG floor match" in texts  # above floor → present
        assert "WEAK floor match" not in texts  # below floor → ABSENT, not flagged


# --- embedding_model guard ---------------------------------------------------


@pytest.mark.asyncio
async def test_foreign_model_chunk_excluded_even_when_vector_matches(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
    db_session: AsyncSession,
) -> None:
    query = "model-guard probe"
    q = await _query_vector(query)

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "8e1-modelguard@example.com")
        tenant = UUID(reg["active_tenant_id"])
        user = UUID(reg["user_id"])
        doc_id = await _ingest(app_session_factory, tenant=tenant, user=user, filename="real.pdf")

        _plant_chunk(
            db_session,
            document_id=doc_id,
            tenant=tenant,
            ordinal=800,
            text="REAL match",
            embedding=q,
        )
        # Same vector, foreign model — would rank #1 if the guard weren't applied.
        _plant_chunk(
            db_session,
            document_id=doc_id,
            tenant=tenant,
            ordinal=801,
            text="POISON foreign vector-space row",
            embedding=q,
            model="foreign-model-1",
        )
        await db_session.commit()

        r = await c.post("/api/v1/documents/search", headers=_auth(reg), json={"query": query})
        assert r.status_code == 200, r.text
        texts = [h["text"] for h in r.json()]
        assert "REAL match" in texts
        assert "POISON foreign vector-space row" not in texts  # 5d guard


# --- whitelist: no full_text, no embedding vector ----------------------------


@pytest.mark.asyncio
async def test_response_omits_full_text_and_embedding_vector(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "8e1-whitelist@example.com")
        tenant = UUID(reg["active_tenant_id"])
        user = UUID(reg["user_id"])
        doc_id = await _ingest(app_session_factory, tenant=tenant, user=user, filename="w.pdf")
        s = await app_session_factory(tenant)
        try:
            chunk = (await DocumentRepository(s).list_chunks(doc_id))[0]
        finally:
            await s.close()

        r = await c.post("/api/v1/documents/search", headers=_auth(reg), json={"query": chunk.text})
        assert r.status_code == 200, r.text
        hit = next(h for h in r.json() if h["text"] == chunk.text)
        assert "full_text" not in hit
        assert "embedding" not in hit
        # Exact field whitelist — nothing leaks by accident.
        assert set(hit) == {"document_id", "filename", "text", "similarity", "position", "citation"}


# --- soft delete -------------------------------------------------------------


@pytest.mark.asyncio
async def test_soft_deleted_document_absent_from_search(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "8e1-softdel@example.com")
        tenant = UUID(reg["active_tenant_id"])
        user = UUID(reg["user_id"])
        doc_id = await _ingest(app_session_factory, tenant=tenant, user=user, filename="gone.pdf")
        s = await app_session_factory(tenant)
        try:
            chunk_text = (await DocumentRepository(s).list_chunks(doc_id))[0].text
        finally:
            await s.close()

        r = await c.post("/api/v1/documents/search", headers=_auth(reg), json={"query": chunk_text})
        assert any(h["text"] == chunk_text for h in r.json())  # findable first

        d = await c.delete(f"/api/v1/documents/{doc_id}", headers=_auth(reg))
        assert d.status_code == 204
        r2 = await c.post(
            "/api/v1/documents/search", headers=_auth(reg), json={"query": chunk_text}
        )
        assert r2.status_code == 200
        assert r2.json() == []  # soft-deleted doc excludes its chunks


# --- tenant isolation (through HTTP) -----------------------------------------


@pytest.mark.asyncio
async def test_tenant_B_search_never_returns_tenant_A_chunks(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        alice = await _register(c, "8e1-tenantA@example.com")
        a_tenant = UUID(alice["active_tenant_id"])
        a_user = UUID(alice["user_id"])
        doc_id = await _ingest(
            app_session_factory, tenant=a_tenant, user=a_user, filename="alice-secret.pdf"
        )
        s = await app_session_factory(a_tenant)
        try:
            chunk_text = (await DocumentRepository(s).list_chunks(doc_id))[0].text
        finally:
            await s.close()

        bob = await _register(c, "8e1-tenantB@example.com")
        r = await c.post("/api/v1/documents/search", headers=_auth(bob), json={"query": chunk_text})
        assert r.status_code == 200, r.text
        assert r.json() == []  # RLS-scoped: B never sees A's chunks


# --- cross-user WITHIN a tenant (deliberate diff from memory) ----------------


@pytest.mark.asyncio
async def test_colleague_in_same_org_can_search_the_document(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
    db_session: AsyncSession,
) -> None:
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        alice = await _register(c, "8e1-org-alice@example.com")
        org = UUID(alice["active_tenant_id"])
        a_user = UUID(alice["user_id"])
        doc_id = await _ingest(
            app_session_factory, tenant=org, user=a_user, filename="shared-policy.pdf"
        )
        s = await app_session_factory(org)
        try:
            chunk_text = (await DocumentRepository(s).list_chunks(doc_id))[0].text
        finally:
            await s.close()

        bob = await _make_second_user_in_org(
            c, db_session, email="8e1-org-bob@example.com", organization_id=org
        )
        r = await c.post(
            "/api/v1/documents/search",
            headers={"Authorization": f"Bearer {bob['access_token']}"},
            json={"query": chunk_text},
        )
        assert r.status_code == 200, r.text
        # Org-scoped (unlike per-user memory): the colleague finds the teammate's doc.
        assert any(h["filename"] == "shared-policy.pdf" for h in r.json())


# --- auth --------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_without_token_is_401(db_client: AsyncClient) -> None:
    r = await db_client.post("/api/v1/documents/search", json={"query": "anything"})
    assert r.status_code == 401
