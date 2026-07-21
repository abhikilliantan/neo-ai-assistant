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

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.documents import DocumentChunk as DocumentChunkVO
from app.infrastructure.db.models import (
    Conversation,
    Document,
    DocumentChunk,
    Membership,
    Memory,
    Message,
    Organization,
    Role,
    Session,
    User,
    UserPreference,
    Workflow,
)

# --- app-role (neo_app) repositories -----------------------------------------


class WorkflowRepository:
    """Tenant-scoped read of tenant-defined workflows (7f-2). RLS filters
    organization_id at the DB layer; the explicit WHERE keeps app-layer intent
    audit-visible, matching MemoryRepository's convention.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_enabled_for_org(self, organization_id: UUID) -> list[Workflow]:
        """Enabled, non-soft-deleted rows for the org, oldest first (stable
        registration order). Disabled / soft-deleted rows are excluded here so
        the resolution layer never has to think about them.
        """
        stmt = (
            select(Workflow)
            .where(
                Workflow.organization_id == organization_id,
                Workflow.enabled.is_(True),
                Workflow.deleted_at.is_(None),
            )
            .order_by(Workflow.created_at.asc(), Workflow.id.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())


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
        agent_name: str | None = None,
    ) -> Conversation:
        c = Conversation(
            organization_id=organization_id,
            user_id=user_id,
            title=title,
            agent_name=agent_name,
        )
        self.session.add(c)
        await self.session.flush()
        return c

    async def get_by_id(self, conversation_id: UUID) -> Conversation | None:
        return await self.session.get(Conversation, conversation_id)

    async def set_agent(self, conversation_id: UUID, agent_name: str) -> None:
        """Update the stored agent for a thread. Called when the caller
        provides an explicit body.agent that differs from what's already
        stored — the thread follows the user's latest picker choice.
        """
        c = await self.session.get(Conversation, conversation_id)
        if c is None:
            return
        c.agent_name = agent_name
        await self.session.flush()

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


class MemoryRepository:
    """Tenant-scoped. RLS filters organization_id at the DB layer; every
    method takes it explicitly so the app-layer intent is audit-visible.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        content: str,
        embedding: list[float],
        embedding_model: str,
        kind: str = "fact",
        source: str | None = None,
    ) -> Memory:
        m = Memory(
            organization_id=organization_id,
            user_id=user_id,
            content=content,
            embedding=embedding,
            embedding_model=embedding_model,
            kind=kind,
            source=source,
        )
        self.session.add(m)
        await self.session.flush()
        return m

    async def search_similar(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        query_embedding: list[float],
        limit: int = 5,
        kind: str | None = None,
        embedding_model: str | None = None,
    ) -> list[tuple[Memory, float]]:
        """Cosine-similarity ANN search, tenant + user scoped, soft-delete aware.

        Uses pgvector's `<=>` operator (SQLAlchemy: `.cosine_distance()`),
        backed by the HNSW `vector_cosine_ops` index from the migration.
        RLS applies inside the DB, so even without the explicit
        organization_id predicate a cross-tenant row would be filtered out;
        the predicate is kept for explicitness and for future EXPLAIN diffing.

        Returned similarity = 1 - cosine_distance ∈ [-1, 1] (in [0, 1] for
        L2-normalized vectors, which both mock and Voyage produce).

        `embedding_model` (6c) is an optional guard against mixing vector
        spaces: pgvector's cosine distance across rows from different models
        is numerically meaningless. When set, only rows tagged with this
        exact model are considered. Callers that embed the query themselves
        should pass the provider's reported model here.
        """
        distance = Memory.embedding.cosine_distance(query_embedding).label("distance")
        stmt = (
            select(Memory, distance)
            .where(Memory.organization_id == organization_id)
            .where(Memory.user_id == user_id)
            .where(Memory.deleted_at.is_(None))
        )
        if kind is not None:
            stmt = stmt.where(Memory.kind == kind)
        if embedding_model is not None:
            stmt = stmt.where(Memory.embedding_model == embedding_model)
        stmt = stmt.order_by(distance.asc()).limit(limit)
        rows = (await self.session.execute(stmt)).all()
        return [(memory, 1.0 - float(dist)) for memory, dist in rows]

    async def list_for_user(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        active_only: bool = True,
    ) -> list[Memory]:
        stmt = (
            select(Memory)
            .where(Memory.organization_id == organization_id)
            .where(Memory.user_id == user_id)
        )
        if active_only:
            stmt = stmt.where(Memory.deleted_at.is_(None))
        stmt = stmt.order_by(Memory.created_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_by_id(self, memory_id: UUID) -> Memory | None:
        # RLS filters cross-tenant on read; the endpoint layer still checks
        # user_id ownership so same-tenant users can't touch each other's rows.
        return await self.session.get(Memory, memory_id)

    async def soft_delete(self, memory_id: UUID) -> None:
        m = await self.session.get(Memory, memory_id)
        if m is None or m.deleted_at is not None:
            return
        m.deleted_at = datetime.now(UTC)
        await self.session.flush()


class DocumentRepository:
    """Tenant-scoped. RLS filters organization_id at the DB layer; every method
    takes it explicitly so the app-layer intent is audit-visible. Mirrors
    MemoryRepository, including the embedding_model guard on chunk search.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        organization_id: UUID,
        uploaded_by_user_id: UUID,
        filename: str,
        content_type: str,
        byte_size: int,
        full_text: str,
        status: str = "ready",
    ) -> Document:
        doc = Document(
            organization_id=organization_id,
            uploaded_by_user_id=uploaded_by_user_id,
            filename=filename,
            content_type=content_type,
            byte_size=byte_size,
            full_text=full_text,
            status=status,
        )
        self.session.add(doc)
        await self.session.flush()  # populate doc.id for chunk FKs
        return doc

    async def add_chunks(
        self,
        *,
        document_id: UUID,
        organization_id: UUID,
        chunks: list[DocumentChunkVO],
        vectors: list[list[float]],
        embedding_model: str,
    ) -> list[DocumentChunk]:
        """Insert all chunk rows in one unit of work. `strict=True` refuses a
        chunk/vector count mismatch loudly rather than persisting a skewed set.
        """
        rows: list[DocumentChunk] = []
        for chunk, vector in zip(chunks, vectors, strict=True):
            row = DocumentChunk(
                document_id=document_id,
                organization_id=organization_id,
                ordinal=chunk.ordinal,
                text=chunk.text,
                embedding=vector,
                embedding_model=embedding_model,
                char_start=chunk.position.char_start,
                char_end=chunk.position.char_end,
                page_start=chunk.position.page_start,
                page_end=chunk.position.page_end,
                section=chunk.position.section,
            )
            self.session.add(row)
            rows.append(row)
        await self.session.flush()
        return rows

    async def search_chunks(
        self,
        *,
        organization_id: UUID,
        query_embedding: list[float],
        limit: int = 5,
        embedding_model: str | None = None,
    ) -> list[tuple[DocumentChunk, float]]:
        """Cosine-similarity ANN search over chunks, tenant-scoped, soft-delete
        aware at BOTH the chunk and its parent document.

        Joins `documents` and filters `Document.deleted_at IS NULL`, so
        soft-deleting a single document row excludes all its chunks from search.

        `embedding_model` (5d guard) filters to one vector space: cosine distance
        across rows from different models is numerically meaningless. When set,
        only rows tagged with this exact model are considered — a model swap
        can't poison results with foreign-vector-space rows.
        """
        distance = DocumentChunk.embedding.cosine_distance(query_embedding).label("distance")
        stmt = (
            select(DocumentChunk, distance)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(DocumentChunk.organization_id == organization_id)
            .where(DocumentChunk.deleted_at.is_(None))
            .where(Document.deleted_at.is_(None))
        )
        if embedding_model is not None:
            stmt = stmt.where(DocumentChunk.embedding_model == embedding_model)
        stmt = stmt.order_by(distance.asc()).limit(limit)
        rows = (await self.session.execute(stmt)).all()
        return [(chunk, 1.0 - float(dist)) for chunk, dist in rows]

    async def get_document(self, document_id: UUID) -> Document | None:
        return await self.session.get(Document, document_id)

    async def list_chunks(
        self, document_id: UUID, *, active_only: bool = True
    ) -> list[DocumentChunk]:
        stmt = select(DocumentChunk).where(DocumentChunk.document_id == document_id)
        if active_only:
            stmt = stmt.where(DocumentChunk.deleted_at.is_(None))
        stmt = stmt.order_by(DocumentChunk.ordinal.asc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def soft_delete(self, document_id: UUID) -> None:
        doc = await self.session.get(Document, document_id)
        if doc is None or doc.deleted_at is not None:
            return
        doc.deleted_at = datetime.now(UTC)
        await self.session.flush()


class UserPreferenceRepository:
    """Tenant-scoped. Upserts on the composite (org, user, key) unique constraint."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def upsert(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        key: str,
        value: object,
    ) -> UserPreference:
        stmt = pg_insert(UserPreference).values(
            organization_id=organization_id,
            user_id=user_id,
            key=key,
            value=value,
        )
        # ORM's onupdate=func.now() doesn't fire on raw INSERT ... ON CONFLICT,
        # so set updated_at explicitly on the conflict branch.
        stmt = stmt.on_conflict_do_update(
            constraint="uq_user_preferences_org_user_key",
            set_={"value": stmt.excluded.value, "updated_at": func.now()},
        )
        await self.session.execute(stmt)
        await self.session.flush()
        pref = await self.get(organization_id=organization_id, user_id=user_id, key=key)
        # RLS-scoped SELECT after an RLS-scoped INSERT must find the row.
        assert pref is not None
        return pref

    async def get(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
        key: str,
    ) -> UserPreference | None:
        stmt = (
            select(UserPreference)
            .where(UserPreference.organization_id == organization_id)
            .where(UserPreference.user_id == user_id)
            .where(UserPreference.key == key)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_for_user(
        self,
        *,
        organization_id: UUID,
        user_id: UUID,
    ) -> list[UserPreference]:
        stmt = (
            select(UserPreference)
            .where(UserPreference.organization_id == organization_id)
            .where(UserPreference.user_id == user_id)
            .order_by(UserPreference.key.asc())
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
