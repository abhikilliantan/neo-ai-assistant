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
    # R6: gate public self-registration. Route-level kill switch mirroring
    # tools_enabled / documents_enabled. Default True so dev/CI (where ~30 tests
    # bootstrap via POST /register) are unaffected. The admin-provisioned pilot
    # sets REGISTRATION_ENABLED=false in .env; new users are then created only via
    # `make create-user` (scripts/create_user.py), which bypasses this flag.
    registration_enabled: bool = True

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
    # `mock` is the CI/test default and needs no key. `n8n` (7c) calls real
    # webhooks and requires N8N_BASE_URL + N8N_AUTH_TOKEN (below).
    workflow_client: Literal["mock", "n8n"] = "mock"
    # Kill switch mirroring tools_enabled. 7b uses it as a route-level gate
    # (WORKFLOWS ARE TOOLS) exactly like tools_enabled gates the tool loop.
    workflows_enabled: bool = True

    # --- n8n workflow client (phase 7c) ---
    # Read ONLY when WORKFLOW_CLIENT=n8n; build_workflow_client fails fast if
    # base URL or token is missing. The webhook URL is derived by convention
    # (base_url + "/webhook/" + workflow_name).
    n8n_base_url: str = ""
    # SECRET — .env only. NEVER logged, never put in an error/response string.
    n8n_auth_token: str = ""
    # HARD timeout. Load-bearing: the call runs inside the tool loop inside the
    # live provider stream, so a hanging webhook would stall a watched response.
    n8n_timeout_seconds: float = 10.0
    # 7f-1 SSRF allowlist (comma-separated hosts). Empty = deny-by-range only
    # (the guard still blocks loopback/metadata/private ranges). When set, it is
    # authoritative: nothing outside it is reachable. Exact host match, no
    # wildcards. A security-conscious deployment turns this on.
    n8n_allowed_hosts: str = ""

    # --- document intelligence (phase 8a) ---
    # Fallback parser for formats WITHOUT a real parser (text/markdown always use
    # the real TextDocumentParser). `reject` (default) rejects such formats at
    # upload with 415 rather than fabricating content — silent fabrication is
    # worse than failure. `mock` fabricates and is opt-in for tests/CI ONLY,
    # scoped exactly like MockProvider (ai_provider="mock"): conftest pins it, so
    # a dev/prod default of `reject` never invents searchable text. `unstructured`
    # (real PDF/DOCX) is NOT implemented until a later 8f slice — build raises.
    document_parser: Literal["reject", "mock", "unstructured"] = "reject"
    # Kill switch mirroring tools_enabled / workflows_enabled. Inert in 8a —
    # nothing consumes it yet; a route-level gate lands in 8c (ingest) / 8d
    # (retrieval).
    documents_enabled: bool = True
    # Chunking, in CHARACTERS. The real limit is the embedding model's max
    # TOKENS (≈ 4 chars/token) — keep chunk_size well under the model cap.
    document_chunk_size: int = 1000
    document_chunk_overlap: int = 200
    # ADR 0001: chunker selection. "block_aware" (default) packs whole
    # ParsedBlocks on paragraph/section boundaries; "fixed" is the legacy
    # fixed-size char window. block_aware became the default per ADR 0001
    # Amendment 1 — it won the citation-quality gate (tighter citations, answers
    # in the first sentence) that replaced the falsified score-margin gate.
    # chunk_size/overlap are shared by both (overlap = whole-block carry budget
    # for block_aware, Decision 3).
    document_chunker: Literal["fixed", "block_aware"] = "block_aware"
    # Resource limits on UNTRUSTED uploads (8c enforces at the route; the parser
    # enforces max_bytes now). Timeout is enforced by the CALLER via
    # asyncio.wait_for — a parser can't reliably self-timeout mid-CPU-work.
    document_max_bytes: int = 10_000_000  # 10 MB
    document_max_pages: int = 500
    document_parse_timeout_seconds: float = 30.0
    # ADR 0003: memory cap (RLIMIT_AS) for the parse-isolation child. 1 GiB
    # default (resolved Open Question 1) — tolerates a large-but-legitimate
    # document's working set while hard-killing an unbounded allocation.
    document_parse_max_memory_bytes: int = 1_073_741_824  # 1 GiB
    # ADR 0003: DOCX decompressed-size cap (zip-bomb defense). 200 MiB default
    # (resolved OQ2) — 20x the 10 MB upload cap; generous for real files, lethal
    # to bombs.
    document_docx_max_decompressed_bytes: int = 209_715_200  # 200 MiB
    # ADR 0003: PDF scanned/image-only floor (resolved OQ3). If a PDF's average
    # extractable chars-per-page is below this, it is rejected with 422 + a clear
    # "OCR isn't supported" message rather than silently ingested as empty — a PDF
    # with no text layer is almost always a scan. Measured margin is wide: scanned
    # pages extract 0 chars, real text pages hundreds+, so 10 separates comfortably
    # without rejecting sparse-but-real text. Ops-tunable per corpus.
    document_pdf_min_chars_per_page: int = 10
    # ADR 0003: PER-FORMAT enablement of real (native) parsers — comma-separated
    # format keys ("docx", "pdf"). Empty default → no native parser; unlisted
    # formats fall to the fallback (mock in tests, reject in prod). Enabling
    # "docx" does NOT enable "pdf". mock/reject stay the CI/test/prod defaults.
    document_native_parsers: str = ""
    # ADR 0002 — original file storage. Bytes live OUTSIDE the DB behind a
    # StorageProvider; the documents row keeps only an opaque pointer. Slice 1
    # ships the single "filesystem" backend (S3/MinIO/Azure land later behind the
    # same port). The root is a mounted Docker volume so stored files survive
    # container recreation. NOTE: the pilot host must provide an ENCRYPTED volume
    # for this root (ADR 0002 encryption-at-rest deployment precondition).
    document_storage_backend: Literal["filesystem"] = "filesystem"
    document_storage_root: str = "/var/neo/documents"
    # 8c allowlist of accepted upload content types (comma-separated). The part's
    # declared type is ATTACKER-CONTROLLED, so only these are accepted; anything
    # else → 415. Kept as a security-tunable setting (like n8n_allowed_hosts),
    # not a hard-coded constant, so ops can widen/narrow it per deployment.
    document_allowed_content_types: str = (
        "application/pdf,"
        "text/plain,"
        "text/markdown,"
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    # 8e-1 UI citation floor. search_chunks returns top-k regardless of
    # closeness — fine for the model (it reads excerpts and judges), NOT fine
    # for the UI, where a weak match rendered as a citation asserts confidence
    # the number doesn't support. POST /documents/search omits results below
    # this cosine similarity entirely. Deliberately independent of, and lower
    # than, memory_retrieval_min_similarity (0.7): document retrieval casts a
    # wider net than personal-memory recall, and this gate drops topical noise
    # rather than tuning recall. Ops-tunable per corpus.
    document_search_min_similarity: float = 0.5

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.api_cors_origins.split(",") if o.strip()]

    @property
    def n8n_allowed_hosts_list(self) -> list[str]:
        return [h.strip().lower() for h in self.n8n_allowed_hosts.split(",") if h.strip()]

    @property
    def document_allowed_content_types_set(self) -> frozenset[str]:
        return frozenset(
            t.strip().lower() for t in self.document_allowed_content_types.split(",") if t.strip()
        )

    @property
    def document_native_parsers_set(self) -> frozenset[str]:
        return frozenset(
            t.strip().lower() for t in self.document_native_parsers.split(",") if t.strip()
        )

    @property
    def is_prod(self) -> bool:
        return self.python_env == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Cached settings accessor — built once per process."""
    return Settings()
