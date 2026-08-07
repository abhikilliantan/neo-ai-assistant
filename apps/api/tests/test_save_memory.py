"""save_memory feature — write helper, tool, REST endpoint, and the
end-to-end acceptance ("remember to call me Boss").

Layers:
  - unit: `save_memory_deduped` create + near-dupe skip; `clamp_kind`.
  - tool: `SaveMemoryTool.run` writes a row; a second identical call dedupes.
  - API: POST happy-path, POST dedupe idempotency, and tenant isolation
    (tenant B never sees tenant A's memory).
  - acceptance: a /chat turn where the model calls save_memory persists a row;
    a later turn's retrieval injects it and the agent addresses the user by it.

Embeddings are the deterministic MockEmbeddingProvider (identical text →
identical vector → cosine 1.0), so dedupe (>= 0.95) is exercised for real.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.ai.memory.write import clamp_kind, save_memory_deduped
from app.ai.providers.embeddings.mock import MockEmbeddingProvider
from app.ai.tools.save_memory import SaveMemoryTool
from app.application.ports.chat import ChatCompletion, ChatMessage, ChatStreamEvent, ToolExecutor
from app.application.ports.tools import ToolCall
from app.infrastructure.db.models import Memory
from app.infrastructure.db.repositories import MemoryRepository

_THRESHOLD = 0.95


async def _register(client: AsyncClient, email: str) -> dict[str, Any]:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password12345"},
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# --- unit: clamp_kind --------------------------------------------------------


def test_clamp_kind_maps_unknown_to_other_and_none_to_fact() -> None:
    assert clamp_kind(None) == "fact"
    assert clamp_kind("preference") == "preference"
    assert clamp_kind("INSTRUCTION") == "instruction"  # normalised
    assert clamp_kind("nonsense") == "other"


# --- unit: save_memory_deduped ----------------------------------------------


@pytest.mark.asyncio
async def test_save_memory_deduped_creates_then_skips_near_duplicate(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "save-dedupe@example.com")
    tenant = UUID(reg["active_tenant_id"])
    user_id = UUID(reg["user_id"])
    embed = MockEmbeddingProvider()

    s = await app_session_factory(tenant)
    try:
        repo = MemoryRepository(s)
        first, created1 = await save_memory_deduped(
            repo=repo,
            embedding_provider=embed,
            organization_id=tenant,
            user_id=user_id,
            content="The user prefers to be called Boss.",
            dedupe_threshold=_THRESHOLD,
            kind="preference",
            source="user",
        )
        assert created1 is True
        assert first.kind == "preference"
        # Identical content → identical mock vector → cosine 1.0 → dedup.
        second, created2 = await save_memory_deduped(
            repo=repo,
            embedding_provider=embed,
            organization_id=tenant,
            user_id=user_id,
            content="The user prefers to be called Boss.",
            dedupe_threshold=_THRESHOLD,
            kind="preference",
            source="user",
        )
        assert created2 is False
        assert second.id == first.id
        # A genuinely different fact still stores.
        _third, created3 = await save_memory_deduped(
            repo=repo,
            embedding_provider=embed,
            organization_id=tenant,
            user_id=user_id,
            content="The user works in the Nairobi office.",
            dedupe_threshold=_THRESHOLD,
            kind="fact",
            source="user",
        )
        assert created3 is True
        await s.commit()
    finally:
        await s.close()


# --- tool: SaveMemoryTool.run -----------------------------------------------


@pytest.mark.asyncio
async def test_save_memory_tool_writes_and_dedupes(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "save-tool@example.com")
    tenant = UUID(reg["active_tenant_id"])
    user_id = UUID(reg["user_id"])

    s = await app_session_factory(tenant)
    try:
        tool = SaveMemoryTool(
            memory_repo=MemoryRepository(s),
            embedding_provider=MockEmbeddingProvider(),
            organization_id=tenant,
            user_id=user_id,
            dedupe_threshold=_THRESHOLD,
        )
        out1 = await tool.run({"content": "Deploys go out on Fridays.", "kind": "instruction"})
        assert "Saved to memory" in out1
        out2 = await tool.run({"content": "Deploys go out on Fridays.", "kind": "instruction"})
        assert "Already remembered" in out2
        await s.commit()
    finally:
        await s.close()

    # Read in a FRESH session: the write session's transaction-local
    # app.current_tenant GUC resets after commit, so querying the same session
    # post-commit would 500 on the RLS ::uuid cast (the 8b landmine).
    s2 = await app_session_factory(tenant)
    try:
        rows = await MemoryRepository(s2).list_for_user(organization_id=tenant, user_id=user_id)
        matching = [m for m in rows if "Fridays" in m.content]
        assert len(matching) == 1  # dedupe kept it to one
        assert matching[0].kind == "instruction"
        assert matching[0].source == "agent"  # tool-initiated provenance
    finally:
        await s2.close()


# --- API: POST happy-path + dedupe + DELETE ---------------------------------


@pytest.mark.asyncio
async def test_post_memory_creates_lists_and_deletes(db_app) -> None:  # type: ignore[no-untyped-def]
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "save-api@example.com")
        token = reg["access_token"]

        r = await c.post(
            "/api/v1/memories",
            json={"content": "Invoices are approved by Finance.", "kind": "fact"},
            headers=_auth(token),
        )
        assert r.status_code == 201, r.text
        created = r.json()
        assert created["content"] == "Invoices are approved by Finance."
        assert created["kind"] == "fact"
        assert created["source"] == "user"
        mem_id = created["id"]

        # POST an equivalent memory → dedupe returns the SAME row (idempotent).
        r2 = await c.post(
            "/api/v1/memories",
            json={"content": "Invoices are approved by Finance."},
            headers=_auth(token),
        )
        assert r2.status_code == 201
        assert r2.json()["id"] == mem_id

        listed = (await c.get("/api/v1/memories", headers=_auth(token))).json()
        assert [m["id"] for m in listed].count(mem_id) == 1

        d = await c.delete(f"/api/v1/memories/{mem_id}", headers=_auth(token))
        assert d.status_code == 204
        after = (await c.get("/api/v1/memories", headers=_auth(token))).json()
        assert mem_id not in [m["id"] for m in after]


@pytest.mark.asyncio
async def test_post_memory_rejects_empty_content(db_app) -> None:  # type: ignore[no-untyped-def]
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "save-empty@example.com")
        r = await c.post(
            "/api/v1/memories", json={"content": ""}, headers=_auth(reg["access_token"])
        )
        assert r.status_code == 422  # Field(min_length=1)


# --- API: tenant isolation ---------------------------------------------------


@pytest.mark.asyncio
async def test_memory_created_in_tenant_a_invisible_to_tenant_b(db_app) -> None:  # type: ignore[no-untyped-def]
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        a = await _register(c, "save-iso-a@example.com")
        b = await _register(c, "save-iso-b@example.com")  # different personal org

        r = await c.post(
            "/api/v1/memories",
            json={"content": "Tenant A secret: launch is May 1.", "kind": "fact"},
            headers=_auth(a["access_token"]),
        )
        assert r.status_code == 201
        a_mem_id = r.json()["id"]

        # B lists → never sees A's memory (RLS + user scope).
        b_list = (await c.get("/api/v1/memories", headers=_auth(b["access_token"]))).json()
        assert a_mem_id not in [m["id"] for m in b_list]

        # B cannot delete A's memory (cross-tenant → 404, no oracle).
        d = await c.delete(f"/api/v1/memories/{a_mem_id}", headers=_auth(b["access_token"]))
        assert d.status_code == 404
        assert d.json()["error"]["code"] == "not_found"


# --- acceptance: "remember to call me Boss" ---------------------------------


class _RememberThenGreetProvider:
    """Scripted chat provider (no live LLM in CI).

    Turn 1 (user says "remember…"): invokes save_memory via the tool_executor,
    then confirms. Later turns: reads the memory-context system message the
    retrieval step injected and greets the user by the remembered name.
    """

    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_executor: ToolExecutor | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> ChatCompletion:
        last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
        if "remember" in last_user.lower():
            assert tool_executor is not None, "save_memory must be offered to the agent"
            names = [t["name"] for t in (tools or [])]
            assert "save_memory" in names, f"save_memory not offered; got {names}"
            res = await tool_executor(
                ToolCall(
                    id="s1",
                    name="save_memory",
                    arguments={
                        "content": "The user prefers to be called Boss.",
                        "kind": "preference",
                    },
                )
            )
            assert not res.is_error, res.content
            return ChatCompletion(
                content="Got it — I'll call you Boss.",
                model="scripted",
                usage=None,
                finish_reason="stop",
            )
        # Later turn: address from the injected memory context.
        ctx = " ".join(m.content for m in messages if m.role == "system")
        name = "Boss" if "Boss" in ctx else "there"
        return ChatCompletion(
            content=f"Sure, {name}. What can I do?",
            model="scripted",
            usage=None,
            finish_reason="stop",
        )

    async def stream(
        self, *, messages: list[ChatMessage], model: str | None = None, temperature: float = 0.7
    ) -> AsyncIterator[ChatStreamEvent]:
        raise NotImplementedError  # non-streaming /chat only
        yield  # pragma: no cover


@pytest.mark.asyncio
async def test_acceptance_remember_call_me_boss(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    # Script the provider; force retrieval to inject regardless of mock-embedding
    # similarity so the end-to-end wiring (save → persist → retrieve → use) is
    # deterministic.
    db_app.state.chat_provider = _RememberThenGreetProvider()
    db_app.state.settings.memory_retrieval_min_similarity = -1.0

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "boss@example.com")
        token = reg["access_token"]
        tenant = UUID(reg["active_tenant_id"])
        user_id = UUID(reg["user_id"])

        # Turn 1: the model calls save_memory.
        r1 = await c.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "Please remember to call me Boss."}]},
            headers=_auth(token),
        )
        assert r1.status_code == 200, r1.text
        assert "Boss" in r1.json()["message"]["content"]

    # A memory row now exists under this user.
    s = await app_session_factory(tenant)
    try:
        rows = (
            (
                await s.execute(
                    select(Memory)
                    .where(Memory.user_id == user_id)
                    .where(Memory.deleted_at.is_(None))
                )
            )
            .scalars()
            .all()
        )
        boss_rows = [m for m in rows if "Boss" in m.content]
        assert boss_rows, "expected a persisted memory mentioning Boss"
        assert any(m.kind == "preference" for m in boss_rows)
    finally:
        await s.close()

    # Turn 2 (fresh request, no prior messages): retrieval injects the memory
    # and the agent addresses the user as Boss.
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r2 = await c.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "What should I focus on today?"}]},
            headers=_auth(token),
        )
        assert r2.status_code == 200, r2.text
        assert "Boss" in r2.json()["message"]["content"]


# --- always-on standing preferences (the cross-chat fix) --------------------


async def _seed_memory(
    app_session_factory,  # type: ignore[no-untyped-def]
    *,
    tenant_id: UUID,
    user_id: UUID,
    content: str,
    kind: str,
) -> None:
    result = await MockEmbeddingProvider().embed(texts=[content])
    s = await app_session_factory(tenant_id)
    try:
        await MemoryRepository(s).add(
            organization_id=tenant_id,
            user_id=user_id,
            content=content,
            embedding=result.vectors[0],
            embedding_model=result.model,
            kind=kind,
            source="user",
        )
        await s.commit()
    finally:
        await s.close()


class _SystemEchoProvider:
    """Records the system-message context it received and greets by name if the
    context mentions one. Lets a test prove WHAT reached the model."""

    def __init__(self) -> None:
        self.system_seen: list[str] = []

    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_executor: ToolExecutor | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> ChatCompletion:
        ctx = "\n".join(m.content for m in messages if m.role == "system")
        self.system_seen.append(ctx)
        name = "Boss" if "Boss" in ctx else "there"
        return ChatCompletion(
            content=f"Hello, {name}!", model="scripted", usage=None, finish_reason="stop"
        )

    async def stream(
        self, *, messages: list[ChatMessage], model: str | None = None, temperature: float = 0.7
    ) -> AsyncIterator[ChatStreamEvent]:
        raise NotImplementedError  # non-streaming /chat only
        yield  # pragma: no cover


@pytest.mark.asyncio
async def test_preference_injected_on_unrelated_message_without_semantic_match(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """A saved preference reaches a brand-new chat whose first message ('hi') is
    NOT semantically related — proving the always-on injection, independent of
    similarity. Semantic retrieval is turned OFF via an impossible threshold, so
    ONLY the standing-preferences path can deliver it."""
    provider = _SystemEchoProvider()
    db_app.state.chat_provider = provider
    db_app.state.settings.memory_retrieval_min_similarity = 2.0  # cosine ≤ 1 → semantic off

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "standing-pref@example.com")
        await _seed_memory(
            app_session_factory,
            tenant_id=UUID(reg["active_tenant_id"]),
            user_id=UUID(reg["user_id"]),
            content="The user prefers to be called Boss.",
            kind="preference",
        )
        r = await c.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "hi"}]},
            headers=_auth(reg["access_token"]),
        )
        assert r.status_code == 200, r.text
        assert "Boss" in r.json()["message"]["content"]

    # The preference was delivered via the standing-preferences block.
    assert "Known user preferences" in provider.system_seen[-1]
    assert "Boss" in provider.system_seen[-1]


@pytest.mark.asyncio
async def test_fact_memory_is_not_auto_injected(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,  # type: ignore[no-untyped-def]
) -> None:
    """A kind='fact' memory must NOT be force-injected every turn — it only
    surfaces via semantic search_memory. With semantic retrieval off and an
    unrelated message, the fact must be absent from the injected context."""
    provider = _SystemEchoProvider()
    db_app.state.chat_provider = provider
    db_app.state.settings.memory_retrieval_min_similarity = 2.0  # semantic off

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "no-fact-inject@example.com")
        await _seed_memory(
            app_session_factory,
            tenant_id=UUID(reg["active_tenant_id"]),
            user_id=UUID(reg["user_id"]),
            content="The user's favorite color is teal.",
            kind="fact",
        )
        r = await c.post(
            "/api/v1/chat",
            json={"messages": [{"role": "user", "content": "hi"}]},
            headers=_auth(reg["access_token"]),
        )
        assert r.status_code == 200, r.text

    ctx = provider.system_seen[-1] if provider.system_seen else ""
    assert "teal" not in ctx.lower()  # facts are never auto-injected
    assert "Known user preferences" not in ctx  # nothing standing to inject
