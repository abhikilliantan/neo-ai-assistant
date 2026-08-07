"""Memory + preference management endpoints.

All routes run under TenantSessionDep so Postgres RLS filters cross-tenant
rows first. Within a tenant there can be multiple users, so every route also
scopes to `current_user.id` — either via the repo query (`list_for_user`,
`upsert`) or via an explicit ownership check (DELETE /memories/{id}).

The DELETE ownership guard exists because `MemoryRepository.soft_delete`
takes only a memory_id: RLS alone would let user A2 (same tenant as A1)
delete A1's memory. We fetch first, check `user_id`, then act.

Unknown id, cross-tenant id (RLS-hidden), and same-tenant-different-user
all collapse to 404 — no existence oracle.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status
from fastapi.responses import Response

from app.ai.memory import save_memory_deduped
from app.infrastructure.db.models.memory import Memory
from app.infrastructure.db.repositories import MemoryRepository, UserPreferenceRepository
from app.presentation.http.deps import (
    CurrentTenantDep,
    CurrentUserDep,
    EmbeddingProviderDep,
    SettingsDep,
    TenantSessionDep,
)
from app.presentation.http.schemas.memory import (
    MemoryCreateRequest,
    MemoryOut,
    PreferenceOut,
    PreferenceUpsertRequest,
)
from app.shared.exceptions.auth import AuthenticationError
from app.shared.exceptions.common import NotFoundError

router = APIRouter(prefix="/api/v1", tags=["memories"])


def _to_out(m: Memory) -> MemoryOut:
    """Whitelist ORM → response: never leaks embedding / org / user / deleted_at."""
    return MemoryOut(
        id=m.id,
        content=m.content,
        kind=m.kind,
        source=m.source,
        created_at=m.created_at,
    )


# --- memories ---------------------------------------------------------------


@router.get("/memories", response_model=list[MemoryOut])
async def list_memories(
    user: CurrentUserDep,
    tenant_id: CurrentTenantDep,
    session: TenantSessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[MemoryOut]:
    if tenant_id is None:
        raise AuthenticationError("user has no active tenant")
    rows = await MemoryRepository(session).list_for_user(
        organization_id=tenant_id,
        user_id=user.id,
        active_only=True,
        limit=limit,
        offset=offset,
    )
    return [_to_out(m) for m in rows]


@router.post("/memories", response_model=MemoryOut, status_code=status.HTTP_201_CREATED)
async def create_memory(
    body: MemoryCreateRequest,
    user: CurrentUserDep,
    tenant_id: CurrentTenantDep,
    session: TenantSessionDep,
    embedding_provider: EmbeddingProviderDep,
    settings: SettingsDep,
) -> MemoryOut:
    """Create a memory (user-initiated). Embeds the content and dedupes against
    the caller's existing memories via the SAME helper the save_memory tool and
    the chat-extraction path use, so an equivalent memory is never stored twice
    (a near-dupe returns the existing row with 201 — idempotent for the UI)."""
    if tenant_id is None:
        raise AuthenticationError("user has no active tenant")
    memory, _created = await save_memory_deduped(
        repo=MemoryRepository(session),
        embedding_provider=embedding_provider,
        organization_id=tenant_id,
        user_id=user.id,
        content=body.content,
        dedupe_threshold=settings.memory_dedupe_min_similarity,
        kind=body.kind,
        source="user",
    )
    return _to_out(memory)


@router.delete("/memories/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: UUID,
    user: CurrentUserDep,
    tenant_id: CurrentTenantDep,
    session: TenantSessionDep,
) -> Response:
    if tenant_id is None:
        raise AuthenticationError("user has no active tenant")
    repo = MemoryRepository(session)
    memory = await repo.get_by_id(memory_id)
    # None → unknown id OR cross-tenant (RLS-hidden). Wrong user_id → same
    # tenant, someone else's row. Both collapse to 404.
    if memory is None or memory.user_id != user.id:
        raise NotFoundError("memory not found")
    await repo.soft_delete(memory_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- preferences ------------------------------------------------------------


@router.get("/preferences", response_model=list[PreferenceOut])
async def list_preferences(
    user: CurrentUserDep,
    tenant_id: CurrentTenantDep,
    session: TenantSessionDep,
) -> list[PreferenceOut]:
    if tenant_id is None:
        raise AuthenticationError("user has no active tenant")
    rows = await UserPreferenceRepository(session).list_for_user(
        organization_id=tenant_id,
        user_id=user.id,
    )
    return [PreferenceOut(key=p.key, value=p.value) for p in rows]


@router.put("/preferences/{key}", response_model=PreferenceOut)
async def upsert_preference(
    key: str,
    body: PreferenceUpsertRequest,
    user: CurrentUserDep,
    tenant_id: CurrentTenantDep,
    session: TenantSessionDep,
) -> PreferenceOut:
    if tenant_id is None:
        raise AuthenticationError("user has no active tenant")
    pref = await UserPreferenceRepository(session).upsert(
        organization_id=tenant_id,
        user_id=user.id,
        key=key,
        value=body.value,
    )
    return PreferenceOut(key=pref.key, value=pref.value)
