"""search_memory — the model can query the caller's saved memories mid-turn.

Reuses the 5b vector-search primitive (`MemoryRepository.search_similar`) with
the 6c `embedding_model` guard so a query embedded by model X only scores
against rows embedded by model X. Best-effort behavior is provided by the
6b `ToolRegistry.execute` — a raise here (bad embed, DB fault, missing arg)
surfaces to the model as `is_error=True` on the next tool_result, so chat
still completes normally.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.application.ports.embeddings import EmbeddingProvider
from app.application.ports.repositories import MemoryRepositoryPort

_DEFAULT_LIMIT = 5
_MIN_LIMIT = 1
_MAX_LIMIT = 10


class SearchMemoryTool:
    def __init__(
        self,
        *,
        memory_repo: MemoryRepositoryPort,
        embedding_provider: EmbeddingProvider,
        organization_id: UUID,
        user_id: UUID,
    ) -> None:
        self._repo = memory_repo
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
        hits = await self._repo.search_similar(
            organization_id=self._org_id,
            user_id=self._user_id,
            query_embedding=result.vectors[0],
            limit=limit,
            embedding_model=result.model,
        )
        if not hits:
            return "No relevant memories found."
        return "\n".join(f"- {m.content}  (similarity {sim:.2f})" for m, sim in hits)
