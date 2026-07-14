# Decisions

> Summary index of all ADRs. Full text in `docs/adr/`.
> Update this file when a new ADR is created or its status changes.

| ADR | Title | Status | Date |
|---|---|---|---|
| ADR-001 | Migration strategy — Hybrid parallel-run | Accepted | Phase 0 |
| ADR-002 | Database strategy — Single shared PostgreSQL | Accepted | Phase 0 |
| ADR-003 | Backend tech stack — Python 3.13, Django 6.x, uv, Ruff | Accepted | Phase 0 |
| ADR-004 | Frontend tech stack — React 19, TypeScript, Vite, TanStack, shadcn/ui | Accepted | Phase 0 |
| ADR-005 | API versioning — /api/v1/ prefix | Accepted | Phase 0 |
| ADR-006 | Authentication — SimpleJWT, shared signing key during transition | Accepted | Phase 0 |
| ADR-007 | Service layer — views never touch ORM | Accepted | Phase 0 |
| ADR-008 | Signal strategy — Celery tasks replace cross-app signals | Accepted | Phase 0 |
| ADR-009 | Production cutover gate — 6 simultaneous criteria | Accepted | Phase 0 |
| ADR-010 | Legacy read-only rule — no commits except emergency hotfixes | Accepted | Phase 0 |

## Pending Decisions

| # | Question | Owner | Needed By |
|---|---|---|---|
| OQ-A | JWT signing: HS256 (shared) vs RS256 during transition | PM | Phase 1 start |
| OQ-B | Celery broker: shared Redis vs separate DB index | PM | Phase 1 start |
| OQ-C | Performance benchmark endpoint list (10 endpoints) | PM | Phase 1 start |
| OQ-7 | User model: managed=False proxy vs Profile OneToOne | PM | Phase 1 start |
