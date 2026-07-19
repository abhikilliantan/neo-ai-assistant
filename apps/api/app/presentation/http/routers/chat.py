"""Chat endpoints — non-streaming (/chat) + streaming (/chat/stream).

Non-streaming holds a tenant-scoped DB session for the whole request (fine —
short call). The streaming variant deliberately does NOT: it would pin a DB
connection for the whole LLM response duration, exhausting the pool. Instead
it resolves the user via the scoped variant and reads tenant_id from the
token payload (no DB). Phase 4 will open a short write-transaction AFTER
the stream to persist the assistant message.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.application.ports.chat import ChatMessage, ChatProvider
from app.presentation.http.deps import (
    CurrentTenantDep,
    CurrentUserDep,
    StreamingCurrentUserDep,
    TenantSessionDep,
)
from app.presentation.http.schemas.chat import ChatRequest, ChatResponse
from app.shared.exceptions.ai import (
    ProviderAPIError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)

router = APIRouter(prefix="/api/v1", tags=["chat"])


def get_chat_provider(request: Request) -> ChatProvider:
    """Read the chat provider built once in the lifespan.

    build_chat_provider(settings) picks mock vs anthropic per AI_PROVIDER;
    test fixtures override app.state.chat_provider directly to pin `mock`.
    """
    return request.app.state.chat_provider  # type: ignore[no-any-return]


ProviderDep = Annotated[ChatProvider, Depends(get_chat_provider)]


@router.post("/chat", response_model=ChatResponse)
async def chat(
    body: ChatRequest,
    _user: CurrentUserDep,
    _session: TenantSessionDep,  # engages SET LOCAL app.current_tenant
    provider: ProviderDep,
) -> ChatResponse:
    completion = await provider.complete(messages=body.messages)
    return ChatResponse(
        message=ChatMessage(role="assistant", content=completion.content),
        model=completion.model,
        usage=completion.usage,
    )


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


@router.post("/chat/stream")
async def chat_stream(
    body: ChatRequest,
    _user: StreamingCurrentUserDep,  # scoped session — no held DB connection
    _tenant: CurrentTenantDep,  # read from token; Phase 4 uses it
    provider: ProviderDep,
) -> StreamingResponse:
    async def _generator() -> AsyncIterator[bytes]:
        try:
            async for event in provider.stream(messages=body.messages):
                yield f"data: {event.model_dump_json()}\n\n".encode()
        except _PROVIDER_ERROR_TYPES as e:
            # Headers already sent; can't change status. Emit terminal error frame.
            code = _PROVIDER_ERROR_CODES[type(e)]
            yield _sse_frame({"type": "error", "code": code, "message": str(e) or code})

    return StreamingResponse(
        _generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
