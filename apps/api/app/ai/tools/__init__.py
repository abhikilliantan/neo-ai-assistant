"""Tool adapters + registry builders (startup + per-request).

Two builders because tools split into two categories:
  - **Stateless baseline** (built once at startup, safe to share across all
    requests): EchoTool. Pinned onto `app.state.tool_registry` by main.py.
  - **Request-scoped** (need per-caller state — session, user_id): built
    fresh inside the /chat handler via `build_request_tool_registry`.

The two builders share `_stateless_tools()` so the baseline set is defined in
exactly one place and can never drift between startup + per-request views.

Why per-request rather than mutating the startup registry: the singleton is
shared by every concurrent request. Mutating it with a caller-bound tool
would race — request A's search_memory could bind to request B's user_id
between the register + execute steps. A per-request registry is the natural
scope for anything holding session or identity state.
"""

from __future__ import annotations

from uuid import UUID

from app.ai.tools.echo import EchoTool
from app.ai.tools.registry import ToolRegistry
from app.ai.tools.search_memory import SearchMemoryTool
from app.application.ports.embeddings import EmbeddingProvider
from app.application.ports.repositories import MemoryRepositoryPort
from app.application.ports.tools import Tool
from app.infrastructure.config import Settings


def _stateless_tools() -> list[Tool]:
    """Tools with no per-caller state. Safe to share process-wide."""
    return [EchoTool()]


def build_tool_registry(settings: Settings) -> ToolRegistry:
    """Startup registry — stateless baseline only. Pinned onto app.state."""
    del settings  # unused; kept for signature parity with 3a/5a/5c/5d
    registry = ToolRegistry()
    for tool in _stateless_tools():
        registry.register(tool)
    return registry


def build_request_tool_registry(
    *,
    settings: Settings,
    memory_repo: MemoryRepositoryPort,
    embedding_provider: EmbeddingProvider,
    organization_id: UUID,
    user_id: UUID,
) -> ToolRegistry:
    """Per-request registry: stateless baseline + tools bound to the caller.

    Called from /chat with the current request's tenant-scoped MemoryRepository,
    the embedding provider, and the resolved (org, user). Never mutates the
    startup registry — a fresh instance every time.
    """
    del settings  # unused for 6c; future TOOLS_* toggles slot in without churn
    registry = ToolRegistry()
    for tool in _stateless_tools():
        registry.register(tool)
    registry.register(
        SearchMemoryTool(
            memory_repo=memory_repo,
            embedding_provider=embedding_provider,
            organization_id=organization_id,
            user_id=user_id,
        )
    )
    return registry


__all__ = [
    "EchoTool",
    "SearchMemoryTool",
    "ToolRegistry",
    "build_request_tool_registry",
    "build_tool_registry",
]
