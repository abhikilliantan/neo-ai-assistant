"""memory + user_preferences — pgvector, HNSW, RLS-locked

Revision ID: c9f4e2b7d8a5
Revises: b2e5f7a1c9d3
Create Date: 2026-07-19 11:00:00.000000

Two new tenant-scoped tables under the neo_app/RLS regime:
  - memories: durable observations/facts about a user, embedded with the
    Phase 5a embedding provider (vector(1024)); an HNSW index on the
    embedding column with vector_cosine_ops backs cosine-similarity ANN
    scans via the `<=>` operator.
  - user_preferences: structured k/v per user (JSONB value), UNIQUE on
    (organization_id, user_id, key) — the ON CONFLICT target for upsert.

CREATE EXTENSION IF NOT EXISTS vector runs as owner `neo` (the migration
role). RLS matches the memberships/api_keys/conversations/messages pattern:
ENABLE + FORCE + one FOR ALL policy on organization_id.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

revision: str = "c9f4e2b7d8a5"
down_revision: str | None = "b2e5f7a1c9d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TENANT_TABLES: tuple[tuple[str, str], ...] = (
    ("memories", "organization_id"),
    ("user_preferences", "organization_id"),
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.create_table(
        "memories",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("kind", sa.String(length=20), server_default="fact", nullable=False),
        sa.Column("source", sa.String(length=40), nullable=True),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("embedding_model", sa.String(length=64), nullable=False),
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
            "kind IN ('fact', 'preference', 'summary')",
            name="ck_memories_kind",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_memories_organization_id",
        "memories",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_memories_org_user",
        "memories",
        ["organization_id", "user_id"],
        unique=False,
    )
    # HNSW index for cosine-similarity ANN scans; used by the `<=>` operator
    # (SQLAlchemy: `Memory.embedding.cosine_distance(query_vec)`).
    op.execute(
        "CREATE INDEX ix_memories_embedding_hnsw "
        "ON memories USING hnsw (embedding vector_cosine_ops);"
    )

    op.create_table(
        "user_preferences",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("key", sa.String(length=100), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
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
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "organization_id", "user_id", "key", name="uq_user_preferences_org_user_key"
        ),
    )
    op.create_index(
        "ix_user_preferences_organization_id",
        "user_preferences",
        ["organization_id"],
        unique=False,
    )

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
    op.drop_index("ix_user_preferences_organization_id", table_name="user_preferences")
    op.drop_table("user_preferences")
    op.execute("DROP INDEX IF EXISTS ix_memories_embedding_hnsw;")
    op.drop_index("ix_memories_org_user", table_name="memories")
    op.drop_index("ix_memories_organization_id", table_name="memories")
    op.drop_table("memories")
    # Leaving the vector extension in place — other future rows may depend on it,
    # and CREATE EXTENSION IF NOT EXISTS is idempotent on re-upgrade.
