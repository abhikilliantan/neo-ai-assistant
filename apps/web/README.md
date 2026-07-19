# Neo Web

Next.js 15 (App Router) · React 19 · TypeScript · Tailwind · shadcn/ui ·
TanStack Query · Zustand · React Hook Form + Zod · Axios.

## Layout

```
src/
├── app/           App Router routes (dashboard, chat, settings, not-found)
├── components/    shared: ui/ (shadcn), layout/ (Shell, Sidebar, Topbar)
├── features/      vertical slices: chat/, dashboard/, settings/
├── hooks/         cross-feature hooks
├── services/      axios client + API modules
├── lib/           helpers (cn, env)
├── store/         Zustand slices (ui, session-placeholder)
├── types/         cross-cutting TS types
└── styles/        globals.css + Tailwind base
```

## Dev

```bash
pnpm install
pnpm dev
```
