# Licence 2583 — Business Decision Report

Status: **Awaiting decisions.** No calculation or data has been changed. Each question below needs business knowledge that the repository and database cannot supply. Amounts are USD (FC). All scenario figures are reproduced in `licence-2583-financial-forensic-audit.md` §7.

Current state, for reference:

| Figure | Value |
|---|---:|
| Balance CIF (list, overview, engine) | 1,913.61 |
| Financial Ledger "Current Balance" (API, canonical) | 4,01,583.40 |
| Customs Ledger "Available" | 4,11,473.61 |

These three cannot all be right. Q-01 to Q-03 decide the first two; Q-07 decides which one the product shows.

---

## Q-01 — Previous-owner utilisation: what belongs in it?

**Exact question.** Which amounts should be classed as previous-owner utilisation for this licence, and on what date should they fall?

**Current implementation.** The ledger's opening row, dated 30-May-2026, shows previous-owner utilisation of 10,15,669.77. That is hidden BOEs (21,669.77) plus purchase credits (9,94,000.00). The purchase credits include 4,00,000 from line 1246, dated 27-Oct-2026, which is after every sale on the licence.

**Transaction evidence.**
- Hidden BOE 27622 (SR 6), 05-06-2026, 21,669.77 USD.
- Purchase 704 (GST/0676/26-27), 05-06-2026, 5,94,000 USD, QUARTERFOLD → LABDHI.
- Purchase 1246 (P-NI/2026-27/0001), 27-10-2026, 4,00,000 USD. See Q-02.

**Amount affected.** 10,15,669.77 displayed. The 4,00,000 dated after the sales is the item most likely to be misplaced.

**Options.**
- A. Hidden BOEs only. Previous-owner utilisation becomes 21,669.77. Purchases are handled as purchase events (Q-02).
- B. Hidden BOEs plus purchases, but each purchase is placed on its own date. The opening stops being negative and the 4,00,000 moves to 27-Oct-2026.
- C. Keep the current single opening row.

**Consequences.** A changes the figure only by the purchase treatment. B corrects the display without changing the total. C keeps a row that exceeds the original CIF, which D-1 does not define.

**ECC recommendation.** B, provided Q-02 confirms that the purchases are genuine acquisitions. Under D-1, "previous owner" is not a utilisation category, so the display should not present it as one.

**Approval required.** Yes.

---

## Q-02 — Does a licence purchase add CIF to the holder, and is line 1246 genuine?

**Exact question.** (a) When a licence is purchased, does the purchased CIF add to the holder's available CIF, replace the original, or do nothing? (b) Is trade 684 (P-NI/2026-27/0001, 4,00,000 USD, recorded as PURCHASE from 881 to 866) a genuine purchase, a sale recorded in the wrong direction, or a round trip?

**Current implementation.**
- Engine: purchases are neutral. The opening is `original − hidden − purchases`, so the purchases cancel. Result 1,913.61.
- Canonical: a valid purchase resets the running balance to zero before adding it. Result 4,01,583.40.
- Neither service is consistent with the other.

**Transaction evidence for line 1246.**
- Its paired SALE (1229, LGL/2026-27/0101) has the same parties, amount, invoice total (₹32,76,650) and pair UUID.
- Both record from = 881 (LABDHI) to 866 (NEELKANTH). Purchase 704, which is consistent with the rest of the data, runs from the seller (851) to the buyer (881).
- The invoice numbers differ (`P-NI/…` and `LGL/…`), so the documents may be separate.
- It has no INR value.

**Amount affected.** 4,00,000 USD. This is the difference between the two most plausible answers: 1,913.61 (line 1246 is a duplicate or mis-recorded sale) and 4,01,913.61 (a genuine round trip where the purchase cancels the sale but both count).

**Options.**
- A. Purchases are neutral; line 1246 is recorded in error, so it is excluded or corrected. Result 1,913.61.
- B. Purchases are real acquisitions; line 1246 is a genuine credit and the sale 1229 stays. Result 4,01,913.61 (engine opening with line 1246 credited).
- C. Purchase replaces the original. Result 4,01,583.40. Requires the original to be treated as the previous owner's.

**Consequences.** A and B differ by 4,00,000 on this licence alone. C ignores the original 6,15,999.98 for a purchased licence, which D-1 does not provide for.

**ECC recommendation.** Obtain the source invoice for P-NI/2026-27/0001 before deciding. Until then, show the licence balance as **REVIEW REQUIRED** with the 4,00,000 line flagged, rather than selecting A, B or C.

**Approval required.** Yes. The invoice must be checked by the business.

---

## Q-03 — Are the billed sales' USD amounts correct?

**Exact question.** For sale lines with no BOE and no INR value (846: 9,560 USD; 1229: 4,00,000 USD), are the USD CIF amounts correct?

**Current implementation.** The stored USD values are used as they are. Their invoice totals are in INR (₹44,229 and ₹32,76,650). Converting those totals at the rate used on the other BOEs (about 96) gives roughly 460 and 34,100 USD, not 9,560 and 4,00,000.

**Transaction evidence.** Every other trade and BOE line with INR implies a rate of 95–97. These three imply 4.63 and 8.19 (audit §2.3, reconciliation §F).

**Amount affected.** Billed without BOE: 4,09,560 USD. If line 1229 were about 34,100 USD, the licence balance would rise from 1,913.61 to roughly 3.68 lakh. This is the largest single uncertainty on the licence.

**Options.**
- A. Accept the stored USD values as correct.
- B. Re-derive USD from the invoice INR total at a stated rate (BOE rate, or the invoice-date reference rate). Needs the rate source (Q-04).
- C. Hold the billed amount as **unverified** until the invoice and its CIF are checked, and show the balance as REVIEW REQUIRED.

**Consequences.** A keeps the current figure with an unknown basis. B may move the balance by several lakh. C is the only option that does not present an unverified amount as confirmed.

**ECC recommendation.** C now; then A or B once the sale invoices are checked.

**Approval required.** Yes.

---

## Q-04 — Which currency and exchange rate apply?

**Exact question.** (a) Confirm that the authoritative currency for every CIF figure is USD (FC), with INR as a derived figure. (b) For a line without INR, which rate and date should be used?

**Current implementation.** CIF is stored in `cif_fc`, labelled `usd` on the export line, and displayed as `$` on the list. BOE and trade INR values use the BOE's `exchange_rate`. Lines without INR have no rate.

**Evidence.** Export line currency `usd`. BOE INR / FC equals the BOE exchange rate (95.15–97.20). The brief's ₹ wording does not match the stored data.

**Amount affected.** Every BOE line is consistent. The exposure is the three lines in Q-03 (4,09,560 and the line 1246 question).

**Options.**
- (a) USD (FC) is authoritative; INR is derived. Recommended.
- (b1) For linked BOEs: the BOE's own rate. Recommended.
- (b2) For unlinked lines: the invoice-date reference rate. Requires the reference rate source.
- (b3) For unlinked lines: the rate on the nearest BOE. Less defensible.

**ECC recommendation.** (a) and (b1). (b2) needs approval of the rate source.

**Approval required.** Yes, for the rate source.

---

## Q-05 — Is the hidden BOE part of this licence's utilisation?

**Exact question.** Should BOE 27622 (21,669.77 USD on SR 6, invoice marker "OTH", no buyer) count as CIF utilised by this licence?

**Current implementation.** Counted in the engine (through opening) and in the customs total (204,526.37). Excluded from the overview's "Debited CIF" (182,856.60) and from the item balance for SR 6 (which shows 22,000).

**Transaction evidence.** The BOE row sits on this licence's item (39071), so the licence is recorded as the source of the CIF. The BOE has no buyer, and its invoice number is the legacy hidden-BOE marker.

**Amount affected.** 21,669.77. Balance with the hidden BOE counted: 1,913.61. Without it: 23,583.38.

**Options.**
- A. Counted as utilisation. The balance is 1,913.61. Consistent with the engine and the customs total.
- B. Informational only. The balance is 23,583.38. Overview "Debited" and the item view would then match.

**Consequences.** Option B makes the overview's Debited figure match the BOE list, but it leaves the customs and engine figures unexplained by 21,669.77. Option A keeps every total consistent.

**ECC recommendation.** A, so long as Q-01 accepts the hidden BOE as previous-owner usage. Show it on the page as "Used before ownership transfer", separately from BOEs used by this holder.

**Approval required.** Yes.

---

## Q-06 — How are purchases and billed sales attributed to SR items?

**Exact question.** Purchases 704 and 1246 and billed sales 846 and 1229 all sit on SR 3, although their CIF is not part of SR 3's authorised credit. What rule should attribute them to items?

**Current implementation.** Attribution is whatever the trade line's `sr_number_id` says. Item balances therefore cannot be reconciled with the licence balance unless billed sales are placed on SR 3 (which they are).

**Amount affected.** Item view for SR 3 shows 3,44,761.83. Including the billed sales gives −64,798.17.

**Options.**
- A. Licence-level only. Item view shows credit and BOE per item; billed and purchases are shown at licence level.
- B. Attribute by line, as recorded.
- C. Allocate pro-rata to each item's credit.

**ECC recommendation.** A until the business defines an allocation rule. B is what the data currently says and would show SR 3 as over-utilised.

**Approval required.** Yes.

---

## Q-07 — Which ledger figure does the product show?

**Exact question.** The engine and the canonical ledger service disagree on the opening for purchase-bearing licences. Which is authoritative for the balance the product shows?

**Current implementation.** The code calls the canonical service "the single authoritative source" (`license_balance_ledger_builder.py`, Phase 4E-D). The list and overview use the engine. The ledger total is overridden by the canonical figure, so the same page shows two totals.

**Evidence.** 111 of 222 licences differ. Combined absolute gap 17,455,579.83 USD. 95 involve purchases (RC-1); 16 are not yet explained (audit §6).

**Options.**
- A. Canonical service is authoritative. The list and overview would show 4,01,583.40 for this licence and change for all 111.
- B. Engine is authoritative. The canonical service's opening rule is corrected to match, and its total is used only where it agrees.
- C. Keep both, and display the mismatch.

**Consequences.** A and B each change the displayed balance on 111 licences. C keeps the inconsistency.

**ECC recommendation.** B. The engine is the rule that matches the approved D-1 formula. A is not in D-1. C is not acceptable for an operational screen.

**Approval required.** Yes. This is a change to figures on 111 licences and must be sized and approved before code changes.

---

## Summary

| ID | Decision | Figure at stake | Approval | Blocks |
|---|---|---:|---|---|
| Q-01 | Previous-owner utilisation | 10,15,669.77 displayed | Yes | Display, opening |
| Q-02 | Purchase treatment and line 1246 | 4,00,000 | Yes, after invoice check | Balance |
| Q-03 | Billed sales' USD amounts | 4,09,560 | Yes | Balance |
| Q-04 | Currency and rate source | all non-USD derived figures | Yes (rate source) | Q-03 |
| Q-05 | Hidden BOE as utilisation | 21,669.77 | Yes | Balance, debited |
| Q-06 | Item attribution | SR 3 item view | Yes | Item view |
| Q-07 | Authoritative ledger figure | 111 licences; 17.46M abs | Yes | Everything above |

Until Q-02, Q-03 and Q-04 are answered, the correct balance for licence 2583 is **not established**. The page should say so.
