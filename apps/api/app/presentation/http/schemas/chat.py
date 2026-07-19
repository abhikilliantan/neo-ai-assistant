"""HTTP request/response schemas for /api/v1/chat + /api/v1/conversations."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.application.ports.chat import ChatMessage, ChatUsage


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)
    conversation_id: UUID | None = None

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


class ConversationSummary(BaseModel):
    id: UUID
    title: str | None
    last_message_at: datetime | None
    created_at: datetime


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
    messages: list[ConversationMessageOut]
