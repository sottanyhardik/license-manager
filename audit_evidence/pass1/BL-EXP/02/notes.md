BL-EXP-02: `latest_transfer` can surface a stale pending/rejected transfer
instead of the actually-latest completed one (wrong sort key + NULL semantics)

File: backend/apps/license/models/core.py, `LicenseDetailsModel.latest_transfer`
(cached_property, ~line 830):

    @cached_property
    def latest_transfer(self):
        qs = self.transfers.order_by("-transfer_date", "-id")
        if qs.exists():
            return qs.first()
        if self.current_owner:
            return f"Current Owner is {self.current_owner.name}"
        return "Data Not Found"

Consumers (all reachable in production):
- backend/apps/license/serializers/license.py:433
  `latest_transfer = serializers.CharField(read_only=True)` — exposed on the
  license detail/list API (`views/license.py` field list includes
  "latest_transfer"), i.e. shown directly in the frontend license detail page.
- backend/apps/license/services/exporters/license_balance_excel.py:85 and
  services/exporters/license_balance_pdf.py:739 — printed verbatim into the
  Balance Report Excel/PDF exports.

Root cause: `transfer_date` (`LicenseTransferModel.transfer_date`) is populated
by DGFT only once a transfer is finalized/approved — for a "Transfer - Pending
Acceptance" (or any non-approved) transfer it is NULL (confirmed: real row id
2076 for license 0311043123, transfer_status = "Transfer - Pending Acceptance",
transfer_date = NULL, while transfer_initiation_date is always populated).
Postgres' default NULL ordering for `ORDER BY col DESC` is NULLS FIRST
(verified empirically against this DB in query 1) — the opposite of "most
recent first" for a nullable date. So `order_by("-transfer_date", "-id")`
always places every not-yet-finalized (or otherwise date-less) transfer ahead
of every dated one, regardless of how old that pending/rejected transfer
actually is.

The rest of the codebase's own "most recent transfer" logic does NOT make this
mistake: `update_license_ownership.py`'s `_parse_transfer_dt` /
`_derive_current_owner_from_transfers` / `_derive_file_transfer_status` all key
off `transfer_initiation_date` (via `max(transfers, key=_parse_transfer_dt)`),
which is always populated and reflects true chronological order. The model
property is inconsistent with the command's own, more-correct implementation
of the same concept.

Failure scenario (traced, not currently present in the 228-license sample):
license has an Approved transfer on 2025-01-01 (transfer_date = 2025-01-01),
then later initiates a second transfer that stalls/is abandoned in "Pending
Acceptance" (transfer_date stays NULL) on 2025-02-01, and separately a THIRD,
properly completed transfer happens on 2025-06-01 (transfer_date = 2025-06-01,
the true latest). `latest_transfer` would return the 2025-02-01 pending row
(NULL sorts first) instead of the 2025-06-01 approved one, showing the license
detail page / balance report as "pending transfer to X" when it has in fact
already been re-transferred and is settled with a different current owner.

Live-data check: the current 27-row transfer table has exactly one
transfer_date-NULL row (license 0311043123 / id 1955), and it happens to also
be the true latest transfer for that license by transfer_initiation_date, so
today's API response for that license is coincidentally correct. Query 3
confirms zero licenses in the current dataset where the (-transfer_date) pick
differs from the (-transfer_initiation_date) pick.

Expected: `latest_transfer` should order by `transfer_initiation_date` (always
populated, matches the command's own recency logic), not by `transfer_date`.

Actual: orders by `transfer_date`, which is NULL for anything not yet
finalized, and NULLs sort first in Postgres DESC — so an old stalled/pending
transfer can permanently "win" over later completed ones.

Confidence: medium — the defective mechanism (wrong sort column + NULL
ordering) is proven directly against this database, and a real pending
transfer with NULL transfer_date exists in the sample; but the exact
data sequence that would make the returned answer visibly wrong does not
currently exist among the 228 licenses, so I have not reproduced a wrong
API response today. Recorded as `ambiguous=false` (this is a code defect,
not a business-rule ambiguity) but confidence capped at medium per the
audit instructions because the wrong-output sequence itself is not present
in the current data — the "no wrong output in the sample" fact is not a
counter-argument to the bug, only a reason not to claim `high` confidence.
