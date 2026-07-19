"""LLM provider adapters + config-driven selection."""

from __future__ import annotations

from anthropic import AsyncAnthropic

from app.ai.providers.anthropic import AnthropicProvider
from app.ai.providers.mock import MockProvider
from app.application.ports.chat import ChatProvider
from app.infrastructure.config import Settings


def build_chat_provider(settings: Settings) -> ChatProvider:
    """Wire the concrete ChatProvider based on settings.ai_provider.

    Fail-fast: if AI_PROVIDER=anthropic but ANTHROPIC_API_KEY is empty, raise
    at startup. Never silently fall back to mock — that would mask config errors.
    """
    if settings.ai_provider == "mock":
        return MockProvider()
    if settings.ai_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise RuntimeError("AI_PROVIDER=anthropic requires ANTHROPIC_API_KEY to be set")
        client = AsyncAnthropic(api_key=settings.anthropic_api_key)
        return AnthropicProvider(
            client=client,
            model=settings.anthropic_model,
            max_tokens=settings.ai_max_tokens,
        )
    raise RuntimeError(f"Unknown AI_PROVIDER: {settings.ai_provider!r}")


__all__ = [
    "AnthropicProvider",
    "MockProvider",
    "build_chat_provider",
]
