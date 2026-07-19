"""Tool adapters + config-driven registry build.

Mirrors the chat / embedding / extractor bootstrap pattern: a `build_*`
factory called once in the lifespan and pinned onto `app.state`.

For 6a the mock EchoTool is the only registered tool — settings is accepted
so a future TOOLS_ENABLED-style toggle can slot in without churning callers.
"""

from __future__ import annotations

from app.ai.tools.echo import EchoTool
from app.ai.tools.registry import ToolRegistry
from app.infrastructure.config import Settings


def build_tool_registry(settings: Settings) -> ToolRegistry:
    """Register the built-in tools. Fail-fast on unknown selectors (none yet)."""
    del settings  # unused for 6a; kept for signature parity with 3a/5a/5c/5d
    registry = ToolRegistry()
    registry.register(EchoTool())
    return registry


__all__ = ["EchoTool", "ToolRegistry", "build_tool_registry"]
