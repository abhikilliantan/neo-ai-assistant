"""Phase 8c — document upload endpoint. Security-focused: this is where
untrusted files enter the system.

Covers the load-bearing properties:
  - oversized upload is rejected WHILE streaming (never buffers the whole body),
  - the content-type allowlist rejects disallowed types (415),
  - filenames are sanitized (no traversal / control chars / unbounded length),
  - 8b's all-or-nothing transaction survives the HTTP layer,
  - cross-tenant isolation (404, no existence oracle), soft-delete, and the
    full_text field never crossing the API boundary.
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.documents.chunker import FixedSizeChunker
from app.ai.documents.ingest import DocumentIngestService
from app.ai.documents.mock import MockDocumentParser
from app.ai.providers.embeddings.mock import MockEmbeddingProvider
from app.application.ports.embeddings import EmbeddingResult, InputType
from app.infrastructure.db.models import Document, DocumentChunk
from app.infrastructure.db.repositories import DocumentRepository
from app.presentation.http.multipart import read_upload, sanitize_filename
from app.shared.exceptions.common import BadRequestError
from app.shared.exceptions.documents import DocumentTooLargeError
from app.shared.exceptions.embeddings import EmbeddingProviderUnavailableError

_PDF = "application/pdf"


async def _register(client: AsyncClient, email: str) -> dict[str, Any]:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password12345"},
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def _auth(reg: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {reg['access_token']}"}


# --- filename sanitization (unit) -------------------------------------------


def test_sanitize_filename_defeats_traversal_control_chars_and_length() -> None:
    # Path traversal → basename only, both separators.
    assert sanitize_filename("../../etc/passwd") == "passwd"
    assert sanitize_filename("..\\..\\windows\\system32\\cmd.exe") == "cmd.exe"
    assert sanitize_filename("/absolute/path/report.pdf") == "report.pdf"
    # Control characters stripped.
    cleaned = sanitize_filename("a\x00\x07\x1bb.pdf")
    assert cleaned == "ab.pdf"
    assert all(c.isprintable() for c in cleaned)
    # Length bounded.
    assert sanitize_filename("x" * 500) == "x" * 255
    # Degenerate inputs fall back, never "" / "." / "..".
    assert sanitize_filename("") == "upload"
    assert sanitize_filename("..") == "upload"
    assert sanitize_filename("/") == "upload"


# --- streaming size guard (unit): proves early abort ------------------------


class _FakeStreamRequest:
    """Minimal Request stand-in that COUNTS how many chunks get consumed, so the
    test can prove the reader stopped early instead of buffering everything."""

    def __init__(self, chunks: list[bytes]) -> None:
        self.headers = {"content-type": "multipart/form-data; boundary=B"}
        self._chunks = chunks
        self.consumed = 0

    async def stream(self):  # type: ignore[no-untyped-def]
        for c in self._chunks:
            self.consumed += 1
            yield c


@pytest.mark.asyncio
async def test_read_upload_aborts_before_consuming_the_whole_body() -> None:
    # 10 chunks of 100 bytes = 1000 total; limit 250 -> must fail after 3 chunks.
    req = _FakeStreamRequest([b"x" * 100 for _ in range(10)])
    with pytest.raises(DocumentTooLargeError):
        await read_upload(req, max_bytes=250)
    # The proof: it did NOT read all 10 chunks. A "read everything first"
    # implementation would have consumed all 10 before checking the size.
    assert req.consumed == 3
    assert req.consumed < 10


@pytest.mark.asyncio
async def test_read_upload_rejects_non_multipart() -> None:
    class _JsonReq:
        def __init__(self) -> None:
            self.headers = {"content-type": "application/json"}

        async def stream(self):  # type: ignore[no-untyped-def]
            yield b"{}"

    with pytest.raises(BadRequestError):
        await read_upload(_JsonReq(), max_bytes=1000)


# --- happy path -------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_persists_document_and_chunks_and_appears_in_list(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    reg = await _register(db_client, "alice@docs8c.example")
    r = await db_client.post(
        "/api/v1/documents",
        files={"file": ("paper.pdf", b"%PDF-1.4 anything at all", _PDF)},
        headers=_auth(reg),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["filename"] == "paper.pdf"
    assert body["content_type"] == _PDF
    assert body["byte_size"] == len(b"%PDF-1.4 anything at all")
    assert body["status"] == "ready"
    assert body["chunk_count"] >= 1
    assert "full_text" not in body  # whitelist discipline — never leaks

    # Chunks really landed with provenance (deeper round-trip proven in 8b).
    chunks = (await db_session.execute(select(DocumentChunk))).scalars().all()
    assert len(chunks) == body["chunk_count"]
    assert all(c.char_start is not None and c.char_end is not None for c in chunks)

    # Appears in the tenant's list with the same chunk count, no full_text.
    lst = await db_client.get("/api/v1/documents", headers=_auth(reg))
    assert lst.status_code == 200
    rows = lst.json()
    assert len(rows) == 1
    assert rows[0]["id"] == body["id"]
    assert rows[0]["chunk_count"] == body["chunk_count"]
    assert "full_text" not in rows[0]


@pytest.mark.asyncio
async def test_traversal_filename_is_basenamed_in_the_stored_document(
    db_client: AsyncClient,
) -> None:
    reg = await _register(db_client, "alice@fname8c.example")
    r = await db_client.post(
        "/api/v1/documents",
        files={"file": ("../../etc/passwd", b"%PDF-1.4 data", _PDF)},
        headers=_auth(reg),
    )
    assert r.status_code == 200, r.text
    assert r.json()["filename"] == "passwd"  # no path components stored


# --- content-type allowlist -------------------------------------------------


@pytest.mark.asyncio
async def test_disallowed_content_type_returns_415(db_client: AsyncClient) -> None:
    reg = await _register(db_client, "alice@ctype8c.example")
    r = await db_client.post(
        "/api/v1/documents",
        files={"file": ("evil.bin", b"data", "application/x-msdownload")},
        headers=_auth(reg),
    )
    assert r.status_code == 415, r.text
    assert r.json()["error"]["code"] == "unsupported_content_type"


# --- oversized upload -------------------------------------------------------


@pytest.mark.asyncio
async def test_oversized_upload_returns_413(db_app: FastAPI, db_client: AsyncClient) -> None:
    db_app.state.settings.document_max_bytes = 512  # tighten for the test
    reg = await _register(db_client, "alice@big8c.example")
    r = await db_client.post(
        "/api/v1/documents",
        files={"file": ("big.pdf", b"x" * 4096, _PDF)},  # well over 512
        headers=_auth(reg),
    )
    assert r.status_code == 413, r.text
    assert r.json()["error"]["code"] == "document_too_large"


# --- all-or-nothing survives the route --------------------------------------


class _BoomEmbeddingProvider:
    @property
    def dimension(self) -> int:
        return 1024

    async def embed(
        self, *, texts: list[str], input_type: InputType = "document"
    ) -> EmbeddingResult:
        # A typed provider failure → mapped 5xx response (not a re-raised 500).
        raise EmbeddingProviderUnavailableError("embed boom")


@pytest.mark.asyncio
async def test_upload_unsupported_type_rejected_with_415_not_fabricated(
    db_app: FastAPI, db_client: AsyncClient, db_session: AsyncSession
) -> None:
    # Production default ("reject"): pdf/docx have no real parser → 415 with a
    # message naming what's supported, and NO document/chunks are fabricated.
    from app.ai.documents.dispatch import ContentTypeDocumentParser
    from app.ai.documents.text import TextDocumentParser

    db_app.state.document_ingest = DocumentIngestService(
        parser=ContentTypeDocumentParser(
            text_parser=TextDocumentParser(max_bytes=1_000_000), fallback=None
        ),
        chunker=FixedSizeChunker(chunk_size=1000, overlap=200),
        embedding_provider=MockEmbeddingProvider(),
        chunk_size=1000,
        embedding_model="voyage-3.5",
    )
    reg = await _register(db_client, "alice@reject8.example")
    r = await db_client.post(
        "/api/v1/documents",
        files={"file": ("paper.pdf", b"%PDF-1.7 anything", _PDF)},
        headers=_auth(reg),
    )
    assert r.status_code == 415, r.text
    body = r.json()
    assert body["error"]["code"] == "unsupported_content_type"
    assert "PDF and Word" in body["error"]["message"]  # names what's supported / coming

    doc_n = (await db_session.execute(select(func.count()).select_from(Document))).scalar_one()
    assert doc_n == 0  # nothing fabricated, nothing persisted


@pytest.mark.asyncio
async def test_ingest_failure_leaves_zero_documents_and_chunks(
    db_app: FastAPI, db_client: AsyncClient, db_session: AsyncSession
) -> None:
    # Swap in an ingest service whose embed step fails MID-INGEST (after the
    # document row is created). All-or-nothing must roll it all back.
    db_app.state.document_ingest = DocumentIngestService(
        parser=MockDocumentParser(max_bytes=1_000_000),
        chunker=FixedSizeChunker(chunk_size=1000, overlap=200),
        embedding_provider=_BoomEmbeddingProvider(),
        chunk_size=1000,
        embedding_model="voyage-3.5",
    )
    reg = await _register(db_client, "alice@boom8c.example")
    r = await db_client.post(
        "/api/v1/documents",
        files={"file": ("paper.pdf", b"%PDF-1.4 anything", _PDF)},
        headers=_auth(reg),
    )
    assert r.status_code >= 500  # provider/ingest failure surfaces as 5xx

    doc_n = (await db_session.execute(select(func.count()).select_from(Document))).scalar_one()
    chunk_n = (
        await db_session.execute(select(func.count()).select_from(DocumentChunk))
    ).scalar_one()
    assert doc_n == 0
    assert chunk_n == 0


# --- cross-tenant isolation -------------------------------------------------


@pytest.mark.asyncio
async def test_cross_tenant_cannot_list_or_delete(db_client: AsyncClient) -> None:
    alice = await _register(db_client, "alice@iso8c.example")
    bob = await _register(db_client, "bob@iso8c.example")

    up = await db_client.post(
        "/api/v1/documents",
        files={"file": ("alice.pdf", b"%PDF-1.4 secret", _PDF)},
        headers=_auth(alice),
    )
    assert up.status_code == 200
    alice_doc_id = up.json()["id"]

    # Bob's list is empty — never sees Alice's document.
    bob_list = await db_client.get("/api/v1/documents", headers=_auth(bob))
    assert bob_list.status_code == 200
    assert bob_list.json() == []

    # Bob deleting Alice's doc → 404 (no existence oracle), not 403.
    bob_del = await db_client.delete(f"/api/v1/documents/{alice_doc_id}", headers=_auth(bob))
    assert bob_del.status_code == 404
    assert bob_del.json()["error"]["code"] == "not_found"

    # Alice still sees it (nothing was actually deleted).
    alice_list = await db_client.get("/api/v1/documents", headers=_auth(alice))
    assert [d["id"] for d in alice_list.json()] == [alice_doc_id]


@pytest.mark.asyncio
async def test_delete_unknown_id_returns_404(db_client: AsyncClient) -> None:
    reg = await _register(db_client, "alice@unknown8c.example")
    r = await db_client.delete(
        "/api/v1/documents/00000000-0000-0000-0000-000000000001",
        headers=_auth(reg),
    )
    assert r.status_code == 404


# --- soft delete ------------------------------------------------------------


@pytest.mark.asyncio
async def test_soft_delete_excludes_from_list_and_search(
    db_client: AsyncClient, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    from uuid import UUID

    reg = await _register(db_client, "alice@del8c.example")
    tenant_id = UUID(reg["active_tenant_id"])
    up = await db_client.post(
        "/api/v1/documents",
        files={"file": ("paper.pdf", b"%PDF-1.4 anything", _PDF)},
        headers=_auth(reg),
    )
    assert up.status_code == 200
    doc_id = up.json()["id"]

    d = await db_client.delete(f"/api/v1/documents/{doc_id}", headers=_auth(reg))
    assert d.status_code == 204

    # Gone from the list.
    lst = await db_client.get("/api/v1/documents", headers=_auth(reg))
    assert lst.json() == []

    # Gone from chunk search (soft-deleted document excludes its chunks).
    query_vec = (await MockEmbeddingProvider().embed(texts=["anything"])).vectors[0]
    s = await app_session_factory(tenant_id)
    try:
        results = await DocumentRepository(s).search_chunks(
            organization_id=tenant_id,
            query_embedding=query_vec,
            limit=10,
            embedding_model="mock-embed-1",
        )
        assert results == []
    finally:
        await s.close()


# --- GUC helper (defuses the ''::uuid landmine at the session layer) --------


@pytest.mark.asyncio
async def test_set_tenant_guc_nil_sentinel_returns_zero_rows_not_error(
    app_engine, db_session: AsyncSession
) -> None:  # type: ignore[no-untyped-def]
    """set_tenant_guc(session, None) sets a valid nil UUID, so a query on a
    tenant table returns 0 rows rather than 500-ing on the ''::uuid cast that a
    recycled pooled connection would otherwise trigger."""
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.infrastructure.db.models import Organization
    from app.presentation.http.deps import set_tenant_guc

    # Seed a document as neo so a leaking query WOULD have a row to expose.
    org = Organization(name="Guc Org", slug="guc-8c")
    db_session.add(org)
    await db_session.flush()
    db_session.add(
        Document(
            organization_id=org.id,
            uploaded_by_user_id=None,
            filename="x.pdf",
            content_type=_PDF,
            byte_size=1,
            full_text="x",
        )
    )
    await db_session.commit()

    sm = async_sessionmaker(app_engine, expire_on_commit=False)
    async with sm() as s:
        await s.begin()
        await set_tenant_guc(s, None)  # no tenant → nil sentinel, valid ::uuid
        rows = (await s.execute(select(Document))).scalars().all()
        assert rows == []  # nil matches no org → 0 rows, and crucially NO error
        await s.rollback()
