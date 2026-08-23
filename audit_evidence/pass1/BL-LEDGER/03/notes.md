# BL-LEDGER-03 — `ItemBalanceCalculator.calculate_item_balance` ignores sibling items' outstanding allotments in its (common) zero-`cif_fc` branch

## File / function
`backend/apps/license/services/balance_calculator.py`, `ItemBalanceCalculator.calculate_item_credit_debit()` (lines ~1666-1724) → `calculate_item_balance()` (~1726-1739).

## License(s) used
`0911012707` (pk 2666), plus 3 corroborating licenses with the identical
shape: `0911012708` (2667), `0911012714` (2669), `0911012709` (2668). All
four found by scanning for licenses with exactly 2 import items, both
`cif_fc = 0`, with an outstanding `AT`-type allotment on only one of the
two items.

## Root cause
`calculate_item_credit_debit(import_item)` branches on whether
`import_item.cif_fc` is 0:
- If non-zero: `credit = import_item.cif_fc`, `debit` = that item's OWN
  `RowDetails` DEBIT rows only — correctly item-scoped.
- If zero (the branch actually exercised by 2,093 of 2,401 real import
  items, 87%): `credit` = the WHOLE license's export CIF total, and
  `debit` = the WHOLE license's raw BOE `RowDetails` total — i.e. it
  falls back to a license-wide figure.

After the branch, `total_debit = debit + allotment`, where `allotment`
comes from `LicenseBalanceCalculator.get_outstanding_allotment_totals
(import_item)` — but that call is filtered `item=import_item`, i.e.
**only that one item's own outstanding allotment**, never any other
item's. So in the zero-`cif_fc` branch, an item with no allotment of its
own reports `total_debit` = license-wide BOE debit only, completely
omitting any CIF already committed via `AllotmentItems` rows against
*other* items of the same license.

## Reproduction (read-only, real data)
On license `0911012707` (pk 2666), two import items both have `cif_fc = 0`:
- Item 39613 (serial 15): no `AllotmentItems` row of its own.
- Item 39614 (serial 16): one outstanding `AT`-type `AllotmentItems` row, `cif_fc = 13915.40`.

License-wide truth (the app's own authoritative formula):
- `calculate_credit(license)` = 23565.10
- `calculate_boe_debit_total(license)` = 0.00
- `calculate_allotment(license)` = 13915.40 (the sibling item's commitment)
- `calculate_financial_balance` / `calculate_balance(license)` = **9649.70**

But `ItemBalanceCalculator.calculate_item_balance(item_39613)` (the
un-allotted item) returns **23565.10** — the full, un-netted license
credit, overstating the item's real remaining CIF by exactly 13915.40, the
amount already spoken for by its sibling item 39614. The same pattern
reproduces identically on 3 other licenses (see query_result.txt).

## Expected result
An item-level "available balance" helper should never be able to report
MORE headroom than the license's own authoritative Balance CIF
(`calculate_financial_balance`/`calculate_balance`) — at most it should
equal it (when this item is the only unconsumed one). Every other
consumer in this codebase (the license-level calculators, the item's own
correctly-item-scoped quantity calculator `calculate_available_quantity`)
already respects this invariant.

## Actual result
`calculate_item_balance()` on the zero-`cif_fc` path can and does report a
figure 13915.40–18662.37 higher (in the 4 licenses found) than the
license's real Balance CIF, because it nets only the raw BOE debit against
the whole-license credit and only the ONE item's own allotment — never the
allotments already committed to sibling items.

## Reachability / current live impact
Traced every call site of `calculate_item_balance`,
`calculate_item_credit_debit`, `calculate_available_value_for_allocation`,
and the only consumer class that uses them for a real decision,
`apps.allotment.services.allocation_service.AllocationService`
(`calculate_max_allocation` → `validate_allocation_amount`). Result:
`AllocationService` is exported from `apps/allotment/services/__init__.py`
but is **not imported or called by any view, serializer, or other service
module** in the codebase (only by its own module and by
`apps/license/tests/test_balance_calculator.py` /
`backend/tests/test_all_conditions.py`). The actual live allocation gate —
`apps.allotment.views_actions.AllotmentActionViewSet.allocate_items` →
`AllocationService.allocate_item` → `LicenseValidationService.
validate_allocation` — validates value against
`license_obj.get_balance_cif` (the correct, license-wide, allotment-aware
figure) and quantity against `ItemBalanceCalculator.
calculate_available_quantity` (correctly item-scoped, since it also nets
the item's own debited quantity AND its own outstanding allotment
quantity, not other items'). So today, in the code paths actually wired
to a URL, no user can exploit this specific function to over-allocate CIF
beyond a license's real balance.

## Why this is still reported as a defect (not just an improvement)
The function's output is objectively wrong against its own documented
contract ("Calculate balance for an import item" / "Returns: Balance as
Decimal (minimum 0)") and against the invariant every sibling calculator in
the same module upholds. It is exercised by 87% of real import items
(the zero-`cif_fc` branch is the *common* case, not a corner case), and it
sits in a class (`AllocationService`) whose method names
(`calculate_max_allocation`, `validate_allocation_amount`,
`allocate_item`) closely mirror the real, live gate — a very plausible
target for a future feature (a "suggest max quantity" button, a bulk
allocation API, a management command) to be wired to without anyone
re-deriving that it silently ignores sibling-item commitments. Severity is
scored low precisely because of the reachability finding above, not
because the calculation itself is correct.

## Ambiguity
None on the mechanism. Whether the intended fix is to make the zero-`cif_fc`
branch net the license-wide outstanding allotment total (all items, not just
this one) rather than just this item's, or to remove the branch/class
entirely as dead/superseded code now that the real gate lives in
`LicenseValidationService`, is a product/architecture decision this
read-only pass does not make.
