"""Memory + UserPreference models. Both tenant-scoped, RLS-locked.

`memories.embedding` is a pgvector(1024) column matched to the 5a embedding
provider's default dimension (voyage-3.5 / mock). The HNSW index in the
migration uses `vector_cosine_ops` so `embedding <=> query` (via
`Memory.embedding.cosine_distance(query)` in SQLAlchemy) can use the ANN
scan at scale.

`embedding_model` is stored per-row so a future model swap doesn't silently
mix incompatible vector spaces — a query would clearly return rows tagged
with a different model.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from pgvector.sqlalchemy import Vector
from sqlalchemy import CheckConstraint, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import SoftDeleteMixin, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.infrastructure.db.models.identity import User
    from app.infrastructure.db.models.tenancy import Organization


MEMORY_KINDS = ("fact", "preference", "summary")
EMBEDDING_DIMENSION = 1024


class Memory(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "memories"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False, server_default="fact")
    source: Mapped[str | None] = mapped_column(String(40), nullable=True)
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIMENSION), nullable=False)
    embedding_model: Mapped[str] = mapped_column(String(64), nullable=False)

    organization: Mapped[Organization] = relationship()
    user: Mapped[User] = relationship()

    __table_args__ = (
        CheckConstraint(
            f"kind IN {MEMORY_KINDS!r}",
            name="ck_memories_kind",
        ),
        Index("ix_memories_organization_id", "organization_id"),
        Index("ix_memories_org_user", "organization_id", "user_id"),
        # HNSW index is created in the migration via raw SQL — SQLAlchemy Index
        # doesn't cleanly express `USING hnsw (col vector_cosine_ops)`.
    )


class UserPreference(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "user_preferences"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[Any] = mapped_column(JSONB, nullable=False)

    organization: Mapped[Organization] = relationship()
    user: Mapped[User] = relationship()

    __table_args__ = (
        UniqueConstraint(
            "organization_id", "user_id", "key", name="uq_user_preferences_org_user_key"
        ),
        Index("ix_user_preferences_organization_id", "organization_id"),
    )
