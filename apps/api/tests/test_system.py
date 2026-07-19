"""Smoke tests for /health and /ready."""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from app.application.ports.health import HealthCheck


@pytest.mark.asyncio
async def test_health_ok(client: AsyncClient) -> None:
    r = await client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert "version" in body


@pytest.mark.asyncio
async def test_ready_ok(client: AsyncClient) -> None:
    r = await client.get("/ready")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert {d["name"] for d in body["dependencies"]} == {"postgres", "redis"}


@pytest.mark.asyncio
async def test_ready_degraded(
    app: FastAPI, client: AsyncClient, failing_checks: list[HealthCheck]
) -> None:
    app.state.health_checks = failing_checks
    r = await client.get("/ready")
    assert r.status_code == 503
    assert r.json()["status"] == "degraded"


@pytest.mark.asyncio
async def test_request_id_echoed(client: AsyncClient) -> None:
    r = await client.get("/health", headers={"X-Request-ID": "abc123"})
    assert r.headers.get("X-Request-ID") == "abc123"
