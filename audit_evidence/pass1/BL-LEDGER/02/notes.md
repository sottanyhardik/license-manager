# BL-LEDGER-02 — Cached `LicenseBalance.balance_cif` goes stale after reconciliation allocation actions

## License(s) / rows used
- License `0311054433` (pk resolved via `LicenseDetailsModel.objects.get(license_number=...)`).
- SALE trade line: `trade_licensetradeline.id = 846` (trade id 518), `cif_fc = 9560.00`.
- BOE DEBIT row: `bill_of_entry_rowdetails.id = 274889`, `cif_fc = 21669.770`, on the same license, not previously linked by any allocation or legacy `trade.boes` tag.

## What was done
Inside one `transaction.atomic()` block (rolled back afterward — no permanent
DB change), created an `InvoiceBOEAllocation` for 10,000.00 CIF between that
trade line and that BOE row — exactly the record
`apps.reconciliation.services.allocation_service` creates when a user
matches a Sale invoice line to part of a BOE debit row in the Reconciliation
UI.

## Expected result
Per `LicenseDetailsModel.get_balance_cif`'s own docstring, the Financial
Ledger formula (`calculate_financial_balance`) is "the single figure every
consumer... reads as 'the' business balance," and it is mirrored into the
cached `license_licensebalance.balance_cif` column by
`apps.license.signals.update_license_flags()` every time any debit/credit/
allotment/trade component changes. An `InvoiceBOEAllocation` create/edit/
reverse is exactly such a change (it feeds `calculate_debit()`, one of the
five terms of `calculate_financial_balance`), so the cached column should
update to stay in sync, the same way it does for every other transaction
type (import/export items, `AllotmentItems`, `RowDetails`, `LicenseTradeLine`
all have signal receivers in `apps/license/signals.py` that call
`update_license_flags`).

## Actual result
- Live `calculate_debit(license)`: `21669.770` → `11669.770` (correctly nets the 10,000 matched amount).
- Live `get_balance_cif()` / `calculate_financial_balance(license)`: `338299.59` → `348299.59` (correctly +10,000).
- Cached `license_licensebalance.balance_cif` (the column read directly by
  `apps/license/views/active_dfia_report.py`, `planned_report.py`,
  `license_report.py`, `item_plan.py`, and
  `apps/license/views/license_balance_ledger.py`'s `before_balance`):
  stayed at `338299.59` — did not move at all.

The two numbers, identical before the allocation, are now 10,000.00 apart
and will remain apart in the live system until some unrelated write to a
`RowDetails`/`AllotmentItems`/`LicenseTradeLine`/import-or-export-item row on
this same license happens to re-trigger `update_license_flags()`.

## Why the current algorithm fails
`apps/license/signals.py` registers `post_save`/`post_delete` receivers for
`LicenseImportItemsModel`, `LicenseExportItemModel`, `AllotmentItems`,
`RowDetails`, and `LicenseTradeLine` — every one of them calls
`update_license_flags(license)`, which recomputes `get_balance_cif` and
writes it back into `LicenseBalance.balance_cif` via `.filter().update()`.
There is **no equivalent receiver for
`apps.reconciliation.models.InvoiceBOEAllocation` or
`BOEAllotmentAllocation`**, and
`apps/reconciliation/services/allocation_service.py` (which creates,
supersedes/edits, and reverses these rows for every reconciliation action —
"match invoice to BOE," "edit allocation," "reverse allocation," and the
allotment-side equivalents) never calls `update_license_flags` itself
(`grep -rn "update_license_flags" backend/apps/reconciliation` returns
nothing). `apps/reconciliation/apps.py` doesn't even import a `signals`
module.

Both `calculate_debit()` (feeds `calculate_financial_balance`, i.e.
`get_balance_cif`) and `_annotate_allotment_contribution`'s
`allocated`/`matched`/`contributed` (feeds `calculate_allotment`, which also
feeds `calculate_financial_balance`) are keyed off these two reconciliation
models' `ACTIVE`/`is_current` rows — so both the invoice-matching side and
the allotment-matching side of the reconciliation ledger can silently drift
the cached Balance CIF without ever refreshing it.

## Blast radius (who reads the stale cached column instead of the live formula)
`grep -rn "\.balance_cif\b" backend/apps/license/views | grep -v get_balance_cif`
shows the stored column is read directly by:
- `apps/license/views/active_dfia_report.py` (report `balance_cif` figure and its 10%-wastage estimate)
- `apps/license/views/planned_report.py`
- `apps/license/views/license_report.py`
- `apps/license/views/item_plan.py`
- `apps/license/views/license_balance_ledger.py` (`before_balance`)
- `apps/license/serializers/license.py:730`

The main license list view (`apps/license/views/license.py`) was already
patched to batch-compute the *live* balance per page specifically because
the cached column "was originally caching to avoid" an N+1 — its own
docstring calls out the exact risk this finding reproduces — but that fix
was applied to one call site, not the root cause, and the several report
views above still read the column directly.

## Downstream effects of the same staleness
`update_license_flags` also drives `LicenseFlags.is_null` (`balance < $500`
business rule) and `_update_all_import_items_available_value` (which
recomputes every import item's cached `available_value`, including
percentage-condition pool caps). Both silently lag by the same missed delta
until an unrelated write on the license fires the recompute.

## Ambiguity
None on the mechanism (directly reproduced and code-confirmed). What IS a
business-decision, not something to guess at: whether the intended fix is
(a) add `post_save`/`post_delete` signal receivers for
`InvoiceBOEAllocation`/`BOEAllotmentAllocation` mirroring the existing five,
or (b) migrate every remaining stored-column reader over to the live
per-request/batched calculator the way the license list view already was,
retiring the cached column altogether. Both are legitimate; picking one is
a product/architecture call, not something this read-only pass should
decide.
