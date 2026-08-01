"""company → department → project hierarchy, RLS-locked

Revision ID: a1b2c3d4e5f6
Revises: f1a2b3c4d5e6
Create Date: 2026-08-01 12:00:00.000000

Neo Command Center, UI Slice 1. Three tenant-scoped tables for the Overview
dashboard's org chart:
  - companies: one per company under a tenant (name).
  - departments: many per company (name, optional lucide `icon`).
  - projects: many per department; OPTIONAL `dataset_id` (SET NULL) + a JSONB
    `status_config` mapping status-column values to open/blocked/done buckets so
    the Overview endpoint computes LIVE metrics via the safe query service.

RLS matches datasets/documents exactly: ENABLE + FORCE + one FOR ALL policy on
organization_id (USING + WITH CHECK), on all three tables.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "f1a2b3c4d5e6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TENANT_TABLES: tuple[tuple[str, str], ...] = (
    ("companies", "organization_id"),
    ("departments", "organization_id"),
    ("projects", "organization_id"),
)


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_companies_organization_id", "companies", ["organization_id"], unique=False)

    op.create_table(
        "departments",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("icon", sa.String(length=64), nullable=True),
        sa.Column("position", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_departments_organization_id", "departments", ["organization_id"], unique=False
    )
    op.create_index("ix_departments_company_id", "departments", ["company_id"], unique=False)

    op.create_table(
        "projects",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("department_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("dataset_id", sa.UUID(), nullable=True),
        sa.Column(
            "status_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_organization_id", "projects", ["organization_id"], unique=False)
    op.create_index("ix_projects_department_id", "projects", ["department_id"], unique=False)

    for table, column in TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY;")
        op.execute(
            f"CREATE POLICY {table}_tenant_isolation ON {table} "
            f"FOR ALL "
            f"USING ({column} = current_setting('app.current_tenant', true)::uuid) "
            f"WITH CHECK ({column} = current_setting('app.current_tenant', true)::uuid);"
        )


def downgrade() -> None:
    for table, _column in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};")
    # projects (leaf) → departments → companies (root).
    op.drop_index("ix_projects_department_id", table_name="projects")
    op.drop_index("ix_projects_organization_id", table_name="projects")
    op.drop_table("projects")
    op.drop_index("ix_departments_company_id", table_name="departments")
    op.drop_index("ix_departments_organization_id", table_name="departments")
    op.drop_table("departments")
    op.drop_index("ix_companies_organization_id", table_name="companies")
    op.drop_table("companies")
