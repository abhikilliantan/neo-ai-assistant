"""HTTP exception mappers — bind auth-domain errors to consistent JSON responses."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse

from app.shared.exceptions.auth import AuthenticationError, EmailAlreadyRegisteredError


def _error_body(code: str, message: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message": message}}


async def _authentication_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        _error_body("authentication_failed", "invalid credentials or token"),
        status_code=status.HTTP_401_UNAUTHORIZED,
        headers={"WWW-Authenticate": "Bearer"},
    )


async def _email_taken_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        _error_body("email_already_registered", "email is already registered"),
        status_code=status.HTTP_409_CONFLICT,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AuthenticationError, _authentication_handler)
    app.add_exception_handler(EmailAlreadyRegisteredError, _email_taken_handler)
