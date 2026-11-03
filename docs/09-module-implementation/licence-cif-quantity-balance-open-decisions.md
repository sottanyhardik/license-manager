# Licence Item CIF & Quantity Balance — Open Decisions

Status: **Awaiting decisions.** Each item needs business or policy knowledge that the code and data cannot supply. Items the repository and data settle are answered in `licence-cif-quantity-balance-data-model.md` and are not asked again.

Identifiers O-1 to O-10 are used across all documents in this set. Earlier licence decisions (D-1 to D-10, Q-01 to Q-07) remain in force and are cross-referenced where relevant.

---

## Settled from evidence (no decision needed)

| Question | Answer | Source |
|---|---|---|
| Can the four components be mutually exclusive? | Yes, by construction, with sale-covered BOEs inside Invoiced | Business rules §2, §4 |
| Is Available allowed to go negative? | Yes; shown, flagged, never floored | D-1; business rules §2 |
| Are CIF and quantity computed separately? | Yes; the same function runs twice | Pure calculator |
| Is `kg` / `KG` / `Kg` the same unit? | Yes (label variants of kg) | Unit audit |
| Are stored item columns authoritative? | No: 709 of 2,348 satisfy their own identity | Audit §3.2 |
| Are unmapped amounts deducted? | No; reported separately | Business rules §8 |

---

## O-1 — Quantity unit basis for BOE and allotment quantity

**Question.** BOE quantity (`rowdetails.qty`) and allotment quantity (`allotment_allotmentitems.qty`) have no unit field. Are they kilograms, the same unit as the authorised quantity, and is `trade_licensetradeline.qty_kg` also kilograms?

**Evidence.** Sold and BOE quantities differ by more than one unit in 77 of 133 licences with sales. Licence 2583: sold 588,211.6, BOE 245,540.3. Quantity is therefore not reconciled. Seven licences sell more quantity than they were authorised.

**Options.**
- A. All quantity is kg. Verify and document.
- B. Units differ by item or SION. Document a conversion factor for each.
- C. Quantity balances are shown as "unit unverified" until A or B is confirmed.

**Recommendation.** C now. Operations confirms A, or supplies conversion factors (B).

**Approval:** required.

---

## O-2 — Cross-item cover

**Question.** Can a BOE on licence item X be covered by a sale of a different item Y on the same licence?

**Evidence.** 88 item-side cross-item links. The engine excludes such BOEs entirely; the rule treats them as uncovered. Example: licence 2469, BOE 869,858.32 on the licence, linked through trade membership to a sale of other items.

**Options.**
- A. Not valid. The BOE is an uncovered debit on X. Entry rejects such links.
- B. Valid only with an approved item mapping (for example two SR lines of the same product).
- C. Valid for any item on the licence (current, unchecked).

**Recommendation.** A now; B later for named pairs.

**Approval:** required. Changes figures on 28 licences at licence level.

---

## O-3 — Attribution of purchases and of zero-original items

**Question.** 2,026 items have an authorised CIF of zero. 511 of the 544 negative items are among them. Purchases also sit on SR lines. Which item should carry purchase CIF, and how should sales and BOE debits on zero-original items be attributed?

**Evidence.** Licence 2583: purchases 704 and 1246 and billed sales 846 and 1229 all sit on SR 3, although SR 3's own authorised CIF (469,999.98) does not include them. An item view that attributes everything to the line on which it sits does not sum to the licence balance without an explicit rule.

**Options.**
- A. Licence-level only. Item view shows credit and BOE per item; purchases and zero-original sales are shown at licence level, not per item.
- B. Attribute by the line on which the transaction sits (current data). Zero-original items show negative balances.
- C. Allocate purchase CIF to items pro rata to authorised CIF.

**Recommendation.** A for the item table. Negative item balances on zero-original items are then shown as "attribution review", not "over-utilised".

**Approval:** required. Affects every item table.

---

## O-4 — Allotment and sale on the same item

**Question.** When an item has both an active allotment and a sale, is the sale the fulfilment of that allotment (so the allotment is already represented), or a separate transaction?

**Evidence.** 69 items. No database relation links allotments to sales. Counting both would double-deduct if they are the same entitlement.

**Options.**
- A. Separate by default; flag for review (current proposal).
- B. Same entitlement when the customer and quantity match; requires a link record.
- C. A new link record is created on confirmation (preferred long-term).

**Recommendation.** A now; C when the business confirms the relation.

**Approval:** required.

---

## O-5 — Single source of truth for links, and uniqueness

**Question.** Should the allocation table become the only link record, with a database constraint preventing duplicate current allocations per (BOE row, trade line)?

**Evidence.** Two link sources: membership decides exclusion, allocation holds amounts (2 rows). No database constraint on allocations.

**Options.**
- A. Migrate the 37 membership rows into allocation records, enforce uniqueness, derive membership.
- B. Keep both, add a consistency check.

**Recommendation.** A, as a separate migration with a before-and-after reconciliation.

**Approval:** required. A data migration. Nothing has been migrated.

---

## O-6 — Representing cancellation of a trade

**Question.** How should a cancelled sale be recorded?

**Evidence.** `trade_licensetrade` has no status column. Deletion cascades membership links; no cancellation trail was found.

**Options.**
- A. Add a status (ACTIVE, CANCELLED). Keep the record; release links but keep them as history.
- B. Keep deletion; record cancellations only in the audit log.

**Recommendation.** A. The cancelled sale's BOEs must remain as debit, and deletion makes that auditable only by reconstruction.

**Approval:** required. A model change.

---

## O-7 — Rebuild or retire stored item columns

**Question.** The stored `debited_value`, `allotted_value` and `available_value` on import items are wrong for 1,652 items. Should they be retired (the item view reads the canonical calculation), or rebuilt from the calculation?

**Recommendation.** Retire from the item view immediately once the canonical endpoint exists. Rebuild or drop the columns only after O-3 and O-5 are approved.

**Approval:** required before the columns are dropped or rewritten. Not required to stop displaying them.

---

## O-8 — Hidden previous-owner BOEs

**Question.** Should hidden previous-owner BOEs count as debited utilisation of the current holder's item?

**Evidence.** The engine excludes them from debit and deducts them through the licence opening balance. Hidden detection uses the engine's audit-trail rule. Licence 2583: hidden BOE 21,669.77 on SR 6.

**Options.**
- A. Count as debited (uncovered), shown separately as "used before transfer".
- B. Informational only.

**Recommendation.** A, displayed separately. Same question as 2583 Q-05.

**Decision (approved by user instruction, "Additional Business Rule — Previous-Owner BOE Deduction").** Option A. Previous-owner BOEs are deducted once and reported separately. Ownership comes only from the audit trail. Implemented in Milestone 10 of the build log.

---

## O-9 — Currency conversion for lines without INR

**Question.** For sale and purchase lines without an INR value, which exchange rate and date should be used, and is USD the authoritative currency for every CIF figure?

**Evidence.** Three licence-2583 lines have no INR; their invoice totals imply 4.63 and 8.19 INR per USD. Other lines imply 95–97. USD is the export line currency.

**Options.**
- A. USD authoritative; INR derived from the BOE's own rate for linked BOEs; invoice-date reference rate otherwise.
- B. As A, but unlinked lines without a reference rate are held as unverified.

**Recommendation.** B until the reference-rate source is named.

**Approval:** required (rate source).

---

## O-10 — How to present sale-covered BOEs

**Question.** In the item table, should a BOE covered by a sale appear (a) inside Invoiced with a "of which BOE-covered" sub-amount, or (b) as a separate Debited line that is then offset?

**Evidence.** The brief's example (debited 540, invoiced 100) assumes uncovered BOEs in Debited. The rule forbids counting a covered BOE twice.

**Options.**
- A. Inside Invoiced, with a sub-amount (proposed; the calculation already produces it).
- B. Debited shows all BOEs, and Invoiced shows the net uncovered sale; the arithmetic is the same, but the columns are not the brief's.

**Recommendation.** A. Totals are identical under both; A matches the brief's examples.

**Approval:** required for the column definition, not for the arithmetic.

---

## Summary

| ID | Decision | Blocks | Approval |
|---|---|---|---|
| O-1 | Quantity unit basis | Quantity balances | Yes |
| O-2 | Cross-item cover | Item and licence CIF | Yes |
| O-3 | Attribution of purchases and zero-original items | Item table | Yes |
| O-4 | Allotment and sale overlap | Allotted and Invoiced | Yes |
| O-5 | Single link source and uniqueness | Migration | Yes |
| O-6 | Trade cancellation | Cancellation rule | Yes |
| O-7 | Stored item columns | Item view, DB | Yes, before dropping |
| O-8 | Hidden BOEs | Debited | Yes |
| O-9 | Currency for lines without INR | CIF display | Yes |
| O-10 | Presentation of sale-covered BOEs | Column definition | Yes |

Until O-1 is answered, quantity figures must not be presented as reconciled. Until O-3 and O-4 are answered, item-level over-utilisation must be labelled as requiring review.
