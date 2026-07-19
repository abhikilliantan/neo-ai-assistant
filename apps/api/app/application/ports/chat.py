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


class ChatProvider(Protocol):
    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> ChatCompletion: ...
