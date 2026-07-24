"""Capability 1, Slice 1a — migration f1a2b3c4d5e6 (structured datasets).

Two checks:
  1. After `upgrade head` (conftest applies it), the three tables, the GIN index
     on dataset_rows.data, the UNIQUE(dataset_id, key) constraint, and RLS
     (enabled + forced + a tenant_isolation policy) all exist.
  2. `downgrade -1` then `upgrade head` round-trips cleanly (reversible), run via
     the same alembic subprocess conftest uses. Leaves the DB back at head.
"""

from __future__ import annotations

import os
import subprocess
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

_DATASET_TABLES = ("datasets", "dataset_columns", "dataset_rows")
_PREV_REVISION = "d5e6f7a8b9c0"  # the OCR-provenance migration this one follows


def _test_dsn() -> str:
    return os.environ.get(
        "TEST_DATABASE_URL", "postgresql+asyncpg://neo:neo@localhost:5433/neo_test"
    )


def _test_app_dsn() -> str:
    return os.environ.get(
        "TEST_APP_DATABASE_URL", "postgresql+asyncpg://neo_app:neo_app@localhost:5433/neo_test"
    )


def _run_alembic(*args: str) -> None:
    api_dir = Path(__file__).resolve().parent.parent
    env = {**os.environ, "DATABASE_URL": _test_dsn(), "APP_DATABASE_URL": _test_app_dsn()}
    result = subprocess.run(
        ["uv", "run", "--package", "neo-api", "alembic", *args],
        cwd=str(api_dir),
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"alembic {' '.join(args)} failed (exit {result.returncode}):\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )


@pytest_asyncio.fixture
async def probe_engine(_apply_migrations: bool) -> AsyncIterator[AsyncEngine]:
    """A fresh neo engine (its own connection) so schema reads reflect committed
    DDL from the alembic subprocess, without a stale transaction snapshot."""
    engine = create_async_engine(_test_dsn(), pool_pre_ping=True)
    try:
        yield engine
    finally:
        await engine.dispose()


async def _table_exists(engine: AsyncEngine, table: str) -> bool:
    async with engine.connect() as conn:
        reg = await conn.scalar(text("SELECT to_regclass(:t)").bindparams(t=f"public.{table}"))
    return reg is not None


@pytest.mark.asyncio
async def test_upgrade_created_tables_indexes_and_rls(probe_engine: AsyncEngine) -> None:
    async with probe_engine.connect() as conn:
        for table in _DATASET_TABLES:
            reg = await conn.scalar(text("SELECT to_regclass(:t)").bindparams(t=f"public.{table}"))
            assert reg is not None, f"{table} missing"

        # GIN index on the JSONB payload.
        gin = await conn.scalar(
            text("SELECT indexdef FROM pg_indexes WHERE indexname = 'ix_dataset_rows_data_gin'")
        )
        assert gin is not None
        assert "gin" in gin.lower() and "(data" in gin.lower()

        # UNIQUE (dataset_id, key).
        uq = await conn.scalar(
            text(
                "SELECT conname FROM pg_constraint WHERE conname = 'uq_dataset_columns_dataset_key'"
            )
        )
        assert uq == "uq_dataset_columns_dataset_key"

        # RLS: enabled + forced + one tenant_isolation policy per table.
        for table in _DATASET_TABLES:
            row = (
                await conn.execute(
                    text(
                        "SELECT relrowsecurity, relforcerowsecurity "
                        "FROM pg_class WHERE relname = :t"
                    ).bindparams(t=table)
                )
            ).one()
            assert row.relrowsecurity is True, f"{table} RLS not enabled"
            assert row.relforcerowsecurity is True, f"{table} RLS not forced"
            pol = await conn.scalar(
                text("SELECT polname FROM pg_policy WHERE polname = :p").bindparams(
                    p=f"{table}_tenant_isolation"
                )
            )
            assert pol == f"{table}_tenant_isolation", f"{table} policy missing"


@pytest.mark.asyncio
async def test_downgrade_then_upgrade_roundtrip(probe_engine: AsyncEngine) -> None:
    # Start at head (fixture guarantees it) → tables present.
    for table in _DATASET_TABLES:
        assert await _table_exists(probe_engine, table)

    # Downgrade one revision → the three tables are dropped.
    _run_alembic("downgrade", _PREV_REVISION)
    for table in _DATASET_TABLES:
        assert not await _table_exists(probe_engine, table), f"{table} should be dropped"

    # Upgrade back to head → tables restored (reversible).
    _run_alembic("upgrade", "head")
    for table in _DATASET_TABLES:
        assert await _table_exists(probe_engine, table), f"{table} should be restored"
