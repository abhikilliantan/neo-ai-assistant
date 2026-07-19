"""Neo shared — framework-free Python transport contracts.

No business logic. No I/O. No framework imports.
"""

from typing import Literal, TypedDict

__version__ = "0.1.0"


class HealthStatus(TypedDict):
    status: Literal["ok", "degraded"]
    version: str


__all__ = ["HealthStatus", "__version__"]
