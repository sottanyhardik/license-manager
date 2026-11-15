# 05 — Duplicate-Logic Register (Phase Zero discovery)

**Scope:** every business rule or calculation that is implemented more than once. This covers backend vs backend, backend vs frontend, screen vs PDF vs Excel, serializer vs service, and SQL/MV vs Python. Branch `feature/version5`, 2026-11-15.
**Companion:** `04-business-logic-inventory.md`. Its abbreviations apply here: BC = `backend/apps/license/services/balance_calculator.py`, LB = `.../license_balance_ledger_builder.py`, CL = `.../canonical_ledger_service.py`, CS = `backend/apps/core/scripts/calculate_balance.py`, FE = `frontend/src`.
**Evidence standard:** every location below was read at the cited line. "Agree" / "Diverge" is based on reading the code. Where possible it was also checked numerically on the local dev DB with read-only probes; licences are anonymised as L-1 (id=2603) and L-2 (id=822).
**Prior-doc note:** `docs/architecture/GATE3_DUPLICATE_CALCULATIONS.md` §P1 rates licence-balance duplication as "LOW (all delegate to single calculator)". That rating is wrong: see DUP-01 to DUP-07. The lead docs have "APPROVED" sign-offs with `[Name]` placeholders. These docs are not evidence of owner approval.

**Rule for this register:** consolidation is proposed, never performed. Any row whose consolidation would change a number that a user sees is marked **NEEDS OWNER DECISION**.

Risk: **H** = a wrong or inconsistent money figure reaches users or drives a write. **M** = it diverges in reachable edge cases. **L** = latent, dormant or cosmetic.

---

## 1. Summary table

| ID | Rule | # impls | Outputs | Risk | Owner decision? |
|---|---|---|---|---|---|
| DUP-01 | Financial Ledger final balance: engine vs canonical running | 2 | **Diverge (2,036 / 2,185 dev licences)** | H | Yes (which figure the screen shows; restoring it changes a visible number) |
| DUP-02 | Licence "Available CIF": 4 engines + bulk siblings | 8 | Diverge (hidden BOEs, trades, commission) | H | **Yes** |
| DUP-03 | Floor-at-0 vs signed balance | 13 floors in BC vs signed CL | Diverge (35 dev licences) | H | **Yes** (KNOWN OPEN DECISION) |
| DUP-04 | Outstanding allotment CIF/qty | 6 | Diverge (type filter, netting, BOE-linked) | H | Yes |
| DUP-05 | Item available quantity (live vs snapshot vs stored) | 3 | Diverge (5,996 dev items) | H | Yes |
| DUP-06 | Item available CIF / condition pool | 3 (+2 caches) | Diverge (pool double-subtracts SALE + BOE) | H | Yes |
| DUP-07 | Bulk Excel vs single Excel / screen "Balance CIF" | 2 | Diverge for traded or hidden licences | M | Yes |
| DUP-08 | Commission directions in balance | 2 rule sets | Diverge | M | Yes |
| DUP-09 | Billed-CIF-without-BOE | 3 | Diverge | M | Yes |
| DUP-10 | Trade line amount & rounding | 4 (BE + 3 FE) | Diverge (₹ whole vs 2dp) | M | Yes |
| DUP-11 | Invoice total & round-off | 4 | Diverge (HALF_UP vs HALF_EVEN; licence-scoped total) | H | Yes |
| DUP-12 | "Null DFIA" balance threshold | 4 | Diverge ($100 vs $500) | M | Yes |
| DUP-13 | Allotment CIF ↔ unit value ↔ INR | 2 (BE + FE) | Partly diverge | L | No (BE authoritative) |
| DUP-14 | Allocation Max / pair rounding | 4 | Mostly agree; 2 dead copies | L | No |
| DUP-15 | Allotment annotation chain copy (bulk) | 2 | Agree today; drift risk | M | No |
| DUP-16 | Materialized views vs Python engine | 2 | Diverge totally (dormant) | L | No (retire) |
| DUP-17 | Overview cards vs balance | 2 formulas on one card set | Diverge (cards do not sum) | M | Yes |
| DUP-18 | Excel "Total License CIF" vs credit | 2 | Diverge | M | Yes |
| DUP-19 | Profit/Loss definition | 2 (+1 stale docstring) | Diverge in scope | M | Yes |
| DUP-20 | Reconciliation tolerances | 3 | Different constants | L | Yes (policy) |
| DUP-21 | Hidden-BOE exclusion on debited value/qty | live vs stored | Diverge | M | No (bug-class; but visible) → Yes |
| DUP-22 | BOE totals / exchange rate rounding | 3 | Diverge by rounding mode/precision | L | No |
| DUP-23 | SION planning: hard-coded planners vs DB-driven engine | 2 | Shadow-compared | M | Yes (cut-over) |
| DUP-24 | Debit row null-BOE filter single vs bulk | 2 | Agree on dev data | L | No |
| DUP-25 | Mid-calculation quantization (CL) vs edge-only (BC) | 2 | Diverge by ≤ cents | L | Yes (invariant) |

---

## 2. Register entries

### DUP-01 — Financial Ledger "Current Available Balance" (H, NEEDS OWNER DECISION)
- **Rule:** the Financial Ledger final balance must equal `calculate_financial_balance`. This is stated in the docstring at LB:654-662.
- **Locations:**
  - (a) the engine, BC:1582-1651;
  - (b) the ledger's own `running`, LB:647 then LB:664-665;
  - (c) the **override**, LB:667-672: `computed_balance = quantize_2dp(canonical_data['license_running_balance'])`;
  - (d) `canonical_data`, which `build()` always supplies (LB:1614-1624) and the Excel builder also supplies (`license_balance_excel.py:1191-1215`);
  - (e) CL running = seed + PURCHASE − SALE (CL:286-347), with **no BOE and no allotment term**.
- **Divergence (concrete):** for L-1, engine = 3,962.32 and LB own running = 3,962.32, but the displayed `computed_balance` is 190,992.45. The difference is 187,030.13, which is exactly L-1's utilised CIF. The final row prints `MISMATCH vs Balance Engine (Δ $187,030.13)`. The response carries `FINANCIAL_MISMATCH`, and `reconciliation.matched` is False. In a dev sweep, 2,036 of 2,185 licences differ by more than $10. It is shown at `FE/pages/license-overview/FinancialSummarySection.tsx:21` and in the PDF/Excel ledger sheets.
- **Why the tests miss it:** `test_balance_ledger_views.py:194` covers a trade-only licence, where the CL value equals the engine. The builder tests at :534 and later do not pass `canonical_data`.
- **Canonical owner:** `LicenseBalanceCalculator.calculate_financial_balance`. CL keeps ownership of the trade-ledger running total for the separate "License Ledger" screen.
- **Approach:** remove the override, or scope it to CL-only screens. Add a `build()`-level characterization test with a BOE and an allotment.
- **Changes visible numbers:** yes. The screen, PDF and Excel would show 3,962.32 instead of 190,992.45 for L-1.
- **Owner question:** was "Phase 4E-D" meant to make the Financial Ledger trade-only? If yes, the engine check and its label are wrong instead.

### DUP-02 — Licence available CIF, multiple engines (H, NEEDS OWNER DECISION)

| Impl | Location | Formula | Consumers |
|---|---|---|---|
| Customs (visible) | BC:1349 / bulk :1315 | credit − visible BOE − allotment | LB:244, 258; bulk Excel `license_balance_excel.py:1604`; snapshot `customs_balance` (`balance_snapshot.py:153, 237`) |
| Components | BC:1458 | same, components quantized individually | no production caller left (the overview moved to the snapshot) |
| Customs (all) | BC:1406 / bulk :1434 | credit − (visible + hidden BOE) − allotment | customs ledger anchor LB:951, 966; reconciliation LB:1257; snapshot `customs_available_balance` |
| Financial | BC:1582 / bulk :1654 | opening + purchase − sale − netted BOE − allotment | `get_balance_cif`; list; dashboard; reports; planners; pool caps |
| Customs ledger running | LB:792-953 | same as "Customs (all)", row by row | Customs Ledger UI/PDF/Excel |
| Canonical running | CL:286-347 | seed ± PURCHASE/SALE | License Ledger screen; DUP-01 |
| Stored cache | `LicenseBalance.balance_cif` via `license/signals.py:309-313` | financial, at save time | serializer fallback `serializers/license.py:845` |
| MV | `core/materialized_views.py:27-80` | see DUP-16 | none |

- **Agree:** on licences with no hidden BOEs, no trades and no allocations, all Python engines agree (L-1 = 3,962.32 for all four).
- **Diverge:**
  - Hidden BOEs: Customs (visible) > Customs (all).
  - Trades: Financial ≠ Customs, by `purchase − sale − (BOE exclusions)`.
  - Commission: see DUP-08.
  - The BC docstring for `calculate_balance` (:1351-1356) says it is no longer the business figure, yet it still feeds the bulk Excel and the snapshot.
- **Canonical owner:** a single `LicenseBalanceService.snapshot()` returning a named tuple of `original`, `boe`, `allotment`, `billed_without_boe`, `utilised`, `available_customs` and `available_financial`. Each term is computed once.
- **Approach:** first decide which engine *is* AVAILABLE CIF in the 5-line rule. The rule maps to the financial engine, but the financial engine has no explicit BILLED term and nets BOE instead. Then make the others derived views.
- **Changes visible numbers:** yes, for traded or hidden licences. Merging engines is forbidden until the owner decides (`.claude/rules/business-rules.md`).

### DUP-03 — Floor at 0 vs signed (H, NEEDS OWNER DECISION — KNOWN OPEN DECISION)
- **Floors:**
  - BC licence-level: :1345, 1403, 1431, 1454, 1482, 1651, 1699.
  - BC item-level: :1760, 1782, 1858, 1998, 2079, 2100.
  - Elsewhere: LB:665, 953 (final row only; per-row `running_balance` is signed); serializer `serializers/license.py:848`; `condition_pool.py:126`; CS:98; `effective_cif_mode.py:128` (`max(…,0)` as an executable cap).
- **Signed implementations:** CL running and `current_balance` (CL:799, "never absolute-valued"); `license_profit`.
- **Divergence:** L-2 raw −86,090.32 shows as 0.00 in every engine. The customs ledger rows run negative and the final row then shows 0.00, so the ledger does not add up. Dev-wide, 35 licences are affected, totalling −6,957,414.63.
- **Test pinning the floor:** `test_balance_calculator.py:277` (`test_calculate_all_components_negative_balance`).
- **Canonical owner:** the balance service should return the signed value plus an `over_utilised` flag. The *executable* cap stays at `max(…,0)` (allocation must never use negative headroom).
- **Changes visible numbers:** yes.

### DUP-04 — Outstanding allotment CIF / qty (H, NEEDS OWNER DECISION)

| Impl | Location | BOE-linked rule | Partial allocation netting | Type filter |
|---|---|---|---|---|
| Engine, licence | BC:711-842, 970 | `Exists` → 0 | yes | **none (AT + AR)** |
| Engine, bulk (copy) | BC:1196-1262 | `Exists` → 0 | yes | none |
| Engine, item | BC:895, 928 | `Exists` → 0 | yes | **AT only** |
| Condition pool | `condition_pool.py:105-109, 198-200` | `allotment__bill_of_entry__isnull=True` | **no** (gross `cif_fc`) | none |
| Item usage (Excel, item drawer) | `item_usage.py:103, 146` | isnull | **no** | none |
| Overview count | `license_overview_summary.py:101` | isnull | n/a | none |
| Stored ARO term | CS:55-56 | n/a | n/a | `'ARO'` (never matches; the DB code is `AR`) |
| MV | `materialized_views.py:53-56, 117-118` | **counts linked** | no | none |
| FE | `LedgerTab.tsx:511` Σ stored `allotted_value` | stored | stored | — |

- **Divergence:**
  - L-1: engine 111,358.10 vs MV 187,049.32.
  - Any partially reconciled allotment: the pool and item_usage show the gross value while the engine shows the remainder.
  - An unlinked AR allotment is counted at licence level but not at item level. Dev has 0 such rows today, so this is latent.
- **Canonical owner:** `_annotate_allotment_contribution`.
- **Approach:** route the pool, item_usage and bulk through it, and fix the `'ARO'` literal. Whether AR counts as "allotment" or "debited" is a business rule.
- **Changes visible numbers:** yes, for pool-limited items and Excel usage rows.

### DUP-05 — Item available quantity (H, NEEDS OWNER DECISION)
- **(a) Live:** BC:1958 and :2030 compute `qty − visible D qty − AT outstanding − direct-sale qty`, as Decimal.
- **(b) Snapshot:** `balance_snapshot.py:197-205` computes the same **without the direct-sale term**. Its comment claims lock-step.
- **(c) Stored:** CS:72-98 computes `qty − (ALL D qty incl. hidden + ARO≡0) − AT − direct-sale`, using float and `round_down(…, 0)`, i.e. **whole units**.
- **Consumers of (c):** the allocation write cap `allotment/views_actions.py:1341`, the candidate filter :324, serializer `get_available_quantity` (`serializers/license.py:275-278`) and the Excel "Balance Quantity" (`license_balance_excel.py:270`). Plan-mode caps (`views_actions.py:1002`) also use (c).
- **Divergence:** 5,996 of 26,818 dev items differ between (a) and (c); 5,791 of them by less than 1 unit (e.g. 126,953.160 live vs 126,953.000 stored). Hidden BOEs and direct sales add further gaps.
- **Canonical owner:** (a).
- **Approach:** store (a) in the cache writer. Decide whether whole-unit truncation is an intended business rule (it may be: allocation uses `quantity_step=1.000`, `views_actions.py:93`).
- **Changes visible numbers:** yes (fractional units appear; caps move).

### DUP-06 — Item available CIF / condition-type pool (H, NEEDS OWNER DECISION)
- **Implementations:**
  - Live property `available_value_calculated`, `license/models/core.py:1034-1093`.
  - Bulk mirror `condition_pool._resolve_available_value`, :250-290. It agrees with the property by construction, and the docstring demands lock-step.
  - Stored `available_value`, CS:125-198 (capped by `balance_cif_fc`; serial-1 carve-out).
  - Serializer `balance_cif_fc` alias (`serializers/license.py:424-436`).
  - `effective_cif_mode` projection (`effective_cif_mode.py:61-127`; individual mode uses `calculate_item_balance`, otherwise the licence `get_balance_cif`).
- **Divergence:**
  - The pool `used = BOE + allotment + ALL SALE cif_fc` (`condition_pool.py:98-124`). The financial engine nets a represented BOE against its SALE line; the pool subtracts both, which double-counts. The pool also uses gross allotments (DUP-04).
  - Stored vs live differs for 3,032 dev items (e.g. stored 165,290.88 vs live 7,879.16).
  - `calculate_item_balance`'s zero-CIF branch (BC:1795-1817) mixes licence-scope debit with item-scope allotment.
- **Canonical owner:** BC item methods plus a pool function built on the engine's netted terms.
- **Changes visible numbers:** yes (pool-limited items).

### DUP-07 — Excel Balance CIF: bulk vs single vs screen (M, NEEDS OWNER DECISION)
- **Locations:**
  - Single Excel: `license_balance_excel.py:879` (`get_balance_cif`, financial).
  - Bulk Excel: :1402 and :1604 (`calculate_balance_for_licenses`, customs-visible). The comment at :1595-1600 wrongly says this is the same as `get_balance_cif`.
  - Screen / list: financial.
- **Divergence:** any licence with trades or hidden BOEs prints a different "Balance CIF" in the bulk workbook than on screen and in the single workbook.
- **Owner:** the financial bulk (`calculate_financial_balance_for_licenses`).
- **Changes visible numbers:** yes (bulk Excel).

### DUP-08 — Commission directions (M, NEEDS OWNER DECISION)
- **Financial engine:** purchase credit includes `COMMISSION_PURCHASE` (BC:1059, 1190, 1307). Sale debit is `SALE` only (BC:1025, 1282). `has_trading_activity` includes the commission purchase (BC:1139, 1162).
- **Canonical ledger:** `COMMISSION`, `COMMISSION_PURCHASE` and `COMMISSION_SALE` all have `balance_direction: NONE` (`license/domain/transaction_semantics.py:83-130`). They are totalled separately as `total_commission` (CL:344).
- **Other implementations:** `license_profit` uses PURCHASE/SALE only (`license_profit.py:391`). The direct-sale qty uses SALE only (BC:1899). The condition pool uses SALE only.
- **Divergence:** a COMMISSION_PURCHASE of X raises the financial balance by X (and zeroes the opening when it is the only purchase, BC:1527-1530). The canonical ledger does not move. A COMMISSION_SALE moves neither. This is asymmetric.
- **Owner:** `TransactionSemantics` as the single direction→sign table, consumed by BC.
- **Changes visible numbers:** yes.

### DUP-09 — Billed CIF without BOE (M, NEEDS OWNER DECISION)
- **(a) Engine (implicit):** SALE lines counted in full (BC:1063); represented BOEs excluded via formal allocation **or** legacy tag (BC:210-366).
- **(b) Display `billed_no_boe`:** `serializers/license.py:350-385` and `item_usage.py:157-195`: SALE lines whose trade has **no `trade.boes` tag**. It ignores `InvoiceBOEAllocation` and `ExternalInvoiceLink`, and it ignores counterpart/linked pairs.
- **(c) Direct-sale qty:** BC:1861-1927: SALE minus linked BOE on the **same item**, minus counterpart/linked, net of `allocated_qty`.
- **Divergence:** an invoice matched only through a formal allocation shows as "billed no BOE" in (b) but not in (a). A BOE spanning two items is represented for both items in (a) (BOE-level rule, BC:221-233) but only for the same item in (c).
- **Owner:** one `represented_by_invoice` resolver (BC:250), with explicit CIF and qty variants.
- **Changes visible numbers:** yes (the LedgerTab "billed_no_boe" column, `LedgerTab.tsx:512`).

### DUP-10 — Trade line `amount_inr` (M, NEEDS OWNER DECISION)

| Impl | Location | Rounding |
|---|---|---|
| Backend `compute_amount` | `trade/models.py:558-565` | qty to 4dp, rate to 2dp (the column is 3dp, so the rate loses a digit), result 2dp HALF_UP. **Only used if the client sends 0** (:569-570) |
| TradeForm | `FE/pages/TradeForm.tsx:497-504` | `Math.round` → **whole rupee** |
| TradeForm reverse | :476-493 | rate/pct derived from the amount, 3dp |
| Masters NestedFieldArray | `FE/pages/masters/NestedFieldArray.tsx:139-155` | `toFixed(2)` |
| Incentive line | `trade/models.py:633-635` vs `TradeForm.tsx:417-422` (`Math.round`) | 2dp vs ₹1 |

- **Divergence:** qty 10.5 × rate 33.3 = 349.65. TradeForm stores 350.00, NestedFieldArray stores 349.65, and the backend would compute 349.65. The same trade has different totals depending on which form created it.
- **Owner:** the backend `compute_amount` (always recompute and reject client drift), or the owner states that whole-rupee line amounts are the rule.
- **Changes visible numbers:** yes.

### DUP-11 — Invoice total and round-off (H, NEEDS OWNER DECISION)
- **(a) Model:** `recompute_totals` (`trade/models.py:365-391`) rounds to ₹1 with **ROUND_HALF_UP**.
- **(b) Purchase invoice PDF:** `purchase_invoice_pdf.py:449` uses `round(subtotal)`, which is Python banker's rounding (**HALF_EVEN**).
- **(c) Bill of supply PDF:** `bill_of_supply_pdf.py:468`, same as (b) unless `canonical_total_inr` is passed.
- **(d) Ledger-package sale document:** `invoice_document_service.py:106-124` passes `canonical_total_inr = sale_bill_amount`. That value is Σ `amount_inr` for **this licence's lines only** (`CL._extract_bill_amount` :1257-1278), not rounded to the rupee, yet the PDF still lists every line of the trade (`bill_of_supply_pdf.py` iterates `trade.lines.all()`).
- **FE:** `calculateTotal` (`TradeForm.tsx:517-521`) is an unrounded float sum.
- **Divergence:**
  - A subtotal of ₹1,234.50 gives a stored `total_amount` of 1,235.00 but a PDF total of 1,234.00 (verified: `round(Decimal('1234.50')) == 1234`).
  - For a multi-licence SALE trade, the ledger-package PDF total is a partial sum that differs from `total_amount`, and the document hash differs per licence.
- **Owner:** `LicenseTrade.total_amount`. The PDFs should print the stored totals.
- **Changes visible numbers:** yes (printed invoice totals; this is a legal document).

### DUP-12 — "Null DFIA" threshold (M, NEEDS OWNER DECISION)
- **Locations:**
  - `license/signals.py:316`: `is_null = balance < 500` (licence save).
  - CS:204-216: `< 100` (every item balance refresh).
  - `license/management/commands/sync_licenses.py:37`: `500`.
  - Dashboard expiring widgets: `views/dashboard.py:142, 262`: `>= 100`.
  - FE `pages/reports/ActiveLicenses.tsx:20` label: "balance < 100".
- **Divergence:** a licence with a balance of $300 is flagged null after a licence save and un-flagged after the next item refresh. The dashboard counts (`dashboard.py:110-112`) depend on which writer ran last.
- **Owner:** one constant in `apps.core.constants`.
- **Changes visible numbers:** yes.

### DUP-13 — Allotment `cif_fc` / `unit_value` / `cif_inr` (L)
- **Backend:** `allotment/models/core.py:135-160`: qty × unit (2dp HALF_UP); unit = cif/qty (3dp ROUND_UP); inr = cif × rate (2dp HALF_UP).
- **Frontend:** `useMasterFormCalculations.ts:139-193`: same formulas with `toFixed(2)` / `Math.ceil`, plus a reverse `cif_fc = cif_inr / rate` (:160-175). The backend overwrites that reverse value whenever a unit value is set.
- **Status:** this mostly agrees. The JS `toFixed` is not strictly HALF_UP for binary floats, and the reverse path is silently discarded.
- **Owner:** the backend. The frontend copy is a preview only. This is not user-visible after save, so no owner decision is needed.

### DUP-14 — Allocation Max / CIF pair (L)
- **Canonical:** `paired_allocation_max.py:23-73`, via `allocation_availability.py` and `views_actions._position_payload`.
- **Copies:**
  - `AllocationService.calculate_max_allocation`, `allotment/services/allocation_service.py:30-91`: delegates to the canonical function, but uses step 0.001 where the API uses 1.000 (`views_actions.py:93`). Its only callers are tests and legacy code.
  - `ItemBalanceCalculator.calculate_available_value_for_allocation`, BC:2105-2149: unrounded and stepless. It has **no callers**.
  - FE `AllotmentAction.tsx:736`: HALF_UP, where the backend uses ROUND_UP (:1187). The difference is ≤ 0.01, which is inside the backend's 0.01 tolerance (:1321).
  - FE `allocationMath.ts:55-116`: reconciliation allocation budget. It uses `round2` on **qty**, while backend qty is 3dp, so a 0.005-qty slack can be rejected by `_validate_fits` (`reconciliation/services/allocation_service.py:209`).
- **Approach:** delete the dead copy at BC:2105. Have the FE use server-provided `suggested_cif`.
- **Changes visible numbers:** no.

### DUP-15 — Allotment annotation chain copied in the bulk method (M)
- **Locations:** `_annotate_allotment_contribution` BC:711-842 is the shared chain. `calculate_allotment_for_licenses` BC:1196-1262 re-implements it inline.
- **Status:** it agrees today; the comment at :1247 says "kept in sync". There is a drift risk, already realised once for the `has_linked_boe` fix.
- **Approach:** call `get_allotment_rows_bulk(ids).values('item__license_id')`.
- **Changes visible numbers:** no.

### DUP-16 — Materialized views vs Python engine (L, retire)
- **Location:** `core/materialized_views.py:27-150`.
- **Defects:**
  - BOE utilisation is in **INR** (`rd.cif_inr`) while credit is in USD.
  - The deployed definitions still compare against `'DEBIT'` (verified in `pg_matviews`), so utilised = 0. `CREATE … IF NOT EXISTS` never replaces them.
  - BOE-linked allotments are counted.
  - The rd × ai join fans out.
  - There is no hidden or allocation netting and no floor.
- **L-1:** MV balance 3,943.13 vs engine 3,962.32. **L-2:** MV 211,696.12 vs engine 0.
- **Readers:** no non-test readers. Refresh is only via the management command and tasks, auto-refresh is off (`signals_materialized_views.py:25`), and there is no beat entry (`lmanagement/celery.py:43-140`).
- **Approach:** drop the views, or rebuild them over the engine's terms. This needs a migration and owner sign-off for the DB change.
- **Changes visible numbers:** no.

### DUP-17 — License Overview cards (M, NEEDS OWNER DECISION)
- **Location:** `license_overview_summary.py:54-66`.
- **Divergence:** the Total / Debited / Allotted cards use the customs components (visible BOE, licence allotment), while the Balance card is financial. For a traded licence, `credit − debit − allotment ≠ balance` on the same screen. The module docstring (:9-13) still claims numeric identity with `calculate_all_components`.
- **Owner:** the balance snapshot should expose components of *the same* engine.

### DUP-18 — Excel "Total License CIF" (M, NEEDS OWNER DECISION)
- **Location:** `license_balance_excel.py:835-880` and :1340-1460. The value is Σ visible BOE `cif_fc` (via `item_usage.get_item_usage`) + Σ unlinked allotment **gross** + `get_balance_cif`.
- **Divergence:** this equals credit only when there are no trades, no partial allotment allocations and no hidden BOEs, and the balance is not floored. In every other case the printed "total" is not the licence CIF.
- **Owner:** `calculate_credit`.

### DUP-19 — Profit / Loss (M, NEEDS OWNER DECISION)
- **(a)** `license_profit.py:361-416`: `Σ sale amount_inr − Σ purchase amount_inr`, excluding linked trades and commission, raw Decimal.
- **(b)** CL `_build_summary` :805-828: Σ display-row `sale_bill_amount` − Σ `purchase_bill_amount`, 2dp. The display rule and commission exclusion differ from (a).
- **(c)** The CL docstring (:691-704) describes profit as the *position*, `purchase − sale` in USD. That contradicts the code beneath it.
- **(d)** `purchase_profit_report.py:30-50`: `trade_balance_usd = purchase$ − sale$`, deliberately its own figure.
- **Owner decision:** one definition of realised margin, and whether linked transfer pairs count.

### DUP-20 — Tolerances (L, owner policy)
- **Values:**
  - Reconciliation auto-match: CIF 1.00, qty 1.000 (`settings.py:581-582`).
  - Ledger self-check: 10.00 (LB:28).
  - FE allocation: EPS 0.005 (`allocationMath.ts:16`).
  - Allocation pair: 0.01, plus a $20 settlement buffer (`paired_allocation_max.py:8`, `views_actions.py:1318`).
  - Legacy service: `required + 20` (`allocation_service.py:65`).
- **Owner:** a policy table in settings.

### DUP-21 — Hidden-BOE exclusion on debited value / qty (M, NEEDS OWNER DECISION)
- **Live paths:** these exclude hidden rows everywhere: `exclude_hidden` BC:44, `item_usage.py:91-99` and `condition_pool.py:98-103`.
- **Stored paths:** CS:34-44 (`debited_qty`, `debited_value`) and the Customs ledger include them. The ledger does so intentionally.
- **Divergence:** on hidden-BOE licences, the stored debited value/qty and the allocation qty cap (DUP-05) treat the previous owner's imports as our utilisation.
- **Verification:** this cannot be verified on dev data, because there are 0 genuinely hidden BOEs locally.

### DUP-22 — BOE totals and exchange rate (L)
- **(a)** `BillOfEntryModel.save`: `exchange_rate = total_inr / total_fc` at 4dp, updated only if |Δ| > 1 (`bill_of_entry/models.py:252-274`).
- **(b)** The signal re-computation does the same (:501-527).
- **(c)** `get_exchange_rate` uses 3dp HALF_UP (:325-333).
- **(d)** The totals `get_total_fc` / `get_total_inr` are pre-quantized to 2dp with the context's HALF_EVEN (:285-296). The rate is derived from already-rounded totals.
- **(e)** The FE TradeForm rate is 2dp (`TradeForm.tsx:464`).
- **Status:** small numeric differences. The "> 1" guard means a stored rate can be up to ₹1 stale.

### DUP-23 — SION planning engines (M, NEEDS OWNER DECISION on cut-over)
- **Implementations:** the hard-coded norm planners (`e5_plan.py`, `e126_plan.py`, `e132_plan.py`, `e1_plan.py`, `milk_planner.py`, `split_by_percentage_planner.py`, `norm_plan.py`) and the data-driven `database_driven_sion_planner.py` + `sion_rule_engine.py`. Parity is checked by `sion_shadow_comparison.py`.
- **Status:** the outputs are compared, but there is no single owner. Both consume the financial balance, so they inherit DUP-01 to DUP-03 semantics. Detailed parity was not re-verified here; this belongs to the `dgft-dfia-rules-auditor` scope.

### DUP-24 — Debit rows: single vs bulk BOE-null filter (L)
- **Locations:** `get_debit_rows` filters `bill_of_entry__isnull=False` (BC:431). `calculate_boe_debit_total_for_licenses` (:552-554) and `calculate_debit_for_licenses` (:672-677) do not.
- **Status:** the dev DB has 0 D rows with a null BOE, so the outputs agree today. Align them to remove latent drift.

### DUP-25 — Quantization placement (L, invariant)
- **BC:** quantizes once, at the end (`quantize_2dp` BC:39).
- **CL:** quantizes every amount and every running step (CL:323, 347, 361), and keeps a second `quantize_2dp` definition (CL:64).
- **CS and FE:** use float and `toFixed`.
- **Divergence:** up to a few cents on long ledgers. Sub-cent BOE `cif_fc` values (3dp) are rounded per row in CL but summed raw in BC.
- **Owner:** `apps.core.utils.decimal_utils` (a single `quantize_2dp`). Applying the "quantize at the edge" invariant changes cents, so this needs owner sign-off.

---

## 3. Conflicts requiring owner decision (ranked), each with a recommendation

1. **Financial Ledger shows the canonical trade-only running balance instead of the engine (DUP-01).** *Recommendation:* treat this as a defect. Restore the engine figure on the Financial Ledger, keep CL for the License Ledger screen, and add `build()`-level tests. Confirm intent first, because the change moves the visible numbers on 2,036 of 2,185 dev licences.
2. **Negative balances: floor at 0 vs preserve and flag (DUP-03, the KNOWN OPEN DECISION).** *Recommendation:* return the signed value plus an `over_utilised` flag everywhere a balance is displayed or reported. Keep `max(…,0)` only on executable caps (allocation and planning headroom). Re-pin `test_balance_calculator.py:277`.
3. **Which engine is "AVAILABLE CIF" in the 5-line rule (DUP-02 / DUP-17 / DUP-07).** *Recommendation:* the financial engine, with an explicit BILLED-WITHOUT-BOE term so that UTILISED = BOE + ALLOTMENT + BILLED is reportable. Keep customs (all) as the regulatory figure, and retire `calculate_balance` (visible-only) from the bulk Excel and the snapshot.
4. **Invoice totals printed vs stored (DUP-11).** *Recommendation:* PDFs print `LicenseTrade.subtotal_amount`, `roundoff` and `total_amount`. A per-licence ledger package must not issue a bill of supply whose total differs from the trade's total.
5. **Outstanding allotment definition, including AR type and partial netting (DUP-04, DUP-06).** *Recommendation:* one engine definition, used by the pool, item usage and Excel. Clarify whether AR ("ARO") allotments are debit or allotment, and fix the `'ARO'` vs `'AR'` literal.
6. **Item available quantity: stored whole-unit truncation, hidden BOEs and direct-sale omission (DUP-05, DUP-21).** *Recommendation:* the live Decimal formula (BC:2030) is authoritative. If whole units are a business rule, apply them only at the allocation step (`quantity_step`), not in stored balances.
7. **Commission trades in the balance (DUP-08).** *Recommendation:* adopt `TransactionSemantics` (commission excluded) in the financial engine, or explicitly make both commission directions symmetric.
8. **Billed-without-BOE display vs engine representation (DUP-09).** *Recommendation:* derive the display from the engine's represented-BOE resolver.
9. **Trade line amount rounding: whole rupee vs 2dp (DUP-10).** *Recommendation:* the backend recomputes `amount_inr` at 2dp HALF_UP, and rupee rounding is applied once at invoice level (`recompute_totals`).
10. **Null-DFIA threshold $100 vs $500 (DUP-12).** *Recommendation:* a single constant. $500 matches the licence-level writer and the sync command.
11. **Profit/Loss definition (DUP-19).** *Recommendation:* `license_profit` is the owner, and the CL docstring is corrected.
12. **Mid-calculation quantization in CL (DUP-25) and tolerance policy (DUP-20).** *Recommendation:* quantize at the edge only, and collect tolerances in settings.
13. **SION planner cut-over (DUP-23).** *Recommendation:* name the DB-driven engine as owner once shadow parity holds. This needs a `dgft-dfia-rules-auditor` review.

**Safe, non-visible consolidations (no owner decision needed, but they still need `cif-balance-auditor` review and tests):** DUP-14 (delete BC:2105 and the legacy Max), DUP-15 (bulk allotment chain), DUP-16 (retire the MVs; the DB migration needs approval), DUP-24 (null-BOE filter parity), DUP-13 (the FE preview only).
