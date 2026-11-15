# Claude Graph — Global Rules

> These are **specification docs**, not autonomous daemons. This harness has no
> standing multi-agent graph or auto-merge. Treat each file in `.claude/graph/`
> as a role brief you (or a spawned subagent / Workflow) adopt for one bounded
> run. Anything outward-facing or hard to reverse (commit, push, merge, delete,
> dependency changes) is **confirmed with the human first** — the `auto_*` flags
> below describe intent within a run, not permission to act unattended.

## Stack (source of truth — verify before assuming)

- React **19.2**, TypeScript **5.9** (strict via `tsconfig.json`)
- Tailwind **v4** (`@tailwindcss/vite`), CSS entry `src/styles/tailwind.css`
- shadcn/ui — style `new-york`, `cssVariables: true`, base color `slate`, `tsx: true`
- Icons: **lucide-react** only. `bootstrap-icons` is a migration leftover — remove, never add usages.
- Primitives: Radix (`@radix-ui/*`), animation: `framer-motion`
- Build: Vite (`rolldown-vite`), `@vitejs/plugin-react-oxc`
- Aliases: `@/components`, `@/components/ui`, `@/lib`, `@/lib/utils`, `@/hooks`
- Toasts: `sonner` is the target. `react-toastify` is legacy — migrate toward sonner, don't add new react-toastify calls.

## Quality gates (must pass before "done")

```yaml
quality:
  lint:        eslint .          # cd frontend && npm run lint
  typecheck:   tsc --noEmit      # cd frontend && npm run typecheck
  build:       vite build        # cd frontend && npm run build
  accessibility: AA
  responsive:  required
```

## Working rules

- **Preserve business logic.** UI/UX refactors must not change behavior, API
  calls, auth, or data flow. Flag any behavior change explicitly for review.
- Prefer Tailwind utilities over bespoke CSS. No new `.css` files without reason
  (only 4 exist today — keep it that way).
- Reuse existing `@/components/ui/*` primitives before writing new ones.
- Remove unused imports/files as you touch them; never duplicate components.
- Consistent hover/focus states; shared animation timings via Framer Motion.
- Keep DOM depth and layout spacing tight (compact mode).
- Run lint + typecheck after each meaningful change; build before declaring done.

## How to actually run a "graph" pass

- **One role, focused:** spawn an `Agent` (or use the `code-review` / `ui-ux-pro-max`
  skills) with the matching `.claude/graph/<role>.md` as its brief.
- **Fan-out / pipeline:** author a `Workflow` script that runs roles over the file
  list (find → review → verify → synthesize). Opt-in only.
- See `.claude/memory/decisions.md` for log of choices made.
