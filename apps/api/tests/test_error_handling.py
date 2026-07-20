"""7e-fix — unhandled 500s return a generic envelope WITH CORS headers.

An unhandled exception is caught by Starlette's ServerErrorMiddleware, which
sits OUTSIDE CORSMiddleware — so without the catch-all handler its 500 ships
with no Access-Control-Allow-Origin and the browser reports "Failed to fetch",
disguising every server error as a connectivity problem. These tests pin the
fix: the 500 carries CORS for an allowed Origin, leaks NO exception detail, and
still logs the traceback — while typed handlers keep owning their own errors.
"""

from __future__ import annotations

import pytest
import structlog.testing
from httpx import ASGITransport, AsyncClient

from app.infrastructure.config import Settings
from app.main import create_app
from app.shared.exceptions.common import NotFoundError

ORIGIN = "http://localhost:3001"
LEAK = "SECRET-LEAK-DETAIL-xyz"


def _app() -> object:
    settings = Settings(
        python_env="test",
        database_url="postgresql+asyncpg://x/x",
        app_database_url="postgresql+asyncpg://x/x",
        redis_url="redis://x",
        jwt_secret_key="test-secret-key-at-least-32-bytes-long-xxxxx",
        api_cors_origins=ORIGIN,
    )
    app = create_app(settings)

    # Test-only routes that raise. python_env="test" leaves /_test/* servable.
    @app.get("/_test/boom")
    async def _boom() -> None:
        raise RuntimeError(LEAK)

    @app.get("/_test/notfound")
    async def _nf() -> None:
        raise NotFoundError("no such widget")

    return app


@pytest.mark.asyncio
async def test_unhandled_500_carries_cors_header_and_leaks_nothing() -> None:
    app = _app()
    transport = ASGITransport(app=app, raise_app_exceptions=False)  # type: ignore[arg-type]
    with structlog.testing.capture_logs() as logs:
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/_test/boom", headers={"Origin": ORIGIN})

    assert r.status_code == 500
    # THE POINT OF THE SLICE: the 500 carries CORS for an allowed origin, so the
    # browser sees the real status instead of "Failed to fetch".
    assert r.headers.get("access-control-allow-origin") == ORIGIN
    assert r.headers.get("access-control-allow-credentials") == "true"

    body = r.json()
    assert body["error"]["code"] == "internal_error"
    # NO exception detail reaches the client — not the message, not the type.
    assert LEAK not in r.text
    assert "RuntimeError" not in r.text

    # Traceback IS logged (debuggability retained): the handler passes the
    # exception via exc_info so the real chain renders the traceback.
    events = [e for e in logs if e.get("event") == "unhandled_exception"]
    assert len(events) == 1
    assert events[0]["error_type"] == "RuntimeError"
    assert events[0]["path"] == "/_test/boom"
    assert events[0].get("exc_info") is not None


@pytest.mark.asyncio
async def test_unhandled_500_does_not_reflect_a_disallowed_origin() -> None:
    app = _app()
    transport = ASGITransport(app=app, raise_app_exceptions=False)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/_test/boom", headers={"Origin": "http://evil.example"})

    assert r.status_code == 500
    # An origin NOT in the allowlist must never be echoed back.
    assert r.headers.get("access-control-allow-origin") is None


@pytest.mark.asyncio
async def test_typed_handler_still_wins_over_the_catch_all() -> None:
    app = _app()
    transport = ASGITransport(app=app, raise_app_exceptions=False)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        r = await c.get("/_test/notfound", headers={"Origin": ORIGIN})

    # NotFoundError keeps its own 404 envelope — the catch-all does not swallow it.
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "not_found"
