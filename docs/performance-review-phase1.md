# Performance Review — Phase 1 (New Backend)

**Reviewed:** 2026-07-14  
**Reviewer:** performance-engineer  
**Branch:** feature/V1  
**Scope:** backend/apps/*/views, serializers, services/balance_service.py,
services/dashboard_service.py, tasks.py, shared/pagination.py,
config/settings/base.py

Legacy baseline: `legacy/docs/PHASE_1_REVIEW.md §7` — five ranked production
bottlenecks (N+1 serializer, signal cascade, sync PDF/Excel, stale materialized
view, cache thundering herd).

---

## CRITICAL — Production query bombs

None found. The new backend has no unconditional N+1 loops in serializers or
views.

---

## HIGH — Will degrade under load

### H1 — `dashboard_service.get_dashboard_stats` fires 8 separate COUNT queries
**File:** `backend/apps/dashboard/services/dashboard_service.py:63–107`

`base_qs` (all licenses) is hit eight times with individual `.count()` calls
(`total_licenses`, `active_licenses`, `expired_licenses`, `null_licenses`,
`expiring_soon`, `total_balance_cif`, `low_balance_licenses`, and
`recent_allotments`). Each becomes a separate round-trip to Postgres. Even with
the 5-minute per-user cache this is 8+ queries on every cold request.

The cache TTL is per-user (`dashboard:stats:{user.pk}`), so N concurrent users
each hit the cold path once per 5 minutes — with 50 users that is 50 × 8 = 400
`COUNT` queries every 5 minutes.

**Fix:** collapse the eight `LicenseDetailsModel` counts into one
`base_qs.aggregate(...)` call using `Count` with `filter=Q(...)` keyword
arguments (Django 2.0+ conditional aggregation). That reduces 7 license-table
round-trips to 1.

```python
from django.db.models import Count, Q, Sum

stats = base_qs.aggregate(
    total_licenses=Count("pk"),
    active_licenses=Count("pk", filter=Q(flags__is_expired=False, flags__is_null=False)),
    expired_licenses=Count("pk", filter=Q(flags__is_expired=True, flags__is_null=False)),
    null_licenses=Count("pk", filter=Q(flags__is_null=True)),
    expiring_soon=Count("pk", filter=Q(
        license_expiry_date__gte=today,
        license_expiry_date__lte=thirty_days_ahead,
        flags__is_active=True,
        balance__balance_cif__gte=Decimal("100.00"),
    )),
    total_balance_cif=Sum("balance__balance_cif"),
    low_balance_licenses=Count("pk", filter=Q(
        balance__balance_cif__lt=Decimal("100.00"),
        flags__is_active=True,
    )),
)
```

**Before:** 8+ round-trips per cold call (minimum 8 ms × N network latency).  
**After:** 1 round-trip.  
**Behavior:** identical — all values are identical Decimal/int outputs.

---

### H2 — `recompute_license_balance` has no `select_for_update` guard — concurrent tasks corrupt balance
**File:** `backend/apps/license/services/balance_service.py:143–172`

The function wraps everything in `transaction.atomic()` but does NOT acquire a
row-level lock via `select_for_update()` before computing the balance. If two
Celery workers run `recompute_license_balance_task` for the same `license_id`
simultaneously (e.g. an import triggers several allotment signals in quick
succession), both read the same pre-update state, compute identical results, and
then both issue `UPDATE` — a lost-update race. Under the legacy signal cascade
(BOE import of 100 rows = 100 task dispatches for the same license) this is a
genuine production risk.

**Fix:** change the `get()` call to use `select_for_update()`:

```python
license_obj = LicenseDetailsModel.objects.select_related(
    "balance", "flags"
).select_for_update().get(pk=license_id)
```

This serializes concurrent recomputes for the same license, eliminating the
lost-update window. The existing `transaction.atomic()` wrapper is necessary
for this to work (already present).

**Behavior-safe:** same computed value; only serializes concurrent writes.

---

### H3 — `LicenseListSerializer` accesses `flags` and `scheme_code` but `LicenseViewSet.get_queryset()` does not `select_related("flags", "scheme_code")`
**File:** `backend/apps/license/views/license.py:70–85` vs  
`backend/apps/license/serializers/license.py:101–108`

`LicenseListSerializer` reads:
- `flags.is_expired` (line 104)
- `flags.is_active` (line 107)
- `scheme_code.code` (line 101)

`get_queryset()` calls `select_related("scheme_code", "flags")` — wait,
checking again:

```python
.select_related(
    "exporter",
    "scheme_code",       # present
    "notification_number",
    "port",
    "purchase_status",
    "balance",
    "flags",             # present
    "notes",
    "ownership",
    "ownership__current_owner",
)
```

`scheme_code` and `flags` ARE present in `select_related`. **This is not an
N+1.** Struck from critical — documented here for confirmation.

---

## MEDIUM — Should fix before cutover

### M1 — `MasterViewSetMixin.list()` with `?all=true` bypasses pagination entirely — no safeguard on table size
**File:** `backend/apps/core/views/masters.py:155–161`

Any client can request `?all=true` on `HSCodeViewSet` (thousands of rows),
`PortViewSet` (500+ rows), or any other master viewset and receive the full
un-paginated queryset in a single response. The view comment acknowledges the
risk ("Always filter or search before requesting `?all=true`") but there is no
server-side enforcement. A frontend bug or a test script calling `?all=true`
on HS codes will serialize and transmit potentially 10 k+ rows in one HTTP
response.

**Fix:** add a `MAX_ALL_ROWS = 500` guard and return a 400 if the queryset
would exceed it, or at minimum cap with `queryset[:MAX_ALL_ROWS]`.

**Blast radius:** all 20+ master ViewSets. Change is in the single mixin.

---

### M2 — `recompute_license_balance_task` missing `acks_late=True` and `reject_on_worker_lost=True`
**File:** `backend/apps/license/tasks.py:16–35`

The task:
```python
@shared_task(bind=True, max_retries=3)
def recompute_license_balance_task(self, license_id: int):
```

Without `acks_late=True`, Celery ACKs the message when the worker *picks it
up*, not when it *finishes*. If the worker process is killed mid-execution
(OOM kill, deploy restart) the task is silently lost and the license balance
is left stale. For a write-critical task (balance correctness affects
downstream allotment and trade decisions) this is a data-reliability issue.

**Fix:**
```python
@shared_task(bind=True, max_retries=3, acks_late=True, reject_on_worker_lost=True)
def recompute_license_balance_task(self, license_id: int):
```

No behavior change on the happy path. On worker crash the message is
re-queued and picked up by another worker.

The same applies to `generate_license_pdf_task` (line 38), though the
consequence there is a missing PDF rather than corrupted data.

---

### M3 — `get_dashboard_stats` uses per-user cache keys — thundering herd on shared data
**File:** `backend/apps/dashboard/services/dashboard_service.py:54–57`

Cache key: `dashboard:stats:{user.pk}`. All users see the same global stats,
but each user has a separate cache entry that expires independently. With 50
users all hitting the dashboard within a 5-minute window, the 5-minute TTL
produces 50 independent cold-path executions rather than 1. The legacy Phase 1
review called this out explicitly (§7 item 5: cache thundering herd).

**Fix:** use a single shared key `dashboard:stats:global` (or scoped by role
group if stats differ per role). This reduces cold-path queries from N-per-user
to 1 globally per TTL window.

**Behavior:** identical stats values (the underlying queries are already
global/unfiltered by user).

---

### M4 — `LicenseDocumentViewSet.get_queryset()` has no `select_related`
**File:** `backend/apps/license/views/license.py:311–312`

```python
def get_queryset(self):
    return LicenseDocumentModel.objects.filter(license_id=self._get_license_pk())
```

If `LicenseDocumentSerializer` (or any future field) accesses the parent
`license` FK, this will produce one extra query per document. Currently the
serializer only exposes `["id", "license", "type", "file"]` where `license` is
the integer FK ID, so this is a latent risk rather than a current N+1. Add
`select_related("license")` defensively.

---

### M5 — `ActivityLogViewSet` and `CeleryTaskTrackerViewSet` have no `select_related` and can grow to millions of rows
**File:** `backend/apps/core/views/masters.py:519`, `504`

Both use bare `queryset = Model.objects.all()` with no `select_related` and no
`ordering` override beyond `ordering_fields = "__all__"`. Activity logs
accumulate indefinitely. If either model has FK fields accessed by its
serializer, every list page generates N+1 queries. More critically, a
`COUNT(*)` pagination query over millions of unindexed rows can be slow.

Verify:
1. Both serializers do not access any FK traversals beyond integer IDs.
2. `created_on` (or equivalent timestamp) is indexed in the DB.

---

## LOW — Clean up, no immediate production impact

### L1 — `get_dashboard_stats` dead code block at line 205–207
**File:** `backend/apps/dashboard/services/dashboard_service.py:205–207`

```python
result = []
for i in range(11, -1, -1):
    # Walk back from 11 months ago to current month (inclusive), oldest-first
    pass
```

An empty `for` loop that sets `result = []` and then immediately falls through
to a second correct implementation. The `result = []` assignment at line 221
overwrites it. The dead loop is harmless but confusing and was presumably a
merge artifact.

---

### L2 — Balance service fires 4 round-trips per recompute — could be 1 with a CTE
**File:** `backend/apps/license/services/balance_service.py:56–122`

`_compute_credit`, `_compute_debit`, `_compute_allotment`, `_compute_trade`
each issue one `aggregate(Sum(...))` query. For the happy path (all four apps
installed) that is 4 queries plus 1 `get()` plus 2 `UPDATE`s = 7 round-trips
per recompute. This is acceptable and far better than the legacy Python-loop
approach. No change required unless profiling shows recompute throughput is
the bottleneck.

---

## PASSED

- **LicenseViewSet N+1 (legacy issue #8):** `get_queryset()` includes
  `select_related("exporter", "scheme_code", "notification_number", "port",
  "purchase_status", "balance", "flags", "notes", "ownership",
  "ownership__current_owner")` — all fields accessed by `LicenseListSerializer`
  and `LicenseDetailSerializer` are covered. No N+1.

- **AllotmentViewSet N+1 (legacy issue #11):** `get_queryset()` uses
  `select_related("company", "port", "related_company")` and
  `prefetch_related("allotment_details", "allotment_details__item",
  "allotment_details__item__license")`. Allotment detail items are correctly
  prefetched.

- **ImportItemViewSet:** `select_related("hs_code")` present — only FK accessed
  by `ImportItemSerializer` is `hs_code`.

- **IncentiveLicenseViewSet:** `select_related("exporter", "port_code")` —
  matches fields in `IncentiveLicenseSerializer`.

- **TaskViewSet:** `select_related("created_by", "assigned_to", "rejected_by")`
  and `prefetch_related("remarks__created_by")` — fully covered.

- **Master viewsets with FK:** `ItemNameViewSet`, `SionNormClassViewSet`,
  `ProductDescriptionViewSet`, `SIONExportViewSet`, `SIONImportViewSet`,
  `SionNormNoteViewSet`, `SionNormConditionViewSet`, `ItemHeadViewSet` all
  include appropriate `select_related` for their FK fields.

- **Pagination:** `DEFAULT_PAGINATION_CLASS = "shared.pagination.StandardPagination"`
  set globally in `REST_FRAMEWORK` (settings/base.py:174). No ViewSet disables
  it with `pagination_class = None`. Every list endpoint is paginated at 25
  rows by default (max 200).

- **Balance service — no Python-loop aggregation (legacy issue #1 root cause
  fixed):** All four balance components (`_compute_credit`, `_compute_debit`,
  `_compute_allotment`, `_compute_trade`) use DB-side `aggregate(Sum(...))` —
  no Python-level iteration over result sets.

- **Balance service — atomic transaction:** `recompute_license_balance` wraps
  all reads and writes in `transaction.atomic()`. The two `UPDATE` calls
  (`LicenseBalance`, `LicenseFlags`) are issued via `.filter().update()` —
  single SQL `UPDATE ... WHERE`, not Python loops.

- **Dashboard aggregations — correct pattern:** `get_dashboard_stats` uses
  `.count()` (DB-side `COUNT(*)`) and `.aggregate(Sum(...))` — no
  `len(queryset.all())` patterns. `get_monthly_activity` uses
  `TruncMonth` + `Count` annotation — correct.

- **Dashboard caching:** Redis cache with `CACHE_TTL = 300` (5 min) applied to
  all four dashboard functions. Cache key checked before any query is issued.

- **PDF/Excel generation (legacy issue #3 fixed):** Both
  `LicenseViewSet.generate_pdf` and `AllotmentViewSet.generate_pdf` dispatch
  Celery tasks and return `202 Accepted` with a `task_id`. No sync PDF
  generation blocking worker threads.

- **Celery task serialization:** both tasks accept `license_id: int` and
  `user_id: int` (plain scalars, not Django model instances) — no large pickle
  payloads. `CELERY_TASK_SERIALIZER = "json"` confirmed.

- **Balance recompute always async:** `ImportItemViewSet` create/update/destroy
  all call `recompute_license_balance_task.delay(license_pk)` — never inline.
  `recompute_balance` endpoint on `LicenseViewSet` also uses `.delay()`.

---

## Summary

| Severity | Count | Items |
|---|---|---|
| CRITICAL | 0 | — |
| HIGH | 2 | H1 (8 COUNT queries), H2 (race condition on concurrent recompute) |
| MEDIUM | 4 | M1 (?all=true no cap), M2 (acks_late), M3 (per-user cache keys), M4 (LicenseDocumentViewSet), M5 (ActivityLog/CeleryTaskTracker) |
| LOW | 2 | L1 (dead code), L2 (4 round-trips vs 1 CTE) |
| PASSED | 13 | All N+1 hot paths, pagination, balance aggregation, async PDF |

**Compared to legacy §7 bottlenecks:**

| Legacy Issue | Status in New Backend |
|---|---|
| License-list serializer N+1 | FIXED — full select_related coverage |
| Signal cascade on bulk writes | FIXED — balance recompute is async Celery |
| PDF/Excel in request thread | FIXED — Celery + 202 Accepted pattern |
| Materialized view staleness | N/A — new backend uses live queries with Redis cache |
| Cache thundering herd | PARTIAL — caching present but per-user keys (M3) |
