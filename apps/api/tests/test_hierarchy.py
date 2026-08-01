"""Company → Department → Project hierarchy + Overview endpoint (UI Slice 1).

Covers: pure status bucketing; /companies list; /companies/{id}/overview with
LIVE metrics for a project linked to a real dataset; "not_connected" for an
unlinked project/department; unknown/cross-tenant company → 404; tenant isolation.
"""

from __future__ import annotations

import csv
import io
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models import Organization
from app.infrastructure.db.repositories import HierarchyRepository
from app.presentation.http.routers.companies import bucket_status_counts

# --- pure bucketing (no DB) --------------------------------------------------


def test_bucket_status_counts_folds_and_ignores_unmapped() -> None:
    config = {
        "status_column": "status",
        "open": ["Open", "In Progress"],
        "blocked": ["Parked"],
        "done": ["Verified/Closed", "Done-Pending Review"],
    }
    groups = [
        ("Open", 74),
        ("Done-Pending Review", 31),
        ("Verified/Closed", 14),
        ("Parked", 2),
        ("In Progress", 2),
        ("Something Else", 5),  # unmapped: counts toward total only
    ]
    m = bucket_status_counts(groups, config)
    assert m.open == 76  # 74 + 2
    assert m.blocked == 2
    assert m.done == 45  # 31 + 14
    assert m.total == 128  # includes the 5 unmapped
    assert m.progress_pct == round(45 / 128 * 100)  # 35


def test_bucket_status_counts_case_insensitive_and_empty() -> None:
    m = bucket_status_counts([("open", 3), (None, 1)], {"open": ["OPEN"]})
    assert (m.open, m.total, m.progress_pct) == (3, 4, 0)


# --- endpoint helpers --------------------------------------------------------

_TRACKER = [
    ["Task", "Status", "Owner"],
    ["Design", "Open", "Ada"],
    ["Build", "Blocked", "Bob"],
]


def _csv(rows: list[list[Any]]) -> bytes:
    buf = io.StringIO()
    csv.writer(buf).writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


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


async def _only_org(db_session: AsyncSession) -> Organization:
    """After a single register, exactly one organization exists (the per-test DB
    truncates organizations). Insert hierarchy against it on the neo session."""
    return (await db_session.execute(select(Organization))).scalars().one()


# --- endpoint tests ----------------------------------------------------------


@pytest.mark.asyncio
async def test_list_companies_returns_tenant_companies(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    reg = await _register(db_client, "hier-list@example.com")
    org = await _only_org(db_session)
    await HierarchyRepository(db_session).create_company(organization_id=org.id, name="Skillmind")
    await db_session.commit()

    r = await db_client.get("/api/v1/companies", headers=_auth(reg))
    assert r.status_code == 200, r.text
    body = r.json()
    assert [c["name"] for c in body] == ["Skillmind"]


@pytest.mark.asyncio
async def test_overview_live_metrics_for_linked_project(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    reg = await _register(db_client, "hier-live@example.com")
    ds_id = await _ingest(db_client, reg, "Action Tracker")
    org = await _only_org(db_session)

    repo = HierarchyRepository(db_session)
    company = await repo.create_company(organization_id=org.id, name="Skillmind")
    qa = await repo.create_department(
        organization_id=org.id, company_id=company.id, name="QA", icon="ShieldCheck"
    )
    await repo.create_project(
        organization_id=org.id,
        department_id=qa.id,
        name="Bidco UAT",
        dataset_id=ds_id,
        status_config={
            "status_column": "status",
            "open": ["Open"],
            "blocked": ["Blocked"],
            "done": [],
        },
    )
    await db_session.commit()

    r = await db_client.get(f"/api/v1/companies/{company.id}/overview", headers=_auth(reg))
    assert r.status_code == 200, r.text
    body = r.json()

    assert body["company"]["name"] == "Skillmind"
    # KPI rollup is LIVE: 1 open + 1 blocked from the linked 2-row tracker.
    assert body["kpis"]["open_actions"] == 1
    assert body["kpis"]["blocked"] == 1
    assert body["kpis"]["active_projects"] == 1  # progress 0% < 100
    assert body["kpis"]["scheduled_this_week"] == 0  # placeholder

    dept = body["departments"][0]
    assert dept["name"] == "QA"
    assert dept["connected_project_count"] == 1
    assert dept["status"] == "needs_attention"  # something is blocked
    proj = dept["projects"][0]
    assert proj["name"] == "Bidco UAT"
    assert proj["status"] == "needs_attention"
    assert proj["open_actions"] == 1
    assert proj["blocked_actions"] == 1
    assert proj["progress_pct"] == 0


@pytest.mark.asyncio
async def test_overview_unlinked_project_is_not_connected(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    reg = await _register(db_client, "hier-unlinked@example.com")
    org = await _only_org(db_session)

    repo = HierarchyRepository(db_session)
    company = await repo.create_company(organization_id=org.id, name="Skillmind")
    sales = await repo.create_department(
        organization_id=org.id, company_id=company.id, name="Sales", icon="TrendingUp"
    )
    await repo.create_project(organization_id=org.id, department_id=sales.id, name="Q3 Pipeline")
    await db_session.commit()

    r = await db_client.get(f"/api/v1/companies/{company.id}/overview", headers=_auth(reg))
    assert r.status_code == 200, r.text
    dept = r.json()["departments"][0]
    assert dept["status"] == "not_connected"
    assert dept["connected_project_count"] == 0
    assert dept["progress_pct"] is None
    assert dept["open_actions"] is None
    proj = dept["projects"][0]
    assert proj["status"] == "not_connected"
    assert proj["progress_pct"] is None
    assert proj["open_actions"] is None
    assert proj["blocked_actions"] is None


@pytest.mark.asyncio
async def test_overview_unknown_company_returns_404(db_client: AsyncClient) -> None:
    reg = await _register(db_client, "hier-404@example.com")
    r = await db_client.get(
        "/api/v1/companies/00000000-0000-0000-0000-000000000000/overview", headers=_auth(reg)
    )
    assert r.status_code == 404, r.text
    assert r.json()["error"]["code"] == "not_found"


@pytest.mark.asyncio
async def test_tenant_isolation_company_overview(
    db_client: AsyncClient, db_session: AsyncSession
) -> None:
    org_a = await _register(db_client, "hier-iso-a@example.com")
    await _register(db_client, "hier-iso-b@example.com")

    # Company belongs to org A (the org whose slug starts with "hier-iso-a").
    a_org = (
        (
            await db_session.execute(
                select(Organization).where(Organization.slug.like("hier-iso-a%"))
            )
        )
        .scalars()
        .one()
    )
    company = await HierarchyRepository(db_session).create_company(
        organization_id=a_org.id, name="Skillmind"
    )
    await db_session.commit()

    org_b = await _register(db_client, "hier-iso-b2@example.com")
    # B's company list is empty; B cannot read A's overview (404, no oracle).
    b_list = await db_client.get("/api/v1/companies", headers=_auth(org_b))
    assert b_list.status_code == 200 and b_list.json() == []
    b_over = await db_client.get(f"/api/v1/companies/{company.id}/overview", headers=_auth(org_b))
    assert b_over.status_code == 404, b_over.text
    # A still sees its own.
    a_over = await db_client.get(f"/api/v1/companies/{company.id}/overview", headers=_auth(org_a))
    assert a_over.status_code == 200, a_over.text
