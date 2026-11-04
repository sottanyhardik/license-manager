# Full-System Execution Tracker

Statuses: NOT_STARTED, IN_PROGRESS, BLOCKED, IMPLEMENTED, TESTED, VERIFIED, COMPLETE.
A task is COMPLETE only when implementation and acceptance tests pass. Update this file after every workstream.

Last updated: 2026-11-04 (execution cycle 3). Next executable task: **T-PLAN-03**.

## P0 — Financial integrity

| ID | Task | Owner | Files | Status | Evidence / blocker |
|---|---|---|---|---|---|
| T-INC-01 | Local incentive reconciliation (10 correctable rows) | Principal Architect | `management/commands/reconcile_incentive_license_status.py`, `reports/incentive_status_backup_20261103_185849.json` | VERIFIED | Corrected rows match live SALE sums; 0 mismatches; repeat dry-run 0 correctable; 135, 198, 256, 269 untouched. |
| T-INC-02 | Root cause of stale caches (why licences 1–8 were not recalculated) | Incentive ownership | `trade/models.py` signals, `IncentiveLicense.update_sold_status` | NOT_STARTED | Signals do not fire on every write path. Write path that left caches stale not yet identified. |
| T-INC-03 | Automated tests: reversal, deletion, partial/full transfer, duplicate lines, concurrent reconciliation | Incentive ownership | `apps/license/tests/test_incentive_*` | IN_PROGRESS | Existing reconciliation tests were written by another session and are not yet re-run in this cycle. |
| T-PLAN-01 | Authoritative planning budget module (export-manifest Original, canonical utilisation, licence-level cap, norm attribution) | Planning execution | `apps/license/services/planning_financial_budget.py` | TESTED | Pure calculation plus DB adapter `planning_budget_for_licence_norm`. 29 oracle tests pass (`test_planning_financial_budget.py`). |
| T-PLAN-02 | Wire budget into SION execution; remove legacy ceiling as decision input | Planning execution | `apps/license/services/sion_planning_execution.py` (has the user's uncommitted work; edited around it) | IMPLEMENTED | Legacy raw-balance block removed from decisions. Blocked results carry `budget_trace`. `skipped_count` now counts BLOCKED statuses. |
| T-PLAN-03 | Investigate planner re-writing the seed plan (`allocation_provenance` lost in `test_seed_browser_2509_creates_idempotent_canonical_fixture`) | Planning execution | `management/commands/seed_browser_2509.py`, planning persistence path | BLOCKED | Planned qty (234.325) and CIF (2066.75) now match the seed constants, but the planner still overwrites the seed row. Cause not yet isolated. |
| T-PLAN-04 | Adapter-level DB test for attribution (target exported under one norm vs two norms; cross-norm isolation) | Planning execution | new test file | NOT_STARTED | Pure rules are covered; the DB adapter is covered only indirectly by the SION suites. |
| T-PLAN-05 | Frontend: remove legacy `balance_cif` fallback in Planning editor | Frontend | `frontend/src/components/planning/PlanningEditor.tsx` (line ~725) | VERIFIED | Missing canonical value → 0. `tsc` exit 0. 13 tests pass across Planning editor and its consumers. |
| T-PLAN-06 | Frontend: display Original, BOE, allotment, billed-without-BOE, utilised, available, ceiling, source/scope | Frontend | `LicensePlanningPanel.tsx`, `PlanningEditor.tsx` | NOT_STARTED | Backend result carries `budget_trace`; not yet rendered. |

## Test status

| Suite | Result | Notes |
|---|---|---|
| SION regression (`test_sion_planning_execution_caps`, `test_sion_over_utilisation_block`, `test_sion_planning_rules`, `test_e5_production_configuration`) + `test_planning_financial_budget` | **92 passed, 0 failed** | Includes the 59 original SION tests. |
| `test_seed_browser_2509_command.py::…idempotent_canonical_fixture` | **FAILED — introduced by this cycle** | See T-PLAN-03. |
| Broader planning/SION/canonical/allocation selection (`apps/license/tests`, `apps/allotment/tests`, `-k` filter) | 964 passed, 7 failed | 5 failures are in the pre-existing baseline list (`test_item_pivot_planned_import_item` ×2, `test_plan_utilization`, `test_available_licenses_plan_mode`, `test_module3_allocation_scenarios::test_16`). 1 is the seed test above. `test_plan_norms_command_live_balance` passes after the skipped-count fix. |
| Known collection error | Unchanged | `test_parse_pdf_hs_autocreate.py` (`SAMPLE_PDF_DATA`), pre-existing. |
| Frontend typecheck (`tsc --noEmit`) | PASS (exit 0) | |
| Frontend targeted tests (Planning editor, LicencePlanningTab, LicenseOverviewPage) | 13 passed | |
| Full frontend suite, lint, production build | NOT RUN this cycle | |

## Not started

| ID | Workstream | Status |
|---|---|---|
| T-LED-01 | Licence Ledger: summary/detail reconciliation, company isolation, export consistency | NOT_STARTED |
| T-LED-02 | Licence-wise ledger payload (~495 KB): field selection, pagination, query review | NOT_STARTED |
| T-UPL-01 | Ledger Upload: CSV, XLSX, XLS, HTM, HTML; preview; row-level errors; idempotency; audit | NOT_STARTED |
| T-LIC-01 | Licences: every filter end-to-end (URL ↔ UI ↔ API ↔ DB), clear-all, pagination reset, export | NOT_STARTED |
| T-UI-01 | Shared enterprise UI components across the five modules | NOT_STARTED |
| T-PLN-01 | Planning Workbench action consolidation (latest saved rule authoritative; no RuleVersionHistory) | NOT_STARTED |
| T-PERF-01 | Query counts, N+1, indexes, large payloads | NOT_STARTED |
| T-SEC-01 | Company isolation, export permissions, upload security, audit history | NOT_STARTED |
| T-BRW-01 | Browser acceptance on all five routes using the signed-in session | NOT_STARTED |
| T-CLN-01 | Evidence-based cleanup (deletion register) | NOT_STARTED |

## Database operations

| When | Environment | Operation | Result |
|---|---|---|---|
| 2026-11-03 (prior cycle) | `lmanagement`, localhost:5432 (local dev) | `reconcile_incentive_license_status --apply` | 10 licence cache rows corrected; backup written |
| 2026-11-04 (this cycle) | none | No migrations, no data writes | Read-only checks only |

## Repository safety

- No commits. No pushes. No service restarts. No port changes.
- Concurrent work is present in the tree. This cycle edited only the files listed above, and only around existing uncommitted changes.
- Untracked and modified files from other sessions have not been removed.
