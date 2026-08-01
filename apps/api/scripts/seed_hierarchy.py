"""Seed the Skillmind Company → Department → Project hierarchy (Neo Command
Center, UI Slice 1).

Creates a Company + its Departments (Marketing, Sales, Development, QA,
People/HR) + a few Projects under an existing organization, on the privileged
`neo` system session — same posture as scripts/create_api_key.py (no HTTP, no
tokens). Projects whose name matches a real dataset in that org (by substring)
are LINKED to it with a status_config auto-derived from the dataset's live status
values; everything else is left UNLINKED so the Overview shows "not connected".

Idempotent-ish: if the company already exists for the org it does nothing.

Run inside the api container (or via uv):
    python -m scripts.seed_hierarchy --org-slug skillmind-software-ltd
    make seed-hierarchy ORG=skillmind-software-ltd
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.datasets.query import DatasetQueryService
from app.application.ports.datasets import DatasetQuery
from app.infrastructure.config import get_settings
from app.infrastructure.db.models import Company, Dataset, DatasetColumn, Organization
from app.infrastructure.db.repositories import HierarchyRepository
from app.infrastructure.db.session import build_system_database

COMPANY_NAME = "Skillmind"

# (department, icon, [(project, dataset-name-substring | None)])
# A substring links the project to the tenant's dataset whose name contains it
# (case-insensitive) when present; None (or no match) → unlinked → "not connected".
PLAN: tuple[tuple[str, str, tuple[tuple[str, str | None], ...]], ...] = (
    ("Marketing", "Megaphone", (("LinkedIn Content Engine", "LinkedIn"), ("Website Revamp", None))),
    ("Sales", "TrendingUp", (("Q3 Pipeline", None),)),
    ("Development", "Code", (("Platform v2", None),)),
    ("QA", "ShieldCheck", (("Bidco UAT", "Bidco"),)),
    ("People/HR", "Users", (("Hiring Plan", None),)),
)

_DONE_RE = re.compile(r"done|complete|closed|verified|resolved", re.I)
_BLOCKED_RE = re.compile(r"block|parked|hold|stuck", re.I)


async def _resolve_org(session: AsyncSession, slug: str) -> Organization | None:
    stmt = select(Organization).where(Organization.slug == slug)
    return (await session.execute(stmt)).scalar_one_or_none()


async def _find_dataset(session: AsyncSession, org_id: UUID, needle: str) -> Dataset | None:
    stmt = (
        select(Dataset)
        .where(Dataset.organization_id == org_id)
        .where(Dataset.name.ilike(f"%{needle}%"))
        .where(Dataset.deleted_at.is_(None))
        .order_by(Dataset.created_at.desc())
        .limit(1)
    )
    return (await session.execute(stmt)).scalars().first()


async def _status_config(session: AsyncSession, dataset: Dataset) -> dict[str, object] | None:
    """Build a status_config from the dataset's live data: pick the status column
    (semantic_role='status', else a column keyed 'status'), then auto-bucket its
    ACTUAL distinct values by keyword. Returns None if there's no status column."""
    cols = (
        (
            await session.execute(
                select(DatasetColumn)
                .where(DatasetColumn.dataset_id == dataset.id)
                .where(DatasetColumn.deleted_at.is_(None))
            )
        )
        .scalars()
        .all()
    )
    status_col = next((c.key for c in cols if c.semantic_role == "status"), None) or next(
        (c.key for c in cols if c.key == "status"), None
    )
    if status_col is None:
        return None

    result = await DatasetQueryService(session).run(
        DatasetQuery(dataset_id=dataset.id, group_by=status_col),
        organization_id=dataset.organization_id,
    )
    open_v, blocked_v, done_v = [], [], []
    for g in result.groups or []:
        val = g.group_value
        if not val:
            continue
        if _DONE_RE.search(val):
            done_v.append(val)
        elif _BLOCKED_RE.search(val):
            blocked_v.append(val)
        else:
            open_v.append(val)
    return {"status_column": status_col, "open": open_v, "blocked": blocked_v, "done": done_v}


async def _run(args: argparse.Namespace) -> int:
    db = build_system_database(get_settings())
    try:
        async with db.sessionmaker() as session:
            org = await _resolve_org(session, args.org_slug)
            if org is None:
                print(f"error: organization {args.org_slug!r} not found", file=sys.stderr)
                return 1

            existing = (
                (
                    await session.execute(
                        select(Company)
                        .where(Company.organization_id == org.id)
                        .where(Company.name == COMPANY_NAME)
                        .where(Company.deleted_at.is_(None))
                    )
                )
                .scalars()
                .first()
            )
            if existing is not None:
                print(f"company {COMPANY_NAME!r} already exists for {org.slug} — nothing to do")
                return 0

            repo = HierarchyRepository(session)
            company = await repo.create_company(organization_id=org.id, name=COMPANY_NAME)
            linked = 0
            for d_pos, (dept_name, icon, projects) in enumerate(PLAN):
                dept = await repo.create_department(
                    organization_id=org.id,
                    company_id=company.id,
                    name=dept_name,
                    icon=icon,
                    position=d_pos,
                )
                for p_pos, (proj_name, needle) in enumerate(projects):
                    dataset = await _find_dataset(session, org.id, needle) if needle else None
                    config = await _status_config(session, dataset) if dataset else None
                    await repo.create_project(
                        organization_id=org.id,
                        department_id=dept.id,
                        name=proj_name,
                        dataset_id=dataset.id if dataset else None,
                        status_config=config,
                        position=p_pos,
                    )
                    if dataset is not None:
                        linked += 1
                        print(f"  linked {proj_name!r} → dataset {dataset.name!r}")
            await session.commit()
    finally:
        await db.dispose()

    print(
        f"seeded company {COMPANY_NAME!r} for org {org.name} ({linked} project(s) linked to data)"
    )
    return 0


def _parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="seed_hierarchy")
    parser.add_argument("--org-slug", default="skillmind-software-ltd", help="target org slug")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_run(_parse_args(sys.argv[1:] if argv is None else argv)))


if __name__ == "__main__":
    raise SystemExit(main())
