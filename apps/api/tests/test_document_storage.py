"""ADR 0002 slice 1 — original file storage.

The load-bearing properties: original bytes are RETAINED (round-trip), the
pointer/provenance/hash persist, and the WRITE ORDERING holds — a rejected type
never orphans (415 before store), and any post-store failure leaves no row AND no
orphaned bytes (compensating delete). Tenant isolation outside RLS is proven at
the pointer-row gate: a foreign tenant cannot obtain another tenant's storage key.

All hermetic — the store is a per-test temp directory (conftest), no network.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.documents.chunker import FixedSizeChunker
from app.ai.documents.docx import DOCX_CONTENT_TYPE
from app.ai.documents.ingest import DocumentIngestService
from app.ai.documents.mock import MockDocumentParser
from app.ai.documents.pdf import PDF_CONTENT_TYPE
from app.application.ports.embeddings import EmbeddingResult, InputType
from app.infrastructure.db.models import Document
from app.infrastructure.storage import probe_storage_writable
from app.infrastructure.storage.filesystem import LocalFilesystemStorage
from app.shared.exceptions.documents import DocumentParseError
from app.shared.exceptions.embeddings import EmbeddingProviderUnavailableError

_PDF = "application/pdf"


async def _register(client: AsyncClient, email: str) -> dict[str, Any]:
    r = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "password12345"}
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def _auth(reg: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {reg['access_token']}"}


def _files_under(root: Path) -> list[Path]:
    return [p for p in root.rglob("*") if p.is_file()]


def _stored_files(app: FastAPI) -> list[Path]:
    """Every regular file currently in the store's root (a per-test temp dir)."""
    return _files_under(Path(app.state.storage._root))  # FS backend root introspection


async def _load_doc(app_session_factory: Any, tenant: UUID, doc_id: UUID) -> Document | None:
    s = await app_session_factory(tenant)
    try:
        return await s.get(Document, doc_id)
    finally:
        await s.close()


# --- happy path: retention + round-trip + provenance/hash --------------------


@pytest.mark.asyncio
async def test_upload_stores_original_bytes_and_round_trips(
    db_app: FastAPI, db_client: AsyncClient, app_session_factory: Any
) -> None:
    reg = await _register(db_client, "alice@store.example")
    tenant = UUID(reg["active_tenant_id"])
    payload = b"%PDF-1.7 original bytes \x00\x01\x02 not the parsed text"

    r = await db_client.post(
        "/api/v1/documents",
        files={"file": ("paper.pdf", payload, _PDF)},
        headers=_auth(reg),
    )
    assert r.status_code == 200, r.text
    doc_id = UUID(r.json()["id"])

    doc = await _load_doc(app_session_factory, tenant, doc_id)
    assert doc is not None and doc.storage_key is not None
    # Round-trip: the store holds the ORIGINAL bytes, byte-identical.
    got = await db_app.state.storage.get(key=doc.storage_key)
    assert got == payload


@pytest.mark.asyncio
async def test_storage_provenance_and_hash_persisted(
    db_app: FastAPI, db_client: AsyncClient, app_session_factory: Any
) -> None:
    reg = await _register(db_client, "alice@prov.example")
    tenant = UUID(reg["active_tenant_id"])
    payload = b"%PDF-1.4 hello original document bytes"  # %PDF- passes the magic sniff

    r = await db_client.post(
        "/api/v1/documents",
        files={"file": ("n.pdf", payload, _PDF)},
        headers=_auth(reg),
    )
    assert r.status_code == 200, r.text
    doc = await _load_doc(app_session_factory, tenant, UUID(r.json()["id"]))
    assert doc is not None
    assert doc.storage_key.startswith(f"org/{tenant}/")  # org-scoped, server-minted
    assert doc.storage_backend == "filesystem"
    # Hash persisted AND matches the actually-stored bytes.
    assert doc.content_sha256 == hashlib.sha256(payload).hexdigest()
    stored = await db_app.state.storage.get(key=doc.storage_key)
    assert hashlib.sha256(stored).hexdigest() == doc.content_sha256
    # Whitelist discipline: the storage key never crosses the API boundary.
    assert "storage_key" not in r.json()


# --- ordering: 415 before store (no orphan) ----------------------------------


@pytest.mark.asyncio
async def test_415_rejection_writes_no_bytes(db_app: FastAPI, db_client: AsyncClient) -> None:
    reg = await _register(db_client, "alice@415.example")
    assert _stored_files(db_app) == []  # fresh store

    r = await db_client.post(
        "/api/v1/documents",
        files={"file": ("evil.bin", b"whatever", "application/x-msdownload")},
        headers=_auth(reg),
    )
    assert r.status_code == 415, r.text
    # The 415 gate runs BEFORE any storage write → nothing was stored.
    assert _stored_files(db_app) == []


# --- ordering: post-store failure ⇒ no row AND no orphan (compensation) -------


class _BoomEmbeddingProvider:
    @property
    def dimension(self) -> int:
        return 1024

    async def embed(
        self, *, texts: list[str], input_type: InputType = "document"
    ) -> EmbeddingResult:
        raise EmbeddingProviderUnavailableError("embed boom")


@pytest.mark.asyncio
async def test_ingest_failure_after_store_leaves_no_row_and_no_orphan(
    db_app: FastAPI, db_client: AsyncClient, db_session: AsyncSession
) -> None:
    # Store succeeds (real FS), then ingest's embed step fails → compensation must
    # fire, leaving zero rows AND zero stored bytes.
    db_app.state.document_ingest = DocumentIngestService(
        parser=MockDocumentParser(max_bytes=1_000_000),
        chunker=FixedSizeChunker(chunk_size=1000, overlap=200),
        embedding_provider=_BoomEmbeddingProvider(),
        chunk_size=1000,
        embedding_model="voyage-3.5",
    )
    reg = await _register(db_client, "alice@boom.example")
    r = await db_client.post(
        "/api/v1/documents",
        files={"file": ("p.pdf", b"%PDF-1.4 anything", _PDF)},
        headers=_auth(reg),
    )
    assert r.status_code >= 500  # provider failure surfaces as 5xx

    doc_n = (await db_session.execute(select(func.count()).select_from(Document))).scalar_one()
    assert doc_n == 0  # all-or-nothing: no row
    assert _stored_files(db_app) == []  # compensating delete fired: no orphan


# --- ordering: store-write failure ⇒ no row (store-first proven) --------------


class _BoomStorage:
    backend_id = "filesystem"

    async def put(self, *, key: str, data: bytes, content_type: str) -> None:
        raise RuntimeError("store boom")

    async def get(self, *, key: str) -> bytes:  # pragma: no cover
        raise RuntimeError("unused")

    async def delete(self, *, key: str) -> None:  # pragma: no cover
        pass

    async def exists(self, *, key: str) -> bool:  # pragma: no cover
        return False


@pytest.mark.asyncio
async def test_store_write_failure_leaves_no_row(
    db_app: FastAPI, db_client: AsyncClient, db_session: AsyncSession
) -> None:
    db_app.state.storage = _BoomStorage()
    reg = await _register(db_client, "alice@storeboom.example")
    # The store fails BEFORE ingest — an unhandled 5xx (slice 1 has no storage-error
    # mapping); ASGITransport re-raises it. The point is the invariant below.
    with pytest.raises(RuntimeError, match="store boom"):
        await db_client.post(
            "/api/v1/documents",
            files={"file": ("p.pdf", b"%PDF-1.4 anything", _PDF)},
            headers=_auth(reg),
        )
    doc_n = (await db_session.execute(select(func.count()).select_from(Document))).scalar_one()
    assert doc_n == 0  # store-first: ingest never ran, no row


# --- tenant isolation outside RLS: the pointer-row gate ----------------------


@pytest.mark.asyncio
async def test_cross_tenant_cannot_obtain_another_tenants_storage_key(
    db_app: FastAPI, db_client: AsyncClient, app_session_factory: Any
) -> None:
    alice = await _register(db_client, "alice@iso.example")
    a_tenant = UUID(alice["active_tenant_id"])
    up = await db_client.post(
        "/api/v1/documents",
        files={"file": ("secret.pdf", b"%PDF-1.4 alice secret bytes", _PDF)},
        headers=_auth(alice),
    )
    assert up.status_code == 200
    doc_id = UUID(up.json()["id"])

    bob = await _register(db_client, "bob@iso.example")
    b_tenant = UUID(bob["active_tenant_id"])

    # Bob, under HIS tenant session (RLS), cannot even see Alice's row → he can
    # never obtain her storage_key → cannot read her bytes. This is the gate: RLS
    # on the pointer table transitively protects the bytes the store can't guard.
    assert await _load_doc(app_session_factory, b_tenant, doc_id) is None

    # Proof it's isolation, not absence: Alice CAN reach it, and the bytes exist.
    alice_doc = await _load_doc(app_session_factory, a_tenant, doc_id)
    assert alice_doc is not None and alice_doc.storage_key is not None
    stored = await db_app.state.storage.get(key=alice_doc.storage_key)
    assert stored == b"%PDF-1.4 alice secret bytes"


# --- startup writability probe (ADR 0002 slice 1 hardening) -------------------


@pytest.mark.asyncio
async def test_probe_passes_and_cleans_up_on_writable_root(tmp_path: Path) -> None:
    storage = LocalFilesystemStorage(root=str(tmp_path))
    await probe_storage_writable(storage, root=str(tmp_path))  # must not raise
    # The sentinel is always deleted → nothing left behind in the root.
    assert _files_under(tmp_path) == []


class _ReadOnlyStorage:
    """Simulates a root-owned / read-only volume: put is denied. Deterministic and
    independent of the runtime user (a chmod-based test would falsely pass as root)."""

    backend_id = "filesystem"

    async def put(self, *, key: str, data: bytes, content_type: str) -> None:
        raise PermissionError(13, "Permission denied")

    async def get(self, *, key: str) -> bytes:  # pragma: no cover - never reached
        raise RuntimeError("unreachable")

    async def delete(self, *, key: str) -> None:
        pass

    async def exists(self, *, key: str) -> bool:  # pragma: no cover
        return False


@pytest.mark.asyncio
async def test_probe_fails_fast_with_clear_message_on_unwritable_root() -> None:
    root = "/var/neo/documents"
    with pytest.raises(RuntimeError) as ei:
        await probe_storage_writable(_ReadOnlyStorage(), root=root)
    msg = str(ei.value)
    assert root in msg  # names the storage root
    assert "will not start" in msg  # refuses the boot
    assert "Permission denied" in msg  # surfaces the underlying OS error


# --- ADR 0003: DOCX upload-path (hermetic, mock everywhere) -------------------


def _minimal_docx() -> bytes:
    """A real, valid .docx (PK zip) built via python-docx — passes the magic sniff."""
    import io

    from docx import Document as _Docx

    d = _Docx()
    d.add_paragraph("hello")
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


@pytest.mark.asyncio
async def test_docx_magic_number_mismatch_rejected_without_storing(
    db_app: FastAPI, db_client: AsyncClient
) -> None:
    reg = await _register(db_client, "alice@magic.example")
    assert _stored_files(db_app) == []  # fresh store
    # Declared DOCX but the bytes are not a ZIP (no PK\x03\x04) → rejected at the
    # magic sniff, BEFORE the store.
    r = await db_client.post(
        "/api/v1/documents",
        files={"file": ("fake.docx", b"this is plainly not a zip", DOCX_CONTENT_TYPE)},
        headers=_auth(reg),
    )
    assert r.status_code == 415, r.text
    assert r.json()["error"]["code"] == "unsupported_content_type"
    assert _stored_files(db_app) == []  # magic gate is BEFORE the store → nothing written


class _RaisingParser:
    async def parse(self, *, data: bytes, content_type: str):  # type: ignore[no-untyped-def]
        raise DocumentParseError("simulated parse failure")


@pytest.mark.asyncio
async def test_docx_parse_failure_leaves_no_row_and_no_orphan(
    db_app: FastAPI, db_client: AsyncClient, db_session: AsyncSession
) -> None:
    # A valid DOCX (passes the magic sniff, gets stored) whose parse then fails —
    # the store's compensating delete must fire: no Document row AND no orphan.
    db_app.state.document_ingest = DocumentIngestService(
        parser=_RaisingParser(),
        chunker=FixedSizeChunker(chunk_size=1000, overlap=200),
        embedding_provider=_BoomEmbeddingProvider(),  # never reached — parse fails first
        chunk_size=1000,
        embedding_model="voyage-3.5",
    )
    reg = await _register(db_client, "alice@docxfail.example")
    r = await db_client.post(
        "/api/v1/documents",
        files={"file": ("real.docx", _minimal_docx(), DOCX_CONTENT_TYPE)},
        headers=_auth(reg),
    )
    assert r.status_code == 422, r.text  # parse failure surfaces as 422
    doc_n = (await db_session.execute(select(func.count()).select_from(Document))).scalar_one()
    assert doc_n == 0  # no row
    assert _stored_files(db_app) == []  # compensating delete fired: no orphan


@pytest.mark.asyncio
async def test_pdf_magic_number_mismatch_rejected_without_storing(
    db_app: FastAPI, db_client: AsyncClient
) -> None:
    reg = await _register(db_client, "alice@pdfmagic.example")
    assert _stored_files(db_app) == []  # fresh store
    # Declared PDF but the bytes don't start with %PDF- → rejected at the magic
    # sniff, BEFORE the store.
    r = await db_client.post(
        "/api/v1/documents",
        files={"file": ("fake.pdf", b"not a pdf at all", PDF_CONTENT_TYPE)},
        headers=_auth(reg),
    )
    assert r.status_code == 415, r.text
    assert r.json()["error"]["code"] == "unsupported_content_type"
    assert _stored_files(db_app) == []  # magic gate is BEFORE the store → nothing written


@pytest.mark.asyncio
async def test_pdf_parse_failure_leaves_no_row_and_no_orphan(
    db_app: FastAPI, db_client: AsyncClient, db_session: AsyncSession
) -> None:
    # A file that passes the %PDF- magic sniff (so it gets stored) whose parse then
    # fails → the compensating delete must fire: no Document row AND no orphan.
    db_app.state.document_ingest = DocumentIngestService(
        parser=_RaisingParser(),
        chunker=FixedSizeChunker(chunk_size=1000, overlap=200),
        embedding_provider=_BoomEmbeddingProvider(),  # never reached — parse fails first
        chunk_size=1000,
        embedding_model="voyage-3.5",
    )
    reg = await _register(db_client, "alice@pdffail.example")
    pdf_bytes = b"%PDF-1.4 looks like a pdf but the parser rejects it"
    r = await db_client.post(
        "/api/v1/documents",
        files={"file": ("real.pdf", pdf_bytes, PDF_CONTENT_TYPE)},
        headers=_auth(reg),
    )
    assert r.status_code == 422, r.text  # parse failure surfaces as 422
    doc_n = (await db_session.execute(select(func.count()).select_from(Document))).scalar_one()
    assert doc_n == 0  # no row
    assert _stored_files(db_app) == []  # compensating delete fired: no orphan
