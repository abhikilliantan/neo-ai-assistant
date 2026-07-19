"""Chat persistence — tenant-isolation + repo smoke tests.

Runs against the real Alembic migration (via the session-scoped conftest
fixture) so RLS ENABLE + FORCE + policies are exercised for real, exactly as
in production.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models import (
    Conversation,
    Message,
    Organization,
    Role,
    User,
)
from app.infrastructure.db.repositories import (
    ConversationRepository,
    MessageRepository,
)


async def _seed_two_tenants(
    db_session: AsyncSession,
) -> tuple[UUID, UUID, UUID, UUID, UUID, UUID]:
    """As neo (bypasses RLS): orgs A + B, one user each, one conversation each,
    two messages each. Returns (org_a, org_b, user_a, user_b, conv_a, conv_b).
    """
    # Roles are seeded by the identity migration; just fetch one to keep FK happy
    # elsewhere in the suite (not used here directly but ensures seed is intact).
    _ = (await db_session.execute(select(Role).where(Role.name == "owner"))).scalar_one()

    org_a = Organization(name="Org A", slug="chat-a")
    org_b = Organization(name="Org B", slug="chat-b")
    user_a = User(email="alice@chat-a.example", password_hash="x")
    user_b = User(email="bob@chat-b.example", password_hash="x")
    db_session.add_all([org_a, org_b, user_a, user_b])
    await db_session.flush()

    conv_a = Conversation(organization_id=org_a.id, user_id=user_a.id, title="A chat")
    conv_b = Conversation(organization_id=org_b.id, user_id=user_b.id, title="B chat")
    db_session.add_all([conv_a, conv_b])
    await db_session.flush()

    db_session.add_all(
        [
            Message(
                organization_id=org_a.id,
                conversation_id=conv_a.id,
                role="user",
                content="hello from A",
            ),
            Message(
                organization_id=org_a.id,
                conversation_id=conv_a.id,
                role="assistant",
                content="A reply",
            ),
            Message(
                organization_id=org_b.id,
                conversation_id=conv_b.id,
                role="user",
                content="hello from B",
            ),
            Message(
                organization_id=org_b.id,
                conversation_id=conv_b.id,
                role="assistant",
                content="B reply",
            ),
        ]
    )
    await db_session.commit()
    return org_a.id, org_b.id, user_a.id, user_b.id, conv_a.id, conv_b.id


# --- adversarial isolation ---------------------------------------------------


@pytest.mark.asyncio
async def test_no_tenant_context_hides_conversations_and_messages(
    db_session: AsyncSession, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    await _seed_two_tenants(db_session)
    s = await app_session_factory(None)
    try:
        assert (await s.execute(select(Conversation))).scalars().all() == []
        assert (await s.execute(select(Message))).scalars().all() == []
    finally:
        await s.close()


@pytest.mark.asyncio
async def test_tenant_A_sees_only_A(db_session: AsyncSession, app_session_factory) -> None:  # type: ignore[no-untyped-def]
    org_a, org_b, _ua, _ub, _ca, _cb = await _seed_two_tenants(db_session)
    s = await app_session_factory(org_a)
    try:
        conv_orgs = [
            c.organization_id for c in (await s.execute(select(Conversation))).scalars().all()
        ]
        msg_orgs = [m.organization_id for m in (await s.execute(select(Message))).scalars().all()]
        assert conv_orgs == [org_a]
        assert msg_orgs == [org_a, org_a]
        assert org_b not in conv_orgs
        assert org_b not in msg_orgs
    finally:
        await s.close()


@pytest.mark.asyncio
async def test_tenant_B_sees_only_B(db_session: AsyncSession, app_session_factory) -> None:  # type: ignore[no-untyped-def]
    org_a, org_b, _ua, _ub, _ca, _cb = await _seed_two_tenants(db_session)
    s = await app_session_factory(org_b)
    try:
        conv_orgs = [
            c.organization_id for c in (await s.execute(select(Conversation))).scalars().all()
        ]
        msg_orgs = [m.organization_id for m in (await s.execute(select(Message))).scalars().all()]
        assert conv_orgs == [org_b]
        assert msg_orgs == [org_b, org_b]
        assert org_a not in conv_orgs
        assert org_a not in msg_orgs
    finally:
        await s.close()


@pytest.mark.asyncio
async def test_cross_tenant_where_clause_is_still_filtered(
    db_session: AsyncSession, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    """RLS applies BEFORE the WHERE — a targeted cross-tenant query returns nothing."""
    org_a, org_b, _ua, _ub, _ca, _cb = await _seed_two_tenants(db_session)
    s = await app_session_factory(org_a)
    try:
        conv_stmt = select(Conversation).where(Conversation.organization_id == org_b)
        assert (await s.execute(conv_stmt)).scalars().all() == []
        msg_stmt = select(Message).where(Message.organization_id == org_b)
        assert (await s.execute(msg_stmt)).scalars().all() == []
    finally:
        await s.close()


@pytest.mark.asyncio
async def test_insert_conversation_into_other_tenant_rejected(
    db_session: AsyncSession, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    """WITH CHECK: inserting a conversation into a foreign tenant fails."""
    org_a, org_b, _ua, user_b, _ca, _cb = await _seed_two_tenants(db_session)
    s = await app_session_factory(org_a)
    try:
        s.add(Conversation(organization_id=org_b, user_id=user_b, title="sneaky"))
        with pytest.raises(DBAPIError):
            await s.flush()
    finally:
        await s.rollback()
        await s.close()


@pytest.mark.asyncio
async def test_insert_message_into_other_tenant_rejected(
    db_session: AsyncSession, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    """WITH CHECK: inserting a message with a foreign organization_id fails."""
    org_a, org_b, _ua, _ub, _ca, conv_b = await _seed_two_tenants(db_session)
    s = await app_session_factory(org_a)
    try:
        s.add(
            Message(
                organization_id=org_b,
                conversation_id=conv_b,
                role="user",
                content="sneaky",
            )
        )
        with pytest.raises(DBAPIError):
            await s.flush()
    finally:
        await s.rollback()
        await s.close()


# --- repository smoke --------------------------------------------------------


@pytest.mark.asyncio
async def test_repositories_round_trip_under_neo_app_tenant_session(
    db_session: AsyncSession, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    """Repos work under a neo_app session with the tenant GUC set: create a
    conversation, add two messages, list them back in order.
    """
    org_a, _ob, user_a, _ub, _ca, _cb = await _seed_two_tenants(db_session)
    s = await app_session_factory(org_a)
    try:
        conv_repo = ConversationRepository(s)
        msg_repo = MessageRepository(s)

        conv = await conv_repo.create(organization_id=org_a, user_id=user_a, title="repo smoke")
        await msg_repo.add(
            organization_id=org_a,
            conversation_id=conv.id,
            role="user",
            content="hi",
        )
        await msg_repo.add(
            organization_id=org_a,
            conversation_id=conv.id,
            role="assistant",
            content="hello",
            model="mock-1",
            prompt_tokens=1,
            completion_tokens=1,
            finish_reason="stop",
        )
        await conv_repo.touch(conv.id)
        await s.commit()

        # Fresh session under the same tenant, read back.
        s2 = await app_session_factory(org_a)
        try:
            conv_repo2 = ConversationRepository(s2)
            msg_repo2 = MessageRepository(s2)

            convs = await conv_repo2.list_for_org(org_a)
            # New conversation (touched → non-null last_message_at) sorts first.
            assert convs[0].id == conv.id
            assert convs[0].last_message_at is not None

            msgs = await msg_repo2.list_for_conversation(conv.id)
            assert [m.role for m in msgs] == ["user", "assistant"]
            assert [m.content for m in msgs] == ["hi", "hello"]
            assert msgs[1].model == "mock-1"
            assert msgs[1].finish_reason == "stop"
        finally:
            await s2.close()
    finally:
        await s.close()


@pytest.mark.asyncio
async def test_messages_in_one_transaction_have_deterministic_order(
    db_session: AsyncSession, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    """Two messages inserted in ONE transaction (as phase 4b will do for
    user + assistant on the same turn) must list back in insertion order.

    Regression guard: with server_default = now() (transaction-stable) both
    rows would share a timestamp and the sort would be undefined. With
    clock_timestamp() + id.asc() tiebreaker, order is total.
    """
    org_a, _ob, user_a, _ub, _ca, _cb = await _seed_two_tenants(db_session)
    s = await app_session_factory(org_a)
    try:
        conv_repo = ConversationRepository(s)
        msg_repo = MessageRepository(s)

        conv = await conv_repo.create(
            organization_id=org_a, user_id=user_a, title="one-txn ordering"
        )
        # Both inserts inside the same active transaction, then commit once.
        await msg_repo.add(
            organization_id=org_a,
            conversation_id=conv.id,
            role="user",
            content="turn-1 user",
        )
        await msg_repo.add(
            organization_id=org_a,
            conversation_id=conv.id,
            role="assistant",
            content="turn-1 assistant",
        )
        await s.commit()

        s2 = await app_session_factory(org_a)
        try:
            msgs = await MessageRepository(s2).list_for_conversation(conv.id)
            assert [m.role for m in msgs] == ["user", "assistant"]
            assert [m.content for m in msgs] == ["turn-1 user", "turn-1 assistant"]
            # And the timestamps advanced within the txn — no equality.
            assert msgs[0].created_at < msgs[1].created_at
        finally:
            await s2.close()
    finally:
        await s.close()
