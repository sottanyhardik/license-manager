---
paths:
  - "backend/apps/license/**"
  - "backend/apps/allotment/**"
  - "backend/apps/bill_of_entry/**"
  - "backend/apps/trade/**"
  - "backend/apps/reconciliation/**"
  - "backend/apps/core/**"
  - "frontend/src/**/*[Bb]alance*"
  - "frontend/src/**/*[Ll]edger*"
---
# Business-rule protection (License Manager)

## Canonical CIF rule (as stated by the product owner, 2026-11-15)

```
BOE CIF                 = CIF from BOE transactions
ALLOTMENT CIF           = outstanding CIF reserved against allotments, excluding BOEs
BILLED CIF WITHOUT BOE  = invoiced CIF not represented by BOEs, excluding duplicates
UTILISED CIF            = BOE CIF + ALLOTMENT CIF + BILLED CIF WITHOUT BOE
AVAILABLE CIF           = ORIGINAL CIF − UTILISED CIF
```

Invariants: Decimal only (never float; quantize 2dp at the edge, not mid-calculation) ·
no double counting (a CIF amount is in exactly one bucket) · negative balances are
preserved and flagged as over-utilisation · audit trails kept · API contracts and
permissions unchanged · reconciliation workflows untouched unless the task is about them.

## Where it lives in code (`backend/apps/license/services/balance_calculator.py`, `LicenseBalanceCalculator`)

| Rule term | Code |
|---|---|
| ORIGINAL CIF | `calculate_credit()` (sum of export-item `cif_fc`) |
| BOE CIF | `calculate_boe_debit_total()` (raw, non-hidden) / `calculate_debit()` (allocation-aware, excludes BOEs already represented by invoices) |
| ALLOTMENT CIF | `calculate_allotment()` — `cif_fc − min(cif_fc, allocated)` per allotment item via `BOEAllotmentAllocation` |
| BILLED CIF WITHOUT BOE | `calculate_trade()` (SALE lines) paired with `calculate_debit()` exclusions in `_calculate_financial_balance()` |
| AVAILABLE CIF | `calculate_balance()` (customs engine) / `calculate_financial_balance()` (financial engine, used by `LicenseDetailsModel.get_balance_cif`) |

Tests that pin this: `backend/apps/license/tests/test_balance_calculator.py`,
`test_balance_ledger_views.py`, `test_balance_excel_export.py` — run them for any change here.

## DECIDED 2026-11-16 — negative balances are shown, with an over-use flag

Product owner decision: licence-level CIF balances (`calculate_balance*`, `calculate_customs_balance*`,
`calculate_all_components`, `_calculate_financial_balance*`) return the **signed** value, never floored at 0.
Responses carry an additive `is_over_utilised` flag. Callers that use the balance as a **cap** for new
allotments/plans clamp locally to `max(balance, 0)`, so allocation and planning behaviour is unchanged.
"Exhausted" checks are `<= 0`. Item-level availability floors (`ItemBalanceCalculator`) are unchanged.
The two engines (customs vs financial) remain separate by design: the financial engine carries the billed
term; do not merge them without an owner decision.

## Mandatory for any change in these paths

1. Characterization test first (current behaviour pinned) → 2. change → 3. run the
balance test files above + `scripts/dev/quality-gate.sh backend` → 4. `cif-balance-auditor`
review → 5. final report labels it **BUSINESS-RULE CHANGE** (or states "no business-rule change").
