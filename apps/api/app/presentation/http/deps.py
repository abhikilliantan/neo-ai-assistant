"""FastAPI dependencies — DI wiring from app.state into routers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.health import HealthCheck
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


def get_database(request: Request) -> Database:
    return request.app.state.database  # type: ignore[no-any-return]


def get_redis(request: Request) -> Redis:
    return request.app.state.redis  # type: ignore[no-any-return]


def get_health_checks(request: Request) -> list[HealthCheck]:
    return request.app.state.health_checks  # type: ignore[no-any-return]


async def get_db_session(
    db: Annotated[Database, Depends(get_database)],
) -> AsyncIterator[AsyncSession]:
    async with db.sessionmaker() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_db_session)]
RedisDep = Annotated[Redis, Depends(get_redis)]
HealthChecksDep = Annotated[list[HealthCheck], Depends(get_health_checks)]


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


async def get_current_user(
    payload: AccessPayloadDep,
    session: SessionDep,
) -> User:
    user = await UserRepository(session).get_by_id(UUID(payload.sub))
    if user is None or not user.is_active:
        raise AuthenticationError("user not found or inactive")
    return user


def get_current_tenant(payload: AccessPayloadDep) -> UUID | None:
    return UUID(payload.tenant_id) if payload.tenant_id is not None else None


CurrentUserDep = Annotated[User, Depends(get_current_user)]
CurrentTenantDep = Annotated[UUID | None, Depends(get_current_tenant)]
