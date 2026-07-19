"""Chat provider port + value objects.

Streaming is intentionally out of scope for the current Protocol; when a
real streaming provider lands, we add a SEPARATE method:

    async def stream(
        self, *, messages: list[ChatMessage], model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[ChatCompletionChunk]: ...

That keeps `complete()` unchanged (no union return type, no `stream=True`
flag that changes the return shape). Callers that don't need streaming
stay simple; providers implement `stream()` only when they support it.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Literal, Protocol

from pydantic import BaseModel, Field

ChatRole = Literal["system", "user", "assistant"]


class ChatMessage(BaseModel):
    role: ChatRole
    content: str


class ChatUsage(BaseModel):
    prompt_tokens: int
    completion_tokens: int


class ChatCompletion(BaseModel):
    content: str
    model: str
    usage: ChatUsage | None = None
    finish_reason: str = Field(default="stop")


class ChatStreamEvent(BaseModel):
    """One frame in a streamed chat response.

    Single-type-with-discriminator: `type` selects which fields carry payload.
    `delta` events use `content`; `done` events fill in `model` / `usage` /
    `finish_reason`. Endpoint-level error frames are emitted as raw JSON
    (not as ChatStreamEvent) so providers can only ever emit delta/done.
    """

    type: Literal["delta", "done"]
    content: str = ""
    model: str | None = None
    usage: ChatUsage | None = None
    finish_reason: str | None = None


class ChatProvider(Protocol):
    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> ChatCompletion: ...

    def stream(
        self,
        *,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[ChatStreamEvent]: ...
