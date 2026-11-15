# 04 — Business-Logic Inventory (Phase Zero discovery)

**Scope:** every money/quantity/balance calculation in `backend/` and `frontend/src`, as of branch `feature/version5` (HEAD `0c28a897`), 2026-11-15.
**Method:** I read the code at the cited lines. Numbers came from read-only probes against the LOCAL dev DB `lmanagement`: `psql` SELECTs plus a Django shell (`DB_HOST=localhost`) that only called pure calculator and ledger-builder methods. There were no writes, MV refreshes or tasks.
**Status of prior docs:** the `docs/MASTER_CALCULATION_REGISTER.md`, `docs/architecture/GATE3_DUPLICATE_CALCULATIONS.md` and `docs/modules/LEDGER_SCREEN_FINANCIAL_LOGIC_AUDIT.md` files were used only as leads. Several of their claims are contradicted by the code:
- GATE3 §P1 says "Balance ... LOW risk, all delegate to single calculator". In fact there are 4 licence-level engines, plus 3 more balance paths outside the calculator.
- The ledger audit says "Single Source of Truth: RESTORED". In fact the Financial Ledger's final balance is overwritten by a different formula (F-1 below).

No business-rule change was made. This document is descriptive only.

Abbreviations: **BC** = `backend/apps/license/services/balance_calculator.py`. **LB** = `.../license_balance_ledger_builder.py`. **CL** = `.../canonical_ledger_service.py`. **CS** = `backend/apps/core/scripts/calculate_balance.py`. **FE** = `frontend/src`.

---

## 0. Headline findings (all verified in code and, where possible, on dev data)

| # | Finding | Evidence | User-visible? |
|---|---|---|---|
| F-1 | **The Financial Ledger's "Current Available Balance" is not the Financial engine.** `build()` always passes `canonical_data`. `build_financial_ledger` then replaces its own `computed_balance` with `canonical_data['license_running_balance']`, which is `opening + Σpurchase − Σsale` and has **no BOE and no allotment term**. Every licence with BOEs or allotments is flagged `mismatched` and gets a `FINANCIAL_MISMATCH` warning. | LB:1614-1624, LB:666-672, CL:286-347. Dev DB: **2,036 of 2,185 licences** differ by more than $10. Licence L-1 shows 190,992.45 against an engine value of 3,962.32. | YES. `FE/pages/license-overview/FinancialSummarySection.tsx:21`, the red final row in `FinancialLedgerTable.tsx:129`, and the PDF/Excel exports. |
| F-2 | **Balances are floored at 0 in 13 places in BC.** This contradicts the rule "negative balances preserved and flagged". | BC:1345, 1403, 1431, 1454, 1482, 1651, 1699, 1760, 1782, 1858, 1998, 2079, 2100. Dev DB: **35 licences** would be negative, totalling −6,957,414.63; all of them display 0.00. | YES |
| F-3 | **Four licence-level "available CIF" engines coexist**, each also with a bulk sibling: `calculate_balance` (credit − visible BOE − allotment), `calculate_customs_balance` (adds hidden BOEs), `calculate_all_components` (same as `calculate_balance`) and `calculate_financial_balance` (opening + purchase − sale − netted BOE − allotment). | BC:1349, 1406, 1458, 1582 | Yes, when hidden BOEs or trades exist |
| F-4 | **ARO allotment type mismatch.** `CS` filters `allotment__type='ARO'`, but the stored code is `'AR'` (`core/constants.py:25-27`, `max_length=2`), so the ARO terms are always 0. Licence-level `calculate_allotment` has no type filter (AR included), while item-level `get_outstanding_allotment_totals` filters `'AT'`. | CS:55-56, BC:970-1006 vs BC:917. Dev DB: 179 AR items (CIF 17.93M), all currently BOE-linked, so there is no numeric gap today. | Latent |
| F-5 | **The stored item availability uses a legacy lineage that differs from the live one:** float maths, `round_down(...,0)` to whole units, no hidden-BOE exclusion on debits, and the ARO bug. The allotment **write path validates qty against this stored field.** | CS:34-44, 97-98. `allotment/views_actions.py:1341`. Dev DB: **5,996 of 26,818 items** have stored ≠ live `available_quantity`; 5,791 of these differ by less than 1 unit, which is integer truncation. | YES (allocation caps) |
| F-6 | **Commission handling differs.** The Financial engine credits `COMMISSION_PURCHASE` lines (BC:1059, 1307) but never debits `COMMISSION_SALE` (BC:1025, 1282). The canonical ledger excludes all commission directions from the balance (`license/domain/transaction_semantics.py` `COMMISSION*` → `balance_direction: NONE`). | — | Yes, for licences with commission trades |
| F-7 | **The dormant materialized views are wrong.** In the deployed definitions `utilized_cif` uses the word `'DEBIT'` (pg_matviews check), so it is 0. The views also mix INR (`rd.cif_inr`) with USD, have no hidden or allocation netting, count BOE-linked allotments, and fan out through a join. Nothing reads them (`get_license_balance` and the other readers have no non-test callers). Auto-refresh is off (`core/signals_materialized_views.py:25`). | `core/materialized_views.py:27-80, 89-150`. L-1 MV: utilised 0, allotted 187,049.32, balance 3,943.13. | No (dormant) |

---

## 1. Authoritative source data

| Concept | Table / field | Units, precision |
|---|---|---|
| Original licence CIF | `license_licenseexportitemmodel.cif_fc` | USD (FC), 2dp |
| Item credit / qty | `license_licenseimportitemsmodel.cif_fc`, `cif_inr`, `quantity`; plus CREDIT rows in `bill_of_entry_rowdetails` | USD / INR / kg (3dp) |
| BOE utilisation | `bill_of_entry_rowdetails` with `transaction_type='D'` (`cif_fc` 15,3; `cif_inr` 15,3; `qty` 15,3; `bill_of_entry_rowdetails.py` model at `bill_of_entry/models.py:388-411`) | USD, INR, kg |
| Hidden (previous-owner) BOE | `BillOfEntryModel.invoice_no == OTH_INVOICE_MARKER` **plus** an audit-trail confirmation (`bill_of_entry/models.py:58`, `annotate_and_exclude_hidden`) | — |
| Allotment | `allotment_allotmentitems.cif_fc`, `qty`; `allotment_allotmentmodel.type` (`AT`/`AR`), `required_quantity`, `unit_value_per_unit`; BOE link via the M2M `bill_of_entry_billofentrymodel_allotment` | USD |
| BOE↔allotment allocation | `reconciliation_boeallotmentallocation.allocated_cif_fc` (20,3), `allocated_qty`, `status=ACTIVE`, `is_current` | USD |
| Invoice↔BOE allocation | `reconciliation_invoiceboeallocation`, `reconciliation_externalinvoicelink` | USD/INR |
| Trades / invoices | `trade_licensetrade` (direction PURCHASE/SALE/COMMISSION_PURCHASE/COMMISSION_SALE; `subtotal_amount`, `roundoff`, `total_amount`); `trade_licensetradeline` (`qty_kg` 4dp, `rate_inr_per_kg` 3dp, `cif_fc` 2dp, `exc_rate` 4dp, `cif_inr`, `fob_inr`, `pct` 3dp, `amount_inr` 2dp); legacy M2M `trade_licensetrade_boes` | INR bill; USD licence value |
| Caches (not authoritative) | `license_licensebalance.balance_cif`; `LicenseImportItemsModel.available_quantity/available_value/debited_*/allotted_*`; the 3 MVs | — |

Local dev DB note: `trade_licensetrade`, `trade_licensetradeline` and both allocation tables are **empty**. No "hidden" BOEs pass the audit-trail test (1,222 BOEs carry `OTH` text but none is genuinely hidden). Trade and hidden-BOE behaviour therefore cannot be demonstrated with real local rows.

---

## 2. Calculation inventory

Legend for the Floor column: **0** = clamped at 0. **raw** = negative values propagate.

### 2.1 Licence-level CIF

| Calc | Implementation(s) | Formula | Rounding | Null | Floor | Duplicates / edge cases | Tests pinning it | Gaps |
|---|---|---|---|---|---|---|---|---|
| ORIGINAL CIF | `BC.calculate_credit` :92; bulk :616; `LicenseDetailsModel.opening_balance` `license/models/core.py:293`; CL:263 (quantized); MV `total_cif` | Σ export `cif_fc` | none (CL quantizes 2dp) | `Coalesce(…,0)` | n/a | The Excel "Total License CIF" is **not** this value. It is Σ visible BOE + Σ unlinked allotment gross + balance (`license_balance_excel.py:879-880`, 1460). The FE `LedgerTab.tsx:509-525` "License Value" is Σ import `cif_fc`, falling back to Σ export `cif_fc ?? fob_fc`. | `test_balance_calculator.py` (mocked) | No test that the Excel total equals credit |
| BOE CIF, raw visible | `BC.calculate_boe_debit_total` :512 via `get_debit_rows` :369 (filter `bill_of_entry__isnull=False` :431); bulk :542 (**no** isnull filter); `LicenseDetailsModel.get_total_debit` `models/core.py:305` | Σ D-row `cif_fc`, hidden excluded | none | Coalesce | n/a | Single vs bulk filters differ on null-BOE D rows (0 such rows in dev). | `test_balance_calculator.py`, `test_balance_ledger_views.py` | Null-BOE D-row parity |
| BOE CIF, hidden | `BC.calculate_hidden_boe_debit_total` :562; bulk :591 | Σ hidden D-row `cif_fc` | none | Coalesce | n/a | Included by the customs engine and ledger; excluded elsewhere | `test_boe_hide_service.py` | — |
| BOE CIF, allocation-netted (UNMATCHED BOE) | `BC.calculate_debit` :459, bulk :645; `_linked_boe_debit_exclusion_case` :294; `resolve_boes_represented_by_invoice` :210/:250 | per row `max(cif_fc − min(cif_fc, allocated + linked_excluded), 0)`. `linked_excluded` = full `cif_fc` when the BOE is "represented" (formal `InvoiceBOEAllocation` OR legacy `trade.boes` tag) and the row has no own allocation. | none | Coalesce | per-row `Greatest(…,0)` | Whole-BOE representation is a documented product decision (docstring :221-233) | `reconciliation/tests/test_allocation_service.py`, `test_boe_invoice_representation.py` | — |
| ALLOTMENT CIF (outstanding) | `BC._annotate_allotment_contribution` :711 → `get_allotment_rows` :845 → `calculate_allotment` :970. **Hand-copied** chain in `calculate_allotment_for_licenses` :1196-1262. Item-level `get_outstanding_allotment_totals` :895 / `_for_items` :928. Other definitions: `condition_pool.py:105-109, 198-200`, `item_usage.py:103, 146`, `license_overview_summary.py:101` (count only), MV | per item `0` if the allotment has **any** linked BOE (`Exists` on the M2M), else `max(cif_fc − min(cif_fc, Σ active BOEAllotmentAllocation), 0)` | none | Coalesce | per-row `Greatest` | Licence level: **all types** (AT and AR). Item level: **AT only** (:917, :956). Condition pool and item_usage use `allotment__bill_of_entry__isnull=True` with **no partial-allocation netting**. | `test_balance_calculator.py`, `allotment/tests/test_allocate_items_cif_validation.py` | AR-type at licence vs item level is untested |
| BILLED CIF WITHOUT BOE | Not computed as a term. It is implicit in the financial engine pair `calculate_trade` (:1063, SALE lines in full) + `calculate_debit` exclusions. Displayed separately as `billed_no_boe` in `serializers/license.py:350-385` and `item_usage.billed_no_boe_bulk_map` :157-195. | Engine: SALE `cif_fc` − nothing; the BOE side is netted. Display: Σ SALE `cif_fc` where `trade.boes` is empty. | none | Coalesce / `float(…or 0)` | n/a | The display ignores formal `InvoiceBOEAllocation` and counterpart/linked pairs, so it can show billed-no-BOE for an invoice that the engine treats as represented. | `test_sale_trade_quantity_consumption.py` (qty) | No test of the CIF display vs engine |
| UTILISED CIF | Nowhere as a single number. Customs: `boe_debit (+hidden) + allotment`. Financial: `opening − balance` implicitly. MV `utilized_cif` = Σ `cif_inr` (wrong currency). | — | — | — | — | The 5-line rule's UTILISED term has no owner | — | Needs a definition |
| AVAILABLE CIF, customs (visible) | `BC.calculate_balance` :1349; bulk :1315; `calculate_all_components` :1458 | `credit − (visible BOE + allotment)` | `quantize_2dp` HALF_UP at the end | — | **0** | Used by `license_balance_ledger_builder.py:244, 258`, the bulk Excel (`license_balance_excel.py:1604`) and `balance_snapshot.py:153` (`customs_balance` alias) | `test_balance_calculator.py:229-291` **pins the floor** (`test_calculate_all_components_negative_balance`) | Floor test pins the contested behaviour |
| AVAILABLE CIF, customs (all) | `BC.calculate_customs_balance` :1406; bulk :1434; LB customs ledger :726-990 (running) | `credit − (visible + hidden BOE + allotment)` | 2dp at the end | — | **0** final. Per-row running is raw. | The customs ledger's final row shows the engine value as its anchor (LB:966) | `test_balance_ledger_views.py:584` | — |
| AVAILABLE CIF, financial ("Balance CIF") | `BC._calculate_financial_balance` :1582 (memoised :1572); bulk :1654; `LicenseDetailsModel.get_balance_cif` `models/core.py:330-349` | `opening + purchase − sale − netted BOE − allotment`. `opening` (:1486) = `credit − hidden − purchase` if hidden > 0; else `0` if any purchase exists; else `credit`. | 2dp at the end | — | **0** | Purchase includes COMMISSION_PURCHASE (:1059); sale excludes COMMISSION_SALE (:1025) | `test_balance_cif_single_source.py`, `test_balance_ledger_views.py:194` | No floor/negative test; no commission test |
| Running ledger, financial | LB `build_financial_ledger` :194-720 (`running += credit − debit` :647) | row-by-row | final 2dp :664 | — | **0** final; rows raw | **Final value replaced by the canonical running total (F-1)** LB:666-672 | Tests call the builder **without** `canonical_data` (`test_balance_ledger_views.py:534`) or trade-only through the view (:194), so F-1 is not covered | Critical gap |
| Running ledger, canonical ("License Ledger" screen) | `CL.build_canonical_ledger_dataset` :84-470; `_build_summary` :686-830 | seed = `opening` unless a valid PURCHASE exists; ± PURCHASE/SALE; commission excluded | **quantize per transaction and per step** (:323, :347). This is mid-calculation rounding and violates the "quantize at the edge" invariant. | to_decimal | raw (signed) | `current_balance = Σpurchase − Σsale` over display rows (:799) ≠ `license_running_balance` when an opening and a purchase coexist (docstring :714-723) | `test_cross_output_parity_option_c.py`, `test_license_ledger_export_parity.py` | — |
| Overview cards | `license_overview_summary.py:54-66` via `balance_snapshot.get_snapshot` | credit / visible BOE / allotment (customs components) **+ financial balance** | 2dp per card | — | balance 0 | The cards no longer add up (`credit − debit − allotment ≠ balance`) for traded or hidden licences. The module docstring (:9-13) still claims identical figures to `calculate_all_components`. | `test_license_overview_summary_view.py` | — |
| Licence list "Balance CIF" | `serializers/license.py:826-848`, map from `views/license.py:315` (financial bulk); falls back to the stored `balance_cif` | financial | — | `None` passthrough | `bal if bal > 0 else 0` | The docstring names `calculate_balance_for_licenses`, but the code uses financial | `test_license_list_balance_consistency.py` | — |
| Null-DFIA flag | `license/signals.py:316` (`< 500`), `CS:210` (`< 100`), `sync_licenses.py:37` (`500`); dashboard expiring filter `views/dashboard.py:142, 262` (`>= 100`) | threshold on the financial balance | — | — | — | Last writer wins (see DUP-12) | `test_signals.py` | No threshold consistency test |

### 2.2 Item-level

| Calc | Implementation(s) | Formula | Rounding | Floor | Notes / divergence | Tests |
|---|---|---|---|---|---|---|
| Item CIF balance | `ItemBalanceCalculator.calculate_item_balance` BC:1846 ← `calculate_item_credit_debit` :1786 | if item `cif_fc` is 0: **licence** credit − **licence** visible BOE − **item** outstanding AT; else item `cif_fc` − item visible BOE − item outstanding AT | **none** (no quantize) | 0 | The zero-CIF branch mixes licence-scope debit with item-scope allotment. Used by allocation (`allocation_service.py:73`), `effective_cif_mode.py:75` and `sion_planning_execution.py:1587`. | `test_balance_calculator.py:338-430` |
| Item attributed balance | BC:1743 / bulk :1763 | item `cif_fc` − item visible BOE − item outstanding AT | none | 0 | Same as above for positive-CIF items | `test_bl_ledger_03_cif_attribution.py` |
| `available_value_calculated` (live) | `license/models/core.py:1034-1093`; bulk mirror `condition_pool._resolve_available_value` :250-290 / `available_value_bulk_map` :292 | 0.01 marker → 0.01. `%` condition → `min(pool_remaining, financial_balance)`. Positive item CIF → attributed balance. Otherwise financial balance. | none | via components | Pool (`condition_pool.py:46-128`): `credit × pct − (visible BOE + allotment[isnull, no netting, AR incl.] + ALL SALE cif_fc)`. **SALE is counted even when the BOE that represents it is also counted**, so represented BOEs are double-subtracted. | `test_balance_cif_single_source.py`, `test_signals.py` |
| Stored `available_value` | `CS.calculate_available_value` :125-160, capped at `balance_cif_fc` :193-198 | the property above, or serial-1 full-balance carve-out | `round(float, 2)` | — | Dev: **3,032 items** stored ≠ live (stale cache) | `test_balance_cif_single_source.py` |
| Available qty (live) | BC `calculate_available_quantity` :1958 / `_for_items` :2030 | `quantity − visible BOE qty − outstanding AT qty − direct-sale qty` (`_direct_sale_quantity_rows` :1861: SALE lines without a linked BOE on the same item and without counterpart/linked trade, net of `InvoiceBOEAllocation.allocated_qty`) | none | 0 | — | `test_sale_trade_quantity_consumption.py`, `test_balance_calculator.py:483` |
| Available qty (snapshot) | `balance_snapshot.py:197-205` | `quantity − debited − outstanding` | none | 0 | **Omits the direct-sale term.** The comment claims lock-step with BC:2030. | `test_license_overview_summary_view.py` (licence-level only) |
| Available qty (stored) | `CS.calculate_available_quantity` :72-98 via `update_balance_values` :164 | `quantity − (all D qty incl. hidden + ARO['ARO'→0]) − outstanding AT − direct-sale` | float; `round_down(x, 0)` → **whole units**; `max(round(v,2),0)` | 0 | Read by the allocation write cap (`views_actions.py:1341`), the Excel "Balance Quantity" (`license_balance_excel.py:270`) and the serializer `get_available_quantity` (`serializers/license.py:275-278`) | `test_balance_cif_single_source.py` |
| Debited / allotted value (stored) | CS:113-123 | Σ D `cif_fc` (hidden incl.) + ARO; AT outstanding | `round(float,2)` | — | Hidden included, unlike every live calc | — |

### 2.3 Allotment, BOE, reconciliation, trade

| Calc | Implementation(s) | Formula / rule | Rounding | Notes |
|---|---|---|---|---|
| Allotment `cif_fc` | `allotment/models/core.py:135-160` (save); FE `useMasterFormCalculations.ts:139-193` | Priority 1: `unit_value × required_qty`. Priority 2: `unit_value = cif_fc / qty`. Then `cif_inr = cif_fc × exchange_rate`. | BE: 2dp HALF_UP; unit_value 3dp **ROUND_UP**. FE: `toFixed(2)`; `Math.ceil(x*1000)/1000`. | FE also offers `cif_fc = cif_inr / rate` (:160-175). BE save overwrites it via Priority 1 whenever a unit value is set. |
| Required value / balance qty | `allotment/models/core.py:163-188, 201-210` | `required_qty × unit_value` (2dp HALF_UP); `required − Σ allotted qty`, floored at 0 | — | — |
| Allocation Max (canonical) | `allotment/services/paired_allocation_max.py:23-73`; `allocation_availability.py:27-60`; payload `views_actions.py:64-130` | qty stepped DOWN to `quantity_step`; `cif = qty × unit_price` **ROUND_UP** to the cent, stepping down while above the ceiling. Final-settlement exceptions: ±0.01, or `+$20` buffer (`FINAL_SETTLEMENT_BUFFER` :8). | ROUND_DOWN qty / ROUND_UP cif | — |
| Allocation Max (legacy, duplicate) | `allotment/services/allocation_service.py:30-91` (step 0.001, `required + $20` default :65); `BC.calculate_available_value_for_allocation` :2105 (**no callers**) | — | — | BC:2105 does no stepping and no rounding |
| Allocation write validation | `views_actions.py:1072-1400` | `cif == round_up(qty × price)` ± 0.01 (:1187, :1321) or settlement. qty ≤ **stored** `available_quantity` (:1341). cif ≤ `effective_source_row_cif_available` (:1374 → `effective_cif_mode.py:114`). qty ≤ `required − alloted`. | — | FE pre-computes `Math.round(qty*price*100)/100` (HALF_UP, `AllotmentAction.tsx:736`). This is accepted only because of the ±0.01 tolerance. |
| BOE totals / rate | `bill_of_entry/models.py:285-333`; `_recalculate_boe_exchange_rate` :501-527 (signal on RowDetails save/delete) | `total_fc`, `total_inr` = Σ rows, quantized to 2dp (context rounding = HALF_EVEN). Stored `exchange_rate = total_inr / total_fc` (4dp), updated only if \|Δ\| > 1. `get_exchange_rate` returns 3dp HALF_UP. `unit_price` = `total_fc / qty` (3dp). | mixed | Totals include **all** transaction types and hidden rows. The rate is derived from already-rounded totals. |
| Reconciliation remaining | `reconciliation/services/allocation_service.py:68-198` | `own − Σ active current allocations` per side; invoice side also subtracts `ExternalInvoiceLink` | none | each `_floor0` (:50). Over-allocation is blocked by `_validate_fits` :209. |
| Auto BOE↔invoice match | `boe_link_reconciler.py:47-140` | candidate = same `sr_number` D-row on a `trade.boes` BOE with remaining capacity; exactly 1 candidate and \|ΔCIF\| ≤ `RECONCILIATION_CIF_TOLERANCE` (1.00) and \|Δqty\| ≤ 1.000 (`settings.py:581-582`) | — | Run only by management commands and dry-run inside LB:531 |
| Ledger self-check tolerance | LB:28 `TOLERANCE = 10.00` | \|computed − engine\| > 10 ⇒ mismatched | — | Different tolerance from reconciliation (1.00) and FE `ALLOCATION_EPS = 0.005` (`allocationMath.ts:16`) |
| Trade line amount | `trade/models.py:558-565` (`compute_amount`, used only if `amount_inr` is 0, :567-572); FE `TradeForm.tsx:450-510`; FE `NestedFieldArray.tsx:139-155` | QTY: `q4(qty) × q2(rate)`. CIF_INR: `q2(cif_inr) × pct/100`. FOB_INR likewise. | BE 2dp HALF_UP; **TradeForm whole rupee `Math.round`**; NestedFieldArray `toFixed(2)` | The client value is persisted as-is (BE only fills zeros) |
| Exchange rate / `cif_inr` on trade lines | FE `TradeForm.tsx:456` `cif_inr = (cif_fc × exc_rate).toFixed(2)`; `:464` `exc_rate = round(cif_inr / cif_fc, 2dp)` | — | rate 2dp in FE vs `exc_rate` 4dp column (`trade/models.py:543`) | No backend recomputation |
| Trade totals | `LicenseTrade.recompute_totals` `trade/models.py:365-391` | `subtotal = q2(Σ amount_inr)`; `roundoff = round_half_up(subtotal, ₹1) − subtotal`; `total = subtotal + roundoff` | HALF_UP | FE `calculateTotal` :517-521 is an unrounded float sum |
| Invoice PDF totals | `purchase_invoice_pdf.py:318-449`; `bill_of_supply_pdf.py:329-469` | re-sums `amount_inr`; `rounded_total = round(subtotal)` | **Python `round(Decimal)` = HALF_EVEN** (₹1,234.50 → 1,234; the model gives 1,235) | The bill of supply uses `canonical_total_inr` when passed (`invoice_document_service.py:122-124`). That value is the licence-scoped Σ `amount_inr` (`CL._extract_bill_amount` :1257-1278), with no rupee round-off. |
| Tax / GST | none computed. Only GSTIN strings are printed (`purchase_invoice_pdf.py:182-200`). | — | — | No tax engine exists |
| Payments / due | `trade/models.py:351-363` | `q2(total) − q2(Σ payments)` | 2dp | — |
| Profit | `license_profit.profit_for_licenses` :361-416 (`sale_amount − purchase_amount`, excludes linked trades and commission); CL `_build_summary` :809, 826 (`Σ sale_bill_inr − Σ purchase_bill_inr` over display rows) | — | raw vs 2dp | The CL docstring (:691-704) says profit = position, but the code says bill difference |

### 2.4 SION norm planning, units, reports

| Area | Implementations | Notes |
|---|---|---|
| Norm planning engines | Hard-coded per norm: `e5_plan.py`, `e126_plan.py`, `e132_plan.py`, `e1_plan.py`, `milk_planner.py`, `norm_plan.py`, `split_by_percentage_planner.py`. Data-driven: `database_driven_sion_planner.py` (+ `sion_rule_engine.py`, `sion_planning_execution.py`). Comparison harness: `sion_shadow_comparison.py`. | Two parallel implementations under shadow migration. The budget input is the financial balance (`sion_rule_engine.py:335`, `sion_planning_execution.py:384`) or the item balance (`sion_planning_execution.py:1587`), so the planners inherit the F-1/F-2 semantics. Percentage split quantizes at `database_driven_sion_planner.py:274`. The prior doc flags E126/E132 CIF not recomputed after flooring (`MASTER_CALCULATION_REGISTER.md` PLAN-007); not re-verified here. |
| Plan caps | `plan_enforcement.py` (live aggregates; avoids stale stored `allotted_*`); `canonical_planning_service.py` | — |
| Unit conversion | No generic engine. `SionOutputMapping.conversion_factor` (`license/models/core.py:1758`), seeded as `"1"` KG everywhere (`sion_legacy_configurations.py:104-173`). PDF-import USD-rate conversion `bill_of_entry/views/parse_pdf.py:74`. | All quantities are assumed to be kg. |
| Dashboard | `license/views/dashboard.py:105-145, 215-285` (financial bulk; `>= $100` expiring filter); MV `dashboard_stats_mv` unused | — |
| Reports | `item_report.py` (`get_balance_cif` ×12), `item_pivot_report.py:681, 1019, 1367-1378`, `license_report.py:119`, `planned_report.py:222`, `active_dfia_report.py:114`, `purchase_profit_report.py:39` (own `trade_balance_usd = purchase$ − sale$`) | All except the bulk Excel use the financial engine |
| Frontend arithmetic (verified lines) | `LedgerTab.tsx:509-516` (Σ item `balance_cif_fc` vs licence `get_balance_cif`; a known ×N double-count trap commented at :500-505); `allocationMath.ts:55-116` (`round2` on **qty**, while backend qty is 3dp); `AllotmentAction.tsx:736`; `TradeForm.tsx:417-521`; `useMasterFormCalculations.ts:139-193`; `NestedFieldArray.tsx:128-155` | The other FE files listed in `09-ui-ux-assessment.md` §6 (ItemPivotReport, ItemReportTotalsBar, LicenseBalanceModal, PlanningEditor) were **not** line-audited here |

---

## 3. Worked numeric examples (dev DB, read-only)

**Licence L-1 (id=2603).** 1 export item, 13 import items, 1 BOE debit row, 3 AT allotment items, no trades, no hidden BOEs.

| Rule term | Source rows | Value |
|---|---|---|
| ORIGINAL CIF | 1 export item, `cif_fc` 190,992.45 (13 CREDIT RowDetails also sum to 190,992.450) | **190,992.45** |
| BOE CIF | RowDetails #464730, D, qty 44,238.000, `cif_fc` 75,672.030, `cif_inr` 7,207,760.960, BOE ex-rate 95.2500 | **75,672.03** (`calculate_boe_debit_total` = `calculate_debit`, since no allocations exist) |
| ALLOTMENT CIF | #27051 AT 75,691.22, linked to 19 BOEs ⇒ contributes 0. #27209 AT 19,097.10, unlinked. #26905 AT 92,261.00, unlinked. | 19,097.10 + 92,261.00 = **111,358.10** |
| BILLED CIF WITHOUT BOE | no trade lines in dev DB | **0.00** |
| UTILISED CIF | 75,672.03 + 111,358.10 + 0 | **187,030.13** |
| AVAILABLE CIF | 190,992.45 − 187,030.13 | **3,962.32** |

All four engines (`calculate_balance`, `calculate_customs_balance`, `calculate_financial_balance`, `calculate_all_components`), the stored `balance_cif`, and the customs ledger all return **3,962.32**. Divergent outputs for the same licence:
- **Financial Ledger API** (`GET /api/licenses/2603/balance-ledger/`, `build()`) returns `computed_balance` **190,992.45**, `engine_balance` 3,962.32, `difference` 187,030.13 (exactly the utilised CIF), `mismatched` True and warnings `FINANCIAL_MISMATCH`, `UNSOURCED_BOE`. The last two data rows run to 96,223.32 and then 3,962.32, but the final row prints 190,992.45. Running the same builder **without** `canonical_data` gives 3,962.32 with `mismatched` False.
- **`license_balance_mv`** returns utilised 0, allotted 187,049.32 (includes the BOE-linked #27051) and balance **3,943.13**.

**Floor example: Licence L-2 (id=822).** Credit 211,696.12; visible BOE 297,786.44; allotment 0. The raw result is **−86,090.32**. Every engine returns **0.00**, the stored `balance_cif` is 0.00, and the customs ledger final row is 0.00 while its BOE rows run negative. The Financial Ledger API shows 211,696.12 (F-1). Dev-wide, 35 licences are affected; the worst raw value is −3,447,851.40.

**Billed-without-BOE / financial engine (synthetic, from the test fixture, not dev data).** `test_balance_ledger_views.py:170-196`: PURCHASE line 89,283.10 and SALE line 80,359.10, no BOE. opening = 0 (purchase exists), so 0 + 89,283.10 − 80,359.10 − 0 − 0 = **8,924.00**. The canonical running total is the same, which is why the existing view test passes despite F-1.

**Item quantity example.** Item id 31722: stored `available_quantity` 126,953.000 vs live 126,953.160 (`CS:97`, `round_down(...,0)`).

---

## 4. End-to-end paths for the 3 critical workflows

### 4.1 Licence balance
1. **Input:** DGFT licence import, `ledger.py` upload, BOE entry and allotment entry.
2. **DB:** `license_licenseexportitemmodel`, `bill_of_entry_rowdetails`, `allotment_allotmentitems` + BOE M2M, `reconciliation_*allocation`, `trade_licensetradeline` + `trade_licensetrade_boes`.
3. **Rule:** `.claude/rules/business-rules.md` (5-line rule).
4. **Service:** `LicenseBalanceCalculator._calculate_financial_balance` BC:1582 (via `get_balance_cif` `models/core.py:330`); customs engine BC:1406; ledger builder LB:1596.
5. **Cache writes:** `license/signals.py:282-320` writes `LicenseBalance.balance_cif` and `is_null` (<500); `CS.update_balance_values` :164 writes item fields and `is_null` (<100).
6. **API:**
   - `GET /api/licenses/` (`get_balance_cif`, `serializers/license.py:826`; map from `views/license.py:315`).
   - `GET /api/licenses/{id}/overview-summary/` (`views/license_overview.py:33` → `license_overview_summary.py:54`).
   - `GET /api/licenses/{id}/balance-ledger/` (`views/license_balance_ledger.py:63` → LB `build`).
   - `GET .../item-usage/` (`views/license.py:822`).
7. **Frontend:** `pages/license-overview/OverviewTab.tsx:226` → `FinancialSummarySection.tsx:21` (F-1 value), `FinancialLedgerTable.tsx`, customs ledger section; `pages/masters/tables/LedgerTab.tsx:516` (client chooses licence vs Σ item balance); `pages/license-balance/useLicenseBalanceLedger.ts`.
8. **Outputs:**
   - PDF `GET .../balance-pdf/` (`views/license.py:887` → `license_balance_pdf.py:646`, uses `engine_balance`, so it is correct, but it renders the F-1 ledger rows and summary).
   - Excel `GET .../balance-excel/` (`views/license.py:924` → `license_balance_excel.py:1166`, which calls `build_financial_ledger` with `canonical_data` at :1191-1209, so F-1 applies; `get_balance_cif` at :879).
   - Bulk Excel `POST .../bulk-balance-excel/` (`:1604` **customs-visible engine**).

### 4.2 Allotment → BOE allocation
1. **FE:** `pages/AllotmentAction.tsx` → `GET allotment-actions/{id}/available-licenses/` (`views_actions.py:229`). Candidates come from the stored `available_quantity > 0` (:324) and live `available_value_bulk_map` (:548). The pair payload is built by `_position_payload` :64 → `allocation_availability.py` → `paired_allocation_max.py`.
2. **Write:** `POST allotment-actions/{id}/allocate-items/` (`AllotmentAction.tsx:570` → `views_actions.py:1050/1072`). The CIF pair is checked as ROUND_UP (:1187, :1321). qty ≤ **stored** `available_quantity` (:1341). CIF ≤ `effective_source_row_cif_available` (:1374).
3. **DB:** `allotment_allotmentitems` insert. The `update_stock` signal (`allotment/models/core.py:445-470`) runs `CS.update_balance_values`.
4. **BOE link:** the BOE form sets `BillOfEntryModel.allotment` M2M (+ `is_boe`). From then on, BC `Exists` forces the allotment contribution to 0 (BC:808-812, 823-830). The BOE `RowDetails` row becomes the debit.
5. **Partial match:** the reconciliation UI → `ReconciliationViewSet` (`reconciliation/urls.py:10`) → `create_boe_allotment_allocation` (`allocation_service.py:437`). The allocation is netted in BC `_annotate_allotment_contribution`. It only matters while no BOE is M2M-linked to the allotment.
6. **Outputs:** `GET .../generate-pdf/` (`views_actions.py:1639`), transfer letter (:1665), and the customs ledger "Pending Allotment" rows (LB:910-940).

### 4.3 Invoice / trade billing
1. **FE:** `pages/TradeForm.tsx` computes the line `amount_inr` (whole rupee), `cif_inr` and `exc_rate` client-side (:450-510).
2. **POST/PUT** `/api/trades/` → `trade/serializers.py` → `LicenseTradeLine.save` (`trade/models.py:567`, fills `amount_inr` only if 0) → `LicenseTrade.recompute_totals` (:365).
3. **Pairing:** `copy-to-purchase/sale`, `link-trade` (`trade/views.py:556-612`, `trade_service.py:202-450`).
4. **Representation:** the legacy `trade.boes` tag and/or `create_invoice_boe_allocation` (`allocation_service.py:224`). Auto-match `reconcile_trade_boe_links` runs only from management commands or as a dry run (`boe_link_reconciler.py:71`, LB:531).
5. **Balance effect:** BC `calculate_trade` (SALE in full) + `calculate_debit` (represented BOE excluded) + `calculate_purchase_credit` (incl. COMMISSION_PURCHASE).
6. **Ledger:** `CanonicalLedgerService` → `license/views/ledger.py` (`LicenseLedgerViewSet`) → FE `pages/LicenseLedger*`.
7. **PDFs:**
   - `GET /api/trades/{id}/generate-bill-of-supply/` (`trade/views.py:404` → `bill_of_supply_pdf.py:468`, `round(subtotal)` HALF_EVEN).
   - `generate-purchase-invoice` (:446 → `purchase_invoice_pdf.py:449`).
   - The ledger-package sale document (`license_ledger_export.py:40-50` → `invoice_document_service.py:106-124`) prints the licence-scoped `sale_bill_amount` as the invoice total.

---

## 5. Test coverage summary and gaps

Existing tests that pin behaviour:
- `license/tests/test_balance_calculator.py`: mock-heavy; **pins the floor** at :277.
- `test_balance_ledger_views.py`: builder-level and trade-only view cases.
- `test_balance_excel_export.py`, `test_balance_cif_single_source.py`, `test_license_list_balance_consistency.py`, `test_cross_output_parity_option_c.py`.
- `reconciliation/tests/test_allocation_service.py`, `test_boe_link_reconciler.py`.
- `allotment/tests/test_module3_allocation_scenarios.py`.
- `core/tests/test_materialized_views.py`: SQL text only, not the numbers.
- `FE/pages/license-balance/allocationMath.test.ts`, `balanceMetricContract.test.ts`.

Gaps, ranked:
1. **No test of `LicenseBalanceLedgerBuilder.build()` / `balance-ledger` with a BOE or allotment.** This is the gap that lets F-1 through.
2. No negative-balance characterization beyond the floor-pinning test.
3. No test for `LicenseTradeLine.compute_amount` or `recompute_totals`; grep finds 0 test files referencing either.
4. No test of PDF round-off vs `total_amount`.
5. No AR-type allotment test at licence vs item level.
6. No parity test of stored vs live `available_quantity` (5,996 dev mismatches).
7. No test of snapshot item `available_quantity` vs BC:2030.
8. No test of `condition_pool` against the represented-BOE + SALE double subtraction.
9. No commission-direction test in the financial engine.
10. No test of null-DFIA threshold consistency.
11. No bulk-Excel vs single-Excel Balance CIF parity test.
