# Licence Sale ↔ BOE — Allocation Data Model

Status: **Audit of the existing schema. No schema change made.** Answers to the ten schema questions in the brief are backed by the database (`lmanagement`, read-only) and the code.

## 1. Relevant tables

| Table | Role | Key columns | Rows (read-only) |
|---|---|---|---:|
| `trade_licensetrade` | Trade header; `direction` SALE or PURCHASE | `id`, `direction`, `invoice_number`, `invoice_date`, `from_company_id`, `to_company_id`, `subtotal_amount`, `transaction_pair_uuid`, `linked_trade_id` | — |
| `trade_licensetradeline` | Sale or purchase line on one licence item | `id`, `trade_id`, `sr_number_id` (→ licence import item), `cif_fc`, `cif_inr`, `qty_kg`, `counterpart_line_id` | — |
| `trade_licensetrade_boes` | **Trade ↔ BOE membership** (many-to-many, no amount) | `licensetrade_id`, `billofentrymodel_id` | 7 rows for licence 2583 |
| `bill_of_entry_rowdetails` | BOE debit (`D`) and licence credit (`C`) rows per item | `id`, `bill_of_entry_id`, `sr_number_id`, `transaction_type`, `cif_fc`, `cif_inr`, `qty` | 1,503 D rows |
| `reconciliation_invoiceboeallocation` | **Amount-level allocation** of a BOE row to a trade line | `row_details_id`, `trade_line_id`, `allocated_cif_fc`, `allocated_cif_inr`, `allocated_qty`, `status`, `is_current`, `version`, `superseded_by_id`, `notes`, `created_by_id` | **2** |
| `reconciliation_boeallotmentallocation` | Amount-level allocation of a BOE to an allotment item | similar | **0** |
| `allotment_allotmentitems` | Customer allotment reservation per licence item | `cif_fc`, `qty`, `status`, `is_boe`, `allotment_id`, `item_id` | 100 |
| `bill_of_entry_billofentrymodel_allotment` | BOE ↔ allotment membership | — | 37 |
| `license_licenseimportitemsmodel` | Licence item (SR): authorised quantity and CIF | `quantity`, `cif_fc`, `cif_inr`, `hs_code_id`, `license_id` | 2,377 |

## 2. Answers to the ten schema questions

**Q1. Does a sale reduce the seller's available CIF immediately?**
Yes for CIF. `calculate_trade()` sums the full `cif_fc` of every SALE line on the licence's items, regardless of BOE linking (`balance_calculator.py`, `calculate_trade`). The Financial Ledger shows the sale as a debit on the sale date. **For quantity: not established.** The licence-level engine does not net sale quantity. Item-level quantity is computed in `ItemBalanceCalculator`, and I did not verify it against the sale rule.

**Q2. Which relationship represents a BOE linked to a sale?**
Two relationships, and the engine uses both:
- `trade_licensetrade_boes` (trade-level membership, no amount) — used for the **all-or-nothing exclusion** of a BOE row.
- `reconciliation_invoiceboeallocation` (line-level, with amount) — used for **partial netting**.
There are two sources of truth for the same fact. Only the membership table is used for exclusion, so it governs the outcome.

**Q3. Does the model allow partial allocations?**
Yes, through `reconciliation_invoiceboeallocation.allocated_cif_fc` and `allocated_qty`. The membership table cannot express a partial link. In production the allocation table holds **2 rows**, so partial allocation is effectively unused today.

**Q4. Can one BOE link to more than one sale?**
Yes in both tables. There is no database uniqueness constraint on the allocation table; uniqueness relies on application checks under `select_for_update` (`reconciliation/services/allocation_service.py`). In the current data, no BOE row is linked to two sales through the membership table (audit: 0 duplicate links).

**Q5. How are partially covered BOEs handled?**
Through the allocation table, the unmatched remainder of the row stays visible to the debit calculation (`calculate_debit`, with the `allocated == 0` guard). Through the membership table, the whole row is excluded. **The membership table is the one that decides, so partial coverage is treated as full coverage.** This is the source of the over-link defect.

**Q6. What happens to linked BOEs when a sale is cancelled or reversed?**
- `trade_licensetrade` has **no status or cancellation column**. A cancellation can only be a deletion, which removes the membership rows by cascade. No cancellation audit trail was found in the columns inspected. This is not exhaustively verified.
- `reconciliation_invoiceboeallocation.status` and `is_current` exist, so reversal can be represented, but the 2 current rows give no evidence of the values used.
- Result today: cancellation releases the sale and the BOE debit reappears only if its membership is gone. The rule (case G) requires the BOE to remain as uncovered utilisation.

**Q7. Are allotments and sales separate transaction types?**
Yes. Allotments are `allotment_allotmentitems` (reservation to a customer, `status = CREATED`). Sales are `trade_licensetrade` with `direction = SALE`. The engine's allotment term excludes allotments whose parent has any BOE link. No evidence was found that a sale is stored as an allotment.

**Q8. Is the sale amount stored in licence currency, invoice currency, or both?**
Both, per line: `cif_fc` (USD, the licence currency) and `cif_inr`. Invoice totals (`subtotal_amount`) are in INR. Three lines in the 2583 case have `cif_inr = 0`, and their invoice totals do not imply a consistent rate (documented in the 2583 reconciliation).

**Q9. Is customer BOE CIF sourced from the actual BOE line or a manual debit?**
From the actual BOE line: `bill_of_entry_rowdetails.cif_fc` with `transaction_type = 'D'`. There is no manual debit entry in the schema.

**Q10. Are CIF and quantity stored per licence item and SION?**
Per licence item (SR), yes:
- Authorised: `license_licenseimportitemsmodel.quantity`, `cif_fc`.
- Sale: `trade_licensetradeline.sr_number_id`, `cif_fc`, `qty_kg`.
- BOE debit: `bill_of_entry_rowdetails.sr_number_id`, `cif_fc`, `qty`.
- Allotment: `allotment_allotmentitems.item_id`, `cif_fc`, `qty`.
SION is a property of the item (`sion_norm_class`), not a separate allocation key.

**Quantity units.** Sale quantity is `qty_kg`. BOE quantity is `rowdetails.qty`. Authorised quantity is `quantity`. The units of `rowdetails.qty` and `quantity` were not confirmed. For licence 2583, sold qty 588,211.6 and BOE qty 245,540.3 are not comparable without that confirmation (decision D-4).

## 3. Relationships used by the rule

```
licence item (SR) ──< trade line (sale) >── trade (SALE) ──< trade↔BOE membership >── BOE
       │                    │                                                        │
       │                    └──< allocation (amount, status, is_current) >──────────┤
       │                                                                             │
       └──< BOE debit row (RowDetails, cif_fc, qty) >────────────────────────────────┘
```

## 4. Canonical allocation record (proposed, not created)

The existing `reconciliation_invoiceboeallocation` already carries the required fields. The proposal is to make it the **single source of link truth**, so that:

1. Every link has an amount, a quantity, a stable row ID and a status.
2. The membership table is derived from allocations, not used for exclusion.
3. `status` values are fixed (ACTIVE, RELEASED, SUPERSEDED).
4. Changes are versioned (`version`, `superseded_by_id`) rather than overwritten.
5. Uniqueness is enforced per (`row_details_id`, `trade_line_id`) for current rows, by a database constraint rather than application code alone.

Migration of the 37 membership rows into allocation records, and enforcement of the constraint, require approval (decision D-9). Nothing has been migrated.

## 5. Invariants the canonical service must enforce

- Σ allocations per BOE row ≤ the row's `cif_fc` (and `qty`).
- Σ allocations per sale line ≤ the line's amount, or the excess is flagged as OVER-LINKED.
- Allocation is only between rows on the **same licence item**, unless an approved mapping exists (decision D-2).
- No allocation is created against a cancelled or superseded sale or BOE row.
- Each change writes an audit record (who, when, what, previous value).
- Concurrency: link and unlink run inside `transaction.atomic`, with `select_for_update` on the BOE row and the sale line, as the allotment action already does (`allotment/views_actions.py`, lines 1098 and 1192).

## 6. Locking and concurrency (current state)

- Allotment allocation locks the allotment and the licence item (`select_for_update`). This is the live path.
- The BOE and invoice allocation service locks both sides for reconciliation (`reconciliation/services/allocation_service.py`, lines 257–262 and 471–472).
- Trade↔BOE membership changes (the path that drives the exclusion) were not inspected for locking in this stage. This is an open verification item.
