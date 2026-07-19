"""Embedding provider port + value objects.

Mirrors the chat provider pattern: framework-free VOs + a Protocol.

Voyage — and modern embedding models generally — perform better when the
caller tells them *how* the text will be used. Documents (stored content
being embedded once) and queries (short text the user is searching with)
get different implicit prefixes and, sometimes, different linear heads.
Baking `input_type` into the port from day one means:
  - 5b (embedding chat messages / stored content) passes "document";
  - 5c (embedding the user's query for cosine-nearest lookup) passes "query".
The mock accepts and ignores it; the real Voyage provider forwards it.
"""

from __future__ import annotations

from typing import Literal, Protocol

from pydantic import BaseModel

InputType = Literal["document", "query"]


class EmbeddingUsage(BaseModel):
    total_tokens: int


class EmbeddingResult(BaseModel):
    vectors: list[list[float]]
    model: str
    dimension: int
    usage: EmbeddingUsage | None = None


class EmbeddingProvider(Protocol):
    @property
    def dimension(self) -> int: ...

    async def embed(
        self,
        *,
        texts: list[str],
        input_type: InputType = "document",
    ) -> EmbeddingResult: ...
