"""Repository ports. Concrete impls live in infrastructure/db/repositories.py."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from app.infrastructure.db.models import (
        Conversation,
        Membership,
        Memory,
        Message,
        Organization,
        Session,
        User,
        UserPreference,
    )


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


# --- chat persistence (tenant-scoped, RLS-enforced) --------------------------


class ConversationRepositoryPort(Protocol):
    async def create(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        title: str | None = None,
    ) -> Conversation: ...
    async def get_by_id(self, conversation_id: UUID) -> Conversation | None: ...
    async def list_for_org(
        self, organization_id: UUID, *, active_only: bool = True
    ) -> list[Conversation]: ...
    async def touch(self, conversation_id: UUID) -> None: ...


class MessageRepositoryPort(Protocol):
    async def add(
        self,
        *,
        organization_id: UUID,
        conversation_id: UUID,
        role: str,
        content: str,
        model: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        finish_reason: str | None = None,
    ) -> Message: ...
    async def list_for_conversation(self, conversation_id: UUID) -> list[Message]: ...


# --- memory + preferences (tenant-scoped, RLS-enforced) ---------------------


class MemoryRepositoryPort(Protocol):
    async def add(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        content: str,
        embedding: list[float],
        embedding_model: str,
        kind: str = "fact",
        source: str | None = None,
    ) -> Memory: ...
    async def search_similar(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        query_embedding: list[float],
        limit: int = 5,
        kind: str | None = None,
    ) -> list[tuple[Memory, float]]: ...
    async def list_for_user(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        active_only: bool = True,
    ) -> list[Memory]: ...
    async def get_by_id(self, memory_id: UUID) -> Memory | None: ...
    async def soft_delete(self, memory_id: UUID) -> None: ...


class UserPreferenceRepositoryPort(Protocol):
    async def upsert(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        key: str,
        value: object,
    ) -> UserPreference: ...
    async def get(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        key: str,
    ) -> UserPreference | None: ...
    async def list_for_user(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
    ) -> list[UserPreference]: ...
