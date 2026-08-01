"""FastAPI dependencies — DI wiring from app.state into routers.

Session lifecycle:
  - Each session dep wraps its work in `session.begin()` — commits on
    normal exit, rolls back on exception. Routes DO NOT call commit.
  - `get_tenant_session` additionally sets the `app.current_tenant` GUC
    inside the transaction via set_config(..., true), so Postgres RLS
    filters engage for the caller's org.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.agents import AgentRegistry
from app.ai.documents import DocumentIngestService
from app.ai.tools import ToolRegistry
from app.ai.workflows import WorkflowRegistry
from app.ai.workflows.urlguard import Resolver, system_resolver
from app.application.ports.documents import Chunker, DocumentParser
from app.application.ports.embeddings import EmbeddingProvider
from app.application.ports.health import HealthCheck
from app.application.ports.memory_extraction import MemoryExtractor
from app.application.ports.storage import StorageProvider
from app.application.ports.workflows import WorkflowClient
from app.application.use_cases.api_keys import Principal, authenticate_api_key
from app.infrastructure.config import Settings
from app.infrastructure.db import Database
from app.infrastructure.db.models import User
from app.infrastructure.db.repositories import SystemRepository, UserRepository
from app.infrastructure.security import (
    DEFAULT_SCOPES,
    KEY_PREFIX,
    ExpiredTokenError,
    InvalidTokenError,
    TokenPayload,
    decode_access_token,
)
from app.shared.exceptions.auth import AuthenticationError

_bearer = HTTPBearer(auto_error=False)


def get_app_database(request: Request) -> Database:
    """Runtime DB (neo_app, RLS-enforced)."""
    return request.app.state.database  # type: ignore[no-any-return]


def get_system_database(request: Request) -> Database:
    """Privileged DB (neo). Only used by the SystemRepository code path."""
    return request.app.state.system_database  # type: ignore[no-any-return]


# Back-compat alias for pre-2c-2 imports.
get_database = get_app_database


def get_redis(request: Request) -> Redis:
    return request.app.state.redis  # type: ignore[no-any-return]


def get_embedding_provider(request: Request) -> EmbeddingProvider:
    """Built once in the lifespan; consumed by 5b/5c. No route uses it yet."""
    return request.app.state.embedding_provider  # type: ignore[no-any-return]


def get_memory_extractor(request: Request) -> MemoryExtractor:
    """Built once in the lifespan; consumed by /chat + /chat/stream for the
    best-effort memory write path (5c). Never fails the request when it
    misbehaves — see chat.py::_extract_and_store_memories.
    """
    return request.app.state.memory_extractor  # type: ignore[no-any-return]


def get_tool_registry(request: Request) -> ToolRegistry:
    """Built once in the lifespan. NO route consumes this yet — 6b wires it
    into the chat path. Present here so 6b is a pure route-level change.
    """
    return request.app.state.tool_registry  # type: ignore[no-any-return]


def get_agent_registry(request: Request) -> AgentRegistry:
    """Built once in the lifespan. NO route consumes this yet — 6f is the
    contract-and-registry slice; 6g wires it into the chat path. Present
    here so 6g is a pure route-level change (same shape as get_tool_registry).
    """
    return request.app.state.agent_registry  # type: ignore[no-any-return]


def get_workflow_client(request: Request) -> WorkflowClient:
    """Built once in the lifespan. NO route consumes this yet — 7a is the
    contract/registry/mock slice; 7b wires workflows into the tool loop
    (WORKFLOWS ARE TOOLS). Present here so 7b is a pure route-level change
    (same shape as get_tool_registry / get_agent_registry).
    """
    return request.app.state.workflow_client  # type: ignore[no-any-return]


def get_workflow_registry(request: Request) -> WorkflowRegistry:
    """Built once in the lifespan. NO route consumes this yet — 7b wires it
    into the chat path. Present here so 7b is a pure route-level change.
    """
    return request.app.state.workflow_registry  # type: ignore[no-any-return]


def get_workflow_url_resolver(request: Request) -> Resolver:
    """7f-2: DNS resolver used to validate tenant workflow URLs at read time.
    Injectable via app.state so tests stay OFFLINE; defaults to the real
    getaddrinfo-backed resolver in production.
    """
    resolver: Resolver = getattr(request.app.state, "workflow_url_resolver", system_resolver)
    return resolver


def get_document_parser(request: Request) -> DocumentParser:
    """Built once in the lifespan. NO route consumes this yet — 8a is the
    contracts/mock slice; 8c wires document ingest. Present here so 8c is a
    pure route-level change (same shape as get_workflow_client).
    """
    return request.app.state.document_parser  # type: ignore[no-any-return]


def get_chunker(request: Request) -> Chunker:
    """Built once in the lifespan. Consumed indirectly via the ingest service."""
    return request.app.state.chunker  # type: ignore[no-any-return]


def get_document_ingest(request: Request) -> DocumentIngestService:
    """The 8b ingest pipeline, built once in the lifespan. Consumed by 8c's
    upload route. Its constructor already ran the token-cap guard at startup.
    """
    return request.app.state.document_ingest  # type: ignore[no-any-return]


def get_storage(request: Request) -> StorageProvider:
    """The original-file store (ADR 0002), built once in the lifespan. Consumed by
    the upload route to persist original bytes before ingest."""
    return request.app.state.storage  # type: ignore[no-any-return]


def get_app_settings(request: Request) -> Settings:
    """Read the Settings instance built in create_app / lifespan.

    Named `get_app_settings` (not `get_settings`) to avoid colliding with the
    module-level cached factory in infrastructure.config.
    """
    return request.app.state.settings  # type: ignore[no-any-return]


def get_health_checks(request: Request) -> list[HealthCheck]:
    return request.app.state.health_checks  # type: ignore[no-any-return]


async def get_app_session(
    db: Annotated[Database, Depends(get_app_database)],
) -> AsyncIterator[AsyncSession]:
    """neo_app session, transaction-wrapped, no tenant GUC set."""
    async with db.sessionmaker() as session, session.begin():
        yield session


async def get_system_session(
    db: Annotated[Database, Depends(get_system_database)],
) -> AsyncIterator[AsyncSession]:
    """neo session, transaction-wrapped. RLS bypassed at the role level."""
    async with db.sessionmaker() as session, session.begin():
        yield session


AppSessionDep = Annotated[AsyncSession, Depends(get_app_session)]
SystemSessionDep = Annotated[AsyncSession, Depends(get_system_session)]
# Back-compat alias for the 2c-1 session dep name.
SessionDep = AppSessionDep

RedisDep = Annotated[Redis, Depends(get_redis)]
HealthChecksDep = Annotated[list[HealthCheck], Depends(get_health_checks)]
EmbeddingProviderDep = Annotated[EmbeddingProvider, Depends(get_embedding_provider)]
MemoryExtractorDep = Annotated[MemoryExtractor, Depends(get_memory_extractor)]
ToolRegistryDep = Annotated[ToolRegistry, Depends(get_tool_registry)]
AgentRegistryDep = Annotated[AgentRegistry, Depends(get_agent_registry)]
WorkflowClientDep = Annotated[WorkflowClient, Depends(get_workflow_client)]
WorkflowRegistryDep = Annotated[WorkflowRegistry, Depends(get_workflow_registry)]
WorkflowUrlResolverDep = Annotated[Resolver, Depends(get_workflow_url_resolver)]
DocumentParserDep = Annotated[DocumentParser, Depends(get_document_parser)]
ChunkerDep = Annotated[Chunker, Depends(get_chunker)]
DocumentIngestDep = Annotated[DocumentIngestService, Depends(get_document_ingest)]
StorageDep = Annotated[StorageProvider, Depends(get_storage)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]


def get_access_payload(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> TokenPayload:
    if creds is None or creds.scheme.lower() != "bearer":
        raise AuthenticationError("missing bearer token")
    try:
        return decode_access_token(creds.credentials)
    except (InvalidTokenError, ExpiredTokenError) as e:
        raise AuthenticationError("invalid or expired token") from e


AccessPayloadDep = Annotated[TokenPayload, Depends(get_access_payload)]


# Sentinel tenant for "no active org". Set explicitly (rather than leaving the
# GUC unset) so `current_setting('app.current_tenant', true)::uuid` never sees
# the post-commit placeholder reset value '' — which ERRORS on the ::uuid cast
# rather than returning zero rows (the 8b landmine). gen_random_uuid() never
# produces all-zeros, so nil matches no organization → RLS returns 0 rows.
NIL_TENANT = "00000000-0000-0000-0000-000000000000"


async def set_tenant_guc(session: AsyncSession, tenant_id: UUID | str | None) -> None:
    """ALWAYS set `app.current_tenant` (transaction-local, SET LOCAL semantics).

    Never leave it unset: a pooled connection whose placeholder GUC has reset to
    '' would make every RLS predicate 500 on the ::uuid cast. When there's no
    tenant we set the nil sentinel, which safely matches nothing. set_config(...,
    true) is the transaction-local form and accepts bind params (`SET` does not).
    """
    value = str(tenant_id) if tenant_id is not None else NIL_TENANT
    await session.execute(
        text("SELECT set_config('app.current_tenant', :t, true)").bindparams(t=value)
    )


async def get_tenant_session(
    db: Annotated[Database, Depends(get_app_database)],
    payload: AccessPayloadDep,
) -> AsyncIterator[AsyncSession]:
    """neo_app session with `app.current_tenant` GUC set (SET LOCAL semantics).

    The GUC is ALWAYS set via set_tenant_guc — to the caller's tenant, or the nil
    sentinel when the token has no tenant_id. A no-tenant caller then sees 0 rows
    on tenant tables (safe default) WITHOUT risking the '' ::uuid-cast 500 that a
    recycled pooled connection would otherwise trigger.
    """
    async with db.sessionmaker() as session, session.begin():
        await set_tenant_guc(session, payload.tenant_id)
        yield session


TenantSessionDep = Annotated[AsyncSession, Depends(get_tenant_session)]


async def get_current_user(
    payload: AccessPayloadDep,
    session: AppSessionDep,
) -> User:
    user = await UserRepository(session).get_by_id(UUID(payload.sub))
    if user is None or not user.is_active:
        raise AuthenticationError("user not found or inactive")
    return user


async def get_current_user_scoped(
    payload: AccessPayloadDep,
    db: Annotated[Database, Depends(get_app_database)],
) -> User:
    """Streaming-safe variant: opens/closes a session inside this function so
    NO pooled DB connection is held for the response duration. Use in endpoints
    that return StreamingResponse; the regular `get_current_user` keeps the
    session open across the response body via generator-dep teardown.
    """
    async with db.sessionmaker() as session:
        user = await UserRepository(session).get_by_id(UUID(payload.sub))
        if user is None or not user.is_active:
            raise AuthenticationError("user not found or inactive")
        return user


def get_current_tenant(payload: AccessPayloadDep) -> UUID | None:
    return UUID(payload.tenant_id) if payload.tenant_id is not None else None


CurrentUserDep = Annotated[User, Depends(get_current_user)]
StreamingCurrentUserDep = Annotated[User, Depends(get_current_user_scoped)]
CurrentTenantDep = Annotated[UUID | None, Depends(get_current_tenant)]


# --- service-key auth (Slice 1: read-only, tenant-locked) --------------------


def _extract_api_key(request: Request) -> str | None:
    """Read a service key from `X-API-Key`, or from `Authorization: Bearer` ONLY
    when the token carries the neo_sk_ prefix — so a user JWT on the same header
    is never mistaken for a service key.
    """
    x = request.headers.get("x-api-key")
    if x:
        return x
    auth = request.headers.get("authorization")
    if auth and auth[:7].lower() == "bearer ":
        token = auth[7:].strip()
        if token.startswith(KEY_PREFIX):
            return token
    return None


async def get_service_principal(
    request: Request,
    system_session: SystemSessionDep,
) -> Principal:
    """Validate a service key and yield its Principal. The lookup is cross-tenant
    (privileged `neo` session) — the tenant lives inside the matched key row —
    exactly like login resolves a user by email before any tenant is known.
    Enforces the `read` scope; touches last_used_at on success.
    """
    raw = _extract_api_key(request)
    if raw is None:
        raise AuthenticationError("missing api key")
    return await authenticate_api_key(
        raw, system=SystemRepository(system_session), required_scope="read"
    )


ServicePrincipalDep = Annotated[Principal, Depends(get_service_principal)]


async def get_service_session(
    principal: ServicePrincipalDep,
    db: Annotated[Database, Depends(get_app_database)],
) -> AsyncIterator[AsyncSession]:
    """neo_app session with `app.current_tenant` set from the SERVICE key's org —
    RLS engages identically to the user-JWT TenantSessionDep path."""
    async with db.sessionmaker() as session, session.begin():
        await set_tenant_guc(session, principal.organization_id)
        yield session


ServiceSessionDep = Annotated[AsyncSession, Depends(get_service_session)]


async def get_principal(
    request: Request,
    system_session: SystemSessionDep,
    db: Annotated[Database, Depends(get_app_database)],
) -> Principal:
    """Combined principal — a valid service key OR a valid user JWT. Endpoints
    protected by this accept either (Slice 4). Service keys win when present
    (neo_sk_ prefix); otherwise falls back to the JWT path.
    """
    raw = _extract_api_key(request)
    if raw is not None:
        return await authenticate_api_key(
            raw, system=SystemRepository(system_session), required_scope="read"
        )
    auth = request.headers.get("authorization")
    if not (auth and auth[:7].lower() == "bearer "):
        raise AuthenticationError("missing bearer token or api key")
    try:
        payload = decode_access_token(auth[7:].strip())
    except (InvalidTokenError, ExpiredTokenError) as e:
        raise AuthenticationError("invalid or expired token") from e
    async with db.sessionmaker() as session:
        user = await UserRepository(session).get_by_id(UUID(payload.sub))
    if user is None or not user.is_active:
        raise AuthenticationError("user not found or inactive")
    org_id = UUID(payload.tenant_id) if payload.tenant_id is not None else None
    # ponytail: user gets the read scope this slice enforces; broaden via RBAC
    # (apikey:* perms are already seeded) when write scopes land.
    return Principal(
        kind="user",
        organization_id=org_id,
        scopes=list(DEFAULT_SCOPES),
        user_id=user.id,
    )


PrincipalDep = Annotated[Principal, Depends(get_principal)]


async def get_principal_session(
    principal: PrincipalDep,
    db: Annotated[Database, Depends(get_app_database)],
) -> AsyncIterator[AsyncSession]:
    """neo_app session with the GUC set from EITHER principal kind — the shared
    RLS-scoped session for combined-auth endpoints."""
    async with db.sessionmaker() as session, session.begin():
        await set_tenant_guc(session, principal.organization_id)
        yield session


PrincipalSessionDep = Annotated[AsyncSession, Depends(get_principal_session)]
