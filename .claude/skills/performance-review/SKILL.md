---
name: performance-review
description: Measure-first performance review (Django queries, indexes, reports, React renders, bundle). Use for slowness or before shipping heavy endpoints/pages.
metadata:
  origin: project
---
Generic: ECC `react-performance`, `postgres-patterns`. Specialist: `performance-engineer`.

1. Index first: `grep -i Name .claude/index/symbols.tsv`, blast radius `grep '^path' .claude/index/dependents.tsv`; read only the needed line ranges.
2. Measure before changing: query count/time (`CaptureQueriesContext`, `EXPLAIN ANALYZE` on local DB), endpoint timing, `npm run build` chunk sizes, React render profiling.
3. Usual suspects: N+1 in list/export serializers, per-row balance calls instead of bulk services, missing indexes, unpaginated lists, large synchronous reports (→ Celery), eager imports of heavy pages (→ lazy routes).
4. Fix only the proven bottleneck; re-measure and report before/after.
5. Balance/report query changes → `cif-balance-auditor` (results must be identical).
