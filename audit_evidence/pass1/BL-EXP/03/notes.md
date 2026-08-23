BL-EXP-03: Two transfer-sync write paths dedupe LicenseTransferModel rows on
different uniqueness keys (latent duplicate-row risk, currently unreachable)

Files:
- backend/apps/license/views_actions.py
  - `update_license_transfer` (singular, line ~93-223): keys
    `update_or_create` on `(license, transfer_date, from_company, to_company)`.
  - `bulk_update_license_transfer` (line ~225-434): keys `update_or_create` on
    `(license, transfer_initiation_date)`.
- backend/apps/license/management/commands/update_license_ownership.py
  - `save_ownership_locally` (line 437): the actual local-DB write used every
    time the sync command runs keys on `(license, transfer_initiation_date)` —
    i.e. the SAME key as the bulk endpoint, not the singular one.
  - `SERVER_API` (line 19) is built from the singular endpoint's URL but is
    never referenced again anywhere in the file — a dead constant. The
    command's real server-sync call is `bulk_sync_to_server()`, which POSTs to
    `/api/license-actions/bulk-update-license-transfer/` exclusively.

Why this matters: `LicenseTransferModel` conceptually represents one real-world
DGFT transfer event, uniquely identified by `(license, transfer_initiation_date)`
— that's the field DGFT itself assigns and the only one guaranteed non-null at
every stage (pending or approved). If the singular `update-license-transfer`
endpoint is ever exercised for a license whose transfers were already
populated via the bulk/sync path (or vice-versa), the two code paths will not
recognize each other's rows as the same transfer:
  - the bulk/sync path's key `(license, transfer_initiation_date)` will not
    match a row the singular path created keyed on
    `(license, transfer_date, from_company, to_company)`,
  - so a second call for the same real transfer creates a new
    `LicenseTransferModel` row instead of updating the existing one —
    duplicate transfer history for the same license, which would corrupt
    `latest_transfer` (see BL-EXP-02), `current_owner` derivation, and the
    `ownership-data` API's transfer list shown to users.

Live-data status: not currently manifesting. The singular endpoint has zero
external callers in this codebase (no frontend usage; the only test hits it
for a permission check, not the create logic; `SERVER_API` is unused dead
code) and confirmed by query 1 that all 27 real `LicenseTransferModel` rows
have a non-null `transfer_initiation_date`, i.e. every row was actually
written by the bulk/command path, never the singular one. Query 2 confirms no
duplicate-looking transfer rows exist today.

Expected: both write paths should identify "the same transfer" using the same
key, e.g. both keyed on `(license, transfer_initiation_date)`.

Actual: the singular endpoint uses a different key than the bulk endpoint and
the command's own local-save function.

Confidence: low/latent — the code inconsistency is real and directly read from
source, but there is no evidence in the live system that the singular endpoint
is ever invoked (unverifiable assumption: whether any OTHER license-manager
server instance, or a future integration, calls `update-license-transfer`
directly — the multi-server "master-sync" architecture mentioned in
`lmanagement/celery.py`'s comments makes an external caller plausible, but I
could not find one in this repository). Recorded as an unverifiable assumption
rather than a proven current defect, per instructions.

Unverifiable assumption: no other license-manager server/service outside this
repository calls `POST /api/license-actions/update-license-transfer/` directly
(I can only confirm no in-repo caller exists).
