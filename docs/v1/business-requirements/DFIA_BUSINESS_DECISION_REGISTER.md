# DFIA Balance — Business Decision Register

| Field | Value |
|---|---|
| Status | Draft. Nothing in this register is decided. |
| Date opened | 2026-11-01 |
| Parent | `DFIA_BALANCE_MANAGEMENT_MASTER_SPECIFICATION.md` |
| Owner | Product owner |

Decision status values: PENDING_USER, QUEUED (waiting for an earlier question to be answered), ANSWERED, CONFIRMED, IMPLEMENTATION_REQUIRED, IMPLEMENTED, VERIFIED.

**Asking order.** Questions are asked one at a time. Q-017 (Null DFIA live versus stored) is still open and is asked first. BD-01 is the next question after Q-017 is answered. Nothing in this register is asked as a questionnaire.

## Conflict with an approved decision

| Conflict | Approved decision | New specification | Status |
|---|---|---|---|
| Whether an unconsumed allotment reduces available balance | UD-002: available = allotted entitlement − unbilled BOE − billed utilisation (no reservation term) | Master specification §4.2: outstanding reservation for the unconsumed allotment is deducted | **BD-01, OPEN, critical.** UD-002 stays Approved until the owner reopens it. |

## Summary

| ID | Area | Decision needed | Priority | Status | Recommendation |
|---|---|---|---|---|---|
| BD-01 | Formula | Does an unconsumed allotment reduce available balance? | CRITICAL | ANSWERED — PROVISIONAL (UD-005). Sign follow-up pending. | Owner's formula matches the reservation rule (option A) once every term is subtracted. Literal bracket signs fail the examples. Confirm the signs. |
| BD-02 | Allocation | Automatic allocation when a BOE exceeds its allotment | HIGH | PENDING_USER | Auto-allocate up to the remaining allotment; excess is direct utilisation, subject to licence balance and an audit record. |
| BD-03 | Allocation | Order and cap when one BOE covers several allotments | HIGH | PENDING_USER | Owner to choose the order rule; the cap is the BOE item's unallocated quantity and CIF in each dimension. |
| BD-04 | Invoice | Partial-invoice replacement mechanism | HIGH | PENDING_USER | Replace only the invoiced portion; reject any excess over the uninvoiced BOE value unless an approved amendment applies. |
| BD-05 | Currency | Foreign currency rules | HIGH | PENDING_USER | Never add currencies together; never recalculate historical FC values at a current rate. |
| BD-06 | Limits | Item-level and aggregate limits | HIGH | PENDING_USER | Enforce per licence item and per dimension. Aggregates must not hide item over-utilisation. |
| BD-07 | Lifecycle | Balance effect of edits and cancellations; what is allowed after downstream transactions | HIGH | PENDING_USER | Preserve history for every operation; block edits that would orphan downstream records. |
| BD-08 | Negative balance | Behaviour when a transaction would make a balance negative | HIGH | PENDING_USER | Block; name the licence item and dimension; require an authorised correction. |
| BD-09 | Uniqueness | Scope of uniqueness for licence, BOE and invoice numbers | MEDIUM | PENDING_USER | Owner to confirm scope per number type. Do not assume global uniqueness. |
| BD-10 | Quantity | Whether quantity is a hard limit, and unit reconciliation | MEDIUM | PENDING_USER | Owner to decide; units must match before comparison. |
| BD-11 | Reassignment | Whether a direct BOE may later be linked to an allotment | MEDIUM | PENDING_USER | Owner to decide; any reassignment is an audited event. |
| BD-12 | Ledger | Reversal and amendment as distinct ledger events | MEDIUM | PENDING_USER | Keep them distinct; reversal restores balance, amendment records a change. |

---

## BD-01 — Does an unconsumed allotment reduce available balance?

- **Date opened:** 2026-11-01
- **Priority:** CRITICAL (financial). Must be decided before any engine change is designed.
- **Status:** QUEUED (asked after Q-017).

**Original question.** When an allotment of 40 exists on an entitlement of 100 and no BOE has consumed it, is the available balance 60 (the allotment is reserved) or 100 (the allotment is not deducted until a BOE uses it)?

**Options.**

- A. **Reservation rule (canonical spec).** The unconsumed allotment is deducted. Available = entitlement − utilisation − unconsumed reservation. Example 1 gives 60.
- B. **Utilisation-only rule (UD-002 reading).** Only BOE utilisation is deducted. Available = entitlement − BOE utilisation. Example 1 gives 100, and Example 4 gives 75.
- C. **Hybrid.** Reservations are deducted only for allotments that have a fixed date or validity, or some other owner-defined condition. Not yet specified; the owner would need to define it.

**Recommendation.** Option A matches the business description in the brief ("an allotment reserves entitlement") and prevents over-commitment: without a reservation, two allotments could together exceed the entitlement. Option B matches the approved wording of UD-002, which would need to be reopened and its example confirmed. The recommendation is a recommendation only.

**Affected modules.** The balance engine; the allotment engine's `calculate_allotment` path; the licence list and dashboard; the balance ledger; every export that shows available balance.

**Required changes if A is approved.** UD-002 is reopened and superseded by the approved rule; the engine applies reservations; tests in the matrix for Examples 1, 4, 7 and 8 are enforced.

**Required changes if B is approved.** The canonical formula in the spec is revised to remove the reservation term; the allotment-over-commitment protection must be defined separately (not in the balance).

**Required regression tests.** Examples 1 to 8 as recorded in `DFIA_BALANCE_FORMULAS_AND_EXAMPLES.md`, under whichever option is chosen.

**Related issues.** ISS-019, ISS-020, ISS-021, ISS-022 (balance engine defects that interact with this rule). Q-016 (reconsider UD-002 in light of those defects).

**User's answer (2026-11-01).** "total qty − (alloted qty without boe − boe without bill − invoice ...)". Recorded as UD-005.

**Interpretation (provisional).** The owner's formula matches the reservation rule (option A) if every term is subtracted. The literal bracket signs add back BOE and invoice amounts and fail Examples 2, 4, 5, 7 and 8-stage B. Formula checked in `DFIA_BALANCE_FORMULAS_AND_EXAMPLES.md` §8.

**Follow-up (open).** Confirm the signs: are all of "allotted without BOE", "BOE without bill" and "invoice" subtracted from total quantity (option A), or is a different rule intended (option B)?

---

## BD-02 — Automatic allocation when a BOE exceeds its allotment

- **Priority:** HIGH. **Status:** PENDING_USER.

**Original question.** An allotment is 40 and its linked BOE is 50. Does the system allocate 40 to the allotment and 10 as direct licence utilisation, or must the user allocate the 10 explicitly?

**Current behaviour.** To be confirmed by the gap analysis (allocation service paths in `apps/allotment` and `apps/reconciliation`). Existing allocation records are per BOE row and per allotment item (`BOEAllotmentAllocation`), so the split is recorded when it is made.

**Options.**

- A. **Automatic.** Allocate up to the remaining allotment; the excess is direct utilisation, subject to licence balance and an audit record.
- B. **Explicit.** The user must allocate any excess themselves; the system blocks the BOE until the user does.

**Recommendation.** A, because it matches how a real import consumes entitlement, and the audit record keeps the split visible. B is safer against accidental allocation but adds steps.

**Affected modules.** BOE creation and linking; the allocation service; the balance engine.

**Required tests.** Example 3 (BOE 50 against allotment 40) under the chosen option.

**Related issues.** ISS-022.

**User's answer.** — (pending)

---

## BD-03 — One BOE across several allotments

- **Priority:** HIGH. **Status:** PENDING_USER.

**Original question.** How is one BOE's quantity and CIF divided across several allotments, and how is it prevented from being allocated more than once?

**Options.**

- A. Owner-specified order (for example by allotment date), with each BOE item allocated up to its unallocated amount in each dimension.
- B. User chooses the split explicitly for each allotment, with the system checking the totals.

**Recommendation.** B for transparency, with a system check that the sum of allocations never exceeds the BOE item in any dimension. Order-based automatic splitting (A) is quick but hides the choice.

**Affected modules.** BOE allocation service; `BOEAllotmentAllocation`; the balance engine.

**Required tests.** Multiple allotments for one BOE; sum of allocations equal to the BOE item; over-allocation rejected.

**Related issues.** ISS-023 (multiple SALE trades tagged to one BOE both subtract; plausible, write path not read).

**User's answer.** — (pending)

---

## BD-04 — Partial invoices

- **Priority:** HIGH. **Status:** PENDING_USER.

**Original question.** When an invoice covers part of a BOE, how much of the BOE is replaced, in quantity and in CIF? Can the invoice exceed the uninvoiced BOE value?

**Recommended rule (proposed).** The invoice replaces only the invoiced quantity and CIF of the BOE item. The invoice may not exceed the uninvoiced BOE value in any dimension unless an approved amendment process applies.

**Options.**

- A. Strict: block any invoice above the uninvoiced BOE value.
- B. Permitted excess, recorded as an amendment, with owner approval.

**Recommendation.** A. It keeps invoice and BOE reconciled and avoids a second debit.

**Affected modules.** Invoice creation; `InvoiceBOEAllocation`; the balance engine.

**Required tests.** Example 6 (partial invoice); invoice above uninvoiced value rejected; multiple invoices against one BOE.

**Related issues.** ISS-020 (partly billed BOE drops the unbilled remainder); ISS-032 (legacy-tagged BOE with partial formal allocation debits the remainder twice).

**User's answer.** — (pending)

---

## BD-05 — Foreign currency and INR

- **Priority:** HIGH. **Status:** PENDING_USER.

**Proposed rules.** Do not add different foreign currencies together. Preserve the original licence currency, the original authorised FC amount, the INR entitlement, the BOE FC and INR values, the invoice FC and INR values, and the exchange rate with its source and date where relevant. Never silently recalculate a historical FC value at a current exchange rate.

**Decision needed.** Confirm the no-recalculation principle, and confirm which rate governs each conversion (the rate on the BOE, the invoice, or the licence).

**Affected modules.** Licence entitlement; BOE; invoice; balance engine; exchange-rate usage in reports.

**Required tests.** FC reconciliation per dimension; no cross-currency addition; historical value unchanged after a rate update.

**Related issues.** None recorded yet. Exchange-rate usage in the balance code is to be confirmed by the gap analysis.

**User's answer.** — (pending)

---

## BD-06 — Item-level and aggregate limits

- **Priority:** HIGH. **Status:** PENDING_USER.

**Proposed rule.** Limits apply per licence item and per dimension. Per-allotment and per-BOE limits apply as well. An aggregate balance must never hide item-level over-utilisation.

**Decision needed.** Confirm which limits are hard (blocking) and which are advisory.

**Required tests.** Item over-utilisation with positive aggregate is detected; aggregate and item totals reconcile.

**Related issues.** ISS-024 (AR allotments counted at licence level and excluded at item level); ISS-049 (negative balances floored, hiding over-utilisation).

**User's answer.** — (pending)

---

## BD-07 — Editing and cancellation

- **Priority:** HIGH. **Status:** PENDING_USER.

**Decision needed.** For each operation (editing an allotment, editing a BOE, reassigning a BOE, editing an invoice, cancelling an allotment, cancelling a BOE, cancelling an invoice, reversing a posted transaction), state the balance effect, and which are allowed once downstream transactions exist.

**Proposed rule.** Financial history is never permanently erased. Each change creates a new record and supersedes the old one. Operations that would orphan a downstream transaction are blocked, or require a reversal first.

**Required tests.** Stage A to C of Example 8; edit after allocation; cancel with downstream invoice.

**Related issues.** ISS-030 (a repeat hide erases the original invoice number); ISS-039 (BOE merge discards duplicate debit rows without audit); ISS-040 (deleting a parent cascades through payments and debit rows); ISS-048 (save on a frozen BOE row silently ignored).

**User's answer.** — (pending)

---

## BD-08 — Negative balances

- **Priority:** HIGH. **Status:** PENDING_USER.

**Recommended rule.** Block the transaction. Explain the exact licence item and dimension causing the violation. Allow only an authorised correction process.

**Options.** A. Block (recommended). B. Allow with a flag and an approval record. C. Allow silently (not recommended; conflicts with §6 of the spec).

**Related issues.** ISS-037 (no licence lock, so sibling allocations can exceed the balance); ISS-049 (negative balances floored in display).

**User's answer.** — (pending)

---

## BD-09 — Uniqueness of licence, BOE and invoice numbers

- **Priority:** MEDIUM. **Status:** PENDING_USER.

**Decision needed.** The scope for each number type. Is a BOE number unique across the system, per licence, per company, or per importer? The same for invoice numbers. Are licence numbers globally unique?

**Required tests.** Duplicate number in each scope; repeated import of the same document is idempotent.

**Related issues.** ISS-039 (BOE merge).

**User's answer.** — (pending)

---

## BD-10 — Quantity as an enforced dimension

- **Priority:** MEDIUM. **Status:** PENDING_USER.

**Decision needed.** Is quantity a hard limit that blocks a transaction, or an advisory figure? How are units reconciled when a BOE and a licence item use different units of measure?

**Related issues.** ISS-036 (stored item-quantity formula differs from live); ISS-042 (quantity-mode trade line may debit zero, suspected).

**User's answer.** — (pending)

---

## BD-11 — Reassignment of a direct BOE

- **Priority:** MEDIUM. **Status:** PENDING_USER.

**Decision needed.** May a BOE that was recorded as direct (no allotment) later be linked to an allotment? If yes, what happens to its prior utilisation, and is the reassignment an audited event?

**Related issues.** Not yet recorded. To be checked by the gap analysis.

**User's answer.** — (pending)

---

## BD-12 — Reversal versus amendment

- **Priority:** MEDIUM. **Status:** PENDING_USER.

**Proposed rule.** Reversal and amendment are distinct ledger events. A reversal restores the balance and keeps the original record. An amendment records a change to values and keeps both versions.

**Decision needed.** Confirm the distinction and whether a reversal requires an authorised user.

**Related issues.** ISS-030; ISS-032.

**User's answer.** — (pending)

---

## Open decisions outside this register

- **Q-017** — Null DFIA threshold applied to the live balance or the stored flag (asked, pending).
- **Q-016** — Whether to reconsider UD-002 given ISS-019 to ISS-021 (queued). Closely related to BD-01.
- **UD-003 and UD-004** — Null DFIA threshold of US$200 on `balance_cif` (recorded as answered; live versus stored follow-up is Q-017).
