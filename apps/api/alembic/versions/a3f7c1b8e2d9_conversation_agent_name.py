"""conversation agent name — nullable per-thread agent selector

Revision ID: a3f7c1b8e2d9
Revises: c9f4e2b7d8a5
Create Date: 2026-07-20 10:00:00.000000

Adds `conversations.agent_name` for phase 6j (per-conversation agent
persistence). Nullable on purpose:
  - NULL means "never explicitly set" and resolves to the runtime default
    at read time. This lets us rename/migrate DEFAULT_AGENT_NAME later
    without touching any existing rows.
  - No DB default (a default here would erase the "never set" signal on
    every insert).
  - No backfill: existing rows stay NULL and read as the current default,
    same as if they'd been created today with no agent picker.

No RLS / policy change — the existing tenant-scoped FOR ALL policy on
`conversations` already covers the new column.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a3f7c1b8e2d9"
down_revision: str | None = "c9f4e2b7d8a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "conversations",
        sa.Column("agent_name", sa.String(length=64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("conversations", "agent_name")
