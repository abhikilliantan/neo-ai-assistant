"""Structured-dataset query VOs (Capability 1, Slice 1c).

The CONSTRAINED query surface the agent fills in — the LLM never writes SQL, it
only populates a `DatasetQuery`. The query service (`app/ai/datasets/query.py`)
turns this into SQLAlchemy expressions with BOUND parameters and validates every
`column_key` against the dataset's real schema before running anything.

Framework-free pydantic VOs (same convention as ports/documents.py, ports/tools.py).
"""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

# Comparison operators the agent may use. text ops (eq/ne/contains) operate on the
# JSONB text (`->>`); gt/gte/lt/lte cast to numeric/date for number/date columns;
# is_empty/not_empty test null/''. `in` matches any of a list of values.
FilterOp = Literal["eq", "ne", "contains", "gt", "gte", "lt", "lte", "in", "is_empty", "not_empty"]
FILTER_OPS: tuple[str, ...] = (
    "eq",
    "ne",
    "contains",
    "gt",
    "gte",
    "lt",
    "lte",
    "in",
    "is_empty",
    "not_empty",
)

AggregateFunc = Literal["count", "sum", "avg", "min", "max"]
AGGREGATE_FUNCS: tuple[str, ...] = ("count", "sum", "avg", "min", "max")


class DatasetFilter(BaseModel):
    column_key: str
    op: FilterOp
    # Comparison value. Omitted for is_empty/not_empty; a list for `in`; a scalar
    # otherwise. Typed Any because it crosses the JSON tool boundary; the service
    # coerces it against the column's data_type and BINDS it (never inlines).
    value: Any = None


class DatasetAggregate(BaseModel):
    func: AggregateFunc = "count"
    # Required for sum/avg/min/max (must name a NUMBER column); ignored for count.
    column_key: str | None = None


class DatasetQuery(BaseModel):
    dataset_id: UUID
    filters: list[DatasetFilter] = Field(default_factory=list)
    group_by: str | None = None
    aggregate: DatasetAggregate = Field(default_factory=DatasetAggregate)


class DatasetGroup(BaseModel):
    group_value: str | None  # the data->>group_key value (None if the cell was null)
    value: int | float | None  # the aggregate for that group


class DatasetQueryResult(BaseModel):
    dataset_name: str
    total_rows_considered: int  # rows matching the filters (the population)
    groups: list[DatasetGroup] | None = None  # set when group_by is used
    value: int | float | None = None  # the scalar aggregate when NOT grouping
    interpreted: str  # plain-English restatement of what ran (for 1d grounding)
