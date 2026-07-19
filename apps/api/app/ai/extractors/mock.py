"""Deterministic mock memory extractor.

Returns exactly one ExtractedMemory whose content is a stable function of
the last user message. Zero LLM calls, zero randomness — this is the CI/test
default and makes 5c's write-path tests deterministic.
"""

from __future__ import annotations

from app.application.ports.chat import ChatMessage
from app.application.ports.memory_extraction import ExtractedMemory


class MockMemoryExtractor:
    async def extract(
        self,
        *,
        messages: list[ChatMessage],
        assistant_reply: str,
    ) -> list[ExtractedMemory]:
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        if not last_user:
            return []
        return [ExtractedMemory(content=f"user_fact: {last_user}", kind="fact")]
