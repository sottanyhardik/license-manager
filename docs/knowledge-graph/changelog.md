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

### Phase 3 addendum — License module correctness fixes (2026-07-14)

Applied after initial scaffold, before commit:
- Fixed `balance_service._compute_debit`: was `boe__license_id` (wrong), corrected to `sr_number__license_id` + `bill_of_entry__license_trades__isnull=True` (matches legacy `balance_calculator.py` exactly)
- Fixed `balance_service._compute_allotment`: was `allotment__license_id` (wrong), corrected to `item__license_id` (path through `LicenseImportItemsModel`)
- Fixed `balance_service._compute_trade`: was `trade__license_id` (wrong), corrected to `sr_number__license_id` (path through `LicenseImportItemsModel`)
- Fixed `LicensePurchase.mode` choices: `DIRECT/BROKER` → `AMOUNT/QTY` (legacy values)
- Fixed `LicensePurchase.amount_source` choices: `INVOICE/MANUAL` → `FOB_INR/CIF_INR/CIF_USD` (legacy values)
- Fixed `LicensePurchase.markup_pct`: `decimal_places=2` → `decimal_places=6` (legacy precision)

### Phase 6 — Trade module (2026-07-14)

- **backend/apps/trade/** — 4 managed=False models (LicenseTrade, LicenseTradeLine, IncentiveTradeLine, LicenseTradePayment), exact db_table names matching legacy schema; `compute_amount()` precision fix (pct/rate_pct: 3dp, never wrapped in q2()); services/trade_service.py ported exactly from legacy (parse_date_strict, get_prefilled_invoice_number, build_trade_summary, link_trades, PartnerTradeNotFound); nested CRUD serializer with inline _sync_nested logic; synchronous PDF actions (purchase invoice + bill of supply with :.3f pct formatting); Celery stub task (acks_late=True); TradePermission enforcement; prefill-invoice-number, summary, link-trade extra actions; wired to INSTALLED_APPS and /api/v1/trades/
- **frontend/src/features/trade/** — types.ts (Trade, TradeLine, IncentiveTradeLine, TradePayment), queries.ts (useTrades, useTrade, useTradeSummary), mutations.ts (useCreateTrade, useUpdateTrade, useDeleteTrade, useGeneratePurchaseInvoice, useGenerateBillOfSupply), components (TradeLineTable with mode-aware columns + 3dp pct step, IncentiveLineTable with 3dp rate_pct step, PaymentTable, TradeSummary), pages (TradeList with direction filter, TradeForm with conditional DFIA/Incentive line tables); wired to router (/trades, /trades/new, /trades/:id)
- **frontend/src/shared/api/endpoints.ts** — TRADES section extended with SUMMARY, PREFILL_INVOICE, PURCHASE_INVOICE_PDF, BILL_OF_SUPPLY_PDF, LINES, PAYMENTS, LINK_TRADE
- **backend/tests/trade/test_trade.py** — 10 unit tests; all pass including the critical precision guard (pct=7.925, cif=100000 → 7925.00 not 7930.00; rate_pct=2.125, value=500000 → 10625.00)

### Still pending (not on disk)

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
