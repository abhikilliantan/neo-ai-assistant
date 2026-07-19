# syntax=docker/dockerfile:1.7
# Build context = REPO ROOT (workspace:* deps require sibling packages).

FROM node:20-alpine AS base
RUN corepack enable && corepack prepare pnpm@9.12.0 --activate
WORKDIR /repo

# --- deps: install workspace deps for `web` only ---
FROM base AS deps
COPY pnpm-workspace.yaml package.json pnpm-lock.yaml ./
COPY apps/web/package.json ./apps/web/
COPY packages/shared-types/package.json ./packages/shared-types/
RUN pnpm install --frozen-lockfile --filter web...

# --- builder: bring in sources, build ---
FROM base AS builder
COPY --from=deps /repo/ ./
COPY packages/shared-types ./packages/shared-types
COPY apps/web ./apps/web
RUN pnpm --filter web build

# --- runtime: full workspace, run as non-root ---
FROM node:20-alpine AS runtime
ENV NODE_ENV=production
RUN addgroup -S neo && adduser -S neo -G neo
WORKDIR /repo
COPY --from=builder --chown=neo:neo /repo ./
USER neo
WORKDIR /repo/apps/web
EXPOSE 3000
CMD ["node_modules/.bin/next", "start", "-p", "3000"]
