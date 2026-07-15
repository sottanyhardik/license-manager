# System Architecture — Knowledge Graph

> **Purpose**: Quick-reference architecture map. Use before starting any development task.  
> Last updated: 2026-07-15 (feature/V1).

---

## 1. System Overview

```mermaid
graph TB
    Browser["Browser\n(React SPA)"]
    Vite["Vite Dev Server\n:5173 (dev)\nor nginx (prod)"]
    Nginx["nginx\n(SSL termination)"]
    NewDjango["New Django App\nbackend/ :8001"]
    LegacyDjango["Legacy Django App\nlegacy/backend/ :8000"]
    PostgreSQL["PostgreSQL\n(shared DB)"]
    Redis["Redis\n/1=cache /2=broker /3=results"]
    Celery["Celery Worker\nbalance recompute\nreport generation"]
    
    Browser --> Vite
    Vite --> Nginx
    Nginx -->|"/api/v1/*"| NewDjango
    Nginx -->|"/api/*"| LegacyDjango
    NewDjango --> PostgreSQL
    LegacyDjango --> PostgreSQL
    NewDjango --> Redis
    Redis --> Celery
    Celery --> PostgreSQL
```

---

## 2. Backend Module Dependency Graph

```mermaid
graph LR
    shared["shared/\nAuditModel\nEnvelopeMixin\nStandardPagination\nBaseRolePermission"]
    accounts["accounts/\nUser proxy\nJWT auth\n12 RBAC roles"]
    core["core/\n23 master models\nCompany Port HS Code\nSION ExchangeRate\nCeleryTaskTracker"]
    license["license/\nLicenseDetailsModel\nLicenseBalance\nLicenseItemPlan\nbalance_service"]
    allotment["allotment/\nAllotmentModel\nAllotmentItems\nallotment_service"]
    boe["bill_of_entry/\nBillOfEntryModel\nRowDetails\nboe_service"]
    trade["trade/\nLicenseTrade\nLicenseTradeLine\ntrade_service"]
    tasks["tasks/\nTask\nTaskRemark\ntask_service"]
    dashboard["dashboard/\ndashboard_service\nread-only KPIs"]
    reports["reports/\nasync generation\nbalance/item/ledger/pivot"]

    shared --> accounts
    shared --> core
    shared --> license
    shared --> allotment
    shared --> boe
    shared --> trade
    shared --> tasks
    shared --> dashboard
    shared --> reports
    
    core --> license
    core --> allotment
    core --> boe
    core --> trade
    
    license --> allotment
    license --> boe
    license --> trade
    license --> dashboard
    license --> reports
    
    allotment --> boe
    boe --> license
    trade --> license
```

---

## 3. Balance Recompute Data Flow

```mermaid
sequenceDiagram
    participant FE as Frontend
    participant API as Django API
    participant DB as PostgreSQL
    participant Redis as Redis Broker
    participant Worker as Celery Worker
    
    Note over FE,Worker: Allotment Create Flow
    FE->>API: POST /api/v1/allotments/
    API->>DB: BEGIN TRANSACTION
    API->>DB: validate_plan (select_for_update on LicenseItemPlan)
    API->>DB: INSERT AllotmentModel
    API->>DB: INSERT AllotmentItems
    API->>DB: UPDATE LicenseItemPlan (planned_qty -= allot_qty)
    API->>DB: COMMIT
    API->>Redis: on_commit → recompute_license_balance_task.delay(license_id)
    API-->>FE: 201 Created
    
    Note over Redis,Worker: Async Balance Update
    Redis->>Worker: Deliver task message
    Worker->>DB: BEGIN TRANSACTION
    Worker->>DB: SELECT FOR UPDATE LicenseDetailsModel
    Worker->>DB: SUM export items → credit
    Worker->>DB: SUM RowDetails → debit
    Worker->>DB: SUM AllotmentItems (no BOE) → allotment
    Worker->>DB: SUM LicenseTradeLine → trade
    Worker->>DB: UPSERT LicenseBalance (balance_cif)
    Worker->>DB: UPSERT LicenseFlags (is_null, is_expired)
    Worker->>DB: bulk_update LicenseImportItemsModel (avail_qty)
    Worker->>DB: COMMIT
    Worker->>Redis: ACK message
```

---

## 4. Authentication Flow

```mermaid
sequenceDiagram
    participant FE as Frontend (AuthContext)
    participant API as Django API
    participant DB as PostgreSQL
    participant LS as localStorage
    
    FE->>API: POST /api/v1/auth/login/ {username, password}
    API->>DB: authenticate(username, password)
    DB-->>API: User object
    API-->>FE: {access, refresh, user: {id, is_superuser, roles}}
    FE->>LS: store access, refresh, user
    
    Note over FE: On every API request
    FE->>FE: read access from localStorage
    FE->>API: GET /api/v1/... (Authorization: Bearer {access})
    
    Note over FE: 401 received
    FE->>API: POST /api/v1/auth/token/refresh/ {refresh}
    API-->>FE: {access, refresh}
    FE->>LS: update access (and refresh if rotated)
    FE->>API: Retry original request
    
    Note over FE: Proactive refresh (5min before expiry)
    FE->>FE: setTimeout based on JWT exp claim
    FE->>API: POST /api/v1/auth/token/refresh/
```

---

## 5. Module Cross-Reference Table

| Module | Reads From | Writes To | Dispatches |
|---|---|---|---|
| license | core, accounts | LicenseDetailsModel, LicenseBalance, LicenseFlags, LicenseItemPlan | recompute_license_balance_task |
| allotment | license (LicenseImportItemsModel), core | AllotmentModel, AllotmentItems, LicenseItemPlan | recompute_license_balance_task |
| bill_of_entry | license (LicenseImportItemsModel), allotment | BillOfEntryModel, RowDetails | recompute_license_balance_task (via signal) |
| trade | license (LicenseImportItemsModel), core | LicenseTrade, LicenseTradeLine, LicenseTradePayment | (none currently) |
| dashboard | license, allotment, bill_of_entry | None (read-only) | None |
| reports | license, allotment, bill_of_entry, trade, core | None (generates files) | generate_*_report_task |
| tasks | accounts | Task, TaskRemark | None |

---

## 6. Frontend Feature Map

```mermaid
graph LR
    shared_api["shared/api/\nclient.ts (axios + JWT + envelope)\nendpoints.ts\nqueryClient.ts"]
    shared_auth["shared/auth/\nAuthContext.tsx\nProtectedRoute.tsx\nroles.ts"]
    shared_ui["shared/ui/\nSidebar AdminLayout TopBar\nbadge button card input label"]
    
    dash["features/dashboard\nKPI stats + charts"]
    lic["features/licenses\nlist + detail + balance + items"]
    allot["features/allotments\nlist + form"]
    boe["features/bill-of-entry\nlist + detail + rows + dispute"]
    trade["features/trade\nlist + form + lines + payments"]
    tasks["features/tasks\nlist + card + remarks"]
    reports["features/reports\nasync generation + polling"]
    masters["features/masters\ncompanies + ports + hs-codes + ..."]
    
    shared_api --> dash
    shared_api --> lic
    shared_api --> allot
    shared_api --> boe
    shared_api --> trade
    shared_api --> tasks
    shared_api --> reports
    shared_api --> masters
    shared_auth --> shared_ui
```

---

## 7. Key Design Decisions (→ ADRs)

| Decision | ADR | Impact |
|---|---|---|
| Hybrid parallel-run strategy | ADR-001 | legacy/ read-only; new code in backend/ + frontend/ |
| Single shared PostgreSQL | ADR-002 | All managed=False models; no migrations for business tables |
| Django 6.x + Python 3.13 | ADR-003 | Latest LTS stack |
| React 19 + Vite + TanStack Query v5 | ADR-004 | Modern frontend stack |
| /api/v1/ prefix for new API | ADR-005 | nginx routes by prefix; no version conflicts |
| JWT HS256 shared SECRET_KEY | ADR-006 | Tokens work on both backends during transition |
| Views → Services → ORM (never views → ORM) | ADR-007 | All business logic in service layer |
| Celery replaces cross-app signals | ADR-008 | No synchronous cross-module calls |
| 6-criteria production cutover gate | ADR-009 | UAT required before cutover |
| legacy/ is read-only | ADR-010 | All work happens in backend/ and frontend/ |

---

## 8. Test Coverage Map

| Test File | Business Rules Covered |
|---|---|
| `tests/balance/test_balance_system.py` | 21 tests: balance formula, item formula, Scenarios A+B, planning, dispatch, flags |
| `tests/integration/test_license_workflows.py` | ~54 tests: BR-01 to BR-08, E2E workflow, permissions, BOE rules |
| `tests/integration/test_permissions.py` | RBAC: all 12 roles × 4 permission classes |
| `tests/accounts/test_auth.py` | Login, logout, refresh, RBAC, inactive users |
| `tests/allotment/test_allotment.py` | Create/delete dispatch, allotment type choices |
| `tests/bill_of_entry/test_boe.py` | Frozen rows, dispute resolution, signal, ledger upload |
| `tests/trade/test_trade.py` | 3dp precision for all billing modes |
| `tests/license/test_license.py` | License CRUD, balance task dispatch, permissions |
| `tests/reports/test_reports.py` | Task dispatch, tracker pre-creation, status polling |
| `tests/tasks/test_tasks.py` | State machine, remarks, transitions |
| `tests/core/test_masters.py` | Master CRUD, auth, pagination, search |
| `tests/dashboard/test_dashboard.py` | Stats, charts, expiring, auth |

---

## 9. Production Cutover Checklist (ADR-009)

Before switching nginx to point the new frontend at the new backend:

- [ ] All 9 modules built (backend + frontend) ✅
- [ ] 161/161 tests pass ✅
- [ ] Zero CRITICAL/HIGH security findings open ✅
- [ ] nginx parallel-run config on all 3 servers ✅
- [ ] Security audit report committed ✅
- [ ] UAT with 3 business users ⏳ (post-merge)

**PR**: https://github.com/sottanyhardik/license-manager/compare/develop...feature/V1
