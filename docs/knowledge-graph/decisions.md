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

---

## Phase 1-9 Build Decisions (feature/V1)

Decisions made during implementation that are not covered by ADR-001 through ADR-010.

| # | Decision | Rationale | Phase |
|---|---|---|---|
| BD-001 | **`dashboard` and `reports` apps have no own models** — they read from other apps' tables | Dashboard is a pure aggregation view; reports generate files tracked via core's CeleryTaskTracker. Avoids model proliferation. | Phase 1-9 |
| BD-002 | **Balance recompute is lazy/deferred** — allotment_service._dispatch() calls recompute_license_balance_task.delay() per item after commit | Prevents blocking HTTP responses on a potentially expensive recalculation. Celery handles retry on failure. | allotment |
| BD-003 | **`_safe_get_model()` pattern in balance_service and ledger_report** — dynamic model lookup via `apps.get_model()` | Avoids circular imports between license, allotment, bill_of_entry, and trade modules. Each service only imports what it owns. | license, reports |
| BD-004 | **CeleryTaskTracker lives in core** — view creates tracker before `.delay()`, Celery task updates it | Frontend polls task status endpoint using task_id. Decouples async state from the originating request. | reports |
| BD-005 | **allotments frontend has `api.ts` instead of `mutations.ts`** — CRUD and PDF generation in api.ts, queries in queries.ts | Structural choice matching the pattern used by licenses; `mutations.ts` pattern was adopted by bill-of-entry, tasks, reports. Both patterns are acceptable. | allotments FE |
| BD-006 | **`trade` module deferred** — backend/apps/trade/ and frontend/src/features/trade/ not yet implemented | Trade is the lowest-priority module; all other modules that depend on trade (balance_service._compute_trade) use `_safe_get_model()` and degrade gracefully to zero when the model is absent. | trade |
| BD-007 | **BOE has a `views/` package** (boe.py + ledger.py) instead of a single views.py | BOE view surface is large enough (list, detail, dispute, merge, ledger upload) to warrant splitting. Same pattern as core and license. | bill_of_entry |
| BD-008 | **Allotment PDF endpoint wired on frontend via `generateAllotmentPdf()`** in api.ts | Allotments can generate a PDF pre-auth allotment document, parallel to license PDF. Backend endpoint confirmed in allotment urls.py. | allotments |

## Open Questions (needing author input)

| # | Question | Impact |
|---|---|---|
| OQ-P1 | When will `trade` module be built? It is the last remaining backend app. | balance_service._compute_trade() currently returns 0 for all licenses; balances are understated until trade ships. |
| OQ-P2 | Should `settings` become a full feature under `frontend/src/features/settings/`? Currently only a page exists under `pages/settings`. | Determines whether to create a features/settings/ directory or keep settings as a plain page. |
