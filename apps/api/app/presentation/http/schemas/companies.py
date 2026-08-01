"""HTTP schemas for /api/v1/companies (Neo Command Center, UI Slice 1).

The Overview payload the dashboard renders: a KPI rollup plus a
Company → Department → Project tree with LIVE metrics. Every metric is computed
from a project's linked dataset; an unlinked project reports null metrics and
status "not_connected" — the API never fabricates numbers.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

# on_track / needs_attention are only set for connected nodes (live metrics);
# not_connected means no linked dataset (or the link/config is broken) → null metrics.
NodeStatus = Literal["on_track", "needs_attention", "not_connected"]


class CompanySummary(BaseModel):
    id: UUID
    name: str


class KpiRollup(BaseModel):
    active_projects: int  # connected projects not yet 100% done
    scheduled_this_week: int  # placeholder (0) until the scheduling slice lands
    open_actions: int  # sum of open actions across connected projects
    blocked: int  # sum of blocked actions across connected projects


class ProjectOverview(BaseModel):
    id: UUID
    name: str
    status: NodeStatus
    progress_pct: int | None  # done / total, 0-100; null when not connected
    open_actions: int | None
    blocked_actions: int | None


class DepartmentOverview(BaseModel):
    id: UUID
    name: str
    icon: str | None
    status: NodeStatus
    project_count: int
    connected_project_count: int
    progress_pct: int | None  # avg across connected projects; null when none connected
    open_actions: int | None  # sum across connected projects; null when none connected
    projects: list[ProjectOverview]


class CompanyOverview(BaseModel):
    company: CompanySummary
    updated_at: datetime
    kpis: KpiRollup
    departments: list[DepartmentOverview]
