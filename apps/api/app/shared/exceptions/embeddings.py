"""Domain exceptions for embedding provider failures.

Mapped to HTTP in core/exceptions.py — separate hierarchy from the chat
provider exceptions so the two providers can fail independently and be
observed independently in the handler wiring.
"""

from __future__ import annotations


class EmbeddingProviderError(Exception):
    """Base class for upstream embedding-provider failures."""


class EmbeddingProviderAuthError(EmbeddingProviderError):
    """Our credentials with the upstream provider are bad (misconfig).

    Maps to 502 — same reasoning as ProviderAuthError on the chat side.
    """


class EmbeddingProviderRateLimitError(EmbeddingProviderError):
    """Upstream is rate-limiting us. Maps to 429."""


class EmbeddingProviderUnavailableError(EmbeddingProviderError):
    """Network / timeout talking to upstream. Maps to 504."""


class EmbeddingProviderAPIError(EmbeddingProviderError):
    """Other upstream API failure. Maps to 502."""
