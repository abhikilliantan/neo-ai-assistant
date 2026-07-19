"""chat persistence — conversations + messages, RLS-locked

Revision ID: b2e5f7a1c9d3
Revises: f9c8a2b1d3e4
Create Date: 2026-07-19 09:00:00.000000

Two new tenant-scoped tables under the neo_app/RLS regime:
  - conversations: soft-deletable, timestamped, one row per thread
  - messages: append-only log; organization_id denormalized off the parent
    conversation so the RLS predicate is a single-column btree comparison
    rather than a per-row subquery into conversations.

Both tables get ENABLE + FORCE ROW LEVEL SECURITY and one FOR ALL policy
matching organization_id against `app.current_tenant`, same pattern as
memberships / api_keys.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b2e5f7a1c9d3"
down_revision: str | None = "f9c8a2b1d3e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TENANT_TABLES: tuple[tuple[str, str], ...] = (
    ("conversations", "organization_id"),
    ("messages", "organization_id"),
)


def upgrade() -> None:
    op.create_table(
        "conversations",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_conversations_organization_id",
        "conversations",
        ["organization_id"],
        unique=False,
    )
    # Composite (organization_id, last_message_at DESC NULLS LAST) for the
    # tenant-scoped recency list. Raw SQL because SQLAlchemy Index does not
    # cleanly express per-column ordering.
    op.execute(
        "CREATE INDEX ix_conversations_org_last_msg "
        "ON conversations (organization_id, last_message_at DESC NULLS LAST);"
    )

    op.create_table(
        "messages",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("model", sa.String(length=255), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("finish_reason", sa.String(length=64), nullable=True),
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        # clock_timestamp() (not now()) so two messages inserted in the same
        # transaction get distinct wall-clock timestamps — required for
        # deterministic in-thread ordering when a chat turn persists both
        # user + assistant messages together.
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("clock_timestamp()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('system', 'user', 'assistant')",
            name="ck_messages_role",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["conversation_id"], ["conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_messages_conversation_id_created_at",
        "messages",
        ["conversation_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "ix_messages_organization_id",
        "messages",
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
    # Policies drop with the tables.
    op.drop_index("ix_messages_organization_id", table_name="messages")
    op.drop_index("ix_messages_conversation_id_created_at", table_name="messages")
    op.drop_table("messages")
    op.execute("DROP INDEX IF EXISTS ix_conversations_org_last_msg;")
    op.drop_index("ix_conversations_organization_id", table_name="conversations")
    op.drop_table("conversations")
