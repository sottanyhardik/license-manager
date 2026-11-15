# OD-10 Follow-up — Financial Ledger Balance Parity Audit

**Date:** 2026-11-15 · **Branch:** `feature/version5` @ `02f15724` · **Mode:** verification-first. No commits, no DB writes, no migrations.
**Proposed patch (not applied):** `docs/erp-transformation/patches/od10-followup.patch`. `git apply --check` is clean against the current tree.

## Final verdict: **PASS WITH NOTES**

The OD-10 change itself is correct and intact:
- The ledger screen, balance Excel and balance PDF all show `calculate_financial_balance`.
- `trade_running_balance` is separate and correctly valued.

Three outstanding items stop this from being a clean PASS (§7):
1. Approved **rule 4** (preserve negatives, flag over-utilisation) is **not implemented anywhere**. All engines still floor at 0.
2. The **Item Report** "Available Balance" totals are mis-aggregated, and the Item Report and LedgerTab compute financial totals in React (rule 8).
3. Several labels are misleading.

None of these is a regression caused by OD-10.

---

## 1. Commit and working-tree verification

| Check | Result |
|---|---|
| `ea029f1d` present on branch | ✅ `git log ea029f1d^..HEAD` shows `ea029f1d`, `1df5dc9d`, `b2bbbf99`, `02f15724` |
| Later commits touching `apps/license/services`, `license-overview`, `license-balance` | ✅ none (`git log ea029f1d..HEAD -- …` is empty) |
| Builder diff vs `ea029f1d` | ✅ empty. The override removal and the additive `trade_running_balance` are intact (`license_balance_ledger_builder.py:667-678`, `:712`) |
| Working tree | Only `.DS_Store` and `.idea/*`, which predate this work. Left untouched |

## 2. Authoritative calculation (Phase 1)

`LicenseBalanceCalculator._calculate_financial_balance` (`backend/apps/license/services/balance_calculator.py:1582-1645`):

```
balance = opening + purchase_credit − sale_debit(calculate_trade) − boe_debit(calculate_debit) − allotment
```

| Approved rule | Code | Status |
|---|---|---|
| R1 `calculate_financial_balance` authoritative | `:1572-1580` (memoised) + bulk sibling `:1654-1702` (same formula) | ✅ |
| R2/R3 Utilised = BOE + outstanding allotment + billed-without-BOE, no duplicates | `calculate_debit()` is allocation-aware: a BOE row already represented by a SALE is counted once (docstring `:1609-1627`); `calculate_allotment()` `:970`; `calculate_trade()` SALE only `:1025` | ✅ formula matches. No new test of the duplicate-exclusion path was added here; the existing coverage is in `test_balance_ledger_views.py` (BoeInvoiceRepresentation / reconciliation classes) |
| **R4 preserve negatives + flag** | `:1645` and `:1701` `return balance if balance >= DEC_0 else DEC_0`; the ledger also floors at `license_balance_ledger_builder.py:665` | ❌ **not implemented** (D-1) |
| R5 trade running balance separately identifiable | `summary.trade_running_balance` (`builder:712`) | ✅ |
| R6 licence-wide running balance excludes COMMISSION | `canonical_ledger_service.py:326-345` + `domain/transaction_semantics.py:83-166` (`is_balance_affecting` False for COMMISSION*) | ✅ for the trade running balance. ⚠ The financial engine credits `COMMISSION_PURCHASE` (`balance_calculator.py:1059,1190,1307`) but never debits `COMMISSION_SALE` (`:1025,1282`), see D-5 |
| R7 no silent divergence screen/PDF/Excel | §3 | ✅ for the balance ledger; ⚠ Item Report (D-2) |
| R8 no independent React financial calcs | §4 | ❌ Item Report totals, LedgerTab (D-2, D-3) |

## 3. Parity matrix

| Surface | Financial Available CIF source | Trade Running Balance source | Correct label? | Result |
|---|---|---|---|---|
| Ledger screen (Financial Summary) `license-overview/FinancialSummarySection.tsx:21-26` | `summary.computed_balance` → builder `:664-665` (cross-checked with `engine_balance` = `calculate_financial_balance`, `:663`) | `summary.trade_running_balance` → canonical `license_running_balance` | ✅ "Current Available Balance" / "Trade Running Balance (purchases − sales)" | PASS |
| Customs ledger cards `CustomsLedgerTable.tsx:323,328` | customs summary `computed_balance` (customs engine, `builder:~968`) | — | ⚠ "Available Balance" on a **customs** figure (OD-02 open) | NOTE (D-6) |
| Overview metric grid `LicenseMetricsGrid.tsx:74` | `total_balance_cif` → `license_overview_summary.py:66,146` → `balance_snapshot` → `calculate_financial_balance` | — | ✅ "Balance CIF" | PASS |
| Licence list, expanded trade ledger `LicensesTable.tsx:592` | — | `license_running_balance` (canonical trade API) | ❌ "License Balance" | NOTE (L1, patched in proposal) |
| Licence list LedgerTab `masters/tables/LedgerTab.tsx:509-517,667` | **React**: `commonBalance ? get_balance_cif : Σ item.balance_cif_fc` (float) | — | "Balance CIF" | ❌ D-3 |
| Trade ledger page `LicenseLedgerDetail.tsx:152,382` | — | `summary.current_balance` (fallback `license_running_balance`) | ⚠ "Current Balance" on a trade figure | NOTE (D-6) |
| Item Report screen `reports/itemReport/ItemReportTable.tsx:115,244` | per row: `license_running_balance ?? available_balance`. The backend never sends `license_running_balance`, so it is **item-level** `available_value` (`item_report.py:393,431`) | — | ⚠ "Available Balance" is item-level | NOTE |
| Item Report totals `ItemReportTable.tsx:387-394`, `ItemReportTotalsBar.tsx:28-33` | **React**: Σ of the **first item's** `available_value` per licence | — | ❌ | **D-2** |
| Item Report "Balance CIF" `item_report.py:376,433`; TotalsBar `:43-49` | `calculate_financial_balance_for_licenses` ✅ (float at edge); total summed once per licence **in React** | — | ✅ | PASS / R8 note |
| Item Report Excel `item_report.py:622-624,701-711` | rows as screen; TOTAL "Available Balance" = Σ first-item `available_value` per licence | — | ❌ same as screen | **D-2** |
| Balance Excel `exporters/license_balance_excel.py:491,570` | `summary['computed_balance']` (receives canonical_data at `:1191-1215`) | not shown | ✅ / ❌ missing row | PASS, M1 open |
| Balance PDF `exporters/license_balance_pdf.py:99,219,339` | `summary['computed_balance']` (builder called **without** canonical_data) | not shown and not computable (`None`) | ✅ / ❌ missing row | PASS, M1 open |
| Ledger (trade) Excel `financial_ledger_excel_renderer.py:155,194,209` | — | `summary.current_balance` / `closing_balance_fc` | ✅ trade statement | PASS |
| Ledger (trade) PDF `financial_ledger_pdf_renderer.py:193,241,335` | — | `summary.current_balance` ("Balance ($)") | ✅ titled "FINANCIAL TRADE LEDGER" | PASS |
| API `GET licenses/{id}/balance-ledger/` | `financial_ledger.summary.computed_balance` / final row | `financial_ledger.summary.trade_running_balance` | ✅ | PASS |
| API canonical ledger `serializers/ledger.py:205,236-241` | — | `license_running_balance` + deprecated aliases `available_balance`, `db_balance` (same value) | ❌ alias names imply Available CIF | NOTE (L1). Not renamed: contract change needs approval |
| `frontend/src/utils/canonicalLedgerAdapter.js:123` | — | `available_balance: license_running_balance` | ❌ name | **dead code**: zero importers (`grep -rn canonicalLedgerAdapter frontend/src`). Already in 06 §A |

Value equivalence checked: the raw `license_running_balance` **equals** the de-duplicated `summary.current_balance`. `opening_seed` is 0 whenever a valid PURCHASE exists (`canonical_ledger_service.py:276-281`). On the dev DB, 2,185/2,185 licences are equal, but the dev DB has 0 trade lines. On a synthetic purchased-and-sold licence both are 30,000.00, pinned by `test_trade_running_balance_counts_acquisition_once`. The docstring at `canonical_ledger_service.py:713-737` ("DOUBLE-COUNTS the licence's acquisition … 141,964.38") is **stale** (D-7).

## 4. Duplicate or misleading field mappings

| ID | Mapping | Severity |
|---|---|---|
| L1-a | `LicensesTable.tsx:592` "License Balance" ← trade running balance | Low (label; value correct) |
| L1-b | API aliases `available_balance` / `db_balance` = trade figure (`serializers/ledger.py:236-241`); FE types `types/canonicalLedger.ts:291-292`, `LicensesTable.tsx:158-159` | Low. Rename/removal needs approval |
| L1-c | `canonicalLedgerAdapter.js:123` `available_balance` ← trade figure | Info (dead file) |
| L1-d | Item Report uses `license_running_balance ?? available_balance`, but the backend sends only item-level `available_balance` | Medium (D-2) |
| D-3 | LedgerTab "Balance CIF" from a React sum of item balances | Medium |
| D-6 | "Available Balance" on the customs figure; "Current Balance" on the trade-ledger page | Low |

## 5. Regression test results

Patched code was run in a throwaway worktree (since removed), using a separate test DB (`TEST_DB_NAME`).

| Run | Result |
|---|---|
| New `test_financial_ledger_parity_od10.py` (5) + existing `test_financial_ledger_current_balance.py` (2), patched | **7 passed** |
| Same new file against **current (unpatched)** code | **3 failed, 2 passed**. The 3 failures are the over-utilisation fields and the Excel/PDF Trade Running Balance row. The 2 passing tests (acquisition counted once, COMMISSION excluded) are guards on behaviour that is already correct |
| Full app-level suite (`apps/license/tests apps/core/tests`), patched | **2,712 passed, 2 failed**. The 2 are the known OD-21 item-pivot tests; the baseline was 2,707/2, so +5 new |
| `backend/tests/`, patched worktree | 236 passed, 1 failed: `test_spa_catchall_resolves_react_entry_template`. Environmental (worktree has no built `frontend/dist/index.html`); passes in the main tree (237/237 earlier today) |
| `makemigrations --check` | No changes |
| Frontend vitest (patched worktree) | **546 passed** (79 files). `tsc --noEmit` and eslint on `LicensesTable.tsx` clean |

Coverage against the brief:

| Behaviour | Test |
|---|---|
| BOE utilisation | `test_financial_ledger_current_balance.py::test_current_balance_is_engine_value_when_boe_utilised` |
| Outstanding allotment | existing `test_balance_calculator.py` / `test_balance_ledger_views.py` (mock- and ledger-level) |
| Billed without BOE + duplicate exclusion | existing reconciliation and representation classes in `test_balance_ledger_views.py`, `test_boe_invoice_representation.py` |
| Negative Available CIF / over-utilisation flag | **new** `test_over_utilisation_is_flagged_with_signed_balance`, `test_not_over_utilised_when_balance_positive` |
| Trade running balance separate | `test_trade_running_balance_is_exposed_separately_and_unchanged` + **new** `test_trade_running_balance_counts_acquisition_once` |
| COMMISSION exclusion | **new** `test_trade_running_balance_excludes_commission` |
| API/React mapping + labels | `FinancialSummarySection.test.tsx` (2) |
| Excel/PDF numerical parity | **new** `test_excel_and_pdf_match_screen`: openpyxl cells and pypdf text compared with `build()` using Decimal; amounts rendered `$x,xxx.xx` |

Not covered by an automated test: the Item Report totals (D-2, needs a decision first) and the LicensesTable label (P3 is a label-only change).

## 6. M1 and L1

- **M1 (balance Excel/PDF don't show the trade figure):** confirmed. The Excel has the value but no row. The PDF builds the ledger without canonical data, so the value is `None`. **Patch P2** adds one summary row, "Trade Running Balance (purchases − sales)", to both, for licences with trading activity only. The PDF now fetches canonical data, guarded by try/except.
  - **Export-format impact:** one extra row in the summary block of the balance Excel ("Financial Ledger" sheet) and the balance PDF, for traded licences only. Existing rows and values are unchanged.
- **L1:** confirmed, see §4.
  - **Patch P3:** relabels `LicensesTable` to "Trade Running Balance" (the number is unchanged).
  - **API aliases:** left as-is. Renaming them needs your approval.
- **L2 (Excel crashes if the canonical service fails):** confirmed (`license_balance_excel.py:1191`, no guard). **Patch P2** adds the same guarded fallback `build()` uses.

## 7. Remaining defects (ranked)

| ID | Sev | Defect | Evidence | Fix |
|---|---|---|---|---|
| **D-1** | **High** | Approved rule 4 not implemented: every engine and the ledger floor Available CIF at 0, and no over-utilisation flag exists | `balance_calculator.py:1645,1701` (+11 other floors, doc 05 DUP-03); `builder:665`; pinned by `test_balance_calculator.py::test_calculate_all_components_negative_balance` | **Step A (P4, additive, no displayed number changes):** `summary.unfloored_balance` + `summary.is_over_utilised`. **Step B (needs your go-ahead):** remove the floors so the displayed Available CIF goes negative. This changes numbers on every surface; 35 dev licences, −6.96M total (doc 04) |
| **D-2** | Medium | Item Report "Available Balance" TOTAL = Σ of the first item's `available_value` per licence, which is neither the item total nor a licence balance. Same logic in screen and Excel. Computed in React (R8) | `ItemReportTable.tsx:387-394`, `ItemReportTotalsBar.tsx:28-33`, `item_report.py:701-703` | Decide the intended total: (a) Σ of all item rows (deduped by import-item id), or (b) licence-level `balance_cif`. Then compute it **once in the backend** and return it with the response. No patch yet |
| **D-3** | Medium | LedgerTab "Balance CIF" is a React float sum of item `balance_cif_fc` unless the licence is "common balance"; it can differ from `calculate_financial_balance` | `LedgerTab.tsx:509-517,667` | Serve the licence-level figure (already available as `get_balance_cif`) for the headline. If an item-sum is wanted, return it from the backend. Changes displayed numbers, so decide first |
| D-5 | Medium (ambiguity) | Financial engine credits COMMISSION_PURCHASE but ignores COMMISSION_SALE (asymmetric). R6 covers the trade running balance; it's unclear whether it also governs Available CIF | `balance_calculator.py:1059,1190,1307` vs `:1025,1282` | Owner decision (= OD-14) |
| D-6 | Low | "Available Balance" on the customs-engine figure; "Current Balance" on the trade-ledger page | `CustomsLedgerTable.tsx:323,328`; `LicenseLedgerDetail.tsx:152` | Relabel: "Customs Available Balance", "Trade Balance". Label-only |
| D-7 | Low | Stale docstring claims `license_running_balance` double-counts the acquisition; the code fixed this (`opening_seed`) | `canonical_ledger_service.py:713-737` vs `:276-281` | Correct the docstring |
| L1-b | Low | Deprecated aliases `available_balance` / `db_balance` = trade figure | `serializers/ledger.py:236-241` | Deprecation plan; removal needs approval |
| Info | — | Float at the API edge in the Item Report (`float(item.available_value)`, `float(balance_cif)`) | `item_report.py:393,433` | Serialize as 2dp Decimal strings when D-2 is fixed |

## 8. Recommended minimal patches (`patches/od10-followup.patch`, NOT applied)

| Patch | Files | Effect on outputs |
|---|---|---|
| P2 (M1 + L2) | `exporters/license_balance_excel.py`, `exporters/license_balance_pdf.py` | +1 labelled summary row in balance Excel/PDF for traded licences; no existing value changes; Excel no longer crashes if the canonical service fails |
| P3 (L1-a) | `pages/masters/tables/LicensesTable.tsx` | label "License Balance" → "Trade Running Balance"; value unchanged |
| P4 (D-1 step A) | `license_balance_ledger_builder.py` | additive API fields `financial_ledger.summary.unfloored_balance`, `is_over_utilised`; displayed balance unchanged |
| Tests | `apps/license/tests/test_financial_ledger_parity_od10.py` (new, 5 tests) | — |

Apply with `git apply docs/erp-transformation/patches/od10-followup.patch`, then run `scripts/dev/quality-gate.sh backend frontend`. A `cif-balance-auditor` review is required before committing.

Not patched (decision required): D-1 step B, D-2, D-3, D-5, L1-b. D-6 and D-7 can be done label/doc-only on request.
