# DFIA Balance — Formulas and Worked Examples

| Field | Value |
|---|---|
| Status | **Draft** — not approved. Depends on BD-01 (see §3). |
| Date | 2026-11-01 |
| Parent | `DFIA_BALANCE_MANAGEMENT_MASTER_SPECIFICATION.md` |

This document gives the canonical formulas and the eight acceptance examples from the brief (Part C1). Each example's arithmetic is checked here. Where the approved decision UD-002 gives a different answer, both results are shown, so the owner can see the difference.

## 1. Formulas

All values are calculated per **licence item**, and separately for three dimensions: quantity, CIF INR and CIF foreign currency.

```
Available Balance = Original Entitlement − Effective Utilisation − Outstanding Reservations
```

- **Effective Utilisation** = direct BOE + linked BOE (for the allocated portion) + invoice value that replaces the corresponding invoiced BOE portion.
- **Outstanding Reservations** = allotment entitlement not yet consumed by an allocated BOE, plus any other explicitly approved reservation category.

Rules that always apply:

- A BOE portion that has been allocated to an allotment converts that reservation into utilisation. It is never counted twice.
- An invoice replaces only its invoiced portion of a BOE. The uninvoiced portion stays at BOE value.
- A direct BOE is never counted as an allotment reservation.

## 2. Worked examples

Original entitlement is the entitlement of one licence item. All figures are in one dimension; the same arithmetic applies to each dimension separately.

### Example 1 — Allotment without BOE

| Item | Value |
|---|---|
| Original entitlement | 100 |
| Allotment | 40 |
| BOE | 0 |
| Outstanding reservation | 40 |
| Effective utilisation | 0 |
| **Canonical available** | 100 − 0 − 40 = **60** |
| UD-002 reading | 100 (the allotment is not deducted), or 40 if "allotted entitlement" means the allotment |

Depends on **BD-01**.

### Example 2 — Direct BOE without allotment

| Item | Value |
|---|---|
| Original entitlement | 100 |
| Allotment | 0 |
| Direct BOE | 50 |
| Effective utilisation | 50 |
| Outstanding reservation | 0 |
| **Canonical available** | 100 − 50 − 0 = **50** |
| UD-002 reading | 50 — same |

No open dependency.

### Example 3 — BOE greater than allotment

| Item | Value |
|---|---|
| Original entitlement | 100 |
| Allotment | 40 |
| Linked BOE | 50 |
| Effective utilisation | 50 (40 from the reservation, 10 from unreserved entitlement) |
| Outstanding reservation | 0 |
| **Canonical available** | 100 − 50 − 0 = **50** |
| UD-002 reading | 50 — same |

The system must not calculate 40 + 50. The 40 reservation is consumed once; only the 10 excess is additional. The 10 excess is subject to BD-02.

### Example 4 — BOE smaller than allotment

| Item | Value |
|---|---|
| Original entitlement | 100 |
| Allotment | 40 |
| BOE allocated against the allotment | 25 |
| Effective utilisation | 25 |
| Outstanding reservation | 15 (40 − 25) |
| **Canonical available** | 100 − 25 − 15 = **60** |
| UD-002 reading | 100 − 25 = **75** (the unconsumed 15 is not deducted) |

Depends on **BD-01**. This is the clearest divergence between the two rules.

### Example 5 — Invoice linked to BOE

| Item | Value |
|---|---|
| Original entitlement | 100 |
| BOE | 50 |
| Invoice against the BOE | 45 |
| Effective utilisation | 45 |
| **Canonical available** | 100 − 45 = **55** |
| UD-002 reading | 100 − 45 (billed) = 55 — same |

The original BOE value of 50 stays on record for audit. It is not deducted as well as the invoice value.

### Example 6 — Partial invoice

| Item | Value |
|---|---|
| Original entitlement | 100 |
| BOE | 50 |
| Invoice against the BOE | 20 |
| Uninvoiced BOE | 30 |
| Effective utilisation | 20 (invoiced) + 30 (uninvoiced) = **50** |
| **Canonical available** | 100 − 50 = **50** |
| UD-002 reading | 30 unbilled + 20 billed = 50 → 50 — same |

The invoice must not replace the whole BOE value when only part is invoiced. This is a gap if an implementation uses the invoice total in place of the BOE total (see the gap analysis).

### Example 7 — Multiple BOEs against one allotment

| Item | Value |
|---|---|
| Original entitlement | 100 |
| Allotment | 60 |
| BOE 1 allocated | 20 |
| BOE 2 allocated | 25 |
| Remaining reservation | 60 − 20 − 25 = 15 |
| Effective utilisation | 20 + 25 = 45 |
| **Canonical available** | 100 − 45 − 15 = **40** |
| UD-002 reading | 100 − 45 = **55** (the unconsumed 15 is not deducted) |

Depends on **BD-01**.

### Example 8 — Cancellation

Stage A (before cancellation):

| Item | Value |
|---|---|
| Original entitlement | 100 |
| Allotment | 40 |
| BOE allocated | 25 |
| Remaining reservation | 15 |
| **Canonical available** | 100 − 25 − 15 = **60** |
| UD-002 reading | 75 |

Stage B (remaining allotment cancelled):

| Item | Value |
|---|---|
| Outstanding reservation | 0 |
| Effective utilisation | 25 |
| **Canonical available** | 100 − 25 = **75** |
| UD-002 reading | 75 — same |

Stage C (BOE validly reversed):

| Item | Value |
|---|---|
| Effective utilisation | 0 |
| Outstanding reservation | 0 |
| **Canonical available** | **100** |
| UD-002 reading | 100 — same |

Every transition must keep its audit trail. A reversal must not erase the original BOE record.

## 3. Summary of divergence

| Example | Canonical | UD-002 reading | Difference | Driver |
|---|---|---|---|---|
| 1 | 60 | 100 (or 40) | yes | Unconsumed allotment reservation |
| 2 | 50 | 50 | no | — |
| 3 | 50 | 50 | no | — |
| 4 | 60 | 75 | yes | Unconsumed reservation of 15 |
| 5 | 55 | 55 | no | — |
| 6 | 50 | 50 | no | — |
| 7 | 40 | 55 | yes | Unconsumed reservation of 15 |
| 8, stage A | 60 | 75 | yes | Unconsumed reservation of 15 |
| 8, stage B | 75 | 75 | no | — |
| 8, stage C | 100 | 100 | no | — |

Every divergence comes from one place: whether an allotment that no BOE has yet consumed reduces the available balance. That is the open question **BD-01**. The owner must answer it before any engine change is designed. The examples here must not be used as tests until BD-01 is resolved, except Examples 2, 3, 5, 6 and 8 stages B and C, which agree under both readings.

## 4. Reading the UD-002 example

UD-002 gives this example: allotted ₹500,000; unbilled BOE ₹100,000; available ₹400,000. Billing the same BOE for ₹100,000 leaves available at ₹400,000.

That example is consistent with the canonical formula only if the ₹500,000 is treated as the licence entitlement, the ₹100,000 BOE is effective utilisation, and the ₹400,000 remainder is **not** a separate reservation. If ₹500,000 is treated as an allotment, the canonical formula would also need the entitlement, which the example does not state. The owner's wording does not settle which reading is meant, so BD-01 covers it.

## 5. Dimensions

| Dimension | Units | Notes |
|---|---|---|
| Quantity | licence unit of measure | Each item has its own unit. Quantities in different units must not be added. Whether quantity is a hard limit is BD-10. |
| CIF INR | ₹ | Exact decimal. |
| CIF foreign currency | licence currency | Never added across currencies. Historical values are not recalculated at a current exchange rate (BD-05). |

## 6. Explainable breakdown

Every balance must be shown as:

```
Original entitlement
− effective BOE and invoice utilisation
− outstanding allotment reservation
= available balance
```

This is required separately for quantity, CIF INR and CIF FC, for each licence item. The breakdown must be produced by the canonical engine, not reconstructed separately by a consumer.

## 7. Acceptance use

- Examples whose result does not depend on an open decision may be used as acceptance tests once the engine is approved.
- Examples that depend on BD-01 must be recorded as `DEPENDS ON BD-01` in the test matrix. They must not be coded as passing or failing until the owner decides.
- The recalculation of any example must be deterministic: running it twice gives the same result.

## 8. Owner's stated formula (answer to BD-01, PROVISIONAL)

Owner's words, 2026-11-01:

> total qty − (allotted qty without BOE − BOE without bill − invoice)

Status: **provisional.** The signs inside the bracket, read as written, give results that contradict the examples, so the sign is a clarification question (BD-01 follow-up). The rule below is the reading that matches every example.

### 8.1 The literal reading fails

Literal: `total − (allotted_wo_BOE − BOE_unbilled − invoice)`. This adds back the BOE and invoice amounts.

| Example | Literal result | Canonical expected |
|---|---|---|
| 2 | 150 | 50 |
| 4 | 110 | 60 |
| 5 | 145 | 55 |
| 7 | 130 | 40 |
| 8 stage B | 125 | 75 |

Results above 100 are impossible on an entitlement of 100. The literal reading cannot be the intended rule.

### 8.2 All terms subtracted

Reading: `available = total − allotted_wo_BOE − BOE_unbilled − invoice`.

| Example | allotted_wo_BOE | BOE_unbilled | invoice | Result | Expected | Match |
|---|---|---|---|---|---|---|
| 1 | 40 | 0 | 0 | 60 | 60 | yes |
| 2 | 0 | 50 | 0 | 50 | 50 | yes |
| 3 | 0 | 50 | 0 | 50 | 50 | yes |
| 4 | 15 | 25 | 0 | 60 | 60 | yes |
| 5 | 0 | 0 | 45 | 55 | 55 | yes |
| 6 | 0 | 30 | 20 | 50 | 50 | yes |
| 7 | 15 | 45 | 0 | 40 | 40 | yes |
| 8 stage A | 15 | 25 | 0 | 60 | 60 | yes |
| 8 stage B | 0 | 25 | 0 | 75 | 75 | yes |
| 8 stage C | 0 | 0 | 0 | 100 | 100 | yes |

Under this reading the formula is the **reservation rule** (BD-01 option A). It is not UD-002 (which gives 75 for Example 4). Here "allotted without BOE" is the unconsumed reservation, "BOE without bill" is the unbilled BOE utilisation, and "invoice" replaces the invoiced BOE portion. Example 3's 10 excess is decided by BD-02; this table assumes the 10 is the unbilled BOE utilisation.

Recorded as UD-005 (provisional) in `execution/user-decisions.md`.
