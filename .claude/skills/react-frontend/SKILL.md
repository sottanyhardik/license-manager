---
name: react-frontend
description: Project router for React 19 + TypeScript 5.9 + Vite + Tailwind v4 + shadcn work in the License Manager SPA — applies project frontend rules and points to the ECC skills (react-patterns, react-testing, react-performance, frontend-a11y) instead of duplicating them. Use when implementing or reviewing frontend code in an ERP task.
metadata:
  origin: project
---

# react-frontend

1. **Purpose** — bind ECC React knowledge to this SPA's stack and migration direction.
2. **Invocation criteria** — edits in `frontend/src/**`.
3. **Required context** — `.claude/rules/frontend.md`, `.claude/memory/project.md` (in-flight migrations),
   `.claude/memory/components.md`, dependents of shared `components/ui/*`.
4. **Workflow** — components/hooks/data → `react-patterns`; tests → `react-testing`; renders/bundle →
   `react-performance`; forms/dialogs/tables → `frontend-a11y`. Reuse existing primitives and form
   libs (OD-09: no RHF/Zod). Show API financial values verbatim (negative CIF visible, OD-01).
5. **Restrictions** — no new packages; no API assumptions not present in the backend serializer;
   no global style/theme changes outside the brief.
6. **Acceptance criteria** — Vitest/RTL tests for behaviour; `tsc --noEmit` + eslint clean on touched files.
7. **Verification commands** — `cd frontend && npx vitest run <files> && npx tsc --noEmit -p . && npx eslint <files>`;
   `sh scripts/dev/quality-gate.sh frontend` (integrator only, never concurrently).
8. **Documentation references** — `.claude/rules/frontend.md`, `.claude/skills/react-*/SKILL.md`,
   `.claude/skills/frontend-a11y/SKILL.md`, `.claude/agents/frontend-engineer.md`.
