# Licence Item CIF & Quantity Balance — Audit (read-only)

Status: **Complete for the item-level calculation across all 2,348 SR items.** Read-only: no database row, calculator or consumer changed. Reproducible with `licence-cif-quantity-item-audit.py` (run from `backend/` with `PYTHONPATH=$PWD` and the project venv; writes the CSV named as its argument). The CSV is `licence-cif-quantity-item-audit.csv`, one row per item.

## 1. Method

For each SR item:

1. Original: `license_licenseimportitemsmodel.cif_fc` and `quantity`.
2. Sales: SALE trade lines on the item, grouped by trade.
3. BOE debits: `bill_of_entry_rowdetails` `D` rows on the item.
4. Links: trade↔BOE membership where the BOE is on a sale's item. The amount is the current active allocation if one exists, otherwise the full row (the engine's current treatment). A link from a BOE to a trade with no sale line on that item is a **cross-item** link and is not treated as covered.
5. Calculation: the approved sale/BOE function run **separately** for CIF and for quantity.
6. Allotted: outstanding residue, `max(0, allotted − BOE matched within linked BOEs)` for allotments with a BOE link; full amount otherwise.
7. Old view: the stored columns `debited_value`, `allotted_value` and `available_value`.

Hidden previous-owner BOEs are not counted in the item audit's Debited, consistent with the licence-level audit; they are a separate open decision (O-8 in the open decisions).

## 2. Results

| Measure | Value |
|---|---:|
| SR items audited | 2,348 |
| Status RECONCILED | 902 |
| Status REVIEW REQUIRED | 229 |
| Status OVER-UTILISED | 165 (status by precedence; 370 items carry the negative-available flag) |
| Status UNMAPPED ITEM | 1,052 (precedence: unmapped HS code) |
| Status OVER-ALLOCATED | 0 |
| Items with cross-item BOE links | 81 |
| Items with an allotment and a sale on the same item (unverified overlap) | 69 |
| Items with a unit flag | 2 (`mts`) |
| Items with an allotment outstanding | 53 |

Status precedence: OVER-ALLOCATED, then OVER-UTILISED, then UNMAPPED ITEM, then REVIEW REQUIRED, then RECONCILED. An item can carry several flags; the status shows the most severe.

### 2.1 Totals across items (USD / units)

| | Original | Debited | Allotted | Invoiced | Available |
|---|---:|---:|---:|---:|---:|
| CIF | 119,265,123.24 | 23,210,485.42 | 629,911.48 | 44,488,452.91 | see note |
| Quantity | 118,873,509.39 | 11,387,364.14 | 771,049.53 | 17,791,405.68 | see note |

Note: the total available is not reported as one figure because 370 items are negative (sum −27,977,390.56) and 31 quantity items are negative. Summing signed balances hides the over-utilisation. The per-item values are the authoritative figures.

## 3. Findings

### 3.1 Negative balances are mostly an attribution artefact (F-1)

Of the 370 items with negative available CIF:

- **336 items have an authorised CIF of zero.** They receive BOE debits or sales, but carry no original credit. The original credit for these licences sits on other items, or is held by a purchase.
- **34 items have authorised CIF above zero** and are genuine over-utilisation or mismatch cases. Examples: item 37436 (original 333,000; invoiced 333,000; debited 269,060.61) and item 37554 (original 116,844.82; invoiced 116,844.82; debited 111,865.37). Both show a BOE debit not covered by the sale on the same item. These need review.

Consequence: item-level OVER-UTILISED cannot be shown as a per-item fact until the attribution rule is decided (decision O-3). The licence-level figure is the reliable one.

### 3.2 Stored item columns are not reliable (F-2)

- Only 709 of 2,348 items satisfy their own identity using the stored columns.
- Stored `available_value` differs from the recalculated value on 1,599 items. Four items store the licence balance 1,913.61 (licence 2583).
- Stored `debited_value` differs on 488 items.
- Example: item 27317 (original 109,859.77, no debits or sales) stores available 0.00.

The item view must not read these columns. They are retained in the CSV for comparison only.

### 3.3 Cross-item links appear on 81 items (F-3)

A BOE on item X is a member of a trade whose sale lines are on item Y. The BOE is not covered on X, and the sale on Y is not reduced by it. Under the business rule these are uncovered debits on X. The engine excludes them entirely, so the old and new views differ. Decision O-2 needs the business to say whether any cross-item cover is valid.

### 3.4 Allotment and sale on the same item (F-4)

69 items have both an active allotment and a sale. No database relation says whether the sale is the fulfilment of the allotment. If it is, the allotment would be counted twice (once as Allotted, once as Invoiced). Flagged, not adjusted. Decision O-4.

### 3.5 Unmapped HS codes (F-5)

1,176 items have no HS code. This is a master-data gap. It does not change the arithmetic, but it leaves the product name unknown for 1,052 items and sets UNMAPPED ITEM status.

### 3.6 Quantity units (F-6)

| Unit label | Items | Status |
|---|---:|---|
| `kg` | 2,314 | Verified (label) |
| `KG`, `Kg` | 32 | Normalised to kg |
| `mts` | 2 | UNIT_UNVERIFIED. Median CIF per unit 0.32 USD, against 1.54 USD for `kg` items. Probably kg; not proven |

BOE and allotment quantity have no unit. Sold and BOE quantities differ by more than one unit in 77 of 133 licences with sales. Quantity is therefore reported as UNIT_UNVERIFIED throughout. Quantity totals are **not** reconciled. Decision O-1.

Quantity negatives: 31 items. Items where invoiced quantity exceeds the original authorised quantity: 16. Items with quantity activity but zero original: 1.

### 3.7 Old versus new, per item (CIF)

| Change | Items |
|---|---:|
| Debited CIF changes | 488 |
| Available CIF changes | 1,599 |
| Items with a stored available that matches the new value | 749 |

The largest changes are the zero-original items (§3.1), where the stored column records a debit that the new view attributes to the item through a sale, and the stored value does not match either. A per-item list of every change is in the CSV, column `old_available_value` against `available_cif`.

### 3.8 Quantity: what the calculation can and cannot say

- The item-level quantity arithmetic is consistent: 2,348 results satisfy the identity.
- The result is not authoritative until the unit basis for BOE and allotment quantity is confirmed (O-1).

## 4. Worked examples

**Item 37436** (negative, original > 0): original 333,000.00; invoiced 333,000.00; debited 269,060.61; allotted 0; available −269,060.61. The sale covers the full original, and a BOE of 269,060.61 is not linked to it. Under the rule the BOE is debited, so the item is over-utilised. Whether the BOE belongs to another sale or to a purchase must be confirmed before the figure is acted on.

**Item 27317** (stored value wrong): original 109,859.77; no debits, sales or allotments; new available 109,859.77; stored available 0.00.

**Item 27318** (zero original): original 0; invoiced 7,062.51; available −7,062.51. Attribution question, not over-use: the sale has no authorised CIF on this item.

## 5. Limits

- Links are reconstructed from membership and current allocations. Per-pair confirmation is not in the data.
- Allotment residue uses the BOE debit on the same item within linked BOEs. Cross-item BOE matches for allotments are not attempted.
- Hidden BOEs are excluded here and reported in the licence-level audit.
- Purchases are not attributed to items. Their effect on the item view is unknown.
- Quantity figures are unverified (§3.6).
