"""search_memory — the model can query the caller's saved memories mid-turn.

Reuses the 5b vector-search primitive (`MemoryRepository.search_similar`) with
the 6c `embedding_model` guard so a query embedded by model X only scores
against rows embedded by model X. Best-effort behavior is provided by the
6b `ToolRegistry.execute` — a raise here (bad embed, DB fault, missing arg)
surfaces to the model as `is_error=True` on the next tool_result, so chat
still completes normally.

Repo acquisition is factory-based so the SAME tool works on both paths:
  - non-streaming /chat holds a tenant session for the whole request → the
    factory yields that already-bound repo (constant, no session churn).
  - /chat/stream cannot hold a session across the multi-second LLM stream →
    the factory opens a SHORT tenant session per tool call (open + set GUC
    + yield → close), matching the 5d retrieval session's discipline.
The `memory_repo=` kwarg preserves the 6b/6c call-site shape; the new
`memory_repo_factory=` kwarg is the streaming path's entry point.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any
from uuid import UUID

from app.application.ports.embeddings import EmbeddingProvider
from app.application.ports.repositories import MemoryRepositoryPort

_DEFAULT_LIMIT = 5
_MIN_LIMIT = 1
_MAX_LIMIT = 10

# A factory returns a fresh async context manager per call whose enter yields
# a MemoryRepositoryPort. Streaming builds one that opens a short tenant
# session; non-streaming builds one that yields the already-bound repo.
MemoryRepoFactory = Callable[[], AbstractAsyncContextManager[MemoryRepositoryPort]]


def _bound_repo_factory(repo: MemoryRepositoryPort) -> MemoryRepoFactory:
    """Wrap a pre-bound repo into a factory that yields it verbatim per call.

    Used for the non-streaming /chat path so `SearchMemoryTool.run()` has one
    code path (`async with self._factory() as repo`) regardless of caller.
    """

    @asynccontextmanager
    async def _factory() -> AsyncIterator[MemoryRepositoryPort]:
        yield repo

    return _factory


class SearchMemoryTool:
    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        organization_id: UUID,
        user_id: UUID,
        memory_repo: MemoryRepositoryPort | None = None,
        memory_repo_factory: MemoryRepoFactory | None = None,
    ) -> None:
        if (memory_repo is None) == (memory_repo_factory is None):
            raise ValueError(
                "SearchMemoryTool: provide exactly one of memory_repo / memory_repo_factory"
            )
        self._factory: MemoryRepoFactory = (
            memory_repo_factory
            if memory_repo_factory is not None
            else _bound_repo_factory(memory_repo)  # type: ignore[arg-type]
        )
        self._embed = embedding_provider
        self._org_id = organization_id
        self._user_id = user_id

    @property
    def name(self) -> str:
        return "search_memory"

    @property
    def description(self) -> str:
        return (
            "Search the user's saved memories for relevant facts and "
            "preferences. Use when the user refers to something they told "
            "you before."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "required": ["query"],
        }

    async def run(self, arguments: dict[str, Any]) -> str:
        query = str(arguments["query"])  # KeyError caught by the registry → is_error
        raw_limit = arguments.get("limit", _DEFAULT_LIMIT)
        limit = max(_MIN_LIMIT, min(_MAX_LIMIT, int(raw_limit)))

        result = await self._embed.embed(texts=[query], input_type="query")
        async with self._factory() as repo:
            hits = await repo.search_similar(
                organization_id=self._org_id,
                user_id=self._user_id,
                query_embedding=result.vectors[0],
                limit=limit,
                embedding_model=result.model,
            )
        if not hits:
            return "No relevant memories found."
        return "\n".join(f"- {m.content}  (similarity {sim:.2f})" for m, sim in hits)
