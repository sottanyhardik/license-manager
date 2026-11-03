# Licence 2583 — Transaction Reconciliation

Companion to `licence-2583-financial-forensic-audit.md`. All amounts are USD (FC). "Verified" means recomputed from source rows, not taken from a stored or displayed total. Nothing here changes data.

---

## A. Overall CIF reconciliation

| Component | Existing figure (where shown) | Verified figure | Difference | Note |
|---|---:|---:|---:|---|
| Original CIF | 6,15,999.98 (Total CIF) | 615,999.98 | 0.00 | Sum of import items = export line |
| BOE CIF, excluding hidden | 1,82,856.60 (Debited CIF) | 182,856.60 | 0.00 | 7 BOEs |
| BOE CIF, including hidden | 2,04,526.37 (Customs "Total BOE CIF") | 204,526.37 | 21,669.77 vs overview | Hidden BOE 27622 on SR 6. Q-05 |
| Allotment CIF | 0.00 (Allotted CIF) | 0.00 | 0.00 | No allotments |
| Billed CIF without BOE | not shown as a figure; implied by Customs − Balance = 4,09,560.00 | 409,560.00 | 0.00 | Sales 846 (9,560) + 1229 (400,000). **INR basis missing; see Q-03, Q-04** |
| Utilised CIF | 6,15,999.98 − 1,913.61 = 6,14,086.37 (implied) | 614,086.37 | 0.00 | BOE incl. hidden + billed. Under D-1 this is the only combination that reproduces the engine balance |
| Available CIF (engine) | 1,913.61 (Balance CIF) | 1,913.61 | 0.00 | Verified under the S1 assumptions (audit §7) |
| Available CIF (financial ledger) | 4,01,583.40 (Current Balance) | 1,913.61 on the ledger's own rows | **399,669.79** | Canonical opening differs (RC-1, RC-2) |
| Available CIF (customs) | 4,11,473.61 (Available) | not a D-1 figure | **409,560.00** | Omits billed sales by design; equals D-1 minus billed |

**Double-count check.** Sales total 592,416.60. BOE-matched sales 182,856.60 plus unmatched sales 409,560.00 equals 592,416.60. Each sale line is in exactly one bucket. No BOE is counted both as a BOE debit and as a matched sale, because the BOE debit is recorded only through the sale line that matches it.

---

## B. BOE reconciliation

| # | BOE number | BOE date | Customer (linked trade) | Item (SR) | CIF USD | Exch. rate | CIF INR | Linked invoice | Matching status | In BOE CIF (D-1) | In overview "Debited" | Hidden | Reversed / cancelled |
|---:|---|---|---|---|---:|---:|---:|---|---|---|---|---|---|
| 1 | 2779853 | 28-07-2026 | PUSHKAR PAPER AGENCIES | 3 | 12,907.20 | 97.20 | 12,54,579.45 | LGL/2026-27/0054 | Matched (1:1 line 904) | Yes | Yes | No | None recorded |
| 2 | 2779834 | 28-07-2026 | PUSHKAR PAPER AGENCIES | 3 | 9,559.99 | 97.20 | 9,29,231.20 | LGL/2026-27/0055 | Matched (1:1 line 905) | Yes | Yes | No | None recorded |
| 3 | 3174951 | 17-08-2026 | PUSHKAR PAPER AGENCIES | 3 | 36,607.20 | 96.05 | 35,16,121.56 | LGL/2026-27/0066 | Matched at trade level (many-to-many) | Yes | Yes | No | None recorded |
| 4 | 3174955 | 17-08-2026 | PUSHKAR PAPER AGENCIES | 3 | 36,118.32 | 96.05 | 34,69,164.64 | LGL/2026-27/0066 | Matched at trade level | Yes | Yes | No | None recorded |
| 5 | 3174949 | 17-08-2026 | PUSHKAR PAPER AGENCIES | 3 | 30,045.44 | 96.05 | 28,85,864.51 | LGL/2026-27/0066 | Matched at trade level | Yes | Yes | No | None recorded |
| 6 | 9831440 | 12-06-2026 | PUSHKAR PAPER AGENCIES | 4 | 36,811.50 | 96.60 | 35,55,990.90 | LGL/2026-27/0021 | Matched (1:1 line 765) | Yes | Yes | No | None recorded |
| 7 | 9831441 | 12-06-2026 | PUSHKAR PAPER AGENCIES | 4 | 20,806.95 | 96.60 | 20,09,951.37 | LGL/2026-27/0022 | Matched (1:1 line 766) | Yes | Yes | No | None recorded |
| 8 | 9707001 (id 27622) | 05-06-2026 | none (company blank) | 6 | 21,669.77 | 96.60 | 20,93,299.36 | "OTH" (legacy marker) | Hidden (previous owner) | Only if Q-05 = yes | **No** | **Yes** | None recorded |

Totals: all eight rows 204,526.37 · overview-visible seven 182,856.60 · hidden 21,669.77.

Independent sum check: 12,907.20 + 9,559.99 + 36,607.20 + 36,118.32 + 30,045.44 + 36,811.50 + 20,806.95 = 182,856.60 ✓. Adding 21,669.77 gives 204,526.37 ✓.

"Reversed / cancelled" is checked only against the BOE columns present (`invoice_no`, `company_id`, dates, exchange rate). No cancellation or reversal flag was found on those rows. This is not an exhaustive reversal audit.

---

## C. Allotment reconciliation

No allotments exist for licence 2583:

- `allotment_allotmentitems` rows on items 38728–39071 / 38732: 0.
- BOE-to-allotment M2M links for this licence: 0.

Nothing to reconcile. The page's "Allotted CIF 0.00" and "Total allotments 0" are correct.

---

## D. Invoice reconciliation

`license_invoice` (the invoice model) has no row linked to this licence. The licence's customer invoices are **trade sale invoices** (`trade_licensetrade`, direction SALE). That is the relationship used in this reconciliation.

| Invoice | Date | Customer | Invoice total (INR) | Licence line (USD) | Line INR | Linked BOE | Matched BOE CIF (USD) | Unmatched billed (USD) | Reversal / cancellation | In billed-without-BOE |
|---|---|---|---:|---:|---:|---|---:|---:|---|---|
| LGL/2026-27/0021 | 16-06-2026 | PUSHKAR | 3,64,489 | 36,811.50 | 35,55,990.90 | 9831440 | 36,811.50 | 0.00 | None | No |
| LGL/2026-27/0022 | 16-06-2026 | PUSHKAR | 2,22,355 | 20,806.95 | 20,09,951.37 | 9831441 | 20,806.95 | 0.00 | None | No |
| LGL/2026-27/0048 | 25-07-2026 | HIMALAYA INTERTRADE | 44,229 | 9,560.00 | **0.00** | none | 0.00 | **9,560.00** | None | **Yes** |
| LGL/2026-27/0054 | 04-08-2026 | PUSHKAR | 62,729 | 12,907.20 | 12,54,579.45 | 2779853 | 12,907.20 | 0.00 | None | No |
| LGL/2026-27/0055 | 04-08-2026 | PUSHKAR | 46,462 | 9,559.99 | 9,29,231.20 | 2779834 | 9,559.99 | 0.00 | None | No |
| LGL/2026-27/0066 | 18-08-2026 | PUSHKAR | 4,93,557 (shared by 3 lines) | 102,770.96 (3 lines) | 98,71,150.71 | 3174949, 3174951, 3174955 | 102,770.96 | 0.00 | None | No |
| LGL/2026-27/0101 | 27-10-2026 | NEELKANTH IMPEX | 32,76,650 | 400,000.00 | **0.00** | none | 0.00 | **400,000.00** | None | **Yes** |

Purchase invoices on this licence (not sales; not in billed):

| Invoice | Date | From → to | Amount (USD) | INR | Note |
|---|---|---|---:|---:|---|
| GST/0676/26-27 | 05-06-2026 | QUARTERFOLD → LABDHI | 594,000.00 | 5,65,19,100.00 | Consistent direction and rate (95.15) |
| P-NI/2026-27/0001 | 27-10-2026 | **LABDHI → NEELKANTH** (recorded as 881 → 866) | 400,000.00 | 0.00 | Same pair as LGL/0101. Q-02 |

**Duplicate-prevention check.** BOE-matched invoice lines total 182,856.60 and are excluded from billed. Billed = 409,560.00. Total invoiced sales = 592,416.60 = matched + billed. No amount appears in both categories.

**Partial matches.** None at the line level. Invoice 0066 is matched to three BOEs in aggregate (102,770.96 on both sides) but without a per-line allocation. The "Δ $72,725.52" warnings on the ledger compare one line with the sum of the three BOEs, so they are false positives (RC-7).

---

## E. Item-wise reconciliation (SR level)

| SR | Import item | Credit (USD) | Quantity (as stored) | BOE debit (USD) | Billed without BOE (USD) | Purchases on item (USD) | Verified remaining (USD) | Stored `available_value` | Remaining per page |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 3 | 38728 | 469,999.98 | 504,707.32 | 125,238.15 | 409,560.00 (lines 846, 1229) | 994,000.00 (lines 704, 1246) | **−64,798.17** (purchases neutral) | 344,761.83 | 344,761.83 |
| 4 | 38729 | 95,000.00 | 83,505.65 | 57,618.45 | 0.00 | 0 | **37,381.55** | 1,913.61 | — |
| 5 | 38730 | 14,500.00 | 5,339.24 | 0.00 | 0.00 | 0 | **14,500.00** | 1,913.61 | — |
| 6 (no HS) | 39071 | 22,000.00 | 50,000.00 | 21,669.77 (hidden, BOE 27622) | 0.00 | 0 | **330.23** (if Q-05 = yes) | 1,913.61 | 22,000 |
| 8 | 38732 | 14,500.00 | 4,506.32 | 0.00 | 0.00 | 0 | **14,500.00** | 1,913.61 | — |
| **Sum** | | **615,999.98** | | **204,526.37** | **409,560.00** | | **1,913.61** | | |

**Verification.** The verified remaining figures sum to **1,913.61**, which equals the licence Balance CIF. This holds only when the billed sales are attributed to SR 3 (where their lines sit) and the purchases are treated as neutral. Under that attribution the item view and the licence view agree.

**Defects.**

- `available_value` on SR 4, SR 5, SR 6 and SR 8 holds the licence balance (1,913.61), not each item's balance. Only SR 3 holds an item-level value, and that value ignores the billed sales on SR 3 (RC-6).
- The page's SR 3 "actual balance" 344,761.83 is credit minus BOE only. Deducting the billed sales gives −64,798.17, which the page does not show.
- SR 6's 22,000 is shown without the hidden debit. Its verified remaining is 330.23 if the hidden BOE belongs to this item.

**Open attribution questions** (Q-06): purchases 704 and 1246 are both attributed to SR 3, yet the purchase CIF is not part of SR 3's original credit. Attributing purchases to items would produce an item view that does not sum to the licence balance. The attribution rule is not defined in the data.

**Product mapping.** SR 6 has no HS code. Its BOE debit (27622) is correctly on item 39071, so the transaction is kept in every total. The gap is master data (HS code), not a reason to exclude the transaction.

---

## F. Currency summary

| Basis | Lines or rows | Status |
|---|---|---|
| USD on BOEs with an exchange rate | 8 BOE rows | Consistent (`cif_inr / cif_fc` = `exchange_rate`) |
| USD on trade lines with INR | 704, 765, 766, 904, 905, 998, 999, 1000 | Consistent (rate 95.15–97.20) |
| USD on trade lines **without** INR | 846 (9,560), 1229 (400,000), 1246 (400,000) | **Unverified.** Invoice totals imply 4.63 and 8.19 INR per USD |

The 409,560 billed category and the 400,000 purchase therefore have no independently verified USD basis. Their effect on every balance is large (Section 7 of the audit).
