---
name: react-development
description: License Manager React 19 + Tailwind v4 + shadcn conventions. Use when writing or changing frontend components/pages/hooks.
metadata:
  origin: project
---
Rules: `.claude/rules/frontend.md` (auto-loaded for `frontend/**`). Generic: ECC `react-patterns`, `react-performance`, `react-testing`, `frontend-a11y`.

1. Index first: `grep -i Name .claude/index/symbols.tsv`, blast radius `grep '^path' .claude/index/dependents.tsv`; read only the needed line ranges.
2. Stack: React 19, TS 5.9 strict, Tailwind v4, shadcn (`@/components/ui`), Radix, icons **lucide-react only**, toasts **sonner** (no new react-toastify), aliases `@/…`.
3. Data access through `frontend/src/api` / `services` — no ad-hoc axios in components; preserve API calls/auth/data flow in UI refactors.
4. Accessibility AA + responsive required.
5. Targeted test: `cd frontend && npx vitest run <file>`; gate: `sh scripts/dev/quality-gate.sh frontend` (lint, typecheck, vitest, build).
