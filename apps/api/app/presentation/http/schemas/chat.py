"""HTTP request/response schemas for /api/v1/chat + /api/v1/conversations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.application.ports.chat import ChatMessage, ChatUsage
from app.application.ports.tools import ToolInvocation


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)
    conversation_id: UUID | None = None
    # Optional agent name (6h). Omitted / null → the default "assistant"
    # agent (byte-for-byte pre-6h behavior). Unknown names surface as a
    # 404 from the endpoint — we can't statically validate here because the
    # valid set lives in the runtime registry.
    agent: str | None = None

    @field_validator("messages")
    @classmethod
    def _last_message_must_be_user(cls, value: list[ChatMessage]) -> list[ChatMessage]:
        # Stricter than "≥1 user message" — the last message must be a user
        # message, because that's the one we persist as the newest user turn
        # and the one the provider is being asked to respond to.
        if not value or value[-1].role != "user":
            raise ValueError("the last message must be a user message")
        return value


class ChatResponse(BaseModel):
    conversation_id: UUID
    message: ChatMessage
    model: str
    usage: ChatUsage | None = None
    # Live signal for the UI: tools the provider ran during THIS turn. Empty
    # list when no tool loop engaged — additive default keeps the no-tools
    # response byte-for-byte identical. NEVER persisted; reloading the
    # conversation via GET /conversations/{id} shows only [user, assistant].
    tool_invocations: list[ToolInvocation] = Field(default_factory=list)
    # Resolved agent name (6i-1). Always the name the server actually used:
    # `body.agent or "assistant"`. Not persisted onto message rows this
    # slice — per-conversation persistence lands in 6j.
    agent: str


class ConversationSummary(BaseModel):
    id: UUID
    title: str | None
    last_message_at: datetime | None
    created_at: datetime


class ConversationRenameRequest(BaseModel):
    # Trimmed, bounded to the column width (String(255)). A blank title is not a
    # rename — min_length=1 after the validator strips whitespace.
    title: str = Field(min_length=1, max_length=255)

    @field_validator("title")
    @classmethod
    def _strip(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("title must not be blank")
        return stripped


class ConversationMessageOut(BaseModel):
    id: UUID
    role: str
    content: str
    model: str | None
    created_at: datetime


class ConversationDetail(BaseModel):
    id: UUID
    title: str | None
    last_message_at: datetime | None
    created_at: datetime
    # 6j: effective per-thread agent. Resolved server-side to `stored value
    # or DEFAULT_AGENT_NAME` so the UI never has a None branch when
    # restoring the picker. Agent belongs to the thread — messages stay
    # agent-free (per-message would be a later slice if useful).
    agent: str
    messages: list[ConversationMessageOut]
