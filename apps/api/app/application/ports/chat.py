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

from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Literal, Protocol

from pydantic import BaseModel, Field

from app.application.ports.tools import ToolCall, ToolResult

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


ToolExecutor = Callable[[ToolCall], Awaitable[ToolResult]]


class ChatProvider(Protocol):
    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_executor: ToolExecutor | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> ChatCompletion:
        """When `tools` is given, the provider runs the tool-use loop
        internally: any `tool_use` responses trigger `tool_executor(call)`,
        the result is fed back to the model, and the loop continues until
        the model produces a final text answer (or an iteration cap is hit).
        The returned `ChatCompletion` carries only that final text — the
        intermediate turns are ephemeral and never surface to the caller.
        """
        ...

    def stream(
        self,
        *,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[ChatStreamEvent]: ...
