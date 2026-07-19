"""Auth endpoints — register, login, refresh, logout."""

from __future__ import annotations

from fastapi import APIRouter, Request, Response, status

from app.application.use_cases import auth as auth_uc
from app.infrastructure.db.repositories import (
    MembershipRepository,
    OrganizationRepository,
    RoleRepository,
    SessionRepository,
    UserRepository,
)
from app.presentation.http.deps import SessionDep
from app.presentation.http.schemas.auth import (
    AuthResponse,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
)

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
    session: SessionDep,
    request: Request,
) -> AuthResponse:
    result = await auth_uc.register(
        email=body.email,
        password=body.password,
        organization_name=body.organization_name,
        users=UserRepository(session),
        organizations=OrganizationRepository(session),
        memberships=MembershipRepository(session),
        roles=RoleRepository(session),
        sessions=SessionRepository(session),
        user_agent=_user_agent(request),
        ip_address=_client_ip(request),
    )
    await session.commit()
    return _to_response(result)


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    session: SessionDep,
    request: Request,
) -> AuthResponse:
    result = await auth_uc.login(
        email=body.email,
        password=body.password,
        users=UserRepository(session),
        memberships=MembershipRepository(session),
        sessions=SessionRepository(session),
        user_agent=_user_agent(request),
        ip_address=_client_ip(request),
    )
    await session.commit()
    return _to_response(result)


@router.post("/refresh", response_model=AuthResponse)
async def refresh(
    body: RefreshRequest,
    session: SessionDep,
    request: Request,
) -> AuthResponse:
    result = await auth_uc.refresh(
        refresh_token=body.refresh_token,
        users=UserRepository(session),
        memberships=MembershipRepository(session),
        sessions=SessionRepository(session),
        user_agent=_user_agent(request),
        ip_address=_client_ip(request),
    )
    await session.commit()
    return _to_response(result)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: RefreshRequest,
    session: SessionDep,
) -> Response:
    await auth_uc.logout(
        refresh_token=body.refresh_token,
        sessions=SessionRepository(session),
    )
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
