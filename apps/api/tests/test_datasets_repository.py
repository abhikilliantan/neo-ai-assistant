"""Capability 1, Slice 1a — DatasetRepository unit + tenant-scoping tests.

Storage-only surface: create dataset → typed columns → bulk rows → read back;
row_count update; soft-delete excluded from the list; and the list is filtered by
organization_id AT THE REPO LAYER (the app runs as a BYPASSRLS superuser, so we
assert the repo's own tenant filter — not that RLS blocks).

Uses the privileged `db_session` (neo, RLS bypassed) so a missing repo filter
would be VISIBLE as a leak.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.repositories import DatasetColumnSpec
from app.infrastructure.db.models import DatasetColumn, DatasetRow, Organization
from app.infrastructure.db.repositories import DatasetRepository


async def _make_org(db_session: AsyncSession, slug: str) -> Organization:
    org = Organization(name=slug.title(), slug=slug)
    db_session.add(org)
    await db_session.flush()
    return org


def _cols() -> list[DatasetColumnSpec]:
    return [
        DatasetColumnSpec(name="Status", key="status", position=0, semantic_role="status"),
        DatasetColumnSpec(name="Owner", key="owner", position=1, semantic_role="owner"),
        DatasetColumnSpec(name="Priority", key="priority", position=2, semantic_role="priority"),
    ]


@pytest.mark.asyncio
async def test_create_columns_rows_roundtrip(db_session: AsyncSession) -> None:
    repo = DatasetRepository(db_session)
    org = await _make_org(db_session, "acme-roundtrip")

    ds = await repo.create_dataset(
        organization_id=org.id, name="Q3 Tracker", sheet_name="Sheet1", description="the tracker"
    )
    assert ds.id is not None
    assert ds.status == "ready"  # default
    assert ds.row_count == 0  # server default

    cols = await repo.add_columns(dataset_id=ds.id, organization_id=org.id, columns=_cols())
    assert len(cols) == 3

    n = await repo.bulk_insert_rows(
        dataset_id=ds.id,
        organization_id=org.id,
        rows=[
            {"status": "open", "owner": "Ada", "priority": "high"},
            {"status": "blocked", "owner": "Bob", "priority": "low"},
            {"status": "done", "owner": "Cy", "priority": "med"},
        ],
    )
    assert n == 3

    # Columns read back in position order, with keys + semantic roles intact.
    got_cols = await repo.get_columns(ds.id)
    assert [c.key for c in got_cols] == ["status", "owner", "priority"]
    assert [c.semantic_role for c in got_cols] == ["status", "owner", "priority"]
    assert all(c.organization_id == org.id for c in got_cols)

    assert await repo.count_rows(ds.id) == 3

    # Rows carry the JSONB payload (keyed by column.key), a 0-based row_index, and org.
    rows = (
        (
            await db_session.execute(
                select(DatasetRow)
                .where(DatasetRow.dataset_id == ds.id)
                .order_by(DatasetRow.row_index)
            )
        )
        .scalars()
        .all()
    )
    assert [r.row_index for r in rows] == [0, 1, 2]
    assert rows[0].data == {"status": "open", "owner": "Ada", "priority": "high"}
    assert rows[1].data["status"] == "blocked"
    assert all(r.organization_id == org.id for r in rows)


@pytest.mark.asyncio
async def test_bulk_insert_empty_is_noop(db_session: AsyncSession) -> None:
    repo = DatasetRepository(db_session)
    org = await _make_org(db_session, "acme-empty")
    ds = await repo.create_dataset(organization_id=org.id, name="Empty")
    assert await repo.bulk_insert_rows(dataset_id=ds.id, organization_id=org.id, rows=[]) == 0
    assert await repo.count_rows(ds.id) == 0


@pytest.mark.asyncio
async def test_update_row_count(db_session: AsyncSession) -> None:
    repo = DatasetRepository(db_session)
    org = await _make_org(db_session, "acme-count")
    ds = await repo.create_dataset(organization_id=org.id, name="Counter")
    await repo.update_row_count(ds.id, 42)
    fetched = await repo.get_dataset(ds.id)
    assert fetched is not None and fetched.row_count == 42
    # No-op on an unknown id (does not raise).
    await repo.update_row_count(uuid4(), 7)


@pytest.mark.asyncio
async def test_soft_delete_excluded_from_list(db_session: AsyncSession) -> None:
    repo = DatasetRepository(db_session)
    org = await _make_org(db_session, "acme-del")
    keep = await repo.create_dataset(organization_id=org.id, name="Keep")
    drop = await repo.create_dataset(organization_id=org.id, name="Drop")

    await repo.soft_delete_dataset(drop.id)

    active = await repo.list_datasets(org.id)
    assert [d.id for d in active] == [keep.id]  # soft-deleted excluded

    everything = await repo.list_datasets(org.id, active_only=False)
    assert {d.id for d in everything} == {keep.id, drop.id}

    # Idempotent: deleting again is a no-op.
    await repo.soft_delete_dataset(drop.id)
    assert [d.id for d in await repo.list_datasets(org.id)] == [keep.id]


@pytest.mark.asyncio
async def test_list_datasets_is_tenant_scoped_at_repo_layer(db_session: AsyncSession) -> None:
    # Two orgs, one dataset each — both created under the SUPERUSER session (RLS
    # bypassed). list_datasets(org_a) must return ONLY org_a's dataset, proving
    # the repo's explicit organization_id filter (not RLS) does the scoping.
    repo = DatasetRepository(db_session)
    org_a = await _make_org(db_session, "tenant-a")
    org_b = await _make_org(db_session, "tenant-b")
    ds_a = await repo.create_dataset(organization_id=org_a.id, name="A tracker")
    ds_b = await repo.create_dataset(organization_id=org_b.id, name="B tracker")

    a_list = await repo.list_datasets(org_a.id)
    assert [d.id for d in a_list] == [ds_a.id]
    assert ds_b.id not in {d.id for d in a_list}

    b_list = await repo.list_datasets(org_b.id)
    assert [d.id for d in b_list] == [ds_b.id]


@pytest.mark.asyncio
async def test_unique_key_per_dataset_enforced(db_session: AsyncSession) -> None:
    # UNIQUE (dataset_id, key): two columns with the same key in one dataset fail.
    from sqlalchemy.exc import IntegrityError

    repo = DatasetRepository(db_session)
    org = await _make_org(db_session, "acme-uniq")
    ds = await repo.create_dataset(organization_id=org.id, name="Uniq")
    db_session.add_all(
        [
            DatasetColumn(dataset_id=ds.id, organization_id=org.id, name="Status", key="status"),
            DatasetColumn(dataset_id=ds.id, organization_id=org.id, name="State", key="status"),
        ]
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
