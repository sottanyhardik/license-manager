# Reports Module

> **Source of truth** — generated from implementation.  
> Last updated: 2026-07-15 (feature/V1).

---

## 1. Purpose & Business Objective

Provides async generation of 4 report types over license data. Reports are dispatched as Celery tasks and stored as JSON files. A frontend polling mechanism tracks completion.

**Why async**: Reports aggregate large datasets across multiple tables. Synchronous generation would block gunicorn workers for 5-30+ seconds. The Celery+polling pattern keeps responses fast.

---

## 2. Report Types

| Type | Endpoint | Service | Purpose |
|---|---|---|---|
| Balance | `POST /api/v1/reports/balance/generate/` | `balance_report.py` | Per-license balance summary |
| Item | `POST /api/v1/reports/items/generate/` | `item_report.py` | Item utilisation across licenses |
| Pivot | `POST /api/v1/reports/pivot/generate/` | `pivot_report.py` | Items grouped by SION norm class |
| Ledger | `POST /api/v1/reports/ledger/generate/` | `ledger_report.py` | Full transaction history for one license |

---

## 3. CeleryTaskTracker Pattern

**Critical**: The tracker row is created BEFORE `apply_async`. A fast worker could call `_mark_started()` before the tracker row exists if order is reversed.

```python
# Correct order (views.py):
task_id = str(uuid.uuid4())                          # 1. pre-generate
_make_tracker(task_name=..., task_id=task_id, ...)   # 2. INSERT tracker row
task.apply_async(kwargs={...}, task_id=task_id)      # 3. dispatch
```

**Task lifecycle**:
```
PENDING  (created by view)
  ↓ worker picks up
STARTED  (_mark_started sets status + started_at)
  ↓ on success
SUCCESS  (_mark_success sets status + result + completed_at)
  ↓ on failure after retries
FAILURE  (_mark_failure sets status + traceback + completed_at)
  ↓ on retry attempt
RETRY    (intermediate state visible to polling)
```

---

## 4. Task Configuration

All 4 tasks use identical decorator:
```python
@shared_task(
    bind=True,
    max_retries=2,
    acks_late=True,           # ACK after completion, not pickup
    reject_on_worker_lost=True,  # Re-queue if worker crashes
    name="generate_{type}_report_task"
)
```

Tasks retry up to 2 times on exception (total 3 attempts).

---

## 5. Report Output

**Storage**: `media/reports/{type}_{task_id}.json`  
**Format**: JSON (all Decimal values serialized as strings via `default=str`)  
**Access**: Via status endpoint → `file_path` in result → protected media URL

**Balance report data shape**:
```json
{
  "licenses": [
    {
      "license_id": 1,
      "license_number": "DFIA/2024/001",
      "exporter": "Acme Exports Ltd",
      "balance_cif": "44000.00",
      "total_authorised": "50000.00",
      "debited_cif": "5000.00",
      "allotted_cif": "1000.00",
      "is_expired": false,
      "is_null": false
    }
  ],
  "generated_at": "2026-07-15T10:30:00Z",
  "format": "json"
}
```

⚠️ **Known Issue (C-001)**: Balance report re-implements aggregation logic instead of calling `balance_service._compute_*`. The trade component (`_compute_trade`) is missing. For licenses with trade sales, `balance_cif` in the report will be higher than the actual `LicenseBalance.balance_cif`. See `docs/improvements/improvement-register.md`.

---

## 6. All API Endpoints

**Auth**: JWT Bearer  
**Permission**: `ReportDispatchPermission` — any MANAGER role or REPORT_VIEWER

| Method | URL | Request body | Response |
|---|---|---|---|
| POST | `/reports/balance/generate/` | `{license_ids: [1,2,3], format: "json"}` | 202 `{task_id: "uuid"}` |
| POST | `/reports/items/generate/` | `{item_name_ids: [...], company_ids: [...], min_balance: 0.0, license_status: "active", expiry_date_from: "YYYY-MM-DD", expiry_date_to: "YYYY-MM-DD", format: "json"}` | 202 |
| POST | `/reports/pivot/generate/` | Same as items + `sion_norm: "..."` | 202 |
| POST | `/reports/ledger/generate/` | `{license_id: 1, format: "json"}` | 202 |
| GET | `/reports/status/{task_id}/` | — | `{task_id, status, file_url?, traceback?}` |

**Status response shape**:
```json
{
  "task_id": "abc-123",
  "status": "done",
  "file_url": "/api/v1/reports/download/abc-123/",
  "traceback": null
}
```

**Status mapping** (CeleryTaskTracker.status → UI status):
```python
_STATUS_MAP = {
    "PENDING": "pending",
    "STARTED": "running",
    "RETRY": "running",
    "SUCCESS": "done",
    "FAILURE": "error",
    "REVOKED": "error",
}
```

---

## 7. Filter Validation (Security Fix)

`ItemReportRequestSerializer` and `PivotReportRequestSerializer` use typed fields instead of free-form `DictField`. This prevents unknown key injection into Celery task args.

```python
# Typed fields (after security fix):
item_name_ids = ListField(child=IntegerField(min_value=1), ...)
company_ids = ListField(child=IntegerField(min_value=1), ...)
min_balance = FloatField(required=False)
license_status = ChoiceField(choices=["active", "all"])
expiry_date_from = RegexField(r"^\d{4}-\d{2}-\d{2}$", ...)
expiry_date_to = RegexField(...)
sion_norm = CharField(...)  # pivot only
```

---

## 8. Frontend Components

| Component | Purpose |
|---|---|
| `ReportsIndex.tsx` | Landing page with 4 report type cards |
| `BalanceReport.tsx` | License selector + format picker + Generate button |
| `ItemReport.tsx` | Filter form (item names, companies, dates, balance threshold) |
| `PivotReport.tsx` | Same as item + SION norm filter |
| `LedgerReport.tsx` | Single license selector |
| `ReportGenerator.tsx` | Shared generate/download button with loading state |
| `ReportTaskStatus.tsx` | Polling component — shows spinner/done/error |
| `LicenseSelector.tsx` | Multi-select for balance report |
| `hooks/useReportTask.ts` | TanStack Query hook for status polling |

**Routes**: `/reports`, `/reports/balance`, `/reports/items`, `/reports/pivot`, `/reports/ledger`

---

## 9. Cross-References

- Balance formula divergence: `docs/business-rules/calculation-engine.md` §15
- CeleryTaskTracker pattern: `docs/claude/backend-context.md` §CeleryTaskTracker Pattern
- Async task lifecycle: `docs/state-machines/entities.md` §5 Celery Report Task State
- Improvement: `docs/improvements/improvement-register.md` C-001
