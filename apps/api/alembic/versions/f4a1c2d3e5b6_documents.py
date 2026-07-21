"""documents + document_chunks — pgvector, HNSW, RLS-locked

Revision ID: f4a1c2d3e5b6
Revises: e7d9c1a2b3f4
Create Date: 2026-07-21 10:00:00.000000

Two new tenant-scoped tables under the neo_app/RLS regime (Phase 8b):
  - documents: an uploaded file's metadata + the CANONICAL extracted text
    (full_text) — chunk char offsets index into that exact string, so it is
    stored as the anchor, never re-derived.
  - document_chunks: retrievable passages with their OWN organization_id (RLS
    holds on the chunk table directly, not only via the join), a vector(1024)
    embedding, embedding_model, and the 8a provenance columns. An HNSW index on
    the embedding (vector_cosine_ops) backs cosine-similarity ANN via `<=>`.

RLS matches memories/workflows: ENABLE + FORCE + one FOR ALL policy on
organization_id, on BOTH tables.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "f4a1c2d3e5b6"
down_revision: str | None = "e7d9c1a2b3f4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


TENANT_TABLES: tuple[tuple[str, str], ...] = (
    ("documents", "organization_id"),
    ("document_chunks", "organization_id"),
)


def upgrade() -> None:
    # vector extension already created by the memories migration; idempotent.
    op.execute("CREATE EXTENSION IF NOT EXISTS vector;")

    op.create_table(
        "documents",
        sa.Column("organization_id", sa.UUID(), nullable=False),
        # Documents belong to the org, not the uploader: SET NULL so deleting a
        # user never deletes their org's documents (silent data loss otherwise).
        sa.Column("uploaded_by_user_id", sa.UUID(), nullable=True),
        sa.Column("filename", sa.String(length=1024), nullable=False),
        sa.Column("content_type", sa.String(length=255), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="ready", nullable=False),
        sa.Column("full_text", sa.Text(), nullable=False),
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
            "status IN ('pending', 'ready', 'failed')",
            name="ck_documents_status",
        ),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_documents_organization_id",
        "documents",
        ["organization_id"],
        unique=False,
    )

    op.create_table(
        "document_chunks",
        sa.Column("document_id", sa.UUID(), nullable=False),
        sa.Column("organization_id", sa.UUID(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1024), nullable=False),
        sa.Column("embedding_model", sa.String(length=64), nullable=False),
        sa.Column("char_start", sa.Integer(), nullable=False),
        sa.Column("char_end", sa.Integer(), nullable=False),
        sa.Column("page_start", sa.Integer(), nullable=True),
        sa.Column("page_end", sa.Integer(), nullable=True),
        sa.Column("section", sa.String(length=255), nullable=True),
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
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["organization_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("document_id", "ordinal", name="uq_document_chunks_doc_ordinal"),
    )
    op.create_index(
        "ix_document_chunks_organization_id",
        "document_chunks",
        ["organization_id"],
        unique=False,
    )
    op.create_index(
        "ix_document_chunks_document_id",
        "document_chunks",
        ["document_id"],
        unique=False,
    )
    # HNSW index for cosine-similarity ANN scans over chunk embeddings.
    op.execute(
        "CREATE INDEX ix_document_chunks_embedding_hnsw "
        "ON document_chunks USING hnsw (embedding vector_cosine_ops);"
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
    for table, _column in TENANT_TABLES:
        op.execute(f"DROP POLICY IF EXISTS {table}_tenant_isolation ON {table};")
    op.execute("DROP INDEX IF EXISTS ix_document_chunks_embedding_hnsw;")
    op.drop_index("ix_document_chunks_document_id", table_name="document_chunks")
    op.drop_index("ix_document_chunks_organization_id", table_name="document_chunks")
    op.drop_table("document_chunks")
    op.drop_index("ix_documents_organization_id", table_name="documents")
    op.drop_table("documents")
    # Leave the vector extension in place — the memories table still needs it.
