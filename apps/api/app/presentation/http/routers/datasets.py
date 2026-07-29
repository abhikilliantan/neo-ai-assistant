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
from app.infrastructure.db.repositories import DatasetRepository
from app.presentation.http.deps import (
    CurrentTenantDep,
    CurrentUserDep,
    SettingsDep,
    TenantSessionDep,
)
from app.presentation.http.multipart import sanitize_filename
from app.presentation.http.schemas.datasets import (
    DatasetColumnOut,
    DatasetDetail,
    DatasetIngestResponse,
    DatasetSummary,
)
from app.shared.exceptions.auth import AuthenticationError
from app.shared.exceptions.common import NotFoundError
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
    allow_duplicate_name: Annotated[bool, Form()] = False,
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
        allow_duplicate_name=allow_duplicate_name,
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


@router.get("/datasets", response_model=list[DatasetSummary])
async def list_datasets(
    tenant_id: CurrentTenantDep,
    session: TenantSessionDep,
) -> list[DatasetSummary]:
    """The tenant's datasets, newest-first. `list_datasets` filters by
    organization_id explicitly (not via RLS), matching the repo convention."""
    if tenant_id is None:
        raise AuthenticationError("user has no active tenant")
    datasets = await DatasetRepository(session).list_datasets(tenant_id)
    return [
        DatasetSummary(
            dataset_id=d.id,
            name=d.name,
            row_count=d.row_count,
            sheet_name=d.sheet_name,
            created_at=d.created_at,
        )
        for d in datasets
    ]


@router.get("/datasets/{dataset_id}", response_model=DatasetDetail)
async def get_dataset(
    dataset_id: UUID,
    tenant_id: CurrentTenantDep,
    session: TenantSessionDep,
) -> DatasetDetail:
    """One dataset + its typed columns. An unknown id OR another tenant's dataset
    both collapse to 404 (no existence oracle) — the org check is explicit, not
    RLS-reliant, matching the 1c query service."""
    if tenant_id is None:
        raise AuthenticationError("user has no active tenant")
    repo = DatasetRepository(session)
    dataset = await repo.get_dataset(dataset_id)
    if dataset is None or dataset.organization_id != tenant_id or dataset.deleted_at is not None:
        raise NotFoundError("dataset not found")
    columns = await repo.get_columns(dataset_id)
    return DatasetDetail(
        dataset_id=dataset.id,
        name=dataset.name,
        row_count=dataset.row_count,
        sheet_name=dataset.sheet_name,
        created_at=dataset.created_at,
        columns=[
            DatasetColumnOut(
                name=c.name,
                key=c.key,
                data_type=c.data_type,
                semantic_role=c.semantic_role,
            )
            for c in columns
        ],
    )
