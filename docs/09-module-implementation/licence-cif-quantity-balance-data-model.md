# Licence Item CIF & Quantity Balance — Data Model

Status: **Audit of the existing schema. No schema change made.** Every source below was checked against the `lmanagement` database (read-only) and the code.

## 1. Source of each component

| Component | Source table(s) | Amount fields | Key | Used by current engine? |
|---|---|---|---|---|
| Original CIF | `license_licenseimportitemsmodel` | `cif_fc` (USD), `cif_inr` | `id` (item), `license_id`, `serial_number` | Yes (licence credit) |
| Original quantity | `license_licenseimportitemsmodel` | `quantity`, `unit` | `id` | Partly (item view only) |
| Debited CIF / qty | `bill_of_entry_rowdetails` (`transaction_type = 'D'`) | `cif_fc`, `cif_inr`, `qty` | `id`, `bill_of_entry_id`, `sr_number_id` | Yes (CIF); qty only in item view |
| Sale link (membership) | `trade_licensetrade_boes` | — (no amount) | `licensetrade_id`, `billofentrymodel_id` | Yes: decides exclusion |
| Sale link (allocation) | `reconciliation_invoiceboeallocation` | `allocated_cif_fc`, `allocated_cif_inr`, `allocated_qty` | `row_details_id`, `trade_line_id`, `status`, `is_current`, `version`, `superseded_by_id` | Partly: netting only (2 rows in production) |
| Invoiced CIF / qty | `trade_licensetradeline` (trade `direction = 'SALE'`) | `cif_fc`, `cif_inr`, `qty_kg` | `id`, `trade_id`, `sr_number_id` | Yes (CIF); quantity not netted at licence level |
| Allotted CIF / qty | `allotment_allotmentitems` (`status = 'CREATED'`) | `cif_fc`, `qty`, `released_quantity` | `id`, `allotment_id`, `item_id` | Yes (CIF); quantity in item view only |
| Allotment → BOE link | `bill_of_entry_billofentrymodel_allotment` | — | `billofentrymodel_id`, `allotmentmodel_id` | Yes: excludes linked allotments |
| Stored item columns | `license_licenseimportitemsmodel` | `debited_value`, `allotted_value`, `available_value` | `id` | Shown in item view; **not authoritative** (see §4) |

## 2. Units

| Table | Unit field | Values found | Status |
|---|---|---|---|
| `license_licenseimportitemsmodel.unit` | yes | `kg` 2,343 · `KG` 30 · `Kg` 2 · `mts` 2 | `kg` case variants: normalise. `mts`: unverified (see §5) |
| `license_licenseexportitemmodel.unit` | yes | `kg` 221 | Consistent |
| `trade_licensetradeline.qty_kg` | name asserts kg | not validated | Assumed kg |
| `bill_of_entry_rowdetails.qty` | **no unit column** | — | Assumed kg; not verified |
| `allotment_allotmentitems.qty` | **no unit column** | — | Assumed kg; not verified |

## 3. Relationships used

```
licence import item (SR)  ──<  BOE debit row (RowDetails D)  >──  BOE
        │                              │                           │
        │                              └── allocation (amount) ──┐ │
        │                                                        │ │
        ├──<  trade line (SALE) >── trade ──< membership >───────┘─┘
        │                    └── allocation (amount)
        │
        └──<  allotment item (CREATED) >── allotment ──< BOE membership
```

Every component is attached to an **item** through `sr_number_id` (trade line, BOE row) or `item_id` (allotment item). Aggregation to licence level is a sum over items.

## 4. Stored item columns are not authoritative

The item columns `debited_value`, `allotted_value` and `available_value` are denormalised copies. Checks on the 2,348 items:

- Stored columns satisfy `original = debited + allotted + available` on **709 items**.
- Stored `available_value` differs from the recalculated value on **1,652 items**.
- Stored `debited_value` differs on **255 items**.
- Four items store 1,913.61, the **licence** balance of 2583, instead of their own balance.

Conclusion: the item view must read the canonical calculation, not these columns. The columns should be retired or rebuilt once the calculation is approved (decision O-7).

## 5. Quantity unit validation

- 2,314 items are `kg`; 32 are `KG` (same unit, normalised); 2 are `mts`.
- The two `mts` items (licences 2655 and 2656) carry 163,077.02 and 166,831.32 units with CIF of 52,608.33 and 53,600.00. The median CIF per unit for the 318 items labelled `kg` is 1.54 USD. The two `mts` items come to 0.32 per unit: about a fifth of that if the unit is kilograms, but about 4,700 times below it if the unit is tonnes. The data favours kilograms. This is an inference, not proof. Correction (verified in the Milestone 1 run): the two items are sold in full, with no BOE link. Item 39559 carries 166,831.32 authorised, 166,831.32 sold, and 0 BOE; both figures are in the same label, so the sale is consistent with the authorisation but still in `mts`. The unit is therefore still unresolved, but the quantities reconcile to each other.
- BOE and allotment quantity have no unit field. Comparison of sold and BOE quantities: **77 of 133** licences with sales differ by more than one unit. Licence 2583: sold 588,211.6, BOE 245,540.3 — not comparable until the unit basis is confirmed (decision O-1).

Quantity is therefore **not validated** for reconciliation. It is reported as UNIT_UNVERIFIED wherever it appears.

## 6. Keys and identity rules the canonical service must use

- Every movement carries its **source ID**: BOE row ID, trade line ID, allotment item ID, licence import item ID.
- Links carry an **allocation ID** (the allocation row, or a stable composite of membership + row + line until migration).
- Uniqueness per (`row_details_id`, `trade_line_id`) for current allocations: **not enforced by the database today**; enforced by application code only (decision O-5).
- Negative amounts are rejected. Floats are rejected. Decimal throughout (`numeric` in PostgreSQL, `Decimal` in Python).

## 7. Concurrency and locking

- Allotment allocation locks the allotment and the licence item (`select_for_update`): live path.
- Reconciliation locks both sides: live path.
- Trade↔BOE membership changes: not verified.
- Any canonical write path must lock the BOE row and the sale line, and the item, inside `transaction.atomic`.

## 8. What the canonical service reads (proposed)

One read per licence, grouped by item: item import rows; BOE debit rows with their current allocations; trade SALE lines with membership; allotment items CREATED with allotment membership. No per-row queries (the audit used this pattern for 2,348 items in one pass per source).

## 9. Missing relations

- No link between an allotment and a sale. The 69 items where both exist cannot be proven distinct or the same (decision O-4).
- No status on trades: cancellation cannot be represented as a state (decision O-6).
- No unit on BOE or allotment quantity (decision O-1).
- No item-level attribution for purchases: purchases sit on SR lines whose authorised CIF is zero for 2,026 items (decision O-3).
