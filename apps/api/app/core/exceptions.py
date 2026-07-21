"""HTTP exception mappers — bind auth-domain errors to consistent JSON responses."""

from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.infrastructure.logging import get_logger
from app.shared.exceptions.ai import (
    ProviderAPIError,
    ProviderAuthError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)
from app.shared.exceptions.auth import AuthenticationError, EmailAlreadyRegisteredError
from app.shared.exceptions.common import BadRequestError, NotFoundError
from app.shared.exceptions.documents import (
    DocumentParseError,
    DocumentTooLargeError,
    UnsupportedContentTypeError,
)
from app.shared.exceptions.embeddings import (
    EmbeddingProviderAPIError,
    EmbeddingProviderAuthError,
    EmbeddingProviderRateLimitError,
    EmbeddingProviderUnavailableError,
)


def _error_body(code: str, message: str) -> dict[str, dict[str, str]]:
    return {"error": {"code": code, "message": message}}


def _cors_headers(request: Request) -> dict[str, str]:
    """CORS headers for the catch-all 500, echoing the request Origin ONLY when
    it is in the app's configured allowlist (never reflecting an arbitrary
    origin). Mirrors the app's explicit-origin + credentials CORSMiddleware
    config — see `_internal_error_handler` for why we set these by hand.
    """
    settings = getattr(request.app.state, "settings", None)
    allowed = settings.cors_origins if settings is not None else []
    origin = request.headers.get("origin")
    if origin and (origin in allowed or "*" in allowed):
        return {
            "access-control-allow-origin": origin,
            "access-control-allow-credentials": "true",  # matches create_app's fixed CORS config
            "vary": "Origin",
        }
    return {}


async def _internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all for UNHANDLED exceptions (7e-fix). Two jobs:

    1. Log the full traceback at ERROR — the ONLY place the detail is kept; it
       NEVER reaches the client. Safety must not cost debuggability.
    2. Return the generic error envelope WITH CORS headers.

    Why set CORS headers by hand: a handler registered for `Exception` runs in
    Starlette's ServerErrorMiddleware, which sits OUTSIDE CORSMiddleware, so its
    response never passes back through CORS. Without this, the 500 ships with no
    Access-Control-Allow-Origin, the browser can't read it, and fetch() rejects
    with "Failed to fetch" — disguising every server error as a connectivity
    problem (which burned a whole debugging cycle). Typed handlers below don't
    need this: they run in the inner ExceptionMiddleware and CORS decorates them
    normally.

    STREAMING BOUNDARY (not a bug): once an SSE body has started, its headers are
    already on the wire, so a mid-stream failure cannot retroactively gain CORS
    headers. This handler covers PRE-stream failures (e.g. an error thrown before
    /chat/stream's first frame — exactly the agent_name case) and every
    non-streaming route. /chat/stream reports mid-stream provider errors as
    in-band SSE `error` frames instead.
    """
    get_logger("http.unhandled").error(
        "unhandled_exception",
        method=request.method,
        path=request.url.path,
        error_type=type(exc).__name__,
        exc_info=exc,
    )
    return JSONResponse(
        _error_body("internal_error", "an internal error occurred"),
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        headers=_cors_headers(request),
    )


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


async def _provider_auth_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        _error_body("provider_auth_error", "upstream AI provider rejected our credentials"),
        status_code=status.HTTP_502_BAD_GATEWAY,
    )


async def _provider_rate_limit_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        _error_body("provider_rate_limited", "upstream AI provider rate-limited the request"),
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    )


async def _provider_unavailable_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        _error_body("provider_unavailable", "upstream AI provider is unreachable"),
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
    )


async def _provider_api_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        _error_body("provider_error", "upstream AI provider returned an error"),
        status_code=status.HTTP_502_BAD_GATEWAY,
    )


async def _not_found_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        _error_body("not_found", str(exc) or "resource not found"),
        status_code=status.HTTP_404_NOT_FOUND,
    )


async def _bad_request_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        _error_body("bad_request", str(exc) or "bad request"),
        status_code=status.HTTP_400_BAD_REQUEST,
    )


# --- document upload (8c). Fixed, non-leaking messages — the file is untrusted,
# so we never echo its content-type/filename/bytes back in an error string.


async def _document_too_large_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        _error_body("document_too_large", "uploaded document exceeds the size limit"),
        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
    )


async def _unsupported_content_type_handler(_: Request, exc: Exception) -> JSONResponse:
    # Surface the raiser's message (e.g. the dispatcher naming supported types);
    # messages are developer constants + a normalized content-type, never user data.
    return JSONResponse(
        _error_body("unsupported_content_type", str(exc) or "unsupported document content type"),
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
    )


async def _document_parse_handler(_: Request, exc: Exception) -> JSONResponse:
    # A corrupt/too-slow document is the client's file — 422, not a 5xx.
    return JSONResponse(
        _error_body("document_unprocessable", "the document could not be processed"),
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


async def _embedding_auth_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        _error_body(
            "embedding_provider_auth_error",
            "upstream embedding provider rejected our credentials",
        ),
        status_code=status.HTTP_502_BAD_GATEWAY,
    )


async def _embedding_rate_limit_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        _error_body(
            "embedding_provider_rate_limited",
            "upstream embedding provider rate-limited the request",
        ),
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
    )


async def _embedding_unavailable_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        _error_body(
            "embedding_provider_unavailable",
            "upstream embedding provider is unreachable",
        ),
        status_code=status.HTTP_504_GATEWAY_TIMEOUT,
    )


async def _embedding_api_handler(_: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        _error_body(
            "embedding_provider_error",
            "upstream embedding provider returned an error",
        ),
        status_code=status.HTTP_502_BAD_GATEWAY,
    )


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AuthenticationError, _authentication_handler)
    app.add_exception_handler(EmailAlreadyRegisteredError, _email_taken_handler)
    app.add_exception_handler(NotFoundError, _not_found_handler)
    app.add_exception_handler(BadRequestError, _bad_request_handler)
    # Document upload: register the SUBCLASSES (too-large, unsupported-type)
    # before the DocumentParseError base so each keeps its specific status. Both
    # subclass DocumentParseError; Starlette dispatches by exact type first.
    app.add_exception_handler(DocumentTooLargeError, _document_too_large_handler)
    app.add_exception_handler(UnsupportedContentTypeError, _unsupported_content_type_handler)
    app.add_exception_handler(DocumentParseError, _document_parse_handler)
    app.add_exception_handler(RequestValidationError, _validation_handler)
    app.add_exception_handler(ProviderAuthError, _provider_auth_handler)
    app.add_exception_handler(ProviderRateLimitError, _provider_rate_limit_handler)
    app.add_exception_handler(ProviderUnavailableError, _provider_unavailable_handler)
    app.add_exception_handler(ProviderAPIError, _provider_api_handler)
    app.add_exception_handler(EmbeddingProviderAuthError, _embedding_auth_handler)
    app.add_exception_handler(EmbeddingProviderRateLimitError, _embedding_rate_limit_handler)
    app.add_exception_handler(EmbeddingProviderUnavailableError, _embedding_unavailable_handler)
    app.add_exception_handler(EmbeddingProviderAPIError, _embedding_api_handler)
    # Catch-all LAST — the most specific handler always wins, so the typed ones
    # above still own their errors; this only fires for genuinely unhandled ones.
    app.add_exception_handler(Exception, _internal_error_handler)
