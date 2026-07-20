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

from app.application.ports.tools import ToolCall, ToolInvocation, ToolResult

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
    # Tools the provider ran during this turn. Empty list when no tool loop
    # engaged — additive default keeps the byte-for-byte no-tools shape.
    # Live-only signal for the UI; never persisted onto message rows.
    tool_invocations: list[ToolInvocation] = Field(default_factory=list)


class ChatStreamEvent(BaseModel):
    """One frame in a streamed chat response.

    Single-type-with-discriminator: `type` selects which fields carry payload.
    `delta` events use `content`; `done` events fill in `model` / `usage` /
    `finish_reason`; `tool` events (6e-1) carry `tool_name` / `tool_ok` and
    fire once per tool the provider ran mid-turn — this is the live "Neo is
    searching…" signal the UI turns into a small chip. Endpoint-level error
    frames are emitted as raw JSON (not ChatStreamEvent) so providers can
    only ever emit delta / done / tool.
    """

    type: Literal["delta", "done", "tool"]
    content: str = ""
    model: str | None = None
    usage: ChatUsage | None = None
    finish_reason: str | None = None
    tool_name: str | None = None
    tool_ok: bool | None = None


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
        tools: list[dict[str, Any]] | None = None,
        tool_executor: ToolExecutor | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[ChatStreamEvent]:
        """When `tools` is given, the provider runs the tool-use loop
        internally across streamed turns: intermediate `tool_use` responses
        do NOT emit delta events (their text is suppressed this slice);
        the executor runs; the next turn is streamed. Only the FINAL answer
        turn emits `delta` events to the client. The terminal `done` event
        carries the final usage/finish_reason ("max_tool_iterations" if the
        cap is hit). The frame contract (delta / done) is unchanged.
        """
        ...
