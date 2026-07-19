"""Memory + UserPreference — tenant-isolation, vector-search correctness,
and repo smoke tests. Runs against the real Alembic migration (pgvector +
HNSW + RLS) using the deterministic MockEmbeddingProvider so ranking is
predictable.
"""

from __future__ import annotations

from uuid import UUID

import pytest
from sqlalchemy import select
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.providers.embeddings.mock import MockEmbeddingProvider
from app.infrastructure.db.models import (
    Memory,
    Organization,
    User,
    UserPreference,
)
from app.infrastructure.db.repositories import (
    MemoryRepository,
    UserPreferenceRepository,
)

_MODEL = "mock-embed-1"


async def _embed(provider: MockEmbeddingProvider, text: str) -> list[float]:
    result = await provider.embed(texts=[text])
    return result.vectors[0]


async def _seed_two_tenants(
    db_session: AsyncSession, provider: MockEmbeddingProvider
) -> tuple[UUID, UUID, UUID, UUID]:
    """As neo (bypasses RLS): orgs A+B, one user each, one memory each
    ("A-different" in A, "target" in B), one preference each. Returns
    (org_a, org_b, user_a, user_b).
    """
    org_a = Organization(name="Org A", slug="mem-a")
    org_b = Organization(name="Org B", slug="mem-b")
    user_a = User(email="alice@mem-a.example", password_hash="x")
    user_b = User(email="bob@mem-b.example", password_hash="x")
    db_session.add_all([org_a, org_b, user_a, user_b])
    await db_session.flush()

    a_diff = await _embed(provider, "A-different")
    b_target = await _embed(provider, "target")

    db_session.add_all(
        [
            Memory(
                organization_id=org_a.id,
                user_id=user_a.id,
                content="A-different",
                embedding=a_diff,
                embedding_model=_MODEL,
            ),
            Memory(
                organization_id=org_b.id,
                user_id=user_b.id,
                content="target",
                embedding=b_target,
                embedding_model=_MODEL,
            ),
            UserPreference(
                organization_id=org_a.id,
                user_id=user_a.id,
                key="theme",
                value="dark",
            ),
            UserPreference(
                organization_id=org_b.id,
                user_id=user_b.id,
                key="theme",
                value="light",
            ),
        ]
    )
    await db_session.commit()
    return org_a.id, org_b.id, user_a.id, user_b.id


# --- adversarial isolation ---------------------------------------------------


@pytest.mark.asyncio
async def test_no_tenant_context_hides_memories_and_prefs(
    db_session: AsyncSession, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    provider = MockEmbeddingProvider()
    await _seed_two_tenants(db_session, provider)
    s = await app_session_factory(None)
    try:
        assert (await s.execute(select(Memory))).scalars().all() == []
        assert (await s.execute(select(UserPreference))).scalars().all() == []
    finally:
        await s.close()


@pytest.mark.asyncio
async def test_tenant_A_sees_only_A(db_session: AsyncSession, app_session_factory) -> None:  # type: ignore[no-untyped-def]
    provider = MockEmbeddingProvider()
    org_a, org_b, _ua, _ub = await _seed_two_tenants(db_session, provider)
    s = await app_session_factory(org_a)
    try:
        mem_orgs = [m.organization_id for m in (await s.execute(select(Memory))).scalars().all()]
        pref_orgs = [
            p.organization_id for p in (await s.execute(select(UserPreference))).scalars().all()
        ]
        assert mem_orgs == [org_a]
        assert pref_orgs == [org_a]
        assert org_b not in mem_orgs
        assert org_b not in pref_orgs
    finally:
        await s.close()


@pytest.mark.asyncio
async def test_tenant_B_sees_only_B(db_session: AsyncSession, app_session_factory) -> None:  # type: ignore[no-untyped-def]
    provider = MockEmbeddingProvider()
    org_a, org_b, _ua, _ub = await _seed_two_tenants(db_session, provider)
    s = await app_session_factory(org_b)
    try:
        mem_orgs = [m.organization_id for m in (await s.execute(select(Memory))).scalars().all()]
        assert mem_orgs == [org_b]
        assert org_a not in mem_orgs
    finally:
        await s.close()


@pytest.mark.asyncio
async def test_cross_tenant_where_clause_is_still_filtered(
    db_session: AsyncSession, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    provider = MockEmbeddingProvider()
    org_a, org_b, _ua, _ub = await _seed_two_tenants(db_session, provider)
    s = await app_session_factory(org_a)
    try:
        mem_stmt = select(Memory).where(Memory.organization_id == org_b)
        assert (await s.execute(mem_stmt)).scalars().all() == []
        pref_stmt = select(UserPreference).where(UserPreference.organization_id == org_b)
        assert (await s.execute(pref_stmt)).scalars().all() == []
    finally:
        await s.close()


@pytest.mark.asyncio
async def test_insert_memory_into_other_tenant_rejected(
    db_session: AsyncSession, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    provider = MockEmbeddingProvider()
    org_a, org_b, _ua, user_b = await _seed_two_tenants(db_session, provider)
    s = await app_session_factory(org_a)
    try:
        s.add(
            Memory(
                organization_id=org_b,
                user_id=user_b,
                content="sneaky",
                embedding=await _embed(provider, "sneaky"),
                embedding_model=_MODEL,
            )
        )
        with pytest.raises(DBAPIError):
            await s.flush()
    finally:
        await s.rollback()
        await s.close()


@pytest.mark.asyncio
async def test_insert_preference_into_other_tenant_rejected(
    db_session: AsyncSession, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    provider = MockEmbeddingProvider()
    org_a, org_b, _ua, user_b = await _seed_two_tenants(db_session, provider)
    s = await app_session_factory(org_a)
    try:
        s.add(
            UserPreference(
                organization_id=org_b,
                user_id=user_b,
                key="sneaky",
                value="value",
            )
        )
        with pytest.raises(DBAPIError):
            await s.flush()
    finally:
        await s.rollback()
        await s.close()


# --- load-bearing vector isolation test -------------------------------------


@pytest.mark.asyncio
async def test_search_similar_ranks_within_tenant_and_never_leaks_other_tenants_nearer_hit(
    db_session: AsyncSession, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    """Setup:
      - Org A has memories `"target"` and `"A-different"`.
      - Org B has memory `"target"` (identical content → identical vector to query).
      - Query = embed("target").

    Expectations:
      - Under GUC=A, search_similar returns A's `"target"` first (similarity ≈ 1.0),
        then A's `"A-different"` (similarity < 1.0). B's `"target"` — which would
        also be similarity 1.0 — is NEVER returned; RLS scopes the ANN scan.
      - Under GUC=B, search_similar returns B's `"target"` first.
    """
    provider = MockEmbeddingProvider()

    # Reset the two-tenant seed and add a second A-memory (`"target"`) so we
    # can prove ordering AND cross-tenant invisibility in the same test.
    org_a, org_b, user_a, user_b = await _seed_two_tenants(db_session, provider)
    a_target_vec = await _embed(provider, "target")
    db_session.add(
        Memory(
            organization_id=org_a,
            user_id=user_a,
            content="target",
            embedding=a_target_vec,
            embedding_model=_MODEL,
        )
    )
    await db_session.commit()

    query = await _embed(provider, "target")

    # --- GUC=A: sees exactly A's two memories, target first --------------
    sa = await app_session_factory(org_a)
    try:
        results_a = await MemoryRepository(sa).search_similar(
            organization_id=org_a,
            user_id=user_a,
            query_embedding=query,
            limit=10,
        )
        contents_a = [m.content for m, _sim in results_a]
        assert contents_a == ["target", "A-different"]
        # Identical vector → distance 0 → similarity 1.0. Second row is farther.
        first_sim = results_a[0][1]
        second_sim = results_a[1][1]
        assert first_sim > second_sim
        assert abs(first_sim - 1.0) < 1e-6
        # And critically: no B-memory ever appears, even though B has an
        # equally-similar `"target"` row.
        assert all(m.organization_id == org_a for m, _ in results_a)
    finally:
        await sa.close()

    # --- GUC=B: sees only B's `"target"` -----------------------------------
    sb = await app_session_factory(org_b)
    try:
        results_b = await MemoryRepository(sb).search_similar(
            organization_id=org_b,
            user_id=user_b,
            query_embedding=query,
            limit=10,
        )
        assert [m.content for m, _sim in results_b] == ["target"]
        assert abs(results_b[0][1] - 1.0) < 1e-6
        assert all(m.organization_id == org_b for m, _ in results_b)
    finally:
        await sb.close()


# --- preference upsert ------------------------------------------------------


@pytest.mark.asyncio
async def test_preference_upsert_updates_in_place(
    db_session: AsyncSession, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    provider = MockEmbeddingProvider()
    org_a, _ob, user_a, _ub = await _seed_two_tenants(db_session, provider)
    s = await app_session_factory(org_a)
    try:
        repo = UserPreferenceRepository(s)
        # Seed inserted (theme, "dark"); upsert same key with a new value.
        updated = await repo.upsert(
            organization_id=org_a, user_id=user_a, key="theme", value="ultradark"
        )
        assert updated.value == "ultradark"

        # Still exactly one row for (org_a, user_a, "theme") — UNIQUE holds.
        all_rows = (
            (
                await s.execute(
                    select(UserPreference)
                    .where(UserPreference.user_id == user_a)
                    .where(UserPreference.key == "theme")
                )
            )
            .scalars()
            .all()
        )
        assert len(all_rows) == 1
        assert all_rows[0].value == "ultradark"

        # JSONB accepts objects too.
        obj_pref = await repo.upsert(
            organization_id=org_a,
            user_id=user_a,
            key="editor",
            value={"font": "Inter", "size": 14},
        )
        assert obj_pref.value == {"font": "Inter", "size": 14}
        await s.commit()
    finally:
        await s.close()


# --- repo smoke -------------------------------------------------------------


@pytest.mark.asyncio
async def test_repositories_round_trip_under_neo_app_tenant_session(
    db_session: AsyncSession, app_session_factory
) -> None:  # type: ignore[no-untyped-def]
    provider = MockEmbeddingProvider()
    org_a, _ob, user_a, _ub = await _seed_two_tenants(db_session, provider)

    s = await app_session_factory(org_a)
    try:
        mem_repo = MemoryRepository(s)
        pref_repo = UserPreferenceRepository(s)

        vec = await _embed(provider, "user likes espresso")
        added = await mem_repo.add(
            organization_id=org_a,
            user_id=user_a,
            content="user likes espresso",
            embedding=vec,
            embedding_model=_MODEL,
            kind="preference",
            source="chat",
        )
        assert added.kind == "preference"
        assert added.source == "chat"

        listed = await mem_repo.list_for_user(organization_id=org_a, user_id=user_a)
        # Newest first: `"user likes espresso"` beats `"A-different"` from the seed.
        assert listed[0].content == "user likes espresso"

        results = await mem_repo.search_similar(
            organization_id=org_a,
            user_id=user_a,
            query_embedding=vec,
            limit=1,
        )
        assert results[0][0].content == "user likes espresso"

        await pref_repo.upsert(organization_id=org_a, user_id=user_a, key="lang", value="en")
        got = await pref_repo.get(organization_id=org_a, user_id=user_a, key="lang")
        assert got is not None
        assert got.value == "en"

        await mem_repo.soft_delete(added.id)
        active = await mem_repo.list_for_user(organization_id=org_a, user_id=user_a)
        assert added.id not in {m.id for m in active}
        # soft-deleted still visible when active_only=False.
        all_rows = await mem_repo.list_for_user(
            organization_id=org_a, user_id=user_a, active_only=False
        )
        assert added.id in {m.id for m in all_rows}
        await s.commit()
    finally:
        await s.close()
