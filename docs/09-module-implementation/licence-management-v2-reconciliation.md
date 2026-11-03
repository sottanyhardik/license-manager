# Licence Management V2 — Reconciliation (Stage 4, read-only)

Purpose: compare the current licence figures with the D-1 reconstruction for every licence **before** any consumer is changed (Part 10). Nothing in the database was written.

Artefacts:
- `licence-management-v2-reconciliation.csv` — one row per licence (222 rows).
- `licence-management-v2-reconcile-d1.py` — the script that produced it. Run from `backend/` with `PYTHONPATH=$PWD` and the project venv: `python licence-management-v2-reconcile-d1.py <out.csv>`.

## 1. Method

For each licence:

| Column | Definition |
|---|---|
| `original_cif_fc` | Sum of import-item `cif_fc` |
| `boe_cif_fc` | Sum of BOE debit rows (`RowDetails` `transaction_type='D'`) on the licence's items |
| `allotment_outstanding_fc` | Per allotment item with `status='CREATED'`: full `cif_fc` if the parent allotment has no BOE link; otherwise `max(0, cif_fc − BOE debit on that item within the linked BOEs)` (D-1 section 3.4) |
| `billed_without_boe_fc` | 0 (no licence relation established, P3) |
| `d1_available_fc` | `original − boe − allotment − billed` (no floor) |
| `list_financial_fc` | `LicenseBalanceCalculator.calculate_financial_balance` (what the list shows) |
| `customs_fc` | `LicenseBalanceCalculator.calculate_balance` (bulk XLSX formula) |
| `purchase_credit_fc`, `trade_debit_fc` | The two components the financial engine adds and subtracts |
| `diff_d1_minus_list` | `d1_available − list_financial` |
| `classification` | First match of: over-utilised under D-1; purchase or trade activity present; linked-allotment residue; other difference; match |

## 2. Results

| Classification | Licences |
|---|---:|
| Purchase or trade activity present | 197 |
| Over-utilised under D-1 | 12 |
| Match | 12 |
| Other difference | 1 |
| **Total** | **222** |

Totals:

- Sum of absolute `d1 − list` differences: **11,128,099.01 FC**.
- Positive allotment residue (clipped per item): **629,911.48 FC**.
- Purchase credit: 201 licences, 51,924,669.68 FC. Trade debit: 202 licences, 44,488,452.91 FC.

### 2.1 Reading the classification

The purchase/trade class is first in precedence, so it hides residue on licences that also have purchases or trades. The classes overlap in practice. The headline is that **D-1 as written disagrees with the list for almost every licence that has purchase or trade activity.** That is precondition P1 in `licence-management-v2-financial-engine.md`.

### 2.2 Over-utilised under D-1

| Licence ID | D-1 available | List shows | Note |
|---:|---:|---:|---|
| 2406 | −126,916.21 | 221,989.19 | List and D-1 disagree in sign |
| 2437 | −111,864.55 | 0.00 | Hidden by floor |
| 2488 | −7,133.81 | 0.00 | Hidden by floor |
| 2496 | −173,214.31 | 6.03 | Near-zero residue shown |
| 2497 | −133,092.05 | 2.01 | Near-zero residue shown |
| 2501 | −343,740.50 | 0.00 | Original CIF is 0.00 (P5) |
| 2510 | −488.99 | 18.19 | |
| 2515 | −30,824.45 | 0.00 | Hidden by floor |
| 2517 | −241,278.40 | 0.00 | Hidden by floor |
| 2558 | −23,945.77 | 174.42 | |
| 2569 | −1,212.24 | 169.45 | |
| 2580 | −4.42 | 56,674.80 | Tiny negative vs large positive |

### 2.3 Worked example — licence 2460 (`0811016774`)

| Component (FC) | Value |
|---|---:|
| Original CIF | 812,619.99 |
| BOE CIF | 387,663.44 |
| Allotment outstanding (incl. 336.60 residue) | 40,032.60 |
| Billed without BOE | 0.00 (not established) |
| **D-1 available** | **384,923.95** |
| List (financial engine) | 323,386.15 |
| Customs engine | 385,260.55 |
| Purchase credit / trade debit | 1,597,470.48 / 1,234,388.33 |

Customs (385,260.55) equals D-1 without the 336.60 residue. The gap between D-1 and the list (61,537.80) comes from purchase credit and trade debit (P1). The 336.60 residue difference is the P2 defect.

## 3. Limits of this reconciliation

- **Item-level matching is approximate.** A BOE's debit on an item is matched to the allotment item that shares that item, not to a verified allocation pair. The residue total needs a per-pair check before correction.
- **Hidden BOEs are not separated.** `calculate_customs_balance` includes hidden BOEs. The reconciliation does not exclude them, so the BOE column may differ from the customs engine where BOEs are hidden.
- **Billed without BOE is zero** for every licence (P3). This understates utilisation wherever invoices exist without BOEs.
- **Original is import-item `cif_fc`.** The engine's credit (`calculate_credit`) was not compared row by row. Licence 2500 shows a difference that suggests the two can diverge (P5).
- **No historical figure was changed.** The "Existing Detail", "Existing Ledger", "Existing PDF" and "Existing Excel" columns from the Part 10 template are not in this CSV yet. Ledger and PDF generation require the authenticated API and were not exercised in this stage.

## 4. Next steps

1. Resolve P1 (purchase/trade treatment in Original). This changes most of the 197 licences, so it comes first.
2. Resolve P2 with a per-pair check of the 56 residue items.
3. Find the invoice-to-licence relation (P3).
4. Investigate P5 licences individually.
5. Only then migrate the list and overview to `financial_position.py`, with the old figures kept as a comparison column.
