"""Read-only conversation endpoints.

Both routes run under TenantSessionDep so Postgres RLS filters cross-tenant
rows before anything else — an unknown or foreign conversation_id therefore
collapses to a NotFoundError (404) with no existence oracle.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter

from app.ai.agents import DEFAULT_AGENT_NAME
from app.infrastructure.db.repositories import ConversationRepository, MessageRepository
from app.presentation.http.deps import CurrentTenantDep, CurrentUserDep, TenantSessionDep
from app.presentation.http.schemas.chat import (
    ConversationDetail,
    ConversationMessageOut,
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
    if conv is None:
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
