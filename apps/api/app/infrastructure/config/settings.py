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

    # --- database ---
    database_url: str = Field(
        default="postgresql+asyncpg://neo:neo@localhost:5432/neo",
        description="Async SQLAlchemy URL (postgresql+asyncpg://...)",
    )
    db_echo: bool = False
    db_pool_size: int = 10
    db_pool_max_overflow: int = 20

    # --- redis ---
    redis_url: str = "redis://localhost:6379/0"

    # --- llm providers (kept optional at scaffold stage) ---
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    gemini_api_key: str | None = None

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
