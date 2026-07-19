"""Deterministic mock embedding provider.

Same text → identical vector across processes and runs (uses a keyed
SHA-256 stream, not any language-runtime PRNG). Vectors are L2-normalized
so cosine similarity behaves. Zero external calls; the CI/test default.

Locked at 1024 dims by config default — matches the pgvector schema
that 5b will create for voyage-3.5.
"""

from __future__ import annotations

import hashlib
import math

from app.application.ports.embeddings import (
    EmbeddingResult,
    EmbeddingUsage,
    InputType,
)

_DEFAULT_DIM = 1024


def _mock_vector(text: str, dim: int) -> list[float]:
    """Reproducibly derive `dim` L2-normalized floats from `text`."""
    buf = bytearray()
    counter = 0
    while len(buf) < dim * 4:
        digest = hashlib.sha256(f"{text}::{counter}".encode()).digest()
        buf.extend(digest)
        counter += 1

    raw: list[float] = []
    for i in range(dim):
        n = int.from_bytes(buf[i * 4 : i * 4 + 4], byteorder="big", signed=True)
        raw.append(n / (2**31))

    norm = math.sqrt(sum(x * x for x in raw))
    if norm == 0.0:
        return raw
    return [x / norm for x in raw]


class MockEmbeddingProvider:
    def __init__(self, *, dimension: int = _DEFAULT_DIM) -> None:
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(
        self,
        *,
        texts: list[str],
        input_type: InputType = "document",
    ) -> EmbeddingResult:
        vectors = [_mock_vector(t, self._dimension) for t in texts]
        total_tokens = sum(len(t.split()) for t in texts)
        return EmbeddingResult(
            vectors=vectors,
            model="mock-embed-1",
            dimension=self._dimension,
            usage=EmbeddingUsage(total_tokens=total_tokens),
        )
