# Security Audit — Phase 1 (feature/V1)
Date: 2026-07-14
Auditor: security-auditor agent

---

## Executive Summary

The new `backend/` Django 6.x app is a sound rebuild. Secret handling is correct
(env-var only in production), the RBAC framework is well-structured, ORM usage is
safe (no raw SQL), and the JWT pipeline is properly configured with rotation and
blacklisting. The principal risks are:

- An **IDOR in the BOE row sub-resource** that allows any authenticated
  BOE_MANAGER to edit or delete rows belonging to BOEs they did not create,
  simply by supplying an arbitrary `row_id`. This is the only finding that must
  be closed before merge.
- An **unvalidated Celery `filters` dict** passed directly as `**kwargs` to
  report service functions. A malicious or buggy caller can inject unexpected
  keyword arguments that alter query behaviour or cause 500s in the worker.
- A **missing `is_active` check** in `BaseRolePermission` (the root of all RBAC
  classes), meaning a deactivated user whose JWT has not yet expired retains
  full role-based access to every protected endpoint.
- The **API schema and Swagger UI are publicly reachable** without authentication,
  leaking the full internal data model.
- **No rate limiting** is configured on the login endpoint, enabling
  credential-stuffing attacks at network speed.

Overall verdict: **CONDITIONAL PASS** — merge is blocked only by finding H1
(IDOR). H2, H3, M1, and M2 should be remediated before the first production
deployment.

---

## Findings

### CRITICAL

_No critical findings._

---

### HIGH

#### H1 — IDOR on BOE Row Sub-Resource
**Severity:** High
**Location:**
- `backend/apps/bill_of_entry/services/boe_service.py:348` (`update_row_detail`)
- `backend/apps/bill_of_entry/services/boe_service.py:370` (`delete_row_detail`)
- `backend/apps/bill_of_entry/services/boe_service.py:198` (`resolve_dispute_row`)
- `backend/apps/bill_of_entry/views/boe.py:86–120` (`row_detail` action)
- `backend/apps/bill_of_entry/views/boe.py:127–148` (`resolve_dispute` action)

**What & why:**
The `row_detail` action in `BillOfEntryViewSet` receives a `{pk}` (the BOE id)
and a `{row_id}` from the URL. Both the view and the underlying service functions
look up the `RowDetails` row solely by primary key:

```python
row = RowDetails.objects.get(pk=row_id)   # no bill_of_entry filter
```

There is no check that the retrieved `RowDetails` row belongs to the BOE
identified by `{pk}`. Any authenticated user with `BOE_MANAGER` (or
`BOE_VIEWER` for GET on the parent) can:

1. `PATCH /api/v1/bill-of-entries/1/rows/9999/` — supply a `row_id` (9999) that
   belongs to a completely different BOE. The service modifies it if it exists.
2. `DELETE /api/v1/bill-of-entries/1/rows/9999/` — same pattern.
3. `POST /api/v1/bill-of-entries/1/rows/9999/resolve-dispute` — same pattern.

Exploit path: attacker iterates `row_id` from 1 upward; for each existing row
the system silently applies the supplied `data` or deletes the row, corrupting
financial records of other BOEs without any error.

**Fix:**
In all three service functions, replace the bare `get(pk=row_id)` with:

```python
row = RowDetails.objects.get(pk=row_id, bill_of_entry_id=boe_id)
```

The `boe_id` must be passed from the view (it is already available as `int(pk)`
in `row_detail`). For `resolve_dispute_row`, the view already has the BOE object;
pass `boe.pk` and add the constraint. This single-line change eliminates the
IDOR.

**Confidence:** High — verified by reading service function signatures and view
code. Confirm with:
```
PATCH /api/v1/bill-of-entries/1/rows/<id_from_different_boe>/ with valid token
```
Expect 404 after fix, 200 before.

---

#### H2 — Missing `is_active` Guard in `BaseRolePermission`
**Severity:** High
**Location:** `backend/apps/accounts/permissions.py:31–49` (`BaseRolePermission.has_permission`)

**What & why:**
`BaseRolePermission` (the parent of every app-specific permission class:
`LicensePermission`, `AllotmentPermission`, `BillOfEntryPermission`,
`TradePermission`, `IncentiveLicensePermission`, etc.) checks
`request.user.is_authenticated` but does **not** check `request.user.is_active`.

SimpleJWT does not re-validate `is_active` on every request. A user deactivated
in the Django admin (`is_active=False`) continues to make authenticated API calls
until their access token expires (30 minutes by default per `base.py:192`). If
the refresh token (7-day lifetime) is not manually blacklisted, the user can
re-obtain new access tokens indefinitely.

Compare with `shared/permissions.py:12` (`IsAuthenticatedAndActive`) which
correctly includes `request.user.is_active` — `BaseRolePermission` does not
inherit from it.

**Fix:**
Add `is_active` to the authentication guard in `BaseRolePermission`:

```python
def has_permission(self, request, view):
    if not request.user or not request.user.is_authenticated:
        return False
    if not request.user.is_active:          # ADD THIS
        return False
    if request.user.is_superuser:
        return True
    ...
```

Alternatively, configure SimpleJWT with `"USER_AUTHENTICATION_RULE":
"rest_framework_simplejwt.authentication.default_user_authentication_rule"`
(the default) and verify `check_blacklist` is active — but the explicit check in
the permission class is the safer belt-and-suspenders approach.

**Confidence:** High — confirmed by reading both permission files.

---

#### H3 — Unvalidated `filters` Dict Passed as `**kwargs` to Report Services
**Severity:** High
**Location:**
- `backend/apps/reports/tasks.py:121` (`generate_item_report_task`)
- `backend/apps/reports/tasks.py:146` (`generate_pivot_report_task`)
- `backend/apps/reports/views.py:74–76` (`ItemReportRequestSerializer.filters`)

**What & why:**
The `ItemReportRequestSerializer` accepts a free-form `DictField`:

```python
filters = serializers.DictField(default=dict, required=False)
```

This dict is stored in the Celery task kwargs and, inside the worker, passed
verbatim to the service:

```python
data = generate_item_report(**filters)
```

`generate_item_report` in `item_report.py` accepts specific keyword arguments
(`item_name_ids`, `company_ids`, `min_balance`, `license_status`,
`expiry_date_from`, `expiry_date_to`). Any key in `filters` that does **not**
match one of these function parameters causes `TypeError: unexpected keyword
argument` — a worker exception that is retried up to 2 times, holding the Celery
slot. More seriously, if the service function signature is ever extended to
include an ORM-query-building parameter, a caller can inject arbitrary filter
logic.

This also applies to `generate_pivot_report` (same pattern at line 146).

**Fix — Option A (recommended):** Replace `DictField` with an explicit typed
serializer:

```python
class ItemReportRequestSerializer(serializers.Serializer):
    item_name_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, default=list
    )
    company_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, default=list
    )
    min_balance = serializers.DecimalField(
        max_digits=15, decimal_places=2, required=False, allow_null=True
    )
    license_status = serializers.ChoiceField(
        choices=["active", "all"], default="active"
    )
    expiry_date_from = serializers.DateField(required=False, allow_null=True)
    expiry_date_to   = serializers.DateField(required=False, allow_null=True)
    format = serializers.ChoiceField(choices=["json", "pdf", "excel"], default="json")
```

**Fix — Option B (minimal):** Add a whitelist in the task:

```python
ALLOWED_ITEM_FILTER_KEYS = {
    "item_name_ids", "company_ids", "min_balance",
    "license_status", "expiry_date_from", "expiry_date_to",
}
safe_filters = {k: v for k, v in filters.items() if k in ALLOWED_ITEM_FILTER_KEYS}
data = generate_item_report(**safe_filters)
```

**Confidence:** High — confirmed by reading serializer, task, and service.

---

### MEDIUM

#### M1 — API Schema and Swagger UI Publicly Accessible (No Auth)
**Severity:** Medium
**Location:**
- `backend/config/urls.py:10–15` (`api/schema/` and `api/docs/`)
- `backend/config/settings/base.py:203–207` (`SPECTACULAR_SETTINGS`)

**What & why:**
`SpectacularAPIView` and `SpectacularSwaggerUIView` are mounted with no
`permission_classes` override. DRF Spectacular's default is to inherit
`DEFAULT_PERMISSION_CLASSES` (`IsAuthenticated`), but `SpectacularAPIView` by
default allows unauthenticated access to the schema when
`SERVE_INCLUDE_SCHEMA: False` (the setting only controls the schema endpoint
link inside the generated spec, not authentication). An unauthenticated request
to `/api/schema/` returns the full OpenAPI YAML with all endpoint paths, query
parameters, and model field names.

This is not critical because there is no authentication bypass, but it provides
a complete map of the attack surface to an unauthenticated attacker, and
constitutes data exposure of internal data-model field names (license numbers,
exporter names, etc.) in schema examples.

**Fix:**
Add explicit authentication to both views in `config/urls.py`:

```python
from rest_framework.permissions import IsAuthenticated, IsAdminUser

path("api/schema/",
     SpectacularAPIView.as_view(permission_classes=[IsAdminUser]),
     name="schema"),
path("api/docs/",
     SpectacularSwaggerUIView.as_view(
         url_name="schema",
         permission_classes=[IsAdminUser],
     ),
     name="swagger-ui"),
```

**Confidence:** High. Confirm with `curl /api/schema/` (no `Authorization` header)
— expect 401 after fix.

---

#### M2 — No Rate Limiting on Login Endpoint
**Severity:** Medium
**Location:**
- `backend/apps/accounts/views.py:26–62` (`LoginView`)
- `backend/config/settings/base.py:170–186` (`REST_FRAMEWORK`)

**What & why:**
`LoginView` uses `AllowAny` and `authentication_classes = []` (correct for a
login endpoint) but the `REST_FRAMEWORK` settings contain no
`DEFAULT_THROTTLE_CLASSES` or `DEFAULT_THROTTLE_RATES`. The endpoint accepts
unlimited username/password pairs at full network speed, enabling
credential-stuffing and brute-force attacks with zero friction.

In a multi-tenant enterprise app handling import/export licenses (financial data),
account takeover is a high-impact outcome.

**Fix:**
Add DRF throttle configuration to `base.py`:

```python
REST_FRAMEWORK = {
    ...
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "20/min",       # covers login brute-force
        "user": "1000/hour",    # covers authenticated API abuse
    },
}
```

For the login endpoint specifically, a tighter scope is advisable:

```python
class LoginView(APIView):
    throttle_scope = "login"
    ...
```

with `"login": "5/min"` in `DEFAULT_THROTTLE_RATES`.

**Confidence:** High — no throttle classes found anywhere in the codebase.

---

#### M3 — `report_type` Parameter Passed Unvalidated to Celery Task
**Severity:** Medium
**Location:**
- `backend/apps/license/views/license.py:203–204` (`LicenseViewSet.generate_pdf`)
- `backend/apps/license/tasks.py:39–64` (`generate_license_pdf_task`)

**What & why:**
The `generate_pdf` action reads `report_type` directly from the request body
without validation:

```python
report_type = request.data.get("report_type", "license_detail")
result = generate_license_pdf_task.delay(int(pk), report_type, request.user.id)
```

The value is logged at `INFO` level inside the task:
```python
logger.info("...report_type=%s...", report_type, ...)
```

As the task is currently a stub, the impact is low today. However, when Phase 8
implements the actual PDF renderer, an unvalidated `report_type` passed as a file
path fragment or template name could enable path traversal or template injection
depending on how the renderer consumes it. The `pdf_type` parameter in
`generate_trade_pdf_task` (`trade/tasks.py:8`) has the same pattern.

**Fix:**
Add a `ChoiceField` validation at the view level before dispatching:

```python
VALID_REPORT_TYPES = {"license_detail", "balance_report", "ledger"}
report_type = request.data.get("report_type", "license_detail")
if report_type not in VALID_REPORT_TYPES:
    return Response(
        EnvelopeMixin.wrap(success=False, message="Invalid report_type."),
        status=status.HTTP_400_BAD_REQUEST,
    )
```

**Confidence:** High for current state (low impact); flag as mandatory before PDF
renderer is implemented.

---

#### M4 — `LedgerUploadView` Accepts Any File Without MIME/Extension Validation
**Severity:** Medium
**Location:** `backend/apps/bill_of_entry/views/ledger.py:14–31`

**What & why:**
`LedgerUploadView` accepts a multipart file upload (protected by
`BillOfEntryPermission`). The handler performs no file type, extension, or size
validation:

```python
file_obj = request.FILES.get("file")
if not file_obj:
    return Response(...)
task_id = f"ledger-upload-stub-{file_obj.name}"
```

Currently this is a stub that does not process the file, but `file.name` is
embedded in the response `task_id` field. An attacker with `BOE_MANAGER` role
could upload a file named `../../etc/passwd` and observe whether the server
path-traverses (response leaks the path fragment). More critically, when the stub
is replaced with real processing, the absence of validation is a path-traversal
and arbitrary-file-write risk.

**Fix:**
Add validation now, before the implementation lands:

```python
ALLOWED_LEDGER_EXTENSIONS = {".xlsx", ".xls", ".csv"}
import os
_, ext = os.path.splitext(file_obj.name)
if ext.lower() not in ALLOWED_LEDGER_EXTENSIONS:
    return Response(
        {"detail": "Unsupported file type. Allowed: xlsx, xls, csv."},
        status=status.HTTP_400_BAD_REQUEST,
    )
MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB
if file_obj.size > MAX_UPLOAD_BYTES:
    return Response({"detail": "File too large."}, status=status.HTTP_400_BAD_REQUEST)
```

Do not trust the client-supplied `file.name` for storage — use a random UUID
filename in `upload_to`.

**Confidence:** High — confirmed by reading the view; stub status confirmed.

---

### LOW / INFO

#### L1 — `is_superuser` Flag Exposed in All User Serializer Responses
**Severity:** Low / Info
**Location:** `backend/apps/accounts/serializers.py:50–65` (`UserSerializer`)

**What & why:**
`UserSerializer` includes `is_superuser` in the response for `/me/` and the
login response. All users can see their own `is_superuser` flag (expected), but
the field is also included in `UsersListSerializer` (exposed via
`/api/v1/auth/users/`). The users-list endpoint is protected by `IsAdminUser`
(staff-only), so the exposure is bounded. However, disclosing superuser status
to any staff user creates a map of privileged accounts that a compromised staff
account could target.

**Fix:** Consider removing `is_superuser` from `UsersListSerializer.fields`; it
is not needed by any front-end feature documented in the API contract.

**Confidence:** High.

---

#### L2 — Dev Settings Fallback Secret Key in Source Code
**Severity:** Low / Info
**Location:** `backend/config/settings/dev.py:5`

**What & why:**
```python
SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-key-not-for-production-use")
```

A developer who accidentally starts the server with `DJANGO_SETTINGS_MODULE=config.settings.dev`
in a CI or staging environment that does not set `SECRET_KEY` will run with a
well-known fixed secret, making all JWT tokens forgeable. The `# noqa: S105`
suppresses the Bandit warning, meaning CI will not catch this.

The prod settings (`prod.py`) correctly hard-fail if `SECRET_KEY` is missing.
The dev fallback is acceptable for local development, but should not have the
Bandit warning suppressed.

**Fix:** Remove the `# noqa: S105` suppression so Bandit reports it; add a
comment warning that this value must never be used outside a local laptop.

**Confidence:** High.

---

#### L3 — Task Ownership: Any Authenticated User Can Poll Any Report Task Status
**Severity:** Low / Info
**Location:** `backend/apps/reports/views.py:256–290` (`ReportTaskStatusView`)

**What & why:**
`GET /reports/task/{task_id}/status/` is protected by `ReportDispatchPermission`
(any report-role user). The task_id is a Celery UUID. Any user with a
report role can poll the status of a task they did not create by guessing or
enumerating UUIDs. The response includes `file_url` — a URL to the generated
report file in media. This allows cross-user data access for report files.

Because Celery task IDs are version-4 UUIDs (128-bit random), brute-force
enumeration is not feasible. However, a server log or error message disclosing
another user's `task_id` would allow access to their report.

**Fix:** Store `user_id` in `CeleryTaskTracker` at creation time and add a check
in `ReportTaskStatusView`:

```python
if tracker.user_id and tracker.user_id != request.user.pk and not request.user.is_superuser:
    return Response({"detail": "Not found."}, status=status.HTTP_404_NOT_FOUND)
```

**Confidence:** Medium — impact depends on whether task IDs are ever disclosed
outside the requesting user's session.

---

#### L4 — Unauthenticated Health Check Endpoint
**Severity:** Low / Info
**Location:** `backend/config/urls.py:8` and `backend/shared/views.py:4–8`

**What & why:**
`GET /api/health/` returns `{"status": "ok", "version": "1.0.0"}` without
authentication. This is standard practice for load-balancer health checks and is
not a vulnerability in isolation. The version number (`1.0.0`) is a minor
information disclosure (confirms app version to an unauthenticated probe). The
health check apps (`health_check.db`, `health_check.cache`) are in
`INSTALLED_APPS` but their endpoints are not mounted in `urls.py`, so DB/cache
status is not exposed.

**Fix:** Consider removing the `version` field from the health response:
`{"status": "ok"}` is sufficient for load-balancers.

**Confidence:** High.

---

#### L5 — `?all=true` Bypass on Master ViewSets (DoS via Large Payload)
**Severity:** Low / Info
**Location:** `backend/apps/core/views/masters.py:155–161`
(`MasterViewSetMixin.list`)

**What & why:**
`MasterViewSetMixin` supports `?all=true` to return unpaginated lists for
dropdown use. Any authenticated user (minimum `IsAuthenticated`) can trigger this
on potentially large tables (`PortViewSet` comments note 500+ rows; `HSCodeModel`
can have thousands). This is not an injection risk, but repeated `?all=true`
requests to `hs-codes` by a malicious authenticated user could degrade server
performance.

**Fix:** Scope `?all=true` to staff users only, or add a maximum return cap
(e.g., 1000 rows) with a warning header:

```python
if request.query_params.get("all", "").lower() == "true":
    if not request.user.is_staff:
        raise PermissionDenied("?all=true requires staff access.")
```

**Confidence:** High.

---

## Summary Table

| ID | Severity | Area                         | Must-Fix Before Merge |
|----|----------|------------------------------|-----------------------|
| H1 | HIGH     | IDOR — BOE row sub-resource  | YES                   |
| H2 | HIGH     | RBAC — missing is_active     | Before prod deploy    |
| H3 | HIGH     | Celery — unvalidated filters | Before prod deploy    |
| M1 | MEDIUM   | API schema exposed           | Before prod deploy    |
| M2 | MEDIUM   | No login rate limiting       | Before prod deploy    |
| M3 | MEDIUM   | report_type unvalidated      | Before PDF impl       |
| M4 | MEDIUM   | File upload no validation    | Before stub → real    |
| L1 | LOW      | is_superuser in list API     | Optional              |
| L2 | LOW      | Dev fallback secret key      | Optional              |
| L3 | LOW      | Task status cross-user read  | Optional              |
| L4 | LOW      | Health check version leak    | Optional              |
| L5 | LOW      | ?all=true DoS surface        | Optional              |

---

## What Was Checked and Found Clean

- **No raw SQL / `.extra()` / `RawSQL()`** — confirmed by full-codebase grep.
  All ORM queries use typed FilterSets and parameterised lookups.
- **No hardcoded secrets** — `SECRET_KEY` is env-var only in production;
  dev fallback is clearly labelled.
- **JWT configuration** — `ROTATE_REFRESH_TOKENS=True`,
  `BLACKLIST_AFTER_ROTATION=True`, 30-minute access token lifetime. Logout
  correctly blacklists the refresh token. Token refresh is wrapped correctly.
- **CORS** — `CORS_ALLOWED_ORIGINS` read from env; empty list is the default
  (no CORS wildcard). No `CORS_ALLOW_ALL_ORIGINS` found.
- **CSRF** — DRF's JWT-only auth means CSRF protection is not the primary line
  of defence; `CsrfViewMiddleware` is still present in the middleware stack. No
  `@csrf_exempt` decorators found outside the standard DRF path.
- **Password handling** — `write_only=True` on the password field;
  `django.contrib.auth.authenticate` used (constant-time); `is_active` checked
  in `LoginSerializer.validate`.
- **Object-level access** — viewsets use `get_object()` (which calls
  `check_object_permissions()`) for all retrieve/update/destroy paths. The IDOR
  at H1 is a sub-resource path, not the main object path.
- **RBAC completeness** — every ViewSet has explicit `permission_classes`. The
  `MasterWritePermission` correctly gates writes but opens reads to all
  authenticated users (correct for reference data). `MasterChangeViewSet`,
  `CeleryTaskTrackerViewSet`, and `ActivityLogViewSet` are correctly restricted
  to `IsAdminUser`. No endpoint found with `AllowAny` other than `LoginView`
  (by design).
- **`select_for_update()` in balance service** — `recompute_license_balance`
  wraps the read-compute-write cycle in `transaction.atomic()` and uses
  `select_for_update()` on the license row; `update_or_create` prevents race
  conditions on the balance and flags rows.
- **Celery task safety** — `acks_late=True, reject_on_worker_lost=True` on
  balance and trade tasks. Report tasks lack `acks_late` (low risk since they
  are idempotent).

---

## Verdict

**CONDITIONAL PASS**

The codebase is production-quality in structure and intent. One finding (H1 —
IDOR on BOE rows) must be fixed before merge because it permits silent corruption
of financial records with a valid session token. H2 and H3 are deployment
blockers and should be addressed immediately after merge. All remaining findings
are defence-in-depth improvements.

### Top 3 Must-Fix Before Merge

1. **H1** — `backend/apps/bill_of_entry/services/boe_service.py` lines 198, 348,
   370: add `bill_of_entry_id=boe_id` to all `RowDetails.objects.get(pk=row_id)`
   lookups so cross-BOE row manipulation is impossible.

2. **H2** — `backend/apps/accounts/permissions.py:37`: add
   `request.user.is_active` check to `BaseRolePermission.has_permission` so
   deactivated users are immediately locked out regardless of token validity.

3. **H3** — `backend/apps/reports/views.py:74–76` and `tasks.py:121,146`:
   replace `DictField(default=dict)` with a typed serializer for report filters
   and remove the `**filters` dict-splat in report tasks.
