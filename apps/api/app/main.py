"""FastAPI application factory + lifespan."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.ai.agents import build_agent_registry
from app.ai.documents import (
    build_chunker,
    build_document_ingest_service,
    build_document_parser,
)
from app.ai.extractors import build_memory_extractor
from app.ai.providers import build_chat_provider
from app.ai.providers.embeddings import build_embedding_provider
from app.ai.tools import build_tool_registry
from app.ai.workflows import build_workflow_client, build_workflow_registry
from app.ai.workflows.urlguard import system_resolver
from app.application.ports.health import HealthCheck
from app.core.exceptions import register_exception_handlers
from app.core.middleware import RequestContextMiddleware
from app.infrastructure.cache import build_redis
from app.infrastructure.config import Settings, get_settings
from app.infrastructure.db import build_database, build_system_database
from app.infrastructure.health import DatabaseHealthCheck, RedisHealthCheck
from app.infrastructure.logging import configure_logging, get_logger
from app.infrastructure.storage import build_storage_provider, probe_storage_writable
from app.presentation.http.routers import (
    agents_router,
    auth_router,
    chat_router,
    conversations_router,
    documents_router,
    memories_router,
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
    memory_extractor = build_memory_extractor(settings, chat_provider)
    tool_registry = build_tool_registry(settings)
    workflow_client = build_workflow_client(settings)  # fail-fast if misconfigured
    workflow_registry = build_workflow_registry(settings)
    # 7d: the "operator" agent's permissions derive from the live workflow set.
    agent_registry = build_agent_registry(settings, workflow_names=workflow_registry.list_names())
    # 8a: document parser + chunker (mock default). Fail-fast if misconfigured.
    document_parser = build_document_parser(settings)
    chunker = build_chunker(settings)
    # 8b: ingest service. Its constructor runs the token-cap guard, so a
    # chunk_size that could be silently truncated at embed fails HERE, at startup.
    document_ingest = build_document_ingest_service(
        settings,
        parser=document_parser,
        chunker=chunker,
        embedding_provider=embedding_provider,
    )
    # ADR 0002: original-file store. Bytes live outside the DB behind this port.
    storage = build_storage_provider(settings)  # fail-fast if misconfigured
    # Fail-fast at BOOT if the storage root isn't writable (e.g. a root-owned
    # volume) — a clear error naming the root beats 500-ing the first upload.
    await probe_storage_writable(storage, root=settings.document_storage_root)
    checks: list[HealthCheck] = [
        DatabaseHealthCheck(name="postgres", db=database),
        RedisHealthCheck(name="redis", redis=redis),
    ]

    app.state.database = database
    app.state.system_database = system_database
    app.state.redis = redis
    app.state.chat_provider = chat_provider
    app.state.embedding_provider = embedding_provider
    app.state.memory_extractor = memory_extractor
    app.state.tool_registry = tool_registry
    app.state.agent_registry = agent_registry
    app.state.workflow_client = workflow_client
    app.state.workflow_registry = workflow_registry
    # 7f-2: resolver for validating tenant workflow URLs at read time. Real
    # getaddrinfo in prod; conftest pins an offline one so tests never hit DNS.
    app.state.workflow_url_resolver = system_resolver
    app.state.document_parser = document_parser
    app.state.chunker = chunker
    app.state.document_ingest = document_ingest
    app.state.storage = storage
    app.state.health_checks = checks
    log.info(
        "startup",
        version=__version__,
        env=settings.python_env,
        ai_provider=settings.ai_provider,
        embedding_provider=settings.embedding_provider,
        memory_extractor=settings.memory_extractor,
        tools=",".join(t["name"] for t in tool_registry.specs()),
        agents=",".join(agent_registry.list_names()),
        workflows=",".join(workflow_registry.list_names()),
        documents=settings.document_parser,
    )

    try:
        yield
    finally:
        log.info("shutdown")
        if hasattr(chat_provider, "close"):
            await chat_provider.close()
        if hasattr(embedding_provider, "close"):
            await embedding_provider.close()
        # 7c: the n8n client holds a pooled httpx client; the mock has no close.
        if hasattr(workflow_client, "close"):
            await workflow_client.close()
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
    app.include_router(memories_router)
    app.include_router(agents_router)
    app.include_router(documents_router)
    return app


app = create_app()
