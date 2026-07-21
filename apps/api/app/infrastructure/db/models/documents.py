"""Document + DocumentChunk models (Phase 8b). Both tenant-scoped, RLS-locked.

`documents.full_text` is the CANONICAL anchor: a chunk's char offsets index into
THIS exact string, so it must be stored, never re-derived from a re-parse (which
could silently produce a different string → silently wrong highlights).

`document_chunks` carries its OWN `organization_id` so RLS holds on the chunk
table directly — retrieval never depends on the join to `documents` for tenant
isolation. `embedding` is `Vector(1024)` matched to the Phase 5 provider default;
the HNSW `vector_cosine_ops` index (created in the migration) backs cosine ANN
scans via `<=>`. `embedding_model` is stored per-row so a model swap can be
filtered out at search time (5d guard) rather than poisoning results with
foreign-vector-space rows.

The provenance columns (`char_start`/`char_end` mandatory; `page_start`/
`page_end`/`section` nullable) are the persisted form of 8a's `DocumentPosition`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import SoftDeleteMixin, TimestampMixin, UUIDPKMixin
from app.infrastructure.db.models.memory import EMBEDDING_DIMENSION

if TYPE_CHECKING:
    from app.infrastructure.db.models.identity import User
    from app.infrastructure.db.models.tenancy import Organization

# ingest status. `ready` = fully ingested (document + all chunks committed).
# `pending`/`failed` are reserved for 8c's out-of-band bookkeeping if it does
# async ingest; the 8b service only ever writes `ready` (all-or-nothing txn).
DOCUMENT_STATUSES = ("pending", "ready", "failed")


class Document(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "documents"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Documents belong to the ORGANISATION, not the uploader. Deleting a user
    # (e.g. an employee leaving) must NOT delete the org's documents — the FK is
    # SET NULL, so the row survives with uploaded_by_user_id going NULL.
    uploaded_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    filename: Mapped[str] = mapped_column(String(1024), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="ready")
    # Canonical extracted text — chunk char offsets index into THIS string.
    full_text: Mapped[str] = mapped_column(Text, nullable=False)

    organization: Mapped[Organization] = relationship()
    uploaded_by: Mapped[User | None] = relationship()

    __table_args__ = (
        CheckConstraint(
            f"status IN {DOCUMENT_STATUSES!r}",
            name="ck_documents_status",
        ),
        Index("ix_documents_organization_id", "organization_id"),
    )


class DocumentChunk(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "document_chunks"

    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    # Own tenant column so RLS holds on THIS table, not only via the join.
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    ordinal: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSION), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(64), nullable=False)
    # Provenance (8a DocumentPosition). char offsets mandatory; the rest nullable
    # rather than faked — page only for paginated formats, section a best-effort hint.
    char_start: Mapped[int] = mapped_column(Integer, nullable=False)
    char_end: Mapped[int] = mapped_column(Integer, nullable=False)
    page_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    page_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String(255), nullable=True)

    document: Mapped[Document] = relationship()
    organization: Mapped[Organization] = relationship()

    __table_args__ = (
        UniqueConstraint("document_id", "ordinal", name="uq_document_chunks_doc_ordinal"),
        Index("ix_document_chunks_organization_id", "organization_id"),
        Index("ix_document_chunks_document_id", "document_id"),
        # HNSW index created in the migration via raw SQL (vector_cosine_ops).
    )
