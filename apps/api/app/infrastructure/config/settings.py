"""Application settings — pydantic-settings, loaded from env / .env."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "staging", "production", "test"]


class Settings(BaseSettings):
    """Single source of truth for runtime configuration."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # --- runtime ---
    python_env: Environment = "development"
    log_level: str = "info"

    # --- api ---
    api_host: str = "0.0.0.0"  # noqa: S104 (container bind)
    api_port: int = 8000
    api_secret_key: str = "change-me"  # noqa: S105 (scaffold default; override via env)
    api_cors_origins: str = "http://localhost:3000"

    # --- auth / jwt ---
    jwt_secret_key: str = "change-me"  # noqa: S105 (scaffold default; override via env)
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # --- database ---
    # `database_url` — privileged role (neo, owner). Used by Alembic and the
    # tiny SystemRepository. Not used for regular request-scoped DML.
    database_url: str = Field(
        default="postgresql+asyncpg://neo:neo@localhost:5432/neo",
        description="Async SQLAlchemy URL for the privileged role (migrations + system ops)",
    )
    # `app_database_url` — runtime role (neo_app, NOSUPERUSER NOBYPASSRLS).
    # Feature endpoints connect as this so RLS (with FORCE) actually applies.
    app_database_url: str = Field(
        default="postgresql+asyncpg://neo_app:neo_app@localhost:5432/neo",
        description="Async SQLAlchemy URL for the runtime app role (RLS-scoped)",
    )
    db_echo: bool = False
    db_pool_size: int = 10
    db_pool_max_overflow: int = 20

    # --- redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- ai / llm providers ---
    ai_provider: Literal["mock", "anthropic"] = "mock"
    ai_max_tokens: int = 1024

    anthropic_api_key: str = ""  # empty default; real value goes in .env
    anthropic_model: str = "claude-sonnet-5"

    openai_api_key: str | None = None
    gemini_api_key: str | None = None

    # --- embeddings ---
    # Locked at 1024 to match the pgvector schema 5b creates for voyage-3.5.
    embedding_provider: Literal["mock", "voyage"] = "mock"
    voyage_api_key: str = ""  # empty default; real value goes in .env
    embedding_model: str = "voyage-3.5"
    embedding_dimensions: int = 1024

    # --- memory extraction (phase 5c) ---
    # `llm` reuses the chat provider — no new API key. `mock` is the CI/test
    # default and makes write-path tests deterministic.
    memory_extractor: Literal["mock", "llm"] = "mock"

    # --- memory retrieval (phase 5d) ---
    # Threshold-gated top-K nearest neighbours on the caller's own memories,
    # injected as a system message before the provider call. Ephemeral —
    # never persisted. Disable to make the chat path a strict no-op.
    memory_retrieval_enabled: bool = True
    memory_retrieval_top_k: int = 5
    memory_retrieval_min_similarity: float = 0.7

    # --- tools (phase 6b) ---
    # Clean kill switch: when false, BOTH /chat and /chat/stream pass tools=None
    # to the provider — the tool-use loop never engages on either path (stream
    # runs the loop too since 6d). Provider stays wired; only the specs +
    # executor are withheld.
    tools_enabled: bool = True

    # --- workflows (phase 7a) ---
    # `mock` is the CI/test default and needs no key. `n8n` is NOT implemented
    # until 7c (build_workflow_client raises NotImplementedError). n8n webhook
    # URLs + auth tokens are SECRETS — they live in .env, never in code, and
    # their Settings fields arrive with the 7c client that reads them.
    workflow_client: Literal["mock", "n8n"] = "mock"
    # Kill switch mirroring tools_enabled. Inert in 7a — nothing consumes it
    # yet; 7b uses it as a route-level gate (WORKFLOWS ARE TOOLS) exactly like
    # tools_enabled gates the /chat tool loop.
    workflows_enabled: bool = True

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]

    @property
    def is_prod(self) -> bool:
        return self.python_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor — built once per process."""
    return Settings()
