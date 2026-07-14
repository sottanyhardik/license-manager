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

## Resolved Pre-Phase-1 Decisions

| # | Decision | Rationale |
|---|---|---|
| OQ-A | **HS256, shared `SECRET_KEY`** between legacy and `backend/` during transition | Tokens mutually verifiable — no forced re-login when switching. Switch to RS256 at final cutover. |
| OQ-B | **Separate Redis DB index** — legacy uses `/0`, `backend/` uses `/2` | Same Redis server, zero operational overhead, zero task-queue namespace collision. |
| OQ-C | **Performance benchmark endpoints** (10): licenses/list, licenses/:id, trades/create, reports/balance, upload-ledger, allotments/list, bill-of-entries/list, masters/companies, licenses/:id/generate-pdf, dashboard | Covers all major access patterns — read-heavy, write, async, PDF, aggregation. |
| OQ-7 | **`managed=False` proxy** pointing at `accounts_user` table during transition | Zero migration, zero risk. Migrate to `Profile` OneToOne at final cutover. |

## Pending Decisions

*None blocking Phase 1. Phase 1 (Authentication module) may begin once Phase 0 exit gate passes.*
