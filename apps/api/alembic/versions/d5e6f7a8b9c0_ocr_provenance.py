"""OCR provenance: documents.extraction_method + document_chunks.ocr_confidence (ADR 0004 slice 1)

Revision ID: d5e6f7a8b9c0
Revises: c3d4e5f6a7b8
Create Date: 2026-07-23 12:00:00.000000

Adds the two OCR provenance columns in ONE migration (ADR 0004 OQ c — capturing
confidence in the same slice is near-free during the OCR pass, whereas a second
migration later is not):

- `documents.extraction_method` — "text" | "ocr". NOT NULL, server_default "text",
  so legacy rows (all natively extracted, predating OCR) backfill correctly. A
  CHECK constraint pins the two allowed values.
- `document_chunks.ocr_confidence` — nullable float, the chunk's mean per-word
  Tesseract confidence (0-100). NULL for natively-extracted chunks.

No RLS / policy change — both tables are already RLS-locked.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d5e6f7a8b9c0"
down_revision: str | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "extraction_method",
            sa.String(length=16),
            nullable=False,
            server_default="text",
        ),
    )
    op.create_check_constraint(
        "ck_documents_extraction_method",
        "documents",
        "extraction_method IN ('text', 'ocr')",
    )
    op.add_column(
        "document_chunks",
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("document_chunks", "ocr_confidence")
    op.drop_constraint("ck_documents_extraction_method", "documents", type_="check")
    op.drop_column("documents", "extraction_method")
