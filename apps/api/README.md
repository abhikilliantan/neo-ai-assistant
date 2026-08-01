# Neo API

FastAPI backend for Neo AI Assistant. Clean Architecture, async SQLAlchemy 2.x,
Pydantic v2, structlog.

## Layout

```
app/
├── domain/            entities, value objects (framework-free)
├── application/       use cases + ports (Protocols)
│   └── ports/         abstract interfaces implemented by infrastructure
├── infrastructure/    adapters
│   ├── config/        pydantic-settings
│   ├── db/            async engine + session factory + declarative base
│   ├── cache/         redis client factory
│   ├── logging/       structlog setup
│   └── health/        DB / Redis health-check adapters
├── presentation/
│   └── http/
│       ├── deps.py    FastAPI dependencies
│       ├── routers/   /health, /ready
│       └── schemas/   request/response models
├── core/              middleware, error handlers
├── shared/            constants, enums, exceptions, utilities, types (framework-free, no biz logic)
└── ai/                AI engine — providers, prompts, memory, orchestration
    ├── providers/     anthropic, openai, gemini, ollama
    ├── prompts/
    ├── memory/
    └── orchestration/
```

## Dev

```bash
uv sync
uv run uvicorn app.main:app --reload
```

## Migrations

```bash
uv run alembic revision --autogenerate -m "message"
uv run alembic upgrade head
```

## Tests

```bash
uv run pytest
```

## Service API keys

External systems (n8n, the Telegram bot) authenticate with a scoped,
tenant-locked API key instead of a user JWT. Keys are `read`-only for now.

Mint the first key for an org (operator/seed path — prints the secret ONCE):

```bash
make create-api-key ORG=<org-slug> NAME="n8n"
# or, inside the container:
python -m scripts.create_api_key --org-slug <org-slug> --name n8n
```

Use it on any service endpoint via either header:

```bash
curl -H "Authorization: Bearer neo_sk_..." http://localhost:8000/api/v1/service/whoami
curl -H "X-API-Key: neo_sk_..."          http://localhost:8000/api/v1/service/whoami
# -> {"organization_id": "...", "scopes": ["read"]}
```

Only the SHA-256 hash + display prefix are stored — the plaintext is shown once
and unrecoverable. The key is bound to one org; RLS scopes it exactly like a user
session. Manage keys under the caller's own org via the user-authed endpoints:
`POST/GET /api/v1/api-keys` and `DELETE /api/v1/api-keys/{id}` (revoke).
