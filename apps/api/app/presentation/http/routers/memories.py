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

from uuid import UUID

from fastapi import APIRouter, status
from fastapi.responses import Response

from app.infrastructure.db.repositories import MemoryRepository, UserPreferenceRepository
from app.presentation.http.deps import CurrentTenantDep, CurrentUserDep, TenantSessionDep
from app.presentation.http.schemas.memory import (
    MemoryOut,
    PreferenceOut,
    PreferenceUpsertRequest,
)
from app.shared.exceptions.auth import AuthenticationError
from app.shared.exceptions.common import NotFoundError

router = APIRouter(prefix="/api/v1", tags=["memories"])


# --- memories ---------------------------------------------------------------


@router.get("/memories", response_model=list[MemoryOut])
async def list_memories(
    user: CurrentUserDep,
    tenant_id: CurrentTenantDep,
    session: TenantSessionDep,
) -> list[MemoryOut]:
    if tenant_id is None:
        raise AuthenticationError("user has no active tenant")
    rows = await MemoryRepository(session).list_for_user(
        organization_id=tenant_id,
        user_id=user.id,
        active_only=True,
    )
    return [
        MemoryOut(
            id=m.id,
            content=m.content,
            kind=m.kind,
            source=m.source,
            created_at=m.created_at,
        )
        for m in rows
    ]


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
