# V1 Issue Register

Companion to [V1_MASTER_TRACKER.md](./V1_MASTER_TRACKER.md).

Severity: Critical / High / Medium / Low.
Status: `OPEN` · `IN PROGRESS` · `BLOCKED` (needs a business decision) · `VERIFIED` (reproduced by test or data) · `RESOLVED` · `WONTFIX` (with decision reference).

"Evidence" names the test, code line or data run that backs the claim. Money figures use the unit of the field they come from: `cif_fc` is foreign currency (USD for most rows), not INR.

## Phase 1 observations

| ID | Module | Severity | Status | Observation | Evidence / next step |
|---|---|---|---|---|---|
| ISS-001 | Customer Management | Medium | RESOLVED (design) | No standalone customer model existed. Resolved by DEC-003: customers are roles on the unified Company master. | Implementation tracked under Company Master. |
| ISS-002 | Invoice Management | Medium | OPEN | Invoices are split across `license.Invoice`/`InvoiceItem`, `trade.TradeInvoiceDocument` and `reconciliation.InvoiceBOEAllocation`. | Map in Phase 3 (Trade) and Phase 5 (Invoice). |
| ISS-003 | Repository | Low | OPEN | `backend/apps/accounting/` is an empty directory, untracked by git, not in `INSTALLED_APPS`. | Verified: `git ls-files backend/apps/accounting` is empty. Record in cleanup register, then remove. |
| ISS-004 | Repository | Low | OPEN | Root and `backend/` hold many one-off scripts, sample data, backups, logs and a third-party template folder. | Classify in V1_CLEANUP_REGISTER.md before any removal. |
| ISS-005 | Repository | Low | VERIFIED | `backend/db.sqlite3` is not tracked by git. | Verified: `git ls-files backend/db.sqlite3` is empty. Confirm `.gitignore` coverage. |
| ISS-006 | Testing | High | IN PROGRESS | Quality gate status, measured this pass (see §Gate results below). Backend full suite is running; result to be recorded. | Frontend gates: typecheck pass, lint pass (9 warnings, 0 errors), vitest pass after ISS-018, build pass. |
| ISS-007 | Documentation | Medium | OPEN | About 200 existing docs under `docs/` overlap and may be stale. | Audit before any replacement. No deletion before migration (DEC-005). |

## Phase 2 findings — Licence Management

| ID | Module | Severity | Status | Observation | Evidence / next step |
|---|---|---|---|---|---|
| ISS-008 | Balance Engine | High (see note) | VERIFIED | A partly used allotment loses its unused reservation. Example: CIF 100, allotment 40, BOE 25. Engine: reserved 0, remaining 75. Brief: reserved 15, available 60. | Code: `balance_calculator.py` `_annotate_allotment_contribution`, `When(has_linked_boe, then=0)` overrides the remainder `cif_fc - matched`. Test: `test_scenario_b_partial_utilisation_reserved_and_available` (strict xfail). **Data (read-only run on local DB):** 53 of 222 licences hold 4,808,628.02 FC of unused linked-allotment remainder that the engine drops. **Note:** whether the remainder is *reserved* or *released* is a business rule — see ISS-016 and DEC-010. Escalate to Critical if allocation validation uses this figure. |
| ISS-009 | Balance Engine | Medium | VERIFIED | `calculate_balance` floors at 0, so over-utilisation is hidden. Example: CIF 100, BOEs 90 and 20: debit 110, balance 0. | Test: `test_scenario_g_over_utilisation_is_floored_and_not_signalled`. Rejection must happen at BOE save; not yet verified. |
| ISS-010 | Allotment | High | VERIFIED (code) | Allotment cancellation is a hard delete. `destroy_allotment` calls `allotment.delete()`, which cascades to items. The brief requires reversals and no permanent deletion of financial records. | `backend/apps/allotment/views.py` `destroy_allotment`. Test `test_scenario_e_…` documents current behaviour. Check whether `allotment.AuditEvent` records the delete. |
| ISS-011 | Allotment | Medium | VERIFIED (absent) | No partial cancellation of unused reservation. Allotments are cancelled whole. | Scenario F skipped with this reason. |
| ISS-012 | Balance Engine | Medium | OPEN | No quantity-balance scenarios. CIF and quantity are separate paths (`ItemBalanceCalculator`) and must not be assumed to reconcile. | Build quantity scenarios. |
| ISS-013 | Repository / Security | Medium | VERIFIED | `.env` is tracked by git. It was 0 bytes at inventory. | `git ls-files .env` returns `.env`. Check history for secrets. Untracking or history rewrite needs approval. |
| ISS-014 | Company Master | Medium | OPEN | `core.CompanyModel` is the existing company table, keyed on a unique IEC. It has single-value contacts, no roles, no addresses or documents table. It inherits `MasterSyncMixin` (`master_uid`, `sync_version`, `is_tombstone`, `origin_server`, `synced_at`), so rows are replicated through `apps/core/sync/`. | Read: `apps/core/sync/mixins.py`, `push.py`, `service.py`. New role, address and contact tables must be sync-aware or deliberately local. Decide before schema change. |
| ISS-015 | Documentation | Low | OPEN | `docs/v1/business-requirements/` contains two untracked files of unknown provenance. | Read before deciding. Do not move or delete without a cleanup-register entry. |
| ISS-016 | Balance Engine | **Critical** | BLOCKED (business decision) | **There is no single balance. At least five CIF-balance functions exist, and they disagree.** `calculate_balance` (50 callers), `calculate_financial_balance` (38), `calculate_customs_balance`, `calculate_opening_balance`, `calculate_item_balance` (3, ignores allotments entirely), `calculate_available_value_for_allocation`. Their docstrings describe "two Balance Engines" with hidden-BOE, purchased-CIF and trade rules. This breaks DEC-007 and the brief's single-source rule. | **Data (read-only, 222 licences):** `balance` ≠ `financial` on 183; `balance` ≠ `customs` on 97; `customs` ≠ `financial` on 124. Example licence 2539: balance 525,220.54, customs 12.35, financial 0.00. Which figure is "available" for allotment is a business and regulatory rule the brief does not define. **Stop condition (brief §3).** See DEC-010. |
| ISS-017 | Frontend tooling | Low | RESOLVED | ESLint failed (3 errors) on `frontend/route-browser-test.js`, an unreferenced duplicate of `route-browser-test.mjs` that used `require` in an ESM package. | Removed the duplicate after a reference search (none). Recoverable from git history. Cleanup register updated. |
| ISS-018 | Frontend tests | Medium | RESOLVED | `AllocationStrategyEditor.test.tsx` expected the old percentage-row shape. The component adds `cif_restriction_percentage: null`, introduced in commit `7eed2a9e`, and the backend accepts that field. | Test expectation updated to the current contract. 8 of 8 pass. |

| ISS-019 | Backend tests | High | OPEN — **verified pre-existing** | Full backend suite on this branch: 9 failures and 1 collection error. **The same 9 failures and 1 error reproduce on an untouched `develop` checkout (d2cb2446)**, so this branch did not introduce them. Triage below. | Each needs a fix or a deliberate re-scope. Never marked as passing while failing. Priority: `test_16_pair_mismatch_rejected` first. |

### ISS-019 triage

| Test | Reason from the run | Likely area |
|---|---|---|
| `apps/license/tests/test_parse_pdf_hs_autocreate.py` (collection) | `ImportError: SAMPLE_PDF_DATA` is not exported from `apps/license/tests/conftest.py`. Stale test import. | Test infrastructure (Phase 3/4, PDF import) |
| `test_available_licenses_plan_mode.py::test_plan_candidate_query_count_is_constant_for_a_paginated_response` | 17 queries, limit 16. Query-count regression. | Allotment, available-licences query (performance) |
| `test_a3627_item_pivot_e2e.py::test_excel_export_places_each_line_under_its_category` | Expected item key `32061190` missing from the Excel export. | Item pivot export |
| `test_a3627_item_pivot_e2e.py::test_excel_rutile_block_has_unit_price_after_balance_qty` | No RUTILE block in the workbook. | Item pivot export |
| `test_module3_allocation_scenarios.py::test_16_pair_mismatch_rejected` | Expected 400 for a pair mismatch, got 201 (created). **Validation gap if confirmed; it is a business-rule check.** | Allotment allocation validation (high priority) |
| `test_item_pivot_planned_import_item.py` (2 tests) | Planned-source description shows `PP A, PP B`, expected empty; HS list is `11010000, 11010090`, expected `11010090` only. | Item pivot, planned import item |
| `test_plan_utilization.py::test_falls_back_to_item_names_then_id_for_description` | Result includes `hs_code: None`, which the test does not expect. Possibly a response-shape change. | Plan utilisation |
| `test_e132_display_sequence.py`, `test_e1_classification_sequence.py` | E132 and E1 licence not found in the Excel export. | Licence Excel export (SION) |

Priority within triage: `test_16_pair_mismatch_rejected` (a possible validation bypass, which the brief treats as critical), then the Excel export tests (customer-facing reports), then the query-count regression.

| ISS-020 | Frontend tests | Medium | OPEN | Two tests fail only in the full `vitest run`, not in isolation: `AllotmentAction` "clears a Max draft when the planning target changes" (took 2,093 ms) and `LicenseLedger` "selects all visible hierarchical rows by default…" (`toBeEnabled` assertion). Earlier full runs passed them. The pattern points to timing or load sensitivity, not logic. | Find the async waits and timeouts in both tests and make them deterministic. Do not raise timeouts to hide a real ordering bug. Confirm with repeated full runs. |

## Gate results (this pass, uncommitted working tree)

| Gate | Result |
|---|---|
| Frontend typecheck (`tsc --noEmit`) | PASS |
| Frontend lint (`eslint .`) | PASS, 0 errors, 9 warnings (pre-existing) |
| Frontend unit tests (`vitest run`) | Final full run: 542 passed, 2 failed (ISS-020). The two failing files pass in isolation (23 of 23). Not green until ISS-020 is fixed. |
| Frontend production build (`vite build`) | PASS |
| Backend balance tests (`test_balance_ledger_views.py`) | PASS, 73 |
| Backend scenario tests (`test_canonical_cif_balance_scenarios.py`) | PASS 7, strict xfail 2, skip 1 |
| Backend full suite (`pytest -n 4`, 54m) | **3,196 passed, 9 failed, 1 collection error, 1 skipped, 2 xfailed.** Failures listed in ISS-019. Not green. |
