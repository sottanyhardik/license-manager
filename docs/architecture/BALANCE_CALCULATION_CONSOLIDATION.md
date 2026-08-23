# Balance Calculation Architecture

This document records the current inventory and license-balance calculation contract.
It replaces the older deployment checklist that referenced obsolete paths, removed
debug scripts, and historical commit IDs.

## Source Of Truth

License-level balance calculations are centralized in:

```text
backend/apps/license/services/balance_calculator.py
```

The authoritative service is `LicenseBalanceCalculator`. Parent model properties
delegate to that service instead of maintaining separate formulas in model,
serializer, report, or script code.

Current license-level formula:

```text
balance = credit - (debit + allotment + trade)
balance = max(quantize_2dp(balance), 0)
```

Component definitions:

| Component | Source | Meaning |
|---|---|---|
| `credit` | `LicenseExportItemModel.cif_fc` | Total export CIF for the license. |
| `debit` | `RowDetails.cif_fc` | BOE debit rows for the license, excluding BOEs linked to trades. |
| `allotment` | `AllotmentItems.cif_fc` | Allotments whose parent allotment is not linked to a BOE. |
| `trade` | `LicenseTradeLine.cif_fc` | SALE trade lines for the license. |

Balances are converted through `apps.core.utils.decimal_utils.to_decimal`,
quantized to two decimal places with `ROUND_HALF_UP`, and floored at zero.

## Model Contract

`backend/apps/license/models/core.py` exposes compatibility properties on
`LicenseDetailsModel`:

| Property or method | Contract |
|---|---|
| `opening_balance` | Delegates to `LicenseBalanceCalculator.calculate_credit`. |
| `get_total_debit` | Delegates to `LicenseBalanceCalculator.calculate_debit`. |
| `get_total_allotment` | Delegates to `LicenseBalanceCalculator.calculate_allotment`. |
| `get_balance_cif` | Delegates to `LicenseBalanceCalculator.calculate_balance`. |

Stored balance state lives in the `LicenseBalance` one-to-one subrow:

```text
LicenseDetailsModel --one-to-one--> LicenseBalance(balance_cif, ledger_date)
```

`LicenseBalance.balance_cif` is denormalized state. It exists for filtering,
reporting, and list performance. It must be refreshed from
`LicenseBalanceCalculator`; it must not become a second formula source.

## Refresh Paths

Use the management command when stored balances need to be repaired or refreshed:

```bash
python manage.py update_balance_cif
python manage.py update_balance_cif --batch-size 100
python manage.py update_balance_cif --license-number 0310837441
python manage.py update_balance_cif --dry-run
```

The command validates:

| Input | Validation |
|---|---|
| `--batch-size` | Must be greater than zero. |
| `--license-number` | Trimmed and rejected if blank. |

Updates run through `LicenseBalanceCalculator.calculate_balance` and write only
the `LicenseBalance` subrow. The command uses ordered iteration for batch runs
and wraps each write in an atomic transaction.

## Validation And Edge Cases

The current balance contract handles:

| Case | Expected behavior |
|---|---|
| Missing aggregate rows | Treated as `Decimal("0")` through `Coalesce` and `to_decimal`. |
| `None` aggregate values | Coerced to `Decimal("0")`. |
| Negative calculated balance | Stored and reported as `Decimal("0")`. |
| Exact zero balance | Preserved as `Decimal("0")`. |
| Fractional cents | Rounded to two decimals with `ROUND_HALF_UP`. |
| Trade-linked BOE rows | Excluded from BOE debit to avoid double counting with SALE trade lines. |
| Allotments already linked to BOE | Excluded from non-BOE allotment consumption. |

Any new inventory or balance path must add focused tests before changing one of
these rules.

## Maintained Tests

Primary regression coverage lives in:

```text
backend/apps/license/tests/test_balance_calculator.py
backend/apps/license/tests/test_update_balance_cif_command.py
backend/tests/test_api_license.py
```

The old standalone scripts under `backend/scripts/` were removed because they
depended on mutable development data and printed observations instead of
asserting deterministic behavior.

Recommended focused verification for balance changes:

```bash
.venv/bin/python -m pytest backend/apps/license/tests/test_balance_calculator.py -q
.venv/bin/python -m pytest backend/apps/license/tests/test_update_balance_cif_command.py -q
.venv/bin/python backend/manage.py check
.venv/bin/python backend/manage.py makemigrations license --check --dry-run
```

## Implementation Rules

When adding or changing inventory and balance behavior:

1. Reuse `LicenseBalanceCalculator` for license-level formulas.
2. Reuse `ItemBalanceCalculator` for import/export item balance helpers.
3. Do not add serializer, view, report, or script-specific balance formulas.
4. Keep stored `LicenseBalance.balance_cif` as a cache of the service result.
5. Add regression tests for zero, negative, missing aggregate, trade-linked BOE,
   and BOE-linked allotment cases when those paths are touched.
6. Prefer database aggregates with `Coalesce` for totals and use `to_decimal` at
   service boundaries.
