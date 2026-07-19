"""Anthropic (Claude) chat provider — non-streaming.

Streaming lives in phase 3b via a separate `stream()` method on the Protocol;
`complete()` here stays untouched when that lands.
"""

from __future__ import annotations

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

from app.application.ports.chat import ChatCompletion, ChatMessage, ChatUsage
from app.shared.exceptions.ai import (
    ProviderAPIError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderUnavailableError,
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

    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        model: str | None = None,
        temperature: float = 0.7,
    ) -> ChatCompletion:
        # Anthropic takes the system prompt as a top-level `system=` param,
        # not as a message role. Extract + join system content; drop those
        # messages from the outgoing array.
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

        try:
            response = await self._client.messages.create(**kwargs)
        except (AuthenticationError, PermissionDeniedError) as e:
            raise ProviderAuthError(str(e)) from e
        except RateLimitError as e:
            raise ProviderRateLimitError(str(e)) from e
        except (APIConnectionError, APITimeoutError) as e:
            raise ProviderUnavailableError(str(e)) from e
        except (APIStatusError, APIError) as e:
            raise ProviderAPIError(str(e)) from e

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

    async def close(self) -> None:
        await self._client.close()
