# SAT Phase 3 — Financial integrity audit (sat-fin)

Date 2026-11-20 · branch `feature/v5` (HEAD `ec3604cb` + 178 uncommitted paths owned by other sessions) ·
local DB `lmanagement@localhost`, **read-only** (SELECT only; all app calls inside `atomic()` + `set_rollback(True)`) ·
test DB `test_lmanagement_sat_fin`. Audit only — nothing was fixed. Evidence lives in `/tmp/sat/fin/`.

## 1. Methodology

1. **Independent side** (`/tmp/sat/fin/recompute.py`): raw SQL on source tables only, with no import of
   `balance_calculator`, `balance_snapshot` or the ledger services. It computes, per licence:
   - original CIF = Σ export `cif_fc`;
   - BOE debit, split into visible and hidden (hidden = `invoice_no='OTH'` and the latest HIDE/RESTORE `ReconciliationLog` is HIDE);
   - BOE contribution, net of `InvoiceBOEAllocation` and legacy `trade.boes` representation;
   - outstanding allotment, per allotment item `cif − min(cif, BOEAllotmentAllocation)`, with an M2M-linked allotment = 0;
   - SALE, PURCHASE and COMMISSION trade CIF;
   - the opening-balance gate (hidden > 0 → original − hidden − purchase; any purchase → 0; otherwise original);
   - the financial, customs and visible-only balances.

   Per import item it computes:
   - debited qty/CIF (visible);
   - outstanding AT qty/CIF;
   - direct-sale qty;
   - available qty, signed and floored.
2. **App side**:
   - every `LicenseBalanceCalculator` bulk method and every single-licence method for ALL 2,185 licences;
   - `LicenseDetailsModel.get_balance_cif`;
   - `ItemBalanceCalculator` item maps for all 26,818 items;
   - the licence **list API**, run through the real `LicenseDetailsViewSet` with `is_expired=all&is_null=all` (2,185 rows);
   - the **detail API** for 166 licences: all 11 hidden-BOE licences, all 36 over-utilised licences, and 120 random ones (seed 20261120).
   (`/tmp/sat/fin/api_check.py`)
3. Re-run of `audit_cross_surface_reconciliation`, diffed against the prior report.
4. Targeted SQL probes for duplicates, transfers, multi-licence records, cancellations and ARO (`q1`–`q6` `.py/.out/.json`).
5. Pinned financial tests, plus 13 throwaway characterisation tests (`/tmp/sat/fin/test_sat_fin_char.py`, not in the repo).

Tolerances: CIF 0.01, qty 0.001. Decimal throughout.

## 2. Row counts (start = end; `/tmp/sat/fin/rowcounts_start.txt`, `rowcounts_end.txt`, identical except the timestamp)

| Table | Rows | Table | Rows |
|---|---|---|---|
| license_licensedetailsmodel | 2,185 | allotment_allotmentmodel | 6,526 (AT 6,494 · AR 32) |
| license_licenseexportitemmodel | 2,178 (7 licences have none) | allotment_allotmentitems | 11,610 (all status CREATED) |
| license_licenseimportitemsmodel | 26,818 | bill_of_entry_billofentrymodel_allotment (M2M) | 6,427 |
| bill_of_entry_billofentrymodel | 14,425 (24 without rows; 1,220 `OTH`) | reconciliation_reconciliationlog | 75 (61 HIDE, 11 RESTORE) |
| bill_of_entry_rowdetails | 168,629 (D 22,075 · C 146,554 item-opening rows, BOE NULL, not in CIF) | license_licensetransfermodel | 2,336 |
| **trade_licensetrade / tradeline / trade_boes** | **0 / 0 / 0** | **reconciliation_invoiceboeallocation / boeallotmentallocation** | **0 / 0** |

Missing tables: `license_importitemmappingapproval(+version)`. Migration 0067 is not applied (known; not a CIF table).

Totals (independent):
- Original CIF 2,393,537,328.28.
- Visible BOE 1,733,748,635.75.
- Hidden BOE 4,412,937.86 (11 licences).
- Outstanding allotment 31,592,776.75 (AT 13,658,504.39 · AR 17,934,272.36 on 154 licences).
- Billed 0.
- Financial available Σ 623,782,977.92.
- 36 licences over-utilised, Σ −7,054,283.95.

Visible + hidden = Σ all DEBIT rows (1,738,161,573.61), so no row is lost or double-assigned across licences.

## 3. Results — app engine vs independent recomputation

`/tmp/sat/fin/recompute.json`, log `recompute.log` exit 0:

- **0 discrepancies** on 2,185 licences × 9 bulk metrics + 9 single metrics + `get_balance_cif`.
- **0 discrepancies** on 26,818 items × 6 metrics.

The 11 rule-level "differences" are the hidden-BOE licences, where the literal canonical rule (our BOEs only)
≠ the financial engine. This is the known, approved opening-balance rule (RC2/RC8).

`/tmp/sat/fin/api_check.json`, exit 0:
- List API: 2,185 rows, 0 differences on `balance_cif`, `get_balance_cif` and `is_over_utilised`.
- Detail API: 166 rows, 0 differences on the same fields.
- **4** differences in `operational_reconciliation.actual_balance_cif` → D02.

Cross-surface re-run (`/tmp/sat/fin/recon.json`, `recon.log` exit 0): **2,182 licences / 26,818 items / 14,314 cells /
4,831 discrepancies on 2,071 licences. This is identical to the prior report**, by cause:

| Cause | Count |
|---|---|
| RC4 | 3,055 |
| RC3 | 973 |
| RC11 | 632 |
| RC12 | 80 |
| RC7 | 69 |
| RC8 | 11 |
| RC2 | 11 |

## 4. Test-ID table

Pinned tests: `/tmp/sat/fin/pytest_pinned.log` — 19 files (balance_calculator, balance_ledger_views, balance_excel_export,
balance_cif_single_source, m2m_full_consumption, negative_balance, financial_balance_memo, license_list_balance_consistency,
ledger_reconciliation_smoking_gun, ledger_summary_reconciliation, stored_available_quantity_hidden, cross_surface_reconciliation,
license_overview_summary_view, license_balance_validator, boe_invoice_no_hidden_state, boe_balance_refresh_triggers,
reconciliation allocation_service + boe_link_reconciler, allotment allocate_items_cif_validation). Result: **278 passed, exit 0**.

Characterisation tests: `/tmp/sat/fin/pytest_char.log` — **13 passed, exit 0**. They pin current behaviour, not approval.

| ID | Area | Status | Evidence |
|---|---|---|---|
| SAT-FIN-001 | Original CIF entitlement | PASS | recompute.json (credit 0 diffs ×2 engines). 7 licences have no export items (data) |
| SAT-FIN-002 | BOE CIF debit | PASS | recompute (boe_raw/hidden/debit 0 diffs); pinned tests |
| SAT-FIN-003 | Allotment reservations | PASS-EXC | engine = independent (0 diffs). Exceptions: D02 (is_boe without M2M), D04 (rowless BOE link), D05 (cross-licence link), D08 (status ignored) |
| SAT-FIN-004 | Invoice CIF | BLOCKED (data) → PASS on test DB | trade tables are empty locally. Pinned tests + char `test_invoice_and_boe_linked_counted_once`, `test_commission_*` (D06) |
| SAT-FIN-005 | Billed without BOE | BLOCKED (data) → PASS on test DB | same; known deferred double count when SALE and BOE are not linked (`test_debit_double_counts_when_boe_not_linked_to_matching_trade`) |
| SAT-FIN-006 | Available CIF | PASS | 2,185/2,185 engine = independent = list API; 166/166 detail API |
| SAT-FIN-007 | Quantity entitlement | PASS-EXC | item qty = source; RC12 (80 licences) and units (RC/N4) carried |
| SAT-FIN-008 | Quantity consumption | FAIL | **D01**: ARO qty never deducted (157 items, 40,992,712.93 kg); RC3/RC13 carried |
| SAT-FIN-009 | Product/HSN mapping effect | PASS-EXC | licence-level engine reads no mapping (code: `balance_calculator.py`); pivot = licence (RC9 = 0 in re-run); D1–D4 / RC4a carried |
| SAT-FIN-010 | Debit attribution to items | PASS-EXC | Σ item visible debit = licence (0 diffs). RC4a carried; D09 shared-ceiling item cap |
| SAT-FIN-011 | Licence transfer / opening balance | PASS-EXC | 11 hidden-BOE licences: financial = customs = original − hidden − visible − allot (independent = engine). The hidden flag is manual only (D-Q3). RC2/RC8 carried |
| SAT-FIN-012 | Multi-licence allocation | PASS-EXC | 3,244 BOEs and 1,838 allotments span licences. Per-row attribution is exact (no loss or duplication). D05: 207 M2M items whose BOE debits another licence |
| SAT-FIN-013 | Reversal / cancellation | PASS-EXC | delete is a hard CASCADE (char test); hidden/restore honoured (10 restored BOEs stay visible). D07 disputed rows counted; D08 RELEASED status never written and not honoured |
| SAT-FIN-014 | Duplicate debit prevention | FAIL | 0 duplicate (BOE, item, type) rows (unique_together). **D03**: BOE 8391561 stored twice → 14,835.86 counted twice; D02 allotment + BOE on the same goods. D04, D07 related |
| SAT-FIN-015 | Over-utilisation | PASS-EXC | signed values kept, `is_over_utilised` correct on 2,185 list + 166 detail rows; 36 licences −7,054,283.95. Exception: 4 flags are caused by D02 |

## 5. Discrepancy / defect register

| ID | Class | Sev | Module / code | Expected vs actual | Scope | Impact | Evidence |
|---|---|---|---|---|---|---|---|
| **D01** | Confirmed defect | High | `core/scripts/calculate_balance.py:79-81` filters `allotment__type='ARO'`, but the stored codes are `AR`/`AT` (`max_length=2`), so `aro_qty`/`aro_value` are always 0. The live `ItemBalanceCalculator.calculate_*available_quantity*` deducts AT only (`balance_calculator.py:957,919`) | ARO qty is supposed to be "folded into debited" (stated in the code docstrings). Actually it is deducted nowhere at item level. The licence CIF *does* include the AR CIF | 179 AR items · 157 items / 156 licences overstated | 40,992,712.93 kg available qty overstated. Item-level CIF omits 17,934,272.36 vs licence. Top: 0310825235 item 2393 (3,838,597 kg), 0310705160 item 2362 (3,151,848), 0310831630 item 4281 (2,513,171). **Prior RC3 top-3 "stale stored allotted qty" are actually this** | q6_aro_qty.json; char `test_aro_*`, `test_stored_writer_aro_*` |
| **D02** | Confirmed defect (two definitions) + data quality | High | Engine `_annotate_allotment_contribution` uses M2M only. `planning_usage_reconciliation.aggregate_license_usage:119-125` also excludes `allotment.is_boe`/`item.is_boe` | 12 allotments (15 items) have `is_boe=True` but no M2M link. The engine counts them as outstanding; planning `operational_reconciliation` does not. Several have a BOE on the same item, company and qty (8357 ↔ BOE 25789 270,300; 8795 ↔ 26394 38,000; 8985 ↔ 26598) → probable allotment + BOE double count | 15 items / 13 licences | 1,160,224.05 CIF. Over-utilised flag on 4 licences depends on it: 5211016746 (−75,036.77 vs +963.23), 5211016747 (−310.51 vs +188,589.49), 3411007496 (−10,667.36 vs +266,772.64), 3411007247 (−18,401.98 vs +15,936.97) | q5_isboe_no_m2m.json, api_check.json; char `test_is_boe_true_without_m2m_*` |
| **D03** | Suspected defect / data quality | Medium | `BillOfEntryModel.unique_together=(number,date)` | BOE 8391561 exists twice: ids 28686 (2026-03-30) and 27109 (2026-04-30). Same port 710, company 637, invoice "GE 41", item 33479, cif 14,835.86, qty 5,800, cif_inr 1,398,280. Row 454900 on 27109 is `is_dispute` (missing from the latest ledger). Both are debited | 1 licence 5211018767 | 14,835.86 over-debited if it is a duplicate. Other same-number + port + company pairs: 3044428 (17845/17847, different CIF), 6895442 (26404 rowless / 26286) | q2.out, q3.out; char `test_same_boe_number_*` |
| **D04** | Data quality (rule gap) | Medium | M2M full-consumption rule | Allotments linked only to BOEs with no DEBIT rows contribute 0, and nothing is debited anywhere. This includes placeholder BOE `1234567` (allotment 3743, 8 licences) | 10 allotments / 16 items | 665,624.43 CIF released. 188,100 of it (6895442) has a real twin BOE 26286 on the same licence → net 477,524.43 unaccounted | q4.json `allot_linked_to_rowless_boe`; char `test_m2m_allotment_linked_to_rowless_boe_vanishes` |
| **D05** | Business-rule ambiguity | Medium | same | The allotment is on licence A; the linked BOE debits only licence B. The allotment contributes 0 on A by the approved rule. Correct if the BOE was filed on a different licence; under-count if not | 207 items / 172 licences (301 items / 230 licences at item level) | 8,133,632.89 CIF on A not utilised. Top: 5211006440 allotment 3495 268,800 → BOE 8814027 on 5211006446 | q3.json, q4.json; char `test_m2m_allotment_zero_on_own_licence_*` |
| **D06** | Business-rule ambiguity (latent) | Low | `get_purchase_trade_rows`, `has_purchase_for_licenses`, `calculate_trade` | COMMISSION_PURCHASE is counted as purchase credit (and zeroes the opening balance). COMMISSION_SALE is ignored. LEDGER_APPROVED_SEMANTICS says COMMISSION is excluded from the running balance | 0 locally (trade tables empty) | latent | char `test_commission_*` |
| **D07** | Business-rule ambiguity | Low | engine ignores `RowDetails.is_dispute` | Disputed rows (missing from the latest DGFT ledger) are still debited | 7 rows / 7 licences | 131,125.49 CIF | q3.json `disputed_rows_detail` |
| **D08** | Suspected defect (latent) | Low | `AllotmentItems.status` RELEASED/COMPLETED is never written by any code and never read by the engine | A RELEASED item would still reserve CIF | 0 locally (all CREATED) | latent | char `test_released_status_still_counted` |
| **D09** | Confirmed (extends D-B) | Medium | `ItemBalanceCalculator.calculate_item_credit_debit` for `cif_fc=0` (shared-ceiling) items | credit = licence CIF, debit = licence visible BOE + *this item's* AT outstanding only. Sibling allotments, AR and hidden BOEs are ignored, so the item cap can exceed the licence balance (char: 1,000 vs licence 600). Used in INDIVIDUAL mode (`effective_cif_mode.py:75`), the legacy `allotment/services/allocation_service.py:73` and `sion_planning_execution.py:1585` | not measured on the DB | cap overstatement | char `test_item_balance_shared_ceiling_*` |
| DQ | Data quality (no defect) | — | — | 4,809 allotments are M2M-linked with `is_boe=False` (stale cache; the engine is safe) · 17 reused BOE numbers (14 are different port/company/year) · 24 BOEs without rows · 7 licences without export items · identical-row screens (same item, CIF, qty, date, port, different BOE number: 2,136 pairs, 250,362,685.18) are consecutive container BOEs, **not** treated as duplicates (reconciled by id) | — | — | q2–q4 |

Aggregate by root cause (CIF):

| Root cause | Amount |
|---|---|
| D05 cross-licence M2M | 8,133,632.89 |
| D01 ARO item gap | 17,934,272.36 item-level CIF + 40,992,712.93 kg |
| D02 is_boe without M2M | 1,160,224.05 |
| D04 rowless BOE link | 665,624.43 |
| D07 disputed rows | 131,125.49 |
| D03 duplicate BOE | 14,835.86 |
| D06 / D08 | 0 (latent) |

**Top 20 by absolute FC impact** (record ids):

| # | Licence | Record | Amount | Source |
|---|---|---|---|---|
| 1 | 0811013826 | — | 77,746,799.19 | RC12 (carried) |
| 2 | 0811013826 | item 28563 | 76,838,632.07 | RC4a (carried) |
| 3 | 0310636996 | — | 21,251,787.50 | RC11 (carried) |
| 4 | 0310705160 | — | 19,563,358.47 | RC11 (carried) |
| 5 | 0310653755 | item 32156 | 16,421,642.82 | RC4a (carried) |
| 6 | 0310653755 | — | 16,223,222.82 | RC12 (carried) |
| 7–8 | 0310664188 | items 32041 / 32042 | 15,129,911.93 each | RC4a (carried) |
| 9 | 0310835522 | item 7214 | 14,339,508.30 | RC4a (carried) |
| 10 | 5211016560 | allotment 8357 ↔ BOE 25789 | 270,300.00 | D02 |
| 11 | 5211006440 | allotment 3495 | 268,800.00 | D05 |
| 12 | 3411008583 | allotment 10317 | 256,240.00 | D05 |
| 13 | 5211006539 | allotment 3526 | 232,100.00 | D05 |
| 14 | 3011006726 | allotment 7479 | 230,000.00 | D05 |
| 15 | 0310827509 | allotment 183 | 221,122.00 | D05 |
| 16 | 3411007703 | allotment 9551 | 221,086.62 | D05 |
| 17 | 5211009162 | allotment 4839 | 217,743.54 | D05 |
| 18 | 5211016562 | allotment 8640 | 217,042.92 | D05 |
| 19 | 5211014543 | allotment 7792 | 216,240.00 | D05 |
| 20 | 5211016747 | allotment 8605 | 188,900.00 | D02 |

## 6. Known items carried over (verified on the current tree)

**Unchanged; still present.** Re-run counts are identical. Code checks:

| Item | Status |
|---|---|
| RC4a | `condition_pool` still has no override check |
| RC14 | `custom_ledger_pdf.py:93-99` still computes `total − (total − balance) − balance` |
| N2 | PDF Total CIF = `opening_balance` (`:93`) |
| RC15 | floats remain at `item_report.py:71-73,144,378` |
| RC3, RC4b, RC7, RC11, RC12, RC13, RC16, N1, N3, N4 | still present |

All of these are decided (D-A…D-F) but not implemented. Correction: of RC3's largest quantity cases, 0310825235, 0310705160 and 0310831630
are D01 (ARO not deducted live), not stale stored columns.

## 7. Open questions for the owner

1. D02 — Should `is_boe=True` without an M2M link count as consumed (the planning view's rule) or as outstanding (the engine's rule)? Should the 12 allotments be linked through the UI?
2. D05 — An M2M-linked allotment whose BOE debits a different licence: is 0 on the allotted licence correct?
3. D04 / D03 / D07 — Should a placeholder or rowless BOE link release an allotment? Should disputed or duplicate BOE rows still be debited?
4. D01 — Confirm that ARO (`AR`) qty is consumption at item level (the docstring says so; the code does not).
5. D06 — Is COMMISSION_PURCHASE meant to count as purchase credit in the financial engine?
6. Transfer — Hidden BOEs rely on manual hides only: 11 licences, and no approved `LicenseTransferModel` row on any of them. Is any automatic transfer-date rule wanted?

## 8. Blocked / environment limitations

- Trades, InvoiceBOEAllocation and BOEAllotmentAllocation have 0 rows locally. Invoice CIF, billed-without-BOE and partial allocation
  are therefore verified only by the pinned tests and the characterisation tests on the test DB, not on real data. The independent SQL implements those terms anyway.
- The detail API was sampled on 166 of 2,185 licences (it is a heavy endpoint). The list API covered all licences.
- Quality gates (`quality-gate.sh`) were not run: this is an audit only, with no code change.
