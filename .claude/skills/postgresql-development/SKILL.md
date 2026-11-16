---
name: postgresql-development
description: PostgreSQL/ORM query and index work for this repo. Use for slow queries, raw SQL, indexes, materialized views.
metadata:
  origin: project
---
Generic: ECC `postgres-patterns`. Design questions → `database-architect`; review → `database-reviewer`.

1. Index first: `grep -i Name .claude/index/symbols.tsv`, blast radius `grep '^path' .claude/index/dependents.tsv`; read only the needed line ranges.
2. ORM first; raw SQL only when needed, always parameterised (never f-string SQL).
3. Measure on the **local** DB: `EXPLAIN (ANALYZE, BUFFERS)`, Django `CaptureQueriesContext` for N+1.
4. Indexes: justify with a plan; large tables → `AddIndexConcurrently` in a non-atomic migration.
5. Materialized views / ledger SQL feed balances — changes need `cif-balance-auditor` (`.claude/rules/business-rules.md`).
6. Postgres: 18 local, 16 in CI — avoid 17+/18-only features.
