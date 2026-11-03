# V1 Master Tracker

Branch: `feature/version-4` (from `develop`). All work is **uncommitted**.
Last updated: 2026-11-01.

Status vocabulary: `NOT_STARTED` · `IN_PROGRESS` · `BLOCKED` · `IMPLEMENTED` · `TESTING` · `COMPLETED` · `DEFERRED`.
A phase is `COMPLETED` only when implementation, tests, documentation and acceptance criteria are all met.

Companion registers:
- [V1_ISSUE_REGISTER.md](./V1_ISSUE_REGISTER.md) — findings, severity, gate results.
- [V1_DECISION_REGISTER.md](./V1_DECISION_REGISTER.md) — decisions, including the blocking business questions (DEC-010).
- [V1_CLEANUP_REGISTER.md](./V1_CLEANUP_REGISTER.md) — repository classification and actions.

## 1. Phase status

| Phase | Scope | Status |
|---|---|---|
| 0 | Initial inventory | COMPLETED |
| 1 | Architecture and coverage audit | COMPLETED |
| 2 | Licence Management and unified Company Master | BLOCKED (business decision, DEC-010) |
| 3 | Trade Management | NOT_STARTED |
| 4 | BOE Management | NOT_STARTED |
| 5 | Invoice Management | NOT_STARTED |
| 6 | Accounting and Payments | NOT_STARTED |
| 7 | Reporting and Analytics | NOT_STARTED |
| 8 | Administration and Security | NOT_STARTED |
| 9 | Full-system integration | NOT_STARTED |
| 10 | UI/UX finalization | NOT_STARTED |
| 11 | Production readiness and deployment | NOT_STARTED |

## 2. Module tracker

| Module | Explore | Critique | Specification | Implementation | Testing | Status |
|---|---|---|---|---|---|---|
| Licence Management (incl. balance engine) | COMPLETED | IN_PROGRESS | NOT_STARTED | NOT_STARTED | IN_PROGRESS | BLOCKED |
| Balance Engine (part of Licence) | COMPLETED | COMPLETED (ISS-016) | NOT_STARTED | NOT_STARTED | IN_PROGRESS | BLOCKED |
| Company Master (replaces "Customer Management", DEC-003) | IN_PROGRESS | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED |
| Allotments | IN_PROGRESS | IN_PROGRESS | NOT_STARTED | NOT_STARTED | NOT_STARTED | BLOCKED (DEC-009, DEC-010) |
| BOE Management | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED |
| Invoice Management | IN_PROGRESS | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED |
| Trade Management | IN_PROGRESS | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED |
| Reports | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED |
| Dashboard | COMPLETED | COMPLETED | IMPLEMENTED | IMPLEMENTED | IN_PROGRESS | IN_PROGRESS |
| Settings and Administration | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED | NOT_STARTED |

Other discovered modules (Authentication, Master Data, Reconciliation, SION Planning, Ledger Upload, Incentive Licences, Tasks, Background jobs) are scheduled after Phase 2 unless a dependency requires earlier work.

## 3. Phase 2 — Licence Management: what is done

### Verified

- **Balance divergence measured** (read-only, local database, 222 licences). The five CIF-balance functions disagree on most licences (ISS-016). Result is recorded in the issue register.
- **Reservation loss measured** (ISS-008): 53 licences, 4,808,628.02 FC of unused linked-allotment remainder dropped.
- **Canonical CIF scenarios** — `backend/apps/license/tests/test_canonical_cif_balance_scenarios.py`: 7 pass, 2 strict xfail (ISS-008), 1 skip (ISS-011).
- **Existing balance tests** — `test_balance_ledger_views.py`: 73 pass.
- **Frontend gates:** typecheck PASS; lint PASS (0 errors, 9 pre-existing warnings); build PASS; vitest 543 passed before the ISS-018 fix, targeted file 8 of 8 after it.

### Changed in this pass

- Removed `frontend/route-browser-test.js`, an unreferenced duplicate that failed lint (ISS-017).
- Updated `frontend/src/pages/planning/AllocationStrategyEditor.test.tsx` to the current row contract (ISS-018).
- Added the scenario test file above.
- Rewrote the three V1 registers and this tracker.
- **No balance formula, schema or API was changed.** DEC-007 and DEC-010 require the business answers first.

### Blocked

- **Consolidating the balance engine (ISS-016, DEC-010).** The brief does not define the hidden-BOE, purchased-CIF and trade rules the code uses. Five answers are needed. They are listed in the decision register.
- **Remaining-reservation output and the ISS-008 fix.** Depends on DEC-010 question 2.
- **Allotment cancellation as reversal (ISS-010, DEC-009).** Needs a rollback plan first.

### Not started

- Company Master implementation (DEC-003). Design needs the sync rules in ISS-014. This does not depend on DEC-010, so it is the next workable task.
- Quantity-balance scenarios (ISS-012). Also independent of DEC-010.
- Over-utilisation rejection at BOE save (ISS-009).

## 3a. Dashboard (module 09)

Design and contract: [09-module-implementation/dashboard.md](./09-module-implementation/dashboard.md). Status: `IN_PROGRESS`.

### Verified

- **BOE Activity and Invoice Activity render real data** against the current code. A live browser check on an isolated backend shows 10 BOE rows and 10 invoice rows, with one dashboard request and zero page errors or contract violations.
- **Single-section endpoint** `GET /api/dashboard/?section=<name>`. It returns 400 for an unknown or licence section, 403 for a role without the grant, and 200 otherwise. Retry merges that one section only.
- **Invoice aggregation** matches the trade model's own settlement properties on all 11 checks against the dev data.
- **Tests:** 48 backend dashboard tests, 716 frontend unit tests across 93 files, 5 section browser tests, plus 4 earlier browser tests. Typecheck, lint (0 errors) and production build pass.

### Root causes

- **Both errors came from a stale process, not from the current code.** The server on `127.0.0.1:8000` (PID 9723, `--noreload`, started 14:12) predates the fixes. The browser reaches it because `frontend/.env` sets `VITE_API_URL=http://localhost:8000`.
- **Two defects were in this session's code and are fixed:** builder lookup captured function objects, and the invoice split used an aggregate over an annotated queryset.

### Open

- **Restart the server on port 8000.** Until then, both sections show their errors in the browser. Port 8000 now also has a second listener (27969). Confirm which process should own it.
- **Layout:** the right-hand columns of the BOE and allotment tables are clipped at the card edge, and the fixed action bar overlaps content.
- **Backend full suite** has not been run for this change.

### Allotment activity

Design: [dashboard.md §11](./09-module-implementation/dashboard.md#11-allotment-activity-2026-11-02). Status: `IN_PROGRESS`.

- **Fixed:** a partly utilised, BOE-linked allotment was labelled "Consumed", because the engine reports zero reservation for it. Status now comes from utilised against allocated.
- **Added:** reference, licence(s), original quantity, placed and unplaced quantities, BOE count, not-reserved CIF, and section totals. The totals reconcile: allotted = utilised + reserved + not reserved. The allotment-side reserved total equals the licence-side engine total (207,550.16).
- **Open, business decision:** 37 of 44 allotments show zero utilised CIF, because their BOEs are linked without allocation rows. The not-reserved total, 4,808,628.02, matches the ISS-008 register. DEC-010 Q2 and Q4 decide this.
- **Open, data quality:** BOE debit rows and allotment items disagree on 33 of the 37 linked allotments. Four allotments have no items.
- **Tests:** 14 backend allotment tests, 62 backend dashboard tests, 741 frontend unit tests across 96 files, 4 allotment browser tests, 12 dashboard browser tests. Typecheck passes, lint has 0 errors, and the build passes. A live check on the isolated stack shows 10 rows with no overflow and no contract violations.
- **Not verified:** keyboard scrolling of the table region, in headless Chromium.

### Autonomous completion pass (2026-11-02)

- **Environment (fixed):** a `--noreload` backend launch agent (`com.license-manager.backend`) was serving stale code, and the browser reached it through `localhost:8000`. The agent is unloaded, the stale process is stopped, and the IDE-owned backend on `:8000` serves current code. `scripts/development/check-dev-ports.sh` guards against recurrence.
- **Browser (verified):** `http://localhost:5173/dashboard` makes one `/api/dashboard/` request per load, with no failed requests, no console messages and no uncaught exceptions. All three activity sections render real data. Dark theme renders. No clipping at 1440 px, and no document overflow at 390 px.
- **BOE Activity:** full-row card at `xl`, with a labelled scroll region. Matches the allotment card's layout.
- **Licence health (verified against list filters):** missing DGFT 111, expired 135, active 87, and expiry windows 0 / 6 / 13 / 20 for 7 / 15 / 30 / 60 days. All match the licence list.
- **Performance:** uncached payload 0.23–0.31 s, sections about 26 ms each, cached 10 ms.
- **Tests:** full backend 3,327 passed, with 11 failures and 4 errors. The failures are the ISS-019 baseline plus two order-dependent files (see dashboard.md §12.6). Dashboard backend 62 passed. Frontend 741 passed. Typecheck, lint (0 errors) and build pass. Dashboard browser suite 13 passed.
- **Open decision (blocks Phase 6 headline):** switch Utilised and Available CIF to the approved D-1 rule now, or hold the canonical engine until residue sign-off (P2). Recommendation: hold. See dashboard.md §12.5.
- **Open, not dashboard scope:** test-isolation debt in the ledger-package and invoice-secure-link tests; ISS-019 failures; a date-basis difference between the licence list (local date) and the dashboard (UTC).
- **Status:** `IN_PROGRESS`. Not completed: the D-1 decision is open, and the backend suite is not fully green.

## 4. Next steps

1. **Business:** answer the five questions in DEC-010. This unblocks Phase 2.
2. **Engineering, not blocked:** draft the Company Master design against `apps/core/sync/` (ISS-014). Then write quantity-balance scenarios (ISS-012).
3. **Gates:** record the backend full-suite result in the issue register, and triage any failures without marking them as passing.
