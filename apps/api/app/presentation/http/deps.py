"""FastAPI dependencies — DI wiring from app.state into routers.

Session lifecycle:
  - Each session dep wraps its work in `session.begin()` — commits on
    normal exit, rolls back on exception. Routes DO NOT call commit.
  - `get_tenant_session` additionally sets the `app.current_tenant` GUC
    inside the transaction via set_config(..., true), so Postgres RLS
    filters engage for the caller's org.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.embeddings import EmbeddingProvider
from app.application.ports.health import HealthCheck
from app.application.ports.memory_extraction import MemoryExtractor
from app.infrastructure.config import Settings
from app.infrastructure.db import Database
from app.infrastructure.db.models import User
from app.infrastructure.db.repositories import UserRepository
from app.infrastructure.security import (
    ExpiredTokenError,
    InvalidTokenError,
    TokenPayload,
    decode_access_token,
)
from app.shared.exceptions.auth import AuthenticationError

_bearer = HTTPBearer(auto_error=False)


def get_app_database(request: Request) -> Database:
    """Runtime DB (neo_app, RLS-enforced)."""
    return request.app.state.database  # type: ignore[no-any-return]


def get_system_database(request: Request) -> Database:
    """Privileged DB (neo). Only used by the SystemRepository code path."""
    return request.app.state.system_database  # type: ignore[no-any-return]


# Back-compat alias for pre-2c-2 imports.
get_database = get_app_database


def get_redis(request: Request) -> Redis:
    return request.app.state.redis  # type: ignore[no-any-return]


def get_embedding_provider(request: Request) -> EmbeddingProvider:
    """Built once in the lifespan; consumed by 5b/5c. No route uses it yet."""
    return request.app.state.embedding_provider  # type: ignore[no-any-return]


def get_memory_extractor(request: Request) -> MemoryExtractor:
    """Built once in the lifespan; consumed by /chat + /chat/stream for the
    best-effort memory write path (5c). Never fails the request when it
    misbehaves — see chat.py::_extract_and_store_memories.
    """
    return request.app.state.memory_extractor  # type: ignore[no-any-return]


def get_app_settings(request: Request) -> Settings:
    """Read the Settings instance built in create_app / lifespan.

    Named `get_app_settings` (not `get_settings`) to avoid colliding with the
    module-level cached factory in infrastructure.config.
    """
    return request.app.state.settings  # type: ignore[no-any-return]


def get_health_checks(request: Request) -> list[HealthCheck]:
    return request.app.state.health_checks  # type: ignore[no-any-return]


async def get_app_session(
    db: Annotated[Database, Depends(get_app_database)],
) -> AsyncIterator[AsyncSession]:
    """neo_app session, transaction-wrapped, no tenant GUC set."""
    async with db.sessionmaker() as session, session.begin():
        yield session


async def get_system_session(
    db: Annotated[Database, Depends(get_system_database)],
) -> AsyncIterator[AsyncSession]:
    """neo session, transaction-wrapped. RLS bypassed at the role level."""
    async with db.sessionmaker() as session, session.begin():
        yield session


AppSessionDep = Annotated[AsyncSession, Depends(get_app_session)]
SystemSessionDep = Annotated[AsyncSession, Depends(get_system_session)]
# Back-compat alias for the 2c-1 session dep name.
SessionDep = AppSessionDep

RedisDep = Annotated[Redis, Depends(get_redis)]
HealthChecksDep = Annotated[list[HealthCheck], Depends(get_health_checks)]
EmbeddingProviderDep = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]
MemoryExtractorDep = Annotated[MemoryExtractor, Depends(get_memory_extractor)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]


def get_access_payload(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> TokenPayload:
    if creds is None or creds.scheme.lower() != "bearer":
        raise AuthenticationError("missing bearer token")
    try:
        return decode_access_token(creds.credentials)
    except (InvalidTokenError, ExpiredTokenError) as e:
        raise AuthenticationError("invalid or expired token") from e


AccessPayloadDep = Annotated[TokenPayload, Depends(get_access_payload)]


async def get_tenant_session(
    db: Annotated[Database, Depends(get_app_database)],
    payload: AccessPayloadDep,
) -> AsyncIterator[AsyncSession]:
    """neo_app session with `app.current_tenant` GUC set (SET LOCAL semantics).

    If the caller's token has no tenant_id (user has no active org), we
    intentionally DO NOT set the GUC — RLS then returns 0 rows on tenant
    tables (safe default). set_config(..., true) is the transaction-local
    equivalent of `SET LOCAL`, and it accepts bind parameters (`SET` does not).
    """
    async with db.sessionmaker() as session, session.begin():
        if payload.tenant_id is not None:
            await session.execute(
                text("SELECT set_config('app.current_tenant', :t, true)").bindparams(
                    t=payload.tenant_id
                )
            )
        yield session


TenantSessionDep = Annotated[AsyncSession, Depends(get_tenant_session)]


async def get_current_user(
    payload: AccessPayloadDep,
    session: AppSessionDep,
) -> User:
    user = await UserRepository(session).get_by_id(UUID(payload.sub))
    if user is None or not user.is_active:
        raise AuthenticationError("user not found or inactive")
    return user


async def get_current_user_scoped(
    payload: AccessPayloadDep,
    db: Annotated[Database, Depends(get_app_database)],
) -> User:
    """Streaming-safe variant: opens/closes a session inside this function so
    NO pooled DB connection is held for the response duration. Use in endpoints
    that return StreamingResponse; the regular `get_current_user` keeps the
    session open across the response body via generator-dep teardown.
    """
    async with db.sessionmaker() as session:
        user = await UserRepository(session).get_by_id(UUID(payload.sub))
        if user is None or not user.is_active:
            raise AuthenticationError("user not found or inactive")
        return user


def get_current_tenant(payload: AccessPayloadDep) -> UUID | None:
    return UUID(payload.tenant_id) if payload.tenant_id is not None else None


CurrentUserDep = Annotated[User, Depends(get_current_user)]
StreamingCurrentUserDep = Annotated[User, Depends(get_current_user_scoped)]
CurrentTenantDep = Annotated[UUID | None, Depends(get_current_tenant)]
