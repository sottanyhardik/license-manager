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
| AVAILABLE CIF | `calculate_financial_balance()` — canonical (OD-02), SIGNED (OD-01), used by `LicenseDetailsModel.get_balance_cif`. Customs engine `calculate_balance()` is a separate customs figure. Planning capacity = `planning_tolerances.plannable_capacity_cif(balance)` (never negative) |

Tests that pin this: `backend/apps/license/tests/test_balance_calculator.py`,
`test_balance_ledger_views.py`, `test_balance_excel_export.py` — run them for any change here.

## Approved decisions (owner, 2026-11-15) — binding

- **OD-01:** negative Available CIF is preserved end-to-end (engine, serializers, React, Excel, PDF) and flagged with
  `is_over_utilised`. The historical floor-at-0 is a defect being removed; never re-introduce or re-clamp.
- **OD-02:** `calculate_financial_balance` is THE Available CIF. The customs engine (`calculate_balance`) is exposed
  under its own name `customs_available_cif`; never label it "Available CIF".
- **OD-03 / OD-10:** the trade-only licence-wide running balance (`trade_running_balance`) excludes COMMISSION and is
  never shown as Available CIF.
- Still OPEN (do not change): outstanding-allotment AR/AT semantics (OD-12), item qty (OD-13), commission in other
  calculations (OD-14), trade rounding/profit/thresholds (OD-15), invoice rounding (OD-11).

## Mandatory for any change in these paths

1. Characterization test first (current behaviour pinned) → 2. change → 3. run the
balance test files above + `scripts/dev/quality-gate.sh backend` → 4. `cif-balance-auditor`
review → 5. final report labels it **BUSINESS-RULE CHANGE** (or states "no business-rule change").
