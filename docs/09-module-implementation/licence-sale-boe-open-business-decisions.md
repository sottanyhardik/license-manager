# Licence Sale ↔ BOE — Open Business Decisions

Status: **Awaiting decisions.** Each item below is a business or policy choice that the code and data cannot settle. Items the repository and database **do** settle are answered in `licence-sale-boe-allocation-data-model.md` §2 and are not asked again.

Amounts are USD (FC) unless stated. Balance effects are for the sale/BOE component only.

---

## Answered from evidence (no decision needed)

| Brief question | Answer | Source |
|---|---|---|
| Does a sale reduce the seller's CIF immediately? | Yes, for CIF. Quantity is not netted at licence level. | `calculate_trade()`; data model §2 Q1 |
| Which relation links a BOE to a sale? | Membership (`trade_licensetrade_boes`) for exclusion; allocation (`reconciliation_invoiceboeallocation`) for amount | Data model §2 Q2 |
| Partial allocations? | Supported by the allocation table; unused (2 rows) | Data model §2 Q3 |
| One BOE to several sales? | Supported; no duplicates in the current data | Audit INFO-3 |
| Are allotments and sales separate? | Yes | Data model §2 Q7 |
| Is customer BOE CIF from the actual BOE line? | Yes | Data model §2 Q9 |
| Are CIF and quantity per licence item? | Yes | Data model §2 Q10 |

---

## D-1 — Over-linked BOEs: count them, and block new ones?

**Question.** When BOEs linked to a sale exceed the sale amount, should the excess (a) count as utilisation, and (b) be blocked at entry?

**Current implementation.** The excess disappears from utilisation (DEF-1). Entry is not blocked.

**Evidence.** 14 licences, 647,104.04 excess. Licence 2406: sold 195,840.00, linked 544,745.40, excess 348,905.40 that the engine drops.

**Options.**
- A. Count the excess as utilisation; warn at entry.
- B. Count the excess; block new over-links at entry; existing excess is shown as a warning until resolved.
- C. Keep the current behaviour.

**Example.** Sale 500, BOEs linked 600. Option A and B: utilised 600, available 400. Option C: utilised 500, available 500, with 100 of BOE silently lost.

**Recommendation.** B. It is what the approved rule says (§5-I), and blocking at entry prevents the case recurring.

**Approval required.** Yes.

---

## D-2 — Cross-item links: can a sale of one item cover a BOE of another?

**Question.** Is a BOE on licence item X ever a valid cover for a sale of item Y, within the same licence?

**Current implementation.** The BOE is excluded (engine), so the sale of Y "covers" X's BOE without any check (DEF-2).

**Evidence.** 28 licences. Licence 2469: BOE 869,858.32 on the licence, linked to a sale of other items. Engine excludes it; rule treats it as uncovered.

**Options.**
- A. Not valid. A cross-item link is uncovered utilisation. Entry must reject it.
- B. Valid only with an approved item mapping (for example, two SR lines of the same product). The mapping table is created and approved by the business.
- C. Valid for any item on the same licence (current, unchecked behaviour).

**Example.** Licence 2469: option A reduces available by 869,858.32 relative to the engine. Option C keeps the engine figure.

**Recommendation.** A now. Option B later, if the business confirms specific pairs.

**Approval required.** Yes. This changes figures on 28 licences.

---

## D-3 — When a sale is reduced below its linked BOEs, which BOEs stay covered?

**Question.** If a sale is reduced below the BOE amount linked to it, which BOEs remain covered?

**Current implementation.** Not defined. The engine excludes whole rows regardless.

**Options.**
- A. Aggregate only: the sale covers up to its amount, and the excess is uncovered utilisation. No BOE is chosen. (Implemented.)
- B. Most recent BOEs stay covered first.
- C. Oldest BOEs stay covered first.
- D. Operator chooses per reduction.

**Example.** Sale 500 → 150 with linked 40 + 50 + 100. Option A: covered 150, excess 40. Option B: the BOEs of 100 and 50 are covered (150); the BOE of 40 is uncovered. Option A and B give the same totals; they differ only in which BOE row is shown as uncovered.

**Recommendation.** A for the balance (totals are identical under any option). Choose B or C only if the screen must name a BOE.

**Approval required.** Yes, for the display rule. The totals do not depend on it.

---

## D-4 — Quantity unit basis

**Question.** Which unit and measure is authoritative for quantity, and how do sale `qty_kg` and BOE `rowdetails.qty` relate?

**Current implementation.** Sale quantity is `trade_licensetradeline.qty_kg`. BOE quantity is `bill_of_entry_rowdetails.qty`. Authorised quantity is `license_licenseimportitemsmodel.quantity`. The units of the last two are not confirmed.

**Evidence.** Sold and BOE quantities differ by more than 1 unit in 77 of 133 licences with sales. Licence 2583: sold 588,211.6, BOE 245,540.3. Sold quantity exceeds authorised quantity in 7 licences.

**Options.**
- A. All quantity in kg; BOE and item quantities are kg. Verify the data.
- B. Different units per SION or item; conversion factors are needed.
- C. Quantity is not used for balances until units are confirmed.

**Example.** Licence 2583: if the BOE quantity is kg and the sale quantity is kg, the sales exceed the BOE quantity by about 343,000 kg, and the quantity balance cannot be stated from these records.

**Recommendation.** C now. Confirm A or B with the operations team, with conversion factors where needed.

**Approval required.** Yes.

---

## D-5 — Hidden previous-owner BOEs

**Question.** Should hidden previous-owner BOEs count as utilisation of this licence?

**Current implementation.** The engine excludes hidden rows from debit and deducts them through the opening balance (for licence 2583: 21,669.77). Hidden detection uses the audit-trail rule in `annotate_and_exclude_hidden`.

**Options.**
- A. Count them as utilisation (uncovered BOE).
- B. Informational only; excluded from utilisation.

**Example.** Licence 2583: A gives available 1,913.61; B gives 23,583.38.

**Recommendation.** A, and show them separately as "used before transfer", as set out in the 2583 decision report (Q-05).

**Approval required.** Yes. Same question as 2583 Q-05.

---

## D-6 — Purchase treatment

**Question.** How does a licence purchase affect the holder's available CIF? This is the question already raised as Q-02 for licence 2583.

**Current implementation.** The engine treats purchases as neutral when there is an original credit, and replaces the original with the purchase amount when there is none (`calculate_opening_balance`, rule 2). The canonical ledger replaces the original with the purchase. The rule in this stage ignores purchases.

**Evidence.** 201 licences have purchase credit. 54 licences have negative available CIF under the sale/BOE rule, most of which are purchase-bearing (INFO-2).

**Options.**
- A. Purchase neutral; original retained (rule as applied here).
- B. Purchase replaces the original (canonical ledger).
- C. Purchase adds to the original.

**Recommendation.** Decide before reporting any of the 54 as over-utilised. A is consistent with the approved D-1 formula.

**Approval required.** Yes. Affects the figures on purchase-bearing licences.

---

## D-7 — Sales with no BOE yet

**Question.** A sale with no BOE linked: should it remain counted until a BOE is linked, or be released after a time?

**Current implementation.** Counted, with no release (both engine and rule).

**Evidence.** 38 licences, 12,546,327.93 sold with no BOE.

**Options.**
- A. Counted until cancelled (current).
- B. Counted for a defined period, then flagged for review.

**Recommendation.** A, with a visible "awaiting BOE" status and an age indicator, so that stale sales are reviewed rather than released automatically.

**Approval required.** Yes, if B is preferred.

---

## D-8 — Cancellation semantics for trades

**Question.** How is a cancelled sale represented?

**Current implementation.** `trade_licensetrade` has no status column. Deletion cascades the membership links. No cancellation trail was found.

**Options.**
- A. Add a status (ACTIVE, CANCELLED) and keep the record; links are released but kept as history.
- B. Keep deletion; record cancellations in the audit log only.

**Recommendation.** A. The rule's case G requires the cancelled sale's BOEs to remain as debit, which deletion makes impossible to audit.

**Approval required.** Yes. A model change.

---

## D-9 — Single source of link truth

**Question.** Should the amount-level allocation table become the only link record, with the membership table derived from it?

**Current implementation.** Two sources. Exclusion uses membership; netting uses allocation.

**Options.**
- A. Migrate the 37 membership rows into allocation records (amount = full row amount), enforce a uniqueness constraint, then derive membership.
- B. Keep both, with a consistency check.

**Recommendation.** A, as a separately approved migration with a reconciliation report before and after.

**Approval required.** Yes. A data migration. Nothing has been migrated.

---

## D-10 — Unmapped items

**Question.** Who owns the HS-code master data for the 106 licences with unmapped items, and what should the system do with transactions on them?

**Current implementation.** Transactions are counted; the item shows no product.

**Recommendation.** Count them (never drop them), flag as UNMAPPED ITEM, and assign the mapping to the master-data owner.

**Approval required.** Yes, to confirm the owner.
