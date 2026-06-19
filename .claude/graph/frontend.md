# 🖥️ Frontend Role

**Purpose:** umbrella brief for frontend work — delegates to the focused
sub-roles and the frontend rules; load this first when a task is "frontend".

## Routing

| Concern | Brief |
|---|---|
| Visual consistency, shadcn primitives, Tailwind | `graph/ui.md` |
| Navigation, a11y, responsive, async states | `graph/ux.md` |
| Tokens, theme, color/spacing scale | `graph/design-system.md` |
| Re-renders, code-split, bundle | `graph/performance.md` |
| React conventions | `rules/react.md` |
| TypeScript (strict) conventions | `rules/typescript.md` |
| UI rules (Tailwind v4 + shadcn) | `rules/frontend-ui.md` |
| Stack/structure orientation | `context/frontend.md` |

## Mandate
- Reuse `@/components/ui/*` and existing hooks/services before building new.
- Function components + top-level hooks; data via the single axios instance.
- Tailwind utilities first; `lucide-react` icons; `sonner` toasts.
- Preserve business logic during UI changes.

## Checklist
- [ ] Right sub-role(s) consulted for the task
- [ ] No duplicate component/util (grep `components/` + `@/lib` first)
- [ ] Accessibility AA + responsive at sm/md/lg/xl
- [ ] No behavior change during a pure UI refactor

## Exit criteria
`npm run lint` → `npm run typecheck` → `npm run build` all pass (see `graph/qa.md`).
