BL-EXP-05: `fetch_eligible_licenses()` uses a different expiry boundary than
the rest of the codebase, so a license expiring exactly "today" is skipped by
the default DGFT ownership-fetch run

File: backend/apps/license/management/commands/update_license_ownership.py,
`fetch_eligible_licenses` (lines 67-108):

    if expired_only:
        qs = LicenseDetailsModel.objects.filter(
            license_expiry_date__isnull=False,
            license_expiry_date__lte=today,          # <=  (expired incl. today)
        )...
    else:
        qs = LicenseDetailsModel.objects.filter(
            Q(license_expiry_date__isnull=True) | Q(license_expiry_date__gt=today)  # >  (strict)
        )...

Every other place in the codebase that classifies a license as expired uses
the strict rule "expired = expiry_date < today" (expiry-day-itself still
counts as active) — see signals.py:170, tasks.py:98/277/390,
views/license.py:484/487, services/ledger_service.py:277. This management
command instead treats "expiry_date == today" as already-expired for the
`--expired` branch (`<=`) while simultaneously treating it as not-yet-active
for the default branch (`> today`, strict) — i.e. a license expiring exactly
today falls into neither the default eligible set nor the plain "active" set,
and is only reachable by explicitly re-running the command with `--expired`.

Impact: this command is not scheduled via Celery Beat in this repository (the
beat schedule in `lmanagement/celery.py` only registers `sync_all_licenses`,
`identify_licenses_needing_update`, and `cleanup_old_task_records` —
`update_license_ownership` is invoked manually/externally, per its own
docstring "Fetch ownership status... " and the module's interactive
server-selection prompt). Whatever external cron/script runs this daily would,
if it only runs in default mode (no `--expired`), silently skip refreshing
DGFT ownership/transfer data for any license on the exact day it expires,
delaying detection of a transfer that completes right at expiry by one cycle.

Live-data status: no license in the current 228-row dataset expires exactly
today (2026-08-07), so this cannot be demonstrated against live data; reported
purely by tracing the two boundary definitions in source.

Expected: `fetch_eligible_licenses` should use the same `< today` / `>= today`
boundary as the rest of the codebase, so a license expiring today is (a)
correctly classified as still-active/eligible for the default run, or (b) if
the intent is genuinely "grace period" pre-fetching for soon-to-expire
licenses, that should be an explicit, named window rather than an accidental
one-day gap between two independently-written filters.

Actual: `<=`/`>` boundary creates a one-day gap that neither branch covers by
default.

Confidence: low — real inconsistency confirmed in source, but (a) no license
in the live sample currently sits in the affected one-day window, and (b) the
actual operational schedule/flags used to invoke this command in production
are outside this repository, so I cannot confirm how often (if ever) the
`--expired` flag is combined with the default run to close this gap in
practice.

Unverifiable assumption: the external cron/script that invokes
`update_license_ownership` in production — its schedule and whether it ever
passes `--expired` — is not present in this repository, so the practical
impact of this one-day gap cannot be fully verified from code + local DB alone.
