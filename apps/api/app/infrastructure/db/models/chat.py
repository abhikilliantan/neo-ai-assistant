"""Chat persistence models: Conversation + Message. Both tenant-scoped, RLS-locked.

`Message.organization_id` is denormalized off the parent Conversation so the
RLS policy is a single-column btree comparison (no per-row subquery into
conversations). The app-layer invariant — messages.organization_id ==
conversations.organization_id — is also enforced by the WITH CHECK clause on
insert.

Messages are append-only (no updated_at, no soft-delete).
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import SoftDeleteMixin, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.infrastructure.db.models.identity import User
    from app.infrastructure.db.models.tenancy import Organization


MESSAGE_ROLES = ("system", "user", "assistant")


class Conversation(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "conversations"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # 6j: per-thread agent selector. NULL means "never explicitly set" and
    # resolves to DEFAULT_AGENT_NAME at read time — keeping the default
    # renamable without touching old rows. No FK: agents are a code-owned
    # registry, not a table.
    agent_name: Mapped[str | None] = mapped_column(String(64), nullable=True)

    organization: Mapped[Organization] = relationship()
    user: Mapped[User] = relationship()
    messages: Mapped[list[Message]] = relationship(
        back_populates="conversation",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_conversations_organization_id", "organization_id"),
        # Composite for the org-scoped list-by-recency query. Explicit
        # DESC/NULLS LAST is created in the migration (SQLAlchemy Index API
        # doesn't cleanly express column ordering).
    )


class Message(UUIDPKMixin, Base):
    __tablename__ = "messages"

    # No TimestampMixin (only need created_at); no SoftDeleteMixin.
    # clock_timestamp() (not now()) so two rows inserted in the same
    # transaction get distinct timestamps — list_for_conversation needs
    # deterministic ordering when user + assistant messages are persisted
    # together after a chat turn.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.clock_timestamp(),
    )

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    model: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    finish_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

    conversation: Mapped[Conversation] = relationship(back_populates="messages")

    __table_args__ = (
        CheckConstraint(
            f"role IN {MESSAGE_ROLES!r}",
            name="ck_messages_role",
        ),
        Index("ix_messages_conversation_id_created_at", "conversation_id", "created_at"),
        Index("ix_messages_organization_id", "organization_id"),
    )
