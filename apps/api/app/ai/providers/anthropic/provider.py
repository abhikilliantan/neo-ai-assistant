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
    ToolExecutor,
)
from app.application.ports.tools import ToolCall, ToolInvocation
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


_DEFAULT_MAX_TOOL_ITERATIONS = 5


class AnthropicProvider:
    def __init__(
        self,
        *,
        client: AsyncAnthropic,
        model: str,
        max_tokens: int,
        max_tool_iterations: int = _DEFAULT_MAX_TOOL_ITERATIONS,
    ) -> None:
        self._client = client
        self._model = model
        self._max_tokens = max_tokens
        self._max_tool_iterations = max_tool_iterations

    def _prepare_kwargs(
        self,
        messages: list[ChatMessage],
        model: str | None,
        temperature: float,
        *,
        tools: list[dict[str, Any]] | None = None,
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
        if tools:
            kwargs["tools"] = tools
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

    @staticmethod
    def _text_from(response: Any) -> str:
        return "".join(
            getattr(block, "text", "")
            for block in response.content
            if getattr(block, "type", None) == "text"
        )

    @staticmethod
    def _completion_from(response: Any, *, finish_reason: str) -> ChatCompletion:
        return ChatCompletion(
            content=AnthropicProvider._text_from(response),
            model=response.model,
            usage=ChatUsage(
                prompt_tokens=response.usage.input_tokens,
                completion_tokens=response.usage.output_tokens,
            ),
            finish_reason=finish_reason,
        )

    @staticmethod
    def _serialize_block(block: Any) -> dict[str, Any]:
        """Turn an SDK content block back into a JSON-shaped dict for replay.

        The next SDK call needs the assistant's full content list — including
        any tool_use blocks — verbatim. Text and tool_use are the two shapes
        Claude emits mid-turn; anything else best-efforts through model_dump.
        """
        t = getattr(block, "type", None)
        if t == "text":
            return {"type": "text", "text": getattr(block, "text", "")}
        if t == "tool_use":
            return {
                "type": "tool_use",
                "id": getattr(block, "id", ""),
                "name": getattr(block, "name", ""),
                "input": getattr(block, "input", {}) or {},
            }
        dump = getattr(block, "model_dump", None)
        return dump() if callable(dump) else {"type": t or "unknown"}

    async def complete(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_executor: ToolExecutor | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> ChatCompletion:
        kwargs = self._prepare_kwargs(messages, model, temperature, tools=tools)
        # `api_messages` is the same list object the SDK will read on every
        # iteration — appending to it grows the conversation in place.
        api_messages: list[dict[str, Any]] = kwargs["messages"]

        # Accumulate one ToolInvocation per tool_use we actually run. Surfaced
        # on the returned ChatCompletion so the /chat handler can pass it to
        # the client for THIS turn only — never persisted, never reloaded.
        invocations: list[ToolInvocation] = []

        last_response: Any = None
        for _ in range(self._max_tool_iterations + 1):
            try:
                response = await self._client.messages.create(**kwargs)
            except _SDK_EXCEPTIONS as e:
                raise self._translate(e) from e
            last_response = response

            stop_reason = getattr(response, "stop_reason", None) or "stop"
            if stop_reason != "tool_use" or tool_executor is None:
                completion = self._completion_from(response, finish_reason=stop_reason)
                completion.tool_invocations = invocations
                return completion

            # Run every tool_use block in this response, collect tool_result blocks.
            tool_result_blocks: list[dict[str, Any]] = []
            for block in response.content:
                if getattr(block, "type", None) != "tool_use":
                    continue
                call = ToolCall(
                    id=getattr(block, "id", ""),
                    name=getattr(block, "name", ""),
                    arguments=getattr(block, "input", {}) or {},
                )
                result = await tool_executor(call)
                invocations.append(ToolInvocation(name=call.name, ok=not result.is_error))
                tr: dict[str, Any] = {
                    "type": "tool_result",
                    "tool_use_id": result.tool_call_id,
                    "content": result.content,
                }
                if result.is_error:
                    tr["is_error"] = True
                tool_result_blocks.append(tr)

            # Extend the conversation for the next SDK call: assistant's full
            # content list (text + tool_use), then the user turn of results.
            assistant_content = [self._serialize_block(b) for b in response.content]
            api_messages.append({"role": "assistant", "content": assistant_content})
            api_messages.append({"role": "user", "content": tool_result_blocks})

        # Fell off the loop — every iteration was tool_use. Return the last
        # response's text with the cap flag; no infinite loops, no more calls.
        assert last_response is not None
        completion = self._completion_from(last_response, finish_reason="max_tool_iterations")
        completion.tool_invocations = invocations
        return completion

    async def stream(
        self,
        *,
        messages: list[ChatMessage],
        tools: list[dict[str, Any]] | None = None,
        tool_executor: ToolExecutor | None = None,
        model: str | None = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[ChatStreamEvent]:
        kwargs = self._prepare_kwargs(messages, model, temperature, tools=tools)

        # No tool loop → 3a behavior verbatim: stream deltas LIVE from the SDK.
        if tools is None or tool_executor is None:
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
            return

        # Tool-loop path. Per turn: fully consume the SDK stream into a
        # per-turn text buffer WITHOUT emitting deltas — we can't know until
        # stop_reason arrives whether this is an intermediate tool_use turn
        # (suppress) or the final answer (emit). Only the FINAL turn's
        # buffered text is emitted as delta events; intermediate turns are
        # silent this slice ("Neo is searching…" status frame → 6e).
        # `api_messages` is the same list the SDK reads on every iteration;
        # appending grows the conversation in place.
        api_messages: list[dict[str, Any]] = kwargs["messages"]
        last_final: Any = None

        for _ in range(self._max_tool_iterations + 1):
            turn_deltas: list[str] = []
            try:
                async with self._client.messages.stream(**kwargs) as s:
                    async for text_delta in s.text_stream:
                        turn_deltas.append(text_delta)
                    final = await s.get_final_message()
            except _SDK_EXCEPTIONS as e:
                raise self._translate(e) from e

            last_final = final
            stop_reason = getattr(final, "stop_reason", None) or "stop"

            if stop_reason != "tool_use":
                for chunk in turn_deltas:
                    yield ChatStreamEvent(type="delta", content=chunk)
                yield ChatStreamEvent(
                    type="done",
                    model=final.model,
                    usage=ChatUsage(
                        prompt_tokens=final.usage.input_tokens,
                        completion_tokens=final.usage.output_tokens,
                    ),
                    finish_reason=stop_reason,
                )
                return

            # tool_use turn — run every tool_use block, collect tool_result
            # blocks, and yield a live "tool" frame per invocation so the UI
            # can render "Neo used X" WHILE the loop runs (6e-1). Tool frames
            # are surfaced only; the /chat/stream endpoint's accumulator
            # appends only on type=="delta", so tool frames never enter the
            # persisted assistant content — the ephemeral invariant holds.
            tool_result_blocks: list[dict[str, Any]] = []
            for block in final.content:
                if getattr(block, "type", None) != "tool_use":
                    continue
                call = ToolCall(
                    id=getattr(block, "id", ""),
                    name=getattr(block, "name", ""),
                    arguments=getattr(block, "input", {}) or {},
                )
                result = await tool_executor(call)
                yield ChatStreamEvent(type="tool", tool_name=call.name, tool_ok=not result.is_error)
                tr: dict[str, Any] = {
                    "type": "tool_result",
                    "tool_use_id": result.tool_call_id,
                    "content": result.content,
                }
                if result.is_error:
                    tr["is_error"] = True
                tool_result_blocks.append(tr)

            assistant_content = [self._serialize_block(b) for b in final.content]
            api_messages.append({"role": "assistant", "content": assistant_content})
            api_messages.append({"role": "user", "content": tool_result_blocks})

        # Fell off the loop — every iteration was tool_use. Emit a terminal
        # done with the cap flag; no infinite streams, no more SDK calls.
        assert last_final is not None
        yield ChatStreamEvent(
            type="done",
            model=last_final.model,
            usage=ChatUsage(
                prompt_tokens=last_final.usage.input_tokens,
                completion_tokens=last_final.usage.output_tokens,
            ),
            finish_reason="max_tool_iterations",
        )

    async def close(self) -> None:
        await self._client.close()
