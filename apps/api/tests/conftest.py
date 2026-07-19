"""Test fixtures — app + async HTTP client with stubbed and DB-backed variants."""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from dataclasses import dataclass

import asyncpg
import pytest
import pytest_asyncio
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.application.ports.health import HealthCheck
from app.infrastructure.config import Settings, get_settings
from app.infrastructure.db import Base, Database
from app.infrastructure.db import models as _models  # noqa: F401  register metadata
from app.main import create_app

_SEED_PERMISSIONS = (
    ("org:read", "Read organization details"),
    ("org:write", "Update organization details"),
    ("org:delete", "Delete an organization"),
    ("member:read", "List members"),
    ("member:write", "Update a member's role"),
    ("member:invite", "Invite a new member"),
    ("member:remove", "Remove a member"),
    ("apikey:read", "List API keys"),
    ("apikey:write", "Create API keys"),
    ("apikey:revoke", "Revoke API keys"),
)
_SEED_ROLES = (
    ("owner", "Full control of the organization."),
    ("admin", "Administer members and API keys; cannot delete the org."),
    ("member", "Read-only baseline."),
)
_SEED_ROLE_PERMS = {
    "owner": tuple(c for c, _ in _SEED_PERMISSIONS),
    "admin": tuple(c for c, _ in _SEED_PERMISSIONS if c != "org:delete"),
    "member": ("org:read", "member:read", "apikey:read"),
}


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
        redis_url="redis://x",
    )


@pytest.fixture
def app(settings: Settings) -> FastAPI:
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


# --- DB-backed fixtures for auth tests --------------------------------------

_DEFAULT_TEST_DSN = "postgresql+asyncpg://neo:neo@localhost:5433/neo_test"
_ADMIN_DSN = "postgres://neo:neo@localhost:5433/postgres"


def _test_dsn() -> str:
    return os.environ.get("TEST_DATABASE_URL", _DEFAULT_TEST_DSN)


async def _ensure_test_db_exists(dsn: str) -> None:
    db_name = dsn.rsplit("/", 1)[-1]
    admin_dsn = os.environ.get("TEST_ADMIN_DSN", _ADMIN_DSN)
    try:
        probe = await asyncpg.connect(dsn.replace("+asyncpg", ""))
        await probe.close()
        return
    except asyncpg.InvalidCatalogNameError:
        conn = await asyncpg.connect(admin_dsn)
        try:
            await conn.execute(f'CREATE DATABASE "{db_name}"')
        finally:
            await conn.close()


async def _seed_rbac(session: AsyncSession) -> None:
    from app.infrastructure.db.models import Permission, Role, RolePermission

    perms_by_code: dict[str, Permission] = {}
    for code, desc in _SEED_PERMISSIONS:
        p = Permission(code=code, description=desc)
        session.add(p)
        perms_by_code[code] = p
    roles_by_name: dict[str, Role] = {}
    for name, desc in _SEED_ROLES:
        r = Role(name=name, description=desc, is_system=True)
        session.add(r)
        roles_by_name[name] = r
    await session.flush()
    for role_name, codes in _SEED_ROLE_PERMS.items():
        for code in codes:
            session.add(
                RolePermission(
                    role_id=roles_by_name[role_name].id,
                    permission_id=perms_by_code[code].id,
                )
            )
    await session.flush()


@pytest_asyncio.fixture
async def db_engine() -> AsyncIterator[AsyncEngine]:
    dsn = _test_dsn()
    await _ensure_test_db_exists(dsn)
    engine = create_async_engine(dsn, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    sm = async_sessionmaker(engine, expire_on_commit=False)
    async with sm() as s:
        await _seed_rbac(s)
        await s.commit()
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    sm = async_sessionmaker(db_engine, expire_on_commit=False)
    async with sm() as s:
        yield s


@pytest_asyncio.fixture
async def db_app(db_engine: AsyncEngine) -> AsyncIterator[FastAPI]:
    settings = Settings(
        python_env="test",
        database_url=_test_dsn(),
        redis_url="redis://x",
        jwt_secret_key="test-secret-key-at-least-32-bytes-long-xxxxx",
    )
    app = create_app(settings)
    sm = async_sessionmaker(db_engine, expire_on_commit=False)
    app.state.database = Database(engine=db_engine, sessionmaker=sm)
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
