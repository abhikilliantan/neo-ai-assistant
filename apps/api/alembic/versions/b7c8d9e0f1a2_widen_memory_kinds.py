"""widen memories.kind CHECK to add 'instruction' and 'other'

The save-memory feature lets the model/user classify a memory as an
instruction ("always do X") or an uncategorised note ("other"), on top of the
original fact/preference/summary. Widen the CHECK constraint to the union —
non-breaking: every existing value stays valid.

Revision ID: b7c8d9e0f1a2
Revises: a1b2c3d4e5f6
"""

from __future__ import annotations

from alembic import op

revision = "b7c8d9e0f1a2"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None

_OLD = "('fact', 'preference', 'summary')"
_NEW = "('fact', 'preference', 'summary', 'instruction', 'other')"


def upgrade() -> None:
    op.drop_constraint("ck_memories_kind", "memories", type_="check")
    op.create_check_constraint("ck_memories_kind", "memories", f"kind IN {_NEW}")


def downgrade() -> None:
    # Reverting narrows the set; rows using the new kinds would violate it, so
    # fold them to 'fact' (a value valid in the old set) before re-narrowing.
    op.execute("UPDATE memories SET kind = 'fact' WHERE kind IN ('instruction', 'other')")
    op.drop_constraint("ck_memories_kind", "memories", type_="check")
    op.create_check_constraint("ck_memories_kind", "memories", f"kind IN {_OLD}")
