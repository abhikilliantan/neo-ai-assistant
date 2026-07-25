"""HTTP schemas for /api/v1/datasets (Capability 1, Slices 1b + list/detail)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class DatasetColumnOut(BaseModel):
    name: str  # original header
    key: str  # normalized slug used in queries + DatasetRow.data
    data_type: str  # text | number | date | boolean
    semantic_role: str  # status | owner | priority | due_date | none


class DatasetIngestResponse(BaseModel):
    dataset_id: UUID
    name: str
    row_count: int
    columns: list[DatasetColumnOut]


class DatasetSummary(BaseModel):
    dataset_id: UUID
    name: str
    row_count: int
    sheet_name: str | None
    created_at: datetime


class DatasetDetail(BaseModel):
    dataset_id: UUID
    name: str
    row_count: int
    sheet_name: str | None
    created_at: datetime
    columns: list[DatasetColumnOut]
