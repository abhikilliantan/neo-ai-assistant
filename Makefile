# Neo AI Assistant — dev entrypoint
# Thin wrapper over docker compose + workspace scripts.
.DEFAULT_GOAL := help
.PHONY: help bootstrap up down logs ps clean api api-rebuild web fmt lint test precommit migrate migration shell-db

include .env
export

help:  ## Show this help
	@awk 'BEGIN{FS=":.*##"; printf "\nUsage: make <target>\n\nTargets:\n"} /^[a-zA-Z_-]+:.*##/ {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

bootstrap:  ## Copy .env, install pre-commit + workspace deps
	@test -f .env || cp .env.example .env
	pre-commit install || true
	pnpm install
	cd apps/api && uv sync || pip install -e .

up:  ## Start the full stack (docker compose)
	docker compose up -d --build

down:  ## Stop the stack
	docker compose down

logs:  ## Tail logs (service=... to filter)
	docker compose logs -f $(service)

ps:  ## Show running services
	docker compose ps

clean:  ## Stop stack and remove volumes
	docker compose down -v

api:  ## Run FastAPI locally (no docker)
	cd apps/api && uvicorn app.main:app --reload --port 8000

api-rebuild:  ## Rebuild api image + refresh anon volumes (use after adding a Python dep)
	# docker-compose.override.yml mounts an ANONYMOUS volume at /app/.venv.
	# Anon volumes are sticky across `docker compose up -d`, so a plain rebuild
	# reattaches the stale pre-dep venv → ModuleNotFoundError crash-loop that a
	# normal rebuild never fixes. --renew-anon-volumes discards it. Bitten twice.
	docker compose build api && docker compose up -d --force-recreate --renew-anon-volumes api

web:  ## Run Next.js locally (no docker)
	pnpm --filter web dev

fmt:  ## Format everything
	pnpm -w run format
	cd apps/api && ruff format . && ruff check --fix .

lint:  ## Lint everything
	pnpm -w run lint
	cd apps/api && ruff check . && mypy app

test:  ## Run tests
	pnpm -w run test
	cd apps/api && pytest

precommit:  ## Run pre-commit against all files
	pre-commit run --all-files

migrate:  ## Apply alembic migrations inside the running api container
	docker compose exec api alembic upgrade head

migration:  ## Create alembic migration (usage: make migration name="add users")
	docker compose exec api alembic revision --autogenerate -m "$(name)"

shell-db:  ## psql shell into postgres
	docker compose exec postgres psql -U $(POSTGRES_USER) -d $(POSTGRES_DB)
