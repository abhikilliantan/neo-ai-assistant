"""Domain exceptions for AI provider failures. Mapped to HTTP in core/exceptions.py."""

from __future__ import annotations


class AIProviderError(Exception):
    """Base class for upstream AI-provider failures."""


class ProviderAuthError(AIProviderError):
    """Our credentials with the upstream provider are bad (misconfig).

    Maps to 502 (bad gateway) — NOT 401, because this is our config error,
    not the caller's; mapping to 401 would confuse a client into logging
    the user out.
    """


class ProviderRateLimitError(AIProviderError):
    """Upstream is rate-limiting us. Maps to 429."""


class ProviderUnavailableError(AIProviderError):
    """Network / timeout talking to upstream. Maps to 504."""


class ProviderAPIError(AIProviderError):
    """Other upstream API failure. Maps to 502."""
