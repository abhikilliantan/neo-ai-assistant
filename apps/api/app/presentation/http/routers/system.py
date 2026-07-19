"""System endpoints — liveness (/health) and readiness (/ready)."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app import __version__
from app.presentation.http.deps import HealthChecksDep
from app.presentation.http.schemas.system import (
    DependencyStatus,
    HealthResponse,
    ReadinessResponse,
)

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    """Liveness probe — process is up."""
    return HealthResponse(status="ok", version=__version__)


@router.get("/ready", response_model=ReadinessResponse)
async def ready(checks: HealthChecksDep) -> JSONResponse:
    """Readiness probe — dependencies reachable. 503 if any fail."""
    results = await asyncio.gather(*(c.check() for c in checks), return_exceptions=True)
    deps = [
        DependencyStatus(name=c.name, ok=bool(r) and not isinstance(r, BaseException))
        for c, r in zip(checks, results, strict=True)
    ]
    all_ok = all(d.ok for d in deps)
    payload = ReadinessResponse(status="ok" if all_ok else "degraded", dependencies=deps)
    return JSONResponse(
        payload.model_dump(),
        status_code=status.HTTP_200_OK if all_ok else status.HTTP_503_SERVICE_UNAVAILABLE,
    )
