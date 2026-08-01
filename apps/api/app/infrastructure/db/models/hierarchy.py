"""Company → Department → Project hierarchy (Neo Command Center, UI Slice 1).

A tenant's org chart for the Overview dashboard: one Company has many
Departments, each Department has many Projects. All three are tenant-scoped and
RLS-locked exactly like `datasets` — each carries its OWN `organization_id` so
RLS holds per-table, not via a join.

A Project OPTIONALLY links to a `Dataset` (`dataset_id` nullable, SET NULL) plus
a small `status_config` (JSONB) that says which status-column values mean
open / blocked / done. That's all the Overview endpoint needs to compute LIVE
metrics via the safe `DatasetQueryService` (group-by the status column, bucket
the counts). A project with no linked dataset has null metrics and renders
"not connected" — the endpoint NEVER fabricates numbers.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import SoftDeleteMixin, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.infrastructure.db.models.datasets import Dataset
    from app.infrastructure.db.models.tenancy import Organization


class Company(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "companies"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    organization: Mapped[Organization] = relationship()

    __table_args__ = (Index("ix_companies_organization_id", "organization_id"),)


class Department(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "departments"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # lucide-react icon name for the department hero card (e.g. "Megaphone"). The
    # frontend maps an unknown/null value to a default icon.
    icon: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # Display order in the Overview (lower = earlier); seed sets it.
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    organization: Mapped[Organization] = relationship()
    company: Mapped[Company] = relationship()

    __table_args__ = (
        Index("ix_departments_organization_id", "organization_id"),
        Index("ix_departments_company_id", "company_id"),
    )


class Project(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "projects"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    department_id: Mapped[UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Display order within the department (lower = earlier); seed sets it.
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    # Optional live-data source. SET NULL so deleting a dataset unlinks the
    # project (→ "not connected") rather than deleting the project.
    dataset_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("datasets.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Which status-column values count as open / blocked / done, e.g.
    #   {"status_column": "status",
    #    "open": ["Open", "In Progress"],
    #    "blocked": ["Parked"],
    #    "done": ["Verified/Closed"]}
    # Null (or dataset_id null) → the project is "not connected" (null metrics).
    status_config: Mapped[dict[str, object] | None] = mapped_column(JSONB, nullable=True)

    organization: Mapped[Organization] = relationship()
    department: Mapped[Department] = relationship()
    dataset: Mapped[Dataset | None] = relationship()

    __table_args__ = (
        Index("ix_projects_organization_id", "organization_id"),
        Index("ix_projects_department_id", "department_id"),
    )
