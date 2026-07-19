"""Extraction prompt — kept separate from business logic so it can be
iterated on / A/B-tested without touching the coordinator.
"""

from __future__ import annotations

from app.application.ports.chat import ChatMessage

_EXTRACTION_SYSTEM_PROMPT = """\
You are a memory-extraction assistant.

Given a conversation between a user and an assistant, identify DURABLE,
USER-SPECIFIC facts or preferences worth remembering long-term. Examples:
  - "user is a vegetarian"
  - "user's name is Priya"
  - "user prefers concise answers"

EPHEMERAL or one-off chatter (weather, small talk, jokes, single-turn
factual questions the user asks) must NOT be extracted — return [].

Output STRICTLY a JSON array of objects, no prose, no code fences, no
comments. Each object has:
  - "content": a short factual statement about the user (<= 500 chars).
  - "kind":    "fact" | "preference" | "summary".

If nothing durable is worth storing, output exactly: []
"""


def build_extraction_messages(
    messages: list[ChatMessage],
    assistant_reply: str,
) -> list[ChatMessage]:
    """Convert the chat turn into a self-contained extraction request.

    The full conversation is included as a `user` message (not replayed as
    roles) so the extractor treats it as data to analyze rather than a
    dialogue to continue.
    """
    transcript_parts: list[str] = []
    for m in messages:
        transcript_parts.append(f"{m.role.upper()}: {m.content}")
    transcript_parts.append(f"ASSISTANT: {assistant_reply}")
    transcript = "\n".join(transcript_parts)

    return [
        ChatMessage(role="system", content=_EXTRACTION_SYSTEM_PROMPT),
        ChatMessage(
            role="user",
            content=(
                "Extract durable memories from this conversation. "
                "Return a JSON array, or [] if none.\n\n"
                f"<conversation>\n{transcript}\n</conversation>"
            ),
        ),
    ]
