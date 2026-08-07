"""save_memory — the model can persist a durable fact/preference mid-turn.

The WRITE counterpart to search_memory (6b/6c). Same dual repo-acquisition so
one tool works on both paths:
  - non-streaming /chat: bound to the request's tenant session (`memory_repo=`).
  - /chat/stream: a `memory_repo_factory=` opens a SHORT tenant session per
    call (set GUC → write → COMMIT on context exit → close), never pinning a
    connection across the LLM stream.

Dedupe + insert go through `save_memory_deduped`, the SAME helper the POST
endpoint and the post-chat extraction path use, so "call me Boss" can't be
stored twice.

This is a WRITE tool: it is classified in WRITE_TOOL_NAMES (app/ai/tools) and
granted only to the assistant + project_analyst agents — never the default
read-only classification.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.ai.memory.write import save_memory_deduped
from app.ai.tools.search_memory import MemoryRepoFactory, _bound_repo_factory
from app.application.ports.embeddings import EmbeddingProvider
from app.application.ports.repositories import MemoryRepositoryPort

# Kinds surfaced to the model. Aligns with the DB CHECK (memory model) minus
# "summary" (extraction-only) — the model classifies user-stated memories.
_KINDS = ("fact", "preference", "instruction", "other")
_DEFAULT_KIND = "fact"


class SaveMemoryTool:
    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        organization_id: UUID,
        user_id: UUID,
        dedupe_threshold: float,
        source: str = "agent",
        memory_repo: MemoryRepositoryPort | None = None,
        memory_repo_factory: MemoryRepoFactory | None = None,
    ) -> None:
        if (memory_repo is None) == (memory_repo_factory is None):
            raise ValueError(
                "SaveMemoryTool: provide exactly one of memory_repo / memory_repo_factory"
            )
        self._factory: MemoryRepoFactory = (
            memory_repo_factory
            if memory_repo_factory is not None
            else _bound_repo_factory(memory_repo)  # type: ignore[arg-type]
        )
        self._embed = embedding_provider
        self._org_id = organization_id
        self._user_id = user_id
        self._threshold = dedupe_threshold
        self._source = source

    @property
    def name(self) -> str:
        return "save_memory"

    @property
    def description(self) -> str:
        return (
            "Save a durable memory about the user so you can recall it in future "
            "conversations. Call this when the user asks you to remember something, "
            "states a lasting preference (how to be addressed, tone, defaults), or "
            "shares a durable fact about themselves or their work. Do NOT save "
            "one-off chit-chat or transient details. Near-duplicates are ignored "
            "automatically. Confirm to the user in one short line after saving."
        )

    @property
    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "content": {
                    "type": "string",
                    "description": "The memory to store, in a clear self-contained sentence.",
                },
                "kind": {
                    "type": "string",
                    "enum": list(_KINDS),
                    "description": "preference (how to be treated), fact, instruction, or other.",
                },
            },
            "required": ["content"],
        }

    async def run(self, arguments: dict[str, Any]) -> str:
        content = str(arguments["content"]).strip()  # KeyError → registry is_error
        if not content:
            return "Nothing to save: the memory content was empty."
        kind = arguments.get("kind", _DEFAULT_KIND)

        async with self._factory() as repo:
            memory, created = await save_memory_deduped(
                repo=repo,
                embedding_provider=self._embed,
                organization_id=self._org_id,
                user_id=self._user_id,
                content=content,
                dedupe_threshold=self._threshold,
                kind=str(kind) if kind is not None else None,
                source=self._source,
            )
        if not created:
            return f'Already remembered something equivalent — kept it as "{memory.content}".'
        return f'Saved to memory ({memory.kind}): "{memory.content}".'
