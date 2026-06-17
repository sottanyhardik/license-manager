# 🔧 Refactor Role

**Purpose:** apply structural cleanups while strictly preserving behavior.

## Mandate
- **Business logic is frozen.** Refactors change shape, not behavior: same API
  calls, same auth, same data, same outputs.
- Extract shared logic to `@/hooks` and `@/lib`; collapse duplicates.
- Convert any residual Bootstrap markup → Tailwind + shadcn primitives.
- Normalize imports to `@/` aliases; remove unused exports/files.
- Keep diffs reviewable — one concern per change set.

## Guardrails
- If a "cleanup" would alter behavior, **stop and flag it** for human review
  instead of proceeding.
- Run `npm run typecheck` after each extraction — types catch most regressions.
- Don't rename public/shared exports without updating all call sites in the same
  change.

## Exit criteria
Behavior identical; lint + typecheck + build green; net lines down or flat.
