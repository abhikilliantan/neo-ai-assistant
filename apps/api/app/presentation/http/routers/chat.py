"""Chat endpoints — non-streaming (/chat) + streaming (/chat/stream).

BOTH variants use the SAME short-bookending discipline (6k-2 aligned /chat to
what 4b built for the stream): a short tenant write-txn BEFORE the provider
call (Txn A — resolve/create conversation + persist the user message), memory
retrieval in its own short session, the provider call holding NO connection,
then a short txn AFTER (Txn B — persist the assistant message + touch). No DB
session is ever held across the multi-second provider round trip, so a pool
connection is never pinned for it. The 5c memory write runs OFF the response
path as a FastAPI BackgroundTask on both endpoints.

Provider-failure semantics (LOCKED, both paths): Txn A commits the user
message before the provider call, so on a provider failure the user turn
PERSISTS and the assistant turn does not — the user can see their message in
history and retry without retyping. On /chat/stream, if the client
disconnects mid-stream the "after" txn simply doesn't run — same outcome.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from app.ai.agents import DEFAULT_AGENT_NAME, AgentRunner, agent_for_request
from app.ai.tools import build_streaming_request_tool_registry
from app.ai.tools.search_documents import DocumentRepoFactory
from app.ai.tools.search_memory import MemoryRepoFactory
from app.ai.workflows.registry import WorkflowRegistry
from app.ai.workflows.tenant import resolve_request_workflows
from app.ai.workflows.urlguard import Resolver
from app.application.ports.agents import AgentDefinition
from app.application.ports.chat import ChatMessage, ChatProvider, ToolExecutor
from app.application.ports.embeddings import EmbeddingProvider
from app.application.ports.memory_extraction import MemoryExtractor
from app.application.ports.repositories import DocumentRepositoryPort, MemoryRepositoryPort
from app.application.ports.workflows import WorkflowClient
from app.infrastructure.db import Database
from app.infrastructure.db.repositories import (
    ConversationRepository,
    DocumentRepository,
    MemoryRepository,
    MessageRepository,
)
from app.infrastructure.logging import get_logger
from app.presentation.http.deps import (
    AgentRegistryDep,
    CurrentTenantDep,
    EmbeddingProviderDep,
    MemoryExtractorDep,
    SettingsDep,
    StreamingCurrentUserDep,
    WorkflowClientDep,
    WorkflowRegistryDep,
    WorkflowUrlResolverDep,
    get_app_database,
    get_embedding_provider,
    get_memory_extractor,
    set_tenant_guc,
)
from app.presentation.http.schemas.chat import ChatRequest, ChatResponse
from app.shared.exceptions.ai import (
    ProviderAPIError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)
from app.shared.exceptions.auth import AuthenticationError
from app.shared.exceptions.common import NotFoundError

router = APIRouter(prefix="/api/v1", tags=["chat"])


def get_chat_provider(request: Request) -> ChatProvider:
    return request.app.state.chat_provider  # type: ignore[no-any-return]


ProviderDep = Annotated[ChatProvider, Depends(get_chat_provider)]

_TITLE_LIMIT = 60


def _title_from(text: str) -> str:
    collapsed = " ".join(text.split())
    if not collapsed:
        return "New conversation"
    return collapsed[:_TITLE_LIMIT]


def _usage_tokens(usage: object) -> tuple[int | None, int | None]:
    """Split ChatUsage into (prompt_tokens, completion_tokens); (None, None) if absent."""
    if usage is None:
        return (None, None)
    return (
        getattr(usage, "prompt_tokens", None),
        getattr(usage, "completion_tokens", None),
    )


_MEMORY_CONTEXT_PREAMBLE = (
    "The following facts were retrieved from this user's saved memories. Treat them as the "
    "source of truth about the user; use them where relevant, and do not invent details "
    "beyond what they state:"
)


async def _retrieve_memory_context(
    db: Database,
    embedding_provider: EmbeddingProvider,
    *,
    tenant_id: UUID,
    user_id: UUID,
    query_text: str,
    top_k: int,
    min_similarity: float,
) -> str | None:
    """Best-effort semantic retrieval of this user's prior memories.

    Returns a formatted system-message string, or None if nothing above the
    similarity floor. ANY failure (embed/DB) is swallowed with a log line
    and returns None — a retrieval failure MUST NOT break chat.

    Uses input_type="query" for the embedding call (locked; retrieval side
    of the write path's "document"). Search is org+user scoped by the repo
    AND filtered again by RLS at the DB layer.
    """
    log = get_logger("memory.retrieval")
    try:
        result = await embedding_provider.embed(texts=[query_text], input_type="query")
        query_vec = result.vectors[0]
        async with db.sessionmaker() as session, session.begin():
            await session.execute(
                text("SELECT set_config('app.current_tenant', :t, true)").bindparams(
                    t=str(tenant_id)
                )
            )
            hits = await MemoryRepository(session).search_similar(
                organization_id=tenant_id,
                user_id=user_id,
                query_embedding=query_vec,
                limit=top_k,
                # 6k-1: only compare within one vector space. Rows embedded
                # with a different model live in an incompatible space, and
                # their cosine distances against a query from THIS model are
                # noise that drowns out real matches (the 5d demo bug).
                # search_memory (6c) already applies this guard; retrieval
                # was the last hole.
                embedding_model=result.model,
            )
        kept = [(m, sim) for m, sim in hits if sim >= min_similarity]
        log.info(
            "memory.retrieval",
            candidates=len(hits),
            injected=len(kept),
            user_id=str(user_id),
        )
        if not kept:
            return None
        lines = [f"- {m.content}" for m, _sim in kept]
        return _MEMORY_CONTEXT_PREAMBLE + "\n" + "\n".join(lines)
    except Exception as e:
        log.warning(
            "memory.retrieval.failed",
            error=str(e),
            error_type=type(e).__name__,
            user_id=str(user_id),
        )
        return None


def _augment_messages(base: list[ChatMessage], memory_context: str | None) -> list[ChatMessage]:
    """Prepend a system message carrying `memory_context` (or return `base`).

    Returns a NEW list — never mutates `base`, so downstream code that reads
    `body.messages` (persistence, 5c memory write) is untouched.
    """
    if memory_context is None:
        return base
    return [ChatMessage(role="system", content=memory_context), *base]


async def _extract_and_store_memories(
    db: Database,
    embedding_provider: EmbeddingProvider,
    extractor: MemoryExtractor,
    *,
    tenant_id: UUID,
    user_id: UUID,
    messages: list[ChatMessage],
    assistant_reply: str,
) -> None:
    """Best-effort: extract durable facts from a completed chat turn, embed
    them, and persist as memories. ANY failure (extractor/embed/DB) is
    swallowed with a log line — a memory failure MUST NOT break chat.

    Uses input_type="document" for the embedding call. Retrieval (5d) will
    embed the query with input_type="query".

    6k-2: runs as a FastAPI BackgroundTask on BOTH endpoints — off the
    response path, so the user never waits on extract+embed. Opens its OWN
    short tenant session (below) because the request-scoped sessions are all
    closed by the time this runs.
    """
    log = get_logger("memory.write")
    try:
        facts = await extractor.extract(messages=messages, assistant_reply=assistant_reply)
        if not facts:
            return
        result = await embedding_provider.embed(
            texts=[f.content for f in facts],
            input_type="document",
        )
        async with db.sessionmaker() as session, session.begin():
            await session.execute(
                text("SELECT set_config('app.current_tenant', :t, true)").bindparams(
                    t=str(tenant_id)
                )
            )
            repo = MemoryRepository(session)
            for fact, vector in zip(facts, result.vectors, strict=True):
                await repo.add(
                    organization_id=tenant_id,
                    user_id=user_id,
                    content=fact.content,
                    embedding=vector,
                    embedding_model=result.model,
                    kind=fact.kind,
                    source="chat",
                )
        log.info("memory.write.success", count=len(facts), user_id=str(user_id))
    except Exception as e:
        log.warning(
            "memory.write.failed",
            error=str(e),
            error_type=type(e).__name__,
            user_id=str(user_id),
        )


async def _resolve_workflows_for_request(
    *,
    db: Database,
    tenant_id: UUID,
    settings: Any,
    builtin_registry: WorkflowRegistry,
    workflow_client: WorkflowClient,
    resolver: Resolver,
    agent: AgentDefinition,
) -> tuple[WorkflowRegistry, WorkflowClient, AgentDefinition]:
    """7f-2: resolve this tenant's workflow set (built-ins + enabled rows,
    fail-closed + bad-row-skipping), rebind the client to the tenant URLs, and
    expand the operator agent's per-request permissions. Returns the trio the
    tool builder + AgentRunner consume. Shared by both endpoints so they can't
    drift.
    """
    req_registry, url_overrides = await resolve_request_workflows(
        db=db,
        tenant_id=tenant_id,
        builtin_registry=builtin_registry,
        settings=settings,
        resolve=resolver,
    )
    # Rebind so tenant workflows POST to their row URL. No-op for MockWorkflow
    # Client (it ignores URLs) — hence duck-typed, not isinstance.
    with_overrides = getattr(workflow_client, "with_url_overrides", None)
    req_client: WorkflowClient = (
        with_overrides(url_overrides) if with_overrides is not None else workflow_client
    )
    req_agent = agent_for_request(
        agent,
        builtin_workflow_names=frozenset(builtin_registry.list_names()),
        request_workflow_names=frozenset(req_registry.list_names()),
    )
    return req_registry, req_client, req_agent


# --- non-streaming ----------------------------------------------------------


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    user: StreamingCurrentUserDep,  # scoped session — no DB connection held
    tenant_id: CurrentTenantDep,
    provider: ProviderDep,
    embedding_provider: EmbeddingProviderDep,
    memory_extractor: MemoryExtractorDep,
    settings: SettingsDep,
    agents: AgentRegistryDep,
    workflow_registry: WorkflowRegistryDep,
    workflow_client: WorkflowClientDep,
    workflow_url_resolver: WorkflowUrlResolverDep,
    background_tasks: BackgroundTasks,
    db: Annotated[Database, Depends(get_app_database)],
) -> ChatResponse:
    if tenant_id is None:
        raise AuthenticationError("user has no active tenant")

    # Phase 1 (6j): early-validate `body.agent` BEFORE any side effect. This
    # keeps the 6h no-orphan-row guarantee: an unknown name 404s before we
    # create a conversation or persist the user message. Body.agent = None is
    # legal here — the stored value (or the default) supplies the name below.
    if body.agent is not None and agents.get(body.agent) is None:
        raise NotFoundError(f"agent not found: {body.agent!r}")

    # --- Txn A: BEFORE the provider call -----------------------------------
    # 6k-2: same short-bookending discipline as /chat/stream — resolve/create
    # the conversation + persist the user message in a short txn, then release
    # the connection. Because this commits before the provider call, a provider
    # failure below leaves the user message PERSISTED (matches the stream path);
    # pre-6k-2 the single request session rolled everything back on failure.
    conv_id, stored_agent = await _persist_user_and_resolve_conversation(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        conversation_id=body.conversation_id,
        user_message=body.messages[-1].content,
        body_agent=body.agent,
    )

    # Phase 2 (6j): body.agent wins → stored → default. Defensive fallback
    # if a stored name no longer exists in the registry (agent removed in a
    # deploy) — don't lock a user out of their own thread.
    if body.agent is not None:
        agent_name = body.agent
    elif stored_agent is not None:
        agent_name = stored_agent
    else:
        agent_name = DEFAULT_AGENT_NAME
    agent = agents.get(agent_name)
    if agent is None:
        # 6k-1: stored agent name is not in the current registry (e.g. the
        # agent was renamed or removed in a code deploy since the row was
        # written). We fall back to the default so the user isn't locked
        # out of their own thread, but an operator needs to know — the
        # stored data still references a ghost.
        get_logger("chat.agent.fallback").warning(
            "chat.agent.fallback",
            missing=agent_name,
            fallback=DEFAULT_AGENT_NAME,
            user_id=str(user.id),
        )
        agent_name = DEFAULT_AGENT_NAME
        agent = agents.get(DEFAULT_AGENT_NAME)
    assert agent is not None, f"built-in default {DEFAULT_AGENT_NAME!r} missing from registry"

    get_logger("chat.turn").info("chat.turn", agent=agent_name, user_id=str(user.id))

    # Retrieve prior memories BEFORE the provider call, in its OWN short
    # session (released before the provider call). The 5c write for THIS turn
    # runs AFTER the response as a background task, so the just-being-extracted
    # fact cannot leak into this turn's context.
    memory_context: str | None = None
    if settings.memory_retrieval_enabled:
        memory_context = await _retrieve_memory_context(
            db,
            embedding_provider,
            tenant_id=tenant_id,
            user_id=user.id,
            query_text=body.messages[-1].content,
            top_k=settings.memory_retrieval_top_k,
            min_similarity=settings.memory_retrieval_min_similarity,
        )
    augmented = _augment_messages(body.messages, memory_context)

    # 7f-2: resolve tenant workflows (built-ins + this tenant's enabled rows),
    # rebind the client to their URLs, and expand operator's per-request perms.
    req_workflow_registry, req_workflow_client, agent = await _resolve_workflows_for_request(
        db=db,
        tenant_id=tenant_id,
        settings=settings,
        builtin_registry=workflow_registry,
        workflow_client=workflow_client,
        resolver=workflow_url_resolver,
        agent=agent,
    )

    # Tools: 6k-2 — bind search_memory to the SHORT-per-call session factory
    # (same as /chat/stream) rather than a held request session, so NO DB
    # connection is pinned across the provider call. 7b/7f-2 — built-in AND
    # tenant workflows join the tool set here, gated by workflows_enabled inside
    # the builder. The tool-use loop itself lives INSIDE the provider and is
    # untouched; intermediate tool_use/tool_result turns stay ephemeral (only
    # completion.content persists).
    tools: list[dict[str, Any]] | None = None
    tool_executor: ToolExecutor | None = None
    if settings.tools_enabled:
        request_registry = build_streaming_request_tool_registry(
            settings=settings,
            memory_repo_factory=_make_streaming_memory_repo_factory(db, tenant_id=tenant_id),
            document_repo_factory=_make_streaming_document_repo_factory(db, tenant_id=tenant_id),
            embedding_provider=embedding_provider,
            organization_id=tenant_id,
            user_id=user.id,
            workflow_registry=req_workflow_registry,
            workflow_client=req_workflow_client,
        )
        specs = request_registry.specs()
        if specs:
            tools = specs
            tool_executor = request_registry.execute

    # Apply the (already-resolved) agent's persona + tool filter to the
    # provider-call inputs. Default "assistant" is identity on both — pre-6h
    # byte-compat. See AgentRunner for the transparency argument.
    runner = AgentRunner(
        agent,
        workflow_names=frozenset(req_workflow_registry.list_names()),
        # 7d: actor recorded EXPLICITLY on every workflow audit line.
        user_id=str(user.id),
        org_id=str(tenant_id),
    )
    augmented = runner.prepare_messages(augmented)
    if tools is not None and tool_executor is not None:
        tools, tool_executor = runner.filter_tools(tools, tool_executor)

    # Provider call holding NO DB connection.
    completion = await provider.complete(
        messages=augmented,
        tools=tools,
        tool_executor=tool_executor,
    )

    # --- Txn B: AFTER the provider call ------------------------------------
    # Fresh short session, persist the assistant message + touch.
    await _persist_assistant_and_touch(
        db,
        tenant_id=tenant_id,
        conversation_id=conv_id,
        content=completion.content,
        model=completion.model,
        usage=completion.usage,
        finish_reason=completion.finish_reason,
    )

    # 5c memory write — OFF the response path (6k-2). Scheduled as a background
    # task so the user never waits on extract+embed. It opens its OWN short
    # tenant session and stays best-effort (never raises — see the function).
    background_tasks.add_task(
        _extract_and_store_memories,
        db,
        embedding_provider,
        memory_extractor,
        tenant_id=tenant_id,
        user_id=user.id,
        messages=body.messages,
        assistant_reply=completion.content,
    )

    return ChatResponse(
        conversation_id=conv_id,
        message=ChatMessage(role="assistant", content=completion.content),
        model=completion.model,
        usage=completion.usage,
        tool_invocations=completion.tool_invocations,
        agent=agent_name,
    )


def _make_streaming_memory_repo_factory(db: Database, *, tenant_id: UUID) -> MemoryRepoFactory:
    """Factory that opens a SHORT-lived tenant session per tool call.

    The streaming path deliberately avoids holding a pooled DB connection for
    the multi-second LLM response. This factory therefore opens a fresh
    session, sets `app.current_tenant` inside the transaction, yields a
    MemoryRepository, and closes on exit — one session PER search_memory
    call, mirroring the 5d retrieval session's discipline. No session is
    ever bound across the stream.
    """

    @asynccontextmanager
    async def _factory() -> AsyncIterator[MemoryRepositoryPort]:
        async with db.sessionmaker() as session, session.begin():
            await session.execute(
                text("SELECT set_config('app.current_tenant', :t, true)").bindparams(
                    t=str(tenant_id)
                )
            )
            yield MemoryRepository(session)

    return _factory


def _make_streaming_document_repo_factory(db: Database, *, tenant_id: UUID) -> DocumentRepoFactory:
    """Document twin of `_make_streaming_memory_repo_factory`: opens a SHORT-lived
    tenant session per search_documents call (set GUC → search → close), so no DB
    connection is pinned across the LLM stream. Uses the 8c `set_tenant_guc`
    helper so the nil-sentinel/'' landmine is handled in one place.
    """

    @asynccontextmanager
    async def _factory() -> AsyncIterator[DocumentRepositoryPort]:
        async with db.sessionmaker() as session, session.begin():
            await set_tenant_guc(session, tenant_id)
            yield DocumentRepository(session)

    return _factory


# --- streaming --------------------------------------------------------------

_PROVIDER_ERROR_CODES: dict[type[Exception], str] = {
    ProviderAuthError: "provider_auth_error",
    ProviderRateLimitError: "provider_rate_limited",
    ProviderUnavailableError: "provider_unavailable",
    ProviderAPIError: "provider_error",
}
_PROVIDER_ERROR_TYPES = tuple(_PROVIDER_ERROR_CODES)


def _sse_frame(payload: dict[str, object]) -> bytes:
    return f"data: {json.dumps(payload, separators=(',', ':'))}\n\n".encode()


async def _persist_user_and_resolve_conversation(
    db: Database,
    *,
    tenant_id: UUID,
    user_id: UUID,
    conversation_id: UUID | None,
    user_message: str,
    body_agent: str | None,
) -> tuple[UUID, str | None]:
    """Short tenant write-txn: resolve-or-create conversation + persist the
    user message + write per-thread agent (6j). Returns (conv_id, stored
    agent_name) — the caller layers the DEFAULT_AGENT_NAME fallback on
    `stored is None`. Session opens and closes here — nothing is held for
    the caller.
    """
    async with db.sessionmaker() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant', :t, true)").bindparams(t=str(tenant_id))
        )
        conv_repo = ConversationRepository(session)
        msg_repo = MessageRepository(session)

        stored_agent: str | None
        if conversation_id is not None:
            conv = await conv_repo.get_by_id(conversation_id)
            if conv is None:
                raise NotFoundError("conversation not found")
            # 6j: continuation with an explicit picker choice that differs
            # from the stored value → update, so the thread tracks the
            # user's latest visible choice.
            if body_agent is not None and conv.agent_name != body_agent:
                await conv_repo.set_agent(conv.id, body_agent)
                stored_agent = body_agent
            else:
                stored_agent = conv.agent_name
        else:
            conv = await conv_repo.create(
                organization_id=tenant_id,
                user_id=user_id,
                title=_title_from(user_message),
                # NULL when the caller didn't pick — resolves to the
                # runtime default at read time.
                agent_name=body_agent,
            )
            stored_agent = body_agent
        await msg_repo.add(
            organization_id=tenant_id,
            conversation_id=conv.id,
            role="user",
            content=user_message,
        )
        return conv.id, stored_agent


async def _persist_assistant_and_touch(
    db: Database,
    *,
    tenant_id: UUID,
    conversation_id: UUID,
    content: str,
    model: str | None,
    usage: object,
    finish_reason: str | None,
) -> None:
    """Short tenant write-txn to persist the assistant message + touch the
    conversation's last_message_at. Opens + closes its own session.
    """
    prompt_tokens, completion_tokens = _usage_tokens(usage)
    async with db.sessionmaker() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant', :t, true)").bindparams(t=str(tenant_id))
        )
        await MessageRepository(session).add(
            organization_id=tenant_id,
            conversation_id=conversation_id,
            role="assistant",
            content=content,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            finish_reason=finish_reason,
        )
        await ConversationRepository(session).touch(conversation_id)


@router.post("/chat/stream")
async def chat_stream(
    body: ChatRequest,
    user: StreamingCurrentUserDep,  # scoped session — no held DB connection
    tenant_id: CurrentTenantDep,  # from token; no DB call
    provider: ProviderDep,
    db: Annotated[Database, Depends(get_app_database)],
    embedding_provider: Annotated[EmbeddingProvider, Depends(get_embedding_provider)],
    memory_extractor: Annotated[MemoryExtractor, Depends(get_memory_extractor)],
    settings: SettingsDep,
    agents: AgentRegistryDep,
    workflow_registry: WorkflowRegistryDep,
    workflow_client: WorkflowClientDep,
    workflow_url_resolver: WorkflowUrlResolverDep,
    background_tasks: BackgroundTasks,
) -> StreamingResponse:
    if tenant_id is None:
        raise AuthenticationError("user has no active tenant")

    # Phase 1 (6j): early-validate body.agent BEFORE Txn A. Unknown → 404
    # bubbles to the exception handler → clean JSON envelope, NO orphan
    # user-message row, NO SSE frames — same discipline as 4b's
    # conversation-not-found 404 raised before StreamingResponse.
    if body.agent is not None and agents.get(body.agent) is None:
        raise NotFoundError(f"agent not found: {body.agent!r}")

    # --- Txn A: BEFORE the stream ------------------------------------------
    # Resolve/create conversation + persist the user message + write per-
    # thread agent in a short txn, then release the connection.
    conv_id, stored_agent = await _persist_user_and_resolve_conversation(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        conversation_id=body.conversation_id,
        user_message=body.messages[-1].content,
        body_agent=body.agent,
    )

    # Phase 2 (6j): body.agent wins → stored → default. Defensive fallback
    # if stored name is no longer registered. body.agent was validated in
    # phase 1, so it never falls through this branch.
    if body.agent is not None:
        agent_name = body.agent
    elif stored_agent is not None:
        agent_name = stored_agent
    else:
        agent_name = DEFAULT_AGENT_NAME
    agent = agents.get(agent_name)
    if agent is None:
        # 6k-1: stored agent name absent from the current registry — same
        # ghost case as /chat above, same fallback + warn shape.
        get_logger("chat.agent.fallback").warning(
            "chat.agent.fallback",
            missing=agent_name,
            fallback=DEFAULT_AGENT_NAME,
            user_id=str(user.id),
        )
        agent_name = DEFAULT_AGENT_NAME
        agent = agents.get(DEFAULT_AGENT_NAME)
    assert agent is not None, f"built-in default {DEFAULT_AGENT_NAME!r} missing from registry"
    get_logger("chat.turn").info("chat.turn", agent=agent_name, user_id=str(user.id))

    # Memory retrieval — its OWN short session, closed BEFORE we return
    # StreamingResponse. Never held across the LLM stream.
    memory_context: str | None = None
    if settings.memory_retrieval_enabled:
        memory_context = await _retrieve_memory_context(
            db,
            embedding_provider,
            tenant_id=tenant_id,
            user_id=user.id,
            query_text=body.messages[-1].content,
            top_k=settings.memory_retrieval_top_k,
            min_similarity=settings.memory_retrieval_min_similarity,
        )
    augmented = _augment_messages(body.messages, memory_context)

    # 7f-2: resolve tenant workflows + rebind client + expand operator perms.
    # Runs BEFORE the StreamingResponse is returned, so its short DB read holds
    # no connection across the stream.
    req_workflow_registry, req_workflow_client, agent = await _resolve_workflows_for_request(
        db=db,
        tenant_id=tenant_id,
        settings=settings,
        builtin_registry=workflow_registry,
        workflow_client=workflow_client,
        resolver=workflow_url_resolver,
        agent=agent,
    )

    # Tools: build a per-request STREAMING registry. search_memory binds to a
    # SHORT-per-call session factory (never holds a session across the LLM
    # stream). Retrieval/persist txns above/below remain the sole DB sessions
    # bookending this request; tool-driven DB access is entirely per-call.
    # The stream path DOES run the tool loop (wired in 6d) — tools_enabled=false
    # → provider gets tools=None on BOTH paths. 7b/7f-2: built-in AND tenant
    # workflows join the tool set here, gated by workflows_enabled in the builder.
    tools: list[dict[str, Any]] | None = None
    tool_executor: ToolExecutor | None = None
    if settings.tools_enabled:
        streaming_registry = build_streaming_request_tool_registry(
            settings=settings,
            memory_repo_factory=_make_streaming_memory_repo_factory(db, tenant_id=tenant_id),
            document_repo_factory=_make_streaming_document_repo_factory(db, tenant_id=tenant_id),
            embedding_provider=embedding_provider,
            organization_id=tenant_id,
            user_id=user.id,
            workflow_registry=req_workflow_registry,
            workflow_client=req_workflow_client,
        )
        specs = streaming_registry.specs()
        if specs:
            tools = specs
            tool_executor = streaming_registry.execute

    # Apply the (already-resolved) agent's persona + tool filter. Default
    # "assistant" is identity on both — pre-6h byte-compat.
    runner = AgentRunner(
        agent,
        workflow_names=frozenset(req_workflow_registry.list_names()),
        # 7d: actor recorded EXPLICITLY on every workflow audit line.
        user_id=str(user.id),
        org_id=str(tenant_id),
    )
    augmented = runner.prepare_messages(augmented)
    if tools is not None and tool_executor is not None:
        tools, tool_executor = runner.filter_tools(tools, tool_executor)

    async def _generator() -> AsyncIterator[bytes]:
        # Leading endpoint meta frame — raw dict via json.dumps (same shape
        # as the terminal error frame). NOT a provider ChatStreamEvent so the
        # provider VO stays {delta, done} only.
        yield _sse_frame({"type": "meta", "conversation_id": str(conv_id), "agent": agent_name})

        accumulated: list[str] = []
        done_model: str | None = None
        done_usage: object = None
        done_finish_reason: str | None = None

        try:
            async for event in provider.stream(
                messages=augmented,
                tools=tools,
                tool_executor=tool_executor,
            ):
                yield f"data: {event.model_dump_json()}\n\n".encode()
                if event.type == "delta":
                    accumulated.append(event.content)
                elif event.type == "done":
                    done_model = event.model
                    done_usage = event.usage
                    done_finish_reason = event.finish_reason
        except _PROVIDER_ERROR_TYPES as e:
            code = _PROVIDER_ERROR_CODES[type(e)]
            yield _sse_frame({"type": "error", "code": code, "message": str(e) or code})
            # Provider failed — do NOT persist an assistant row.
            return

        if done_model is None:
            # Stream ended without a done event (defensive; providers should
            # always emit one). Skip persistence rather than write a partial.
            return

        # --- Txn B: AFTER the stream ---------------------------------------
        # Fresh short session, GUC set again, persist assistant + touch.
        assistant_content = "".join(accumulated)
        await _persist_assistant_and_touch(
            db,
            tenant_id=tenant_id,
            conversation_id=conv_id,
            content=assistant_content,
            model=done_model,
            usage=done_usage,
            finish_reason=done_finish_reason,
        )

        # 5c memory write — OFF the response path (6k-2). Scheduled here (once
        # assistant_content is known) as a background task; Starlette runs it
        # AFTER the stream body closes, so it never delays the visible answer
        # NOR keeps the response open. If the provider errored or emitted no
        # `done`, we returned above and never scheduled it — assistant +
        # conversation are already persisted by Txn B, so no data is lost.
        # Opens its OWN short tenant session; stays best-effort (never raises).
        background_tasks.add_task(
            _extract_and_store_memories,
            db,
            embedding_provider,
            memory_extractor,
            tenant_id=tenant_id,
            user_id=user.id,
            messages=body.messages,
            assistant_reply=assistant_content,
        )

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
        # Attach the request's BackgroundTasks explicitly: the 5c task is
        # appended from inside the generator above, and Starlette reads
        # `background.tasks` after the body completes.
        background=background_tasks,
    )
