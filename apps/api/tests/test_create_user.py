"""Admin provisioning CLI (R6) — scripts/create_user.provision_user.

Proves the pilot-onboarding path creates user + org + owner membership directly on
the privileged (neo) session, and that a duplicate email fails cleanly — all
WITHOUT the HTTP route (so it works regardless of registration_enabled).
"""

from __future__ import annotations

import pytest
from scripts.create_user import provision_user
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models import Membership, Organization, Role, User
from app.infrastructure.security import normalize_email
from app.shared.exceptions.auth import EmailAlreadyRegisteredError


@pytest.mark.asyncio
async def test_provision_creates_user_org_and_owner_membership(db_session: AsyncSession) -> None:
    user, org, membership = await provision_user(
        db_session,
        email="Owner@Pilot.Example",
        password="correct horse battery staple",
        org_name="Pilot Co",
    )

    # Email normalized; org named as given.
    assert user.email == normalize_email("Owner@Pilot.Example")
    assert org.name == "Pilot Co"

    # Membership links the user to the org with the seeded 'owner' role.
    assert membership.user_id == user.id
    assert membership.organization_id == org.id
    role_row = await db_session.execute(select(Role).where(Role.id == membership.role_id))
    assert role_row.scalar_one().name == "owner"

    # Persisted on the session (register_bootstrap flushes) — exactly one of each.
    for model in (User, Organization, Membership):
        n = (await db_session.execute(select(func.count()).select_from(model))).scalar_one()
        assert n == 1, model.__name__


@pytest.mark.asyncio
async def test_provision_defaults_org_name_when_omitted(db_session: AsyncSession) -> None:
    _user, org, _m = await provision_user(
        db_session, email="solo@pilot.example", password="correct horse battery staple"
    )
    assert org.name == "solo's workspace"  # same default as the register use case


@pytest.mark.asyncio
async def test_provision_duplicate_email_fails_cleanly(db_session: AsyncSession) -> None:
    await provision_user(
        db_session,
        email="dup@pilot.example",
        password="correct horse battery staple",
        org_name="First",
    )
    with pytest.raises(EmailAlreadyRegisteredError):
        await provision_user(
            db_session,
            email="DUP@pilot.example",  # same email, different case → normalizes to the dup
            password="correct horse battery staple",
            org_name="Second",
        )
