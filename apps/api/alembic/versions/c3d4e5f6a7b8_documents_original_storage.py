"""documents original-file storage pointer + provenance (ADR 0002 slice 1)

Revision ID: c3d4e5f6a7b8
Revises: b7e3d9a1f2c4
Create Date: 2026-07-22 12:00:00.000000

Adds `documents.storage_key`, `storage_backend`, `content_sha256` — the opaque
pointer to the original uploaded bytes (which now live OUTSIDE the DB behind a
StorageProvider), plus the writing backend and a SHA-256 integrity anchor for
reprocessing/dedup.

All three are NULLABLE with no server default: legacy rows predate storage and
their originals are gone, so they legitimately have no pointer. New uploads always
set them. `storage_backend`/`content_sha256` mirror the per-row provenance
discipline of `embedding_model`/`chunker` on `document_chunks`.

No RLS / policy change — `documents` is already RLS-locked, and the storage layer
is outside RLS by design (tenancy is enforced by the pointer-row lookup).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b7e3d9a1f2c4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("storage_key", sa.String(length=512), nullable=True))
    op.add_column("documents", sa.Column("storage_backend", sa.String(length=32), nullable=True))
    op.add_column("documents", sa.Column("content_sha256", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("documents", "content_sha256")
    op.drop_column("documents", "storage_backend")
    op.drop_column("documents", "storage_key")
