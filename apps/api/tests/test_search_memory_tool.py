"""Phase 6c — SearchMemoryTool + request-scoped registry.

Covers:
  - Repository: `search_similar(embedding_model=...)` filters by exact model
    tag, closing the 5d mixed-vector-space pollution hole (backward-compatible
    default when omitted).
  - SearchMemoryTool.run: seeded memories are surfaced with similarity;
    empty state has the locked string; limit is clamped to [1, 10].
  - Request registry: `build_request_tool_registry` exposes both `echo` and
    `search_memory`; execute(search_memory) → non-error ToolResult; the
    6b best-effort execute contract still shields raising tools into
    is_error=True results.
  - End-to-end via a scripted provider double: `/chat` builds a per-request
    registry, the provider requests search_memory via tool_executor, the
    real tool runs against the seeded row, and only [user, assistant] are
    persisted — the ephemeral guarantee still holds.
  - tools_enabled=False still overrides the request registry (kill switch).
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.ai.providers.embeddings.mock import MockEmbeddingProvider
from app.ai.tools import build_request_tool_registry
from app.ai.tools.search_memory import SearchMemoryTool
from app.application.ports.chat import (
    ChatCompletion,
    ChatMessage,
    ChatStreamEvent,
    ToolExecutor,
)
from app.application.ports.tools import ToolCall
from app.infrastructure.db.repositories import MemoryRepository

# --- helpers -----------------------------------------------------------------


async def _register(client: AsyncClient, email: str) -> dict[str, Any]:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password12345"},
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


async def _seed_memory(
    app_session_factory,  # type: ignore[no-untyped-def]
    *,
    tenant_id: UUID,
    user_id: UUID,
    content: str,
    embedding_model_override: str | None = None,
    provider: MockEmbeddingProvider | None = None,
) -> UUID:
    """Insert one memory (with mock embedding of `content`) under the caller's
    tenant/user, then commit. `embedding_model_override` lets a test seed rows
    tagged with a non-default model to exercise the 6c filter guard.
    """
    p = provider or MockEmbeddingProvider()
    result = await p.embed(texts=[content])
    s = await app_session_factory(tenant_id)
    try:
        m = await MemoryRepository(s).add(
            organization_id=tenant_id,
            user_id=user_id,
            content=content,
            embedding=result.vectors[0],
            embedding_model=embedding_model_override or result.model,
        )
        await s.commit()
        return m.id
    finally:
        await s.close()


# --- Repository: embedding_model filter guard --------------------------------


@pytest.mark.asyncio
async def test_search_similar_embedding_model_filter_excludes_other_models(
    db_app,  # type: ignore[no-untyped-def]  # ensures app is available for register
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """Seed two rows under the same user, one tagged mock-embed-1 (default)
    and one tagged an alternate model. Search with embedding_model="mock-embed-1"
    must return only the matching-model row — the 5d mixed-vector-space guard.
    """
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "6c-filter@example.com")
        tenant = UUID(reg["active_tenant_id"])
        user_id = UUID(reg["user_id"])

        matching_id = await _seed_memory(
            app_session_factory, tenant_id=tenant, user_id=user_id, content="same thing"
        )
        # Same content → identical mock vector; only the tag differs.
        await _seed_memory(
            app_session_factory,
            tenant_id=tenant,
            user_id=user_id,
            content="same thing",
            embedding_model_override="voyage-3.5",
        )

    s = await app_session_factory(tenant)
    try:
        embed = MockEmbeddingProvider()
        result = await embed.embed(texts=["same thing"], input_type="query")
        hits = await MemoryRepository(s).search_similar(
            organization_id=tenant,
            user_id=user_id,
            query_embedding=result.vectors[0],
            limit=10,
            embedding_model="mock-embed-1",
        )
        got_ids = [m.id for m, _ in hits]
        assert got_ids == [matching_id]

        # No filter → both rows return (backward-compat default).
        hits_no_filter = await MemoryRepository(s).search_similar(
            organization_id=tenant,
            user_id=user_id,
            query_embedding=result.vectors[0],
            limit=10,
        )
        assert len(hits_no_filter) == 2
    finally:
        await s.close()


# --- SearchMemoryTool.run ----------------------------------------------------


@pytest.mark.asyncio
async def test_search_memory_tool_returns_hits_with_similarity(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "6c-tool-hits@example.com")
        tenant = UUID(reg["active_tenant_id"])
        user_id = UUID(reg["user_id"])
        await _seed_memory(
            app_session_factory, tenant_id=tenant, user_id=user_id, content="user_fact: I like tea"
        )
        await _seed_memory(
            app_session_factory,
            tenant_id=tenant,
            user_id=user_id,
            content="user_fact: I dislike coffee",
        )

    s = await app_session_factory(tenant)
    try:
        tool = SearchMemoryTool(
            memory_repo=MemoryRepository(s),
            embedding_provider=MockEmbeddingProvider(),
            organization_id=tenant,
            user_id=user_id,
        )
        out = await tool.run({"query": "user_fact: I like tea"})
        assert "I like tea" in out
        assert "(similarity 1.00)" in out
    finally:
        await s.close()


@pytest.mark.asyncio
async def test_search_memory_tool_empty_state(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "6c-tool-empty@example.com")
        tenant = UUID(reg["active_tenant_id"])
        user_id = UUID(reg["user_id"])

    s = await app_session_factory(tenant)
    try:
        tool = SearchMemoryTool(
            memory_repo=MemoryRepository(s),
            embedding_provider=MockEmbeddingProvider(),
            organization_id=tenant,
            user_id=user_id,
        )
        out = await tool.run({"query": "anything"})
        assert out == "No relevant memories found."
    finally:
        await s.close()


@pytest.mark.asyncio
async def test_search_memory_tool_clamps_limit(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """Request limit=20 → clamped to 10; request limit=0 → clamped to 1.
    Verified by spying on the repo's `search_similar` call.
    """

    class _SpyRepo:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        async def search_similar(self, **kw: Any) -> list[tuple[Any, float]]:
            self.calls.append(kw)
            return []

    spy = _SpyRepo()

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "6c-tool-clamp@example.com")
        tenant = UUID(reg["active_tenant_id"])
        user_id = UUID(reg["user_id"])

    tool = SearchMemoryTool(
        memory_repo=spy,  # type: ignore[arg-type]
        embedding_provider=MockEmbeddingProvider(),
        organization_id=tenant,
        user_id=user_id,
    )
    await tool.run({"query": "q", "limit": 20})
    assert spy.calls[-1]["limit"] == 10
    await tool.run({"query": "q", "limit": 0})
    assert spy.calls[-1]["limit"] == 1
    await tool.run({"query": "q"})  # default
    assert spy.calls[-1]["limit"] == 5


# --- Request registry --------------------------------------------------------


@pytest.mark.asyncio
async def test_request_registry_registers_echo_and_search_memory(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "6c-registry@example.com")
        tenant = UUID(reg["active_tenant_id"])
        user_id = UUID(reg["user_id"])
        await _seed_memory(
            app_session_factory, tenant_id=tenant, user_id=user_id, content="hello world"
        )

    s = await app_session_factory(tenant)
    try:
        registry = build_request_tool_registry(
            settings=db_app.state.settings,
            memory_repo=MemoryRepository(s),
            embedding_provider=MockEmbeddingProvider(),
            organization_id=tenant,
            user_id=user_id,
        )
        names = [spec["name"] for spec in registry.specs()]
        assert set(names) == {"echo", "search_memory"}

        result = await registry.execute(
            ToolCall(id="c1", name="search_memory", arguments={"query": "hello world"})
        )
        assert result.is_error is False
        assert "hello world" in result.content
    finally:
        await s.close()


# --- End-to-end via a scripted provider double ------------------------------


class _MemorySearchingProvider:
    """Scripted provider that, when given a tool_executor, invokes
    search_memory once and folds the result content into a final answer.

    Mirrors what a real model does with tool-use, but deterministically —
    no live LLM in CI.
    """

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
            ToolCall(id="call_S", name="search_memory", arguments={"query": "user_fact: my name"})
        )
        return ChatCompletion(
            content=f"you told me: {result.content}",
            model="scripted-mem",
            usage=None,
            finish_reason="stop",
        )

    async def stream(
        self,
        *,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[ChatStreamEvent]:
        yield ChatStreamEvent(type="done", model="scripted-mem", finish_reason="stop")


@pytest.mark.asyncio
async def test_chat_e2e_search_memory_surfaces_content_and_stays_ephemeral(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    scripted = _MemorySearchingProvider()
    db_app.state.chat_provider = scripted

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "6c-e2e@example.com")
        token = reg["access_token"]
        tenant = UUID(reg["active_tenant_id"])
        user_id = UUID(reg["user_id"])
        # Seed the memory the scripted provider will query for.
        await _seed_memory(
            app_session_factory,
            tenant_id=tenant,
            user_id=user_id,
            content="user_fact: my name is Priya",
        )

        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "what's my name?"}]},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # The seeded memory content came through the tool → into final text.
        assert "Priya" in body["message"]["content"]
        conv_id = body["conversation_id"]

        # Ephemeral guarantee: only [user, assistant]. No tool_use / tool_result
        # rows. Same posture as 5d's ephemeral memory injection and the 6b
        # e2e proof.
        detail = await c.get(
            f"/api/v1/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail.status_code == 200
        msgs = detail.json()["messages"]
        assert [m["role"] for m in msgs] == ["user", "assistant"]
        assert msgs[0]["content"] == "what's my name?"
        assert "Priya" in msgs[1]["content"]

    # Endpoint offered the read-only tools. 7d: the default agent no longer
    # gets create_task (workflows require the operator agent). 8d: search_documents
    # is read-only, so the default agent DOES get it.
    assert scripted.tools_seen
    assert scripted.tools_seen[-1] is not None
    assert {s["name"] for s in scripted.tools_seen[-1]} == {
        "echo",
        "search_memory",
        "search_documents",
    }


# --- tools_enabled=False still overrides the request registry ---------------


class _SpyProvider:
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
        return ChatCompletion(
            content="(spy) hi",
            model="spy-6c",
            usage=None,
            finish_reason="stop",
        )

    async def stream(
        self,
        *,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[ChatStreamEvent]:
        yield ChatStreamEvent(type="done", model="spy-6c", finish_reason="stop")


@pytest.mark.asyncio
async def test_tools_enabled_false_bypasses_request_registry(
    db_app,  # type: ignore[no-untyped-def]
) -> None:
    spy = _SpyProvider()
    db_app.state.chat_provider = spy
    db_app.state.settings = db_app.state.settings.model_copy(update={"tools_enabled": False})

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "6c-tools-off@example.com")
        token = reg["access_token"]
        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 200

    assert spy.tools_seen == [None]
