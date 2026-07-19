"""Phase 5d — memory retrieval + injection.

End-to-end from HTTP through embed(query) → search_similar → threshold gate
→ system-message injection before the provider call. The injected context
is ephemeral (never persisted) — proven by inspecting the recording
provider AND GET /conversations/{id}.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient

from app.ai.providers.embeddings.mock import MockEmbeddingProvider
from app.ai.providers.mock import MockProvider
from app.application.ports.chat import ChatCompletion, ChatMessage, ChatStreamEvent
from app.application.ports.embeddings import EmbeddingResult, InputType
from app.infrastructure.db.repositories import MemoryRepository

# --- test doubles ------------------------------------------------------------


class _RecordingProvider:
    """Wraps MockProvider and records the messages passed to complete()/stream()."""

    def __init__(self) -> None:
        self._inner = MockProvider()
        self.complete_calls: list[list[ChatMessage]] = []
        self.stream_calls: list[list[ChatMessage]] = []

    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_executor: Any = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> ChatCompletion:
        # 6b widened the ChatProvider port; this recording double accepts the
        # extra kwargs to stay Protocol-conformant. Behavior unchanged.
        del tools, tool_executor
        self.complete_calls.append(list(messages))
        return await self._inner.complete(messages=messages, model=model, temperature=temperature)

    async def stream(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_executor: Any = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[ChatStreamEvent]:
        # 6d widened stream() the same way 6b widened complete(); this
        # recording double accepts the extra kwargs to stay Protocol-conformant.
        # MockProvider ignores them; behavior unchanged.
        del tools, tool_executor
        self.stream_calls.append(list(messages))
        async for e in self._inner.stream(messages=messages, model=model, temperature=temperature):
            yield e


class _SpyEmbeddingProvider:
    """Wraps MockEmbeddingProvider and records every embed() call."""

    def __init__(self) -> None:
        self._inner = MockEmbeddingProvider()
        self.calls: list[dict[str, Any]] = []

    @property
    def dimension(self) -> int:
        return self._inner.dimension

    async def embed(
        self,
        *,
        texts: list[str],
        input_type: InputType = "document",
    ) -> EmbeddingResult:
        self.calls.append({"texts": list(texts), "input_type": input_type})
        return await self._inner.embed(texts=texts, input_type=input_type)


class _RaisingEmbeddingProvider:
    """Anything calling embed() raises. Used to prove retrieval is best-effort."""

    @property
    def dimension(self) -> int:
        return 1024

    async def embed(
        self,
        *,
        texts: list[str],
        input_type: InputType = "document",
    ) -> EmbeddingResult:
        raise RuntimeError("embed exploded")


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
    provider: MockEmbeddingProvider,
) -> None:
    """Insert one memory (with mock embedding of `content`) under the caller's
    tenant/user, then commit. Uses the neo_app tenant session — WITH CHECK
    is exercised, same as production writes.
    """
    result = await provider.embed(texts=[content])
    s = await app_session_factory(tenant_id)
    try:
        await MemoryRepository(s).add(
            organization_id=tenant_id,
            user_id=user_id,
            content=content,
            embedding=result.vectors[0],
            embedding_model=result.model,
        )
        await s.commit()
    finally:
        await s.close()


def _parse_sse(raw: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for chunk in raw.split("\n\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        for line in chunk.split("\n"):
            if line.startswith("data:"):
                events.append(json.loads(line[len("data:") :].strip()))
    return events


def _system_content_from(calls: list[list[ChatMessage]]) -> str | None:
    """Return the concatenated content of any role='system' messages in the
    most recent call, or None if none.
    """
    if not calls:
        return None
    system_parts = [m.content for m in calls[-1] if m.role == "system"]
    if not system_parts:
        return None
    return "\n".join(system_parts)


# --- 1: retrieval injects a matching memory ---------------------------------


@pytest.mark.asyncio
async def test_retrieval_injects_matching_memory(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,
) -> None:
    rec = _RecordingProvider()
    db_app.state.chat_provider = rec

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "retr-hit@example.com")
        token = reg["access_token"]
        tenant_id = UUID(reg["active_tenant_id"])
        user_id = UUID(reg["user_id"])

        # Seed a memory whose vector is identical to embed("target text").
        await _seed_memory(
            app_session_factory,
            tenant_id=tenant_id,
            user_id=user_id,
            content="target text",
            provider=MockEmbeddingProvider(),
        )

        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "target text"}]},
        )
        assert r.status_code == 200

    system = _system_content_from(rec.complete_calls)
    assert system is not None
    assert "target text" in system


# --- 2: below floor → no injection ------------------------------------------


@pytest.mark.asyncio
async def test_retrieval_stays_silent_below_floor(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,
) -> None:
    rec = _RecordingProvider()
    db_app.state.chat_provider = rec

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "retr-below@example.com")
        token = reg["access_token"]
        tenant_id = UUID(reg["active_tenant_id"])
        user_id = UUID(reg["user_id"])

        await _seed_memory(
            app_session_factory,
            tenant_id=tenant_id,
            user_id=user_id,
            content="target text",
            provider=MockEmbeddingProvider(),
        )

        # Query a distinct text — mock vectors are near-orthogonal in 1024
        # dims, similarity ~= 0, well below the 0.7 floor.
        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "wholly unrelated"}]},
        )
        assert r.status_code == 200

    assert _system_content_from(rec.complete_calls) is None


# --- 3: retrieval is best-effort --------------------------------------------


@pytest.mark.asyncio
async def test_retrieval_is_best_effort(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,
) -> None:
    rec = _RecordingProvider()
    db_app.state.chat_provider = rec
    db_app.state.embedding_provider = _RaisingEmbeddingProvider()

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "retr-fail@example.com")
        token = reg["access_token"]
        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 200
        assert r.json()["message"]["content"] == "(mock) hi"

    # Provider was called (chat succeeded); no injection.
    assert rec.complete_calls, "chat provider must still be called even if retrieval fails"
    assert _system_content_from(rec.complete_calls) is None


# --- 4: input_type="query" wiring -------------------------------------------


@pytest.mark.asyncio
async def test_retrieval_uses_input_type_query(
    db_app,  # type: ignore[no-untyped-def]
) -> None:
    spy = _SpyEmbeddingProvider()
    db_app.state.embedding_provider = spy

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "input-type-query@example.com")
        token = reg["access_token"]
        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "hello query"}]},
        )
        assert r.status_code == 200

    # Retrieval side (query) and write side (document) both fired in this turn.
    query_calls = [c for c in spy.calls if c["input_type"] == "query"]
    document_calls = [c for c in spy.calls if c["input_type"] == "document"]
    assert len(query_calls) >= 1
    assert query_calls[0]["texts"] == ["hello query"]
    # The 5c write fires with input_type="document" — proves both sides coexist.
    assert len(document_calls) >= 1


# --- 5: tenant isolation of retrieval ---------------------------------------


@pytest.mark.asyncio
async def test_retrieval_tenant_isolated(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,
) -> None:
    rec = _RecordingProvider()
    db_app.state.chat_provider = rec

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        alice = await _register(c, "retr-iso-alice@example.com")
        bob = await _register(c, "retr-iso-bob@example.com")

        # Seed a memory under Alice (org A).
        await _seed_memory(
            app_session_factory,
            tenant_id=UUID(alice["active_tenant_id"]),
            user_id=UUID(alice["user_id"]),
            content="alice secret",
            provider=MockEmbeddingProvider(),
        )

        # Bob (org B) queries the SAME text — RLS must keep Alice's memory
        # invisible to search_similar under Bob's neo_app tenant session.
        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {bob['access_token']}"},
            json={"messages": [{"role": "user", "content": "alice secret"}]},
        )
        assert r.status_code == 200

    system = _system_content_from(rec.complete_calls)
    assert system is None or "alice secret" not in system


# --- 6: streaming path injects matching memory ------------------------------


@pytest.mark.asyncio
async def test_stream_injects_matching_memory(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,
) -> None:
    rec = _RecordingProvider()
    db_app.state.chat_provider = rec

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "retr-stream@example.com")
        token = reg["access_token"]
        tenant_id = UUID(reg["active_tenant_id"])
        user_id = UUID(reg["user_id"])

        await _seed_memory(
            app_session_factory,
            tenant_id=tenant_id,
            user_id=user_id,
            content="stream target",
            provider=MockEmbeddingProvider(),
        )

        r = await c.post(
            "/api/v1/chat/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "stream target"}]},
        )
        assert r.status_code == 200
        events = _parse_sse(r.text)
        assert events[0]["type"] == "meta"
        assert any(e["type"] == "delta" for e in events)
        assert events[-1]["type"] == "done"

    system = _system_content_from(rec.stream_calls)
    assert system is not None
    assert "stream target" in system


# --- 7: injected context is not persisted -----------------------------------


@pytest.mark.asyncio
async def test_injected_context_not_persisted(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,
) -> None:
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "retr-not-persisted@example.com")
        token = reg["access_token"]
        tenant_id = UUID(reg["active_tenant_id"])
        user_id = UUID(reg["user_id"])

        await _seed_memory(
            app_session_factory,
            tenant_id=tenant_id,
            user_id=user_id,
            content="persisted check",
            provider=MockEmbeddingProvider(),
        )

        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "persisted check"}]},
        )
        assert r.status_code == 200
        conv_id = r.json()["conversation_id"]

        detail = await c.get(
            f"/api/v1/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail.status_code == 200
        msgs = detail.json()["messages"]
        # Exactly [user, assistant]. The injected system context is EPHEMERAL —
        # never a saved row.
        assert [m["role"] for m in msgs] == ["user", "assistant"]
        assert msgs[0]["content"] == "persisted check"
        assert msgs[1]["content"] == "(mock) persisted check"


# --- 8: retrieval disabled → strict no-op ------------------------------------


@pytest.mark.asyncio
async def test_retrieval_disabled_skips_embedding_call(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,
) -> None:
    """Sanity: with memory_retrieval_enabled=False, no query-side embed happens."""
    spy = _SpyEmbeddingProvider()
    db_app.state.embedding_provider = spy
    db_app.state.settings = db_app.state.settings.model_copy(
        update={"memory_retrieval_enabled": False}
    )

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "retr-off@example.com")
        token = reg["access_token"]
        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "hi"}]},
        )
        assert r.status_code == 200

    query_calls = [c for c in spy.calls if c["input_type"] == "query"]
    assert query_calls == []
    # The 5c write still runs.
    assert any(c["input_type"] == "document" for c in spy.calls)
