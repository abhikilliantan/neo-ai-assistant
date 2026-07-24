"""Capability 1, Slice 1c — constrained dataset query service + agent tools.

Query service: count/filter/contains/range/group_by/sum/avg over dataset_rows,
SAFELY (bound params, column-key validation). The injection-attempt test proves
values are bound: `' OR 1=1 --` is matched as a literal ILIKE pattern and finds
nothing. Tenant isolation: a dataset in org A is NotFound under org B.

Tools: query_dataset / list_datasets go through the best-effort registry
(execute never raises — a bad dataset surfaces as is_error, not an exception).

Uses the privileged `db_session` (neo, RLS bypassed) so a missing tenant filter
would be VISIBLE — the service must scope by organization_id itself.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.datasets.query import DatasetQueryService
from app.ai.providers.embeddings.mock import MockEmbeddingProvider
from app.ai.tools import build_streaming_request_tool_registry
from app.ai.tools.dataset_tools import (
    ListDatasetsTool,
    QueryDatasetTool,
    bound_session_factory,
)
from app.ai.workflows import WorkflowRegistry
from app.application.ports.datasets import DatasetQuery
from app.application.ports.repositories import DatasetColumnSpec
from app.application.ports.tools import ToolCall
from app.infrastructure.config import Settings
from app.infrastructure.db.models import Organization
from app.infrastructure.db.repositories import DatasetRepository
from app.shared.exceptions.common import NotFoundError

pytestmark = pytest.mark.asyncio


def _cols() -> list[DatasetColumnSpec]:
    return [
        DatasetColumnSpec(name="Task", key="task", data_type="text", position=0),
        DatasetColumnSpec(
            name="Status", key="status", data_type="text", position=1, semantic_role="status"
        ),
        DatasetColumnSpec(
            name="Owner", key="owner", data_type="text", position=2, semantic_role="owner"
        ),
        DatasetColumnSpec(name="Points", key="points", data_type="number", position=3),
        DatasetColumnSpec(
            name="Due", key="due", data_type="date", position=4, semantic_role="due_date"
        ),
    ]


_ROWS = [
    {"task": "Design", "status": "Open", "owner": "Ada", "points": 3, "due": "2024-01-15"},
    {"task": "Build", "status": "Blocked", "owner": "Bob", "points": 5, "due": "2024-02-01"},
    {"task": "Ship", "status": "Open", "owner": "Ada", "points": 8, "due": "2024-03-10"},
    {"task": "Test", "status": "Done", "owner": "Cy", "points": 2, "due": "2024-01-20"},
]


async def _seed(db_session: AsyncSession, slug: str) -> tuple[Organization, object]:
    org = Organization(name=slug.title(), slug=slug)
    db_session.add(org)
    await db_session.flush()
    repo = DatasetRepository(db_session)
    ds = await repo.create_dataset(organization_id=org.id, name="Q3 Tracker")
    await repo.add_columns(dataset_id=ds.id, organization_id=org.id, columns=_cols())
    await repo.bulk_insert_rows(dataset_id=ds.id, organization_id=org.id, rows=_ROWS)
    await repo.update_row_count(ds.id, len(_ROWS))
    return org, ds


# --- query service -----------------------------------------------------------


async def test_count_all(db_session: AsyncSession) -> None:
    org, ds = await _seed(db_session, "q-count")
    res = await DatasetQueryService(db_session).run(
        DatasetQuery(dataset_id=ds.id), organization_id=org.id
    )
    assert res.value == 4
    assert res.total_rows_considered == 4
    assert res.groups is None
    assert "count of rows" in res.interpreted


async def test_filter_eq(db_session: AsyncSession) -> None:
    org, ds = await _seed(db_session, "q-eq")
    res = await DatasetQueryService(db_session).run(
        DatasetQuery.model_validate(
            {
                "dataset_id": ds.id,
                "filters": [{"column_key": "status", "op": "eq", "value": "Open"}],
            }
        ),
        organization_id=org.id,
    )
    assert res.value == 2


async def test_filter_contains_is_case_insensitive(db_session: AsyncSession) -> None:
    org, ds = await _seed(db_session, "q-contains")
    res = await DatasetQueryService(db_session).run(
        DatasetQuery.model_validate(
            {
                "dataset_id": ds.id,
                "filters": [{"column_key": "owner", "op": "contains", "value": "AD"}],
            }
        ),
        organization_id=org.id,
    )
    assert res.value == 2  # "Ada" x2, case-insensitive ILIKE


async def test_numeric_gt_and_gte(db_session: AsyncSession) -> None:
    org, ds = await _seed(db_session, "q-gt")
    svc = DatasetQueryService(db_session)
    gt = await svc.run(
        DatasetQuery.model_validate(
            {"dataset_id": ds.id, "filters": [{"column_key": "points", "op": "gt", "value": 4}]}
        ),
        organization_id=org.id,
    )
    assert gt.value == 2  # 5, 8
    gte = await svc.run(
        DatasetQuery.model_validate(
            {"dataset_id": ds.id, "filters": [{"column_key": "points", "op": "gte", "value": 5}]}
        ),
        organization_id=org.id,
    )
    assert gte.value == 2  # 5, 8


async def test_group_by_count(db_session: AsyncSession) -> None:
    org, ds = await _seed(db_session, "q-group")
    res = await DatasetQueryService(db_session).run(
        DatasetQuery.model_validate({"dataset_id": ds.id, "group_by": "owner"}),
        organization_id=org.id,
    )
    assert res.value is None
    assert res.groups is not None
    by = {g.group_value: g.value for g in res.groups}
    assert by == {"Ada": 2, "Bob": 1, "Cy": 1}
    assert res.groups[0].group_value == "Ada"  # ordered by count desc


async def test_sum_and_avg_on_numeric(db_session: AsyncSession) -> None:
    org, ds = await _seed(db_session, "q-sum")
    svc = DatasetQueryService(db_session)
    s = await svc.run(
        DatasetQuery.model_validate(
            {"dataset_id": ds.id, "aggregate": {"func": "sum", "column_key": "points"}}
        ),
        organization_id=org.id,
    )
    assert s.value == 18  # 3+5+8+2
    a = await svc.run(
        DatasetQuery.model_validate(
            {"dataset_id": ds.id, "aggregate": {"func": "avg", "column_key": "points"}}
        ),
        organization_id=org.id,
    )
    assert a.value == 4.5


async def test_unknown_column_raises_valueerror(db_session: AsyncSession) -> None:
    org, ds = await _seed(db_session, "q-unknown")
    with pytest.raises(ValueError, match="unknown column"):
        await DatasetQueryService(db_session).run(
            DatasetQuery.model_validate(
                {"dataset_id": ds.id, "filters": [{"column_key": "nope", "op": "eq", "value": "x"}]}
            ),
            organization_id=org.id,
        )


async def test_sum_requires_number_column(db_session: AsyncSession) -> None:
    org, ds = await _seed(db_session, "q-sumtext")
    with pytest.raises(ValueError, match="number column"):
        await DatasetQueryService(db_session).run(
            DatasetQuery.model_validate(
                {"dataset_id": ds.id, "aggregate": {"func": "sum", "column_key": "status"}}
            ),
            organization_id=org.id,
        )


async def test_injection_value_is_bound_and_matches_nothing(db_session: AsyncSession) -> None:
    org, ds = await _seed(db_session, "q-inject")
    # If this value were concatenated into SQL it would change the query; bound,
    # it's just a literal substring that no status contains.
    res = await DatasetQueryService(db_session).run(
        DatasetQuery.model_validate(
            {
                "dataset_id": ds.id,
                "filters": [{"column_key": "status", "op": "contains", "value": "' OR 1=1 --"}],
            }
        ),
        organization_id=org.id,
    )
    assert res.value == 0
    assert res.total_rows_considered == 0


async def test_tenant_isolation_not_queryable_by_other_org(db_session: AsyncSession) -> None:
    _org_a, ds = await _seed(db_session, "q-iso-a")
    other = Organization(name="Iso B", slug="q-iso-b")
    db_session.add(other)
    await db_session.flush()
    with pytest.raises(NotFoundError):
        await DatasetQueryService(db_session).run(
            DatasetQuery(dataset_id=ds.id), organization_id=other.id
        )


# --- tool wrappers (best-effort registry) ------------------------------------


async def test_query_dataset_tool_happy_path_returns_count(db_session: AsyncSession) -> None:
    org, ds = await _seed(db_session, "t-happy")
    tool = QueryDatasetTool(
        session_factory=bound_session_factory(db_session), organization_id=org.id
    )
    content = await tool.run(
        {
            "dataset_id": str(ds.id),
            "filters": [{"column_key": "status", "op": "eq", "value": "Open"}],
        }
    )
    assert json.loads(content)["value"] == 2


async def test_query_dataset_unknown_dataset_is_error_not_raise(db_session: AsyncSession) -> None:
    org, _ds = await _seed(db_session, "t-bad")
    from app.ai.tools.registry import ToolRegistry

    registry = ToolRegistry()
    registry.register(
        QueryDatasetTool(session_factory=bound_session_factory(db_session), organization_id=org.id)
    )
    result = await registry.execute(
        ToolCall(id="tc1", name="query_dataset", arguments={"dataset_id": str(uuid4())})
    )
    assert result.is_error is True  # NotFound surfaced, not raised
    assert result.tool_call_id == "tc1"


async def test_list_datasets_tool_returns_schema(db_session: AsyncSession) -> None:
    org, ds = await _seed(db_session, "t-list")
    tool = ListDatasetsTool(
        session_factory=bound_session_factory(db_session), organization_id=org.id
    )
    payload = json.loads(await tool.run({}))
    assert len(payload["datasets"]) == 1
    d = payload["datasets"][0]
    assert d["dataset_id"] == str(ds.id)
    assert d["row_count"] == 4
    keys = {c["key"]: c for c in d["columns"]}
    assert keys["status"]["semantic_role"] == "status"
    assert keys["points"]["data_type"] == "number"


async def test_build_registers_both_dataset_tools() -> None:
    # Builder is sync + specs-only; the factory is never opened here.
    @asynccontextmanager
    async def _never_opened():  # type: ignore[no-untyped-def]
        yield None  # pragma: no cover

    settings = Settings(
        python_env="test",
        database_url="postgresql+asyncpg://x/x",
        app_database_url="postgresql+asyncpg://x/x",
        redis_url="redis://x",
        jwt_secret_key="test-secret-key-at-least-32-bytes-long-xxxxx",
    )  # type: ignore[call-arg]
    registry = build_streaming_request_tool_registry(
        settings=settings,
        memory_repo_factory=_never_opened,  # type: ignore[arg-type]
        document_repo_factory=_never_opened,  # type: ignore[arg-type]
        embedding_provider=MockEmbeddingProvider(),
        organization_id=uuid4(),
        user_id=uuid4(),
        workflow_registry=WorkflowRegistry(),
        workflow_client=None,  # type: ignore[arg-type]  # workflows_enabled defaults false
        dataset_session_factory=_never_opened,  # type: ignore[arg-type]
    )
    names = {s["name"] for s in registry.specs()}
    assert {"list_datasets", "query_dataset"} <= names
