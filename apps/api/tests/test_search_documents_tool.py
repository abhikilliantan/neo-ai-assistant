"""Phase 8d — SearchDocumentsTool + read-only classification + e2e tool loop.

The load-bearing properties:
  - CITATIONS: a result string carries the source filename AND the canonical
    DocumentPosition.render() string, asserted on a BOUNDARY-SPANNING chunk
    (pp. N-M) — the case the whole provenance design exists for.
  - SCOPE: tenant-only. Tenant B can't see tenant A's docs; a DIFFERENT user in
    the SAME org CAN find a colleague's doc (the deliberate difference from
    search_memory).
  - embedding_model guard, soft-delete exclusion, empty-state string.
  - The DEFAULT agent gets search_documents (read-only); a narrow agent doesn't.
  - End-to-end through the real tool loop on BOTH endpoints (scripted provider).
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.documents.chunker import FixedSizeChunker
from app.ai.documents.ingest import DocumentIngestService
from app.ai.documents.mock import MockDocumentParser
from app.ai.providers.embeddings.mock import MockEmbeddingProvider
from app.ai.tools.search_documents import SearchDocumentsTool
from app.application.ports.chat import (
    ChatCompletion,
    ChatMessage,
    ChatStreamEvent,
    ToolExecutor,
)
from app.application.ports.documents import DocumentPosition
from app.application.ports.tools import ToolCall
from app.infrastructure.db.models import DocumentChunk, Membership, Role
from app.infrastructure.db.repositories import DocumentRepository

_MODEL = "mock-embed-1"
_PDF = "application/pdf"


# --- helpers -----------------------------------------------------------------


async def _register(client: AsyncClient, email: str) -> dict[str, Any]:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password12345"},
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def _auth(reg: dict[str, Any]) -> dict[str, str]:
    return {"Authorization": f"Bearer {reg['access_token']}"}


def _ingest_service(chunk_size: int = 100) -> DocumentIngestService:
    return DocumentIngestService(
        parser=MockDocumentParser(max_bytes=1_000_000),
        chunker=FixedSizeChunker(chunk_size=chunk_size, overlap=0),
        embedding_provider=MockEmbeddingProvider(),
        chunk_size=chunk_size,
        embedding_model="voyage-3.5",
    )


async def _ingest(
    app_session_factory: Any,
    *,
    tenant: UUID,
    user: UUID,
    filename: str,
    chunk_size: int = 100,
) -> UUID:
    s = await app_session_factory(tenant)
    try:
        doc = await _ingest_service(chunk_size).ingest(
            s,
            organization_id=tenant,
            uploaded_by_user_id=user,
            filename=filename,
            content_type=_PDF,
            data=b"anything",
        )
        await s.commit()
        return doc.id
    finally:
        await s.close()


async def _make_second_user_in_org(
    client: AsyncClient,
    db_session: AsyncSession,
    *,
    email: str,
    organization_id: UUID,
) -> dict[str, Any]:
    """Register a second user, move them into `organization_id`, and log in so
    their token's active tenant is the shared org (mirrors test_memories_api)."""
    reg = await _register(client, email)
    user_id = UUID(reg["user_id"])
    role = (await db_session.execute(select(Role).where(Role.name == "owner"))).scalar_one()
    db_session.add(
        Membership(
            user_id=user_id,
            organization_id=organization_id,
            role_id=role.id,
            status="active",
            created_at=datetime.now(UTC),
        )
    )
    await db_session.commit()
    stmt = (
        select(Membership)
        .where(Membership.user_id == user_id)
        .where(Membership.organization_id != organization_id)
    )
    for m in (await db_session.execute(stmt)).scalars().all():
        await db_session.delete(m)
    await db_session.commit()
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": "password12345"},
    )
    assert login.status_code == 200, login.text
    return login.json()  # type: ignore[no-any-return]


def _sse_delta_text(body: str) -> str:
    """Join the content of all `delta` frames in an SSE body."""
    out = []
    for block in body.split("\n\n"):
        for line in block.strip().split("\n"):
            if line.startswith("data:"):
                frame = json.loads(line[len("data:") :].strip())
                if frame.get("type") == "delta":
                    out.append(frame.get("content", ""))
    return "".join(out)


# --- citation: filename + boundary-spanning position -------------------------


@pytest.mark.asyncio
async def test_result_cites_filename_and_boundary_spanning_position(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "8d-cite@example.com")
    tenant = UUID(reg["active_tenant_id"])
    user = UUID(reg["user_id"])
    doc_id = await _ingest(app_session_factory, tenant=tenant, user=user, filename="paper.pdf")

    s = await app_session_factory(tenant)
    try:
        chunks = await DocumentRepository(s).list_chunks(doc_id)
        # A boundary-spanning chunk straddles two pages → render() gives "pp. N-M".
        boundary = next(c for c in chunks if c.page_start != c.page_end)
        expected = DocumentPosition(
            char_start=boundary.char_start,
            char_end=boundary.char_end,
            page_start=boundary.page_start,
            page_end=boundary.page_end,
            section=boundary.section,
        ).render()
        assert expected.startswith("pp. ")  # this is the case citations exist for

        tool = SearchDocumentsTool(
            document_repo=DocumentRepository(s),
            embedding_provider=MockEmbeddingProvider(),
            organization_id=tenant,
        )
        # Query = the boundary chunk's own text → it ranks first.
        out = await tool.run({"query": boundary.text})
        top_line = out.splitlines()[0]
        assert "paper.pdf" in top_line
        assert expected in top_line  # rendered position matches DocumentPosition.render()
    finally:
        await s.close()


# --- empty state + limit clamp -----------------------------------------------


@pytest.mark.asyncio
async def test_empty_corpus_returns_clear_string(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "8d-empty@example.com")
    tenant = UUID(reg["active_tenant_id"])
    s = await app_session_factory(tenant)
    try:
        tool = SearchDocumentsTool(
            document_repo=DocumentRepository(s),
            embedding_provider=MockEmbeddingProvider(),
            organization_id=tenant,
        )
        assert await tool.run({"query": "anything"}) == "No relevant documents found."
    finally:
        await s.close()


@pytest.mark.asyncio
async def test_limit_is_clamped() -> None:
    class _SpyRepo:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        async def search_chunks(self, **kw: Any) -> list[tuple[Any, float]]:
            self.calls.append(kw)
            return []

    spy = _SpyRepo()
    tool = SearchDocumentsTool(
        document_repo=spy,  # type: ignore[arg-type]
        embedding_provider=MockEmbeddingProvider(),
        organization_id=uuid4(),
    )
    await tool.run({"query": "q", "limit": 50})
    assert spy.calls[-1]["limit"] == 10
    await tool.run({"query": "q", "limit": 0})
    assert spy.calls[-1]["limit"] == 1
    await tool.run({"query": "q"})
    assert spy.calls[-1]["limit"] == 5
    # 5d guard: the provider's reported model is passed through.
    assert spy.calls[-1]["embedding_model"] == _MODEL


# --- embedding_model guard ---------------------------------------------------


@pytest.mark.asyncio
async def test_foreign_model_chunk_excluded_even_when_vector_matches(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
    db_session: AsyncSession,
) -> None:
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "8d-modelguard@example.com")
    tenant = UUID(reg["active_tenant_id"])
    user = UUID(reg["user_id"])
    doc_id = await _ingest(
        app_session_factory, tenant=tenant, user=user, filename="real.pdf", chunk_size=1000
    )

    query_vec = (await MockEmbeddingProvider().embed(texts=["anything"])).vectors[0]
    # Plant a foreign-model chunk whose vector == the query (would rank #1).
    db_session.add(
        DocumentChunk(
            document_id=doc_id,
            organization_id=tenant,
            ordinal=999,
            text="POISON foreign vector-space row",
            embedding=query_vec,
            embedding_model="foreign-model-1",
            char_start=0,
            char_end=1,
        )
    )
    await db_session.commit()

    s = await app_session_factory(tenant)
    try:
        tool = SearchDocumentsTool(
            document_repo=DocumentRepository(s),
            embedding_provider=MockEmbeddingProvider(),
            organization_id=tenant,
        )
        out = await tool.run({"query": "anything"})
        assert "POISON" not in out  # foreign-model row filtered by the 5d guard
        assert "real.pdf" in out
    finally:
        await s.close()


# --- soft delete -------------------------------------------------------------


@pytest.mark.asyncio
async def test_soft_deleted_document_absent_from_results(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "8d-softdel@example.com")
    tenant = UUID(reg["active_tenant_id"])
    user = UUID(reg["user_id"])
    doc_id = await _ingest(
        app_session_factory, tenant=tenant, user=user, filename="gone.pdf", chunk_size=1000
    )
    s = await app_session_factory(tenant)
    try:
        repo = DocumentRepository(s)
        tool = SearchDocumentsTool(
            document_repo=repo,
            embedding_provider=MockEmbeddingProvider(),
            organization_id=tenant,
        )
        assert "gone.pdf" in await tool.run({"query": "anything"})
        await repo.soft_delete(doc_id)
        assert await tool.run({"query": "anything"}) == "No relevant documents found."
    finally:
        await s.close()


# --- scripted providers for the e2e tool loop --------------------------------


class _DocSearchingProvider:
    """Invokes search_documents once and folds its result into the answer, on
    both the complete and stream paths — a deterministic stand-in for a model."""

    def __init__(self) -> None:
        self.tools_seen: list[list[dict[str, Any]] | None] = []

    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_executor: ToolExecutor | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> ChatCompletion:
        self.tools_seen.append(tools)
        assert tool_executor is not None
        result = await tool_executor(
            ToolCall(id="call_D", name="search_documents", arguments={"query": "anything"})
        )
        return ChatCompletion(
            content=f"from the docs: {result.content}",
            model="scripted-doc",
            usage=None,
            finish_reason="stop",
        )

    async def stream(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_executor: ToolExecutor | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[ChatStreamEvent]:
        self.tools_seen.append(tools)
        assert tool_executor is not None
        result = await tool_executor(
            ToolCall(id="call_D", name="search_documents", arguments={"query": "anything"})
        )
        text = f"from the docs: {result.content}"
        for i, word in enumerate(text.split(" ")):
            yield ChatStreamEvent(type="delta", content=word if i == 0 else " " + word)
        yield ChatStreamEvent(type="done", model="scripted-doc", finish_reason="stop")


class _ToolRecordingProvider:
    """Records the tools offered without invoking the executor — for asserting
    which tools an agent exposes."""

    def __init__(self) -> None:
        self.tools_seen: list[list[dict[str, Any]] | None] = []

    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_executor: ToolExecutor | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> ChatCompletion:
        self.tools_seen.append(tools)
        return ChatCompletion(content="ok", model="spy", usage=None, finish_reason="stop")

    async def stream(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_executor: ToolExecutor | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[ChatStreamEvent]:
        self.tools_seen.append(tools)
        yield ChatStreamEvent(type="done", model="spy", finish_reason="stop")


# --- e2e on BOTH endpoints ---------------------------------------------------


@pytest.mark.asyncio
async def test_e2e_chat_folds_document_search_and_stays_ephemeral(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    scripted = _DocSearchingProvider()
    db_app.state.chat_provider = scripted

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "8d-e2e-chat@example.com")
        tenant = UUID(reg["active_tenant_id"])
        user = UUID(reg["user_id"])
        await _ingest(app_session_factory, tenant=tenant, user=user, filename="handbook.pdf")

        r = await c.post(
            "/api/v1/chat",
            headers=_auth(reg),
            json={"messages": [{"role": "user", "content": "what's in the docs?"}]},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "handbook.pdf" in body["message"]["content"]  # citation folded in

        # Ephemeral invariant: only [user, assistant] persist.
        conv_id = body["conversation_id"]
        detail = await c.get(f"/api/v1/conversations/{conv_id}", headers=_auth(reg))
        assert [m["role"] for m in detail.json()["messages"]] == ["user", "assistant"]

    assert {s["name"] for s in scripted.tools_seen[-1]} >= {"search_documents"}


@pytest.mark.asyncio
async def test_e2e_stream_folds_document_search(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    scripted = _DocSearchingProvider()
    db_app.state.chat_provider = scripted

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "8d-e2e-stream@example.com")
        tenant = UUID(reg["active_tenant_id"])
        user = UUID(reg["user_id"])
        await _ingest(app_session_factory, tenant=tenant, user=user, filename="stream-doc.pdf")

        r = await c.post(
            "/api/v1/chat/stream",
            headers=_auth(reg),
            json={"messages": [{"role": "user", "content": "search the docs"}]},
        )
        assert r.status_code == 200, r.text
        # The tool ran mid-stream via the SHORT-per-call factory (6d discipline:
        # no session held across the provider stream) and its citation folded in.
        assert "stream-doc.pdf" in _sse_delta_text(r.text)

    assert {s["name"] for s in scripted.tools_seen[-1]} >= {"search_documents"}


# --- tenant scoping (through HTTP) -------------------------------------------


@pytest.mark.asyncio
async def test_tenant_B_cannot_retrieve_tenant_A_documents(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    scripted = _DocSearchingProvider()
    db_app.state.chat_provider = scripted

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        alice = await _register(c, "8d-tenantA@example.com")
        a_tenant = UUID(alice["active_tenant_id"])
        a_user = UUID(alice["user_id"])
        await _ingest(
            app_session_factory, tenant=a_tenant, user=a_user, filename="alice-secret.pdf"
        )

        bob = await _register(c, "8d-tenantB@example.com")
        r = await c.post(
            "/api/v1/chat",
            headers=_auth(bob),
            json={"messages": [{"role": "user", "content": "find alice's file"}]},
        )
        assert r.status_code == 200, r.text
        content = r.json()["message"]["content"]
        assert "alice-secret.pdf" not in content  # RLS-scoped: B never sees A's docs
        assert "No relevant documents found." in content


# --- cross-user WITHIN a tenant (the deliberate diff from search_memory) -----


@pytest.mark.asyncio
async def test_colleague_in_same_org_can_find_the_document(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
    db_session: AsyncSession,
) -> None:
    scripted = _DocSearchingProvider()
    db_app.state.chat_provider = scripted

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        alice = await _register(c, "8d-org-alice@example.com")
        org = UUID(alice["active_tenant_id"])
        a_user = UUID(alice["user_id"])
        await _ingest(app_session_factory, tenant=org, user=a_user, filename="shared-policy.pdf")

        # A DIFFERENT user in the SAME org.
        bob = await _make_second_user_in_org(
            c, db_session, email="8d-org-bob@example.com", organization_id=org
        )
        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {bob['access_token']}"},
            json={"messages": [{"role": "user", "content": "what's the policy?"}]},
        )
        assert r.status_code == 200, r.text
        # Unlike search_memory (per-user), documents are org-scoped: the colleague
        # finds the file their teammate uploaded.
        assert "shared-policy.pdf" in r.json()["message"]["content"]


# --- read-only classification: default HAS it, narrow agent doesn't ----------


@pytest.mark.asyncio
async def test_default_agent_offers_search_documents_both_endpoints(
    db_app,  # type: ignore[no-untyped-def]
) -> None:
    spy = _ToolRecordingProvider()
    db_app.state.chat_provider = spy
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "8d-default-agent@example.com")
        for path in ("/api/v1/chat", "/api/v1/chat/stream"):
            r = await c.post(
                path,
                headers=_auth(reg),
                json={"messages": [{"role": "user", "content": "hi"}]},
            )
            assert r.status_code == 200, r.text
    # Both endpoints offered search_documents to the default agent.
    assert len(spy.tools_seen) == 2
    for seen in spy.tools_seen:
        assert "search_documents" in {s["name"] for s in (seen or [])}


@pytest.mark.asyncio
async def test_narrow_agent_excludes_search_documents(
    db_app,  # type: ignore[no-untyped-def]
) -> None:
    """6g filtering intact: the 'recall' agent's tool_names is [search_memory],
    so search_documents must NOT be offered to it."""
    spy = _ToolRecordingProvider()
    db_app.state.chat_provider = spy
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "8d-narrow-agent@example.com")
        r = await c.post(
            "/api/v1/chat",
            headers=_auth(reg),
            json={"messages": [{"role": "user", "content": "hi"}], "agent": "recall"},
        )
        assert r.status_code == 200, r.text
    names = {s["name"] for s in (spy.tools_seen[-1] or [])}
    assert names == {"search_memory"}
    assert "search_documents" not in names
