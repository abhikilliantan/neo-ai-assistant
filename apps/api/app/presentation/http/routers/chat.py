"""Chat endpoint — first tenant-scoped feature route.

Uses `TenantSessionDep` so RLS engages with the caller's tenant GUC even
though this endpoint doesn't touch the DB yet — Phase 4 will use it for
message persistence, and this proves the wiring end-to-end today.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.application.ports.chat import ChatMessage, ChatProvider
from app.presentation.http.deps import CurrentUserDep, TenantSessionDep
from app.presentation.http.schemas.chat import ChatRequest, ChatResponse

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
