"""Structured-dataset agent tools (Capability 1, Slice 1c): list_datasets +
query_dataset.

Two READ-ONLY tools that let the model answer counting/filtering/aggregation
questions over an uploaded tracker WITHOUT writing SQL:

  - list_datasets — DISCOVERY. Returns each dataset's id, row_count, and typed
    columns (name/key/data_type/semantic_role) so the model can pick the right
    dataset_id and column keys before querying.
  - query_dataset — fills a structured DatasetQuery (dataset_id + filters +
    group_by + aggregate) and runs it through the constrained query service
    (app/ai/datasets/query.py), which binds every value and validates every
    column key. The model NEVER emits SQL.

Both take a session factory (a fresh tenant-scoped AsyncSession per call, GUC
set) mirroring the short-per-call discipline of search_documents/search_memory,
and are best-effort: a raise here (bad UUID, unknown column, missing dataset)
surfaces to the model as ToolResult(is_error=True) via the 6b registry, so a
chat turn never 500s.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.datasets.query import DatasetQueryService
from app.application.ports.datasets import AGGREGATE_FUNCS, FILTER_OPS, DatasetQuery
from app.infrastructure.db.repositories import DatasetRepository

# A fresh tenant-scoped session per call (GUC set), matching DocumentRepoFactory.
DatasetSessionFactory = Callable[[], AbstractAsyncContextManager[AsyncSession]]


def bound_session_factory(session: AsyncSession) -> DatasetSessionFactory:
    """Wrap an already-open session into a factory yielding it verbatim — for the
    bound (non-streaming) caller and tests."""

    @asynccontextmanager
    async def _factory() -> AsyncIterator[AsyncSession]:
        yield session

    return _factory


class ListDatasetsTool:
    def __init__(self, *, session_factory: DatasetSessionFactory, organization_id: UUID) -> None:
        self._factory = session_factory
        self._org_id = organization_id

    @property
    def name(self) -> str:
        return "list_datasets"

    @property
    def description(self) -> str:
        return (
            "List the datasets (uploaded trackers/spreadsheets) in this "
            "organization, each with its columns (name, key, data_type, "
            "semantic_role) and row count. Call this FIRST to discover what data "
            "exists and which column keys to use before calling query_dataset."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}, "required": []}

    async def run(self, arguments: dict[str, Any]) -> str:
        del arguments  # no inputs
        async with self._factory() as session:
            repo = DatasetRepository(session)
            datasets = await repo.list_datasets(self._org_id)
            out = []
            for d in datasets:
                cols = await repo.get_columns(d.id)
                out.append(
                    {
                        "dataset_id": str(d.id),
                        "name": d.name,
                        "row_count": d.row_count,
                        "columns": [
                            {
                                "name": c.name,
                                "key": c.key,
                                "data_type": c.data_type,
                                "semantic_role": c.semantic_role,
                            }
                            for c in cols
                        ],
                    }
                )
        if not out:
            return "No datasets have been uploaded yet."
        return json.dumps({"datasets": out}, ensure_ascii=False)


class QueryDatasetTool:
    def __init__(self, *, session_factory: DatasetSessionFactory, organization_id: UUID) -> None:
        self._factory = session_factory
        self._org_id = organization_id

    @property
    def name(self) -> str:
        return "query_dataset"

    @property
    def description(self) -> str:
        return (
            "Run a SAFE structured count/filter/aggregation over ONE dataset's "
            "rows — you never write SQL, you only fill in dataset_id, optional "
            "filters, optional group_by, and an aggregate. Use list_datasets "
            "first for the dataset_id and column keys. Examples: 'how many are "
            "open?' -> filters [{column_key:'status', op:'eq', value:'Open'}], "
            "aggregate {func:'count'}; 'count by owner' -> group_by 'owner', "
            "aggregate {func:'count'}."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "dataset_id": {
                    "type": "string",
                    "description": "The dataset UUID from list_datasets.",
                },
                "filters": {
                    "type": "array",
                    "description": "Row filters, ANDed together.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "column_key": {"type": "string"},
                            "op": {"type": "string", "enum": list(FILTER_OPS)},
                            "value": {
                                "description": (
                                    "Comparison value. Omit for is_empty/"
                                    "not_empty; use a list for 'in'."
                                )
                            },
                        },
                        "required": ["column_key", "op"],
                    },
                },
                "group_by": {
                    "type": ["string", "null"],
                    "description": "column_key to group the aggregate by.",
                },
                "aggregate": {
                    "type": "object",
                    "properties": {
                        "func": {"type": "string", "enum": list(AGGREGATE_FUNCS)},
                        "column_key": {
                            "type": ["string", "null"],
                            "description": ("A number column for sum/avg/min/max; omit for count."),
                        },
                    },
                },
            },
            "required": ["dataset_id"],
        }

    async def run(self, arguments: dict[str, Any]) -> str:
        query = DatasetQuery.model_validate(arguments)  # bad/missing args -> is_error
        async with self._factory() as session:
            result = await DatasetQueryService(session).run(query, organization_id=self._org_id)
        return result.model_dump_json(exclude_none=True)
