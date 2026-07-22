"""Auth endpoints — register, login, refresh, logout.

Two DB sessions per request:
  - `AppSessionDep` (neo_app, RLS-enforced) — for sessions table (global).
  - `SystemSessionDep` (neo, privileged) — for the SystemRepository ops.

Both sessions are transaction-wrapped by their deps and auto-commit at
request end. Routes never call session.commit().
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from app.application.use_cases import auth as auth_uc
from app.infrastructure.db.repositories import (
    SessionRepository,
    SystemRepository,
    UserRepository,
)
from app.presentation.http.deps import AppSessionDep, SettingsDep, SystemSessionDep
from app.presentation.http.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
)
from app.shared.exceptions.auth import RegistrationClosedError

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _user_agent(request: Request) -> str | None:
    ua = request.headers.get("user-agent")
    return ua[:512] if ua else None


def _to_response(result: auth_uc.AuthResult) -> AuthResponse:
    return AuthResponse(
        user_id=result.user_id,
        email=result.email,
        active_tenant_id=result.active_tenant_id,
        access_token=result.access_token,
        refresh_token=result.refresh_token,
        expires_in=result.expires_in,
    )


@router.post(
    "/register",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    body: RegisterRequest,
    system_session: SystemSessionDep,
    settings: SettingsDep,
    request: Request,
) -> AuthResponse:
    # R6: gate public self-registration BEFORE any side effect (no user/org/session
    # row, no token). The admin-provisioned pilot sets REGISTRATION_ENABLED=false;
    # onboarding then happens only via `make create-user`.
    if not settings.registration_enabled:
        raise RegistrationClosedError("public registration is closed")
    # Register runs ENTIRELY on the system session so user creation and the
    # first sessions row live in one transaction. Using the app session for
    # sessions here would FK-violate — the app-session connection can't see
    # the uncommitted user rows in the system-session's transaction.
    result = await auth_uc.register(
        email=body.email,
        password=body.password,
        organization_name=body.organization_name,
        system=SystemRepository(system_session),
        sessions=SessionRepository(system_session),
        user_agent=_user_agent(request),
        ip_address=_client_ip(request),
    )
    return _to_response(result)


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    app_session: AppSessionDep,
    system_session: SystemSessionDep,
    request: Request,
) -> AuthResponse:
    result = await auth_uc.login(
        email=body.email,
        password=body.password,
        system=SystemRepository(system_session),
        sessions=SessionRepository(app_session),
        user_agent=_user_agent(request),
        ip_address=_client_ip(request),
    )
    return _to_response(result)


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    body: RefreshRequest,
    app_session: AppSessionDep,
    system_session: SystemSessionDep,
    request: Request,
) -> AuthResponse:
    result = await auth_uc.refresh(
        refresh_token=body.refresh_token,
        users=UserRepository(app_session),
        sessions=SessionRepository(app_session),
        system=SystemRepository(system_session),
        user_agent=_user_agent(request),
        ip_address=_client_ip(request),
    )
    return _to_response(result)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: RefreshRequest,
    app_session: AppSessionDep,
) -> Response:
    await auth_uc.logout(
        refresh_token=body.refresh_token,
        sessions=SessionRepository(app_session),
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
