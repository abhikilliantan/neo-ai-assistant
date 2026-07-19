"""Health-check port. Implemented by infrastructure adapters."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class HealthCheck(Protocol):
    """A single dependency check. Name identifies it in the response."""

    name: str

    async def check(self) -> bool:
        """Return True if the dependency is reachable and usable."""
        ...
