"""Structured-data models (Capability 1, Slice 1a): Dataset + DatasetColumn +
DatasetRow. All three tenant-scoped and RLS-locked.

An uploaded tracker/spreadsheet becomes a `Dataset` with a typed schema
(`DatasetColumn` rows) and its data as `DatasetRow` rows whose `data` JSONB is
keyed by `column.key`. Later slices (1c) answer status questions with SAFE,
constrained queries (counts/filters/group-by) over this shape — never raw LLM
SQL. `DatasetColumn.semantic_role` lets those slices map canonical fields
(status/owner/priority/due_date) deterministically instead of string-matching
headers.

Each of the three tables carries its OWN `organization_id` so RLS holds on every
table directly, not via a join — matching `document_chunks`. `data_type`,
`status`, and `semantic_role` are stored as String + CheckConstraint ("logical
enums"), consistent with `documents.status` / `documents.extraction_method`
rather than Postgres ENUM types (which are painful to evolve).
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import SoftDeleteMixin, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.infrastructure.db.models.tenancy import Organization

# Ingest lifecycle. `ready` = fully ingested and queryable; `ingesting`/`failed`
# give 1b room for out-of-band bookkeeping. 1a only ever writes `ready`.
DATASET_STATUSES = ("ready", "ingesting", "failed")

# A column's inferred storage type — drives how 1c parses/compares JSONB values.
COLUMN_DATA_TYPES = ("text", "number", "date", "boolean")

# Canonical role a column plays, so later slices resolve "status"/"owner"/etc.
# deterministically. `none` = an ordinary column with no canonical meaning.
COLUMN_SEMANTIC_ROLES = ("status", "owner", "priority", "due_date", "none")


class Dataset(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "datasets"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The uploaded file this dataset was extracted from. SET NULL (not CASCADE):
    # deleting the source document must not silently drop the structured data.
    source_document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="SET NULL"),
        nullable=True,
    )
    sheet_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="ready")
    # Datasets belong to the ORG, not the creator: SET NULL so removing a user
    # never deletes their org's datasets (mirrors documents.uploaded_by_user_id).
    created_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    organization: Mapped[Organization] = relationship()

    __table_args__ = (
        CheckConstraint(f"status IN {DATASET_STATUSES!r}", name="ck_datasets_status"),
        Index("ix_datasets_organization_id", "organization_id"),
    )


class DatasetColumn(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "dataset_columns"

    dataset_id: Mapped[UUID] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    # `name` is the original header verbatim; `key` is the normalized slug used
    # as the JSONB key in DatasetRow.data and in queries — unique per dataset.
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    data_type: Mapped[str] = mapped_column(String(16), nullable=False, server_default="text")
    position: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    nullable: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    semantic_role: Mapped[str] = mapped_column(String(16), nullable=False, server_default="none")

    dataset: Mapped[Dataset] = relationship()
    organization: Mapped[Organization] = relationship()

    __table_args__ = (
        UniqueConstraint("dataset_id", "key", name="uq_dataset_columns_dataset_key"),
        CheckConstraint(f"data_type IN {COLUMN_DATA_TYPES!r}", name="ck_dataset_columns_data_type"),
        CheckConstraint(
            f"semantic_role IN {COLUMN_SEMANTIC_ROLES!r}",
            name="ck_dataset_columns_semantic_role",
        ),
        Index("ix_dataset_columns_dataset_id", "dataset_id"),
        Index("ix_dataset_columns_organization_id", "organization_id"),
    )


class DatasetRow(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "dataset_rows"

    dataset_id: Mapped[UUID] = mapped_column(
        ForeignKey("datasets.id", ondelete="CASCADE"),
        nullable=False,
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    row_index: Mapped[int] = mapped_column(Integer, nullable=False)
    # JSONB keyed by DatasetColumn.key. A GIN index (created in the migration)
    # backs containment/key lookups for 1c's constrained filters.
    data: Mapped[dict[str, object]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    dataset: Mapped[Dataset] = relationship()
    organization: Mapped[Organization] = relationship()

    __table_args__ = (
        Index("ix_dataset_rows_dataset_id", "dataset_id"),
        Index("ix_dataset_rows_organization_id", "organization_id"),
        Index("ix_dataset_rows_dataset_row_index", "dataset_id", "row_index"),
        # GIN index on `data` created in the migration via raw SQL (using gin).
    )
