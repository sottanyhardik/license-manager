# Backend Architecture — Claude Context

> **Read this at the start of any backend development session.**

---

## Architecture in One Sentence

Django 6.x REST API serving `/api/v1/*` at port 8001. All business models use `managed=False` (tables owned by legacy backend). Service layer pattern: Views → Services → ORM. Async side effects via Celery.

---

## Critical Constraints

1. **NEVER run `makemigrations`** for these apps: `accounts`, `core`, `license`, `allotment`, `bill_of_entry`, `tasks`, `trade` — they are `managed=False`.
2. **All business logic in services** — views only call services, never ORM directly.
3. **Cross-app Celery, not signals** — `on_commit` callback dispatches tasks.
4. **Shared PostgreSQL** — legacy backend owns DDL; new backend is a read/write proxy.

---

## Project Layout

```
backend/
├── apps/
│   ├── accounts/     → User proxy, JWT, RBAC (15 role codes)
│   ├── core/         → 23 master models (Company, Port, HSCode, SION, etc.)
│   ├── license/      → Central license models + balance service
│   ├── allotment/    → Pre-auth allotments + planning
│   ├── bill_of_entry/→ BOE processing + dispute resolution
│   ├── trade/        → Purchase invoices + bills of supply
│   ├── tasks/        → Internal workflow task state machine
│   ├── dashboard/    → Read-only KPI aggregation
│   └── reports/      → Async report generation
├── config/
│   ├── settings/     → base + dev + prod + test + local
│   ├── celery.py
│   ├── urls.py       → /admin/, /api/health/, /api/v1/, /api/schema/, /api/docs/
│   └── api_urls.py   → all /api/v1/ sub-routes
└── shared/
    ├── models.py     → AuditModel base (but NOTE: core.models.masters.AuditModel is the one actually used)
    ├── serializers.py→ EnvelopeMixin
    ├── pagination.py → StandardPagination (25/page)
    ├── exceptions.py → custom_exception_handler
    └── permissions.py→ base permission classes
```

---

## AuditModel: Which One to Use

There are TWO AuditModel definitions:
- `shared.models.AuditModel` — has `created_at`, `updated_at`, `deleted_at`, `created_by`
- `apps.core.models.masters.AuditModel` — has `created_on`, `modified_on`, `created_by`, `modified_by`

**The concrete apps (license, allotment, boe, trade, tasks) import from `apps.core.models.masters`.**  
`shared.models.AuditModel` is orphaned (no concrete subclasses use it).  
This is a known discrepancy — do not introduce new classes inheriting from `shared.models.AuditModel`.

---

## Response Envelope

ALL API responses use this format:

```python
# shared/serializers.py: EnvelopeMixin.wrap()
{"success": True, "data": ..., "message": None}
{"success": False, "data": None, "errors": [...], "message": "Validation failed"}
```

Paginated responses add `"pagination"` key alongside `"data"`.

---

## User Model: has_any_role

Roles are Django Groups. Role membership check:
```python
user.has_any_role(["LICENSE_MANAGER", "LICENSE_VIEWER"])
# → self.groups.filter(name__in=role_codes).exists()
```

Superusers bypass all role checks in `BaseRolePermission.has_permission()`.  
`is_active` is checked FIRST, before `is_superuser`.

---

## Permission Class Map

| Module | Class | Read roles | Write roles |
|---|---|---|---|
| License | `LicensePermission` | MANAGER + VIEWER + TRADE_VIEWER/MANAGER | MANAGER only |
| Allotment | `AllotmentPermission` | ALLOTMENT_MANAGER + VIEWER | MANAGER only |
| BOE | `BillOfEntryPermission` | BOE_MANAGER + VIEWER + ACCOUNT_ACCESS + TL_GENERATE | MANAGER only |
| Trade | `TradePermission` | TRADE_MANAGER + VIEWER | MANAGER only |
| Incentive | `IncentiveLicensePermission` | INCENTIVE_LICENSE_MANAGER + VIEWER | MANAGER only |
| Reports | `ReportPermission` | REPORT_VIEWER + all MANAGER roles | (none) |
| Users | `UserManagementPermission` | USER_MANAGER | USER_MANAGER |

All classes: `is_active` AND `is_authenticated` checked before role check.

---

## Celery Task Reliability

All financial tasks MUST have:
```python
@shared_task(bind=True, acks_late=True, reject_on_worker_lost=True, max_retries=3)
```

- `acks_late=True` — message acknowledged AFTER task completes, not when picked up
- `reject_on_worker_lost=True` — message re-queued if worker crashes

Current tasks with this: `recompute_license_balance_task`, all 4 report generation tasks.

---

## Common Import Patterns

```python
# Lazy import inside function (prevents circular import at module load)
def _compute_debit(license_id):
    from apps.bill_of_entry.models import RowDetails
    ...

# Service layer calling another app's task
def _dispatch(item_ids):
    def _task():
        from apps.license.tasks import recompute_license_balance_task
        ...
    return _task
```

**Never** import cross-app models at module level in service files.

---

## Test Infrastructure

Tests use `managed=False` → `managed=True` patch applied via `conftest_managed.py`:

```python
# conftest_managed.py: pytest_sessionstart hook
for model in apps.get_models():
    if not model._meta.managed:
        model._meta.managed = True
```

This runs AFTER Django setup, creating SQLite tables for all managed=False models.

All business logic tests use `unittest.mock.patch` — NO `@pytest.mark.django_db` for service tests.

---

## CeleryTaskTracker Pattern (Reports)

For async reports, the tracker row must be created BEFORE `apply_async`:

```python
# CORRECT order (prevents tracker race condition):
task_id = str(uuid.uuid4())
_make_tracker(task_name=..., task_id=task_id, ...)  # INSERT first
task.apply_async(kwargs={...}, task_id=task_id)      # THEN dispatch

# WRONG order (race condition — worker can call _mark_started before tracker exists):
result = task.apply_async(...)
task_id = result.id
_make_tracker(task_id=task_id, ...)  # TOO LATE
```

---

## Redis Database Map

```
/1 → Django cache
/2 → Celery broker
/3 → Celery result backend
```

Never flush `/2` as a "cache clear" — you'd lose in-flight task messages.

---

## What NOT to Do

1. ❌ Never call `recompute_license_balance()` synchronously from a view
2. ❌ Never run `makemigrations` for managed=False apps
3. ❌ Never use `_safe_get_model` (removed — was silently zeroing balances)
4. ❌ Never pass import-item IDs to `recompute_license_balance_task` (expects license_id)
5. ❌ Never import cross-app models at module level in services
6. ❌ Never compare `transaction_type` to 'DEBIT' — the DB value is 'D'
7. ❌ Never use `q2(pct)` before dividing by 100 in trade — use `Decimal(str(pct))`
