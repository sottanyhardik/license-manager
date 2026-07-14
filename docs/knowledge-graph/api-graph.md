# API Graph

> Living document. Each row is added when the endpoint is implemented in `backend/`.
> Legacy endpoints live at `/api/*`. New endpoints live at `/api/v1/*`.

## Endpoint Count by App

> Full legacy contract: `docs/api-contract/legacy-v1.yaml`
> All endpoints catalogued 2026-07-14 from URL files only (fast-path pass).

| App | Endpoint Group | Legacy Prefix | Endpoint Count | Parity Status |
|---|---|---|---|---|
| system | Health, schema, media | /api/ | 6 | done |
| auth | Login, logout, me, refresh, password-reset, users CRUD + actions | /api/auth/ | 16 | done |
| masters | 14 resource types (companies, ports, HS codes, SION, items, etc.) + throttle | /api/masters/ | 91 | done |
| licenses | License CRUD + actions, items, plans, ledger, inventory, incentive, reports, dashboard, upload | /api/ | 47 | done |
| allotments | Allotment CRUD + allotment-actions | /api/ | 8 | done |
| bill_of_entry | BOE CRUD + parse-pdf + generate-transfer-letter | /api/ | 8 | done |
| trades | Trade CRUD + lines + payments + generate-transfer-letter | /api/ | 19 | done |
| tasks | Task CRUD + complete/reject/reopen + remarks + assignable_users | /api/ | 12 | done |
| **Total** | | | **~207** | **all done** |

> Note: counts include both collection (`/`) and detail (`/{id}/`) routes and
> all custom actions. Masters count is high because 14 resource types × 6
> CRUD methods = 84, plus 5 throttle endpoints and 2 activity-log read-only
> endpoints = 91.

## Parity Tracker (representative sample)

| New Endpoint | Legacy Equivalent | Auth | Method | Status |
|---|---|---|---|---|
| /api/v1/auth/login/ | /api/auth/login/ | none | POST | done |
| /api/v1/auth/logout/ | /api/auth/logout/ | JWT | POST | done |
| /api/v1/auth/refresh/ | /api/auth/refresh/ | none | POST | done |
| /api/v1/licenses/ | /api/licenses/ | JWT+role | GET, POST | done |
| /api/v1/licenses/{id}/ | /api/licenses/{id}/ | JWT+role | GET, PATCH, DELETE | done |
| /api/v1/allotments/ | /api/allotments/ | JWT+role | GET, POST | done |
| /api/v1/bill-of-entries/ | /api/bill-of-entries/ | JWT+role | GET, POST | done |
| /api/v1/trades/ | /api/trades/ | JWT+role | GET, POST | done |
| /api/v1/tasks/ | /api/tasks/ | JWT | GET, POST | done |
| /api/v1/masters/companies/ | /api/masters/companies/ | JWT | GET, POST | done |

> Full endpoint list with all methods, descriptions, and parity flags is in
> `docs/api-contract/legacy-v1.yaml`.

## API Response Envelope

All `/api/v1/` responses use:

```json
{
  "success": true,
  "data": {},
  "message": null
}
```

```json
{
  "success": false,
  "data": null,
  "errors": [{"field": "...", "message": "..."}],
  "message": "Validation failed"
}
```

## URL Routing (nginx)

```
/api/v1/*   → backend/ (new Django app, port 8001)
/api/*      → legacy/backend/ (existing, port 8000)
/           → frontend/ dist (new React app)
```
