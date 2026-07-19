"""Voyage embedding provider — httpx over the Voyage HTTP API.

Chose httpx over the voyageai SDK: the endpoint is stable and single-shot,
error mapping is trivial by status code, and it avoids adding another
provider SDK to the dep tree for one endpoint.

The API returns embeddings ordered by their input index; we preserve
that order into EmbeddingResult.vectors.
"""

from __future__ import annotations

import httpx

from app.application.ports.embeddings import (
    EmbeddingResult,
    EmbeddingUsage,
    InputType,
)
from app.shared.exceptions.embeddings import (
    EmbeddingProviderAPIError,
    EmbeddingProviderAuthError,
    EmbeddingProviderRateLimitError,
    EmbeddingProviderUnavailableError,
)

_ENDPOINT = "https://api.voyageai.com/v1/embeddings"


class VoyageEmbeddingProvider:
    def __init__(
        self,
        *,
        api_key: str,
        model: str = "voyage-3.5",
        dimension: int = 1024,
        client: httpx.AsyncClient | None = None,
        timeout: float = 30.0,
    ) -> None:
        self._model = model
        self._dimension = dimension
        self._client = client or httpx.AsyncClient(
            timeout=timeout,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
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
        payload = {
            "input": texts,
            "model": self._model,
            "input_type": input_type,
            "output_dimension": self._dimension,
        }
        try:
            response = await self._client.post(_ENDPOINT, json=payload)
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            raise EmbeddingProviderUnavailableError(str(e)) from e
        except httpx.HTTPError as e:
            raise EmbeddingProviderAPIError(str(e)) from e

        self._raise_for_status(response)

        body = response.json()
        # Voyage returns items in input order but re-sort defensively.
        items = sorted(body["data"], key=lambda d: d["index"])
        vectors = [item["embedding"] for item in items]
        usage_dict = body.get("usage") or {}
        usage = (
            EmbeddingUsage(total_tokens=usage_dict["total_tokens"])
            if "total_tokens" in usage_dict
            else None
        )
        return EmbeddingResult(
            vectors=vectors,
            model=body.get("model", self._model),
            dimension=self._dimension,
            usage=usage,
        )

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_success:
            return
        status = response.status_code
        # Best-effort extraction of the upstream error message; don't leak
        # request/header contents.
        try:
            detail = response.json().get("error", {}).get("message") or response.text
        except ValueError:
            detail = response.text
        if status in (401, 403):
            raise EmbeddingProviderAuthError(detail or f"HTTP {status}")
        if status == 429:
            raise EmbeddingProviderRateLimitError(detail or f"HTTP {status}")
        if status >= 500:
            raise EmbeddingProviderAPIError(detail or f"HTTP {status}")
        raise EmbeddingProviderAPIError(detail or f"HTTP {status}")

    async def close(self) -> None:
        await self._client.aclose()
