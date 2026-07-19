"""FastAPI application factory + lifespan."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.ai.providers import build_chat_provider
from app.ai.providers.embeddings import build_embedding_provider
from app.application.ports.health import HealthCheck
from app.core.exceptions import register_exception_handlers
from app.core.middleware import RequestContextMiddleware
from app.infrastructure.cache import build_redis
from app.infrastructure.config import Settings, get_settings
from app.infrastructure.db import build_database, build_system_database
from app.infrastructure.health import DatabaseHealthCheck, RedisHealthCheck
from app.infrastructure.logging import configure_logging, get_logger
from app.presentation.http.routers import (
    auth_router,
    chat_router,
    conversations_router,
    system_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings: Settings = app.state.settings
    log = get_logger("lifespan")

    database = build_database(settings)  # neo_app (RLS-enforced)
    system_database = build_system_database(settings)  # neo (privileged)
    redis = build_redis(settings)
    chat_provider = build_chat_provider(settings)  # fail-fast if misconfigured
    embedding_provider = build_embedding_provider(settings)  # fail-fast if misconfigured
    checks: list[HealthCheck] = [
        DatabaseHealthCheck(name="postgres", db=database),
        RedisHealthCheck(name="redis", redis=redis),
    ]

    app.state.database = database
    app.state.system_database = system_database
    app.state.redis = redis
    app.state.chat_provider = chat_provider
    app.state.embedding_provider = embedding_provider
    app.state.health_checks = checks
    log.info(
        "startup",
        version=__version__,
        env=settings.python_env,
        ai_provider=settings.ai_provider,
        embedding_provider=settings.embedding_provider,
    )

    try:
        yield
    finally:
        log.info("shutdown")
        if hasattr(chat_provider, "close"):
            await chat_provider.close()
        if hasattr(embedding_provider, "close"):
            await embedding_provider.close()
        await redis.aclose()
        await database.dispose()
        await system_database.dispose()


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

    # Belt-and-braces: even if a `/_test/*` route is ever accidentally wired
    # into production code, refuse to serve it outside python_env=="test".
    # Test suites build their own app via create_app(Settings(python_env="test"))
    # and mount `/_test/*` routes onto that instance only.
    if settings.python_env != "test":

        @app.middleware("http")
        async def _block_test_routes(request: Request, call_next):  # type: ignore[no-untyped-def]
            if request.url.path.startswith("/_test/"):
                return JSONResponse({"error": "not found"}, status_code=404)
            return await call_next(request)

    register_exception_handlers(app)
    app.include_router(system_router)
    app.include_router(auth_router)
    app.include_router(chat_router)
    app.include_router(conversations_router)
    return app


app = create_app()
