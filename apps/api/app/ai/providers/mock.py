"""Deterministic mock provider. Returns a canned reply that echoes the last
user message. Zero external calls; suitable for tests + local dev before the
real provider (Phase 3) lands.
"""

from __future__ import annotations

import asyncio

from app.application.ports.chat import ChatCompletion, ChatMessage


class MockProvider:
    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> ChatCompletion:
        await asyncio.sleep(0)  # keep async boundary honest
        last_user = next(
            (m.content for m in reversed(messages) if m.role == "user"),
            "",
        )
        return ChatCompletion(
            content=f"(mock) {last_user}",
            model=model or "mock-1",
            usage=None,
            finish_reason="stop",
        )
