"""search_documents — the model can query the ORG's ingested documents mid-turn,
and cite them.

Same shape as 6c's search_memory (embedded corpus behind the Tool protocol, a
per-request repo bound via factory so ONE code path serves both /chat and
/chat/stream), over document chunks instead of memories. Two deliberate
differences from search_memory:

  1. SCOPE IS TENANT-ONLY, not per-user (see run()): documents belong to the
     organisation, so any member finds any colleague's document.
  2. CITATIONS ARE THE POINT: each result carries its source filename plus the
     canonical position string from 8a's DocumentPosition.render(), so the model
     can quote where a passage came from.

Best-effort behavior comes from the 6b ToolRegistry.execute — a raise here (bad
embed, DB fault, missing arg) surfaces to the model as is_error=True on the next
tool_result, so chat still completes.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any
from uuid import UUID

from app.application.ports.documents import DocumentPosition
from app.application.ports.embeddings import EmbeddingProvider
from app.application.ports.repositories import DocumentRepositoryPort

_DEFAULT_LIMIT = 5
_MIN_LIMIT = 1
_MAX_LIMIT = 10

# A factory returns a fresh async context manager per call whose enter yields a
# DocumentRepositoryPort. Streaming builds one that opens a short tenant session;
# non-streaming builds one that yields the already-bound repo. Mirrors
# MemoryRepoFactory so both tools share the 6c/6d/6k session discipline.
DocumentRepoFactory = Callable[[], AbstractAsyncContextManager[DocumentRepositoryPort]]


def _bound_repo_factory(repo: DocumentRepositoryPort) -> DocumentRepoFactory:
    """Wrap a pre-bound repo into a factory that yields it verbatim per call, so
    run() has one code path regardless of caller."""

    @asynccontextmanager
    async def _factory() -> AsyncIterator[DocumentRepositoryPort]:
        yield repo

    return _factory


class SearchDocumentsTool:
    def __init__(
        self,
        *,
        embedding_provider: EmbeddingProvider,
        organization_id: UUID,
        document_repo: DocumentRepositoryPort | None = None,
        document_repo_factory: DocumentRepoFactory | None = None,
    ) -> None:
        if (document_repo is None) == (document_repo_factory is None):
            raise ValueError(
                "SearchDocumentsTool: provide exactly one of document_repo / document_repo_factory"
            )
        self._factory: DocumentRepoFactory = (
            document_repo_factory
            if document_repo_factory is not None
            else _bound_repo_factory(document_repo)  # type: ignore[arg-type]
        )
        self._embed = embedding_provider
        self._org_id = organization_id
        # NOTE: intentionally NO user_id — see run().

    @property
    def name(self) -> str:
        return "search_documents"

    @property
    def description(self) -> str:
        return (
            "Search the organization's uploaded documents for passages relevant "
            "to a question. Returns excerpts with citations (source filename plus "
            "page or section) that you should quote when answering."
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

        # Embed as a QUERY and pass the provider's REPORTED model into the search
        # (5d guard): only chunks embedded by the same model are scored, so a
        # model swap can't silently mix vector spaces.
        result = await self._embed.embed(texts=[query], input_type="query")
        async with self._factory() as repo:
            # ⚠️ TENANT-SCOPED, NOT user-scoped — DELIBERATE. Documents belong to
            # the ORGANISATION: any member may find any document the org ingested.
            # This differs from search_memory, which is per-user (memories carry a
            # user_id and an ownership guard). Do NOT "fix" this into a user filter
            # by pattern-matching search_memory — that would break the point of an
            # enterprise document platform.
            hits = await repo.search_chunks(
                organization_id=self._org_id,
                query_embedding=result.vectors[0],
                limit=limit,
                embedding_model=result.model,
            )
        if not hits:
            return "No relevant documents found."
        return "\n".join(self._format(chunk, sim) for chunk, sim in hits)

    @staticmethod
    def _format(chunk: Any, similarity: float) -> str:
        # Rebuild the position from the STORED provenance columns and render it
        # with the canonical 8a renderer — never re-derive page/section logic
        # here, or a second implementation will drift from DocumentPosition.
        position = DocumentPosition(
            char_start=chunk.char_start,
            char_end=chunk.char_end,
            page_start=chunk.page_start,
            page_end=chunk.page_end,
            section=chunk.section,
            # ADR 0004: OCR-derived docs render "(OCR)" in the citation.
            is_ocr=chunk.document.extraction_method == "ocr",
        )
        excerpt = " ".join(chunk.text.split())
        return (
            f"- {chunk.document.filename} ({position.render()}): "
            f"{excerpt}  (similarity {similarity:.2f})"
        )
