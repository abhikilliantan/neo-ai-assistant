"""Service endpoints — protected by a service API key (not a user JWT).

Slice 1 ships one read-only probe: GET /api/v1/service/whoami. It proves the
key auth path end-to-end (key → org → scopes) so n8n / the Telegram bot can
confirm their credential before real endpoints get wired next slice.
"""

from __future__ import annotations

from fastapi import APIRouter

from app.presentation.http.deps import ServicePrincipalDep
from app.presentation.http.schemas.api_keys import WhoAmIResponse

router = APIRouter(prefix="/api/v1/service", tags=["service"])


@router.get("/whoami", response_model=WhoAmIResponse)
async def whoami(principal: ServicePrincipalDep) -> WhoAmIResponse:
    return WhoAmIResponse(
        organization_id=principal.organization_id,
        scopes=principal.scopes,
    )
