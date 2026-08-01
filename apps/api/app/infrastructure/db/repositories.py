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
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, insert, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from app.application.ports.documents import DocumentChunk as DocumentChunkVO
from app.application.ports.repositories import DatasetColumnSpec, DatasetRowData
from app.infrastructure.db.models import (
    ApiKey,
    Company,
    Conversation,
    Dataset,
    DatasetColumn,
    DatasetRow,
    Department,
    Document,
    DocumentChunk,
    Membership,
    Memory,
    Message,
    Organization,
    Project,
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


class ApiKeyRepository:
    """Tenant-scoped API-key MANAGEMENT (create / list / revoke). Used with the
    RLS-enforced app session, so it only ever touches the caller's own org.

    Auth-time lookup is deliberately NOT here: matching a raw key to its row is a
    cross-tenant read (the tenant is inside the row you're trying to find), so it
    lives on SystemRepository (privileged) — exactly like login looks up users by
    email before any tenant is known.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        organization_id: UUID,
        name: str,
        key_prefix: str,
        key_hash: str,
        scopes: list[str],
    ) -> ApiKey:
        key = ApiKey(
            organization_id=organization_id,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes=scopes,
        )
        self.session.add(key)
        await self.session.flush()
        return key

    async def list_for_org(
        self, organization_id: UUID, *, active_only: bool = True
    ) -> list[ApiKey]:
        stmt = select(ApiKey).where(ApiKey.organization_id == organization_id)
        if active_only:
            stmt = stmt.where(ApiKey.revoked_at.is_(None))
        stmt = stmt.order_by(ApiKey.created_at.desc(), ApiKey.id.desc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_by_id(self, api_key_id: UUID) -> ApiKey | None:
        # RLS hides cross-tenant rows on read; a None here means unknown OR
        # another tenant's key — the endpoint collapses both to 404.
        return await self.session.get(ApiKey, api_key_id)

    async def revoke(self, api_key_id: UUID) -> None:
        """Idempotent — no-op on missing/already-revoked."""
        key = await self.session.get(ApiKey, api_key_id)
        if key is not None and key.revoked_at is None:
            key.revoked_at = datetime.now(UTC)
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

    async def soft_delete(self, conversation_id: UUID) -> None:
        """Idempotent soft-delete. Ownership is enforced at the endpoint layer
        (fetch → check user_id) exactly like MemoryRepository.soft_delete — this
        takes only an id, so RLS alone would let a same-tenant user delete
        another's thread; the caller MUST verify ownership first."""
        c = await self.session.get(Conversation, conversation_id)
        if c is None or c.deleted_at is not None:
            return
        c.deleted_at = datetime.now(UTC)
        await self.session.flush()

    async def rename(self, conversation_id: UUID, *, title: str) -> Conversation | None:
        """Set the thread title. Same ownership caveat as soft_delete — the
        endpoint checks user_id first. Returns the updated row (None if gone)."""
        c = await self.session.get(Conversation, conversation_id)
        if c is None:
            return None
        c.title = title
        await self.session.flush()
        return c


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
        extraction_method: str = "text",
        storage_key: str | None = None,
        storage_backend: str | None = None,
        content_sha256: str | None = None,
    ) -> Document:
        doc = Document(
            organization_id=organization_id,
            uploaded_by_user_id=uploaded_by_user_id,
            filename=filename,
            content_type=content_type,
            byte_size=byte_size,
            full_text=full_text,
            status=status,
            extraction_method=extraction_method,
            storage_key=storage_key,
            storage_backend=storage_backend,
            content_sha256=content_sha256,
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
        chunker: str,
    ) -> list[DocumentChunk]:
        """Insert all chunk rows in one unit of work. `strict=True` refuses a
        chunk/vector count mismatch loudly rather than persisting a skewed set.
        `chunker` is the algorithm's name+version (ADR 0001 Decision 8).
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
                chunker=chunker,
                char_start=chunk.position.char_start,
                char_end=chunk.position.char_end,
                page_start=chunk.position.page_start,
                page_end=chunk.position.page_end,
                section=chunk.position.section,
                ocr_confidence=chunk.ocr_confidence,
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

        The parent `Document` is eager-loaded via `contains_eager` on the same
        join used for the soft-delete filter, so a caller can read
        `chunk.document.filename` after the session closes (8d citations) without
        a lazy load — `expire_on_commit=False` keeps it live post-commit.
        """
        distance = DocumentChunk.embedding.cosine_distance(query_embedding).label("distance")
        stmt = (
            select(DocumentChunk, distance)
            .join(DocumentChunk.document)
            .options(contains_eager(DocumentChunk.document))
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

    async def list_for_org_with_chunk_counts(
        self, organization_id: UUID, *, active_only: bool = True
    ) -> list[tuple[Document, int]]:
        """Documents for the org, newest first, each with its live chunk count.

        One query (LEFT JOIN a grouped count subquery) instead of N+1 counts.
        RLS scopes to the tenant; the explicit organization_id keeps app-layer
        intent audit-visible, matching the other repos.
        """
        counts = (
            select(
                DocumentChunk.document_id.label("document_id"),
                func.count().label("n"),
            )
            .where(DocumentChunk.deleted_at.is_(None))
            .group_by(DocumentChunk.document_id)
            .subquery()
        )
        stmt = (
            select(Document, func.coalesce(counts.c.n, 0))
            .outerjoin(counts, counts.c.document_id == Document.id)
            .where(Document.organization_id == organization_id)
        )
        if active_only:
            stmt = stmt.where(Document.deleted_at.is_(None))
        stmt = stmt.order_by(Document.created_at.desc(), Document.id.desc())
        rows = (await self.session.execute(stmt)).all()
        return [(doc, int(n)) for doc, n in rows]

    async def count_chunks(self, document_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .where(DocumentChunk.deleted_at.is_(None))
        )
        return int((await self.session.execute(stmt)).scalar_one())

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

    async def find_api_keys_by_prefix(self, key_prefix: str) -> list[ApiKey]:
        """Cross-tenant lookup by prefix for service-key auth — the pre-tenant
        step, exactly like find_user_by_email for login. Returns ALL matches
        (prefix collisions are astronomically unlikely but a list keeps this from
        ever 500ing on one); the use case verifies each by full-hash compare and
        picks the match. Includes revoked/expired rows — the use case rejects
        those so the failure reason stays precise.
        """
        stmt = select(ApiKey).where(ApiKey.key_prefix == key_prefix)
        return list((await self.session.execute(stmt)).scalars().all())

    async def touch_api_key_last_used(self, api_key_id: UUID) -> None:
        """Stamp last_used_at at auth time. Runs on the privileged session (the
        auth lookup already does), so no tenant GUC is needed here."""
        key = await self.session.get(ApiKey, api_key_id)
        if key is not None:
            key.last_used_at = datetime.now(UTC)
            await self.session.flush()

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


class DatasetRepository:
    """Tenant-scoped structured-dataset persistence (Capability 1, Slice 1a).

    Storage ONLY — create/read/bulk-insert/soft-delete. NO query/aggregation
    (that SAFE constrained-query surface is 1c). RLS filters organization_id at
    the DB layer, but `list_datasets` ALSO filters it explicitly: the app
    currently connects as a BYPASSRLS superuser, so the repo must not lean on RLS
    for tenant scoping. Child rows (columns, data rows) are stamped with the
    organization_id the caller passes, matching DocumentRepository.add_chunks.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create_dataset(
        self,
        *,
        organization_id: UUID,
        name: str,
        description: str | None = None,
        source_document_id: UUID | None = None,
        sheet_name: str | None = None,
        created_by: UUID | None = None,
        status: str = "ready",
    ) -> Dataset:
        dataset = Dataset(
            organization_id=organization_id,
            name=name,
            description=description,
            source_document_id=source_document_id,
            sheet_name=sheet_name,
            created_by=created_by,
            status=status,
        )
        self.session.add(dataset)
        await self.session.flush()  # populate dataset.id for child FKs
        return dataset

    async def add_columns(
        self,
        *,
        dataset_id: UUID,
        organization_id: UUID,
        columns: Sequence[DatasetColumnSpec],
    ) -> list[DatasetColumn]:
        rows = [
            DatasetColumn(
                dataset_id=dataset_id,
                organization_id=organization_id,
                name=c.name,
                key=c.key,
                data_type=c.data_type,
                position=c.position,
                nullable=c.nullable,
                semantic_role=c.semantic_role,
            )
            for c in columns
        ]
        self.session.add_all(rows)
        await self.session.flush()
        return rows

    async def bulk_insert_rows(
        self,
        *,
        dataset_id: UUID,
        organization_id: UUID,
        rows: Sequence[DatasetRowData],
        start_index: int = 0,
    ) -> int:
        """Insert all rows in ONE executemany. `row_index` is assigned by position
        within this call (start_index + offset). Returns the number inserted."""
        payloads = [
            {
                "dataset_id": dataset_id,
                "organization_id": organization_id,
                "row_index": start_index + offset,
                "data": dict(data),
            }
            for offset, data in enumerate(rows)
        ]
        if not payloads:
            return 0
        await self.session.execute(insert(DatasetRow), payloads)
        return len(payloads)

    async def get_dataset(self, dataset_id: UUID) -> Dataset | None:
        return await self.session.get(Dataset, dataset_id)

    async def find_active_dataset_by_name(self, organization_id: UUID, name: str) -> Dataset | None:
        """The tenant's active (not soft-deleted) dataset with this exact name, if
        any — backs the 1b duplicate-name guard. Newest wins if the tenant already
        has duplicates from before the guard existed."""
        stmt = (
            select(Dataset)
            .where(Dataset.organization_id == organization_id)
            .where(Dataset.name == name)
            .where(Dataset.deleted_at.is_(None))
            .order_by(Dataset.created_at.desc(), Dataset.id.desc())
            .limit(1)
        )
        return (await self.session.execute(stmt)).scalars().first()

    async def list_datasets(
        self, organization_id: UUID, *, active_only: bool = True
    ) -> list[Dataset]:
        """Tenant-scoped, newest-first. Explicit organization_id filter (NOT RLS)
        and excludes soft-deleted rows when active_only."""
        stmt = select(Dataset).where(Dataset.organization_id == organization_id)
        if active_only:
            stmt = stmt.where(Dataset.deleted_at.is_(None))
        stmt = stmt.order_by(Dataset.created_at.desc(), Dataset.id.desc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_columns(self, dataset_id: UUID) -> list[DatasetColumn]:
        stmt = (
            select(DatasetColumn)
            .where(DatasetColumn.dataset_id == dataset_id)
            .where(DatasetColumn.deleted_at.is_(None))
            .order_by(DatasetColumn.position.asc(), DatasetColumn.id.asc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def count_rows(self, dataset_id: UUID) -> int:
        stmt = (
            select(func.count())
            .select_from(DatasetRow)
            .where(DatasetRow.dataset_id == dataset_id)
            .where(DatasetRow.deleted_at.is_(None))
        )
        return int((await self.session.execute(stmt)).scalar_one())

    async def update_row_count(self, dataset_id: UUID, n: int) -> None:
        dataset = await self.session.get(Dataset, dataset_id)
        if dataset is None:
            return
        dataset.row_count = n
        await self.session.flush()

    async def soft_delete_dataset(self, dataset_id: UUID) -> None:
        dataset = await self.session.get(Dataset, dataset_id)
        if dataset is None or dataset.deleted_at is not None:
            return
        dataset.deleted_at = datetime.now(UTC)
        await self.session.flush()

    async def hard_delete_rows(self, *, dataset_id: UUID, organization_id: UUID) -> int:
        """Permanently remove a dataset's rows (1b re-ingest/replace). Tenant-scoped
        by organization_id so a replace can never wipe another tenant's rows.
        Returns the number deleted."""
        result = await self.session.execute(
            delete(DatasetRow)
            .where(DatasetRow.dataset_id == dataset_id)
            .where(DatasetRow.organization_id == organization_id)
        )
        return result.rowcount or 0  # type: ignore[attr-defined]  # CursorResult at runtime

    async def hard_delete_columns(self, *, dataset_id: UUID, organization_id: UUID) -> int:
        """Permanently remove a dataset's columns (1b re-ingest/replace).
        Tenant-scoped by organization_id. Returns the number deleted."""
        result = await self.session.execute(
            delete(DatasetColumn)
            .where(DatasetColumn.dataset_id == dataset_id)
            .where(DatasetColumn.organization_id == organization_id)
        )
        return result.rowcount or 0  # type: ignore[attr-defined]  # CursorResult at runtime


class HierarchyRepository:
    """Tenant-scoped Company/Department/Project persistence (Neo Command Center,
    Slice 1). Reads for the Overview endpoint + creates for the seed script. Every
    list filters organization_id explicitly (NOT RLS) and excludes soft-deleted
    rows, matching DatasetRepository — the app runs as a BYPASSRLS superuser.
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_companies(
        self, organization_id: UUID, *, active_only: bool = True
    ) -> list[Company]:
        stmt = select(Company).where(Company.organization_id == organization_id)
        if active_only:
            stmt = stmt.where(Company.deleted_at.is_(None))
        stmt = stmt.order_by(Company.created_at.asc(), Company.id.asc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_company(self, company_id: UUID) -> Company | None:
        return await self.session.get(Company, company_id)

    async def list_departments_for_company(
        self, company_id: UUID, *, active_only: bool = True
    ) -> list[Department]:
        stmt = select(Department).where(Department.company_id == company_id)
        if active_only:
            stmt = stmt.where(Department.deleted_at.is_(None))
        stmt = stmt.order_by(
            Department.position.asc(), Department.created_at.asc(), Department.id.asc()
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_projects_for_departments(
        self, department_ids: Sequence[UUID], *, active_only: bool = True
    ) -> list[Project]:
        """All projects across the given departments in ONE query (avoids the
        per-department N+1); the caller groups by department_id in memory."""
        if not department_ids:
            return []
        stmt = select(Project).where(Project.department_id.in_(department_ids))
        if active_only:
            stmt = stmt.where(Project.deleted_at.is_(None))
        stmt = stmt.order_by(Project.position.asc(), Project.created_at.asc(), Project.id.asc())
        return list((await self.session.execute(stmt)).scalars().all())

    async def create_company(
        self, *, organization_id: UUID, name: str, created_by: UUID | None = None
    ) -> Company:
        company = Company(organization_id=organization_id, name=name, created_by=created_by)
        self.session.add(company)
        await self.session.flush()
        return company

    async def create_department(
        self,
        *,
        organization_id: UUID,
        company_id: UUID,
        name: str,
        icon: str | None = None,
        position: int = 0,
    ) -> Department:
        dept = Department(
            organization_id=organization_id,
            company_id=company_id,
            name=name,
            icon=icon,
            position=position,
        )
        self.session.add(dept)
        await self.session.flush()
        return dept

    async def create_project(
        self,
        *,
        organization_id: UUID,
        department_id: UUID,
        name: str,
        description: str | None = None,
        dataset_id: UUID | None = None,
        status_config: Mapping[str, object] | None = None,
        position: int = 0,
    ) -> Project:
        project = Project(
            organization_id=organization_id,
            department_id=department_id,
            name=name,
            description=description,
            dataset_id=dataset_id,
            status_config=dict(status_config) if status_config is not None else None,
            position=position,
        )
        self.session.add(project)
        await self.session.flush()
        return project
