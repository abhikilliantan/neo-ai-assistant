"""API-key management — create / list / revoke, for the caller's own org.

Protected by the existing USER auth (CurrentUserDep) and scoped by RLS
(TenantSessionDep): a caller can only ever see or touch their own org's keys.
ponytail: any authenticated org member can manage keys this slice; gate on the
seeded apikey:* RBAC perms once a permission dependency exists.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status
from fastapi.responses import Response

from app.application.use_cases import api_keys as api_keys_uc
from app.infrastructure.db.repositories import ApiKeyRepository
from app.presentation.http.deps import CurrentTenantDep, CurrentUserDep, TenantSessionDep
from app.presentation.http.schemas.api_keys import (
    ApiKeyCreatedResponse,
    ApiKeyCreateRequest,
    ApiKeyOut,
)
from app.shared.exceptions.auth import AuthenticationError
from app.shared.exceptions.common import NotFoundError

router = APIRouter(prefix="/api/v1/api-keys", tags=["api-keys"])


@router.post("", response_model=ApiKeyCreatedResponse, status_code=status.HTTP_201_CREATED)
async def create_api_key(
    body: ApiKeyCreateRequest,
    user: CurrentUserDep,
    tenant_id: CurrentTenantDep,
    session: TenantSessionDep,
) -> ApiKeyCreatedResponse:
    if tenant_id is None:
        raise AuthenticationError("user has no active tenant")
    key, raw = await api_keys_uc.create_api_key(
        organization_id=tenant_id,
        name=body.name,
        scopes=body.scopes,
        keys=ApiKeyRepository(session),
    )
    return ApiKeyCreatedResponse(
        id=key.id,
        name=key.name,
        key_prefix=key.key_prefix,
        scopes=key.scopes,
        created_at=key.created_at,
        api_key=raw,
    )


@router.get("", response_model=list[ApiKeyOut])
async def list_api_keys(
    user: CurrentUserDep,
    tenant_id: CurrentTenantDep,
    session: TenantSessionDep,
) -> list[ApiKeyOut]:
    if tenant_id is None:
        raise AuthenticationError("user has no active tenant")
    rows = await ApiKeyRepository(session).list_for_org(tenant_id, active_only=False)
    return [
        ApiKeyOut(
            id=k.id,
            name=k.name,
            key_prefix=k.key_prefix,
            scopes=k.scopes,
            created_at=k.created_at,
            last_used_at=k.last_used_at,
            revoked_at=k.revoked_at,
        )
        for k in rows
    ]


@router.delete("/{api_key_id}", status_code=status.HTTP_204_NO_CONTENT)
async def revoke_api_key(
    api_key_id: UUID,
    user: CurrentUserDep,
    tenant_id: CurrentTenantDep,
    session: TenantSessionDep,
) -> Response:
    if tenant_id is None:
        raise AuthenticationError("user has no active tenant")
    repo = ApiKeyRepository(session)
    # None → unknown id OR another tenant's key (RLS-hidden). Both collapse to 404.
    if await repo.get_by_id(api_key_id) is None:
        raise NotFoundError("api key not found")
    await repo.revoke(api_key_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
