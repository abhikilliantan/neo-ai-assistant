"""Unit tests for OllamaEmbeddingProvider — httpx client fully mocked; no network."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from app.ai.providers.embeddings import ollama as ollama_module
from app.ai.providers.embeddings.ollama import OllamaEmbeddingProvider
from app.shared.exceptions.embeddings import (
    EmbeddingProviderAPIError,
    EmbeddingProviderRateLimitError,
    EmbeddingProviderUnavailableError,
)

_BASE_URL = "http://host.docker.internal:11434"


@pytest.fixture(autouse=True)
def _no_backoff_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skip the real exponential-backoff sleeps so retry tests stay fast."""
    monkeypatch.setattr(ollama_module.provider.asyncio, "sleep", AsyncMock())


def _client_returning(response: httpx.Response) -> httpx.AsyncClient:
    client = httpx.AsyncClient()
    client.post = AsyncMock(return_value=response)  # type: ignore[method-assign]
    return client


def _client_with_side_effect(side_effect: Any) -> httpx.AsyncClient:
    client = httpx.AsyncClient()
    client.post = AsyncMock(side_effect=side_effect)  # type: ignore[method-assign]
    return client


def _fake_response(*, status_code: int, json_body: dict[str, Any]) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=json_body,
        request=httpx.Request("POST", f"{_BASE_URL}/api/embed"),
    )


@pytest.mark.asyncio
async def test_ollama_success_single_batched_request_preserves_input_order() -> None:
    body = {
        "model": "bge-m3",
        "embeddings": [
            [0.1, 0.2, 0.3, 0.4],  # for "a"
            [0.5, 0.6, 0.7, 0.8],  # for "b"
        ],
    }
    client = _client_returning(_fake_response(status_code=200, json_body=body))
    provider = OllamaEmbeddingProvider(
        base_url=_BASE_URL, model="bge-m3", dimension=4, client=client
    )

    result = await provider.embed(texts=["a", "b"], input_type="query")

    # Order preserved exactly as returned (input order).
    assert result.vectors == [[0.1, 0.2, 0.3, 0.4], [0.5, 0.6, 0.7, 0.8]]
    assert result.model == "bge-m3"
    assert result.dimension == 4
    assert result.usage is None

    # ALL texts sent in ONE request — this is what dodges per-chunk rate limits.
    client.post.assert_awaited_once()  # type: ignore[attr-defined]
    call = client.post.await_args  # type: ignore[union-attr]
    assert call.args[0] == f"{_BASE_URL}/api/embed"
    sent = call.kwargs["json"]
    assert sent == {"model": "bge-m3", "input": ["a", "b"]}


@pytest.mark.asyncio
async def test_ollama_base_url_trailing_slash_is_normalised() -> None:
    body = {"model": "bge-m3", "embeddings": [[0.1, 0.2, 0.3, 0.4]]}
    client = _client_returning(_fake_response(status_code=200, json_body=body))
    provider = OllamaEmbeddingProvider(
        base_url=f"{_BASE_URL}/", model="bge-m3", dimension=4, client=client
    )

    await provider.embed(texts=["a"])

    assert client.post.await_args.args[0] == f"{_BASE_URL}/api/embed"  # type: ignore[union-attr]


@pytest.mark.asyncio
async def test_ollama_dimension_mismatch_raises_api_error() -> None:
    # Model set to a 3-dim output while the schema expects 1024.
    body = {"model": "bge-m3", "embeddings": [[0.1, 0.2, 0.3]]}
    client = _client_returning(_fake_response(status_code=200, json_body=body))
    provider = OllamaEmbeddingProvider(
        base_url=_BASE_URL, model="bge-m3", dimension=1024, client=client
    )
    with pytest.raises(EmbeddingProviderAPIError, match="dimension mismatch"):
        await provider.embed(texts=["x"])


@pytest.mark.asyncio
async def test_ollama_429_maps_to_rate_limit_error() -> None:
    client = _client_returning(_fake_response(status_code=429, json_body={"error": "slow down"}))
    provider = OllamaEmbeddingProvider(base_url=_BASE_URL, dimension=1024, client=client)
    with pytest.raises(EmbeddingProviderRateLimitError):
        await provider.embed(texts=["x"])


@pytest.mark.asyncio
async def test_ollama_5xx_maps_to_api_error() -> None:
    client = _client_returning(_fake_response(status_code=500, json_body={"error": "boom"}))
    provider = OllamaEmbeddingProvider(base_url=_BASE_URL, dimension=1024, client=client)
    with pytest.raises(EmbeddingProviderAPIError):
        await provider.embed(texts=["x"])


@pytest.mark.asyncio
async def test_ollama_retries_on_timeout_then_succeeds() -> None:
    body = {"model": "bge-m3", "embeddings": [[0.1, 0.2, 0.3, 0.4]]}
    ok = _fake_response(status_code=200, json_body=body)
    # Cold model load times out twice, succeeds on the third attempt.
    client = _client_with_side_effect(
        [httpx.ReadTimeout("cold load"), httpx.ReadTimeout("cold load"), ok]
    )
    provider = OllamaEmbeddingProvider(
        base_url=_BASE_URL, model="bge-m3", dimension=4, client=client
    )

    result = await provider.embed(texts=["a"])

    assert result.vectors == [[0.1, 0.2, 0.3, 0.4]]
    assert client.post.await_count == 3  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_ollama_timeout_exhausts_retries_and_maps_to_unavailable() -> None:
    client = _client_with_side_effect(httpx.ReadTimeout("still cold"))
    provider = OllamaEmbeddingProvider(base_url=_BASE_URL, dimension=1024, client=client)
    with pytest.raises(EmbeddingProviderUnavailableError):
        await provider.embed(texts=["x"])
    assert client.post.await_count == 3  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_ollama_connect_error_exhausts_retries_and_maps_to_unavailable() -> None:
    client = _client_with_side_effect(httpx.ConnectError("no ollama"))
    provider = OllamaEmbeddingProvider(base_url=_BASE_URL, dimension=1024, client=client)
    with pytest.raises(EmbeddingProviderUnavailableError):
        await provider.embed(texts=["x"])
    assert client.post.await_count == 3  # type: ignore[attr-defined]
