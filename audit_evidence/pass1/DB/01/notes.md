# DB-01 — `on_delete=CASCADE` on nullable master-data FKs (PortModel, CompanyModel)

## What's wrong

`PortModel` and `CompanyModel` are small, low-cardinality **master/reference**
tables (ports of import, trading companies) that are fully exposed for CRUD —
including `DELETE` — through the generic `MasterViewSet`
(`backend/apps/core/views/master_view.py:81-97`, `http_method_names` includes
`'delete'`), gated only by `MasterDataPermission`
(`backend/apps/core/views/master_view.py:43-52`): any authenticated
`is_superuser` account can `DELETE` a single `PortModel` or `CompanyModel` row
with no additional confirmation, dry-run, or dependency check.

Every FK from the license/BOE/allotment domain models into these two master
tables is declared `on_delete=models.CASCADE`, and every one of them is also
`null=True, blank=True` — i.e. the field is *optional*, which is exactly the
case where Django's own docs recommend `SET_NULL`, not `CASCADE`:

- `backend/apps/license/models/core.py:126` — `LicenseDetailsModel.port`
- `backend/apps/bill_of_entry/models.py:186-192` — `BillOfEntryModel.company`
- `backend/apps/bill_of_entry/models.py:195-200` — `BillOfEntryModel.port`
- `backend/apps/allotment/models.py:47-51` — `AllotmentModel.company`
- `backend/apps/allotment/models.py:95-99` — `AllotmentModel.port`
- `backend/apps/allotment/models.py:102-106` — `AllotmentModel.related_company`

Because these fields are nullable, deleting the referenced Port/Company row
was never *required* to keep the schema consistent — nulling the FK would
have preserved the license/BOE/allotment row. `CASCADE` instead deletes the
whole dependent row (and everything cascading from it: import items, export
items, `RowDetails`, `AllotmentItems`, …), unless a downstream `PROTECT`
relationship (e.g. an active `InvoiceBOEAllocation`/`BOEAllotmentAllocation`
pointing at one of those `RowDetails`/`AllotmentItems` rows) happens to block
part of the chain — which is incidental, not a deliberate safeguard.

Note precisely what "CASCADE" means here: `pg_get_constraintdef` (see
`query_result`, section 1) shows **no `ON DELETE` clause** on any of these
Postgres FK constraints — Postgres itself defaults to `NO ACTION`. The
cascade is entirely a **Django ORM-level** behavior: `Model.delete()` walks
the dependency graph in Python (`django.db.models.deletion.Collector`) and
issues explicit `DELETE` statements for every CASCADE-linked child, all
inside one transaction. This means: (a) it only happens via `Model.delete()`
/ `queryset.delete()` through Django — a raw `DELETE FROM core_portmodel ...`
run directly in `psql` would fail with a plain FK violation, since there is
no real `ON DELETE CASCADE` in the DDL; (b) it is unconditionally reachable
from the `DELETE` HTTP verb described above, since that goes through the
Django ORM.

## Live evidence of the blast radius

`query_result` section 2 (per-port row counts) shows port id 513 (`INNSA1`,
Nhava Sheva Sea) is referenced by **171 `LicenseDetailsModel` rows, 436
`BillOfEntryModel` rows, and 37 `AllotmentModel` rows** — a large fraction of
this system's entire financial/customs dataset (228 licenses total, per the
earlier orphan check). A single `DELETE /api/.../ports/513/` call by a
superuser — issued, say, while trying to merge a duplicate port entry or
clean up a typo — would cascade through Django and permanently remove all
171 licenses (and every one of their import/export items, purchases,
ownership row, plan rows, documents…), all 436 BOEs (and every `RowDetails`
row under them), and all 37 allotments, in one transaction. There is no
undo; this is data loss of the core business record, not a display glitch.

`query_result` section 3 shows the same pattern for `CompanyModel`: e.g.
company id 138 (Sigma Chemtrade Pvt Ltd) has 48 BOEs and 21 allotments that
would cascade-delete if that company record were removed.

## Why this is clearly a mistake, not an intentional design choice

The same file tree shows the correct pattern was already used once, for the
*other* `CompanyModel` FK on the same model:

- `backend/apps/license/models/core.py:117-121` —
  `LicenseDetailsModel.exporter` is `on_delete=models.SET_NULL`.
- `backend/apps/license/signals.py:431-438` — a dedicated `pre_delete` signal
  on `CompanyModel` snapshots `archived_exporter_name` before the FK is
  nulled, specifically so the license record survives the company's deletion
  with its human-readable name intact.

That is: the author of `LicenseDetailsModel.exporter` explicitly designed
for "a company gets deleted while licenses still reference it" as a normal,
supported scenario and protected the data. `BillOfEntryModel.company`,
`AllotmentModel.company`/`related_company`, and every `port` FK across all
three apps received no equivalent treatment — they were left at Django's
`CASCADE`, which is the default in older Django snippets/tutorials people
copy from, and is very easy to leave unchanged by accident on a field that
was made nullable for an unrelated reason (e.g. "port not always known at
import time").

## Impact scope

- **Tables:** `core_portmodel`, `core_companymodel`, and every table that
  cascades from a delete of either (`license_licensedetailsmodel` and its
  full sub-table tree, `bill_of_entry_billofentrymodel` and
  `bill_of_entry_rowdetails`, `allotment_allotmentmodel` and
  `allotment_allotmentitems`).
- **APIs:** `DELETE` on the generic master-data endpoints for Ports and
  Companies (`backend/apps/core/views/views.py:188-190, 230-234`, routed
  through `MasterViewSet`).
- **Screens:** any admin/master-data management screen that exposes a
  delete action for Ports or Companies.
- Gated to `is_superuser` only — this lowers likelihood but does not change
  the severity of the outcome once triggered (irreversible mass deletion of
  the core financial/customs ledger), and superusers are exactly the users
  most likely to be doing "cleanup" work on master data (merging duplicate
  ports/companies) where this would fire.

## Fix shape (not applied — this is a read-only investigation pass)

Change `on_delete=models.CASCADE` to `on_delete=models.SET_NULL` (also
already `null=True` in every case, so no data-shape change) on:
`LicenseDetailsModel.port`, `BillOfEntryModel.company`,
`BillOfEntryModel.port`, `AllotmentModel.company`, `AllotmentModel.port`,
`AllotmentModel.related_company`. This requires a Django migration (an
`AlterField` migration changing the FK's `on_delete`, which is a Python/ORM
level change — Postgres has no real `ON DELETE CASCADE` to alter here, so
the migration only changes Django's deletion-collector behavior, not the DB
constraint DDL). **Not generated or applied in this pass** — flagged for
explicit human/migration approval per audit scope rules.

## Second, independent exposure: Django admin

`backend/apps/core/admin.py:56-75` auto-registers **every** model in the
`core` app with a default `admin.ModelAdmin` (wrapped only in
`_MDSReadOnlyAdminMixin`, which only locks down models that appear in the MDS
sync registry — `CompanyModel`/`PortModel` are not in that registry and are
not in the small hand-picked exclusion list on line 59 either). A default
`ModelAdmin` permits delete (single-object and bulk "Delete selected") for
any Django user holding the standard `core.delete_companymodel` /
`core.delete_portmodel` permission — a permission assignable to any staff
group, **not limited to `is_superuser`**. This is a second, wider-reach path
to the exact same CASCADE chain described above, independent of the DRF
`MasterDataPermission` gate.

## Unverifiable assumptions

- Did not verify whether any `core.delete_portmodel` / `core.delete_companymodel`
  Django permission grants currently exist on non-superuser staff accounts in
  this environment (would require inspecting `auth_user_user_permissions` /
  `auth_group_permissions` for a specific deployment's user base, which is
  outside this pass's DB-schema/constraint scope) — the *capability* is
  confirmed by the admin registration code above regardless of current grants.
