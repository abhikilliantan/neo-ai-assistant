# Neo AI Assistant

Production-grade Enterprise AI Operating System.

## Stack

- **Backend**: FastAPI · Python 3.12 · Clean Architecture
- **Frontend**: Next.js 15 · React 19 · TypeScript · Tailwind
- **Data**: PostgreSQL 16 + pgvector · Redis 7
- **Automation**: n8n
- **LLMs**: Anthropic Claude · OpenAI · Gemini
- **Runtime**: Docker Compose

## Layout

```
neo-ai-assistant/
├── apps/
│   ├── api/               FastAPI service (clean architecture)
│   └── web/               Next.js 15 App Router
├── packages/
│   ├── shared-types/      TS types shared across web + tooling
│   └── py-shared/         Python contracts shared across services
├── infra/
│   ├── docker/            Dockerfiles
│   └── n8n/               n8n workflows
├── scripts/               Dev + ops scripts
├── docs/                  Architecture, ADRs
├── .github/workflows/     CI
├── docker-compose.yml
├── Makefile
└── .env.example
```

## Quickstart

```bash
make bootstrap   # copy env, install hooks + deps
make up          # start full stack
make ps          # verify services
```

Then open:

- Web: http://localhost:3000
- API: http://localhost:8000/docs
- n8n: http://localhost:5678

## Development

```bash
make api    # FastAPI hot-reload
make web    # Next.js hot-reload
make fmt    # format
make lint   # lint + typecheck
make test   # tests
```

## Architecture

See [`docs/architecture.md`](docs/architecture.md) (TBD).

The API follows Clean Architecture:

```
apps/api/app/
├── domain/          entities, value objects, domain services
├── application/     use cases, ports (Protocols)
├── infrastructure/  adapters: db, cache, llm, http
├── presentation/    FastAPI routers, schemas
├── core/            middleware, error handlers
├── shared/          constants, enums, exceptions, utilities, types
└── ai/              AI engine (providers, prompts, memory, orchestration)
```
