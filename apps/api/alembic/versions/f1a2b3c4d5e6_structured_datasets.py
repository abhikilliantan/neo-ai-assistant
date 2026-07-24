"""structured datasets — datasets + dataset_columns + dataset_rows, RLS-locked

Revision ID: f1a2b3c4d5e6
Revises: d5e6f7a8b9c0
Create Date: 2026-07-24 10:00:00.000000

Capability 1 (Structured Data), Slice 1a. Three tenant-scoped tables that store
an uploaded tracker/spreadsheet as structured, queryable rows:
  - datasets: one per uploaded sheet (name, optional source_document link,
    sheet_name, row_count, status).
  - dataset_columns: the typed schema (original header `name` + normalized `key`,
    data_type, ordinal position, nullability, and a canonical semantic_role).
    UNIQUE (dataset_id, key).
  - dataset_rows: the data — `row_index` + `data` JSONB keyed by column.key. A
    GIN index on `data` backs 1c's constrained key/containment filters.

RLS matches documents/memories/workflows exactly: ENABLE + FORCE + one FOR ALL
policy on organization_id (USING + WITH CHECK), on all three tables. Policies are
defined correctly even though the app currently connects as a BYPASSRLS
superuser (that's a separately-tracked task).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "f1a2b3c4d5e6"
down_revision: str | None = "d5e6f7a8b9c0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


# (table, tenant column) — RLS is applied identically to each.
TENANT_TABLES: tuple[tuple[str, str], ...] = (
    ("datasets", "organization_id"),
    ("dataset_columns", "organization_id"),
    ("dataset_rows", "organization_id"),
)


def upgrade() -> None:
    op.create_table(
        "datasets",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_document_id", sa.UUID(), nullable=True),
        sa.Column("sheet_name", sa.String(length=255), nullable=True),
        sa.Column("row_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="ready", nullable=False),
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
        sa.CheckConstraint(
            "status IN ('ready', 'ingesting', 'failed')",
            name="ck_datasets_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_document_id"], ["documents.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_datasets_organization_id", "datasets", ["organization_id"], unique=False)

    op.create_table(
        "dataset_columns",
        sa.Column("dataset_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("key", sa.String(length=255), nullable=False),
        sa.Column("data_type", sa.String(length=16), server_default="text", nullable=False),
        sa.Column("position", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("nullable", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("semantic_role", sa.String(length=16), server_default="none", nullable=False),
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
        sa.CheckConstraint(
            "data_type IN ('text', 'number', 'date', 'boolean')",
            name="ck_dataset_columns_data_type",
        ),
        sa.CheckConstraint(
            "semantic_role IN ('status', 'owner', 'priority', 'due_date', 'none')",
            name="ck_dataset_columns_semantic_role",
        ),
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset_id", "key", name="uq_dataset_columns_dataset_key"),
    )
    op.create_index(
        "ix_dataset_columns_dataset_id", "dataset_columns", ["dataset_id"], unique=False
    )
    op.create_index(
        "ix_dataset_columns_organization_id",
        "dataset_columns",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "dataset_rows",
        sa.Column("dataset_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("row_index", sa.Integer(), nullable=False),
        sa.Column(
            "data",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
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
        sa.ForeignKeyConstraint(["dataset_id"], ["datasets.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dataset_rows_dataset_id", "dataset_rows", ["dataset_id"], unique=False)
    op.create_index(
        "ix_dataset_rows_organization_id",
        "dataset_rows",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_dataset_rows_dataset_row_index",
        "dataset_rows",
        ["dataset_id", "row_index"],
        unique=False,
    )
    # GIN index on the JSONB payload for containment / key lookups (1c filters).
    op.execute("CREATE INDEX ix_dataset_rows_data_gin ON dataset_rows USING gin (data);")

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
    # dataset_rows (leaf) → dataset_columns → datasets (root).
    op.execute("DROP INDEX IF EXISTS ix_dataset_rows_data_gin;")
    op.drop_index("ix_dataset_rows_dataset_row_index", table_name="dataset_rows")
    op.drop_index("ix_dataset_rows_organization_id", table_name="dataset_rows")
    op.drop_index("ix_dataset_rows_dataset_id", table_name="dataset_rows")
    op.drop_table("dataset_rows")
    op.drop_index("ix_dataset_columns_organization_id", table_name="dataset_columns")
    op.drop_index("ix_dataset_columns_dataset_id", table_name="dataset_columns")
    op.drop_table("dataset_columns")
    op.drop_index("ix_datasets_organization_id", table_name="datasets")
    op.drop_table("datasets")
