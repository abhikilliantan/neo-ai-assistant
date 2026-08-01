"""Company hierarchy + Overview dashboard (Neo Command Center, UI Slice 1).

GET /api/v1/companies                 — the tenant's companies (switcher).
GET /api/v1/companies/{id}/overview   — KPI rollup + Department→Project tree with
                                        LIVE metrics computed from each project's
                                        linked dataset via the SAFE query service.

Metrics are never fabricated: a project with no linked dataset (or a broken
link/config) reports null metrics and status "not_connected". Connected projects
get open/blocked/done counts by grouping the linked dataset on its status column
(one safe, parameterised query per project) and bucketing the values per the
project's `status_config`.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter

from app.ai.datasets.query import DatasetQueryService
from app.application.ports.datasets import DatasetQuery
from app.infrastructure.db.models import Project
from app.infrastructure.db.repositories import HierarchyRepository
from app.presentation.http.deps import CurrentTenantDep, TenantSessionDep
from app.presentation.http.schemas.companies import (
    CompanyOverview,
    CompanySummary,
    DepartmentOverview,
    KpiRollup,
    NodeStatus,
    ProjectOverview,
)
from app.shared.exceptions.auth import AuthenticationError
from app.shared.exceptions.common import NotFoundError

router = APIRouter(prefix="/api/v1", tags=["companies"])

# ponytail: a connected project needs attention if anything is blocked OR it's
# less than half done. Tune the threshold (or move it to status_config) when the
# product defines real SLAs.
_ATTENTION_PROGRESS_FLOOR = 50


@dataclass(frozen=True)
class _Metrics:
    open: int
    blocked: int
    done: int
    total: int
    progress_pct: int


def bucket_status_counts(
    groups: Iterable[tuple[str | None, int]], config: dict[str, object]
) -> _Metrics:
    """Pure: fold per-status-value counts into open/blocked/done buckets using
    `config`'s value lists (case-insensitive, whitespace-trimmed). Values not in
    any bucket still count toward `total` (progress = done/total) but nowhere
    else — so a stray status never inflates open/blocked/done."""

    def _set(key: str) -> set[str]:
        raw = config.get(key, [])
        seq = raw if isinstance(raw, (list, tuple)) else []
        return {str(v).strip().lower() for v in seq}

    open_set, blocked_set, done_set = _set("open"), _set("blocked"), _set("done")
    open_n = blocked_n = done_n = total = 0
    for value, count in groups:
        total += count
        key = (value or "").strip().lower()
        if key in open_set:
            open_n += count
        elif key in blocked_set:
            blocked_n += count
        elif key in done_set:
            done_n += count
    progress = round(done_n / total * 100) if total else 0
    return _Metrics(open=open_n, blocked=blocked_n, done=done_n, total=total, progress_pct=progress)


def _project_status(m: _Metrics | None) -> NodeStatus:
    if m is None:
        return "not_connected"
    if m.blocked > 0 or (m.total > 0 and m.progress_pct < _ATTENTION_PROGRESS_FLOOR):
        return "needs_attention"
    return "on_track"


async def _project_metrics(
    qs: DatasetQueryService, project: Project, organization_id: UUID
) -> _Metrics | None:
    """LIVE metrics for one project, or None ("not connected") when it has no
    linked dataset / no status config / a broken link (dataset deleted or the
    status column renamed away). Never raises for a broken link — that's a
    not-connected state, not a 500."""
    config = project.status_config
    if project.dataset_id is None or not isinstance(config, dict):
        return None
    status_column = config.get("status_column")
    if not isinstance(status_column, str) or not status_column:
        return None
    try:
        result = await qs.run(
            DatasetQuery(dataset_id=project.dataset_id, group_by=status_column),
            organization_id=organization_id,
        )
    except (NotFoundError, ValueError):
        return None
    groups = [(g.group_value, int(g.value or 0)) for g in (result.groups or [])]
    return bucket_status_counts(groups, config)


def _avg_or_none(values: list[int]) -> int | None:
    return round(sum(values) / len(values)) if values else None


@router.get("/companies", response_model=list[CompanySummary])
async def list_companies(
    tenant_id: CurrentTenantDep,
    session: TenantSessionDep,
) -> list[CompanySummary]:
    """The tenant's companies, oldest-first — the Overview company switcher. Only
    real companies are returned; the switcher never shows fabricated entries."""
    if tenant_id is None:
        raise AuthenticationError("user has no active tenant")
    companies = await HierarchyRepository(session).list_companies(tenant_id)
    return [CompanySummary(id=c.id, name=c.name) for c in companies]


@router.get("/companies/{company_id}/overview", response_model=CompanyOverview)
async def company_overview(
    company_id: UUID,
    tenant_id: CurrentTenantDep,
    session: TenantSessionDep,
) -> CompanyOverview:
    """KPI rollup + Department→Project tree with LIVE metrics. Unknown id OR
    another tenant's company both collapse to 404 (no existence oracle)."""
    if tenant_id is None:
        raise AuthenticationError("user has no active tenant")

    repo = HierarchyRepository(session)
    company = await repo.get_company(company_id)
    if company is None or company.organization_id != tenant_id or company.deleted_at is not None:
        raise NotFoundError("company not found")

    departments = await repo.list_departments_for_company(company_id)
    dept_ids = [d.id for d in departments]
    projects = await repo.list_projects_for_departments(dept_ids)
    projects_by_dept: dict[UUID, list[Project]] = {d.id: [] for d in departments}
    for p in projects:
        projects_by_dept.setdefault(p.department_id, []).append(p)

    qs = DatasetQueryService(session)
    total_open = total_blocked = active_projects = 0
    dept_out: list[DepartmentOverview] = []

    for dept in departments:
        proj_out: list[ProjectOverview] = []
        progresses: list[int] = []
        dept_open = 0
        connected = 0
        for p in projects_by_dept.get(dept.id, []):
            m = await _project_metrics(qs, p, tenant_id)
            status = _project_status(m)
            proj_out.append(
                ProjectOverview(
                    id=p.id,
                    name=p.name,
                    status=status,
                    progress_pct=m.progress_pct if m else None,
                    open_actions=m.open if m else None,
                    blocked_actions=m.blocked if m else None,
                )
            )
            if m is not None:
                connected += 1
                progresses.append(m.progress_pct)
                dept_open += m.open
                total_open += m.open
                total_blocked += m.blocked
                if m.progress_pct < 100:
                    active_projects += 1

        needs_attention = any(pj.status == "needs_attention" for pj in proj_out)
        dept_status: NodeStatus = (
            "not_connected"
            if connected == 0
            else ("needs_attention" if needs_attention else "on_track")
        )
        dept_out.append(
            DepartmentOverview(
                id=dept.id,
                name=dept.name,
                icon=dept.icon,
                status=dept_status,
                project_count=len(proj_out),
                connected_project_count=connected,
                progress_pct=_avg_or_none(progresses),
                open_actions=dept_open if connected else None,
                projects=proj_out,
            )
        )

    return CompanyOverview(
        company=CompanySummary(id=company.id, name=company.name),
        updated_at=datetime.now(UTC),
        kpis=KpiRollup(
            active_projects=active_projects,
            scheduled_this_week=0,  # placeholder until the scheduling/snapshot slice
            open_actions=total_open,
            blocked=total_blocked,
        ),
        departments=dept_out,
    )
