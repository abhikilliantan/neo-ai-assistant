"""Conversation endpoints — read (org-scoped) + manage (owner-scoped).

All routes run under TenantSessionDep so Postgres RLS filters cross-tenant rows
before anything else — an unknown or foreign conversation_id collapses to a
NotFoundError (404) with no existence oracle.

The reads (list / get) are ORG-scoped: `list_for_org` returns every conversation
the organisation owns, and get only checks the tenant. The MUTATIONS
(delete / rename) are OWNER-scoped: RLS alone would let a same-tenant user delete
or rename another user's thread, so — mirroring DELETE /memories/{id} — we fetch
first, verify `conversation.user_id == current_user.id`, and collapse unknown /
cross-tenant / same-tenant-other-user all to 404.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status
from fastapi.responses import Response

from app.ai.agents import DEFAULT_AGENT_NAME
from app.infrastructure.db.repositories import ConversationRepository, MessageRepository
from app.presentation.http.deps import CurrentTenantDep, CurrentUserDep, TenantSessionDep
from app.presentation.http.schemas.chat import (
    ConversationDetail,
    ConversationMessageOut,
    ConversationRenameRequest,
    ConversationSummary,
)
from app.shared.exceptions.auth import AuthenticationError
from app.shared.exceptions.common import NotFoundError

router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(
    _user: CurrentUserDep,
    tenant_id: CurrentTenantDep,
    session: TenantSessionDep,
) -> list[ConversationSummary]:
    if tenant_id is None:
        raise AuthenticationError("user has no active tenant")
    rows = await ConversationRepository(session).list_for_org(tenant_id)
    return [
        ConversationSummary(
            id=c.id,
            title=c.title,
            last_message_at=c.last_message_at,
            created_at=c.created_at,
        )
        for c in rows
    ]


@router.get("/{conversation_id}", response_model=ConversationDetail)
async def get_conversation(
    conversation_id: UUID,
    _user: CurrentUserDep,
    tenant_id: CurrentTenantDep,
    session: TenantSessionDep,
) -> ConversationDetail:
    if tenant_id is None:
        raise AuthenticationError("user has no active tenant")
    conv = await ConversationRepository(session).get_by_id(conversation_id)
    # `get_by_id` (session.get) does NOT filter soft-deletes, so a deleted thread
    # must 404 here too — otherwise a "deleted" conversation stays readable by id
    # while the list correctly hides it.
    if conv is None or conv.deleted_at is not None:
        raise NotFoundError("conversation not found")
    msgs = await MessageRepository(session).list_for_conversation(conversation_id)
    return ConversationDetail(
        id=conv.id,
        title=conv.title,
        last_message_at=conv.last_message_at,
        created_at=conv.created_at,
        # 6j: NULL means "never set" — resolve to runtime default at read.
        agent=conv.agent_name or DEFAULT_AGENT_NAME,
        messages=[
            ConversationMessageOut(
                id=m.id,
                role=m.role,
                content=m.content,
                model=m.model,
                created_at=m.created_at,
            )
            for m in msgs
        ],
    )


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: UUID,
    user: CurrentUserDep,
    tenant_id: CurrentTenantDep,
    session: TenantSessionDep,
) -> Response:
    if tenant_id is None:
        raise AuthenticationError("user has no active tenant")
    repo = ConversationRepository(session)
    conv = await repo.get_by_id(conversation_id)
    # None → unknown id OR cross-tenant (RLS-hidden). Wrong user_id → same
    # tenant, someone else's thread. Already-deleted → gone. All collapse to 404
    # (no existence oracle).
    if conv is None or conv.user_id != user.id or conv.deleted_at is not None:
        raise NotFoundError("conversation not found")
    await repo.soft_delete(conversation_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{conversation_id}", response_model=ConversationSummary)
async def rename_conversation(
    conversation_id: UUID,
    body: ConversationRenameRequest,
    user: CurrentUserDep,
    tenant_id: CurrentTenantDep,
    session: TenantSessionDep,
) -> ConversationSummary:
    if tenant_id is None:
        raise AuthenticationError("user has no active tenant")
    repo = ConversationRepository(session)
    conv = await repo.get_by_id(conversation_id)
    if conv is None or conv.user_id != user.id or conv.deleted_at is not None:
        raise NotFoundError("conversation not found")
    updated = await repo.rename(conversation_id, title=body.title)
    assert updated is not None  # just fetched under the same session
    return ConversationSummary(
        id=updated.id,
        title=updated.title,
        last_message_at=updated.last_message_at,
        created_at=updated.created_at,
    )
