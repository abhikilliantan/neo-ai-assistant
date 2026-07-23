"""build_embedding_provider — config-driven selection + fail-fast."""

from __future__ import annotations

import pytest

from app.ai.providers.embeddings import (
    MockEmbeddingProvider,
    OllamaEmbeddingProvider,
    VoyageEmbeddingProvider,
    build_embedding_provider,
)
from app.infrastructure.config import Settings


def _base(**overrides: object) -> Settings:
    kwargs: dict[str, object] = {
        "python_env": "test",
        "database_url": "postgresql+asyncpg://x/x",
        "app_database_url": "postgresql+asyncpg://x/x",
        "redis_url": "redis://x",
        "jwt_secret_key": "test-secret-key-at-least-32-bytes-long-xxxxx",
    }
    kwargs.update(overrides)
    return Settings(**kwargs)  # type: ignore[arg-type]


def test_build_mock_by_default() -> None:
    provider = build_embedding_provider(_base(embedding_provider="mock"))
    assert isinstance(provider, MockEmbeddingProvider)
    assert provider.dimension == 1024


def test_build_mock_respects_dimension_override() -> None:
    provider = build_embedding_provider(_base(embedding_provider="mock", embedding_dimensions=256))
    assert provider.dimension == 256


def test_build_voyage_with_key_returns_voyage_provider() -> None:
    provider = build_embedding_provider(
        _base(embedding_provider="voyage", voyage_api_key="fake-not-used-in-tests")
    )
    assert isinstance(provider, VoyageEmbeddingProvider)


def test_build_voyage_without_key_raises_at_startup() -> None:
    with pytest.raises(RuntimeError, match="VOYAGE_API_KEY"):
        build_embedding_provider(_base(embedding_provider="voyage", voyage_api_key=""))


def test_build_ollama_returns_ollama_provider_without_key() -> None:
    provider = build_embedding_provider(_base(embedding_provider="ollama"))
    assert isinstance(provider, OllamaEmbeddingProvider)
    assert provider.dimension == 1024


def test_build_pinned_on_app_state_via_db_app_fixture(db_app) -> None:  # type: ignore[no-untyped-def]
    """The conftest fixture must pin a MockEmbeddingProvider on app.state — a
    real Voyage key leaking in from the host env must never trigger a live call.
    """
    assert isinstance(db_app.state.embedding_provider, MockEmbeddingProvider)
