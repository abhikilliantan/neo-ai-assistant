"""tenant workflows — tenant-defined n8n webhooks, RLS-locked

Revision ID: e7d9c1a2b3f4
Revises: a3f7c1b8e2d9
Create Date: 2026-07-20 18:30:00.000000

One new tenant-scoped table (7f-2): `workflows`. A row is a tenant's own n8n
webhook exposed to the model as a tool (via the operator agent). Carries NO
secrets. RLS matches memories/conversations: ENABLE + FORCE + one FOR ALL
policy on organization_id.

Name uniqueness is enforced among ACTIVE rows only via a PARTIAL unique index
(`WHERE deleted_at IS NULL`) so a soft-deleted name can be reused — SQLAlchemy
Index can't cleanly express the predicate, so it's raw SQL here.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "e7d9c1a2b3f4"
down_revision: str | None = "a3f7c1b8e2d9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workflows",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=64), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("input_schema", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("webhook_url", sa.Text(), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_workflows_organization_id",
        "workflows",
        ["organization_id"],
        unique=False,
    )
    # Name is unique among ACTIVE rows only, so a soft-deleted name is reusable.
    op.execute(
        "CREATE UNIQUE INDEX uq_workflows_org_name_active "
        "ON workflows (organization_id, name) WHERE deleted_at IS NULL;"
    )

    op.execute("ALTER TABLE workflows ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE workflows FORCE ROW LEVEL SECURITY;")
    op.execute(
        "CREATE POLICY workflows_tenant_isolation ON workflows "
        "FOR ALL "
        "USING (organization_id = current_setting('app.current_tenant', true)::uuid) "
        "WITH CHECK (organization_id = current_setting('app.current_tenant', true)::uuid);"
    )


def downgrade() -> None:
    op.execute("DROP POLICY IF EXISTS workflows_tenant_isolation ON workflows;")
    op.execute("DROP INDEX IF EXISTS uq_workflows_org_name_active;")
    op.drop_index("ix_workflows_organization_id", table_name="workflows")
    op.drop_table("workflows")
