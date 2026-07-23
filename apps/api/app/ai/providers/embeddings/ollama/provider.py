"""Ollama embedding provider — httpx over Ollama's local batch endpoint.

Mirrors the Voyage provider: httpx over a single stable endpoint, error
mapping by status code, order-preserving results. The win over Voyage is that
Ollama runs locally (unlimited, private, no per-chunk rate limit), so we send
ALL texts in ONE request to /api/embed.

Ollama's /api/embed accepts a list under "input" and returns
{"embeddings": [[...], ...]} in input order.

A cold model load can make the first call slow (or time out), so the default
timeout is longer than Voyage's and unavailable/timeout failures are retried
with exponential backoff.
"""

from __future__ import annotations

import asyncio

import httpx

from app.application.ports.embeddings import (
    EmbeddingResult,
    InputType,
)
from app.shared.exceptions.embeddings import (
    EmbeddingProviderAPIError,
    EmbeddingProviderRateLimitError,
    EmbeddingProviderUnavailableError,
)

_EMBED_PATH = "/api/embed"
_MAX_ATTEMPTS = 3
_BACKOFF_BASE_SECONDS = 0.5


class OllamaEmbeddingProvider:
    def __init__(
        self,
        *,
        base_url: str,
        model: str = "bge-m3",
        dimension: int = 1024,
        client: httpx.AsyncClient | None = None,
        timeout: float = 120.0,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._dimension = dimension
        self._client = client or httpx.AsyncClient(
            timeout=timeout,
            headers={"Content-Type": "application/json"},
        )

    @property
    def dimension(self) -> int:
        return self._dimension

    async def embed(
        self,
        *,
        texts: list[str],
        input_type: InputType = "document",
    ) -> EmbeddingResult:
        # input_type accepted and ignored (like the mock).
        # TODO: bge-m3 supports a query prefix ("Represent this sentence …");
        # forward input_type == "query" as a prefix once retrieval needs it.
        payload: dict[str, object] = {
            "model": self._model,
            "input": texts,
        }
        response = await self._post_with_retry(payload)

        self._raise_for_status(response)

        body = response.json()
        # /api/embed returns embeddings in input order.
        vectors = body["embeddings"]
        self._validate_dimensions(vectors)
        return EmbeddingResult(
            vectors=vectors,
            model=body.get("model", self._model),
            dimension=self._dimension,
            usage=None,
        )

    async def _post_with_retry(self, payload: dict[str, object]) -> httpx.Response:
        url = f"{self._base_url}{_EMBED_PATH}"
        last_exc: EmbeddingProviderUnavailableError | None = None
        for attempt in range(_MAX_ATTEMPTS):
            try:
                return await self._client.post(url, json=payload)
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                # A cold model load can time out the first hit — back off and retry.
                last_exc = EmbeddingProviderUnavailableError(str(e))
                if attempt < _MAX_ATTEMPTS - 1:
                    await asyncio.sleep(_BACKOFF_BASE_SECONDS * (2**attempt))
                    continue
                raise last_exc from e
            except httpx.HTTPError as e:
                raise EmbeddingProviderAPIError(str(e)) from e
        # Unreachable: the loop either returns or raises. Kept for type-checkers.
        raise last_exc or EmbeddingProviderUnavailableError("unknown error")

    def _validate_dimensions(self, vectors: list[list[float]]) -> None:
        # Guards against pointing a 768-dim model at the 1024-dim schema.
        for vec in vectors:
            if len(vec) != self._dimension:
                raise EmbeddingProviderAPIError(
                    f"embedding dimension mismatch: model returned {len(vec)}, "
                    f"expected {self._dimension}"
                )

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_success:
            return
        status = response.status_code
        # Best-effort extraction of the upstream error message; don't leak
        # request/header contents.
        try:
            detail = response.json().get("error") or response.text
        except ValueError:
            detail = response.text
        if status == 429:
            raise EmbeddingProviderRateLimitError(detail or f"HTTP {status}")
        raise EmbeddingProviderAPIError(detail or f"HTTP {status}")

    async def close(self) -> None:
        await self._client.aclose()
