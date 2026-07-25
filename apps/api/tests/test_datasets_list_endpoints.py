"""GET /api/v1/datasets + GET /api/v1/datasets/{id} — list + detail endpoints.

Covers: list returns the tenant's datasets (summary shape); detail returns the
dataset + typed columns; unknown id → 404; and cross-tenant reads collapse to
404 (no existence oracle) — a dataset in org A is invisible to org B on both
the list and the detail route.
"""

from __future__ import annotations

import csv
import io
from typing import Any

import pytest
from httpx import AsyncClient


def _csv(rows: list[list[Any]]) -> bytes:
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


_TRACKER = [
    ["Task", "Status", "Owner"],
    ["Design", "Open", "Ada"],
    ["Build", "Blocked", "Bob"],
]


async def _register(client: AsyncClient, email: str) -> dict[str, Any]:
    r = await client.post(
        "/api/v1/auth/register", json={"email": email, "password": "password12345"}
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def _auth(reg: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {reg['access_token']}"}


async def _ingest(client: AsyncClient, reg: dict[str, Any], name: str) -> str:
    r = await client.post(
        "/api/v1/datasets/ingest",
        files={"file": ("tracker.csv", _csv(_TRACKER), "text/csv")},
        data={"name": name},
        headers=_auth(reg),
    )
    assert r.status_code == 200, r.text
    return r.json()["dataset_id"]  # type: ignore[no-any-return]


@pytest.mark.asyncio
async def test_list_returns_tenant_datasets(db_client: AsyncClient) -> None:
    reg = await _register(db_client, "ds-list@example.com")
    ds_id = await _ingest(db_client, reg, "Q3 Tracker")

    r = await db_client.get("/api/v1/datasets", headers=_auth(reg))
    assert r.status_code == 200, r.text
    body = r.json()
    assert len(body) == 1
    row = body[0]
    assert row["dataset_id"] == ds_id
    assert row["name"] == "Q3 Tracker"
    assert row["row_count"] == 2
    assert "created_at" in row
    assert "sheet_name" in row  # present (null for a CSV)


@pytest.mark.asyncio
async def test_list_empty_for_new_tenant(db_client: AsyncClient) -> None:
    reg = await _register(db_client, "ds-empty@example.com")
    r = await db_client.get("/api/v1/datasets", headers=_auth(reg))
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_detail_returns_dataset_and_columns(db_client: AsyncClient) -> None:
    reg = await _register(db_client, "ds-detail@example.com")
    ds_id = await _ingest(db_client, reg, "Detail Tracker")

    r = await db_client.get(f"/api/v1/datasets/{ds_id}", headers=_auth(reg))
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["dataset_id"] == ds_id
    assert body["name"] == "Detail Tracker"
    assert body["row_count"] == 2
    cols = {c["key"]: c for c in body["columns"]}
    assert [c["key"] for c in body["columns"]] == ["task", "status", "owner"]
    assert cols["status"]["semantic_role"] == "status"
    assert cols["owner"]["semantic_role"] == "owner"
    assert cols["status"]["data_type"] == "text"


@pytest.mark.asyncio
async def test_detail_unknown_id_returns_404(db_client: AsyncClient) -> None:
    reg = await _register(db_client, "ds-404@example.com")
    r = await db_client.get(
        "/api/v1/datasets/00000000-0000-0000-0000-000000000000", headers=_auth(reg)
    )
    assert r.status_code == 404, r.text
    assert r.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_tenant_isolation_list_and_detail(db_client: AsyncClient) -> None:
    org_a = await _register(db_client, "ds-iso-a@example.com")
    org_b = await _register(db_client, "ds-iso-b@example.com")  # separate org
    a_id = await _ingest(db_client, org_a, "A Tracker")

    # B's list does not include A's dataset.
    b_list = await db_client.get("/api/v1/datasets", headers=_auth(org_b))
    assert b_list.status_code == 200
    assert b_list.json() == []

    # B cannot read A's dataset detail — 404, not 403 (no existence oracle).
    b_detail = await db_client.get(f"/api/v1/datasets/{a_id}", headers=_auth(org_b))
    assert b_detail.status_code == 404, b_detail.text

    # A still sees its own.
    a_detail = await db_client.get(f"/api/v1/datasets/{a_id}", headers=_auth(org_a))
    assert a_detail.status_code == 200
    assert a_detail.json()["dataset_id"] == a_id
