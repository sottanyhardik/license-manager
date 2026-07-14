# Changelog

> Living document. One entry per completed phase or significant change.
> Format: ## [Phase/Date] — Summary followed by bullet list of changes.

---

## [Phase 1-9 Build] — feature/V1

> Consolidated entry covering all phases completed after Phase 0 foundation,
> as reflected on disk at 2026-07-14. The `trade` backend and frontend modules
> were specified but not yet implemented (see modules.md).

### Backend modules completed

- **accounts/** — User proxy model (managed=False, points at accounts_user table), JWT HS256 auth via SimpleJWT, permissions.py with 12 RBAC roles, serializers, views, urls
- **core/** — 23 managed=False master models in models/ package (Company, Port, HSCode, ItemGroup, ItemName, SionNorm, SionNormClass, ExchangeRate, CeleryTaskTracker, and more); CRUD API with serializers/ and views/ packages; filters.py
- **license/** — models/ package with 16+ models (LicenseDetailsModel, LicenseImportItemsModel, LicenseBalance, etc.); services/balance_service.py (recompute_license_balance with credit/debit/allotment/trade sub-computations); services/license_service.py (create, update, delete, create_import_item, update_import_item, delete_import_item); tasks.py (async PDF Celery task); 38 endpoints
- **allotment/** — AT/TR allotment types; services/allotment_service.py (create_allotment, update_allotment, delete_allotment, _dispatch for Celery balance recompute); filters.py
- **bill_of_entry/** — frozen row model, dispute resolution; services/boe_service.py (create_boe, update_row_detail, delete_row_detail, resolve_dispute, resolve_dispute_row, merge_boe, update_invoice_no, fetch_allotment_item_details, update_product_name_for_boe, bulk_update_product_names); views/ package with boe.py and ledger.py
- **tasks/** — state machine (pending → complete / rejected → reopened); services/task_service.py (create_task, complete_task, reject_task, reopen_task, add_remark); TaskRemark model
- **dashboard/** — read-only KPI aggregation (no own models); services/dashboard_service.py (get_dashboard_stats, get_license_utilisation_chart, get_monthly_activity, get_expiring_licenses)
- **reports/** — async Celery report generation; services/ with balance_report.py, item_report.py, ledger_report.py, pivot_report.py; tasks.py with generate_balance_report_task, generate_item_report_task, generate_pivot_report_task, generate_ledger_report_task; CeleryTaskTracker polling pattern

### Frontend features completed

- **shared/auth/** — AuthContext.tsx (JWT context provider), ProtectedRoute.tsx, roles.ts (15 RBAC role constants)
- **shared/api/** — axios client.ts (with JWT refresh interceptor and envelope unwrap), endpoints.ts, queryClient.ts (TanStack Query global client)
- **features/masters/** — 35 TanStack Query hooks in queries.ts, MasterSelect component, MasterDataTable component, CompanyList / PortList / MasterList pages
- **features/licenses/** — LicenseList, LicenseDetail, LicenseCard, LicenseBalancePanel, LicenseImportItems, LicenseStatusBadge, LicenseFilters, LicenseFormModal; api.ts, queries.ts, mutations.ts
- **features/allotments/** — AllotmentList, AllotmentForm, AllotmentItemsTable, AllotmentStatusBadge; api.ts with createAllotment, updateAllotment, deleteAllotment, generateAllotmentPdf; queries.ts
- **features/bill-of-entry/** — BOEList, BOEDetail, BOERowsTable, DisputeResolver, LedgerUpload; queries.ts, mutations.ts
- **features/reports/** — BalanceReport, ItemReport, LedgerReport, PivotReport, ReportsIndex, LicenseSelector, ReportGenerator, ReportTaskStatus; hooks/ for async task polling; queries.ts, mutations.ts
- **features/tasks/** — TaskList, TaskCard, TaskDrawer, TaskRemarks, TaskStatusBadge; queries.ts, mutations.ts
- **features/dashboard/** — Dashboard, StatCard, ActivityChart, UtilisationChart, ExpiringLicensesTable, DashboardSkeleton; queries.ts

### Infrastructure completed

- Docker Compose (6 services: postgres, redis, backend, frontend, celery, mailpit)
- GitHub Actions CI/CD: backend-ci.yml (lint/test/check), frontend-ci.yml (lint/typecheck/build), ci.yml (orchestration)
- Pre-commit hooks: ruff, black, prettier, secret detection (.pre-commit-config.yaml)
- Production deploy config referenced in auto-deploy.sh (gunicorn/supervisor/nginx on legacy path)
- README — full developer onboarding (quick start, architecture, commands)

### Still pending (not on disk)

- backend/apps/trade/ — trade invoices, lines, payments, 3dp billing precision, async PDF
- frontend/src/features/trade/ — TradeForm, trade list
- frontend settings page (pages/settings exists but features/settings not created)

---

## [Phase 0] — Foundation (feature/V1)

### Repository
- Moved `backend/` → `legacy/backend/` (read-only reference)
- Moved `frontend/` → `legacy/frontend/` (read-only reference)
- Created `legacy/README.md` (read-only rule)
- Scaffolded `backend/` (new Django app, empty)
- Scaffolded `frontend/` (new React app, empty)
- Updated `auto-deploy.sh` to reference `legacy/backend/` and `legacy/frontend/`

### Documentation
- Created `docs/adr/` — 10 ADRs (see `docs/knowledge-graph/decisions.md`)
- Created `docs/knowledge-graph/` — 8 living documents scaffolded
- Updated `docs/05-database.md` — full ER diagram, 42-model table inventory, signal map, cascade register

### Pre-Phase-1 Decisions (all approved)
- OQ-A: JWT signing → HS256 shared SECRET_KEY during transition, RS256 at cutover
- OQ-B: Celery broker → Redis DB /2 for backend/ (legacy stays on /0)
- OQ-C: Performance benchmark endpoints → 10 endpoints confirmed (see decisions.md)
- OQ-7: User model → managed=False proxy during transition, Profile OneToOne at cutover

### Tooling (pending)
- `backend/` Django scaffold (P0.5) — in progress
- `frontend/` React scaffold (P0.6) — in progress
- Docker Compose (P0.7) — pending
- GitHub Actions CI/CD (P0.8) — pending
- Pre-commit hooks (P0.9) — pending

---

## [Hotfixes on master — pre-Phase-0]

- `fix(backend/pdf)`: billing % (pct/rate_pct) precision — 3 decimal places enforced in compute_amount(), PDF formatters, TradeForm placeholder
- `fix(deploy)`: health check uses HTTPS domain instead of raw IP (was returning 301 on HTTP)
