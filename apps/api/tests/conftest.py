"""Test fixtures — real Alembic migration against a Postgres test DB.

Sessions come in three flavors:
  - `db_session` — `neo` (privileged) session for test assertions (bypasses RLS).
  - `db_app` / `db_client` — FastAPI app wired with both `neo` (system) and
    `neo_app` (runtime) databases, matching production.
  - `app_session_with_tenant(t)` — helper to open a `neo_app` session and
    SET LOCAL app.current_tenant, for the isolation tests.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

import asyncpg
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.application.ports.health import HealthCheck
from app.infrastructure.config import Settings, get_settings
from app.infrastructure.db import Database
from app.infrastructure.db import models as _models  # noqa: F401 register metadata
from app.main import create_app

_DEFAULT_TEST_DSN = "postgresql+asyncpg://neo:neo@localhost:5433/neo_test"
_DEFAULT_TEST_APP_DSN = "postgresql+asyncpg://neo_app:neo_app@localhost:5433/neo_test"
_DEFAULT_ADMIN_DSN = "postgres://neo:neo@localhost:5433/postgres"


def _test_dsn() -> str:
    return os.environ.get("TEST_DATABASE_URL", _DEFAULT_TEST_DSN)


def _test_app_dsn() -> str:
    return os.environ.get("TEST_APP_DATABASE_URL", _DEFAULT_TEST_APP_DSN)


def _admin_dsn() -> str:
    return os.environ.get("TEST_ADMIN_DSN", _DEFAULT_ADMIN_DSN)


# --- stubbed fixtures for non-DB tests --------------------------------------


@dataclass
class _StubCheck:
    name: str
    ok: bool = True

    async def check(self) -> bool:
        return self.ok


@pytest.fixture
def settings() -> Settings:
    return Settings(
        python_env="test",
        database_url="postgresql+asyncpg://x/x",
        app_database_url="postgresql+asyncpg://x/x",
        redis_url="redis://x",
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
    app = create_app(settings)
    app.state.database = None
    app.state.system_database = None
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


# --- DB-backed fixtures (real Alembic migration) ----------------------------


async def _ensure_db_exists(dsn: str) -> None:
    """Create the test DB via asyncpg if it's missing."""
    db_name = dsn.rsplit("/", 1)[-1]
    try:
        probe = await asyncpg.connect(dsn.replace("+asyncpg", ""))
        await probe.close()
        return
    except asyncpg.InvalidCatalogNameError:
        conn = await asyncpg.connect(_admin_dsn())
        try:
            await conn.execute(f'CREATE DATABASE "{db_name}"')
        finally:
            await conn.close()


def _run_alembic_upgrade(dsn: str) -> None:
    """Run `alembic upgrade head` via subprocess.

    Subprocess avoids nested event-loop trouble (alembic env.py calls
    asyncio.run internally); it also keeps app-side settings caching
    from mixing with the migration's settings load.
    """
    api_dir = Path(__file__).resolve().parent.parent
    env = {
        **os.environ,
        "DATABASE_URL": dsn,
        "APP_DATABASE_URL": _test_app_dsn(),
    }
    result = subprocess.run(
        ["uv", "run", "--package", "neo-api", "alembic", "upgrade", "head"],
        cwd=str(api_dir),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"alembic upgrade failed (exit {result.returncode}):\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


@pytest.fixture(scope="session")
def _apply_migrations() -> bool:
    """Session-scoped SYNC fixture: drop schema and run `alembic upgrade head` once.

    Sync so that the setup doesn't bind to any particular event loop —
    subsequent function-scoped async fixtures can each get their own loop.
    """
    import asyncio

    dsn = _test_dsn()
    asyncio.run(_ensure_db_exists(dsn))
    # Drop and recreate the schema before migrating.
    asyncio.run(_reset_schema(dsn))
    _run_alembic_upgrade(dsn)
    return True


async def _reset_schema(dsn: str) -> None:
    engine = create_async_engine(dsn, pool_pre_ping=True)
    try:
        async with engine.begin() as conn:
            await conn.execute(text("DROP SCHEMA public CASCADE"))
            await conn.execute(text("CREATE SCHEMA public"))
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_engine(_apply_migrations: bool) -> AsyncIterator[AsyncEngine]:
    """Per-test neo engine. Truncates user data + disposes on teardown."""
    engine = create_async_engine(_test_dsn(), pool_pre_ping=True)
    try:
        yield engine
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text("TRUNCATE users, organizations, sessions RESTART IDENTITY CASCADE")
            )
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """`neo` session — bypasses RLS. Use for assertions on test data."""
    sm = async_sessionmaker(db_engine, expire_on_commit=False)
    async with sm() as s:
        yield s


@pytest_asyncio.fixture
async def app_engine(_apply_migrations: bool) -> AsyncIterator[AsyncEngine]:
    """`neo_app` engine — RLS-enforced. Use for isolation tests."""
    engine = create_async_engine(_test_app_dsn(), pool_pre_ping=True)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def app_session_factory(
    app_engine: AsyncEngine,
) -> Callable[[UUID | None], AsyncSession]:
    """Return a factory that builds a neo_app session with an optional tenant GUC.

    Usage:
        s = await app_session_factory(tenant_a)
        # ... do queries under RLS filtered by tenant_a ...
        await s.close()
    """
    sm = async_sessionmaker(app_engine, expire_on_commit=False)

    async def _factory(tenant_id: UUID | None) -> AsyncSession:
        s = sm()
        await s.begin()
        if tenant_id is not None:
            await s.execute(
                text("SELECT set_config('app.current_tenant', :t, true)").bindparams(
                    t=str(tenant_id)
                )
            )
        return s

    return _factory


@pytest_asyncio.fixture
async def db_app(
    db_engine: AsyncEngine,
    app_engine: AsyncEngine,
) -> AsyncIterator[FastAPI]:
    settings = Settings(
        python_env="test",
        database_url=_test_dsn(),
        app_database_url=_test_app_dsn(),
        redis_url="redis://x",
        jwt_secret_key="test-secret-key-at-least-32-bytes-long-xxxxx",
    )
    app = create_app(settings)
    system_sm = async_sessionmaker(db_engine, expire_on_commit=False)
    app_sm = async_sessionmaker(app_engine, expire_on_commit=False)
    app.state.database = Database(engine=app_engine, sessionmaker=app_sm)
    app.state.system_database = Database(engine=db_engine, sessionmaker=system_sm)
    app.state.redis = None
    app.state.health_checks = []
    yield app


@pytest_asyncio.fixture
async def db_client(db_app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def _override_jwt_secret_for_tests(monkeypatch: pytest.MonkeyPatch) -> None:
    """Silence InsecureKeyLengthWarning and stabilize signing across tests."""
    monkeypatch.setenv("JWT_SECRET_KEY", "test-secret-key-at-least-32-bytes-long-xxxxx")
    get_settings.cache_clear()
