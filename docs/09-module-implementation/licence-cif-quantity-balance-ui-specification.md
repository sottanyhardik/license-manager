# Licence Item CIF & Quantity Balance — UI Specification

Status: **Specification only. No frontend code changed.** The table cannot be trusted for quantity until the unit basis is confirmed (open decision O-1). Until then quantity cells must show "Unit unverified" rather than a number that looks reconciled.

## 1. Where it appears

1. **Licence overview:** a summary of the licence totals, and the item table below it.
2. **Items / Balance page:** the full item table with filters, sorting and exports.

Both read one canonical API response (§7). Neither calculates a balance in React.

## 2. Licence summary (top of overview)

Two separate panels, never merged:

**CIF**

| Original authorised | Debited | Allotted | Invoiced | **Available** |
|---:|---:|---:|---:|---:|
| 11,92,65,123.24 USD (all items, audit total) | … | … | … | **…** |

**Quantity** (unit shown on every figure; if unverified, the panel reads "Quantity unit unverified — balances not shown")

| Original | Debited | Allotted | Invoiced | **Available** |
|---:|---:|---:|---:|---:|

Rules:

- The available figure is the largest, bolder and coloured by status, but the status is also written as text.
- Negative available is shown in full, never clipped, with "Over-utilised by X" beneath.
- Every component has an information icon with its one-line definition (§6).
- Unmapped amounts appear as a separate line, "Not attributed to an item: X", not inside any component.
- Each component opens its source list (§5).

## 3. Item table

One row per SR item.

| Column | Format | Notes |
|---|---|---|
| SION | text | SION norm of the item |
| Item | text | Item name / description; SR number as secondary text |
| HS code | text | Blank cell shows "Unmapped" with the UNMAPPED ITEM status |
| Unit | text | Actual declared unit; "kg" normalised; "mts" shown as is with a warning icon |
| Original qty | number, unit | Tabular numerals, thousands separator, 3 dp |
| Debited qty | number, unit | Net uncovered BOE quantity |
| Allotted qty | number, unit | Outstanding reservation |
| Invoiced qty | number, unit | Sales, full amount; BOE-covered part in the expanded row |
| **Available qty** | number, unit | Bold; negative red with sign |
| Original CIF | number, USD | 2 dp, thousands separator, USD in header |
| Debited CIF | number, USD | |
| Allotted CIF | number, USD | |
| Invoiced CIF | number, USD | Sub-line: "of which BOE-covered X" |
| **Available CIF** | number, USD | Bold; negative red with sign |
| Status | pill | Text + icon (§4) |
| Actions | button | "View movements" opens the item ledger (§5) |

Layout:

- Quantity and CIF are **separate column groups** with their own headers. They are never combined into one figure.
- Sticky first two columns (SION, Item) so horizontal scrolling keeps the identity visible.
- At 1,440 px all columns fit or scroll horizontally inside the table card. The page itself must not overflow.
- At 390 px each item becomes a card: item name and status on top, two blocks (qty, CIF) each listing the five components vertically, then "View movements". No horizontal scrolling on the card view.
- Default sort: status (OVER-UTILISED first), then SION, then item.

Filters: SION; status; unit; "has unmapped amount"; "has cross-item link"; text search on item and HS code.

## 4. Status pills

| Pill | Text | Icon | Colour (secondary cue) |
|---|---|---|---|
| RECONCILED | Reconciled | check | green |
| REVIEW REQUIRED | Review required | warning | amber |
| OVER-UTILISED | Over-utilised | down arrow | red |
| UNMAPPED ITEM | Unmapped item | question | grey |
| OVER-ALLOCATED | Over-allocated | stop | red |
| MISMATCH | Mismatch | cross | red (comparison view only) |

Each pill has a tooltip giving the reason (for example "Unit unverified: mts", "Over-linked BOE excess 100 USD").

## 5. Item movement ledger (expanded row or drawer)

Two ledgers, one for CIF and one for quantity, side by side on wide screens, stacked on narrow screens.

Columns:

| Date | Movement | Reference | Debit | Credit | Running balance | Status |
|---|---|---|---:|---:|---:|---|

Opening row: "Original authorisation" with the licence number, credit = original, running balance = original.

Movement types (labels exactly as written):

- Direct BOE debit
- Sale-covered BOE (shown as a sub-line under its sale; not an extra deduction)
- Sale (invoiced)
- Allotment
- Invoice without BOE
- Reversal
- Cancellation
- Adjustment
- Unmapped or requires review

Each row links to its original record: BOE number to the BOE, sale to the trade, allotment to the allotment. The link opens in place or in a new tab, not a modal over the ledger.

Customer view (below the ledger): per customer, used and remaining entitlement, shown as "Customer used X; remaining Y" and labelled "Customer balance is not the same as the licence balance."

## 6. Plain-language labels and helper text

| Column | Label | Helper text |
|---|---|---|
| Original | Original authorised | "What the licence allows for this item." |
| Debited | Used through BOEs | "Goods cleared at customs and not covered by a sale." |
| Allotted | Reserved for customers | "Promised to customers and not yet cleared." |
| Invoiced | Sold (invoiced) | "Sales on this item. BOEs linked to a sale are already included here." |
| Available | Remaining | "What is left to use." |
| Unmapped | Not attributed to an item | "Recorded against the licence but not matched to a product line." |

Technical terms (SR, CIF FC, RowDetails, allocation ID) appear only in the expanded technical section.

## 7. API contract (canonical)

One response per licence, with an `items` array. Each item carries, for each measure (`cif`, `qty`):

```
original, debited, allotted, invoiced, invoiced_boe_covered, available,
unit, unit_status, currency (cif only), status, flags[], unmapped,
movements: [ { type, source_type, source_id, date, reference, debit, credit, running_balance, status } ]
```

Amounts are decimal strings. The frontend formats them; it does not calculate totals. The licence block is the sum of the items, with `unmapped` reported separately. The response includes `identity_ok` per item.

## 8. Accessibility

- Status uses text and icon, not colour alone.
- Amounts right-aligned, tabular numerals.
- Table headers associated with cells; sticky headers keep their association.
- Every information icon is a labelled button, reachable by keyboard.
- The card view on mobile keeps the same reading order as the table.

## 9. Export consistency

PDF and Excel use the same API response. The Excel export contains one sheet with the item table and one with the movement ledger, using the same labels and the same unit cells. Quantity cells carry their unit. PDF shows the licence summary and the item table. Nothing is recalculated in the export code.

## 10. Not yet implemented

Everything in this specification. Dependencies: the canonical endpoint (not created), the unit decision (O-1), the attribution decision for zero-original items (O-3), and the allotment-and-sale overlap rule (O-4).
