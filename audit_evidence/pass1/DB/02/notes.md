# DB-02 — BOE "merge" can raise an unhandled `ProtectedError` on real live data

## What's wrong

`merge_boe()` (`backend/apps/bill_of_entry/services/boe_service.py:203-285`)
merges a `source_boe` into a `target_boe`:

1. It computes `existing_combos` = the set of `(sr_number_id,
   transaction_type)` pairs already present on `target_boe`'s `RowDetails`
   (line 243-245).
2. For each `RowDetails` row on `source_boe`, if its `(sr_number_id,
   transaction_type)` combo is **already** in `existing_combos`, the row is
   counted as "skipped (duplicate)" and left un-moved (lines 249-255) — it
   stays attached to `source_boe`.
3. `source_boe.delete()` is called (line 268) to remove the now-mostly-empty
   source header.
4. `RowDetails.bill_of_entry` is `on_delete=models.CASCADE`
   (`backend/apps/bill_of_entry/models.py:378-384`), so Django's deletion
   collector walks from `source_boe` and tries to cascade-delete every
   `RowDetails` row still pointing at it — **including the "skipped"
   duplicate rows from step 2**, which were deliberately left behind.
5. If any of those skipped rows has an active reconciliation record pointing
   at it — `InvoiceBOEAllocation.row_details`, `BOEAllotmentAllocation.row_details`,
   or `ExternalInvoiceLink.row_details`, all `on_delete=models.PROTECT`
   (`backend/apps/reconciliation/models.py:268-272`, `369-373`, `468-472`) —
   Django's collector raises `django.db.models.deletion.ProtectedError`
   **before issuing any DELETE SQL**.

Both call sites that invoke `merge_boe()` only catch `ValueError`:

- `backend/apps/bill_of_entry/views/boe.py:435-441` — `except ValueError as exc:`
- `backend/apps/reconciliation/views.py:197-208` — `except ValueError as exc:`

`ProtectedError` is not a `ValueError`, so it propagates out of the view as
an unhandled exception → DRF's default exception handling returns a raw
HTTP 500 with a stack trace, instead of a clean 4xx explaining "this BOE has
an existing allocation and can't be merged."

The `db_transaction.atomic()` block (line 241) does mean the failure is
**transactionally safe** — nothing is partially committed, the whole merge
rolls back cleanly. This is not a data-corruption bug. It is an unhandled
error path on a financial write action that leaves the user with a 500
instead of an actionable message, for a precondition (duplicate combo +
existing allocation) that is trivial to detect up front.

## Live evidence this precondition already exists today

`query_result` section 1 shows the **only two** `InvoiceBOEAllocation` rows
that exist in the live database point at two *different* `RowDetails` rows
(`274426`, `274427`) that both belong to `sr_number_id=37689`,
`transaction_type='D'` — but on two *different* BOE headers, `27571` and
`27572` (section 3).

Section 2 shows those two BOE headers are for the same date (`2026-02-20`),
the same port (`489`), with near-sequential BOE numbers `7650222` /
`7650224` — exactly the shape of a plausible "these look like the same
physical BOE entered twice" candidate a user would pick for the Merge
action in the reconciliation UI (`reconciliation/services/queries.py`'s
`duplicate_boes` detector feeds this action, per its own docstring at
`backend/apps/reconciliation/services/queries.py:266-267`).

If a user merged either one into the other today: `existing_combos` on the
target would already contain `(37689, 'D')` from the target's own row, the
source's `(37689, 'D')` row would be classified "skipped (duplicate)," and
`source_boe.delete()` would attempt to cascade-delete that skipped row —
which is exactly the row protected by the live `InvoiceBOEAllocation`
pointing at it. Section 4 confirms the on_delete wiring: `RowDetails ->
BillOfEntryModel` has no DB-level `ON DELETE` clause (Django-side CASCADE
only), and `InvoiceBOEAllocation -> RowDetails` likewise has no DB-level
clause (Django-side PROTECT, enforced by the collector, not the DB).

## Impact scope

- **API:** `POST /api/bill-of-entry/<id>/merge/`
  (`backend/apps/bill_of_entry/views/boe.py:417-446`) and
  `POST /api/reconciliation/merge-boe/`
  (`backend/apps/reconciliation/views.py:179-210`).
- **Screens:** the Reconciliation panel's "Merge BOE" action (surfaced from
  the `duplicate_boes` detection query).
- **Data integrity:** none corrupted (atomic rollback works correctly) — the
  defect is the unhandled-exception / poor-error-surface path, not silent
  data loss. Severity is therefore medium, not critical: the failure mode is
  "user sees a 500 and the merge doesn't happen," not "data is wrongly
  deleted."

## Fix shape (not applied — read-only investigation pass)

In `merge_boe()`, either (a) skip-and-report combos whose source row has any
current reconciliation reference instead of leaving it for the CASCADE to
hit, or (b) wrap `source_boe.delete()` and re-raise as the same `ValueError`
type the callers already handle, with a message identifying which rows
blocked the merge. No model/schema change or migration is required for this
one — it is a pure application-code fix in `boe_service.merge_boe()` — but
per audit scope this pass makes no source-code changes; recorded here for a
future fix pass.

## Unverifiable assumptions

- Did not execute the merge endpoint in a test harness with these exact two
  BOEs to observe the literal traceback (that would require using the app's
  own test DB via a management command / test run, not the live DB, per this
  pass's read-only-on-source-and-DB constraints, and setting up an
  authenticated superuser reconciliation session was out of scope for a
  read-only investigation) — the control-flow trace above is derived
  directly from reading `boe_service.merge_boe()`, the two views, and the
  three models' `on_delete` declarations, cross-checked against the live
  `pg_constraint` definitions and the two real `InvoiceBOEAllocation` rows
  that currently sit on exactly this precondition.
