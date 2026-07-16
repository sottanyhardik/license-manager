# 04 — API Reference

All endpoints are prefixed with `/api/`. Authentication: `Authorization: Bearer <access_token>` header required on all endpoints except `/api/auth/login/` and `/api/health/`.

---

## Authentication (`/api/auth/`)

| Method | Path | Description |
|---|---|---|
| POST | `/api/auth/login/` | Authenticate; returns `{access, refresh, user}` |
| POST | `/api/auth/logout/` | Blacklist refresh token |
| GET | `/api/auth/me/` | Current user profile |
| PUT/PATCH | `/api/auth/me/` | Update own profile |
| POST | `/api/auth/refresh/` | Refresh access token |
| GET | `/api/auth/users/` | List users (USER_MANAGER / superuser) |
| POST | `/api/auth/users/` | Create user |
| GET | `/api/auth/users/:id/` | Get user |
| PUT/PATCH | `/api/auth/users/:id/` | Update user |
| DELETE | `/api/auth/users/:id/` | Delete user |
| POST | `/api/auth/users/:id/reset-password/` | Reset user password |
| GET | `/api/auth/users/available-roles/` | List 15 available role codes |

---

## Licenses (`/api/licenses/`)

### CRUD
| Method | Path | Description |
|---|---|---|
| GET | `/api/licenses/` | List licenses (paginated, filtered) |
| POST | `/api/licenses/` | Create license |
| GET | `/api/licenses/:id/` | Get license detail |
| PUT/PATCH | `/api/licenses/:id/` | Update license |
| DELETE | `/api/licenses/:id/` | Delete license |

**Key Query Params** (GET list):
- `search` — license_number, exporter, port, sion_norm
- `license_type` — `DFIA` | `INCENTIVE` | `ALL`
- `is_active` — boolean
- `is_expired` — boolean
- `is_null` — boolean
- `company` — importer company ID
- `ordering` — e.g. `-license_date`
- `purchase_status` — comma-separated codes (e.g. `GE,MI,GO`)
- `active_only` — boolean

### Custom Actions
| Method | Path | Description |
|---|---|---|
| GET | `/api/licenses/:id/nested_items/` | Load nested items on demand |
| GET | `/api/licenses/:id/item-usage/` | BOE + allotment usage for item |
| GET | `/api/licenses/:id/balance_pdf/` | Generate balance PDF |
| POST | `/api/licenses/bulk_balance_excel/` | Multi-license Excel export |
| POST | `/api/licenses/parse-pdf/` | OCR parse uploaded license PDF |

---

## License Ledger (`/api/license-ledger/`)

| Method | Path | Description |
|---|---|---|
| GET | `/api/license-ledger/` | Paginated license ledger list |
| GET | `/api/license-ledger/:id/` | Single license ledger |
| GET | `/api/license-ledger/:id/ledger_detail/` | Per-company transaction detail |

**Key Query Params**:
- `company` — filter by importer company ID
- `purchase_date_from` / `purchase_date_to` — date range
- `license_type` — `ALL` | `DFIA` | `INCENTIVE`
- `active_only` — boolean
- `no_purchases` — show licenses with no purchase transactions

---

## Incentive Licenses (`/api/incentive-licenses/`)

Standard CRUD endpoint (`GET`, `POST`, `PUT/PATCH`, `DELETE`).

---

## Bill of Entry (`/api/bill-of-entries/`)

| Method | Path | Description |
|---|---|---|
| GET | `/api/bill-of-entries/` | List BOEs |
| POST | `/api/bill-of-entries/` | Create BOE |
| GET | `/api/bill-of-entries/:id/` | Get BOE |
| PUT/PATCH | `/api/bill-of-entries/:id/` | Update BOE |
| DELETE | `/api/bill-of-entries/:id/` | Delete BOE |
| POST | `/api/bill-of-entries/:id/generate-transfer-letter/` | Generate transfer letter |

---

## Allotments (`/api/allotments/`)

| Method | Path | Description |
|---|---|---|
| GET | `/api/allotments/` | List allotments |
| POST | `/api/allotments/` | Create allotment |
| GET | `/api/allotments/:id/` | Get allotment |
| PUT/PATCH | `/api/allotments/:id/` | Update allotment |
| DELETE | `/api/allotments/:id/` | Delete allotment |
| GET | `/api/allotment-actions/:id/` | Full allotment detail with line items + filters |
| POST | `/api/allotment-actions/:id/generate-transfer-letter/` | Generate transfer letter |

---

## Trades (`/api/trades/`)

| Method | Path | Description |
|---|---|---|
| GET | `/api/trades/` | List trades |
| POST | `/api/trades/` | Create trade |
| GET | `/api/trades/:id/` | Get trade |
| PUT/PATCH | `/api/trades/:id/` | Update trade |
| DELETE | `/api/trades/:id/` | Delete trade |
| POST | `/api/trades/:id/generate-transfer-letter/` | Generate transfer letter |

---

## Tasks (`/api/tasks/`)

| Method | Path | Description |
|---|---|---|
| GET | `/api/tasks/` | List tasks (own tasks only; superuser sees all) |
| POST | `/api/tasks/` | Create task |
| GET | `/api/tasks/:id/` | Get task |
| PUT/PATCH | `/api/tasks/:id/` | Update task |
| DELETE | `/api/tasks/:id/` | Delete task |
| POST | `/api/tasks/:id/complete/` | Mark task completed |
| POST | `/api/tasks/:id/reject/` | Reject task (body: `{reason}`) |
| POST | `/api/tasks/:id/reopen/` | Reopen rejected/completed task |
| GET | `/api/tasks/:id/remarks/` | List remarks on task |
| POST | `/api/tasks/:id/remarks/` | Add remark |
| GET | `/api/tasks/assignable_users/` | List users who can be assigned tasks |

---

## Ledger Upload (`/api/upload-ledger/`, `/api/ledger-task-status/`)

| Method | Path | Description |
|---|---|---|
| POST | `/api/upload-ledger/` | Upload CSV/HTM ledger files |
| GET | `/api/ledger-task-status/:task_id/` | Poll Celery task status |

**POST body**: `multipart/form-data` with file(s) field.

**Response**: `{tasks: [{license, task_id}], file}` per uploaded file.

**Task status response**:
```json
{
  "state": "SUCCESS" | "FAILURE" | "PENDING" | "PROGRESS",
  "result": { ... },
  "progress": 42,
  "error": "error message if failed"
}
```

---

## Masters (`/api/masters/`)

All masters follow standard CRUD: `GET`, `POST`, `PUT/PATCH`, `DELETE`.

| Endpoint | Model |
|---|---|
| `/api/masters/companies/` | CompanyModel |
| `/api/masters/ports/` | PortModel |
| `/api/masters/hs-codes/` | HSCodeModel |
| `/api/masters/sion-classes/` | SionNormClassModel |
| `/api/masters/item-names/` | ItemNameModel |
| `/api/masters/exchange-rates/` | ExchangeRateModel |
| `/api/masters/transfer-letters/` | TransferLetterModel |
| `/api/masters/purchase-statuses/` | PurchaseStatus |
| `/api/masters/scheme-codes/` | SchemeCode |
| `/api/masters/notification-numbers/` | NotificationNumber |
| `/api/masters/groups/` | Group (Django) |
| `/api/masters/activity-logs/` | ActivityLog (read-only) |

---

## Reports

| Method | Path | Description |
|---|---|---|
| GET | `/api/dashboard/` | Dashboard KPI data |
| GET | `/api/expiring-licenses/` | Licenses expiring within N days |
| GET | `/api/active-licenses/` | All active licenses with balances |
| GET | `/api/item-pivot/` | Item pivot report (by SION norm) |
| GET | `/api/item-pivot/available-norms/` | Available SION norm classes for pivot |
| GET | `/api/item-report/` | Item-level balance report |
| GET | `/api/inventory-balance/` | Full inventory balance |
| GET | `/api/reports/inventory-balance/` | Inventory balance Excel download |
| GET | `/api/reports/expiring-licenses/` | Expiring licenses report |
| GET | `/api/reports/active-licenses/` | Active licenses report |
| GET | `/api/reports/item-pivot/` | Item pivot data (JSON format) |
| GET | `/api/reports/item-report/` | Item report data |

---

## System

| Method | Path | Description |
|---|---|---|
| GET | `/api/health/` | Health check |
| GET | `/api/masters/throttle-status/` | Throttle status |
| POST | `/api/masters/throttle-reset/` | Reset throttle (superuser) |

---

## Common Response Formats

### Paginated List
```json
{
  "count": 150,
  "next": "/api/licenses/?page=2",
  "previous": null,
  "results": [ ... ]
}
```

### Error Response
```json
{
  "detail": "Error message"
}
```

### Validation Error (DRF)
```json
{
  "field_name": ["Error description"],
  "non_field_errors": ["Cross-field error"]
}
```

---

## Authentication Tokens

| Token | Lifetime | Notes |
|---|---|---|
| Access token | 60 minutes | Bearer header; auto-refreshed 5 min before expiry |
| Refresh token | 7 days | Stored in localStorage; blacklisted on logout |

Frontend auto-refreshes access tokens proactively. Idle > 30 minutes → auto logout with redirect to `/login?reason=idle`.
