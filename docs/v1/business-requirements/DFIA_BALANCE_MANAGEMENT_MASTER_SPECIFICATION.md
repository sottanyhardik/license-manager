# DFIA Balance Management — Master Specification

| Field | Value |
|---|---|
| Document | DFIA Balance Management — Master Specification |
| Version | 0.1 (draft for review) |
| Status | **Draft / Under Review** — not Approved, not Frozen |
| Date | 2026-11-01 |
| Scope | Licence entitlement, allotment reservation, BOE utilisation, invoice utilisation, available balance, and every module that displays or exports them |
| Approval | Not approved. Open decisions are listed in §9 and in `DFIA_BUSINESS_DECISION_REGISTER.md` |
| Related | `DFIA_BALANCE_FORMULAS_AND_EXAMPLES.md`, `DFIA_TRANSACTION_LIFECYCLE.md`, `DFIA_ALLOCATION_RULES.md`, `DFIA_BALANCE_TEST_MATRIX.md`, `DFIA_EXISTING_IMPLEMENTATION_GAP_ANALYSIS.md`, `DFIA_BUSINESS_DECISION_REGISTER.md` |

> **This document is the canonical business source of truth for all DFIA balance calculations. All other system documentation and implementation modules must conform to it.**
>
> Its status is Draft. Nothing in it is frozen yet. Until a rule is marked Approved or Frozen, implementation must not treat it as binding, and existing behaviour must not be changed on the strength of it.

## 1. Purpose and authority

This specification defines how a DFIA licence's entitlement is reduced by allotments, BOEs and invoices, and what the resulting available balance is. It is the single reference for:

- the calculation engine and every module that consumes its results;
- the test matrix that must enforce it;
- the gap analysis of the existing implementation.

It does not change any existing calculation, record or flag. Historical data is not rewritten by adopting this document.

## 2. Architectural principles

**A1. Single source of truth.** There must be exactly one canonical DFIA balance engine. Every consumer (licence master, allotments, BOEs, invoices, dashboard, licence detail, balance ledger, reconciliation, reports, exports, APIs, background jobs, alerts, future automation) obtains its figures from that engine or its approved read-model. No consumer may implement its own formula. The following must have one definition each: available quantity, available CIF INR, available CIF foreign currency, reserved quantity, reserved CIF, actual BOE utilisation, final invoice-based utilisation, remaining licence entitlement.

**A2. Norm independence.** The engine must not depend on a specific SION norm (E1, E5 or future norms). Entitlement is derived from the licence and its authorised item records. Norms may constrain which items are authorised, but they must not introduce a separate balance engine.

## 3. Business model

### 3.1 Licence entitlement (B1)

Each licence carries: licence number, licence date, norm, import validity, original CIF entitlement in INR, original CIF entitlement in foreign currency, foreign currency code, exchange-rate information where applicable, authorised import items, ITC HS codes, item descriptions, authorised quantities, units of measurement, and item-wise CIF entitlement.

- Each licence item has an **independent** balance. Utilisation of one item must never silently consume another item's entitlement.
- The original entitlement and every subsequent transaction must remain in the history. The original value is never overwritten.

### 3.2 Allotment reservation (B2) — subject to BD-01

An allotment is a reservation against licence-item entitlement. It reserves quantity, CIF INR and CIF foreign currency. Creating an allotment reserves immediately; no separate confirmation is required. Cancelling an allotment releases its **remaining** reservation.

An allotment is **not** import utilisation. Whether an unconsumed allotment reduces the available balance is the open rule **BD-01** (see §4.3).

### 3.3 BOE utilisation (B3)

Supported cases: a BOE linked to an allotment; a direct BOE without an allotment; several BOEs against one allotment; partial BOEs; BOEs covering several authorised items; amendments, cancellations and reversals with audit history.

- A BOE is actual import utilisation.
- A **linked** BOE converts the matching allotment reservation into utilisation for the allocated portion. It must not create a second debit for the same portion.
- A **direct** BOE consumes entitlement without any allotment reservation. It must never be counted as an allotment reservation.

### 3.4 Invoice utilisation (B4)

An invoice linked to a BOE replaces the corresponding invoiced portion of the BOE's utilisation. The original BOE values and invoice values are both preserved. An invoice must not create a second debit for the same underlying import. Uninvoiced BOE portions continue to count at BOE value.

Supported: one invoice against one BOE; several invoices against one BOE; partial invoicing; several BOEs linked to one invoice where permitted; amendment; cancellation; reversal; quantity and CIF reconciliation against the BOE.

## 4. Canonical balance formula (Part C)

### 4.1 Calculation level

All calculations occur per **licence item**, independently for three dimensions:

1. Quantity
2. CIF INR
3. CIF foreign currency

### 4.2 Formula

For each dimension:

**Available Balance = Original Entitlement − Effective Utilisation − Outstanding Reservations**

- **Effective Utilisation** = direct BOE utilisation + linked BOE utilisation + invoice utilisation that replaces the corresponding invoiced BOE portion.
- **Outstanding Reservations** = allotment entitlement not yet consumed by an allocated BOE, plus any other explicitly approved reservation category.
- An allotment portion consumed by a BOE is no longer reserved.
- An invoice replaces only its corresponding BOE portion.
- A direct BOE is never an allotment reservation.

### 4.3 Conflict with an approved decision — OPEN (BD-01)

Approved decision **UD-002** (owner, 2026-11-01) states:

> Available balance = allotted entitlement − unbilled BOE utilisation − billed utilisation.

This does not include an "outstanding reservation" term for an allotment that has not yet been consumed by a BOE. Worked comparison, using the figures from the formulas document:

| Case | Canonical formula in §4.2 | UD-002 as worded |
|---|---|---|
| Entitlement 100, allotment 40, no BOE | 100 − 0 − 40 = **60** | Depends on what "allotted entitlement" means; if it means the allotment, 40 − 0 = 40; if it means the licence entitlement, 100 |
| Entitlement 100, allotment 40, BOE allocated 25 | 100 − 25 − 15 = **60** | 100 − 25 = **75** (if the 15 unconsumed reservation is not deducted) |

The two rules diverge whenever an allotment is partly unconsumed. The owner must decide which rule governs. **This specification must not be implemented until BD-01 is resolved.** Under the approval rules, UD-002 must not be silently overwritten, so it stays Approved until the owner reopens it.

The current implementation also differs from §4.2 in places (see the gap analysis). Those differences are recorded as gaps, not as decisions.

## 5. Rule summary

Each rule below refers to its decision record. Status values come from `DFIA_BUSINESS_DECISION_REGISTER.md`.

| Area | Rule | Decision | Status |
|---|---|---|---|
| Available balance formula | §4.2 (reservations included) versus UD-002 | BD-01 | OPEN — critical |
| Allocation when BOE exceeds allotment | Auto-allocate up to the remaining allotment, excess as direct utilisation, subject to licence balance and an audit record | BD-02 | Proposed (recommended) |
| One BOE across several allotments | Allocation order and cap per BOE item | BD-03 | OPEN |
| Partial invoices | Quantity and CIF replacement mechanism; cannot exceed uninvoiced BOE value without an approved amendment | BD-04 | OPEN |
| Foreign currency and INR | No cross-currency addition; historical FC values not recalculated at current rates | BD-05 | Proposed |
| Item and aggregate limits | Limits apply per licence item and per dimension; aggregates cannot hide item over-utilisation | BD-06 | Proposed |
| Editing and cancellation | Effect of each operation on balance; no permanent erasure of financial history | BD-07 | OPEN |
| Negative balance | Block the transaction; name the licence item and dimension; require an authorised correction process | BD-08 | Proposed (recommended) |
| Duplicate prevention | Scope of uniqueness for licence, BOE, invoice numbers; repeated import of the same document | BD-09 | OPEN |
| Quantity as an enforced dimension | Whether quantity is a hard limit and how units are reconciled | BD-10 | OPEN |
| Direct BOE reassignment | Whether a direct BOE may later be linked to an allotment | BD-11 | OPEN |
| Invoice reversal versus amendment | Whether reversal and amendment are distinct ledger events | BD-12 | OPEN |

## 6. Financial integrity requirements (Part F)

The engine must:

1. Use exact decimal arithmetic. No floating point in any financial value.
2. Run every financial change inside a database transaction.
3. Coordinate concurrent allotment and BOE creation against the affected licence items (locking or an equivalent guard).
4. Prevent duplicate allocation, over-allocation and double debit.
5. Keep reversal and correction records auditable.
6. Recalculate deterministically.
7. Be idempotent where an operation may be retried.
8. Keep drafts visibly separate from posted transactions.
9. Provide an explainable breakdown (§7).

## 7. Explainable breakdown (Part F, final requirement)

Every balance must be explainable, separately for quantity, CIF INR and CIF foreign currency:

```
Original entitlement
− effective BOE/invoice utilisation
− outstanding allotment reservation
= available balance
```

A user must be able to see exactly how the current balance was calculated, down to the licence item.

## 8. Change control

Status legend:

- **Draft** — written, not reviewed.
- **Under Review** — submitted for the owner's review.
- **Clarification Required** — the owner's answer is ambiguous; a follow-up is queued.
- **Approved** — the owner has explicitly approved the rule.
- **Frozen** — approved and binding; implementation and tests must enforce it.
- **Superseded** — replaced by a later approved decision, with the link recorded.

Rules:

- A rule becomes **Frozen** only after explicit owner approval.
- Once frozen, implementation must conform, tests must enforce it, and no module may introduce an alternative interpretation.
- A change requires a documented decision, an impact analysis and explicit approval.
- Historical transactions are never silently rewritten.
- Where an approved existing decision conflicts with this specification, the conflict is recorded and resolution is requested. Neither side is overwritten.

## 9. Open decisions requiring the owner

These are not decided by this document. Each has an entry in the decision register.

1. **BD-01** — Does an unconsumed allotment reduce the available balance? (critical; conflicts with UD-002)
2. **BD-02** — Auto-allocation when a BOE exceeds its allotment.
3. **BD-03** — Allocation order when one BOE covers several allotments.
4. **BD-04** — Partial-invoice replacement mechanism.
5. **BD-05** — Foreign currency rules (confirm the no-recalculation principle).
6. **BD-06** — Item-level versus aggregate limits.
7. **BD-07** — Balance effect of edits and cancellations, and what is allowed after downstream transactions.
8. **BD-08** — Negative-balance policy (recommended: block).
9. **BD-09** — Uniqueness scope for licence, BOE and invoice numbers.
10. **BD-10** — Whether quantity is a hard limit, and unit reconciliation.
11. **BD-11** — Reassignment of a direct BOE to an allotment.
12. **BD-12** — Reversal versus amendment as ledger events.

The licence-level Null DFIA threshold (answered in UD-003 as US$200 on the live `balance_cif`) depends on this engine. Its follow-up question Q-017 is still open, and it is separate from this list.

## 10. Verified current-state facts relied on

These were checked against source in this review; the gap analysis gives full references.

- No model is named `DFIA*`. The specification's entity names are logical names. The mapping in §11 is a candidate mapping, to be confirmed by the gap analysis.
- Explicit allocation records exist: `BOEAllotmentAllocation` (`backend/apps/reconciliation/models.py:331`) and `InvoiceBOEAllocation` (`:226`). Both are append-style: rows are not mutated, editing supersedes a row, and reversal sets a status. Both are described as independent consumption tracks.
- `calculate_allotment()` subtracts only the BOE-consumed portion of an allotment from the licence's allotment total (`backend/apps/license/services/balance_calculator.py`, per the `BOEAllotmentAllocation` docstring). Whether the unconsumed remainder is deducted depends on the engine path and is part of the gap analysis.
- The calculator documents a "KNOWN, ACCEPTED TRADE-OFF" for a BOE that debits several licence items (`balance_calculator.py:231-241`). This is an owner-visible rule, recorded as ISS-021.

## 11. Candidate entity mapping (to be verified)

| Specification entity | Candidate existing model(s) | Verification |
|---|---|---|
| DFIALicense | `LicenseDetailsModel` (`apps/license/models/core.py`) | Gap analysis |
| DFIALicenseItem | `LicenseImportItemsModel`, `LicenseExportItemModel` | Gap analysis |
| DFIANorm | SION norm models in `apps/core` (`HeadSIONNorms`, `SionNormClass`) | Gap analysis |
| DFIAAllotment | `AllotmentModel` (`apps/allotment/models/core.py:46`) | Verified name |
| DFIAAllotmentItem | `AllotmentItems` (`apps/allotment/models/core.py:212`) | Verified name |
| DFIABOE | `BillOfEntryModel` (`apps/bill_of_entry/models.py`) | Gap analysis |
| DFIABOEItem | `RowDetails` (`apps/bill_of_entry/models.py`) | Gap analysis |
| DFIABOEAllotmentAllocation | `BOEAllotmentAllocation` (`apps/reconciliation/models.py:331`) | Verified name |
| DFIAInvoice | `Invoice` (`apps/license/models/invoice.py`) | Gap analysis |
| DFIAInvoiceItem | `InvoiceItem` (`apps/license/models/invoice.py`) | Gap analysis |
| DFIABOEInvoiceAllocation | `InvoiceBOEAllocation` (`apps/reconciliation/models.py:226`) | Verified name |
| DFIABalanceLedger | `LicenseBalance` / balance ledger builder | Gap analysis |
| DFIATransactionAudit | Audit models and `ActivityLog` | Gap analysis |

No new model is proposed by this document. Any future model must reuse a canonical one where it exists.
