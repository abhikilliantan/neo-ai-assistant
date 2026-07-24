"""Constrained dataset query service (Capability 1, Slice 1c).

Executes a `DatasetQuery` (structured VO the agent fills in — never SQL) against
one dataset's `dataset_rows`, tenant-scoped. This is the ONLY place structured
questions become SQL, and it is built to make injection impossible:

SAFETY MODEL
  1. The dataset must belong to the calling tenant — else NotFoundError.
  2. Every column_key (filters, group_by, aggregate) is validated against the
     dataset's REAL DatasetColumn.key set. An unknown key is a hard ValueError,
     never a silent pass — the model can't name a column that doesn't exist, so
     it can't smuggle an expression in through the key.
  3. Every VALUE is a BOUND parameter. Filters compare on `data ->> key` (JSONB
     text). numeric/date range ops cast that text with a guarded CASE (a stray
     non-numeric yields NULL, not a 500). We NEVER string-concatenate a value
     into SQL — the injection-attempt test (`' OR 1=1 --`) proves this: it's
     bound as a literal ILIKE pattern and simply matches nothing.

Group results are capped (_MAX_GROUPS) so a high-cardinality column can't return
an unbounded payload to the model.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Date, Numeric, and_, case, cast, func, null, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.datasets import (
    DatasetAggregate,
    DatasetFilter,
    DatasetGroup,
    DatasetQuery,
    DatasetQueryResult,
)
from app.infrastructure.db.models import DatasetColumn, DatasetRow
from app.infrastructure.db.repositories import DatasetRepository
from app.shared.exceptions.common import NotFoundError

_MAX_GROUPS = 200

# JSONB `->>` renders JSON numbers/dates as canonical text; these guard a cast so
# a non-conforming cell drops to NULL (excluded) instead of erroring the query.
_NUM_RE = r"^-?[0-9]+(\.[0-9]+)?$"
_DATE_RE = r"^[0-9]{4}-[0-9]{2}-[0-9]{2}"

_RANGE_CMP: dict[str, Callable[[ColumnElement[Any], object], ColumnElement[bool]]] = {
    "gt": lambda left, right: left > right,
    "gte": lambda left, right: left >= right,
    "lt": lambda left, right: left < right,
    "lte": lambda left, right: left <= right,
}

_OP_PHRASE = {
    "eq": "=",
    "ne": "≠",
    "contains": "contains",
    "gt": ">",
    "gte": "≥",
    "lt": "<",
    "lte": "≤",
    "in": "in",
    "is_empty": "is empty",
    "not_empty": "is not empty",
}


def _to_text(value: object) -> str:
    """Render a scalar as the text form JSONB `->>` would produce, so eq/ne/in
    compare like-for-like (bool → 'true'/'false', 3.0 → '3')."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return str(int(value)) if value.is_integer() else str(value)
    if value is None:
        return ""
    return str(value)


def _escape_like(s: str) -> str:
    return s.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


class DatasetQueryService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def run(self, query: DatasetQuery, *, organization_id: UUID) -> DatasetQueryResult:
        repo = DatasetRepository(self._session)
        dataset = await repo.get_dataset(query.dataset_id)
        if (
            dataset is None
            or dataset.organization_id != organization_id
            or dataset.deleted_at is not None
        ):
            raise NotFoundError("dataset not found")

        columns = {c.key: c for c in await repo.get_columns(query.dataset_id)}
        self._validate_keys(query, columns)
        self._validate_aggregate(query.aggregate, columns)

        conds: list[ColumnElement[bool]] = [
            DatasetRow.dataset_id == query.dataset_id,
            DatasetRow.organization_id == organization_id,
            DatasetRow.deleted_at.is_(None),
        ]
        conds += [self._filter_expr(f, columns) for f in query.filters]

        total = (
            await self._session.execute(select(func.count()).select_from(DatasetRow).where(*conds))
        ).scalar_one()

        groups: list[DatasetGroup] | None = None
        value: int | float | None = None
        if query.group_by is not None:
            groups = await self._grouped(query, conds, columns)
        else:
            agg_row = (
                await self._session.execute(
                    select(self._agg_expr(query.aggregate, columns)).where(*conds)
                )
            ).scalar_one()
            value = _to_number(agg_row)

        return DatasetQueryResult(
            dataset_name=dataset.name,
            total_rows_considered=int(total),
            groups=groups,
            value=value,
            interpreted=self._interpret(dataset.name, query, columns),
        )

    # --- validation ----------------------------------------------------------

    @staticmethod
    def _validate_keys(query: DatasetQuery, columns: dict[str, DatasetColumn]) -> None:
        referenced = {f.column_key for f in query.filters}
        if query.group_by is not None:
            referenced.add(query.group_by)
        if query.aggregate.column_key is not None:
            referenced.add(query.aggregate.column_key)
        unknown = sorted(k for k in referenced if k not in columns)
        if unknown:
            raise ValueError(f"unknown column(s) {unknown}; available keys: {sorted(columns)}")

    @staticmethod
    def _validate_aggregate(agg: DatasetAggregate, columns: dict[str, DatasetColumn]) -> None:
        if agg.func == "count":
            return
        if agg.column_key is None:
            raise ValueError(f"aggregate '{agg.func}' requires a column_key")
        col = columns[agg.column_key]  # presence already checked in _validate_keys
        if col.data_type != "number":
            raise ValueError(
                f"aggregate '{agg.func}' requires a number column; "
                f"'{agg.column_key}' is {col.data_type}"
            )

    # --- expression builders (BOUND params only) -----------------------------

    @staticmethod
    def _filter_expr(f: DatasetFilter, columns: dict[str, DatasetColumn]) -> ColumnElement[bool]:
        col = columns[f.column_key]
        astext: ColumnElement[str] = DatasetRow.data[f.column_key].astext

        if f.op == "is_empty":
            return or_(astext.is_(None), astext == "")
        if f.op == "not_empty":
            return and_(astext.isnot(None), astext != "")
        if f.op == "in":
            if not isinstance(f.value, (list, tuple)):
                raise ValueError("'in' requires a list value")
            return astext.in_([_to_text(v) for v in f.value])
        if f.op == "contains":
            if f.value is None:
                raise ValueError("'contains' requires a value")
            return astext.ilike(f"%{_escape_like(str(f.value))}%", escape="\\")
        if f.op == "eq":
            return astext == _to_text(f.value)
        if f.op == "ne":
            return astext != _to_text(f.value)
        # gt/gte/lt/lte
        if f.value is None:
            raise ValueError(f"'{f.op}' requires a value")
        cmp = _RANGE_CMP[f.op]
        if col.data_type == "number":
            return cmp(_numeric_expr(f.column_key), _as_float(f.value))
        if col.data_type == "date":
            return cmp(_date_expr(f.column_key), _as_date(f.value))
        return cmp(astext, str(f.value))  # text/boolean → lexical

    @staticmethod
    def _agg_expr(agg: DatasetAggregate, columns: dict[str, DatasetColumn]) -> ColumnElement[Any]:
        if agg.func == "count":
            return func.count()
        assert agg.column_key is not None  # guaranteed by _validate_aggregate
        numeric = _numeric_expr(agg.column_key)
        if agg.func == "sum":
            return func.sum(numeric)
        if agg.func == "avg":
            return func.avg(numeric)
        if agg.func == "min":
            return func.min(numeric)
        return func.max(numeric)

    async def _grouped(
        self,
        query: DatasetQuery,
        conds: list[ColumnElement[bool]],
        columns: dict[str, DatasetColumn],
    ) -> list[DatasetGroup]:
        assert query.group_by is not None
        group_value = DatasetRow.data[query.group_by].astext.label("group_value")
        agg = self._agg_expr(query.aggregate, columns).label("agg")
        stmt = (
            select(group_value, agg)
            .where(*conds)
            .group_by(group_value)
            .order_by(agg.desc(), group_value.asc())
            .limit(_MAX_GROUPS)
        )
        rows = (await self._session.execute(stmt)).all()
        return [DatasetGroup(group_value=r.group_value, value=_to_number(r.agg)) for r in rows]

    # --- plain-English restatement (for 1d grounding) ------------------------

    @staticmethod
    def _interpret(name: str, query: DatasetQuery, columns: dict[str, DatasetColumn]) -> str:
        agg = query.aggregate
        if agg.func == "count":
            what = "count of rows"
        else:
            what = f"{agg.func} of {columns[agg.column_key].name}"  # type: ignore[index]
        parts = [f"{what} in dataset '{name}'"]
        if query.filters:
            phrases = [
                f"{columns[f.column_key].name} {_OP_PHRASE[f.op]}"
                + ("" if f.op in ("is_empty", "not_empty") else f" {f.value!r}")
                for f in query.filters
            ]
            parts.append("where " + " and ".join(phrases))
        if query.group_by is not None:
            parts.append(f"grouped by {columns[query.group_by].name}")
        return " ".join(parts) + "."


def _numeric_expr(key: str) -> ColumnElement[Any]:
    astext = DatasetRow.data[key].astext
    expr: ColumnElement[Any] = case((astext.op("~")(_NUM_RE), cast(astext, Numeric)), else_=null())
    return expr


def _date_expr(key: str) -> ColumnElement[Any]:
    astext = DatasetRow.data[key].astext
    expr: ColumnElement[Any] = case((astext.op("~")(_DATE_RE), cast(astext, Date)), else_=null())
    return expr


def _as_float(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError) as e:
        raise ValueError(f"comparison value {value!r} is not a number") from e


def _as_date(value: object) -> date:
    try:
        return date.fromisoformat(str(value))
    except ValueError as e:
        raise ValueError(f"comparison value {value!r} is not an ISO date") from e


def _to_number(value: object) -> int | float | None:
    """Normalize a DB aggregate (int / Decimal / None) to a clean JSON number."""
    if value is None:
        return None
    f = float(value)  # type: ignore[arg-type]  # int | Decimal at runtime
    return int(f) if f.is_integer() else f
