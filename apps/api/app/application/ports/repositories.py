"""Repository ports. Concrete impls live in infrastructure/db/repositories.py."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from app.infrastructure.db.models import Membership, Organization, Session, User


class UserRepositoryPort(Protocol):
    async def get_by_id(self, user_id: UUID) -> User | None: ...


class SessionRepositoryPort(Protocol):
    async def create(
        self,
        *,
        user_id: UUID,
        refresh_token_hash: str,
        expires_at: datetime,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> Session: ...
    async def get_by_refresh_hash(self, refresh_token_hash: str) -> Session | None: ...
    async def revoke(self, session_id: UUID) -> None: ...


class SystemRepositoryPort(Protocol):
    """Privileged surface — the only cross-tenant path. Keep this tiny."""

    async def find_user_by_email(self, email_normalized: str) -> User | None: ...
    async def list_memberships_for_user(
        self, user_id: UUID, *, active_only: bool = True
    ) -> list[Membership]: ...
    async def register_bootstrap(
        self,
        *,
        email_normalized: str,
        password_hash: str,
        org_name: str,
        role_name: str = "owner",
    ) -> tuple[User, Organization, Membership]: ...
