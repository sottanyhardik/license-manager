# Context — Frontend

Orientation only. Authoritative rules: `rules/react.md`, `rules/typescript.md`,
`rules/frontend-ui.md`. Role briefs: `graph/ui.md`, `graph/ux.md`,
`graph/design-system.md`.

## Stack (verify before assuming)

- React **19** + TypeScript **5.9** (strict), built with **Vite** (rolldown).
- **Tailwind v4** (`@tailwindcss/vite`), CSS entry `src/styles/tailwind.css`.
- **shadcn/ui** — style `new-york`, base color `slate`, CSS variables on; Radix primitives.
- `framer-motion` (animation), `cmdk` (Cmd+K palette), `react-router-dom` v7 (routing).
- Icons `lucide-react`; toasts `sonner`. (`bootstrap-icons` / `react-toastify` are legacy.)

## Structure

- Source under `frontend/src/**`.
- Reusable primitives: `@/components/ui/*`. Page-local components co-locate with the page.
- Shared state via existing contexts only: `AuthContext`, `ThemeContext`, `ToastContext`.
- Data fetching through the single axios instance `@/api/axios` or a `services/` module —
  never `fetch()` directly, never a second axios instance.
- Shared domain types in `@/types`; import via `@/…` path aliases (no deep `../../../`).
- Routes are lazy-loaded via `lazyLoadWithRetry` and gated by `ProtectedRoute`.

## Gates

`npm run lint` → `npm run typecheck` → `npm run build` (run from `frontend/`). No JS test
runner is the security boundary — see `graph/qa.md`.

## Deep dives

| Topic | File |
|---|---|
| UI rules (Tailwind + shadcn) | `rules/frontend-ui.md` |
| React conventions | `rules/react.md` |
| TypeScript conventions | `rules/typescript.md` |
| Design tokens / theme | `graph/design-system.md` |
| API client behavior | `context/api.md` |
