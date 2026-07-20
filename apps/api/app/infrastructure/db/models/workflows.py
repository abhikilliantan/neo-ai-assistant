"""Tenant-defined workflow model (Phase 7f-2). Tenant-scoped, RLS-locked.

A `workflows` row is a tenant's own n8n webhook, exposed to the model as a tool
via the operator agent. Rows carry NO secrets — the outbound call uses the
deployment's configured token (per-tenant credentials are a separate problem,
7f-… not this slice). `webhook_url` is validated against the SSRF guard +
admin allowlist at READ time on every request (defense in depth), never trusted
because it was written once.

Name uniqueness is enforced among ACTIVE rows only (partial unique index in the
migration, `WHERE deleted_at IS NULL`) so a soft-deleted name can be reused —
which is what 7f-3's write API will want.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Index, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.base import Base
from app.infrastructure.db.mixins import SoftDeleteMixin, TimestampMixin, UUIDPKMixin

if TYPE_CHECKING:
    from app.infrastructure.db.models.tenancy import Organization


class Workflow(UUIDPKMixin, TimestampMixin, SoftDeleteMixin, Base):
    __tablename__ = "workflows"

    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    input_schema: Mapped[Any] = mapped_column(JSONB, nullable=False)
    webhook_url: Mapped[str] = mapped_column(Text, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    organization: Mapped[Organization] = relationship()

    __table_args__ = (
        Index("ix_workflows_organization_id", "organization_id"),
        # Partial unique index (active rows only) is created in the migration via
        # raw SQL — SQLAlchemy Index doesn't cleanly express `WHERE deleted_at
        # IS NULL` across dialects.
    )
