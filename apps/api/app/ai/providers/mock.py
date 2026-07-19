"""Deterministic mock provider. Returns a canned reply that echoes the last
user message. Zero external calls; suitable for tests + local dev before the
real provider (Phase 3) lands.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any

from app.application.ports.chat import (
    ChatCompletion,
    ChatMessage,
    ChatStreamEvent,
    ToolExecutor,
)


def _last_user_content(messages: list[ChatMessage]) -> str:
    return next((m.content for m in reversed(messages) if m.role == "user"), "")


class MockProvider:
    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_executor: ToolExecutor | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> ChatCompletion:
        # Tools are accepted for Protocol conformance and DELIBERATELY IGNORED.
        # The mock never emits tool_use, so keeping CI deterministic and every
        # existing test byte-for-byte identical is the point of this no-op.
        del tools, tool_executor
        await asyncio.sleep(0)  # keep async boundary honest
        return ChatCompletion(
            content=f"(mock) {_last_user_content(messages)}",
            model=model or "mock-1",
            usage=None,
            finish_reason="stop",
        )

    async def stream(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_executor: ToolExecutor | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[ChatStreamEvent]:
        # Same rationale as complete(): accepted for Protocol conformance and
        # DELIBERATELY IGNORED — the mock never emits tool_use, so keeping CI
        # deterministic and every existing stream test byte-for-byte identical
        # is the point of this no-op.
        del tools, tool_executor
        text = f"(mock) {_last_user_content(messages)}"
        # Word-chunk deltas — first word carries no leading space, rest prepend one.
        for i, word in enumerate(text.split(" ")):
            chunk = word if i == 0 else " " + word
            yield ChatStreamEvent(type="delta", content=chunk)
            await asyncio.sleep(0)
        yield ChatStreamEvent(
            type="done",
            model=model or "mock-1",
            usage=None,
            finish_reason="stop",
        )
