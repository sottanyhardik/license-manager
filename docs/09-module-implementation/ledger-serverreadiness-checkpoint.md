# License Ledger — Server-Readiness Checkpoint

**Verdict: NOT READY.** Checkpoint only. Not a completion record.
Supersedes nothing. The Phase-2 checkpoint (`ledger-phase2-checkpoint.md`) stays as the earlier record. This file is the state record for the server-readiness cycle.

## 1. Repository state (changed since the last checkpoint)

- `git status` is clean. All previously uncommitted work, including this task's Ledger changes and the other owner's `sion_planning_execution.py` and `seed_browser_2509.py` changes, is now in commit **`dd599622`** ("feat(license): add batch identity for replan requests and optimize canonical ledger loading", author `drushahardiksottany`, 2026-11-04 06:51 +0530). The commit has 133 files. I did not create it, and nothing was reverted.
- Pre-task parent: `34d7b967`. Earlier "clean HEAD" comparisons used this commit.
- Consequence: the two "working-tree-only" failures (`test_seed_browser_2509…`, `test_split_by_percent_zero_availability…`) now fail in committed history at `dd599622`. Their passing state exists only at `34d7b967`, so they are regressions relative to the parent.
- Golden snapshot `/tmp/golden_baseline_locked.json` still matches SHA-256 `a6d58a75b515afdc`.

## 2. Failure inventory (app-level gate)

| # | Test | Status | Notes |
|---|---|---|---|
| 1 | `test_plan_utilization::test_falls_back_to_item_names_then_id_for_description` | **Fixed this cycle** | Stale expectation. Commit `7a1371ac` (Oct 23, an ancestor of the parent) deliberately adds `hs_code` to item names. Assertion updated to `{"id","name","hs_code": None}`; the fixture items carry no HS code. Module: 12/12 pass. |
| 2 | `test_a3627_item_pivot_e2e::test_excel_export_places_each_line_under_its_category` | Open | Fails at `34d7b967`. Not investigated. |
| 3 | `test_a3627_item_pivot_e2e::test_excel_rutile_block_has_unit_price_after_balance_qty` | Open | "no RUTILE block in the workbook". Not investigated. |
| 4 | `test_e132_display_sequence::test_excel_columns_follow_the_same_e132_order` | Open | Not investigated. |
| 5 | `test_e1_classification_sequence::test_excel_headers_follow_the_same_e1_order` | Open | Not investigated. |
| 6 | `test_item_pivot_planned_import_item::…test_distinct_sources_remain_traceable…` | Open | Expected `''`, got `'PP A, PP B'` (description join). Not investigated. |
| 7 | `test_item_pivot_planned_import_item::…test_source_items_identify_only_the_planned_import_row` | Open | Expected `'11010090'`, got `'11010000, 11010090'` (HSN aggregation). Likely the same family as #6. Not investigated. |
| 8 | `test_license_overview_summary_view::test_returns_header_fields_and_summary_cards` | Open | Not investigated. |
| 9 | `test_seed_browser_2509::test_seed_browser_2509_creates_idempotent_canonical_fixture` | Open, owner-dependent | `KeyError: 'canonical_unit_price'`. Passes at `34d7b967`. Involves the other owner's `seed_browser_2509.py` and `sion_planning_execution.py`. Must not be modified without the owner. |
| 10 | `test_split_by_percent_strategy::test_split_by_percent_zero_availability_reports_no_remaining_plan` | Open, owner-dependent | `KeyError: 'write_result'`. Passes at `34d7b967`. Same owner dependency as #9. |

Last full app-level run, before fix #1: 10 failed, 3,238 passed, 1 skipped, 2 xfailed, 2,014 s. Log: `/private/tmp/claude-501/-Users-drushahardiksottany-Developer-projects-license-manager/87a27925-75c6-4072-9e8c-8b26731b0cbc/tasks/bpwudvq0i.output`.

## 3. Not done (acceptance gates)

- Full CI gates re-run after the changes above. Frontend lint, typecheck, test and build, backend migrations check, canonical `tests/`, and app-level. The earlier results are stale.
- Root-cause analysis and fixes for failures 2–8, each with regression coverage.
- Failures 9–10 need a decision from the owner of `seed_browser_2509.py` and `sion_planning_execution.py`: is the committed behaviour intended? Then align the tests or the code.
- Canonical financial fixtures for the mandated scenarios: multiple BOEs, allotments, transfers, billed-without-BOE, over-allocation, duplicates. Still partial.
- Metrics-builder review and before/after measurements.
- Table/filter redesign, dark-theme shared-button contrast, and the light-theme navigation accessible name.
- Browser Excel, PDF and print verification against the actual files.
- Independent reviews. None run in this cycle.
- Production-equivalent simulation and deployment runbook.

## 4. Files changed this cycle (uncommitted)

- `backend/apps/license/tests/test_plan_utilization.py`: stale `item_names` expectation updated. Test-only change.

## 5. Next commands

```bash
cd backend
../.venv/bin/python -m pytest apps/license/tests/test_a3627_item_pivot_e2e.py apps/license/tests/test_e132_display_sequence.py apps/license/tests/test_e1_classification_sequence.py apps/license/tests/test_item_pivot_planned_import_item.py apps/license/tests/test_license_overview_summary_view.py -p no:cacheprovider --no-cov -q
```

## 6. Rollback

Only `test_plan_utilization.py` changed in this cycle. Revert that file alone. Do not use `git reset` or `git clean`. Commit `dd599622` is not ours to revert.

## 7. Update — second cycle (HEAD `dd599622`, working tree: 2 entries)

- Working tree: `M backend/apps/license/tests/test_plan_utilization.py` (cycle 1 fix) and this checkpoint file. Nothing else.
- Golden snapshot still SHA-256 `a6d58a75b515afdc`.
- Failure 8, `test_license_overview_summary_view`: `assertNumQueries(47)` fails with **49 executed**. The test's own comment (line ~55) records a earlier change lowering the budget from 48 to 47 when `calculate_purchase_credit_for_licenses` was batched. Two extra queries have appeared since. The queries visible in the failure are licence-document, export-item and import-item aggregates. Fix direction: find the two added per-licence queries in the overview view path and batch them, rather than raising the budget. Not yet traced. Outside the Ledger scope.
- Failures 2–7 and 9–10: still uninvestigated beyond the earlier reproduction notes in section 2.
- No CI gate re-run, fixture work, browser verification, review, or simulation has happened in this cycle. The verdict stays NOT READY.

Next concrete action: trace the overview view's query sequence (`EXPLAIN` the 49 captured queries in the test output), locate the two extra statements, and batch them. Then re-run `apps/license/tests/test_license_overview_summary_view.py`.

## 8. Update — fast recovery cycle (HEAD `dd599622`)

- Recovery backup: `docs/09-module-implementation/evidence/recovery/test_plan_utilization.patch` (the cycle-1 test fix). Restore with `git apply -R` on that file if needed.
- Pre-change copy of the balance calculator: `/tmp/balance_calculator.before_overview_fix.py`.
- **Overview query regression fixed.** Root cause (probed by call site, probe file deleted): `calculate_opening_balance_for_licenses` recomputed `calculate_credit_for_licenses` although `calculate_financial_components_for_licenses` had already computed the same map. Change: optional `credit_map` parameter, passed from the components composer; callers that omit it keep the old behaviour. Budget stays at 47. No budget was raised.
  - File: `backend/apps/license/services/balance_calculator.py` (about lines 1549–1575 and 1690–1700).
  - Verification: `test_license_overview_summary_view.py` 7/7 pass. Balance and financial modules (`test_balance_*`, `test_financial_*`, `test_opening*`): 206/206 pass.
- Golden snapshot: not re-captured in this cycle. The canonical ledger does not call the modified method, but this must be re-verified before release.
- Still open: failures 2–7 (item-pivot, E1/E132 sequences), 9–10 (seed-browser and split-by-percent regressions in `dd599622`), the full CI re-run, the financial fixtures, the performance review, the UI, export/print verification, independent reviews, and the production simulation.
- Verdict: NOT READY.

## 9. Opening CIF lineage investigation — OPENING CIF SYSTEM-WIDE FIX — NOT COMPLETE

- Report: `docs/09-module-implementation/opening-balance-lineage.md`.
- Ultimate source: `LicenseExportItemModel.cif_fc` (licence export entitlement, written by `serializers/_license_write.py`). The gated opening is an aggregate over it, hidden-BOE debit and purchase lines.
- Verified: batched gate equals independent per-licence aggregates for 222 DFIA licences, 0 mismatches (hidden-debit input via single-licence method).
- Blocker (business decision): the canonical ledger uses an ungated opening (credit), while the financial balance and overview use the gated opening. Which figure is "Opening CIF" in each screen must be decided before any consolidation.
- Not yet verified: frontend display, Excel and PDF consumers of opening values; RODTEP and other incentive types.
- No logic or data changed in this investigation. Working tree: `balance_calculator.py` (credit_map pass-through from the earlier cycle) and the test and checkpoint files.

## 10. Opening CIF canonicalization (Option B) — PARTIAL, NOT COMPLETE

- Recovery patch (pre-change, balance_calculator + test_plan_utilization): `docs/09-module-implementation/evidence/recovery/pre-opening-canonicalization.patch`.
- Pre-change copy of the builder: `/tmp/license_balance_ledger_builder.before_opening.py`.
- Measured (read-only, 222 DFIA licences): the financial ledger builder's `computed_balance` equals the financial engine for **all 222** (0 mismatches). Its displayed opening row uses the ungated credit for 215 of 222 licences. So the approved change is a presentation and sequencing change; closing balances are already identical.
- Done: `build_financial_ledger` summary gains additive key `financial_opening_cif` = `calculate_opening_balance(license_obj)`. Verified equal to the batched gate for all 222 licences (0 mismatches). Existing rows and fields are unchanged.
- Test result: balance, financial, ledger, dashboard, BOE-hide and invoice-representation modules: 287 passed.
- Not done: the row refactor. The opening row should show the gated figure, and the separate "Previous Owner Utilisation" debit (which currently subtracts H+P) should be removed, keeping the "Licence Trade (Purchased)" add-back so the closing does not change. Consumers that must be checked first: `balance_snapshot`, `dashboard_summary`, `exporters/license_balance_excel.py`, `exporters/license_balance_pdf.py`, and the balance tests. `build()` also reads `summary['opening_balance']` as `original_cif` (line ~1664), so that field must keep meaning the licence-master CIF.
- Not done: frontend consumers and Excel/PDF reconciliation for the financial-opening figure; RODTEP and incentive types.
- Cost: the builder now issues one extra single-licence gate call per licence. Not yet measured; it should be batched before release.
- Verdict for this workstream: **NOT COMPLETE**. The working tree holds the additive key in `license_balance_ledger_builder.py`. Next action: refactor the opening rows after the consumer audit above, and re-verify closing parity for all 222 licences.

## 11. Opening CIF system-wide audit — cycle 3 — OPENING CIF SYSTEM-WIDE FIX — NOT COMPLETE

- Working tree (HEAD `dd599622`): `balance_calculator.py` (credit_map pass-through, verified against source), `license_balance_ledger_builder.py` (additive `financial_opening_cif`), `sion_planning_execution.py` (ticket 0311040958 fix: blocked licence returns a `write_result`), `test_plan_utilization.py`, new `test_sion_persist_outcomes.py`. Nothing committed. Note: section 1's "git status is clean" is no longer true.
- Verified: overview (7), balance, financial, opening modules: 213 passed. Overview budget 47 holds.
- Not verifiable: golden snapshot `/tmp/golden_baseline_locked.json` is not on disk (`find /` finds nothing). SHA-256 `a6d58a75b515afdc` cannot be re-checked. Release gate remains open.
- Corrections to `opening-balance-lineage.md` section 8:
  - The overview summary API does NOT expose the gated opening. `license_overview_summary.py` returns `total_cif` (credit), `debit`, `allotment` and `balance` (the financial balance). The gated opening only appears in the snapshot's internal `opening_balance` and in `financial_opening_cif` on the financial ledger summary.
- Label audit (no displayed-figure defect found):
  - `FinancialSummarySection.tsx:16` and `CustomsLedgerTable.tsx:319` show "Original Licence CIF" from `opening_balance`. Both ledger summaries set it to `LicenseDetailsModel.opening_balance`, the export credit. The label matches the figure.
  - The two ledgers agree on closing balances (222-licence check in section 10).
- Naming risk: `balance_snapshot` `opening_balance` / `remaining_tradable_licence` (gated) and `LicenseDetailsModel.opening_balance` (credit) share a name with different meanings. Rename candidate; no behaviour change.
- Not done in this cycle: independent specialist reviews, browser verification, Excel and PDF reconciliation, RODTEP and incentive types, new reconciliation fixtures, query attribution. These need the business decision below first.
- Blocker (business decision): should any screen display the gated financial opening as "Opening CIF"? Current screens show the export credit under "Original Licence CIF". Recommended: keep the current labels, rename the internal gated field, and do not add a new displayed figure.
- Verdict: NOT COMPLETE.
- Exact next action: owner decides the display question. Then rename the gated field, add the fixtures in the lineage doc section 10, and run the golden snapshot check once it is restored.

### 11.1 Decision recorded

- Owner decision: keep current labels. "Original Licence CIF" stays the export credit (`LicenseDetailsModel.opening_balance`). The gated figure is not displayed as Opening CIF. No displayed value changes.
- Remaining work for the verdict to move: rename the gated `balance_snapshot` `opening_balance` / `remaining_tradable_licence` (naming only), add the reconciliation fixtures, run Excel and PDF reconciliation, check RODTEP, restore or re-verify the golden snapshot, and run independent reviews and browser checks.
- Verdict: NOT COMPLETE.
