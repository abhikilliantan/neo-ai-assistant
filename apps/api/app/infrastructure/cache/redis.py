"""Redis client factory. Async, connection-pooled."""

from __future__ import annotations

from redis.asyncio import Redis, from_url

from app.infrastructure.config import Settings


def build_redis(settings: Settings) -> Redis:
    return from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=True,
    )
