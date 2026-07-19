"""Memory extractor port + value objects.

Given a chat turn (input messages + assistant reply), extract durable
user-specific facts / preferences worth persisting as long-term memory.
5c only writes what this returns; 5d will retrieve + inject them into the
next chat call.
"""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel

from app.application.ports.chat import ChatMessage

MemoryKind = Literal["fact", "preference", "summary"]


class ExtractedMemory(BaseModel):
    content: str
    kind: MemoryKind = "fact"


class MemoryExtractor(Protocol):
    async def extract(
        self,
        *,
        messages: list[ChatMessage],
        assistant_reply: str,
    ) -> list[ExtractedMemory]: ...
