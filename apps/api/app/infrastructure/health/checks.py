"""Concrete HealthCheck adapters (implement application.ports.health.HealthCheck)."""

from __future__ import annotations

from dataclasses import dataclass

from redis.asyncio import Redis
from sqlalchemy import text

from app.infrastructure.db import Database


@dataclass(slots=True)
class DatabaseHealthCheck:
    name: str
    db: Database

    async def check(self) -> bool:
        try:
            async with self.db.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception:
            return False
        return True


@dataclass(slots=True)
class RedisHealthCheck:
    name: str
    redis: Redis

    async def check(self) -> bool:
        try:
            return bool(await self.redis.ping())
        except Exception:
            return False
