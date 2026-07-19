"""MockEmbeddingProvider — determinism, shape, normalization, batching."""

from __future__ import annotations

import math

import pytest

from app.ai.providers.embeddings.mock import MockEmbeddingProvider


@pytest.mark.asyncio
async def test_mock_returns_exactly_1024_dim_by_default() -> None:
    provider = MockEmbeddingProvider()
    assert provider.dimension == 1024
    result = await provider.embed(texts=["hello"])
    assert result.dimension == 1024
    assert len(result.vectors) == 1
    assert len(result.vectors[0]) == 1024


@pytest.mark.asyncio
async def test_mock_vectors_are_l2_normalized() -> None:
    provider = MockEmbeddingProvider()
    result = await provider.embed(texts=["hello world", "another example text"])
    for v in result.vectors:
        magnitude = math.sqrt(sum(x * x for x in v))
        assert math.isclose(magnitude, 1.0, rel_tol=1e-9, abs_tol=1e-9)


@pytest.mark.asyncio
async def test_mock_is_deterministic_across_calls() -> None:
    provider = MockEmbeddingProvider()
    a = await provider.embed(texts=["the same input"])
    b = await provider.embed(texts=["the same input"])
    assert a.vectors == b.vectors


@pytest.mark.asyncio
async def test_mock_distinct_texts_yield_distinct_vectors() -> None:
    provider = MockEmbeddingProvider()
    result = await provider.embed(texts=["alpha", "beta"])
    assert result.vectors[0] != result.vectors[1]


@pytest.mark.asyncio
async def test_mock_batch_of_n_returns_n_vectors() -> None:
    provider = MockEmbeddingProvider()
    texts = [f"item {i}" for i in range(7)]
    result = await provider.embed(texts=texts)
    assert len(result.vectors) == 7


@pytest.mark.asyncio
async def test_mock_reports_usage_tokens() -> None:
    provider = MockEmbeddingProvider()
    result = await provider.embed(texts=["one two three", "four five"])
    assert result.usage is not None
    # 3 + 2 whitespace tokens.
    assert result.usage.total_tokens == 5


@pytest.mark.asyncio
async def test_mock_dimension_is_configurable() -> None:
    provider = MockEmbeddingProvider(dimension=256)
    assert provider.dimension == 256
    result = await provider.embed(texts=["short vec"])
    assert result.dimension == 256
    assert len(result.vectors[0]) == 256


@pytest.mark.asyncio
async def test_mock_accepts_input_type_and_ignores_it() -> None:
    """Parity with the port; result shouldn't depend on input_type for the mock."""
    provider = MockEmbeddingProvider()
    doc = await provider.embed(texts=["same text"], input_type="document")
    query = await provider.embed(texts=["same text"], input_type="query")
    assert doc.vectors == query.vectors
