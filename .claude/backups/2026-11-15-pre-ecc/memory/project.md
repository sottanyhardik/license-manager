# Project Memory — Frontend

> Plain project notes for the Claude Graph roles. (Distinct from the harness
> auto-memory at `~/.claude/.../memory/`.)

## What this is
License Manager — Django backend + React SPA in `frontend/`. Active branch
`feature/Version5`; PRs target `develop`.

## Frontend stack
- React 19.2, TypeScript 5.9 (strict), Vite (rolldown-vite) + react-oxc plugin
- Tailwind v4, shadcn/ui (`new-york`, lucide, slate, CSS variables)
- Radix primitives, Framer Motion, react-router-dom v7, cmdk (Cmd+K palette)
- 106 `.tsx`, 0 `.jsx` (full TS migration done), 4 `.css` files

## In-flight migration (shadcn / Tailwind v4)
- Phase 1+2: foundation, primitives, Login — done
- Phase 4b: Bootstrap CSS/JS removed, Tailwind preflight on
- Phase 4c: Bootstrap utilities swept, all icons → lucide, all files → `.tsx`
- **Open cleanup:** `bootstrap-icons` still in `package.json` deps (remove);
  `react-toastify` coexists with `sonner` (consolidate on sonner)

## src layout
`api/ assets/ components/ context/ hooks/ layout/ lib/ pages/ routes/
services/ styles/ theme/ types/ utils/`
- UI primitives: `components/ui/*`
- Design tokens: `styles/tailwind.css`, `styles/designSystem.js`, `theme/`

## Reference docs in repo
`frontend/`: REFACTORING_GUIDE.md, MIGRATION_CHECKLIST.md, MIGRATION_RESULTS.md,
FORM_ERROR_HANDLING.md, BACK_NAVIGATION.md, IS_RESTRICTED_FIELD_GUIDE.md,
CLEANUP_ANALYSIS.md

## Constraints
- Preserve business logic on all UI/UX work.
- Gates: `npm run lint`, `npm run typecheck`, `npm run build` (run from `frontend/`).
