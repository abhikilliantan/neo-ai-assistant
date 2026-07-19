"""Tool adapters + registry builders (startup + per-request + streaming).

Three builders because tools split into three registry lifetimes:
  - **Stateless baseline** (built once at startup, safe to share across all
    requests): EchoTool. Pinned onto `app.state.tool_registry` by main.py.
  - **Request-scoped** (need per-caller state — a bound tenant session,
    user_id): built fresh inside the /chat handler via
    `build_request_tool_registry`. Non-streaming path — the /chat handler
    already holds a tenant session for the whole request, so search_memory
    binds to it directly.
  - **Streaming request-scoped**: built inside /chat/stream. The stream
    path deliberately does NOT hold a DB session across the LLM response,
    so search_memory receives a `MemoryRepoFactory` that opens a SHORT
    tenant session per tool call (matching the 5d retrieval discipline).
    `build_streaming_request_tool_registry` is the entry point.

The builders share `_stateless_tools()` so the baseline set is defined in
exactly one place and can never drift across registry variants.

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
from app.ai.tools.search_memory import MemoryRepoFactory, SearchMemoryTool
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
    """Per-request registry (non-streaming /chat): baseline + tools bound to
    the caller's already-open tenant session.

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


def build_streaming_request_tool_registry(
    *,
    settings: Settings,
    memory_repo_factory: MemoryRepoFactory,
    embedding_provider: EmbeddingProvider,
    organization_id: UUID,
    user_id: UUID,
) -> ToolRegistry:
    """Per-request registry (streaming /chat/stream): baseline + tools bound
    to a SHORT-per-call session factory rather than a live request session.

    /chat/stream deliberately avoids holding a DB connection across the
    LLM stream. search_memory therefore receives a factory that opens a
    fresh tenant session per invocation (set GUC → search → close), so
    tool-driven DB access remains RLS-scoped without pinning the pool for
    the stream's whole duration.
    """
    del settings
    registry = ToolRegistry()
    for tool in _stateless_tools():
        registry.register(tool)
    registry.register(
        SearchMemoryTool(
            memory_repo_factory=memory_repo_factory,
            embedding_provider=embedding_provider,
            organization_id=organization_id,
            user_id=user_id,
        )
    )
    return registry


__all__ = [
    "EchoTool",
    "MemoryRepoFactory",
    "SearchMemoryTool",
    "ToolRegistry",
    "build_request_tool_registry",
    "build_streaming_request_tool_registry",
    "build_tool_registry",
]
