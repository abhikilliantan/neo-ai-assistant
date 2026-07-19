"""HTTP exception mappers — bind auth-domain errors to consistent JSON responses."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
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


async def _validation_handler(_: Request, exc: Exception) -> JSONResponse:
    # First error typically pinpoints what's wrong; keep the message short.
    message = "invalid request"
    if isinstance(exc, RequestValidationError):
        errors = exc.errors()
        if errors:
            first = errors[0]
            loc = ".".join(str(p) for p in first.get("loc", ()) if p != "body")
            reason = first.get("msg", "invalid")
            message = f"{loc}: {reason}" if loc else reason
    return JSONResponse(
        _error_body("validation_error", message),
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AuthenticationError, _authentication_handler)
    app.add_exception_handler(EmailAlreadyRegisteredError, _email_taken_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
