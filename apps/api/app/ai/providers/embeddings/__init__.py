"""Embedding provider adapters + config-driven selection."""

from __future__ import annotations

from app.ai.providers.embeddings.mock import MockEmbeddingProvider
from app.ai.providers.embeddings.ollama import OllamaEmbeddingProvider
from app.ai.providers.embeddings.voyage import VoyageEmbeddingProvider
from app.application.ports.embeddings import EmbeddingProvider
from app.infrastructure.config import Settings


def build_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """Wire the concrete EmbeddingProvider based on settings.embedding_provider.

    Fail-fast: EMBEDDING_PROVIDER=voyage with an empty VOYAGE_API_KEY raises
    at startup. Never silently fall back to mock — that would mask config
    errors and result in a live prod pointing at deterministic mock vectors.
    """
    if settings.embedding_provider == "mock":
        return MockEmbeddingProvider(dimension=settings.embedding_dimensions)
    if settings.embedding_provider == "voyage":
        if not settings.voyage_api_key:
            raise RuntimeError("EMBEDDING_PROVIDER=voyage requires VOYAGE_API_KEY to be set")
        return VoyageEmbeddingProvider(
            api_key=settings.voyage_api_key,
            model=settings.embedding_model,
            dimension=settings.embedding_dimensions,
        )
    if settings.embedding_provider == "ollama":
        # Local, unlimited, private — no API key required.
        return OllamaEmbeddingProvider(
            base_url=settings.ollama_base_url,
            model=settings.embedding_model,
            dimension=settings.embedding_dimensions,
        )
    raise RuntimeError(f"Unknown EMBEDDING_PROVIDER: {settings.embedding_provider!r}")


__all__ = [
    "MockEmbeddingProvider",
    "OllamaEmbeddingProvider",
    "VoyageEmbeddingProvider",
    "build_embedding_provider",
]
