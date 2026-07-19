"""LLM-backed memory extractor.

Reuses the phase-3a chat provider — no separate API key. The provider's
reply is expected to be a JSON array of ExtractedMemory. Any parse or
validation failure returns [] (extract-nothing is the safe default —
memory writing is best-effort and callers must not raise from parsing).
"""

from __future__ import annotations

import json

from pydantic import TypeAdapter, ValidationError

from app.ai.extractors.llm.prompts import build_extraction_messages
from app.application.ports.chat import ChatMessage, ChatProvider
from app.application.ports.memory_extraction import ExtractedMemory

_MAX_FACTS_PER_TURN = 5
_MAX_CONTENT_CHARS = 500
_FACTS_ADAPTER = TypeAdapter(list[ExtractedMemory])


class LLMMemoryExtractor:
    def __init__(self, *, chat_provider: ChatProvider) -> None:
        self._chat_provider = chat_provider

    async def extract(
        self,
        *,
        messages: list[ChatMessage],
        assistant_reply: str,
    ) -> list[ExtractedMemory]:
        prompt = build_extraction_messages(messages, assistant_reply)
        completion = await self._chat_provider.complete(messages=prompt)
        raw = _strip_code_fences(completion.content).strip()
        if not raw:
            return []
        try:
            parsed = json.loads(raw)
            facts = _FACTS_ADAPTER.validate_python(parsed)
        except (json.JSONDecodeError, ValidationError, TypeError):
            return []
        # Cap + truncate defensively.
        capped = facts[:_MAX_FACTS_PER_TURN]
        return [
            ExtractedMemory(content=f.content[:_MAX_CONTENT_CHARS], kind=f.kind) for f in capped
        ]


def _strip_code_fences(text: str) -> str:
    """Strip a single ``` or ```json fence pair if the model returned one."""
    stripped = text.strip()
    if not stripped.startswith("```"):
        return stripped
    # Drop first line (```json or ```), and the trailing ``` if present.
    lines = stripped.splitlines()
    if lines and lines[-1].strip().startswith("```"):
        lines = lines[:-1]
    if lines:
        lines = lines[1:]
    return "\n".join(lines)
