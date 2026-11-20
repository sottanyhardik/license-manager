# Master System Acceptance Test (SAT) — Test Plan

Phase 0 deliverable · 2026-11-20 · branch `feature/v5` @ `ec3604cb` · session `backend-03`
Status: **PLAN — Phase 0 complete; Phases 1–9 not started.**

## 0. Ground rules for this SAT (from the owner's master prompt + project rules)

- Read-only against code: no commits, no push, no migrations, no stash/reset. 177 uncommitted paths in the tree
  belong to other sessions (formatting, item-pivot/Item Report, mapping, reports-menu work). The SAT **tests the tree
  as it stands** and never edits those files. A defect found in a peer-owned file is reported, not fixed.
- Data isolation:
  - Automated tests use their own Postgres DBs: `TEST_DB_NAME=test_lmanagement_sat_<purpose>`.
  - Browser workflows that **write** (Scenarios A–J) run only through `scripts/test/run_data_bearing_browser_e2e.sh`,
    which creates a fresh `test_*` DB, migrates it, seeds it (`seed_browser_2509` or a new SAT seed) and drops it.
  - The local `lmanagement` DB (a re-synced copy of real data) is used **read-only**: SELECT and API GET only, for the
    financial reconciliation audit. No writes there, not even through the UI.
  - No production host, no Celery broker shared with a real deployment, no outbound DGFT/MDS calls.
- Business rules: canonical CIF rule `.claude/rules/business-rules.md` and owner decisions in `docs/decisions/`.
  A conflict between code and a rule goes to the **User Decision Register** and is never "fixed".
- Questions to the owner are collected and asked only at Phase 10.

## 1. Baseline already established (reused, not redone)

| Prior work | Result | SAT use |
|---|---|---|
| `docs/reports/cross-surface-reconciliation-2026-11-20.md` | 2,182 licences / 26,818 items / 14,314 pivot cells. **Licence-level CIF reconciles on every surface**; item level does not (4,831 discrepancies on 2,071 licences: RC3, RC4a/b, RC7, RC11–RC16) | Phase 6 starts from it; re-run `audit_cross_surface_reconciliation` on the current tree and diff |
| `docs/decisions/2026-11-20-cross-surface-owner-decisions-da-df.md` | D-A…D-F **decided, not implemented** | Known open items. Listed as "decided, pending implementation", **not** re-asked |
| `docs/decisions/2026-11-20-item-pivot-attribution-owner-decisions-d1-d4.md` | D1–D4 decided | Same |
| Accounting checkpoint (tracker) | Phases A–P implemented + tested on test DB; 5H/8M review findings fixed | Phase 1 §9 verifies by re-execution, not by trusting the tracker |
| Reports-menu, ERP-formatting checkpoints | Verified, uncommitted | Phase 1 §10 regression |
| `docs/audit/phase-01…11-*.md`, `docs/audits/ERP_*` | Earlier module audits | Defect carry-over check: is each finding still open? |

## 2. System inventory

### 2.1 Stack
Django 6 / DRF / Python 3.14 / Postgres / Redis / Celery (`backend/`) · React 19 + TS 5.9 + Vite + Tailwind v4 +
shadcn SPA (`frontend/`) · master-data service (`master-data-service/`) + `mds-client/`.
Auth: JWT (`localStorage.access`), Django groups as roles. Roles found: `LICENSE_MANAGER`, `LICENSE_VIEWER`,
`BOE_VIEWER`, `TRADE_VIEWER`, `USER_MANAGER`, `ACCOUNTS_VIEWER`, `ACCOUNTS_MANAGER`, `ACCOUNTS_APPROVER` (+ superuser,
`REPORT_VIEWER`/`LEDGER_READ_ROLES` referenced by the frontend route guards — Phase 4 confirms the full matrix).

### 2.2 Backend surface
- 37 DRF router registrations (+ function/APIView routes). Registered resources: licenses, license-items,
  license-item-plans, license-actions, license-ledger, incentive-licenses, allotments, allotment-actions,
  bill-of-entries, lines, trades, payments, reconciliation, item-pivot, item-report, planned-report,
  inventory-balance, active-licenses, expiring-licenses, product-descriptions, sion-planning-rules, the masters
  (companies, ports, hs-codes, head-norms, sion-classes, groups, item-names, scheme-codes, notification-numbers,
  purchase-statuses, transfer-letters, exchange-rates, unit-prices), users, activity-logs, tasks; and the
  accounting API (`apps/accounting/api/*`).
- Celery tasks: `apps/core/tasks.py`, `apps/core/tasks_materialized_views.py`, `apps/core/sync/tasks.py`,
  `apps/license/tasks.py`, `apps/core/cache_utils.py`.

### 2.3 Module map (Module → Page → API → Service → Model → Financial calc → Tests)

| # | Module | Frontend page(s) | API | Core services | Financial calc | Backend tests | FE tests |
|---|---|---|---|---|---|---|---|
| M1 | Dashboard | `pages/Dashboard.tsx` | dashboard/summary endpoints | core selectors, materialized views | KPI totals (licence count, CIF available/debited/allotted) | core | 2 (+contract) |
| M2 | Licence management | `/licenses`, `license-overview/*`, `features/licenses/*` | licenses, license-items, license-actions | `balance_calculator.py`, `license_balance_ledger_builder.py`, `canonical_ledger_service.py` | **Canonical CIF** (credit, BOE debit, allotment, billed-without-BOE, available) | license (216 files total) | license-overview 10 |
| M3 | Item mapping / product intelligence | `pages/mapping/*` | product-descriptions, import-item-names, approvals | `product_intelligence/*`, `product_matching.py`, `item_matcher.py` | none directly; feeds pivot attribution | license (mapping subset) | mapping 6 |
| M4 | Planning / SION | `pages/planning/*` | license-item-plans, sion-planning-rules | `condition_pool.py`, sion rule engine, e5/e126/e132 plans | %-pool ceilings (RC16 / D-C) | license | planning 8 |
| M5 | Bills of entry | `/bill-of-entries`, `bill-of-entry/BoeDetailPage` | bill-of-entries, lines | `apps/bill_of_entry/services/*`, exporters | BOE CIF/qty debit | bill_of_entry 16 | 1 |
| M6 | Allotments | `/allotments`, `AllotmentAction` | allotments, allotment-actions | `allotment/api/views_actions.py`, `effective_cif_mode.py` | Outstanding reservation (`cif_fc − min(cif_fc, allocated)`; M2M = full consumption) | allotment 16 | 2 |
| M7 | Reconciliation | `pages/reconciliation/*`, `ReconciliationPanel` | reconciliation | `boe_link_reconciler`, `allocation_service`, `warning_service` | BOE↔allotment netting | reconciliation 6 | 1 of 9 src |
| M8 | Trades / invoices | `/trades`, `TradeForm` | trades, payments | `trade_service`, `invoice_document_service`, invoice PDFs | Billed CIF, `amount_inr` server pricing (T1–T4) | trade 13 | 2 |
| M9 | Accounting & banking | `pages/accounting/*` (20 src) | `apps/accounting/api/*` | `posting.py`, `invoices.py`, `payments.py`, `banking.py`, `loans.py`, `migration.py`, `selectors/reports.py` | Double entry, party ledgers, BRS, P&L, consolidation | accounting 10 | 4 |
| M10 | Item Pivot | `/reports/item-pivot` | item-pivot (+ excel, intelligence) | `item_pivot_service.py`, `item_pivot_selection.py`, `item_pivot_item_summary.py` | Item attribution D1–D4, D-A | license | reports (subset) |
| M11 | Item Report | `/reports/item-report`, `itemReport/*` | item-report, item-report-products | `item_report_products.py`, `item_usage.py` | Stored vs live `available_value` (RC4b) | license | reports (subset) |
| M12 | Other reports | planned-report, licence purchase/profit, active/expiring, SION norm, inventory balance, download licence | matching endpoints | report views | profit, inventory balance | license | reports |
| M13 | Licence ledger / downloads / customs PDF | `/license-ledger*`, `LicenseLedgerDetail` | license-ledger | `custom_ledger_pdf.py`, financial ledger renderers | Ledger totals (RC14 tautology) | license | license-ledger 2 + LicenseLedger* |
| M14 | Exports (Excel/PDF) | export buttons across M2–M13 | export endpoints | `core/exporters/excel/*`, `cell_formats.py`, `pdf_utils.py`, BOE/allotment exporters | Totals in workbook (SUM vs DTO) | golden + cell-type tests | LicenseExportPanel |
| M15 | Masters | `/masters/*` (13 pages) | master routers | `core/views/master_view.py` | exchange rates, unit prices | core | masters 21 |
| M16 | Users, roles, auth, activity log | `Login`, `Profile`, `admin/*`, `Settings` | users, activity-logs, token | `apps/accounts` | — | accounts 5 | Login/Profile; auth/ 0, settings/ 0 |
| M17 | Background jobs / sync / MDS | `TaskDrawer`, `MdsStatusCard` | tasks | `core/sync/*`, `tasks*.py` | materialized-view refresh (staleness source) | tasks **1** | 0 |

### 2.4 Coverage gaps (candidates for Phase 8)
- `apps/tasks` (1 test file / 9 src), `apps/reconciliation` (6 / 19), frontend `reconciliation/` (1 test / 9 src),
  `auth/`, `settings/`, `errors/` (0 tests), `bill-of-entry/` detail page (1 test).
- No browser coverage yet for: allotment → BOE conversion (Scenario B), invoice ↔ BOE no-double-count (C),
  BOE import (D), Item Pivot ↔ Item Report equality (E/F), PDF ↔ screen (H), partial payment (I), bank
  reconciliation UI (J). Existing real-backend specs: `data-bearing`, `accounting`, `licence-edit`,
  `licence-ledger-onepage`, `licence-payment-ledgers`, `masters-*`, `workspaces*` (31 spec files in total).
- No role-matrix test that exercises **every** endpoint for every role (Phase 4).

## 3. Test environment

| Item | Value |
|---|---|
| Backend gate | `TEST_DB_NAME=test_lmanagement_sat_backend scripts/dev/quality-gate.sh backend` → `/tmp/sat/gate-backend.log` |
| Frontend gate | `scripts/dev/quality-gate.sh frontend` → `/tmp/sat/gate-frontend.log` |
| Browser (write) | `scripts/test/run_data_bearing_browser_e2e.sh` (fresh `test_*` DB, seeded, dropped on exit), ports 8000/41731 |
| Browser (read-only, real data) | Playwright GET-only specs against a local `lmanagement` runserver. Created users only in `test_*` DBs |
| Financial audit | `manage.py audit_cross_surface_reconciliation` (read-only) + independent SQL/ORM recomputation scripts in `/tmp/sat/` |
| Performance | `django.test.utils.CaptureQueriesContext` / `connection.queries` on read-only endpoints; Playwright timings |
| Evidence | `/tmp/sat/<phase>/…` logs + screenshots; figures copied into the reports with exit codes |

## 4. Execution plan

| Phase | Work | Owner (agent, model) | Output |
|---|---|---|---|
| 1 Functional | M1–M17 checklists from the master prompt, executed via the API tests + browser harness | backend QA (sonnet), frontend/Playwright QA (sonnet) | `FUNCTIONAL_TEST_RESULTS.md` |
| 2 Financial audit | Independent recomputation of the canonical components per licence from the source tables (BOE lines, allotment items, `BOEAllotmentAllocation`, trade SALE lines, export items) vs every engine/surface. Edge-case fixtures in a test DB | cif-balance-auditor + invoice-auditor + boe-reconciliation-auditor (**opus**) | `FINANCIAL_INTEGRITY_AUDIT.md` |
| 3 UI/UX | Playwright at 1440 / 820 / 390 px on all 26 top-level routes plus the accounting, mapping and planning sub-routes. Scenarios A–J on the isolated harness | Playwright QA (sonnet) | `UI_UX_ACCEPTANCE_REPORT.md` |
| 4 Security | Role × endpoint matrix (direct API calls, not just hidden buttons), CSRF/JWT, upload validation, file access | security-auditor (opus) | `SECURITY_AND_PERMISSIONS_REPORT.md` |
| 5 API/DB/perf | Schema/status/serialization checks; FK/unique/orphan/precision queries (read-only); query counts and timings for the listed screens | performance-engineer + database-reviewer (sonnet) | `PERFORMANCE_REPORT.md` |
| 6 Cross-surface | Re-run the reconciliation audit on the current tree; matrix Licence Detail = Pivot = Item Report = Excel = PDF; classify each mismatch | orchestrator + cif-balance-auditor (opus) | `CROSS_SURFACE_RECONCILIATION.md` |
| 7 Registers | Defect Register (confirmed only) + User Decision Register (new questions only; D-A…D-F / D1–D4 listed as decided) | orchestrator | `DEFECT_REGISTER.md`, `USER_DECISION_REGISTER.md` |
| 8 Regression | Tests for each confirmed defect, **in new SAT-owned files only**. Fixes only for clear technical defects in files no peer session owns | qa-test-engineer (sonnet) | new test files |
| 9 Report | Totals, module status table (PASS / PASS WITH DOCUMENTED EXCEPTIONS / FAIL / BLOCKED / NOT TESTED) | orchestrator (opus) | `MASTER_ACCEPTANCE_REPORT.md` |

Parallelism: Phases 2, 4 and 5 are read-only and independent, so they can run concurrently. Phase 3 (browser) owns
ports 8000/41731 exclusively. Phase 6 depends on 2. Agents own disjoint output files.

## 5. Acceptance gates

| Gate | Requirement |
|---|---|
| Financial integrity | Zero **unexplained** discrepancies (explained = traced to a source record + classified) |
| Functional | All critical workflows executed; untested ⇒ module cannot be PASS |
| UI/UX | Every visible control on the tested pages exercised |
| Cross-surface | Screen = Excel = PDF for identical scope, or a classified exception |
| Security | No unresolved Critical/High |
| Backend / Frontend | `quality-gate.sh` exit 0 (or each failure classified as pre-existing / peer-owned / introduced) |
| Performance | No unexplained regression against `trades.performance.spec.ts` and prior baselines |
| User decisions | Register delivered; nothing business-rule-dependent implemented |

## 6. Known constraints and risks for the SAT itself

1. **Moving target:** peer WIP in `item_pivot_*`, `item_report*` and the mapping files. Results are pinned to this
   tree snapshot (`git diff --stat` hash recorded at each phase).
2. Known item-level discrepancies (RC3/RC4/RC7/RC13–RC16) will reappear until D-A…D-F are implemented. They are
   carried as **decided, pending implementation**, not as new findings.
3. The local DB is re-synced by other tools; each read-only audit records row counts at start so the figures can be
   reproduced.
4. Celery/Redis: the jobs are tested eagerly (`CELERY_TASK_ALWAYS_EAGER` in tests). There is no live broker soak test.
5. Multi-entity accounting (Labdhi Mercantile LLP / Labdhi Global LLP) is tested only where `EntityBooks` exists in a
   test DB. Real books are never activated.

## 7. Phase 0 baseline gate results

See §7.1 (filled when the background gates finish).
