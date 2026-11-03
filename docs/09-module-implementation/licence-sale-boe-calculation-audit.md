# Licence Sale ↔ BOE — Calculation Audit (read-only)

Status: **Complete for the sale/BOE component across all 222 licences.** Read-only. No database row, no calculator and no consumer was changed. Reproducible with `licence-sale-boe-audit.py` (writes `licence-sale-boe-audit.csv`, one row per licence).

## 1. Method

For every licence:

1. **Original:** sum of import-item `cif_fc` and `quantity`.
2. **Sales:** trade SALE lines on the licence's items, grouped by trade. Sold CIF = Σ `cif_fc`; sold quantity = Σ `qty_kg`.
3. **BOE debits:** `bill_of_entry_rowdetails` rows with `transaction_type = 'D'` on the licence's items. Hidden rows are identified with the **engine's own rule** (`get_debit_rows` with and without `include_hidden`), not the raw `invoice_no = 'OTH'` marker. The raw marker is unreliable; the engine's docstring says it collides with about 35–40% of real BOEs.
4. **Links:** a BOE row is linked to a sale when the BOE is a member of that trade (`trade_licensetrade_boes`) **and** the row sits on an item the sale covers. The amount is the current active allocation (`reconciliation_invoiceboeallocation`) if one exists, otherwise the full row amount, which is the engine's current treatment. Links whose row is on a different item are reported as **cross-item** and are not treated as covered.
5. **Rule:** the canonical calculation (`sale_boe_allocation.compute_utilisation`), run for CIF and for quantity independently.
6. **Engine comparison:** sale/BOE utilisation as the engine computes it, `calculate_trade() + calculate_debit()`, which excludes hidden rows. This is compared like-for-like with the rule applied to sales and visible BOEs only. Purchases, the opening balance and allotments are not in this comparison.

## 2. Results

| Measure | Value |
|---|---:|
| Licences audited | 222 |
| Licences with at least one sale | 202 |
| Calculation errors | 0 |
| Licences with a BOE-linked sale | 164 |
| **Licences where rule ≠ engine (sale/BOE, CIF)** | **40** |
| — all in the direction rule > engine | 40 (engine shows less utilisation) |
| — total difference | 3,991,727.07 USD |
| Licences with over-linked sales | 14 (excess 647,104.04 USD) |
| Licences with cross-item links | 28 (all 28 are among the 40 differing) |
| Licences with sales and no BOE link | 38 (sold 12,546,327.93 USD) |
| Licences with duplicate BOE links | 0 |
| Licences where sold CIF > original CIF | 20 |
| Licences where rule available CIF < 0 | 54 (not yet split by purchase treatment; see §5) |
| Total sold CIF | 44,488,452.91 USD |
| Total BOE-linked CIF (audit) | 19,677,191.31 USD |

**Direction.** Every difference runs the same way: the engine shows **less** sale/BOE utilisation than the rule. The engine has no case where it counts more.

## 3. Causes of the differences

### 3.1 Over-linked BOEs (DEF-1)

A BOE linked to a sale for more than the sale amount. The engine excludes the whole BOE row, so the excess disappears. The rule counts it as uncovered.

Licence 2406: sold 195,840.00. Linked BOE rows 544,745.40. Excess 348,905.40.
- Engine sale/BOE utilisation: 195,840.00.
- Rule utilisation: 195,840.00 + 348,905.40 = 544,745.40.
- Difference: **348,905.40**, exactly the excess.

Licence 2415: sold 249,900.00, linked 547,984.55, excess 298,084.55. Difference 298,084.55.

14 licences, 647,104.04 USD of excess in total.

### 3.2 Cross-item links (DEF-2)

A BOE on item X is linked, through trade membership, to a sale whose lines are on item Y. The engine excludes the BOE row (it is a member of the trade); the rule treats it as uncovered because the item does not match.

Licence 2469: BOE 869,858.32 on the licence, linked to a sale of other items. Rule utilisation includes it; engine does not. Difference 869,858.32. Licence 2463: difference 410,183.06.

28 licences. Whether such a link is valid is decision D-2. The rule (§6-4 of the business rules) says it needs an approved mapping. Without one, the rule treats it as uncovered.

### 3.3 Partial allocation ignored (DEF-3)

The membership table cannot express a partial link, so a BOE with a partial allocation record is excluded whole. This is the same mechanism as §3.1. It is listed separately because the allocation table exists and is correct for partial amounts, but only 2 rows exist.

## 4. Other findings

| ID | Finding | Evidence | Impact |
|---|---|---|---|
| DEF-4 | Two link sources of truth (membership and allocation) | `trade_licensetrade_boes` vs `reconciliation_invoiceboeallocation` | The membership table decides the outcome |
| DEF-5 | Licence-level engine does not net sale quantity | No quantity term in `calculate_financial_balance` | Quantity balance cannot be reconciled from the engine |
| DEF-6 | Quantity units not confirmed | Sold `qty_kg` vs BOE `qty` differ by more than 1 unit in **77 of 133** licences with sales. Licence 2583: sold 588,211.6, BOE 245,540.3 | Quantity figures cannot be used until units are confirmed (D-4) |
| DEF-7 | Sold quantity exceeds authorised quantity | 7 licences | Quantity over-utilisation exists in the data and is not flagged |
| DEF-8 | Cancellation cannot be represented | `trade_licensetrade` has no status column | Cancelling a sale removes its links, so the rule's case G cannot be honoured without a model change (D-8) |
| DEF-9 | Unmapped items | 106 licences have at least one item with no HS code | Their BOE and sale rows cannot be matched to a product with confidence |
| INFO-1 | Sales with no BOE yet | 38 licences, 12,546,327.93 USD | Counted by the rule and the engine alike. Correct, but worth monitoring |
| INFO-2 | Rule available CIF < 0 for 54 licences | Rule ignores purchase credit and the opening balance | Not yet a defect. Read only after decision D-6 |
| INFO-3 | No duplicate BOE links | 0 | No double-deduction through the membership table today |

## 5. Caveat on negative balances

The sale/BOE rule, as applied here, ignores purchase credit and the opening balance, because those are outside the rule's scope. Many of the 54 negative results are licences that were purchased and then sold. Their negative values reflect that purchase treatment, not necessarily a sale/BOE error. The purchase question (D-6) must be settled before any of the 54 is reported as over-utilised.

## 6. Worked comparison for licence 2583 (after the hidden-BOE fix)

| Component | Engine | Rule |
|---|---:|---:|
| Net sold | 592,416.60 | 592,416.60 |
| Linked BOE covered by sales | (excluded from debit) | 182,856.60 covered within sales |
| Uncovered BOE (visible) | 0.00 | 0.00 |
| Sale/BOE utilisation | 592,416.60 | 592,416.60 |
| **Difference** | | **0.00** |

The hidden BOE (21,669.77) is outside this comparison because the engine treats it through the opening balance (decision D-5).

## 7. Before and after, on the defect cases

| Licence | Original | Sold | Linked BOE | Engine utilisation (sale/BOE) | Rule utilisation | Rule available (sale/BOE only) |
|---|---:|---:|---:|---:|---:|---:|
| 2406 | — | 195,840.00 | 544,745.40 | 195,840.00 | 544,745.40 | difference 348,905.40 |
| 2583 | 615,999.98 | 592,416.60 | 182,856.60 | 592,416.60 | 592,416.60 | no difference |

Full before/after balances require the purchase decision (D-6) and are not produced here.

## 8. Limits of this audit

- Links are reconstructed from membership and the current active allocation. There is no per-pair confirmation of which BOE amount was intended to cover which sale.
- Cancelled or superseded allocations are not present in the data, so their handling is not tested.
- The quantity comparison uses unverified units.
- Locking behaviour of the membership path was not verified.
- Allotment interactions are excluded.
