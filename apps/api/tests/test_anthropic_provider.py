"""Unit tests for AnthropicProvider — SDK client is fully mocked; no network."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from anthropic import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AuthenticationError,
    PermissionDeniedError,
    RateLimitError,
)

from app.ai.providers.anthropic import AnthropicProvider
from app.application.ports.chat import ChatMessage
from app.shared.exceptions.ai import (
    ProviderAPIError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)


def _fake_response(
    *,
    text: str = "hello from claude",
    model: str = "claude-sonnet-5-fake",
    input_tokens: int = 7,
    output_tokens: int = 3,
    stop_reason: str = "end_turn",
    extra_blocks: list[Any] | None = None,
) -> SimpleNamespace:
    text_block = SimpleNamespace(type="text", text=text)
    blocks = [text_block, *(extra_blocks or [])]
    return SimpleNamespace(
        content=blocks,
        model=model,
        usage=SimpleNamespace(input_tokens=input_tokens, output_tokens=output_tokens),
        stop_reason=stop_reason,
    )


def _provider(create_mock: AsyncMock) -> AnthropicProvider:
    client = MagicMock()
    client.messages.create = create_mock
    client.close = AsyncMock()
    return AnthropicProvider(client=client, model="claude-sonnet-5", max_tokens=1024)


@pytest.mark.asyncio
async def test_system_messages_extracted_and_not_in_messages() -> None:
    create = AsyncMock(return_value=_fake_response())
    provider = _provider(create)

    await provider.complete(
        messages=[
            ChatMessage(role="system", content="rule A"),
            ChatMessage(role="system", content="rule B"),
            ChatMessage(role="user", content="hi"),
            ChatMessage(role="assistant", content="hello"),
            ChatMessage(role="user", content="follow-up"),
        ]
    )

    call_kwargs = create.await_args.kwargs
    assert call_kwargs["system"] == "rule A\n\nrule B"
    # No `system` role should appear in the outgoing messages array.
    roles = [m["role"] for m in call_kwargs["messages"]]
    assert "system" not in roles
    assert roles == ["user", "assistant", "user"]


@pytest.mark.asyncio
async def test_no_system_messages_omits_system_kwarg() -> None:
    create = AsyncMock(return_value=_fake_response())
    provider = _provider(create)

    await provider.complete(messages=[ChatMessage(role="user", content="hi")])

    assert "system" not in create.await_args.kwargs


@pytest.mark.asyncio
async def test_response_mapping_content_model_usage_finish_reason() -> None:
    resp = _fake_response(
        text="first part ",
        model="claude-sonnet-5-20260101",
        input_tokens=42,
        output_tokens=17,
        stop_reason="max_tokens",
        extra_blocks=[SimpleNamespace(type="text", text="second part")],
    )
    create = AsyncMock(return_value=resp)
    provider = _provider(create)

    completion = await provider.complete(messages=[ChatMessage(role="user", content="x")])

    assert completion.content == "first part second part"
    assert completion.model == "claude-sonnet-5-20260101"
    assert completion.usage is not None
    assert completion.usage.prompt_tokens == 42
    assert completion.usage.completion_tokens == 17
    assert completion.finish_reason == "max_tokens"


@pytest.mark.asyncio
async def test_non_text_blocks_are_skipped() -> None:
    resp = _fake_response(
        text="visible ",
        extra_blocks=[SimpleNamespace(type="tool_use", text="INVISIBLE")],
    )
    create = AsyncMock(return_value=resp)
    provider = _provider(create)

    completion = await provider.complete(messages=[ChatMessage(role="user", content="x")])
    assert completion.content == "visible "
    assert "INVISIBLE" not in completion.content


def _http_response(status_code: int) -> httpx.Response:
    return httpx.Response(status_code, request=httpx.Request("POST", "https://x"))


@pytest.mark.parametrize(
    ("sdk_exc_factory", "domain_exc"),
    [
        (
            lambda: AuthenticationError("bad key", response=_http_response(401), body=None),
            ProviderAuthError,
        ),
        (
            lambda: PermissionDeniedError("forbidden", response=_http_response(403), body=None),
            ProviderAuthError,
        ),
        (
            lambda: RateLimitError("rate", response=_http_response(429), body=None),
            ProviderRateLimitError,
        ),
        (
            lambda: APIConnectionError(request=httpx.Request("POST", "https://x")),
            ProviderUnavailableError,
        ),
        (
            lambda: APITimeoutError(request=httpx.Request("POST", "https://x")),
            ProviderUnavailableError,
        ),
        (
            lambda: APIStatusError("boom", response=_http_response(500), body=None),
            ProviderAPIError,
        ),
    ],
)
@pytest.mark.asyncio
async def test_exception_mapping(sdk_exc_factory, domain_exc) -> None:  # type: ignore[no-untyped-def]
    create = AsyncMock(side_effect=sdk_exc_factory())
    provider = _provider(create)
    with pytest.raises(domain_exc):
        await provider.complete(messages=[ChatMessage(role="user", content="hi")])


@pytest.mark.asyncio
async def test_model_override_wins() -> None:
    create = AsyncMock(return_value=_fake_response())
    provider = _provider(create)
    await provider.complete(
        messages=[ChatMessage(role="user", content="hi")],
        model="claude-opus-9",
    )
    assert create.await_args.kwargs["model"] == "claude-opus-9"


@pytest.mark.asyncio
async def test_default_model_used_when_not_overridden() -> None:
    create = AsyncMock(return_value=_fake_response())
    provider = _provider(create)
    await provider.complete(messages=[ChatMessage(role="user", content="hi")])
    assert create.await_args.kwargs["model"] == "claude-sonnet-5"


@pytest.mark.asyncio
async def test_close_closes_underlying_client() -> None:
    create = AsyncMock(return_value=_fake_response())
    provider = _provider(create)
    await provider.close()
    provider._client.close.assert_awaited_once()  # type: ignore[attr-defined]
