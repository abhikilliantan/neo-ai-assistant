"""Capability 1, Slice 1b — spreadsheet ingestion (parser + endpoint).

Parser unit tests (pure, no DB): type inference, semantic_role, slug dedupe,
coercion, caps, empty/no-header. Endpoint tests (DB): xlsx + csv → dataset +
typed columns + JSONB rows; unsupported type → 415; tenant isolation;
replace_dataset_id hard-replaces (no row accumulation).
"""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import Any
from uuid import UUID

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.datasets.parser import parse_spreadsheet
from app.ai.datasets.query import DatasetQueryService
from app.application.ports.datasets import DatasetQuery
from app.infrastructure.db.models import DatasetColumn, DatasetRow
from app.infrastructure.db.repositories import DatasetRepository
from app.shared.exceptions.datasets import (
    EmptySpreadsheetError,
    NoHeaderError,
    SpreadsheetTooLargeError,
)

_XLSX_CT = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _xlsx(rows: list[list[Any]]) -> bytes:
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _csv(rows: list[list[Any]]) -> bytes:
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


# --- parser: types + roles + coercion ---------------------------------------


def test_parser_xlsx_infers_types_roles_and_coerces() -> None:
    data = _xlsx(
        [
            ["Task", "Status", "Owner", "Priority", "Due Date", "Count", "Active"],
            ["Design", "Open", "Ada", "High", date(2024, 1, 15), 3, "yes"],
            ["Build", "Blocked", "Bob", "Low", date(2024, 2, 1), 5, "no"],
            ["Ship", "Done", "Cy", "Med", date(2024, 3, 10), 8, True],
        ]
    )
    parsed = parse_spreadsheet(data, kind="xlsx")

    by_key = {c.key: c for c in parsed.columns}
    assert [c.key for c in parsed.columns] == [
        "task",
        "status",
        "owner",
        "priority",
        "due_date",
        "count",
        "active",
    ]
    # data_type inference
    assert by_key["task"].data_type == "text"
    assert by_key["due_date"].data_type == "date"
    assert by_key["count"].data_type == "number"
    assert by_key["active"].data_type == "boolean"
    # semantic_role heuristic
    assert by_key["status"].semantic_role == "status"
    assert by_key["owner"].semantic_role == "owner"
    assert by_key["priority"].semantic_role == "priority"
    assert by_key["due_date"].semantic_role == "due_date"
    assert by_key["task"].semantic_role == "none"
    assert by_key["count"].semantic_role == "none"

    # rows coerced into JSON-ready values
    assert parsed.rows[0] == {
        "task": "Design",
        "status": "Open",
        "owner": "Ada",
        "priority": "High",
        "due_date": "2024-01-15",  # ISO-8601 string
        "count": 3,  # int
        "active": True,  # bool from "yes"
    }
    assert parsed.rows[2]["active"] is True  # native bool cell
    assert parsed.rows[1]["count"] == 5


def test_parser_csv_and_slug_dedupe_and_empty_null() -> None:
    data = _csv(
        [
            ["Name", "Name", "Due-Date!!", ""],
            ["Ada", "x", "2024-05-01", ""],  # trailing empty header -> trimmed
            ["", "y", "", ""],  # empty cells -> None; not a fully-empty row
        ]
    )
    parsed = parse_spreadsheet(data, kind="csv")
    # duplicate "Name" -> name, name_2; "Due-Date!!" -> due_date; trailing empty dropped
    assert [c.key for c in parsed.columns] == ["name", "name_2", "due_date"]
    assert parsed.rows[1]["name"] is None  # empty cell -> null
    assert parsed.rows[1]["name_2"] == "y"
    assert parsed.rows[0]["due_date"] == "2024-05-01"


def test_parser_skips_fully_empty_rows() -> None:
    data = _csv([["A", "B"], ["1", "2"], ["", ""], ["3", "4"]])
    parsed = parse_spreadsheet(data, kind="csv")
    assert len(parsed.rows) == 2  # the middle blank row is skipped


def test_parser_caps_and_errors() -> None:
    with pytest.raises(SpreadsheetTooLargeError):
        parse_spreadsheet(_csv([["a", "b", "c"], ["1", "2", "3"]]), kind="csv", max_columns=2)
    with pytest.raises(SpreadsheetTooLargeError):
        parse_spreadsheet(_csv([["h"], ["1"], ["2"], ["3"]]), kind="csv", max_rows=2)
    with pytest.raises(EmptySpreadsheetError):
        parse_spreadsheet(b"", kind="csv")
    with pytest.raises(NoHeaderError):
        parse_spreadsheet(_csv([["", "", ""], ["1", "2", "3"]]), kind="csv")


# --- endpoint ----------------------------------------------------------------


async def _register(client: AsyncClient, email: str) -> dict[str, Any]:
    r = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "password12345"}
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def _auth(reg: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {reg['access_token']}"}


_SHEET = [
    ["Task", "Status", "Owner"],
    ["Design", "Open", "Ada"],
    ["Build", "Blocked", "Bob"],
]


@pytest.mark.asyncio
async def test_ingest_xlsx_endpoint_persists_dataset_columns_rows(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    reg = await _register(db_client, "ds-xlsx@example.com")
    r = await db_client.post(
        "/api/v1/datasets/ingest",
        files={"file": ("tracker.xlsx", _xlsx(_SHEET), _XLSX_CT)},
        data={"name": "Q3 Tracker"},
        headers=_auth(reg),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "Q3 Tracker"
    assert body["row_count"] == 2
    cols = {c["key"]: c for c in body["columns"]}
    assert cols["status"]["semantic_role"] == "status"
    assert cols["owner"]["semantic_role"] == "owner"
    assert cols["status"]["data_type"] == "text"

    dataset_id = UUID(body["dataset_id"])
    db_rows = (
        (
            await db_session.execute(
                select(DatasetRow)
                .where(DatasetRow.dataset_id == dataset_id)
                .order_by(DatasetRow.row_index)
            )
        )
        .scalars()
        .all()
    )
    assert [row.data for row in db_rows] == [
        {"task": "Design", "status": "Open", "owner": "Ada"},
        {"task": "Build", "status": "Blocked", "owner": "Bob"},
    ]
    assert all(row.organization_id == UUID(reg["active_tenant_id"]) for row in db_rows)


@pytest.mark.asyncio
async def test_ingest_csv_endpoint(db_client: AsyncClient) -> None:
    reg = await _register(db_client, "ds-csv@example.com")
    r = await db_client.post(
        "/api/v1/datasets/ingest",
        files={"file": ("tracker.csv", _csv(_SHEET), "text/csv")},
        headers=_auth(reg),
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["name"] == "tracker.csv"  # defaults to filename
    assert body["row_count"] == 2


@pytest.mark.asyncio
async def test_unsupported_type_returns_415(db_client: AsyncClient) -> None:
    reg = await _register(db_client, "ds-415@example.com")
    r = await db_client.post(
        "/api/v1/datasets/ingest",
        files={"file": ("notes.txt", b"just some text", "text/plain")},
        headers=_auth(reg),
    )
    assert r.status_code == 415, r.text
    assert r.json()["error"]["code"] == "unsupported_content_type"


@pytest.mark.asyncio
async def test_over_cap_returns_422(db_client: AsyncClient) -> None:
    reg = await _register(db_client, "ds-cap@example.com")
    wide = [[f"c{i}" for i in range(250)], [str(i) for i in range(250)]]  # 250 > 200 columns
    r = await db_client.post(
        "/api/v1/datasets/ingest",
        files={"file": ("wide.csv", _csv(wide), "text/csv")},
        headers=_auth(reg),
    )
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == "dataset_unprocessable"


@pytest.mark.asyncio
async def test_tenant_isolation_ingest_A_invisible_to_B(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    org_a = await _register(db_client, "ds-iso-a@example.com")
    org_b = await _register(db_client, "ds-iso-b@example.com")  # separate org
    r = await db_client.post(
        "/api/v1/datasets/ingest",
        files={"file": ("a.csv", _csv(_SHEET), "text/csv")},
        headers=_auth(org_a),
    )
    assert r.status_code == 200, r.text
    a_id = UUID(r.json()["dataset_id"])

    repo = DatasetRepository(db_session)
    a_list = await repo.list_datasets(UUID(org_a["active_tenant_id"]))
    b_list = await repo.list_datasets(UUID(org_b["active_tenant_id"]))
    assert a_id in {d.id for d in a_list}
    assert a_id not in {d.id for d in b_list}
    assert b_list == []


@pytest.mark.asyncio
async def test_replace_hard_replaces_without_accumulation(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    reg = await _register(db_client, "ds-replace@example.com")
    first = await db_client.post(
        "/api/v1/datasets/ingest",
        files={"file": ("v1.csv", _csv(_SHEET), "text/csv")},  # 2 rows, 3 cols
        headers=_auth(reg),
    )
    assert first.status_code == 200, first.text
    dataset_id = first.json()["dataset_id"]

    # Re-ingest into the SAME dataset with a different, smaller sheet.
    new_sheet = [["Ticket", "State"], ["T-1", "closed"]]  # 1 row, 2 cols
    second = await db_client.post(
        "/api/v1/datasets/ingest",
        files={"file": ("v2.csv", _csv(new_sheet), "text/csv")},
        data={"replace_dataset_id": dataset_id},
        headers=_auth(reg),
    )
    assert second.status_code == 200, second.text
    body = second.json()
    assert body["dataset_id"] == dataset_id  # same dataset, replaced in place
    assert body["row_count"] == 1
    assert [c["key"] for c in body["columns"]] == ["ticket", "state"]

    # No accumulation: exactly 1 row + 2 columns remain (old ones hard-deleted).
    ds_uuid = UUID(dataset_id)
    n_rows = await DatasetRepository(db_session).count_rows(ds_uuid)
    assert n_rows == 1
    n_cols = (
        (await db_session.execute(select(DatasetColumn).where(DatasetColumn.dataset_id == ds_uuid)))
        .scalars()
        .all()
    )
    assert len(n_cols) == 2


@pytest.mark.asyncio
async def test_replace_cross_tenant_returns_404(db_client: AsyncClient) -> None:
    owner = await _register(db_client, "ds-owner@example.com")
    other = await _register(db_client, "ds-other@example.com")
    r = await db_client.post(
        "/api/v1/datasets/ingest",
        files={"file": ("a.csv", _csv(_SHEET), "text/csv")},
        headers=_auth(owner),
    )
    owned_id = r.json()["dataset_id"]

    hijack = await db_client.post(
        "/api/v1/datasets/ingest",
        files={"file": ("b.csv", _csv(_SHEET), "text/csv")},
        data={"replace_dataset_id": owned_id},
        headers=_auth(other),
    )
    assert hijack.status_code == 404, hijack.text
    assert hijack.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_replace_soft_deleted_target_rejected(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    reg = await _register(db_client, "ds-softdel@example.com")
    r = await db_client.post(
        "/api/v1/datasets/ingest",
        files={"file": ("a.csv", _csv(_SHEET), "text/csv")},
        headers=_auth(reg),
    )
    dataset_id = r.json()["dataset_id"]

    # Soft-delete it, then try to replace — the deleted target must not resurrect.
    await DatasetRepository(db_session).soft_delete_dataset(UUID(dataset_id))
    await db_session.commit()

    replace = await db_client.post(
        "/api/v1/datasets/ingest",
        files={"file": ("b.csv", _csv(_SHEET), "text/csv")},
        data={"replace_dataset_id": dataset_id},
        headers=_auth(reg),
    )
    assert replace.status_code == 404, replace.text
    assert replace.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_same_name_without_replace_returns_existing_signal(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    reg = await _register(db_client, "ds-dupname@example.com")
    first = await db_client.post(
        "/api/v1/datasets/ingest",
        files={"file": ("v1.csv", _csv(_SHEET), "text/csv")},
        data={"name": "Bidco"},
        headers=_auth(reg),
    )
    first_id = first.json()["dataset_id"]

    # Same name, no replace, no opt-in → 409 pointing at the existing dataset.
    dup = await db_client.post(
        "/api/v1/datasets/ingest",
        files={"file": ("v2.csv", _csv(_SHEET), "text/csv")},
        data={"name": "Bidco"},
        headers=_auth(reg),
    )
    assert dup.status_code == 409, dup.text
    err = dup.json()["error"]
    assert err["code"] == "duplicate_dataset_name"
    assert err["details"]["existing_dataset_id"] == first_id
    assert err["details"]["existing_dataset_name"] == "Bidco"

    # No silent duplicate was created — still exactly one "Bidco".
    tenant = UUID(reg["active_tenant_id"])
    datasets = await DatasetRepository(db_session).list_datasets(tenant)
    assert [d.name for d in datasets].count("Bidco") == 1


@pytest.mark.asyncio
async def test_allow_duplicate_name_creates_second(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    reg = await _register(db_client, "ds-dupok@example.com")
    first = await db_client.post(
        "/api/v1/datasets/ingest",
        files={"file": ("v1.csv", _csv(_SHEET), "text/csv")},
        data={"name": "Bidco"},
        headers=_auth(reg),
    )
    first_id = first.json()["dataset_id"]

    # Explicit opt-in → a deliberate second dataset with the same name.
    second = await db_client.post(
        "/api/v1/datasets/ingest",
        files={"file": ("v2.csv", _csv(_SHEET), "text/csv")},
        data={"name": "Bidco", "allow_duplicate_name": "true"},
        headers=_auth(reg),
    )
    assert second.status_code == 200, second.text
    assert second.json()["dataset_id"] != first_id

    tenant = UUID(reg["active_tenant_id"])
    datasets = await DatasetRepository(db_session).list_datasets(tenant)
    assert [d.name for d in datasets].count("Bidco") == 2


@pytest.mark.asyncio
async def test_replace_partial_failure_rolls_back(
    db_app: FastAPI, db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    # raise_app_exceptions=False so the unhandled failure surfaces as a 500 the
    # client can read, instead of propagating into the test (see test_error_handling).
    transport = ASGITransport(app=db_app, raise_app_exceptions=False)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        reg = await _register(client, "ds-rollback@example.com")
        first = await client.post(
            "/api/v1/datasets/ingest",
            files={"file": ("v1.csv", _csv(_SHEET), "text/csv")},  # 2 rows, 3 cols
            headers=_auth(reg),
        )
        dataset_id = UUID(first.json()["dataset_id"])

        # Force a failure AFTER the replace has hard-deleted the old rows/columns.
        async def _boom(*_args: object, **_kwargs: object) -> int:
            raise RuntimeError("insert blew up")

        monkeypatch.setattr(DatasetRepository, "bulk_insert_rows", _boom)

        new_sheet = [["Ticket", "State"], ["T-1", "closed"]]
        replace = await client.post(
            "/api/v1/datasets/ingest",
            files={"file": ("v2.csv", _csv(new_sheet), "text/csv")},
            data={"replace_dataset_id": str(dataset_id)},
            headers=_auth(reg),
        )
        assert replace.status_code == 500, replace.text

    # Whole transaction rolled back: the ORIGINAL 2 rows + 3 columns survive intact,
    # never a half-replaced dataset.
    repo = DatasetRepository(db_session)
    assert await repo.count_rows(dataset_id) == 2
    cols = await repo.get_columns(dataset_id)
    assert {c.key for c in cols} == {"task", "status", "owner"}


@pytest.mark.asyncio
async def test_query_over_replaced_sees_new_data_only(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    reg = await _register(db_client, "ds-replace-query@example.com")
    tenant = UUID(reg["active_tenant_id"])
    first = await db_client.post(
        "/api/v1/datasets/ingest",
        files={"file": ("v1.csv", _csv(_SHEET), "text/csv")},  # 2 rows: task/status/owner
        headers=_auth(reg),
    )
    dataset_id = UUID(first.json()["dataset_id"])

    new_sheet = [["Ticket", "State"], ["T-1", "closed"], ["T-2", "open"], ["T-3", "open"]]
    replace = await db_client.post(
        "/api/v1/datasets/ingest",
        files={"file": ("v2.csv", _csv(new_sheet), "text/csv")},
        data={"replace_dataset_id": str(dataset_id)},
        headers=_auth(reg),
    )
    assert replace.status_code == 200, replace.text

    svc = DatasetQueryService(db_session)
    counted = await svc.run(DatasetQuery(dataset_id=dataset_id), organization_id=tenant)
    assert counted.value == 3  # NEW data's 3 rows, not the old 2
    assert counted.total_rows_considered == 3

    # The old columns are gone: a query over a removed key can't resolve.
    with pytest.raises(ValueError, match="unknown column"):
        await svc.run(
            DatasetQuery.model_validate({"dataset_id": str(dataset_id), "group_by": "status"}),
            organization_id=tenant,
        )
