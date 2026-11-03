# Licence Sale ↔ BOE Linking — Business Rules

Status: **Rule stated and implemented as a pure calculation (`backend/apps/license/services/sale_boe_allocation.py`). Not yet wired into any consumer.** The current engine approximates this rule and differs from it in 40 licences (see the audit). No historical balance has changed.

## 1. Approved rule

1. **A licence sale is a utilisation of the original licence.** Its full CIF (and quantity) reduces the seller's available balance when the sale is recorded, whether or not any BOE is linked.
2. **A BOE linked to a sale is already represented by that sale.** It counts only inside the sold entitlement. It is not deducted a second time.
3. **A BOE, or the part of a BOE, not covered by any sale is an additional utilisation** and reduces the available balance separately.
4. **Over-linking is not lost.** Linked BOE amounts above a sale's amount are reported as OVER-LINKED and counted as uncovered utilisation.
5. **Each dimension is calculated from its own records.** CIF is never used to infer quantity, or the reverse.
6. **Available = Original − Utilised.** No zero floor. Negative values are shown and flagged OVER-UTILISED.

The principle in one line: *a utilisation is counted exactly once.*

## 2. Mutually exclusive components

| Component | Definition |
|---|---|
| Original | Authorised CIF (or quantity) of the licence item |
| Net sold | Sum of all sales on the item. Full amount, regardless of linking |
| Uncovered BOE | BOE amount not allocated to any sale, plus any over-linked excess |
| Outstanding allotment | Active allotment reservation not already represented by a sale or BOE (passed in as an input; allotment mechanics are unchanged by this rule) |
| Other approved adjustments | None are approved by this rule |

Utilised = Net sold + Uncovered BOE + Outstanding allotment.

Equivalent form used by the implementation: Utilised = Σ sold + Σ BOE − Σ covered + allotment, where covered per sale = min(sold, linked).

## 3. Worked examples (pinned by tests)

Original 1,000. Sale 500. The same figures apply to quantity in kg.

| Case | Sale | Linked BOEs | Uncovered BOE | Available | Customer remaining | Test |
|---|---:|---|---:|---:|---:|---|
| A. Sale only | 500 | none | 0 | 500 | 500 | ✓ |
| B. Partial linking | 500 | 40 + 50 + 100 = 190 | 0 | 500 | 310 | ✓ |
| C. Fully linked | 500 | 500 | 0 | 500 | 0 | ✓ |
| D. Plus independent BOE | 500 | 190 | 30 | 470 | 310 | ✓ |
| E. BOE linked after creation | 500 | 220 | 0 | 500 | 280 | ✓ |
| F. BOE unlinked | 500 | 190 | 30 | 470 | 310 | ✓ |
| G. Sale cancelled | 0 | none (links removed) | 220 | 780 | — | ✓ |
| H. Sale reduced to 400 | 400 | 190 | 0 | 600 | 210 | ✓ |
| I. Over-linked (600 linked to 500) | 500 | 600 | 100 (excess) | 400 | 0 | ✓ |

Multi-sale: one BOE of 100 covers 60 of sale A (60) and 40 of sale B (100). Utilised 160, available 840 (test ✓).

Quantity: the same nine cases with kg produce the same balances (tests ✓ for A, B, C, D, and I).

## 4. Customer view

For each sale: sold, linked BOE, remaining customer entitlement = sold − covered.

- Customer remaining entitlement is **not** the seller's licence balance.
- In case B the seller's balance stays 500 even though the customer has 310 left to use.

## 5. Lifecycle rules

- **Link:** a link may be created only if its BOE row is on the same licence item the sale covers (see Open decision D-2), and the BOE's unallocated amount is sufficient. A BOE may never be allocated beyond its own amount across all sales.
- **Unlink:** removing a link returns that amount to uncovered utilisation. Available falls accordingly (case F).
- **Over-link:** creating or leaving a link that exceeds the sale is a warning condition. The excess stays in utilisation. Whether new over-links should be blocked outright is decision D-1.
- **Sale reduction:** the function is deterministic at the sale-aggregate level. It does not choose which BOEs remain covered. A BOE-level choice rule is decision D-3.
- **Sale cancellation:** the sale's reservation is released. Its linked BOEs become uncovered utilisation (case G). A BOE debit is never silently dropped.
- **Reversal:** handled as a sale reduction (case H / over-link).

## 6. What the current engine does (for comparison)

- A SALE line counts its full `cif_fc` (CIF only; quantity is not netted at licence level).
- A BOE linked to a sale through the trade↔BOE membership is excluded **entirely**, even when the sale covers less than the BOE. The excess disappears. This is the source of the 14 over-linked licences.
- A BOE linked through a per-line allocation record is netted at allocation amount. Only two such records exist in production.
- A BOE linked to a sale of a **different** item of the same licence is still excluded, with no check. This is the source of the 28 cross-item licences.
- Hidden previous-owner BOEs are handled through the opening balance, not through the sale rule. See decision D-5.

The gap between the rule and the engine is the work item. The engine is not changed by this document.

## 7. Not decided by this rule

These are listed with options in `licence-sale-boe-open-business-decisions.md`:

- D-1 Over-link policy at entry.
- D-2 Cross-item links.
- D-3 Which BOEs stay covered on sale reduction.
- D-4 Quantity unit basis.
- D-5 Hidden BOEs.
- D-6 Purchase treatment (affects how negative balances are read).
- D-7 Sales with no BOE yet.
- D-8 Cancellation semantics for trades.
- D-9 Single source of link truth.
- D-10 Unmapped items.
