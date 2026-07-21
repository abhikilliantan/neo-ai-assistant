"""Document upload + management endpoints (8c). Wires 8b's ingest pipeline to HTTP.

⚠️ This is where UNTRUSTED FILES enter the system. The security-critical work
(streaming size guard, content-type allowlist, filename sanitization) lives in
`multipart.read_upload` + `sanitize_filename`; this router orchestrates them and
maps failures to the standard error envelope.

All routes run under TenantSessionDep, so Postgres RLS filters cross-tenant rows
first and the tenant GUC is always set (no '' ::uuid landmine). The upload route
never commits and never swallows the ingest exception, so 8b's all-or-nothing
transaction property holds through HTTP: success commits at dep teardown, any
failure rolls the whole thing back (zero documents, zero chunks).
"""

from __future__ import annotations

import asyncio
from uuid import UUID

from fastapi import APIRouter, Request, status
from fastapi.responses import Response

from app.infrastructure.db.models import Document
from app.infrastructure.db.repositories import DocumentRepository
from app.presentation.http.deps import (
    CurrentTenantDep,
    CurrentUserDep,
    DocumentIngestDep,
    SettingsDep,
    TenantSessionDep,
)
from app.presentation.http.multipart import read_upload
from app.presentation.http.schemas.documents import DocumentOut
from app.shared.exceptions.auth import AuthenticationError
from app.shared.exceptions.common import NotFoundError
from app.shared.exceptions.documents import DocumentParseError, UnsupportedContentTypeError

router = APIRouter(prefix="/api/v1", tags=["documents"])


@router.post("/documents", response_model=DocumentOut)
async def upload_document(
    request: Request,
    user: CurrentUserDep,
    tenant_id: CurrentTenantDep,
    session: TenantSessionDep,
    settings: SettingsDep,
    ingest: DocumentIngestDep,
) -> DocumentOut:
    # ⚠️ NO-ORIGINAL-STORAGE DECISION (8c): we persist only the extracted
    # full_text (8b), never the uploaded bytes. Consequence: when 8f ships a
    # better parser, its improvements apply ONLY to NEW uploads — re-indexing an
    # existing corpus means the user must RE-UPLOAD, since the original bytes are
    # gone. Therefore original-file storage (object storage or a volume, with
    # retention/deletion) is a GO-LIVE GATE, not a nice-to-have: it must land
    # BEFORE real tenants ingest real volume, or that corpus is permanently
    # stuck on whatever parser extracted it the first time.
    if tenant_id is None:
        raise AuthenticationError("user has no active tenant")

    # Streaming size guard + multipart parse (→413 oversized / →400 malformed).
    upload = await read_upload(request, max_bytes=settings.document_max_bytes)

    # The part's declared content-type is ATTACKER-CONTROLLED. Normalize (drop
    # params, lowercase) and check against the allowlist → 415 if not accepted.
    declared_type = upload.content_type.split(";")[0].strip().lower()
    if declared_type not in settings.document_allowed_content_types_set:
        raise UnsupportedContentTypeError("unsupported document content type")

    # Enforce the parse/processing budget at the call site. NOTE: wait_for cannot
    # interrupt CPU-bound sync work — it only cancels at await points. Adequate
    # for the mock/cooperative parser today; 8f's real parser needs process-level
    # isolation to defend against a CPU/decompression bomb.
    try:
        document = await asyncio.wait_for(
            ingest.ingest(
                session,
                organization_id=tenant_id,
                uploaded_by_user_id=user.id,
                filename=upload.filename,
                content_type=declared_type,
                data=upload.data,
            ),
            timeout=settings.document_parse_timeout_seconds,
        )
    except TimeoutError as e:
        # Timed-out processing collapses into the same client-facing 422 as a
        # corrupt document — the file couldn't be turned into a document.
        raise DocumentParseError("document processing timed out") from e

    chunk_count = await DocumentRepository(session).count_chunks(document.id)
    return _to_out(document, chunk_count)


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    tenant_id: CurrentTenantDep,
    session: TenantSessionDep,
) -> list[DocumentOut]:
    if tenant_id is None:
        raise AuthenticationError("user has no active tenant")
    rows = await DocumentRepository(session).list_for_org_with_chunk_counts(tenant_id)
    return [_to_out(doc, n) for doc, n in rows]


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: UUID,
    tenant_id: CurrentTenantDep,
    session: TenantSessionDep,
) -> Response:
    if tenant_id is None:
        raise AuthenticationError("user has no active tenant")
    repo = DocumentRepository(session)
    doc = await repo.get_document(document_id)
    # None → unknown id OR another tenant's doc (RLS-hidden). Both collapse to
    # 404 — no existence oracle. Documents are org-scoped, so any user in the
    # tenant may delete the tenant's document (no per-user ownership check).
    if doc is None or doc.deleted_at is not None:
        raise NotFoundError("document not found")
    await repo.soft_delete(document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _to_out(document: Document, chunk_count: int) -> DocumentOut:
    # Whitelist fields explicitly — full_text is never included (see schemas).
    return DocumentOut(
        id=document.id,
        filename=document.filename,
        content_type=document.content_type,
        byte_size=document.byte_size,
        status=document.status,
        chunk_count=chunk_count,
        created_at=document.created_at,
    )
