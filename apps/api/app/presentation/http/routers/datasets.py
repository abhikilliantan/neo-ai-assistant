"""Structured-data ingestion endpoint (Capability 1, Slice 1b).

POST /api/v1/datasets/ingest — multipart upload of a tracker/spreadsheet
(.xlsx/.csv) → a Dataset + typed columns + JSONB rows, all in ONE tenant
transaction (committed at session teardown). Uses FastAPI's Form/File so the
optional metadata fields ride alongside the file part.

Validation ordering mirrors the documents route: the cheap 415 type gate and the
byte cap run BEFORE any parse work. An xlsx must be a real ZIP (`PK\\x03\\x04`)
before its bytes reach openpyxl.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, File, Form, UploadFile

from app.ai.datasets.ingest import detect_kind, ingest_spreadsheet
from app.presentation.http.deps import (
    CurrentTenantDep,
    CurrentUserDep,
    SettingsDep,
    TenantSessionDep,
)
from app.presentation.http.multipart import sanitize_filename
from app.presentation.http.schemas.datasets import DatasetColumnOut, DatasetIngestResponse
from app.shared.exceptions.auth import AuthenticationError
from app.shared.exceptions.documents import DocumentTooLargeError, UnsupportedContentTypeError

router = APIRouter(prefix="/api/v1", tags=["datasets"])

# xlsx (like docx) is a ZIP; sniff the signature before handing bytes to openpyxl.
_ZIP_SIGNATURE = b"PK\x03\x04"


@router.post("/datasets/ingest", response_model=DatasetIngestResponse)
async def ingest_dataset(
    user: CurrentUserDep,
    tenant_id: CurrentTenantDep,
    session: TenantSessionDep,
    settings: SettingsDep,
    file: Annotated[UploadFile, File()],
    name: Annotated[str | None, Form()] = None,
    sheet_name: Annotated[str | None, Form()] = None,
    header_row_index: Annotated[int, Form()] = 0,
    replace_dataset_id: Annotated[UUID | None, Form()] = None,
) -> DatasetIngestResponse:
    if tenant_id is None:
        raise AuthenticationError("user has no active tenant")

    filename = sanitize_filename(file.filename or "upload")
    # (a) 415 gate — resolve the kind from the (attacker-controlled) filename /
    # declared type BEFORE reading or parsing.
    kind = detect_kind(filename, file.content_type)
    if kind is None:
        raise UnsupportedContentTypeError("unsupported spreadsheet type (expected .xlsx or .csv)")

    data = await file.read()
    if len(data) > settings.document_max_bytes:
        raise DocumentTooLargeError("upload exceeds the configured size limit")
    # (a2) Magic sniff: a declared xlsx that isn't a ZIP never reaches openpyxl.
    if kind == "xlsx" and not data.startswith(_ZIP_SIGNATURE):
        raise UnsupportedContentTypeError("file content does not match its declared type")

    result = await ingest_spreadsheet(
        session,
        organization_id=tenant_id,
        created_by=user.id,
        filename=filename,
        data=data,
        kind=kind,
        name=name,
        sheet_name=sheet_name,
        header_row_index=header_row_index,
        replace_dataset_id=replace_dataset_id,
    )
    return DatasetIngestResponse(
        dataset_id=result.dataset_id,
        name=result.name,
        row_count=result.row_count,
        columns=[
            DatasetColumnOut(
                name=c.name,
                key=c.key,
                data_type=c.data_type,
                semantic_role=c.semantic_role,
            )
            for c in result.columns
        ],
    )
