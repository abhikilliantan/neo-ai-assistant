"""Concrete repositories.

Two flavors, wired via distinct FastAPI session deps:
  - `UserRepository` / `SessionRepository` — used with `AppSessionDep`
    (neo_app, RLS-enforced). Only touch global or tenant-scoped tables
    where either no RLS applies OR the caller has set the tenant GUC.
  - `SystemRepository` — used with `SystemSessionDep` (neo, privileged).
    The ONLY code path that goes cross-tenant. Deliberately tiny.

Caller (dep) owns the transaction; repositories just flush.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models import (
    Conversation,
    Membership,
    Message,
    Organization,
    Role,
    Session,
    User,
)

# --- app-role (neo_app) repositories -----------------------------------------


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        return await self.session.get(User, user_id)


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


class ConversationRepository:
    """Tenant-scoped. RLS filters organization_id at the DB layer, but every
    method still takes organization_id explicitly so the app-layer intent is
    audit-visible.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        title: str | None = None,
    ) -> Conversation:
        c = Conversation(organization_id=organization_id, user_id=user_id, title=title)
        self.session.add(c)
        await self.session.flush()
        return c

    async def get_by_id(self, conversation_id: UUID) -> Conversation | None:
        return await self.session.get(Conversation, conversation_id)

    async def list_for_org(
        self, organization_id: UUID, *, active_only: bool = True
    ) -> list[Conversation]:
        stmt = select(Conversation).where(Conversation.organization_id == organization_id)
        if active_only:
            stmt = stmt.where(Conversation.deleted_at.is_(None))
        stmt = stmt.order_by(
            Conversation.last_message_at.desc().nullslast(),
            Conversation.created_at.desc(),
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def touch(self, conversation_id: UUID) -> None:
        c = await self.session.get(Conversation, conversation_id)
        if c is None:
            return
        c.last_message_at = datetime.now(UTC)
        await self.session.flush()


class MessageRepository:
    """Tenant-scoped append-only log. Callers must pass organization_id
    matching the parent conversation — WITH CHECK enforces the same on write.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        *,
        organization_id: UUID,
        conversation_id: UUID,
        role: str,
        content: str,
        model: str | None = None,
        prompt_tokens: int | None = None,
        completion_tokens: int | None = None,
        finish_reason: str | None = None,
    ) -> Message:
        m = Message(
            organization_id=organization_id,
            conversation_id=conversation_id,
            role=role,
            content=content,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            finish_reason=finish_reason,
        )
        self.session.add(m)
        await self.session.flush()
        return m

    async def list_for_conversation(self, conversation_id: UUID) -> list[Message]:
        # id.asc() is a final tiebreaker for the astronomically-unlikely
        # clock_timestamp() tie; the (conversation_id, created_at) index
        # still drives the sort.
        stmt = (
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())


# --- system-role (neo) repository --------------------------------------------


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug or "org"


class SystemRepository:
    """Privileged surface. THE ONLY cross-tenant code path.

    Three ops:
      - find_user_by_email        — pre-tenant user lookup (login/register)
      - list_memberships_for_user — cross-tenant read to pick active org
      - register_bootstrap        — atomic (user + org + first membership)

    Adding an operation here widens the auditable surface — do it only
    when a real requirement demands cross-tenant access at the DB layer.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def find_user_by_email(self, email_normalized: str) -> User | None:
        stmt = select(User).where(User.email == email_normalized)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_memberships_for_user(
        self, user_id: UUID, *, active_only: bool = True
    ) -> list[Membership]:
        stmt = select(Membership).where(Membership.user_id == user_id)
        if active_only:
            stmt = stmt.where(Membership.status == "active")
        stmt = stmt.order_by(Membership.created_at.asc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def register_bootstrap(
        self,
        *,
        email_normalized: str,
        password_hash: str,
        org_name: str,
        role_name: str = "owner",
    ) -> tuple[User, Organization, Membership]:
        """Create user + org + first membership atomically (single txn on neo)."""
        role = (
            await self.session.execute(select(Role).where(Role.name == role_name))
        ).scalar_one_or_none()
        if role is None:
            raise RuntimeError(f"system role {role_name!r} is missing; seed data not applied")

        user = User(email=email_normalized, password_hash=password_hash)
        self.session.add(user)
        try:
            await self.session.flush()
        except IntegrityError as e:
            # Race with a concurrent register — surface as domain-level dup.
            from app.shared.exceptions.auth import EmailAlreadyRegisteredError

            raise EmailAlreadyRegisteredError(email_normalized) from e

        base = _slugify(org_name)
        for suffix in ("", *(f"-{i}" for i in range(2, 100))):
            candidate = f"{base}{suffix}"
            existing = (
                await self.session.execute(
                    select(Organization.id).where(Organization.slug == candidate)
                )
            ).first()
            if existing is None:
                org = Organization(name=org_name, slug=candidate)
                self.session.add(org)
                await self.session.flush()
                break
        else:
            raise RuntimeError(f"could not find a free slug for {org_name!r}")

        membership = Membership(user_id=user.id, organization_id=org.id, role_id=role.id)
        self.session.add(membership)
        await self.session.flush()
        return user, org, membership
