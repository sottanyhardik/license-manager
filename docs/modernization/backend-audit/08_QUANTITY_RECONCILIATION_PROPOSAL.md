# Backend Audit 08: Quantity reconciliation (PROPOSAL ONLY)

Status: **PROPOSAL, not approved.** Read-only audit, 2026-11-16, feature/v5 working tree. No code, test,
migration or other doc was changed. No database was queried.

What this doc does:
- Quantity semantics stay open (`DECISION_REGISTER.md` "Approved" D4 note; doc 06 D4 quantity).
- It invents no rule. Every conflict is an owner decision (§5).
- Canonical CIF (`.claude/rules/business-rules.md`) is out of scope and unchanged.

Paths are relative to `backend/apps/` unless they start with `frontend/`. Mapping evidence (units, links, grain)
is in `07_BOE_ALLOTMENT_MAPPING_AUDIT.md`. Allocation divergences D1..D12 and decisions O1..O10 are in `05`.

Headline facts:
- **No transaction-level unit exists.** Every quantity is in the unit of its licence import item (SR).
- **There is no unit conversion code** (07 §3).
- So "quantity" is only additive **within one SR**, or across SRs whose `unit` strings are equal.

---------------------------------------------------------------------------------------------------

## 1. Inventory: every place a quantity is computed

### 1.1 Server-side

| # | Quantity | Formula (as coded) | Where | Precision / floor | Consumers |
|---|---|---|---|---|---|
| S1 | **Dynamic available qty** (engine) | `quantity − Σ DEBIT RowDetails.qty (non-hidden) − Σ AT contributed_qty − Σ direct-sale contributed_qty` | `license/services/balance_calculator.py:1969-2009`; bulk `:2041-2092` | Decimal 3dp; **floored at 0** (:2009) | trade SALE validation (`trade/api/serializers.py:438`), `balance_snapshot`, A6 orphan |
| S2 | Outstanding allotment qty (R2) | per AllotmentItems `contributed_qty = 0 if M2M-linked else max(qty − min(qty, Σ active current allocated_qty), 0)`, **AT only** | `balance_calculator.py:812-841`, `:895-925` (`type='AT'` :919) | Decimal | S1, S3, item summary |
| S3 | **Stored available qty** (`available_quantity` column) | `float(quantity) − (debited + aro) − allotted(S2) − direct_sale`, then `round_down(…, 0)`, `max(…, 0)` | `core/scripts/calculate_balance.py:73-99` | **float, integer floor**, floored 0 | `LicenseImportItemSerializer.available_quantity` (`license/api/serializers/license.py:270-273`), A1/A2 allotment gates (doc 05 D2), `overview-items` `balance_qty` (`license/services/license_overview_items.py:49`) |
| S4 | Stored debited qty (`debited_quantity`) | `debited + aro + direct_sale`; the `aro` filter uses literal `'ARO'` and never matches (`calculate_balance.py:56`) | `calculate_balance.py:102-105` | float, `round(…, 2)` into a 3dp column | serializer `debited_quantity` (:304), `overview-items` `debited_qty`, balance modal |
| S5 | BOE debited qty (`boe_debited_quantity`) | `Σ DEBIT RowDetails.qty` (non-hidden), excludes direct sale | `balance_calculator.py:2012-2039`; serializer `:307-318` | Decimal 3dp | CustomsLedgerSection |
| S6 | Stored allotted qty (`allotted_quantity`) | `round(S2, 2)` | `calculate_balance.py:108-111` | float 2dp | serializer `:323`, CustomsLedgerSection, modal, `overview-items` |
| S7 | Direct-sale qty (engine) | SALE lines, not paired (`counterpart`/`linked_trade` null), `contributed_qty = 0 if the trade's BOEs have a DEBIT row on the same SR else max(qty_kg − Σ InvoiceBOEAllocation.allocated_qty, 0)` | `balance_calculator.py:1872-1936` | Decimal | S1, S3, S4 |
| S8 | **Billed-no-BOE qty** (`billed_no_boe_qty`) | `Σ qty_kg` of SALE lines whose trade has **no** `boes` (any SR). **No** pair exclusion, **no** allocation netting | serializer `license/api/serializers/license.py:384-418`; bulk `license/services/item_usage.py:199-236`; also `item_pivot_service.py:188-190`, `allotment/api/views_actions.py:549-561, :925-941` | Decimal (serialized float) | CustomsLedgerSection (S8 is subtracted client-side), item pivot, allotment candidate grid |
| S9 | Planned qty | `plan_reporting.plan_map_for_import_items` | serializer `:325-339` | Decimal | CustomsLedgerSection "Planned" |
| S10 | Plan remaining (R3) | `max(planned − Σ AllotmentItems.qty where allotment.bill_of_entry IS NULL, AT, PLAN, target)`, no ledger netting | `license/services/plan_enforcement.py:98-139`; emitted `license/api/views/license.py:392, :835`; `views_actions.py:605-615` | Decimal, floored 0 | "Plan Remaining", allotment caps (doc 05 D5/D6) |
| S11 | Plan group qty | `available_qty`, `total_utilized_qty = total − available`, `balance_qty = max(available − planned, 0)`; **mixed units blocked** | `license/services/plan_utilization.py:240-285` | Decimal | PlanningEditor |
| S12 | Pivot item summary | per `(canonical_item_id, sion)` bucket: `actual = boe + allotted`, `available = cell.available_qty or total − actual`, `balance_qty = max(available − planned, 0)`, `over_utilized = max(actual − total, 0)`; **no unit in the key** | `license/services/item_pivot_item_summary.py:52-110` | Decimal | item report / pivot |
| S13 | Overview-items row | `balance_qty = stored available_quantity` (S3); `debited_qty = S4`, `allotted_qty = S6` | `license_overview_items.py:40-63` | stored | `frontend/.../types.ts:98-105` |
| S14 | Overview-allotments row | `quantity = Σ AllotmentItems.qty` of this licence per allotment: AT+AR, ACTUAL+PLAN, linked+unlinked, all SRs/units, not netted | `license/services/license_overview_allotments.py:37-44, :78` | Decimal | AllotmentsTab |
| S15 | Overview-BOEs | `qty = Σ RowDetails.qty` per BOE, **C+D**, not returned | `license_overview_boes.py:82` | — | none (dropped) |
| S16 | BOE header total | `get_total_quantity = Σ qty` all rows (C+D, all SRs/licences); `unit_price = total_fc / total_qty` | `bill_of_entry/models.py:296-320`; serializer `bill_of_entry/api/serializers.py:153-165, :229`; `reconciliation/selectors.py:161`; `bill_of_entry/api/views_export.py:774, :883` | Decimal | BOE list/export, reconciliation |
| S17 | Allotment requirement | `balanced_quantity = max(required_quantity − Σ all AllotmentItems.qty, 0)`; `alloted_quantity = Σ qty` (all SRs, ACTUAL+PLAN) | `allotment/models/core.py:172-196`; re-derived `views_actions.py:260-264, :1295, :1381` | Decimal | allotment serializer (`allotment/api/serializers.py:162-167, :233-238`), A1 caps |
| S18 | Ledger remaining (reconciliation) | `remaining_for_allotment_item`: `max(qty − Σ allocated_qty, 0)`, ignores M2M; `remaining_for_row_details_allotment_side` / `_invoice_side` (invoice side also subtracts ExternalInvoiceLink qty); `remaining_for_trade_line` | `reconciliation/services/allocation_service.py:68-198` | Decimal 4dp | `create/edit_*_allocation`, `license_balance_ledger_builder.py:1045-1082, :1188-1198` |
| S19 | Ledger rows | Customs/Financial ledger "Pending/Active Allotment": `qty = raw a_row.qty` but CIF = `contributed` | `license/services/license_balance_ledger_builder.py:476, :938` | Decimal | ledger UI/PDF/Excel |
| S20 | Paired max allocation | step-floored qty under CIF ceiling | `allotment/services/paired_allocation_max.py:23-73` | 1.000 / 0.001 steps | allotment Max button (doc 05 D12) |
| S21 | `balance_quantity` (model) | delegates to S3; fallback re-derivation `quantity − debited − allotted(bill_of_entry IS NULL)` | `license/models/items.py:176-196` | Decimal floor 0 | legacy readers |
| S22 | `usable` / `opening_balance` | `Σ CREDIT RowDetails.qty` (`round_down`) | `license/models/items.py:351-370` | Decimal | legacy readers |

Partial transactions:
- Partial BOE ↔ allotment: `BOEAllotmentAllocation` (S2, S18).
- Partial invoice ↔ BOE: `InvoiceBOEAllocation` (S7, S18).
- Release/reactivate quantities exist on `AllotmentItems` (`allotment/models/core.py:285-330`), but no code writes
  them (doc 05 O7). Nothing reads `released_quantity` into any quantity above.

Reservations:
- Outstanding allotment qty (S2) is the only reservation that reduces available qty.
- Plan qty (S9/S10) is informational for availability (serializer comment `license.py:194-197`) but caps allotments.

### 1.2 Client-side (frontend)

| # | Site | Formula | Inputs | Notes |
|---|---|---|---|---|
| C1 | **Client** `frontend/src/pages/license-overview/CustomsLedgerSection.tsx:11, :22-27` `actualAvailableQuantity` (not the server `build_customs_ledger`) | `quantity − boe_debited_quantity (S5) − allotted_quantity (S6) − billed_no_boe_qty (S8)` | licence detail `import_license` | **Overrides** any server value. Not floored. JS float. Drives `status` (`:12`, `=== 0` ⇒ "Exhausted") |
| C2 | `frontend/src/components/LicenseBalanceModal.tsx:1027-1035` | `quantity − debited_quantity (S4) − allotted_quantity (S6)` | same | label "Balance Quantity = Total − Debited − Allotted"; not floored. The same modal also shows stored `available_quantity` (S3) at `:901` |
| C3 | `frontend/src/pages/license-overview/AllotmentsTab.tsx:71-72` | `Σ row.quantity` (S14), `Σ row.cif_fc` | overview-allotments | "Total Allotted" (`:126-130`) **includes "Linked to BOE" rows and mixes units** (register cites `:78-79`; the code has moved to `:71-72`) |
| C4 | `AllotmentsTab.tsx:92, :116` Rate | `cif_fc / quantity` | S14 | cross-SR / cross-unit when the allotment spans SRs; includes PLAN rows. `AllotmentModel.unit_value_per_unit` already exists server-side (`allotment/models/core.py:60-65`) |
| C5 | `frontend/src/pages/license-overview/BoesTab.tsx:87` | `Σ cif_fc` | overview-boes (C+D) | CIF; listed for completeness |
| C6 | `frontend/src/pages/reports/itemPivotReportUtils.ts:84-94` `itemSummarySubtotal` | Σ qty fields across rows; balance-weighted unit price | S12 rows | sums across rows of possibly different units |
| C7 | `frontend/src/pages/reports/itemReport/ItemReportTotalsBar.tsx:18`, `ItemReportTable.tsx:382, :400` | Σ `available_quantity`, Σ `planned_quantity` across items | item report | unit-blind totals |
| C8 | `frontend/src/components/planning/PlanningEditor.tsx:259, :333, :432, :699, :780, :812, :1053, :1253-1257` | Σ planned split qty; grand totals across groups | S11 | groups are single-unit (S11), but the grand total row (`:1253-1257`) adds groups together |
| C9 | `frontend/src/pages/masters/NestedFieldArray.tsx:808` | Σ `qty_kg` of trade lines | trade form | form preview |
| C10 | `frontend/src/components/AllotmentFormModal.tsx:244`, `pages/masters/hooks/useMasterFormCalculations.ts:172` | `unit_value_per_unit = ceil(cif/requiredQty, 3dp)` | allotment form | mirrors server ROUND_UP 3dp (doc 05 D10) |
| C11 | `frontend/src/pages/license-balance/allocationMath.ts:47-66` `distributeAllocation` | greedy qty/CIF budgets | — | **only imported by its own test** (orphan) |
| C12 | `frontend/src/pages/masters/tables/LedgerTab.tsx:238, :256, :367, :384` | Σ qty, Rate | — | dead file (register D6) |

---------------------------------------------------------------------------------------------------

## 2. Where the formulas disagree (concrete examples)

Example rows marked **[test]** reuse an existing fixture verbatim. The values for S1 are what that test asserts.
The other columns are derived by reading the code; they were **not executed**. Rows marked **[derived]** are
constructed from the code.

| ID | Scenario | S1 engine | S3 stored | C1 client CustomsLedgerSection | C2 modal | Root cause |
|---|---|---|---|---|---|---|
| X1 [test] | `test_sale_trade_quantity_consumption.py::test_linked_purchase_sale_pair_has_no_net_quantity_consumption`: SR qty 100, paired SALE line 30, no `trade.boes` | **100** (asserted) | 100 | **70** (S8 = 30: no pair exclusion) | 100 | S8 ≠ S7 (pairs) |
| X2 [test] | `::test_formal_invoice_boe_allocation_replaces_direct_sale_quantity`: SR 100, SALE line 30 with `InvoiceBOEAllocation` 30 to a BOE row 30, no `trade.boes` | **70** (asserted) | 70 | **40** (S5 30 + S8 30: the same 30 kg subtracted twice) | 70 | S8 ignores allocation netting → **double count**. The fixture is hand-built. In production this arises only when a trade edit clears `trade.boes` (`trade/api/serializers.py:528`, `instance.boes.set(new_boes)`) while an `InvoiceBOEAllocation` stays ACTIVE (no reversal on that path was found). X1, by contrast, can occur directly |
| X3 [derived] | SR 100, SALE line 30 on a trade whose `boes` holds a BOE with a row only on a *sibling* SR | 70 (engine comment `balance_calculator.py:1894-1897`) | 70 | **100** (S8 excludes any trade with BOEs) | 70 | S8 BOE test is header-level, S7 is per-SR |
| X4 [test] | `test_balance_calculator.py::test_partially_allocated_allotment_only_leaves_remainder_quantity`: AllotmentItems 100 qty / 500 CIF, BOE row 60 / 300, allocation 60 / 300 | outstanding **40** (asserted) | allotted 40 | uses S6 = 40 | uses 40 | agree at item level. But S14 row shows **100 / 500**. AllotmentsTab total adds 500 next to BoesTab's 300 (screen 800 vs engine utilised 300 + 200). The ledger row (S19) prints qty 100 next to CIF 200 |
| X5 [test] | `::test_boe_linked_allotment_quantity_excluded_even_when_not_formally_allocated`: AllotmentItems 100 / 500, parent allotment in a BOE M2M | outstanding **0** (asserted) | 0 | 0 | 0 | item level agrees. S14 still returns 100 / 500 ("Linked to BOE"), and C3 "Total Allotted" includes it → **double count on screen** |
| X6 [derived] | SR 1000.500, no debits (doc 05 D2) | 1000.500 | **1000** | 1000.500 | 1000.500 | S3 integer floor |
| X7 [derived] | SR 1000, DEBIT row 10.125 | 989.875 | **989** | 989.875 | **989.88** (S4 = Python `round(10.125, 2)` = 10.12, exact binary half → even) | S3 floor, S4 2dp float |
| X8 [derived] | SR 100, DEBIT rows 120 (over-use) | 0 (floored) | 0 | **−20** | **−20** | floor vs signed; status in C1 is not "Exhausted" (`=== 0` fails) |
| X9 [derived] | SR 0.3, BOE 0.1, allotted 0.2 | 0.000 | 0 | **−2.78e-17** (JS float), so status falls through to "Partially Used" | same float | C1/C2 float arithmetic |
| X10 [derived] | AR-type allotment item 100 kg / $1 000 | unchanged (AT filter) | unchanged (`'ARO'` literal) | unchanged | unchanged | qty is consistent, but licence ALLOTMENT CIF counts the $1 000 (R1, doc 05 D3) → qty and CIF tell different stories |
| X11 [derived] | Allotment with SR 1 = 500 kg and SR 2 = 20 pcs on one licence | n/a | n/a | n/a | n/a | S14 `quantity` = **520**. C4 Rate = cif / 520. S17 `balanced_quantity` = required − 520 |
| X12 [derived] | BOE with DEBIT 50 and CREDIT 50 on one SR | debited 50 | 50 | 50 | 50 | S16 `total_quantity` = **100**; S15 likewise (C+D) |
| X13 [derived] | Same canonical name on SR A (kg) and SR B (pcs), two licences | per SR | per SR | per SR | per SR | S12 bucket adds them; C6/C7 totals add them |
| X14 [derived] | PLAN AllotmentItems 10 on a target, its allotment M2M-linked to a BOE | outstanding 0 | 0 | 0 | 0 | S10 counts it as **not** used (filter `bill_of_entry IS NULL`) → plan capacity restored while the BOE debits. Doc 05 D5/D6/O4 |
| X16 [derived] | SR 100, DEBIT row 30 on a genuinely hidden (previous-owner) BOE | **100** (S1 uses `exclude_hidden`, `balance_calculator.py:1996`) | **70** (stored writer `core/scripts/calculate_balance.py:41-45` aggregates `item_details` with no hidden exclusion) | 100 (S5 excludes hidden, `:2033`) | **70** (S4 includes the hidden row) | stored writer ignores hidden BOEs |
| X15 [derived] | Manual `BOEAllotmentAllocation` from a BOE row on SR 3 (kg) to an allotment item on SR 5 (pcs) | SR 5 outstanding reduced in pcs by a kg figure | same | same | same | no same-SR check (07 OD-MAP-3) |

Duplicate-count risks summarised (quantity):
- X2: S5 + S8 subtract the same allocated sale qty.
- X4/X5: S14 and C3 show linked or allocated allotment qty next to the BOE qty that represents it.
- X12: S15/S16 add CREDIT to DEBIT. This is LATENT: current writers never attach a C row to a BOE (07 §1.2).
- X16: the stored S3/S4 values count hidden-BOE quantity that S1/S5 exclude.
- X13, X11, C6–C8 grand totals: adding across units.
- F5 in 07: joining SR → canonical-name M2M multiplies rows.

---------------------------------------------------------------------------------------------------

## 3. Candidate definitions (options for the owner)

None of these is approved. Recommendations are marked. All reuse engine outputs; none re-derives balance math.

### 3.1 Item "Available Quantity" (the number C1 and C2 try to show)

| Option | Definition | Matches | Cost |
|---|---|---|---|
| **QA-1 [RECOMMENDED]** | S1 as is: `quantity − BOE DEBIT qty − outstanding AT allotment qty (engine) − direct-sale qty (engine)`, Decimal 3dp, floored at 0. Plus additive `over_utilised_quantity = max(−unfloored, 0)` and `is_quantity_over_utilised`. This is consistent with the unchanged item-level floor (business-rules.md "DECIDED 2026-11-16": `ItemBalanceCalculator` floors unchanged). It mirrors the CIF decision's flag only, not its signed value. | trade validation (S1), allotment Max path; fixes X1–X3, X6–X9 on screen | additive serializer fields; C1/C2 read them instead of computing |
| QA-2 | Signed S1 (no floor), no flag | CIF convention (signed) | changes the meaning of the floored value consumers already rely on |
| QA-3 | Keep stored S3 for display | today's list views | integer floor and float (X6, X7); stale-cache risk (doc 05 D2) |
| QA-4 | Keep C1 (client formula) | today's Customs Ledger | X1–X3 wrong vs engine; violates "no backend recalculation by frontend" (`docs/decisions/LEDGER_APPROVED_SEMANTICS.md` Rule 1) |

Component fields to display next to it (QA-1): `boe_debited_quantity` (S5, exists), `outstanding_allotment_quantity`
(S2, Decimal; today only the 2dp float S6 is exposed), and **`direct_sale_quantity` (S7)**. S7 is the
engine-consistent counterpart of S8.

**OD-QTY-2** decides whether "Billed (No BOE)" keeps showing S8 (a header-level trade filter) or switches to S7.
Its CIF sibling `billed_no_boe` has the same filter shape and is outside this doc.

### 3.2 Allotment line quantity in the grouped workspace

| Option | Definition |
|---|---|
| **QL-1 [RECOMMENDED]** | Return the raw `AllotmentItems.qty` + SR `unit`, and split it with engine annotations: `outstanding_qty = contributed_qty`, `represented_qty = qty − contributed_qty`. Totals use `outstanding_qty` only. Depends on the doc 06 §7.4 `classification` and linked-allotment exclusion, which are **PROPOSED, not approved (OD-BA-e)**. |
| QL-2 | Raw qty only, no split; totals omitted |
| QL-3 | Keep today's per-allotment sum (S14) |

### 3.3 BOE line quantity

| Option | Definition |
|---|---|
| **QB-1 [RECOMMENDED]** | DEBIT rows only, per (BOE, SR), + unit; CREDIT rows listed separately (07 OD-MAP-1) |
| QB-2 | C+D sum (today's S15/S16) |

### 3.4 Group (Supplier / Product) quantity

| Option | Definition |
|---|---|
| **QG-1 [RECOMMENDED]** | `qty_by_unit: [{unit, boe_qty, outstanding_allotment_qty, represented_allotment_qty, line_count}]`. No single qty when there is more than one unit. No derived "available" at group level. |
| QG-2 | No quantity at group level at all |

### 3.5 Allotment Rate column (C4)

| Option | Definition |
|---|---|
| **QR-1 [RECOMMENDED]** | Show the stored `AllotmentModel.unit_value_per_unit` from the server (exists, 3dp), as a header attribute |
| QR-2 | Server per-line `cif_fc / qty` only when the line is single-SR (always true at line grain) |
| QR-3 | Keep the client division (cross-unit when the allotment spans SRs) |
| QR-4 | Drop the column until a server field exists (register's own option) |

Backend fields that would carry them. All are **API CONTRACT ADDITIONS** (additive, nothing removed or renamed),
and none is implemented:

| Field | Endpoint / serializer | Source |
|---|---|---|
| `available_quantity_live` (Decimal string 3dp), `over_utilised_quantity`, `is_quantity_over_utilised` | `LicenseImportItemSerializer` (licence detail `import_license`) | `ItemBalanceCalculator.calculate_available_quantity_for_items` (batched, exists) |
| `outstanding_allotment_quantity` | same | `get_outstanding_allotment_totals_for_items` (exists) |
| `direct_sale_quantity` | same | `calculate_direct_sale_quantity_for_items` (exists) |
| `qty`, `unit`, `outstanding_qty`, `represented_qty`, `allotment_type`, `allocation_basis` | new `overview-transactions/` lines (doc 06 §7.4) | engine annotations |
| `qty_by_unit[]`, `mixed_units` | new endpoint group summaries | SQL GROUP BY `sr.unit` |
| `unit_value_per_unit` | `overview-allotments/` row (additive) or new endpoint | `AllotmentModel` column |

The name `available_quantity` is already taken by the stored S3 value, which A1 gates on. Re-pointing it would
change behaviour, so a new name is proposed. Naming is part of OD-QTY-1.

---------------------------------------------------------------------------------------------------

## 4. Characterization and regression tests that should exist first (names + assertions; not written)

Pin current behaviour first: mark a test xfail only where the owner chooses a change.

| Test (proposed path::name) | Fixture | Assertions (current behaviour to pin) |
|---|---|---|
| `license/tests/test_quantity_parity.py::test_paired_sale_engine_vs_billed_no_boe_qty` | X1 | S1 = 100; S3 = 100; serializer `billed_no_boe_qty` = 30; `available_quantity` = 100 |
| `::test_allocated_sale_counted_once_by_engine_twice_by_client_inputs` | X2 | S1 = 70; `boe_debited_quantity` = 30; `billed_no_boe_qty` = 30; S4 `debited_quantity` = 30 |
| `::test_sibling_sr_boe_on_trade_keeps_direct_sale` | X3 | S7 = 30; `billed_no_boe_qty` = 0; S1 = 70 |
| `::test_stored_available_quantity_integer_floor` | X6 | S3 = 1000; S1 = Decimal("1000.500") |
| `::test_stored_debited_quantity_two_dp_rounding` | X7 | S4 = 10.12; S5 = Decimal("10.125") |
| `::test_over_utilised_item_floors_at_zero` | X8 | S1 = 0; S3 = 0; unfloored difference = −20 (computed in test) |
| `::test_ar_allotment_ignored_by_quantity_counted_by_cif` | X10 | S1/S3 unchanged; `calculate_allotment` += 1000 |
| `license/tests/test_license_overview_allotments_view.py::test_quantity_sums_all_rows_unnetted` | X4 | row `quantity` = 100, `cif_fc` = 500 while engine outstanding = 40 / 200 |
| `::test_linked_allotment_row_still_reports_full_quantity` | X5 | `status` = "Linked to BOE", `quantity` = 100 |
| `::test_mixed_unit_allotment_quantity_is_summed` | X11 | `quantity` = 520 (pins the unit-blind sum) |
| `::test_plan_and_actual_rows_both_summed` | F12 | ACTUAL 5 + PLAN 10 on the same SR → 15 |
| `license/tests/test_license_overview_boes_view.py::test_credit_rows_included_in_boe_cif` | X12 | `cif_fc` = C + D; engine `calculate_boe_debit_total` = D only |
| `bill_of_entry/tests/test_boe_totals.py::test_total_quantity_sums_credit_debit_and_srs` | X12 + 2 SRs | `get_total_quantity` = Σ all rows; `get_unit_price` = fc / that sum |
| `license/tests/test_balance_ledger_views.py::test_pending_allotment_row_qty_is_raw_while_cif_is_netted` | X4 | ledger row `qty` = 100, `cif_usd` = 200 |
| `license/tests/test_item_pivot_item_summary.py::test_bucket_sums_across_units` | X13 | bucket `total_qty` = kg + pcs (pins current) |
| `reconciliation/tests/test_allocation_service.py::test_cross_sr_same_licence_allocation_accepted` | X15 | `create_boe_allotment_allocation` succeeds; SR 5 outstanding reduced |
| `allotment/tests/test_plan_residual.py::test_linked_plan_row_releases_plan_capacity` | X14 | S10 `used_quantity` excludes the linked row |
| `license/tests/test_quantity_parity.py::test_hidden_boe_qty_stored_vs_engine` | X16 | S1 = 100 and `boe_debited_quantity` = 0; stored `available_quantity` = 70 and `debited_quantity` = 30 (pins current drift) |
| `::test_allocated_sale_double_subtracted_after_trade_boes_cleared` | X2 via production path | auto-allocate (`reconcile_trade_boe_links`), then a trade update with `boes=[]` (`trade/api/serializers.py:528`). Assert the allocation is still ACTIVE, `billed_no_boe_qty` = 30, S1 = 70 |
| `license/tests/test_license_overview_boes_view.py::test_boe_with_attached_credit_row` | X12 / 07 F9 | create a C `RowDetails` with `bill_of_entry` set (historical shape only). Assert `cif_fc` = C + D and that the row's status is driven by C too |
| `core/tests/test_ledger_import.py::test_reimport_duplicates_credit_rows` | 07 §7 escalation | run `core/scripts/ledger.py` import twice with the same C row. Assert the C row count = 2 and `usable` / `opening_balance` doubled (pins the defect; xfail once the owner rules) |
| Frontend `pages/license-overview/CustomsLedgerSection.test.tsx::"actual available overrides server and is unfloored"` | X8, X9 | renders −20; status not "Exhausted" for −2.78e-17 |
| Frontend `pages/license-overview/AllotmentsTab.test.tsx::"total allotted includes linked rows and adds units"` | X5, X11 | footer CIF includes the linked row; Qty = 520 |
| Frontend `components/LicenseBalanceModal.test.tsx::"balance quantity uses stored debited"` | X7 | shows 989.88 |

Then, after the owner decides:
- QA-1 parity: for each fixture X1–X9, `available_quantity_live == ItemBalanceCalculator.calculate_available_quantity(item)`.
  The UI shows that field and never computes its own.
- Endpoint: query count is constant; no line is counted twice (BOE across 2 SRs; allotment across 2 SRs;
  canonical-name M2M with 2 names); no group-level qty total when units are mixed.
- Run with: `license/tests/test_balance_*`, `test_sale_trade_quantity_consumption.py`, `test_license_overview_*`,
  `reconciliation/tests/*`, `allotment/tests/test_*allocat*`.

---------------------------------------------------------------------------------------------------

## 5. Owner decisions (unresolved; none decided here)

| ID | Question | Conflict evidence | Options (recommendation) |
|---|---|---|---|
| OD-QTY-1 | What is the item "Available Quantity" shown in the licence workspace? | S1 vs S3 vs C1 vs C2 (X1–X9) | QA-1 **[REC]** / QA-2 / QA-3 / QA-4; plus field naming |
| OD-QTY-2 | Is "Billed (No BOE)" qty the header-level S8 or the engine's S7? | X1–X3 | S7 **[REC]**, keep S8 as a separate diagnostic, or keep S8 only |
| OD-QTY-3 | Item qty over-use: floored with a flag, or signed? | CIF is signed (DECIDED); qty is floored (S1/S3); clients signed (C1/C2) | floor + flag **[REC]** / signed / floor only |
| OD-QTY-4 | Authoritative qty for allotment gates: S3 (int floor, cached) or S1 | X6; = doc 05 **O2** (do not decide twice) | defer to O2 |
| OD-QTY-5 | Allotment row/line quantity: raw, outstanding, or split? | X4, X5 | QL-1 **[REC]** / QL-2 / QL-3 |
| OD-QTY-6 | BOE CREDIT rows in BOE quantity and CIF totals | X12; = 07 **OD-MAP-1** | QB-1 **[REC]** / QB-2 |
| OD-QTY-7 | Group quantity across units | X11, X13 | QG-1 **[REC]** / QG-2 |
| OD-QTY-8 | Ledger Pending/Active Allotment row qty: raw or netted (to match its netted CIF)? | S19, X4 | show netted `contributed_qty` with raw as a secondary column **[REC]** / keep raw |
| OD-QTY-9 | Rate column | C4 | QR-1 **[REC]** / QR-2 / QR-3 / QR-4 |
| OD-QTY-10 | Client unit-blind grand totals (C6, C7, C8 `:1253-1257`) | X13 | per-unit totals from the server **[REC]** / hide when mixed / keep |
| OD-QTY-11 | AR allotment qty: reduce availability or not? | X10; = doc 05 **O3** | defer to O3 |
| OD-QTY-12 | Plan residual for BOE-linked PLAN rows | X14; = doc 05 **O4** | defer to O4 |
| OD-QTY-13 | Is a stored-vs-live 2dp/float drift in S4/S6 acceptable for display? | X7 | display Decimal live values **[REC]** / keep stored |
| OD-QTY-14 | Orphan `allocationMath.ts` (C11) | only its test imports it | delete with doc 05 O8 batch **[REC]** / keep |

Doc 05 O2, O3 and O4 and 07 OD-MAP-1 are cross-referenced, not duplicated. The owner should decide them once.

## Not verified

- §2 values other than the ones the cited tests assert. They were derived by reading code, not executed.
- Production frequency of X1–X3, X11–X15 (see 07 §5 M8, M9, M13; add for X1/X2:
  `SELECT count(*) FROM trade_licensetradeline tl JOIN trade_licensetrade t ON t.id = tl.trade_id WHERE t.direction = 'SALE'
  AND NOT EXISTS (SELECT 1 FROM trade_licensetrade_boes b WHERE b.licensetrade_id = t.id) AND (t.counterpart_id IS NOT NULL
  OR t.linked_trade_id IS NOT NULL OR EXISTS (SELECT 1 FROM reconciliation_invoiceboeallocation x WHERE x.trade_line_id = tl.id
  AND x.status = 'ACTIVE' AND x.is_current));`, which was **not run**).
- Tests run this session: the existing tests in 07 "Not verified" (92 passed). No gate was run. No new test was written.
