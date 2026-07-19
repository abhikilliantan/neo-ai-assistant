"""Concrete repositories. Caller (use case) owns the transaction."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models import (
    Membership,
    Organization,
    Role,
    Session,
    User,
)


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(self, *, email: str, password_hash: str) -> User:
        user = User(email=email, password_hash=password_hash)
        self.session.add(user)
        await self.session.flush()
        return user

    async def get_by_email_normalized(self, email: str) -> User | None:
        # Column stores whatever was written; normalize_email at write time
        # keeps this exact-match consistent with the lower(email) unique index.
        stmt = select(User).where(User.email == email)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_id(self, user_id: UUID) -> User | None:
        return await self.session.get(User, user_id)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "org"


class OrganizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_with_unique_slug(self, name: str) -> Organization:
        base = _slugify(name)
        # ponytail: precheck-then-insert; unique constraint is final arbiter.
        # Bounded retry — a tight race would hit the DB constraint, which we let raise.
        for suffix in ("", *(f"-{i}" for i in range(2, 100))):
            candidate = f"{base}{suffix}"
            existing = (
                await self.session.execute(
                    select(Organization.id).where(Organization.slug == candidate)
                )
            ).first()
            if existing is None:
                org = Organization(name=name, slug=candidate)
                self.session.add(org)
                await self.session.flush()
                return org
        raise RuntimeError(f"could not find a free slug for {name!r} after 99 tries")


class MembershipRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        user_id: UUID,
        organization_id: UUID,
        role_id: UUID,
        status: str = "active",
    ) -> Membership:
        m = Membership(
            user_id=user_id,
            organization_id=organization_id,
            role_id=role_id,
            status=status,
        )
        self.session.add(m)
        await self.session.flush()
        return m

    async def list_for_user(self, user_id: UUID, *, active_only: bool = True) -> list[Membership]:
        stmt = select(Membership).where(Membership.user_id == user_id)
        if active_only:
            stmt = stmt.where(Membership.status == "active")
        stmt = stmt.order_by(Membership.created_at.asc())
        return list((await self.session.execute(stmt)).scalars().all())


class RoleRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_name(self, name: str) -> Role | None:
        stmt = select(Role).where(Role.name == name)
        return (await self.session.execute(stmt)).scalar_one_or_none()


class SessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        user_id: UUID,
        refresh_token_hash: str,
        expires_at: datetime,
        user_agent: str | None = None,
        ip_address: str | None = None,
    ) -> Session:
        s = Session(
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            expires_at=expires_at,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self.session.add(s)
        await self.session.flush()
        return s

    async def get_by_refresh_hash(self, refresh_token_hash: str) -> Session | None:
        stmt = select(Session).where(Session.refresh_token_hash == refresh_token_hash)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def revoke(self, session_id: UUID) -> None:
        s = await self.session.get(Session, session_id)
        if s is not None and s.revoked_at is None:
            s.revoked_at = datetime.now(UTC)
            await self.session.flush()
