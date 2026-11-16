---
name: performance-review
description: Measure-first performance review and optimization for License Manager ERP tasks — Django query counts/N+1, EXPLAIN on local Postgres, report generation, React render/bundle cost — with mandatory output-equality tests; layered on ECC postgres-patterns and react-performance. Use when a task targets speed, or when a reviewer suspects a query/render regression.
metadata:
  origin: project
---

# performance-review

1. **Purpose** — faster without changing a single output value.
2. **Invocation criteria** — performance tasks; diffs adding querysets/loops over models, list/report endpoints,
   materialized view use, large tables/pivots in the SPA.
3. **Required context** — ECC `postgres-patterns`, `react-performance`, `rules/ecc/common/performance.md`;
   agent `performance-engineer.md`; resource policy in `.claude/orchestration/README.md`.
4. **Workflow** — (a) baseline metric (query count via `django_assert_num_queries`/`CaptureQueriesContext`,
   `EXPLAIN (ANALYZE, BUFFERS)` on the local DB, timing, `vite build` report); (b) output-equality test on a
   fixture; (c) change; (d) re-measure on the same machine/DB; (e) report before/after.
5. **Restrictions** — no change to financial results, rounding or ordering; no unbounded caches of balances;
   indexes via `safe-migrations`; no concurrent full builds/gates; local DB only.
6. **Acceptance criteria** — equality test passes; measurable improvement recorded; no new N+1 in touched code.
7. **Verification commands** — `cd backend && TEST_DB_NAME=<db> python -m pytest <perf tests> -q`;
   `cd frontend && npx vitest run <file>`; integrator: `sh scripts/dev/quality-gate.sh <area>`.
8. **Documentation references** — `.claude/skills/postgres-patterns/SKILL.md`, `.claude/skills/react-performance/SKILL.md`,
   `.claude/agents/erp-performance.md`.
