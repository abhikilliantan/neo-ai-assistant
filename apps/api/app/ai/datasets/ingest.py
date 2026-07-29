"""Spreadsheet ingest service (Capability 1, Slice 1b).

Parse an uploaded .xlsx/.csv → create (or replace) a Dataset with its typed
columns + JSONB rows, in the caller's tenant transaction. NO AI calls, no
embeddings — this is deterministic structured extraction.

PARSE ISOLATION: the ADR-0003 subprocess harness returns TEXT BLOCKS (its child
protocol is built around `full_text` + char offsets), which does not fit the
columns+rows shape a spreadsheet produces. Extending the harness to a second
structured-result protocol is a real piece of work, so 1b parses IN-PROCESS with
openpyxl `read_only` + the parser's row/column caps + the route's byte cap.
Follow-up: run untrusted-spreadsheet parsing under a subprocess (RLIMIT_AS +
wall-clock kill) for full zip-bomb / XXE isolation. `defusedxml` is available but
openpyxl does not expose a parser hook to plug it in cleanly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.datasets.parser import parse_spreadsheet
from app.application.ports.repositories import DatasetColumnSpec
from app.infrastructure.db.repositories import DatasetRepository
from app.shared.exceptions.common import NotFoundError
from app.shared.exceptions.datasets import DuplicateDatasetNameError

_XLSX_CONTENT_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
_CSV_CONTENT_TYPES = frozenset({"text/csv", "application/csv"})


@dataclass(frozen=True, slots=True)
class IngestResult:
    dataset_id: UUID
    name: str
    row_count: int
    columns: list[DatasetColumnSpec]


def detect_kind(filename: str | None, content_type: str | None) -> str | None:
    """Resolve 'xlsx' | 'csv' from the filename extension or declared content
    type; None → unsupported (the route maps that to 415)."""
    name = (filename or "").lower()
    ct = (content_type or "").split(";")[0].strip().lower()
    if name.endswith(".xlsx") or ct == _XLSX_CONTENT_TYPE:
        return "xlsx"
    if name.endswith(".csv") or ct in _CSV_CONTENT_TYPES:
        return "csv"
    return None


async def ingest_spreadsheet(
    session: AsyncSession,
    *,
    organization_id: UUID,
    created_by: UUID,
    filename: str,
    data: bytes,
    kind: str,
    name: str | None = None,
    sheet_name: str | None = None,
    header_row_index: int = 0,
    replace_dataset_id: UUID | None = None,
    allow_duplicate_name: bool = False,
) -> IngestResult:
    """Parse then persist. On `replace_dataset_id` the existing columns + rows are
    HARD-deleted and repopulated in place (rows carry a soft-delete mixin, so a
    replace must hard-delete to avoid unbounded accumulation). Raises NotFoundError
    if the replace target is not the tenant's dataset.

    When creating (no `replace_dataset_id`), a same-name active dataset raises
    DuplicateDatasetNameError — no silent duplicate — unless `allow_duplicate_name`
    opts into a deliberate second dataset."""
    parsed = parse_spreadsheet(
        data, kind=kind, sheet_name=sheet_name, header_row_index=header_row_index
    )
    repo = DatasetRepository(session)
    dataset_name = name or filename

    if replace_dataset_id is not None:
        dataset = await repo.get_dataset(replace_dataset_id)
        if (
            dataset is None
            or dataset.organization_id != organization_id
            or dataset.deleted_at is not None
        ):
            raise NotFoundError("dataset not found")
        await repo.hard_delete_rows(dataset_id=dataset.id, organization_id=organization_id)
        await repo.hard_delete_columns(dataset_id=dataset.id, organization_id=organization_id)
        dataset.name = dataset_name
        dataset.sheet_name = sheet_name
        dataset.status = "ready"
        dataset.updated_at = datetime.now(UTC)  # pin the bump even if fields are unchanged
        await session.flush()
    else:
        if not allow_duplicate_name:
            existing = await repo.find_active_dataset_by_name(organization_id, dataset_name)
            if existing is not None:
                raise DuplicateDatasetNameError(existing.id, existing.name)
        dataset = await repo.create_dataset(
            organization_id=organization_id,
            name=dataset_name,
            source_document_id=None,
            sheet_name=sheet_name,
            created_by=created_by,
        )

    await repo.add_columns(
        dataset_id=dataset.id, organization_id=organization_id, columns=parsed.columns
    )
    row_count = await repo.bulk_insert_rows(
        dataset_id=dataset.id, organization_id=organization_id, rows=parsed.rows
    )
    await repo.update_row_count(dataset.id, row_count)

    return IngestResult(
        dataset_id=dataset.id,
        name=dataset.name,
        row_count=row_count,
        columns=parsed.columns,
    )
