BL-EXP-04: `is_expired`/`is_active` inconsistently trusted as a cached flag vs.
computed live (staleness window depends on Celery Beat health)

Files:
- backend/apps/license/models/core.py:225 `LicenseDetailsModel.is_expired`
  property → reads `LicenseFlags.is_expired` (a stored boolean).
- backend/apps/license/signals.py:147 `update_license_flags` — recomputes
  `is_expired = license_expiry_date < today` and writes it, but ONLY when a
  post_save/post_delete signal fires on the license itself or one of its
  import/export items, allotment items, BOE rows, or trade lines. A license
  with zero activity around its expiry moment gets no signal.
- backend/lmanagement/celery.py:43-90 — the only time-based refresh:
  `sync-licenses-daily-midnight-ist` (00:30 IST) runs `sync_licenses`, and
  `update-balances-11am-ist` / `-8pm-ist` run `identify_licenses_needing_update`
  → `update_identified_licenses`, both of which also recompute `is_expired`.
  So in practice there are 3 recompute opportunities per day, but all of them
  depend on Celery Beat + at least one worker actually running.
- Consumers that read the CACHED flag directly (can be stale for hours until
  the next scheduled run, or indefinitely if Celery Beat/worker is down):
  - backend/apps/license/services/validation_service.py:43
    `validate_license_active` — `if license_obj.is_expired: errors.append(...)`
  - backend/apps/license/views/dashboard.py:85,91 — `flags__is_expired=False/True`
    counts shown on the dashboard.
  - backend/apps/license/views/ledger.py:272,
    backend/apps/license/services/ledger_service.py:336,432,593,875 —
    `flags__is_expired=False` filters used by DFIA search / ledger search
    (part of the transfer-letter / ledger workflow: users search for a
    license by this filtered list before generating a transfer letter).
- Consumer that instead computes LIVE from `license_expiry_date` (no
  staleness): backend/apps/license/views/license.py:462-549
  `apply_advanced_filters` — `qs.filter(license_expiry_date__lt=today)` /
  `Q(license_expiry_date__gte=today) | Q(license_expiry_date__isnull=True)`.

This is an architectural inconsistency: the same conceptual filter
("is this license expired") is implemented as a live SQL predicate in the main
license list view, but as a stale, batch-refreshed boolean everywhere else
(dashboard, ledger/DFIA search, and the allocation-guard code referenced in
BL-EXP-01). A license can therefore appear "active" in the dashboard/ledger
search, or (per BL-EXP-01, if that dead validation were ever wired back in)
pass an allocation check, for up to ~a few hours after its true expiry moment
in the best case (healthy Celery), or indefinitely if the beat scheduler/worker
is down, while the main license list simultaneously and correctly shows it as
expired.

Live-data status: query 1 shows zero currently-stale rows across all 228
licenses — the scheduled jobs are caught up as of 2026-08-07. This finding is
about the mechanism/architecture, not a currently-wrong value.

Expected: a single, consistently live-or-consistently-cached source of truth
for "is this license expired" used by every consumer (dashboard, ledger
search, list view, allocation gating).

Actual: mixed — live computation in the main license list view, cached/batch
value everywhere else.

Confidence: low — no currently-stale row is observable in the live dataset
(the batch jobs happen to be caught up right now), so I cannot prove a
currently-wrong displayed value; this is reported as a design/consistency
defect with a real but time-window-dependent, infra-dependent impact rather
than a proven wrong-output-today defect.

Unverifiable assumption: whether Celery Beat and a worker are continuously
running in the deployed environment (I only have the code's schedule
definition, not runtime/ops evidence of uptime).
