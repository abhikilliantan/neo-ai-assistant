"""Unit tests for VoyageEmbeddingProvider — httpx client is fully mocked; no network."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import httpx
import pytest

from app.ai.providers.embeddings.voyage import VoyageEmbeddingProvider
from app.shared.exceptions.embeddings import (
    EmbeddingProviderAPIError,
    EmbeddingProviderAuthError,
    EmbeddingProviderRateLimitError,
    EmbeddingProviderUnavailableError,
)


def _client_returning(response: httpx.Response) -> httpx.AsyncClient:
    client = httpx.AsyncClient()
    client.post = AsyncMock(return_value=response)  # type: ignore[method-assign]
    return client


def _client_raising(exc: BaseException) -> httpx.AsyncClient:
    client = httpx.AsyncClient()
    client.post = AsyncMock(side_effect=exc)  # type: ignore[method-assign]
    return client


def _fake_response(*, status_code: int, json_body: dict[str, Any]) -> httpx.Response:
    return httpx.Response(
        status_code=status_code,
        json=json_body,
        request=httpx.Request("POST", "https://api.voyageai.com/v1/embeddings"),
    )


@pytest.mark.asyncio
async def test_voyage_success_returns_ordered_vectors_and_usage() -> None:
    body = {
        "object": "list",
        "data": [
            {"object": "embedding", "index": 1, "embedding": [0.1, 0.2, 0.3, 0.4]},
            {"object": "embedding", "index": 0, "embedding": [0.5, 0.6, 0.7, 0.8]},
        ],
        "model": "voyage-3.5",
        "usage": {"total_tokens": 42},
    }
    client = _client_returning(_fake_response(status_code=200, json_body=body))
    provider = VoyageEmbeddingProvider(
        api_key="k", model="voyage-3.5", dimension=1024, client=client
    )

    result = await provider.embed(texts=["a", "b"], input_type="query")
    # Reordered by index → item[0] first.
    assert result.vectors == [[0.5, 0.6, 0.7, 0.8], [0.1, 0.2, 0.3, 0.4]]
    assert result.model == "voyage-3.5"
    assert result.dimension == 1024
    assert result.usage is not None
    assert result.usage.total_tokens == 42

    # Payload sanity — input_type is forwarded, output_dimension carries the lock.
    sent = client.post.await_args.kwargs["json"]  # type: ignore[union-attr]
    assert sent["input_type"] == "query"
    assert sent["output_dimension"] == 1024


@pytest.mark.asyncio
async def test_voyage_401_maps_to_auth_error() -> None:
    body = {"error": {"message": "bad key"}}
    client = _client_returning(_fake_response(status_code=401, json_body=body))
    provider = VoyageEmbeddingProvider(api_key="k", client=client)
    with pytest.raises(EmbeddingProviderAuthError):
        await provider.embed(texts=["x"])


@pytest.mark.asyncio
async def test_voyage_403_maps_to_auth_error() -> None:
    client = _client_returning(_fake_response(status_code=403, json_body={"error": {}}))
    provider = VoyageEmbeddingProvider(api_key="k", client=client)
    with pytest.raises(EmbeddingProviderAuthError):
        await provider.embed(texts=["x"])


@pytest.mark.asyncio
async def test_voyage_429_maps_to_rate_limit_error() -> None:
    client = _client_returning(_fake_response(status_code=429, json_body={"error": {}}))
    provider = VoyageEmbeddingProvider(api_key="k", client=client)
    with pytest.raises(EmbeddingProviderRateLimitError):
        await provider.embed(texts=["x"])


@pytest.mark.asyncio
async def test_voyage_5xx_maps_to_api_error() -> None:
    client = _client_returning(_fake_response(status_code=500, json_body={"error": {}}))
    provider = VoyageEmbeddingProvider(api_key="k", client=client)
    with pytest.raises(EmbeddingProviderAPIError):
        await provider.embed(texts=["x"])


@pytest.mark.asyncio
async def test_voyage_timeout_maps_to_unavailable_error() -> None:
    client = _client_raising(httpx.ReadTimeout("slow"))
    provider = VoyageEmbeddingProvider(api_key="k", client=client)
    with pytest.raises(EmbeddingProviderUnavailableError):
        await provider.embed(texts=["x"])


@pytest.mark.asyncio
async def test_voyage_connect_error_maps_to_unavailable_error() -> None:
    client = _client_raising(httpx.ConnectError("nope"))
    provider = VoyageEmbeddingProvider(api_key="k", client=client)
    with pytest.raises(EmbeddingProviderUnavailableError):
        await provider.embed(texts=["x"])
