"""Schemas for the service /ask endpoint (Slice 2A).

Stateless one-shot Q&A: an external system (n8n/Telegram) posts a question and
gets the Project Analyst's grounded answer back. No conversation history.
"""

from __future__ import annotations

from pydantic import BaseModel

from app.application.ports.tools import ToolInvocation


class AskRequest(BaseModel):
    # min_length is NOT set here: a whitespace-only question passes a length
    # check but is still empty. The endpoint strips + rejects → 400, so the
    # blank/whitespace cases share one code path.
    question: str


class AskResponse(BaseModel):
    answer: str
    # The tools the analyst ran to ground its answer (list_datasets /
    # query_dataset), name + ok. Reuses the /chat live-signal VO; the answer
    # text carries the human-readable dataset citations.
    sources: list[ToolInvocation] = []
