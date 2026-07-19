"""Memory extractor adapters + config-driven selection."""

from __future__ import annotations

from app.ai.extractors.llm import LLMMemoryExtractor
from app.ai.extractors.mock import MockMemoryExtractor
from app.application.ports.chat import ChatProvider
from app.application.ports.memory_extraction import MemoryExtractor
from app.infrastructure.config import Settings


def build_memory_extractor(
    settings: Settings,
    chat_provider: ChatProvider,
) -> MemoryExtractor:
    """Wire the concrete MemoryExtractor based on settings.memory_extractor.

    The `llm` variant reuses the already-built chat provider — no new API
    key needed. Fail-fast on unknown value; never silent-fallback to mock.
    """
    if settings.memory_extractor == "mock":
        return MockMemoryExtractor()
    if settings.memory_extractor == "llm":
        return LLMMemoryExtractor(chat_provider=chat_provider)
    raise RuntimeError(f"Unknown MEMORY_EXTRACTOR: {settings.memory_extractor!r}")


__all__ = [
    "LLMMemoryExtractor",
    "MockMemoryExtractor",
    "build_memory_extractor",
]
