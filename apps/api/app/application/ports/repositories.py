"""Repository ports. Concrete impls live in infrastructure/db/repositories.py."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, Protocol
from uuid import UUID

if TYPE_CHECKING:
    from app.infrastructure.db.models import (
        ApiKey,
        Conversation,
        Dataset,
        DatasetColumn,
        DocumentChunk,
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
    async def find_api_keys_by_prefix(self, key_prefix: str) -> list[ApiKey]: ...
    async def touch_api_key_last_used(self, api_key_id: UUID) -> None: ...
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


class ApiKeyRepositoryPort(Protocol):
    """Tenant-scoped API-key management (RLS-enforced). Auth-time lookup lives on
    SystemRepositoryPort — it's cross-tenant."""

    async def create(
        self,
        *,
        organization_id: UUID,
        name: str,
        key_prefix: str,
        key_hash: str,
        scopes: list[str],
    ) -> ApiKey: ...
    async def list_for_org(
        self, organization_id: UUID, *, active_only: bool = True
    ) -> list[ApiKey]: ...
    async def get_by_id(self, api_key_id: UUID) -> ApiKey | None: ...
    async def revoke(self, api_key_id: UUID) -> None: ...


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
        embedding_model: str | None = None,
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


class DocumentRepositoryPort(Protocol):
    """Tenant-scoped document-chunk search (8d). Deferred in 8b until a consumer
    existed; search_documents is that consumer, mirroring how MemoryRepositoryPort
    was introduced by search_memory. Only the method the tool needs is on the
    port — searching. Note: NO user_id — documents are ORG-scoped, not per-user.
    """

    async def search_chunks(
        self,
        *,
        organization_id: UUID,
        query_embedding: list[float],
        limit: int = 5,
        embedding_model: str | None = None,
    ) -> list[tuple[DocumentChunk, float]]: ...


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


# --- structured data (Capability 1, Slice 1a) --------------------------------


@dataclass(frozen=True, slots=True)
class DatasetColumnSpec:
    """A typed-schema column to create, as the ingest layer (1b) produces it.
    `key` is the normalized slug used in DatasetRow.data and in queries."""

    name: str
    key: str
    data_type: str = "text"
    position: int = 0
    nullable: bool = True
    semantic_role: str = "none"


# One row's payload — a mapping from column.key to its cell value (JSON-serializable).
DatasetRowData = Mapping[str, object]


class DatasetRepositoryPort(Protocol):
    """Tenant-scoped structured-dataset persistence (Capability 1). Slice 1a is
    storage-only: create/read/bulk-insert/soft-delete. NO query/aggregation — the
    SAFE constrained-query surface is 1c. Methods take organization_id explicitly
    where a row is created or a list is scoped (audit-visible tenant intent,
    matching the other repos); single-id reads rely on RLS / the caller's session.
    """

    async def create_dataset(
        self,
        *,
        organization_id: UUID,
        name: str,
        description: str | None = None,
        source_document_id: UUID | None = None,
        sheet_name: str | None = None,
        created_by: UUID | None = None,
        status: str = "ready",
    ) -> Dataset: ...
    async def add_columns(
        self,
        *,
        dataset_id: UUID,
        organization_id: UUID,
        columns: Sequence[DatasetColumnSpec],
    ) -> list[DatasetColumn]: ...
    async def bulk_insert_rows(
        self,
        *,
        dataset_id: UUID,
        organization_id: UUID,
        rows: Sequence[DatasetRowData],
        start_index: int = 0,
    ) -> int: ...
    async def get_dataset(self, dataset_id: UUID) -> Dataset | None: ...
    async def list_datasets(
        self, organization_id: UUID, *, active_only: bool = True
    ) -> list[Dataset]: ...
    async def get_columns(self, dataset_id: UUID) -> list[DatasetColumn]: ...
    async def count_rows(self, dataset_id: UUID) -> int: ...
    async def update_row_count(self, dataset_id: UUID, n: int) -> None: ...
    async def soft_delete_dataset(self, dataset_id: UUID) -> None: ...
    async def hard_delete_rows(self, *, dataset_id: UUID, organization_id: UUID) -> int: ...
    async def hard_delete_columns(self, *, dataset_id: UUID, organization_id: UUID) -> int: ...
