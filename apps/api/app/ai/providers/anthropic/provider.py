"""Anthropic (Claude) chat provider — complete() and stream().

Both methods share `_prepare_kwargs` (system-prompt extraction + user/assistant
mapping) and `_translate` (SDK exception → domain exception). `complete()`'s
public behavior is unchanged from 3a — the 3a unit tests remain the proof.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from anthropic import (
    APIConnectionError,
    APIError,
    APIStatusError,
    APITimeoutError,
    AsyncAnthropic,
    AuthenticationError,
    PermissionDeniedError,
    RateLimitError,
)

from app.application.ports.chat import (
    ChatCompletion,
    ChatMessage,
    ChatStreamEvent,
    ChatUsage,
)
from app.shared.exceptions.ai import (
    ProviderAPIError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)

_SDK_EXCEPTIONS: tuple[type[BaseException], ...] = (
    AuthenticationError,
    PermissionDeniedError,
    RateLimitError,
    APIConnectionError,
    APITimeoutError,
    APIStatusError,
    APIError,
)


class AnthropicProvider:
    def __init__(
        self,
        *,
        client: AsyncAnthropic,
        model: str,
        max_tokens: int,
    ) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens

    def _prepare_kwargs(
        self,
        messages: list[ChatMessage],
        model: str | None,
        temperature: float,
    ) -> dict[str, Any]:
        """System extraction + user/assistant mapping — shared by complete + stream.

        Anthropic takes the system prompt as a top-level `system=` param;
        it is NOT a message role. Multiple system entries are joined with
        a blank line. The `system` key is OMITTED entirely (not None) when
        there are no system messages, avoiding the SDK's NOT_GIVEN sentinel.
        """
        system_parts = [m.content for m in messages if m.role == "system"]
        api_messages = [
            {"role": m.role, "content": m.content}
            for m in messages
            if m.role in ("user", "assistant")
        ]
        kwargs: dict[str, Any] = {
            "model": model or self._model,
            "max_tokens": self._max_tokens,
            "temperature": temperature,
            "messages": api_messages,
        }
        if system_parts:
            kwargs["system"] = "\n\n".join(system_parts)
        return kwargs

    @staticmethod
    def _translate(exc: BaseException) -> BaseException:
        """Map an Anthropic SDK exception to the corresponding domain exception."""
        if isinstance(exc, (AuthenticationError, PermissionDeniedError)):
            return ProviderAuthError(str(exc))
        if isinstance(exc, RateLimitError):
            return ProviderRateLimitError(str(exc))
        if isinstance(exc, (APIConnectionError, APITimeoutError)):
            return ProviderUnavailableError(str(exc))
        if isinstance(exc, (APIStatusError, APIError)):
            return ProviderAPIError(str(exc))
        return exc

    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> ChatCompletion:
        kwargs = self._prepare_kwargs(messages, model, temperature)
        try:
            response = await self._client.messages.create(**kwargs)
        except _SDK_EXCEPTIONS as e:
            raise self._translate(e) from e

        text = "".join(
            getattr(block, "text", "")
            for block in response.content
            if getattr(block, "type", None) == "text"
        )
        return ChatCompletion(
            content=text,
            model=response.model,
            usage=ChatUsage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
            ),
            finish_reason=response.stop_reason or "stop",
        )

    async def stream(
        self,
        *,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[ChatStreamEvent]:
        kwargs = self._prepare_kwargs(messages, model, temperature)
        try:
            async with self._client.messages.stream(**kwargs) as s:
                async for text_delta in s.text_stream:
                    yield ChatStreamEvent(type="delta", content=text_delta)
                final = await s.get_final_message()
        except _SDK_EXCEPTIONS as e:
            raise self._translate(e) from e

        yield ChatStreamEvent(
            type="done",
            model=final.model,
            usage=ChatUsage(
                prompt_tokens=final.usage.input_tokens,
                completion_tokens=final.usage.output_tokens,
            ),
            finish_reason=final.stop_reason or "stop",
        )

    async def close(self) -> None:
        await self._client.close()
