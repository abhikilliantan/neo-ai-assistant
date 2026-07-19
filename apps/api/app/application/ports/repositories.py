"""Repository ports. Concrete impls live in infrastructure/db/repositories.py."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from app.infrastructure.db.models import (
        Membership,
        Organization,
        Role,
        Session,
        User,
    )


class UserRepositoryPort(Protocol):
    async def create(self, *, email: str, password_hash: str) -> User: ...
    async def get_by_email_normalized(self, email: str) -> User | None: ...
    async def get_by_id(self, user_id: UUID) -> User | None: ...


class OrganizationRepositoryPort(Protocol):
    async def create_with_unique_slug(self, name: str) -> Organization: ...


class MembershipRepositoryPort(Protocol):
    async def create(
        self,
        *,
        user_id: UUID,
        organization_id: UUID,
        role_id: UUID,
        status: str = "active",
    ) -> Membership: ...
    async def list_for_user(
        self, user_id: UUID, *, active_only: bool = True
    ) -> list[Membership]: ...


class RoleRepositoryPort(Protocol):
    async def get_by_name(self, name: str) -> Role | None: ...


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
