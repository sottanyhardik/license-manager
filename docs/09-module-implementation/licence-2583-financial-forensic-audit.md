# Licence 2583 — Financial Forensic Audit

Licence ID 2583 · Licence number 0311054433 · Importer QUARTERFOLD PRINTABILITIES PRIVATE LIMITED (exporter_id 851) · Purchase status LABDHI GLOBAL · Scheme DFIA · SION norm PP.

Scope: `/licenses/2583/overview` and `/licenses`. Method: read-only database queries (`lmanagement`), read-only execution of the existing calculators and ledger builders, one read-only browser session capturing the page and its API responses. **No data, no calculation logic and no UI code were changed.**

Currency: all CIF amounts in this document are **USD (FC)**. Evidence: the licence export line is `usd`; every BOE and trade line that carries INR implies a USD→INR rate of 95–97 (`cif_inr / cif_fc`, e.g. 97.2 on 28-Jul-2026 BOEs). The brief's ₹ wording is not used for these figures.

---

## 1. Page inspection (Phase 1)

### 1.1 What the overview shows, and where each figure comes from

| On screen | Value | Source (verified) |
|---|---:|---|
| Total CIF | 6,15,999.98 | Sum of import-item `cif_fc` (`license_licenseimportitemsmodel`); equals export line `cif_fc` 615,999.98 |
| Debited CIF | 1,82,856.60 | `calculate_boe_debit_total` with hidden BOEs excluded |
| Allotted CIF | 0.00 | No `allotment_allotmentitems` rows for licence 2583 items |
| Balance CIF | 1,913.61 | `calculate_financial_balance` (engine) = `LicenseBalance.balance_cif` |
| Total BOEs | 7 | BOE rows linked, excluding the hidden BOE |
| Financial Ledger, "Current Balance" | 4,01,583.40 | `balance-ledger` API, `financial_ledger.summary.computed_balance` (canonical path) |
| Customs Ledger, "Available" | 4,11,473.61 | `balance-ledger` API, `customs_ledger.summary.computed_balance` |
| Customs "Total BOE CIF" | 2,04,526.37 | Customs ledger, includes hidden BOE |
| Previous Owner Utilisation | 10,15,669.77 | Ledger row 2 = hidden BOE 21,669.77 + purchase credits 9,94,000.00 |

Network: the overview loads `GET /api/licenses/2583/` (detail), `overview-summary/`, `balance-ledger/` and `replan-status/`. The Financial Ledger, Customs Ledger, reconciliation block and warnings all come from **one** `balance-ledger/` response, so their disagreement is internal to that response, not between separate requests.

### 1.2 Screen defects observed at 1440 px (screenshot `v2/screenshots/2583-overview-1440.png`)

- The tab strip (Overview, BOEs, Allotments, Planning, Items, Invoice Ledger) is partly hidden under the header card.
- The Financial Ledger table is wider than its card; the "CIF INR" column is clipped at the right edge.
- Ledger row 2 ("Previous Owner Utilisation") renders as an oversized empty block, so the row beneath is pushed off-screen.
- The floating action bar (New License, New Allotment, New BOE, Reports) covers the bottom of the ledger.
- KPI labels are internal terms: "Debited CIF", "Allotted CIF", "Balance Engine", "Customs Ledger", "Financial Ledger".

Other viewport captures (1920, 1280, 1024, 390) are saved in `v2/screenshots/`. A line-by-line visual review of each is **not** completed in this stage.

---

## 2. Verified transaction facts (Phase 3)

### 2.1 Credits (authorised CIF)

| Item (SR) | Import item ID | Credit `cif_fc` |
|---|---:|---:|
| SR 3 | 38728 | 469,999.98 |
| SR 4 | 38729 | 95,000.00 |
| SR 5 | 38730 | 14,500.00 |
| SR 6 (no HS code) | 39071 | 22,000.00 |
| SR 8 | 38732 | 14,500.00 |
| **Total** | | **615,999.98** |

### 2.2 BOE debit rows (`bill_of_entry_rowdetails`, `transaction_type = 'D'`)

| BOE number | BOE date | Item (SR) | Exchange rate | CIF USD | CIF INR | Hidden? |
|---|---|---|---:|---:|---:|---|
| 2779853 | 28-07-2026 | SR 3 | 97.20 | 12,907.20 | 12,54,579.45 | No |
| 2779834 | 28-07-2026 | SR 3 | 97.20 | 9,559.99 | 9,29,231.20 | No |
| 3174951 | 17-08-2026 | SR 3 | 96.05 | 36,607.20 | 35,16,121.56 | No |
| 3174955 | 17-08-2026 | SR 3 | 96.05 | 36,118.32 | 34,69,164.64 | No |
| 3174949 | 17-08-2026 | SR 3 | 96.05 | 30,045.44 | 28,85,864.51 | No |
| 9831440 | 12-06-2026 | SR 4 | 96.60 | 36,811.50 | 35,55,990.90 | No |
| 9831441 | 12-06-2026 | SR 4 | 96.60 | 20,806.95 | 20,09,951.37 | No |
| 9707001 (id 27622) | 05-06-2026 | SR 6 | 96.60 | 21,669.77 | 20,93,299.36 | **Yes** (`invoice_no = OTH`, no company) |

Sums: SR 3 = 125,238.15 · SR 4 = 57,618.45 · SR 6 = 21,669.77 · **Total 204,526.37** · **Excluding hidden 182,856.60**.

All eight rows are `is_frozen = true`. Each row's `cif_inr / cif_fc` equals its BOE `exchange_rate`, so the USD and INR figures are internally consistent.

### 2.3 Trade lines on this licence (`trade_licensetradeline` / `trade_licensetrade`)

| Trade ID | Line ID | Direction | Invoice | Date | Parties (from → to) | SR | CIF USD | CIF INR | Linked BOE |
|---:|---:|---|---|---|---|---|---:|---:|---|
| 404 | 704 | PURCHASE | GST/0676/26-27 | 05-06-2026 | 851 → 881 (QUARTERFOLD → LABDHI) | 3 | 594,000.00 | 5,65,19,100.00 | — |
| 429 | 765 | SALE | LGL/2026-27/0021 | 16-06-2026 | 881 → 118 PUSHKAR | 4 | 36,811.50 | 35,55,990.90 | 9831440 |
| 430 | 766 | SALE | LGL/2026-27/0022 | 16-06-2026 | 881 → 118 | 4 | 20,806.95 | 20,09,951.37 | 9831441 |
| 518 | 846 | SALE | LGL/2026-27/0048 | 25-07-2026 | 881 → 62 HIMALAYA | 3 | 9,560.00 | **0.00** | **none** |
| 544 | 904 | SALE | LGL/2026-27/0054 | 04-08-2026 | 881 → 118 | 3 | 12,907.20 | 12,54,579.45 | 2779853 |
| 545 | 905 | SALE | LGL/2026-27/0055 | 04-08-2026 | 881 → 118 | 3 | 9,559.99 | 9,29,231.20 | 2779834 |
| 590 | 998/999/1000 | SALE | LGL/2026-27/0066 | 18-08-2026 | 881 → 118 | 3 | 30,045.44 + 36,607.20 + 36,118.32 | 28,85,864.51 + 35,16,121.56 + 34,69,164.64 | 3174949, 3174951, 3174955 |
| 683 | 1229 | SALE | LGL/2026-27/0101 | 27-10-2026 | 881 → 866 NEELKANTH | 3 | **400,000.00** | **0.00** | **none** |
| 684 | 1246 | PURCHASE | P-NI/2026-27/0001 | 27-10-2026 | **881 → 866** | 3 | **400,000.00** | **0.00** | none |

Invoice-level totals: trade 518 subtotal ₹44,229 (line 9,560 USD); trades 683 and 684 each ₹32,76,650 (line 400,000 USD). Both 683 and 684 carry the same `transaction_pair_uuid` (`c427f039-…`) and counterpart IDs 684↔1229.

### 2.4 Sums

| Category | Lines | Total USD |
|---|---|---:|
| BOE-matched sales | 765, 766, 904, 905, 998, 999, 1000 | **182,856.60** |
| Sales with no BOE link | 846, 1229 | **409,560.00** |
| Total sales | | 592,416.60 |
| Purchases | 704, 1246 | 994,000.00 |

The BOE-matched sales equal the non-hidden BOE total exactly. The unmatched sales equal the "Billed without BOE" figure the page reports.

### 2.5 Allotments and invoices

- Allotments: 0 items, 0 allotment-to-BOE links for this licence.
- Invoice table (`license_invoice`): two invoices exist in the whole database and neither is linked to licence 2583 (they link to BOEs 26974 and 26978). The `reconciliation_invoiceboeallocation` table has two rows, both on other licences' trade rows.
- Conclusion: the "billed without BOE" category for this licence is built from **trade sale lines**, not from `license_invoice`. That is a different relationship from the one D-1 describes ("invoiced CIF not yet represented by a BOE") and must be confirmed by the business (Q-03).

---

## 3. Calculation paths (Phase 3, lineage)

Four balance figures are computed for this licence from the same records:

| # | Figure | Function | Treats hidden BOE | Treats sales | Treats purchases | Opening |
|---|---|---|---|---|---|---|
| A | Balance CIF 1,913.61 (list, overview, ledger rows) | `LicenseBalanceCalculator.calculate_financial_balance` → `_calculate_financial_balance` | Deducted (via opening) | Deducted (`calculate_trade`) | Added, cancelled by opening | `credit − hidden − purchase` = **−3,99,669.79** (`calculate_opening_balance`, rule 1) |
| B | Customs 4,11,473.61 | `calculate_balance` / `calculate_customs_balance` | Deducted (in BOE total) | Ignored | Ignored | `credit` 6,15,999.98 |
| C | Financial Ledger 4,01,583.40 (API final) | `CanonicalLedgerService.build_canonical_ledger_dataset` → `license_running_balance`, copied into the ledger summary by `build_financial_ledger(canonical_data=…)` (`license_balance_ledger_builder.py` ≈ 668–672) | **Ignored** | Deducted | Added as the opening seed | `0` when a valid purchase exists (`canonical_ledger_service.py` ≈ 282) |
| D | Ledger rows, plain builder | `build_financial_ledger(lic)` without canonical data | Deducted | Deducted | As A | As A |

Figure D matches A. Figure C is the only one that differs, and it differs by exactly the opening treatment: **C − A = 401,583.40 − 1,913.61 = 399,669.79**, which is the mismatch the page reports.

---

## 4. Discrepancies reproduced (Phase 2), with verdicts

| Brief item | Observation | Reproduced? | Verdict |
|---|---|---|---|
| Financial Ledger vs Balance Engine: 3,99,669.79 | Yes (C − A) | Yes | **Root cause RC-1.** The canonical service and the engine use different opening rules for purchase-bearing licences |
| Customs vs Balance Engine: 4,09,560.00 | Yes (B − A) | Yes | **Explained.** Equals the billed-without-BOE sales (846 + 1229). Customs omits sales, so it does not reconcile to A without this term |
| Customs vs Financial Ledger: 9,890.21 | Yes (B − C) | Yes | **Explained.** B − C = 409,560.00 − 399,669.79 = 9,890.21 |
| A. Previous Owner Utilisation 10,15,669.77 exceeds Original 6,15,999.98 | Yes | Yes | **Explained, but questionable.** = hidden 21,669.77 + purchases 9,94,000.00. About 98% of it is purchase credit (9,94,000 of 10,15,669.77), and 4,00,000 of that purchase (line 1246, 27-Oct-2026) is dated **after** every sale yet is placed in a "previous owner" row dated 30-May-2026. See Q-01, Q-02 |
| B. Overview Debited 1,82,856.60 vs Customs BOE 2,04,526.37, difference 21,669.77 | Yes | Yes | **Explained.** The 21,669.77 is the hidden BOE 27622 on SR 6. The overview excludes it; the customs total includes it. Two definitions of "BOE CIF" are on one screen. See Q-05 |
| C. SR 3: opening 4,69,999.98, BOE 1,25,238.15, billed 4,09,560, displayed balance 3,44,761.83 | Displayed 3,44,761.83 = 469,999.98 − 125,238.15 | Yes | **Confirmed defect.** The item balance deducts BOEs but not the billed sales that sit on SR 3 (9,560.00 and 400,000.00). Including them gives −64,798.17 for SR 3 alone. The item-level view is not reconciled to the licence total |
| D. SR 6: opening 22,000, BOE 21,669.77, displayed balance 22,000 | Yes | Yes | **Confirmed defect (presentation).** The hidden BOE is excluded from item balances, so SR 6 shows its full 22,000 credit. Its true position is 330.23 once the hidden debit is counted. Whether the hidden debit belongs to this item is a business question (Q-05) |
| E. SR 6 shown as an unmapped product, 50,000 kg, ₹22,000 | Yes: no HS code (`hs_code_id` NULL) on item 39071 | Yes | **Data gap.** The transaction (BOE 27622) is correctly on item 39071 and must not be dropped. The product mapping is missing. See Section 5 |
| F. Ledger entries with blank CIF USD and CIF INR | Yes. Trade rows have `cif_usd = None` and `cif_inr = None` in the builder, and three trade lines have INR = 0 | Yes | **Two issues.** (1) The ledger never populates the currency columns for trade rows, so the UI shows blanks even where data exists. (2) Lines 846, 1229 and 1246 have no INR basis. See Q-04 |

---

## 5. Root causes

**RC-1 — Two opening rules for purchase-bearing licences.** Engine (`calculate_opening_balance`, rule 1): `credit − hidden − purchase`. Canonical (`canonical_ledger_service.py` ≈ 282): `0` when a valid purchase exists, then the purchase amount is added as the running seed. For this licence the engine's opening is −399,669.79 and the canonical opening is 0. The engine's docstring describes rule 1 as "purchase is re-added as a separate term, so it nets to zero"; the canonical service does not do that. **Affects 111 of 222 licences** (see Section 6).

**RC-2 — The ledger total overrides its own rows.** `build_financial_ledger` replaces `computed_balance` with the canonical `license_running_balance` whenever canonical data is supplied (≈ 668–672). The rows on the same page still show running balances ending at 1,913.61. A page can therefore show a total that its own rows do not support, and the summary is labelled "MISMATCH" as a consequence.

**RC-3 — Three definitions of "BOE CIF" on one screen.** Overview "Debited" excludes hidden BOEs (182,856.60). Customs includes them (204,526.37). The engine excludes them from debit but deducts them through opening. The item view excludes them entirely (SR 6 shows 22,000). None of the four is labelled as to which definition it uses.

**RC-4 — Trade lines without a currency basis.** Lines 846, 1229 and 1246 have `cif_inr = 0`, while their invoice totals are in INR (₹44,229 and ₹32,76,650). The implied rates from invoice total to USD line are 4.63 and 8.19, against 95–97 everywhere else. The 409,560 USD billed-without-BOE figure therefore cannot be confirmed as USD CIF from the stored data.

**RC-5 — Trade 684 direction and duplication.** Line 1246 is a PURCHASE with from = 881 and to = 866. Its paired SALE (1229) has the same from and to, the same amount, the same invoice total and the same pair UUID. A purchase should run from seller to buyer. Trade 704 (the other purchase) follows that convention (851 → 881). Two readings are possible: a sale recorded with the wrong direction, or a genuine round trip (we sold 400,000 to NEELKANTH and bought it back). The two readings give different balances (Section 7). The invoice numbers differ (`P-NI/…` and `LGL/…`), so this cannot be settled from the data.

**RC-6 — Item balances copy the licence balance.** `license_licenseimportitemsmodel.available_value` is 1,913.61 on SR 4, SR 5, SR 6 and SR 8, which is the licence balance, not the item's. Only SR 3 holds an item-specific value (344,761.83). The stored field is therefore not an item balance.

**RC-7 — Multi-BOE matching warnings are false positives.** The three BOEs (3174949, 3174951, 3174955) are linked to all three invoice lines of trade 590. Each warning compares one line with the sum of all three BOEs (102,770.96). The three lines total 102,770.96, so the aggregate reconciles and the per-line warnings are a comparison-model artefact. The UI says "requires review" for each line; the true status is "aggregate matches, per-line allocation not recorded".

**RC-8 — Documentation drift.** `calculate_debit`'s docstring says it is not part of the Balance CIF formula. `calculate_financial_balance` uses it. The code is correct for the engine's design, but the docstring misleads future work.

---

## 6. Generalisation to other licences (same architecture)

Read-only comparison of all 222 licences (`licence-management-v2-engine-comparison.csv`):

- **111 licences** have an API ledger final balance that differs from the engine balance (the list figure) by a combined **17,455,579.83 USD** (absolute).
- Of those 111, **95 involve purchases**, which is consistent with RC-1.
- **16 do not involve purchases** and their gap has a different cause that was **not investigated** in this stage. Example: licence 2412, gap 81,029.10. This is an open item.
- Licences with a hidden BOE: 97. Licences with purchase credit: 201.

The fix must therefore be made once, in the canonical layer, and then verified on every licence, not patched for 2583.

---

## 7. What the figure should be — evidence, not yet a decision

Five readings of the same records give five answers. The business owner must choose (see `licence-2583-business-questions.md`).

| Scenario | Assumptions | Available (USD) |
|---|---|---:|
| S1 — current Balance CIF | Original retained; hidden BOE deducted; purchases neutral; line 1246 is a duplicate of 1229 (sale only) | **1,913.61** |
| S2 — current Financial Ledger | Canonical opening = purchase; hidden BOE ignored; line 1246 is a genuine +400,000 credit | 401,583.40 |
| S3 — hidden BOE excluded | As S1 but BOE 27622 not counted | 23,583.38 |
| S4 — round trip | As S1 but line 1246 is a genuine credit that offsets sale 1229 (both real) | 401,913.61 |
| S5 — billed amounts re-stated | As S1 but line 1229 USD replaced by its invoice total at a BOE-consistent rate (≈ ₹32,76,650 ÷ 96 ≈ 34,000 USD, indicative only) | ≈ 3.68 lakh (indicative) |

S1 and S4 differ by exactly 400,000 — the value of line 1246. S5 shows that the billed amount's currency alone can move the result by several lakh. **No scenario is verified as the correct figure until Q-02, Q-03 and Q-04 are answered.**

---

## 8. Changes made in this stage

- `backend/apps/license/tests/test_financial_position.py`: three pure arithmetic tests for licence 2583 (`Licence2583ScenarioTests`), pinning S1, S3 and the customs reconciliation. **36 tests pass.**
- Read-only artefacts in `docs/09-module-implementation/`.
- No financial record, calculator, service or UI component was modified.

## 9. Not verified in this stage

- Visual review of the 1920, 1280, 1024 and 390 px captures.
- The 16 non-purchase licences in Section 6.
- Whether the PDF and Excel exports follow the same paths. They were not run for licence 2583.
- Permissions: the page was viewed with an authorised session.
