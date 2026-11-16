---
name: typescript-development
description: TypeScript conventions for the frontend (strict types, API typing). Use when writing/changing .ts/.tsx.
metadata:
  origin: project
---
1. Index first: `grep -i Name .claude/index/symbols.tsv`, blast radius `grep '^path' .claude/index/dependents.tsv`; read only the needed line ranges.
2. `tsconfig.json` is strict — no `any`, no `@ts-ignore`/non-null `!` to silence errors; narrow with type guards.
3. API response types live with clients in `frontend/src/api` / `frontend/src/types`; keep them in sync with DRF serializers (field names are contract).
4. Money/quantities from the API arrive as strings/decimals — don't coerce to float for arithmetic that is displayed as balances; format only.
5. Check: `cd frontend && npm run typecheck` then `npm run lint`. Review: `typescript-reviewer`.
