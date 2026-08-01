"""Service endpoints — protected by a service API key (not a user JWT).

Slice 1 shipped the read-only probe GET /api/v1/service/whoami (proves the
key → org → scopes auth path). Slice 2A adds POST /api/v1/service/ask: a
stateless one-shot "ask Neo" so n8n / the Telegram bot can send a question and
get the Project Analyst's grounded, cited answer over the key-org's datasets.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.ai.agents import AgentRunner
from app.ai.tools import ListDatasetsTool, QueryDatasetTool, ToolRegistry
from app.application.ports.chat import ChatMessage
from app.infrastructure.db import Database
from app.presentation.http.deps import (
    AgentRegistryDep,
    ServicePrincipalDep,
    SettingsDep,
    get_app_database,
)
from app.presentation.http.routers.chat import (
    ProviderDep,
    _make_streaming_dataset_session_factory,
)
from app.presentation.http.schemas.api_keys import WhoAmIResponse
from app.presentation.http.schemas.service import AskRequest, AskResponse
from app.shared.exceptions.auth import AuthenticationError
from app.shared.exceptions.common import BadRequestError

router = APIRouter(prefix="/api/v1/service", tags=["service"])

# The service /ask endpoint always runs this agent — the grounded, dataset-only
# reporter. Not caller-selectable (unlike /chat's agent picker): a service key
# gets one job.
_SERVICE_AGENT = "project_analyst"


@router.get("/whoami", response_model=WhoAmIResponse)
async def whoami(principal: ServicePrincipalDep) -> WhoAmIResponse:
    return WhoAmIResponse(
        organization_id=principal.organization_id,
        scopes=principal.scopes,
    )


@router.post("/ask", response_model=AskResponse)
async def ask(
    body: AskRequest,
    principal: ServicePrincipalDep,
    provider: ProviderDep,
    settings: SettingsDep,
    agents: AgentRegistryDep,
    db: Annotated[Database, Depends(get_app_database)],
) -> AskResponse:
    """Stateless Q&A for a service key. Runs the project_analyst agent for the
    key's org (RLS-scoped via the per-call dataset session factory) and returns
    its grounded answer. Read-only: the agent gets ONLY the read-only dataset
    tools, and provider failures bubble to the global 502/429/504 handlers.
    """
    question = body.question.strip()
    if not question:
        raise BadRequestError("question must not be empty")

    tenant_id = principal.organization_id
    if tenant_id is None:  # defensive — a service key always carries an org
        raise AuthenticationError("service key has no organization")

    agent = agents.get(_SERVICE_AGENT)
    assert agent is not None, f"built-in agent {_SERVICE_AGENT!r} missing from registry"

    # Dataset tools only — the read-only set project_analyst needs for grounded
    # reports, bound to the SAME short-per-call tenant session factory /chat uses
    # (set GUC → query → close). filter_tools drops the agent's other allowed
    # names (search_*) since they aren't in this registry — fine, datasets are
    # the whole job here. No user_id, so no user-scoped search_memory to wire.
    session_factory = _make_streaming_dataset_session_factory(db, tenant_id=tenant_id)
    registry = ToolRegistry()
    registry.register(ListDatasetsTool(session_factory=session_factory, organization_id=tenant_id))
    registry.register(QueryDatasetTool(session_factory=session_factory, organization_id=tenant_id))

    runner = AgentRunner(agent, org_id=str(tenant_id))
    messages = runner.prepare_messages([ChatMessage(role="user", content=question)])
    tools, tool_executor = runner.filter_tools(registry.specs(), registry.execute)

    completion = await provider.complete(
        messages=messages,
        tools=tools or None,
        tool_executor=tool_executor,
        model=settings.service_ask_model,
    )
    return AskResponse(answer=completion.content, sources=completion.tool_invocations)
