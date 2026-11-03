# Licence Management V2 — Canonical Financial Engine

Status: **Stage 3 foundation implemented and unit-tested. Consumers NOT migrated.** Four preconditions (section 5) must be resolved before the list, overview, PDF, Excel and ledger can switch to these figures without changing business results unexpectedly.

Business rule: **D-1 (final, approved). Not reopened here.**

## 1. Implemented

`backend/apps/license/services/financial_position.py` — pure calculation, no database access.

- `calculate_financial_position(original_cif, boe_cif, allotment_cif, billed_without_boe_cif, currency, calculated_at, reconciliation_warnings)` returns a frozen `LicenseFinancialPosition`:
  `original_cif`, `boe_cif`, `allotment_cif`, `billed_without_boe_cif`, `utilised_cif`, `available_cif`, `is_over_utilised`, `over_utilisation_cif`, `utilisation_pct`, `currency`, `calculated_at`, `reconciliation_warnings`.
- Formula: `utilised = BOE + ALLOTMENT + BILLED_WITHOUT_BOE`; `available = ORIGINAL − utilised`.
- No floor at zero. `available_cif` may be negative. `over_utilisation_cif` is the absolute shortfall. `utilisation_pct` is not clamped (above 100 is over-utilised) and is `None` when Original is zero.
- Inputs must be `Decimal`, `int` or `str`. `float` and `bool` raise `TypeError`. NaN, infinity, non-numeric and negative category amounts raise `ValueError`.
- Arithmetic is exact. Outputs are quantised to 2 dp with ROUND_HALF_UP.

Tests: `backend/apps/license/tests/test_financial_position.py` — **33 passed** (`.venv/bin/python -m pytest -o addopts= apps/license/tests/test_financial_position.py`, 0.05 s). Covers D-1 examples 3.2 and 3.3, every category combination, conversion and cancellation invariants (total utilisation unchanged), over-utilisation boundaries, precision, input rejection and metadata.

## 2. Evidence for each D-1 category (read-only, lmanagement)

| Category | Source (verified) | Status |
|---|---|---|
| Original CIF | Sum of `license_licenseimportitemsmodel.cif_fc` (FC) | Used by the reconciliation. Matches the engine's credit for licence 2460. Not verified against `calculate_credit` for all licences (see 5.P1) |
| BOE CIF | `bill_of_entry_rowdetails` rows with `transaction_type='D'` on the licence's items (`sr_number_id`), `cif_fc` | Verified for 2460: 387,663.44. Matches the stored `debited_value` per item. 1,503 D rows exist in total |
| Allotment outstanding | `allotment_allotmentitems` with `status='CREATED'` (all 100 rows) | `is_boe` is `false` on all 100 rows, so it does **not** record BOE conversion |
| BOE conversion of an allotment | `bill_of_entry_billofentrymodel_allotment` M2M (37 rows) | Only relation linking a BOE to an allotment. Used by the engine (`_annotate_allotment_contribution`) |
| Billed CIF without BOE | No licence-level relation found. `license_invoice` links to BOE ids; `reconciliation_invoiceboeallocation` has 2 rows | **Not established.** The reconciliation uses 0 and flags it |

### 2.1 Conversion and the residue defect (D-1 section 3.4)

D-1 says a partial BOE conversion must transfer only the represented amount and **preserve the remaining outstanding reservation**.

The engine does not do this. `balance_calculator._annotate_allotment_contribution` sets `contributed = 0` for every allotment item whose parent allotment has **any** BOE link, regardless of amount. The unrepresented remainder is dropped from every figure.

Example, licence 2460, allotment item 19214 (`cif_fc` 28,106.10), linked to BOE 27826 whose debit on the item is 27,769.50:

- Engine: item contributes 0. Remainder 336.60 counted nowhere.
- D-1: outstanding reservation should be 336.60.

Across the whole table (read-only aggregate, item-level matching): 94 linked allotment items, 4,808,628.02 FC excluded, 4,484,628.89 FC matched by BOE debits. Clipped at zero per item, **629,911.48 FC of positive residue** is currently dropped. Over-debited items (BOE debit above allotment) are not netted against it.

This is a defect against the approved rule, not a new business decision. Fixing it changes figures for the 56 items with residue. It is therefore held behind a reconciliation sign-off (section 5.P2).

## 3. Over-utilisation display

The list and most consumers floor the balance at zero (`balance_calculator.py`, `return balance if balance >= DEC_0 else DEC_0`). D-1 forbids this. The reconciliation found **12 licences** over-utilised under D-1. Five of them display exactly `0.00` on the current list (2437, 2488, 2501, 2515, 2517). Licence 2580 shows 56,674.80 on the list while D-1 gives −4.42. The new engine returns the negative value and the flag. Consumers must not re-floor it.

## 4. Consumers (not yet migrated)

Still on the old engines, by design until section 5 is resolved:

- Licence list and detail: `LicenseBalanceCalculator.calculate_financial_balance`.
- Bulk balance XLSX: `calculate_balance_for_licenses` (customs formula).
- Financial Ledger PDF/XLSX: transaction running balance.
- Dashboard, overview summary: financial components and a dashboard bridge (`dashboard_summary.py`).

No consumer currently calls `financial_position.py`.

## 5. Preconditions before migrating consumers

These are business-rule clarifications or data questions. None is a code choice I can make silently.

**P1 — Original CIF for purchased and traded licences.** D-1 is silent on purchase credit and trade (sale) debits. The current financial engine adds `calculate_purchase_credit` and subtracts `calculate_trade`:

- Purchase credit: 201 licences, 51,924,669.68 FC total.
- Trade debit: 202 licences, 44,488,452.91 FC total.

Licence 2460 alone: purchase credit 1,597,470.48, trade debit 1,234,388.33. Under D-1 without these terms, its available CIF is **384,923.95**. The current list shows **323,386.15**. Question: is Original CIF the effective authorised CIF after purchases and sales, or the import authorisation only?

**P2 — Residue (section 2.1).** Confirm that the 629,911.48 FC of residue should be held as outstanding reservation, as D-1 section 3.4 states, and approve the correction.

**P3 — Billed CIF without BOE.** Identify the invoice-to-licence relation. Until then this category is 0 for every licence and is marked as an open gap.

**P4 — Currency.** Stored CIF is FC (the list displays `$`). D-1 examples are in ₹. A conversion rule (exchange rate per licence, per transaction, or at generation) is undefined. The engine labels amounts with `currency` and does no conversion.

**P5 — Data anomalies.** Licence 2501 has Original CIF 0.00 and BOE debits of 258,142.50. Licence 2500 gives D-1 available 0.00 against a list figure of 122,361.00, which suggests the reconstructed Original differs from the engine's credit. Both need a per-licence investigation before migration.

## 6. Invariants the consumers must keep

1. Each CIF amount appears in exactly one category.
2. A BOE conversion keeps total utilisation unchanged (tested in pure form).
3. Negative available is shown, never floored, and flagged.
4. No float arithmetic on CIF.
5. Only the canonical service computes utilisation. PDF, Excel and frontend only format.

## 7. Traceability (current)

| Requirement | Business rule | Model | Service | API | Component | Test |
|---|---|---|---|---|---|---|
| Utilised = BOE + Allot + Billed | D-1 3.1 | RowDetails, AllotmentItems, M2M | `financial_position.py` | — | — | `test_financial_position.py` (33) |
| Negative shown, not floored | D-1 3.3 | — | `financial_position.py` | — | — | `OverUtilisationTests` |
| No double counting on conversion | D-1 3.4 | M2M, RowDetails | `financial_position.py` (pure) | — | — | `DoubleCountingInvariantTests` |
| Residue preserved on partial conversion | D-1 3.4 | AllotmentItems | **not implemented** (P2) | — | — | — |
| Billed without BOE | D-1 3.1 | not established (P3) | — | — | — | — |
| Canonical figure for every output | D-1 / Part 7.1 | — | **not implemented** (P1, P4) | — | — | — |
