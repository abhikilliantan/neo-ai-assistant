"""FastAPI dependencies — DI wiring from app.state into routers."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.health import HealthCheck
from app.infrastructure.db import Database


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
