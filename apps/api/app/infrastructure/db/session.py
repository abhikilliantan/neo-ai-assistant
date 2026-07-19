"""Async SQLAlchemy engine + session lifecycle."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.infrastructure.config import Settings


@dataclass(slots=True)
class Database:
    """Engine + session factory. Held on app.state, disposed at shutdown."""

    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]

    async def dispose(self) -> None:
        await self.engine.dispose()


def build_database(settings: Settings) -> Database:
    engine = create_async_engine(
        settings.database_url,
        echo=settings.db_echo,
        pool_size=settings.db_pool_size,
        max_overflow=settings.db_pool_max_overflow,
        pool_pre_ping=True,
    )
    sessionmaker = async_sessionmaker(
        engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    return Database(engine=engine, sessionmaker=sessionmaker)


async def get_session(db: Database) -> AsyncIterator[AsyncSession]:
    """Yield a request-scoped session. Wired via FastAPI Depends in interfaces layer."""
    async with db.sessionmaker() as session:
        yield session
