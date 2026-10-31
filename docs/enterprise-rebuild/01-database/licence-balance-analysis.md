# Licence-balance analysis - preliminary

## Documented current-state contract

## Source-to-consumer map (AR-003)

| Domain | Current authoritative calculator/read boundary | Meaning and primary consumers |
|---|---|---|
| Licence operational/customs | `LicenseBalanceCalculator.calculate_balance` / `calculate_customs_balance` | Visible versus all-BOE debit views; licence views, reports and ledger exports consume these deliberately different figures. |
| Financial availability | `LicenseBalanceCalculator.calculate_financial_balance` | Hidden-BOE-aware opening plus purchase/sale, allocation-aware BOE debit and outstanding allotment; financial ledger, dashboard/report filtering and exports. |
| Physical import-item quantity | `ItemBalanceCalculator.calculate_available_quantity` | Quantity less visible BOE quantity, outstanding allotment and unpaired direct sale; allocation and item/report consumers. |
| Bulk read model | `balance_snapshot.get_snapshot_bulk` | Composes bulk calculator maps; it does not redefine the financial/customs formulas. |
| Stored compatibility values | `apps.core.scripts.calculate_balance` | Legacy/materialised field writer with documented ARO and rounding compatibility behavior; not safe to merge into live calculators without lifecycle approval. |

The calculator has 57 static internal dependents. Current evidence classifies these
as distinct business views or read projections, not demonstrated duplicate formulas.

Existing documentation identifies `LicenseImportItemsModel.available_quantity` as a stored/materialised value. Its documented validation formula is:

```text
available_quantity = quantity - debited_quantity - allotted_quantity - direct_sale_quantity
```

The same documentation identifies divergent calculations: a balance snapshot path omits `direct_sale_quantity`, and a frontend customs-ledger calculation uses only quantity minus BOE-debited quantity. This is a confirmed architectural concern from earlier code audit, but this phase has not re-executed each caller against a live database.

## Rebuild decision

Do not migrate a display value as the sole accounting of entitlement. The target must preserve source facts and create:

1. immutable usage/reservation/release/reversal events linked to source documents;
2. a canonical balance service/read model using approved lifecycle definitions;
3. optional materialised snapshots only where performance needs them, with timestamp/version/reconciliation fields;
4. one report/export/UI contract consuming the canonical read model;
5. golden tests covering zero, fractional, unit conversion, exhaustion, cancellation, reversal, direct sale, hidden BOE policy and concurrent allocation.

## Open business decisions

- Exact treatment of reservation versus posted allotment.
- Whether direct sale consumes quantity/value in every licence/item condition.
- Effect of hidden/restored BOEs on operational balance and historical reporting.
- Ordering/timezone/date policy for backdated adjustments.
- Rounding and unit-conversion rules.

These decisions must be approved from source documents and historical cases; the rebuild must not choose them simply to unify implementation code.

