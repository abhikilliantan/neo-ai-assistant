"""Test fixtures — app + async HTTP client with stubbed dependencies."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.application.ports.health import HealthCheck
from app.infrastructure.config import Settings
from app.main import create_app


@dataclass
class _StubCheck:
    name: str
    ok: bool = True

    async def check(self) -> bool:
        return self.ok


@pytest.fixture
def settings() -> Settings:
    return Settings(
        python_env="test", database_url="postgresql+asyncpg://x/x", redis_url="redis://x"
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    # Build app WITHOUT running lifespan (avoids real DB/Redis).
    app = create_app(settings)
    app.state.database = None
    app.state.redis = None
    app.state.health_checks = [_StubCheck("postgres"), _StubCheck("redis")]
    return app


@pytest_asyncio.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def failing_checks() -> list[HealthCheck]:
    return [_StubCheck("postgres", ok=False), _StubCheck("redis", ok=True)]
