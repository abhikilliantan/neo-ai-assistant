# @neo/shared-types

Framework-free TypeScript transport contracts shared across `apps/web` and
future TS tooling. Consumed as source (no build step) via pnpm workspace +
Next.js `transpilePackages`.

## Rules

- No runtime code — types only.
- No business types — those belong to feature packages.
