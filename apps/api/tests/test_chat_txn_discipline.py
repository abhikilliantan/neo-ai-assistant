"""Phase 6k-2 — transaction discipline + provider-failure semantics on /chat.

Covers the runtime-behavior changes this slice makes to the NON-streaming path:

  - Connection discipline (item 1, load-bearing): /chat holds NO DB session
    across the provider call. Proven with the same technique as the 6d stream
    proof — the app's sessionmaker is wrapped to record every AsyncSession it
    opens, and a spy provider snapshots `in_transaction()` for all of them at
    the moment `complete()` is entered. None is in a transaction → no pooled
    connection is pinned for the provider round trip. Distinct identities +
    all released after the request round it out.

  - Provider-failure semantics (item 3, LOCKED, both paths): the user message
    PERSISTS on provider failure, the assistant message does NOT, and the
    conversation shows exactly one [user] row. On /chat this is a deliberate
    behavior change — pre-6k-2 the single request session rolled the user
    message back too.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.chat import ChatCompletion, ChatMessage, ChatStreamEvent
from app.infrastructure.db import Database
from app.shared.exceptions.ai import ProviderRateLimitError


async def _register(client: AsyncClient, email: str) -> dict[str, Any]:
    r = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": "password12345"},
    )
    assert r.status_code == 201, r.text
    return r.json()  # type: ignore[no-any-return]


def _parse_sse(body: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for chunk in body.split("\n\n"):
        chunk = chunk.strip()
        if not chunk:
            continue
        for line in chunk.split("\n"):
            if line.startswith("data:"):
                events.append(json.loads(line[len("data:") :].strip()))
    return events


# --- item 1: connection discipline on /chat ---------------------------------


class _SessionSpyProvider:
    """Non-streaming provider double that snapshots the transaction state of
    every session the app has opened, at the instant `complete()` is entered.
    """

    def __init__(self, created: list[AsyncSession]) -> None:
        self._created = created
        self.n_at_call = 0
        self.in_txn_at_call: list[bool] = []

    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_executor: object = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> ChatCompletion:
        snapshot = list(self._created)
        self.n_at_call = len(snapshot)
        self.in_txn_at_call = [s.in_transaction() for s in snapshot]
        return ChatCompletion(content="(spy) ok", model="spy-1", usage=None, finish_reason="stop")

    async def stream(self, **_: object) -> AsyncIterator[ChatStreamEvent]:  # pragma: no cover
        raise NotImplementedError
        yield  # unreachable — makes this an async generator


@pytest.mark.asyncio
async def test_chat_holds_no_session_across_provider_call(
    db_app,  # type: ignore[no-untyped-def]
) -> None:
    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        # Register FIRST (under the untouched DB), then wrap the sessionmaker so
        # `created` only accumulates the /chat request's sessions.
        token = (await _register(c, "6k2-discipline@example.com"))["access_token"]

        created: list[AsyncSession] = []
        real = db_app.state.database

        def _recording_sessionmaker() -> AsyncSession:
            s = real.sessionmaker()
            created.append(s)
            return s

        db_app.state.database = Database(
            engine=real.engine,
            sessionmaker=_recording_sessionmaker,  # type: ignore[arg-type]
        )
        spy = _SessionSpyProvider(created)
        db_app.state.chat_provider = spy

        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "discipline please"}]},
        )
        assert r.status_code == 200, r.text

    # Load-bearing: at the moment the provider was entered, at least one short
    # session had already run (Txn A user-persist + the scoped user lookup),
    # and NONE was still in a transaction — no pooled connection is held across
    # the provider round trip.
    assert spy.n_at_call >= 1
    assert all(t is False for t in spy.in_txn_at_call), spy.in_txn_at_call

    # After the whole request (incl. Txn B + the background 5c write), every
    # session the app opened is a DISTINCT identity and every one is released.
    assert len(created) >= 2
    assert len({id(s) for s in created}) == len(created)
    assert all(s.in_transaction() is False for s in created)


# --- item 3: provider-failure persistence semantics -------------------------


class _CompleteFailingProvider:
    async def complete(self, **_: object) -> ChatCompletion:
        raise ProviderRateLimitError("slow down")

    async def stream(self, **_: object) -> AsyncIterator[ChatStreamEvent]:  # pragma: no cover
        raise NotImplementedError
        yield


@pytest.mark.asyncio
async def test_chat_provider_failure_persists_user_not_assistant(
    db_app,  # type: ignore[no-untyped-def]
) -> None:
    """Deliberate 6k-2 behavior change on /chat: a provider failure leaves the
    user message persisted (committed in Txn A) and NO assistant row.
    """
    db_app.state.chat_provider = _CompleteFailingProvider()

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token = (await _register(c, "6k2-fail-nonstream@example.com"))["access_token"]

        r = await c.post(
            "/api/v1/chat",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "will fail"}]},
        )
        # ProviderRateLimitError → 429 envelope; the user turn still persisted.
        assert r.status_code == 429, r.text

        lst = await c.get("/api/v1/conversations", headers={"Authorization": f"Bearer {token}"})
        assert lst.status_code == 200
        convs = lst.json()
        assert len(convs) == 1
        conv_id = convs[0]["id"]

        detail = await c.get(
            f"/api/v1/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail.status_code == 200
        msgs = detail.json()["messages"]
        assert [m["role"] for m in msgs] == ["user"]
        assert msgs[0]["content"] == "will fail"


class _StreamFailingProvider:
    async def complete(self, **_: object) -> ChatCompletion:  # pragma: no cover
        raise NotImplementedError

    async def stream(self, **_: object) -> AsyncIterator[ChatStreamEvent]:
        yield ChatStreamEvent(type="delta", content="partial")
        raise ProviderRateLimitError("slow down")


@pytest.mark.asyncio
async def test_chat_stream_provider_failure_persists_user_not_assistant(
    db_app,  # type: ignore[no-untyped-def]
) -> None:
    """Same LOCKED semantics on the stream path: Txn A already committed the
    user message before the stream, so a mid-stream provider error leaves the
    user turn persisted and no assistant row.
    """
    db_app.state.chat_provider = _StreamFailingProvider()

    transport = ASGITransport(app=db_app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        token = (await _register(c, "6k2-fail-stream@example.com"))["access_token"]

        r = await c.post(
            "/api/v1/chat/stream",
            headers={"Authorization": f"Bearer {token}"},
            json={"messages": [{"role": "user", "content": "will fail streaming"}]},
        )
        assert r.status_code == 200  # headers already flushed when the error hits
        events = _parse_sse(r.text)
        conv_id = events[0]["conversation_id"]
        assert events[-1]["type"] == "error"

        detail = await c.get(
            f"/api/v1/conversations/{conv_id}",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert detail.status_code == 200
        msgs = detail.json()["messages"]
        assert [m["role"] for m in msgs] == ["user"]
        assert msgs[0]["content"] == "will fail streaming"
