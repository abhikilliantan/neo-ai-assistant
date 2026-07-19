"""HTTP request/response schemas for /api/v1/chat."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from app.application.ports.chat import ChatMessage, ChatUsage


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)

    @field_validator("messages")
    @classmethod
    def _at_least_one_user_message(cls, value: list[ChatMessage]) -> list[ChatMessage]:
        if not any(m.role == "user" for m in value):
            raise ValueError("at least one user message is required")
        return value


class ChatResponse(BaseModel):
    message: ChatMessage
    model: str
    usage: ChatUsage | None = None
