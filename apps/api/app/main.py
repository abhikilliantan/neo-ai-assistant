"""FastAPI application factory + lifespan."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.application.ports.health import HealthCheck
from app.core.exceptions import register_exception_handlers
from app.core.middleware import RequestContextMiddleware
from app.infrastructure.cache import build_redis
from app.infrastructure.config import Settings, get_settings
from app.infrastructure.db import build_database
from app.infrastructure.health import DatabaseHealthCheck, RedisHealthCheck
from app.infrastructure.logging import configure_logging, get_logger
from app.presentation.http.routers import auth_router, system_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    log = get_logger("lifespan")

    database = build_database(settings)
    redis = build_redis(settings)
    checks: list[HealthCheck] = [
        DatabaseHealthCheck(name="postgres", db=database),
        RedisHealthCheck(name="redis", redis=redis),
    ]

    app.state.database = database
    app.state.redis = redis
    app.state.health_checks = checks
    log.info("startup", version=__version__, env=settings.python_env)

    try:
        yield
    finally:
        log.info("shutdown")
        await redis.aclose()
        await database.dispose()


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings)

    app = FastAPI(
        title="Neo AI Assistant API",
        version=__version__,
        lifespan=lifespan,
    )
    app.state.settings = settings

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)
    app.include_router(system_router)
    app.include_router(auth_router)
    return app


app = create_app()
