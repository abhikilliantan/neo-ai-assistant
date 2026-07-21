"""document_chunks.chunker — per-row chunker provenance (ADR 0001 Decision 8)

Revision ID: b7e3d9a1f2c4
Revises: f4a1c2d3e5b6
Create Date: 2026-07-21 12:00:00.000000

Adds `document_chunks.chunker`, the name+version of the algorithm that cut a
row ("fixed-1", "block-aware-1"), mirroring how `embedding_model` records the
vector space. Recorded only — retrieval never filters by it (mixing chunkers is
merely inconsistent, not wrong; a filter would silently hide half the corpus).

Nullable, no server default: a NULL is read as "fixed" (ADR 0001 Decision 8), so
a future insert path that forgets to set it degrades to the historically-correct
value rather than a fabricated one.

BACKFILL: every existing row is set to "fixed-1". Chosen because `FixedSizeChunker`
was the ONLY chunker in existence before this change (the V1 benchmark baseline
was cut by it at chunk_size=1000/overlap=200), so "fixed-1" is the accurate
provenance for all pre-existing rows, not a guess.

No RLS / policy change — the existing tenant-scoped policy on `document_chunks`
already covers the new column.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b7e3d9a1f2c4"
down_revision: str | None = "f4a1c2d3e5b6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "document_chunks",
        sa.Column("chunker", sa.String(length=32), nullable=True),
    )
    # Backfill: all pre-existing rows were produced by FixedSizeChunker.
    op.execute("UPDATE document_chunks SET chunker = 'fixed-1' WHERE chunker IS NULL")


def downgrade() -> None:
    op.drop_column("document_chunks", "chunker")
