# Licence Item CIF & Quantity Balance — Business Rules

Status: **Rule stated; calculation implemented as pure code** (`backend/apps/license/services/licence_item_balance.py`, built on `sale_boe_allocation.py`). **No consumer uses it yet.** Balances shown in the application are unchanged by this work.

## 1. Scope

Every licence item (SR line, with its SION norm) carries two independent balances: **CIF** and **quantity**. Each is calculated from its own source records. CIF is never derived from quantity, or the reverse.

### 1.1 Original CIF — business definition (ratified)

**Original CIF is the original CIF entitlement granted or endorsed on the import licence** (the licence item's `cif_fc`).

- It is **not** adjusted automatically by purchase credits (licence purchases) or trade debits (licence sales). Those movements are reflected only through the utilisation components below and the sale/purchase records.
- Purchase-credit and trade-debit treatment is an open business question, tracked separately. Until it is formally decided, the production calculator does not change Original CIF for them, and no consumer is migrated between calculation engines on the basis of assumptions.
- The approved D-1 engine `backend/apps/license/services/financial_position.py` remains a separate pure calculator. It is not used by production consumers and must not be wired in without a formal business decision on the same adjustments.

Pinned by test: `backend/apps/license/tests/test_cif_utilisation_formula.py::TestOriginalCifDefinition`.

Module dependency map, verification evidence and open findings: `modernization-dependency-map.md`.

Component mapping to the approved three-part utilisation statement (for CIF, same arithmetic for quantity):

| Approved statement | Production component | Meaning |
|---|---|---|
| BOE CIF | Debited (uncovered BOE + over-linked excess) plus BOE-covered portion through links | Every BOE amount counted once |
| ALLOTMENT CIF | Allotted | Outstanding allotment not represented by a BOE |
| BILLED CIF WITHOUT BOE | Invoiced − BOE-covered | Part of each invoice not represented by any BOE link |

Utilised = BOE CIF + ALLOTMENT CIF + BILLED CIF WITHOUT BOE, and Available = Original CIF − Utilised. Verified numerically in `test_cif_utilisation_formula.py`.

## 2. The four mutually exclusive components

| Component | Meaning | Source records |
|---|---|---|
| **Original** | Authorised CIF or quantity of the item | Licence import item (`cif_fc`, `quantity`) |
| **Debited** | BOE amount not covered by any sale, plus any over-linked excess | BOE debit rows (`bill_of_entry_rowdetails`, `D`), minus the portion covered by sale links |
| **Allotted** | Outstanding customer reservation not represented by a BOE | Allotment items (`status = CREATED`) minus BOE-matched portions |
| **Invoiced** | Sales on the item at full amount. The BOE-covered portion is a sub-amount, not a second deduction | Sale trade lines (`trade_licensetradeline`, `SALE`) and allocation links |
| **Available** | What remains | Original − Debited − Allotted − Invoiced |

**Identity (checked on every result):** Original = Debited + Allotted + Invoiced + Available.

Available may be negative. It is shown, never floored, and flagged OVER-UTILISED.

## 3. Formulas

Quantity:

    Available Qty = Original Qty − Debited Qty − Allotted Qty − Invoiced Qty

CIF:

    Available CIF = Original CIF − Debited CIF − Allotted CIF − Invoiced CIF

Worked example (quantity; CIF follows the same arithmetic on CIF amounts):

| Movement | Qty |
|---|---:|
| Original authorised | 1,000 |
| Debited through BOEs (uncovered) | 540 |
| Allotted to customers (outstanding) | 160 |
| Invoiced (sales, not BOE-covered) | 100 |
| **Available** | **200** |

Pinned by test: `BriefExampleTests` (quantity and CIF).

## 4. How a sale and its BOEs are presented

A sale is an invoiced movement at full value. A BOE linked to that sale is **inside** the invoiced amount and is **not** shown as an additional debit.

Example from the brief: original 1,000; sale 500; linked BOEs 40 + 50 + 100.

| Component | Value | Explanation |
|---|---:|---|
| Invoiced | 500 | Full sale |
| of which BOE-covered | 190 | Shown as sub-amount |
| Debited | 0 | The linked BOEs are not debited again |
| Available | 500 | 1,000 − 500 |

If a further BOE of 30 is not linked to any sale: Debited 30, Available 470.

Customer remaining entitlement = sale − BOE-covered = 310. This is the customer's view. It is not the seller's licence balance.

## 5. Allotments

- An allotment reserves quantity and CIF for a customer.
- Only the **outstanding** reservation is shown. Any part already converted into a BOE is removed from Allotted and appears in Debited.
- For an allotment whose parent has a BOE link, the outstanding amount is `max(0, allotted − BOE debit matched on the item)`. This is the D-1 §3.4 rule. The engine's current treatment (exclude the whole allotment) is a known difference (see the audit).

## 6. Invoices and sales

- Sale lines are the invoice-side movement. They are counted once, in Invoiced.
- A sale that already appears in an allotment must not also appear as an independent Invoiced amount. **Whether this can happen cannot be established from the data today** (69 items have both an allotment and a sale; no link between them exists). It is flagged for review, not assumed.
- An invoice linked to a BOE is not counted again as separate invoiced utilisation. The sale's BOE-covered part is a sub-amount of Invoiced.

## 7. Over-linking, unlinking, cancellation

- **Over-linked:** BOEs linked to a sale above its amount. The excess is Debited and the item is flagged OVER_LINKED.
- **Unlinked:** the BOE returns to Debited. Available falls.
- **Relinked:** Available rises again, provided the link is valid for that item.
- **Sale cancelled:** Invoiced falls. Linked BOEs become Debited. A BOE debit is never silently removed.
- **Allotment cancelled:** Allotted falls. Available rises.

## 8. Unmapped amounts

A transaction that cannot be attributed to a specific item is reported as an **explicit unmapped amount**, outside the four components, and is **never deducted**. Its presence sets status UNMAPPED ITEM. Silent omission is not permitted.

## 9. Units

- Quantity is comparable only within one declared unit.
- `kg`, `KG` and `Kg` are the same unit (verified).
- `mts` is not verified. It may mean tonnes (×1,000 kg) or may be a label for kg. Items with this label are flagged UNIT_UNVERIFIED and cannot be RECONCILED.
- Missing unit: UNIT_UNVERIFIED.
- Mixed units in one total: refused. A documented conversion factor is required.
- BOE quantity and allotment quantity have no unit column. They are assumed to be kg and are **not verified**.

## 10. Statuses

| Status | Rule |
|---|---|
| RECONCILED | Identity holds; no flags; unit verified; no unmapped amount |
| REVIEW REQUIRED | Identity holds, but a flag applies (unit unverified, over-linked, allotment/sale overlap, cross-item link) |
| OVER-UTILISED | Available < 0 |
| UNMAPPED ITEM | Unmapped amount > 0 |
| OVER-ALLOCATED | A BOE row is allocated beyond its own amount. Computation stops; the row is reported |
| MISMATCH | Stored or displayed value differs from the recalculated value (comparison status, not a calculation status) |

A licence is RECONCILED only when every item is RECONCILED and the licence totals match the item totals.

## 11. Relation to earlier rules

- D-1 (approved): Utilised = BOE + Allotment + Billed without BOE; Available = Original − Utilised. This document keeps the same arithmetic and separates Billed-without-BOE into **Invoiced**.
- Sale/BOE rule (earlier stage): preserved exactly. The item calculation calls the same function.
- Nothing in this document changes a previously approved rule. Items the approved rules do not cover are listed in the open decisions.
