"""Phase 5c memory write path.

End-to-end from HTTP endpoint through extractor → embedding → memory write,
with the mock extractor + mock embedding provider pinned by conftest.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.ai.providers.embeddings.mock import MockEmbeddingProvider
from app.application.ports.chat import ChatMessage
from app.application.ports.embeddings import EmbeddingResult, InputType
from app.application.ports.memory_extraction import ExtractedMemory
from app.infrastructure.db.models import Memory
from app.infrastructure.db.repositories import MemoryRepository


async def _register(client: AsyncClient, email: str) -> dict[str, Any]:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password12345"},
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def _parse_sse(text: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for chunk in text.split("\n\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        for line in chunk.split("\n"):
            if line.startswith("data:"):
                events.append(json.loads(line[len("data:") :].strip()))
    return events


# --- non-streaming happy path -----------------------------------------------


@pytest.mark.asyncio
async def test_chat_extracts_and_stores_memory_after_turn(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,
) -> None:
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "mem-write@example.com")
        token = reg["access_token"]
        tenant_id = UUID(reg["active_tenant_id"])
        user_id = UUID(reg["user_id"])

        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "I like espresso"}]},
        )
        assert r.status_code == 200, r.text

    # Under the user's tenant, exactly one memory extracted by the mock.
    s = await app_session_factory(tenant_id)
    try:
        mems = await MemoryRepository(s).list_for_user(organization_id=tenant_id, user_id=user_id)
        assert len(mems) == 1
        m = mems[0]
        assert m.content == "user_fact: I like espresso"
        assert m.kind == "fact"
        assert m.source == "chat"
        assert m.embedding_model == "mock-embed-1"
        assert len(m.embedding) == 1024
    finally:
        await s.close()


# --- streaming happy path ---------------------------------------------------


@pytest.mark.asyncio
async def test_chat_stream_extracts_and_stores_memory_after_done(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,
) -> None:
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "mem-stream@example.com")
        token = reg["access_token"]
        tenant_id = UUID(reg["active_tenant_id"])
        user_id = UUID(reg["user_id"])

        r = await c.post(
            "/api/v1/chat/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "call me Priya"}]},
        )
        assert r.status_code == 200
        events = _parse_sse(r.text)
        assert events[-1]["type"] == "done"

    s = await app_session_factory(tenant_id)
    try:
        mems = await MemoryRepository(s).list_for_user(organization_id=tenant_id, user_id=user_id)
        assert [m.content for m in mems] == ["user_fact: call me Priya"]
        assert mems[0].source == "chat"
    finally:
        await s.close()


# --- best-effort guard: extractor failure MUST NOT break chat ---------------


class _RaisingExtractor:
    async def extract(
        self,
        *,
        messages: list[ChatMessage],
        assistant_reply: str,
    ) -> list[ExtractedMemory]:
        raise RuntimeError("extractor exploded")


@pytest.mark.asyncio
async def test_extractor_failure_does_not_break_chat_non_streaming(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,
) -> None:
    db_app.state.memory_extractor = _RaisingExtractor()

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "mem-fail@example.com")
        token = reg["access_token"]
        tenant_id = UUID(reg["active_tenant_id"])
        user_id = UUID(reg["user_id"])

        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "hello"}]},
        )
        # Chat still succeeds; assistant reply still present.
        assert r.status_code == 200
        assert r.json()["message"]["content"] == "(mock) hello"
        conv_id = r.json()["conversation_id"]
        assert conv_id

        # Assistant message still persisted (Txn A + Txn B).
        detail = await c.get(
            f"/api/v1/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail.status_code == 200
        roles = [m["role"] for m in detail.json()["messages"]]
        assert roles == ["user", "assistant"]

    # Memories table is empty for this user — the extractor failure was swallowed.
    s = await app_session_factory(tenant_id)
    try:
        mems = await MemoryRepository(s).list_for_user(organization_id=tenant_id, user_id=user_id)
        assert mems == []
    finally:
        await s.close()


@pytest.mark.asyncio
async def test_extractor_failure_does_not_break_chat_streaming(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,
) -> None:
    db_app.state.memory_extractor = _RaisingExtractor()

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "mem-stream-fail@example.com")
        token = reg["access_token"]
        tenant_id = UUID(reg["active_tenant_id"])
        user_id = UUID(reg["user_id"])

        r = await c.post(
            "/api/v1/chat/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "hello stream"}]},
        )
        assert r.status_code == 200
        events = _parse_sse(r.text)
        assert events[-1]["type"] == "done"

    s = await app_session_factory(tenant_id)
    try:
        # Assistant row still persisted via Txn B.
        detail_msgs = (
            (await s.execute(select(Memory).where(Memory.user_id == user_id))).scalars().all()
        )
        assert detail_msgs == []
    finally:
        await s.close()


# --- input_type="document" wiring -------------------------------------------


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


@pytest.mark.asyncio
async def test_write_path_uses_input_type_document(
    db_app,  # type: ignore[no-untyped-def]
) -> None:
    spy = _SpyEmbeddingProvider()
    db_app.state.embedding_provider = spy

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        reg = await _register(c, "input-type-spy@example.com")
        token = reg["access_token"]
        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "user prefers dark mode"}]},
        )
        assert r.status_code == 200

    assert len(spy.calls) == 1
    assert spy.calls[0]["input_type"] == "document"
    assert spy.calls[0]["texts"] == ["user_fact: user prefers dark mode"]


# --- tenant isolation of the write path -------------------------------------


@pytest.mark.asyncio
async def test_memory_written_from_org_A_chat_invisible_under_org_B(
    db_app,  # type: ignore[no-untyped-def]
    app_session_factory,
) -> None:
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        alice = await _register(c, "iso-alice@example.com")
        bob = await _register(c, "iso-bob@example.com")

        alice_tenant = UUID(alice["active_tenant_id"])
        alice_user = UUID(alice["user_id"])
        bob_tenant = UUID(bob["active_tenant_id"])
        bob_user = UUID(bob["user_id"])

        # Alice chats — memory written under her tenant.
        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {alice['access_token']}"},
            json={"messages": [{"role": "user", "content": "alice fact"}]},
        )
        assert r.status_code == 200

    # Alice's tenant session sees the memory.
    sa = await app_session_factory(alice_tenant)
    try:
        alice_mems = await MemoryRepository(sa).list_for_user(
            organization_id=alice_tenant, user_id=alice_user
        )
        assert [m.content for m in alice_mems] == ["user_fact: alice fact"]
    finally:
        await sa.close()

    # Bob's tenant session sees nothing — even scanning the whole memories
    # table (no WHERE) returns 0 rows under GUC=B, because RLS filters first.
    sb = await app_session_factory(bob_tenant)
    try:
        # Untargeted scan under B's GUC.
        rows = (await sb.execute(select(Memory))).scalars().all()
        assert rows == []
        # And Bob's user has no memories of his own.
        bob_mems = await MemoryRepository(sb).list_for_user(
            organization_id=bob_tenant, user_id=bob_user
        )
        assert bob_mems == []
    finally:
        await sb.close()
