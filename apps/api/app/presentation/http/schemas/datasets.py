"""HTTP schemas for /api/v1/datasets (Capability 1, Slice 1b)."""

from __future__ import annotations

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
