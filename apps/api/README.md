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
