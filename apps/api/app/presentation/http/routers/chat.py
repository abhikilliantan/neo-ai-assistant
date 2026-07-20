"""Chat endpoints — non-streaming (/chat) + streaming (/chat/stream).

Non-streaming holds a tenant-scoped DB session for the whole request (fine —
short call). The streaming variant deliberately does NOT: it would pin a DB
connection for the whole LLM response duration, exhausting the pool. Instead
it opens TWO short bookending tenant write-txns — one BEFORE the stream
(resolve/create conversation + persist the user message) and one AFTER the
provider's `done` event (persist the assistant message + touch). Neither
session is open across the LLM stream.

If the client disconnects mid-stream, the "after" txn simply doesn't run —
the user question is already saved from the "before" txn, and the assistant
row is skipped. Acceptable for 4b.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from app.ai.tools import (
    build_request_tool_registry,
    build_streaming_request_tool_registry,
)
from app.ai.tools.search_memory import MemoryRepoFactory
from app.application.ports.chat import ChatMessage, ChatProvider
from app.application.ports.embeddings import EmbeddingProvider
from app.application.ports.memory_extraction import MemoryExtractor
from app.application.ports.repositories import MemoryRepositoryPort
from app.infrastructure.db import Database
from app.infrastructure.db.repositories import (
    ConversationRepository,
    MemoryRepository,
    MessageRepository,
)
from app.infrastructure.logging import get_logger
from app.presentation.http.deps import (
    CurrentTenantDep,
    CurrentUserDep,
    EmbeddingProviderDep,
    MemoryExtractorDep,
    SettingsDep,
    StreamingCurrentUserDep,
    TenantSessionDep,
    get_app_database,
    get_embedding_provider,
    get_memory_extractor,
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
    "Things you remember about this user (use where relevant, don't mention unless helpful):"
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

    ENG-BACKLOG: on the non-streaming path this adds extractor+embedding
    latency to the response. Move to a background task once we have one.
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


# --- non-streaming ----------------------------------------------------------


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    user: CurrentUserDep,
    tenant_id: CurrentTenantDep,
    session: TenantSessionDep,  # engages SET LOCAL app.current_tenant
    provider: ProviderDep,
    embedding_provider: EmbeddingProviderDep,
    memory_extractor: MemoryExtractorDep,
    settings: SettingsDep,
    db: Annotated[Database, Depends(get_app_database)],
) -> ChatResponse:
    if tenant_id is None:
        raise AuthenticationError("user has no active tenant")

    conv_repo = ConversationRepository(session)
    msg_repo = MessageRepository(session)

    if body.conversation_id is not None:
        conv = await conv_repo.get_by_id(body.conversation_id)
        if conv is None:
            raise NotFoundError("conversation not found")
    else:
        conv = await conv_repo.create(
            organization_id=tenant_id,
            user_id=user.id,
            title=_title_from(body.messages[-1].content),
        )

    await msg_repo.add(
        organization_id=tenant_id,
        conversation_id=conv.id,
        role="user",
        content=body.messages[-1].content,
    )

    # Retrieve prior memories BEFORE the provider call. The 5c write for THIS
    # turn runs AFTER the provider (below), so the just-being-extracted fact
    # cannot leak into this turn's context.
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

    # Tools: build a PER-REQUEST registry so caller-bound tools (search_memory)
    # get the current tenant session, embedding provider, and user_id. The
    # app.state (startup) registry is stateless-baseline only and is NOT
    # mutated per request. The tool-use loop lives INSIDE the provider —
    # intermediate tool_use/tool_result turns are ephemeral and never surface
    # to persistence (only completion.content does).
    tools = None
    tool_executor = None
    if settings.tools_enabled:
        request_registry = build_request_tool_registry(
            settings=settings,
            memory_repo=MemoryRepository(session),
            embedding_provider=embedding_provider,
            organization_id=tenant_id,
            user_id=user.id,
        )
        specs = request_registry.specs()
        if specs:
            tools = specs
            tool_executor = request_registry.execute

    completion = await provider.complete(
        messages=augmented,
        tools=tools,
        tool_executor=tool_executor,
    )

    prompt_tokens, completion_tokens = _usage_tokens(completion.usage)
    await msg_repo.add(
        organization_id=tenant_id,
        conversation_id=conv.id,
        role="assistant",
        content=completion.content,
        model=completion.model,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        finish_reason=completion.finish_reason,
    )
    await conv_repo.touch(conv.id)

    # Best-effort memory write. Opens its OWN short tenant session, never
    # raises, adds extraction+embedding latency to the response (backlog:
    # move behind a background task).
    await _extract_and_store_memories(
        db,
        embedding_provider,
        memory_extractor,
        tenant_id=tenant_id,
        user_id=user.id,
        messages=body.messages,
        assistant_reply=completion.content,
    )

    return ChatResponse(
        conversation_id=conv.id,
        message=ChatMessage(role="assistant", content=completion.content),
        model=completion.model,
        usage=completion.usage,
        tool_invocations=completion.tool_invocations,
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
) -> UUID:
    """Short tenant write-txn: resolve-or-create conversation + persist the
    user message. Returns the conversation id. Session opens and closes here
    — nothing is held for the caller.
    """
    async with db.sessionmaker() as session, session.begin():
        await session.execute(
            text("SELECT set_config('app.current_tenant', :t, true)").bindparams(t=str(tenant_id))
        )
        conv_repo = ConversationRepository(session)
        msg_repo = MessageRepository(session)

        if conversation_id is not None:
            conv = await conv_repo.get_by_id(conversation_id)
            if conv is None:
                raise NotFoundError("conversation not found")
        else:
            conv = await conv_repo.create(
                organization_id=tenant_id,
                user_id=user_id,
                title=_title_from(user_message),
            )
        await msg_repo.add(
            organization_id=tenant_id,
            conversation_id=conv.id,
            role="user",
            content=user_message,
        )
        return conv.id


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
) -> StreamingResponse:
    if tenant_id is None:
        raise AuthenticationError("user has no active tenant")

    # --- Txn A: BEFORE the stream ------------------------------------------
    # Resolve/create conversation + persist the user message in a short txn,
    # then release the connection. Errors here (NotFoundError, provider
    # config issues) still surface as normal HTTP responses because
    # StreamingResponse hasn't been returned yet.
    conv_id = await _persist_user_and_resolve_conversation(
        db,
        tenant_id=tenant_id,
        user_id=user.id,
        conversation_id=body.conversation_id,
        user_message=body.messages[-1].content,
    )

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

    # Tools: build a per-request STREAMING registry. search_memory binds to a
    # SHORT-per-call session factory (never holds a session across the LLM
    # stream). Retrieval/persist txns above/below remain the sole DB sessions
    # bookending this request; tool-driven DB access is entirely per-call.
    # tools_enabled=false → provider gets tools=None (kill switch gates the
    # stream path too).
    tools: list[dict[str, object]] | None = None
    tool_executor = None
    if settings.tools_enabled:
        streaming_registry = build_streaming_request_tool_registry(
            settings=settings,
            memory_repo_factory=_make_streaming_memory_repo_factory(db, tenant_id=tenant_id),
            embedding_provider=embedding_provider,
            organization_id=tenant_id,
            user_id=user.id,
        )
        specs = streaming_registry.specs()
        if specs:
            tools = specs
            tool_executor = streaming_registry.execute

    async def _generator() -> AsyncIterator[bytes]:
        # Leading endpoint meta frame — raw dict via json.dumps (same shape
        # as the terminal error frame). NOT a provider ChatStreamEvent so the
        # provider VO stays {delta, done} only.
        yield _sse_frame({"type": "meta", "conversation_id": str(conv_id)})

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

        # --- Txn C: memory write (best-effort) -----------------------------
        # Happens AFTER the done frame was yielded, so it never delays the
        # visible answer. If the client already disconnected, generator
        # cancellation skips this — assistant + conversation are already
        # persisted by Txn B, so no data is lost.
        await _extract_and_store_memories(
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
    )
