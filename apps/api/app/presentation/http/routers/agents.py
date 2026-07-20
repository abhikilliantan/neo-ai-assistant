"""GET /api/v1/agents — discover available agents.

Global built-ins, no tenant scoping (every caller sees the same set). Auth
required so we don't leak the agent surface to unauthenticated visitors.

Response is a whitelist: AgentOut carries {name, description} only. The
handler builds each item field-by-field rather than round-tripping the
AgentDefinition — see schemas/agent.py for the rationale.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.presentation.http.deps import AccessPayloadDep, AgentRegistryDep
from app.presentation.http.schemas.agent import AgentOut

router = APIRouter(prefix="/api/v1", tags=["agents"])


@router.get("/agents", response_model=list[AgentOut])
async def list_agents(
    _payload: AccessPayloadDep,  # 401 without a token
    agents: AgentRegistryDep,
) -> list[AgentOut]:
    return [AgentOut(name=d.name, description=d.description) for d in agents.definitions()]
