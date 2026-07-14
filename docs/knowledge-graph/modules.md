# Modules

> Living document. Add a row per module as it is implemented in `backend/`.
> Status: pending = not started, in-progress = being built, done = feature-parity achieved.
> Last updated: Phase 1-9 build on feature/V1 (2026-07-14).

## Backend Modules

Completeness rule: `done` requires models (or models package), views (or views package), `urls.py`, and `services/` all present on disk.

| Module | Status | Purpose | Key Tables | Services | APIs Exposed |
|---|---|---|---|---|---|
| accounts | done | User proxy model, JWT auth (HS256), RBAC (12 roles), permissions | accounts_user (managed=False proxy) | — (logic in views + permissions.py) | /api/v1/auth/ |
| core | done | 23 master-data models (company, port, HS code, SION, exchange rates, CeleryTaskTracker, etc.) | 23 master tables in models/ package; serializers/ and views/ packages | — (no business services; CRUD only) | /api/v1/masters/ |
| license | done | DFIA + incentive licenses, import items, balance ledger, async PDF | license_* models in models/ package | balance_service.py, license_service.py | /api/v1/licenses/ |
| allotment | done | Pre-auth allotments + transfer letters; Celery balance dispatch after commit | allotment*, allotmentitems | allotment_service.py | /api/v1/allotments/ |
| bill_of_entry | done | BOE header + frozen row details, dispute resolution, ledger upload, merge | billofentry*, rowdetails | boe_service.py | /api/v1/bill-of-entries/ |
| trade | done | Trade invoices (DFIA + Incentive), billing lines (QTY/CIF/FOB modes), payments, 3dp pct/rate_pct precision hotfix, synchronous PDF (purchase invoice + bill of supply), async Celery task stub, auto-paired trade creation, bidirectional trade linking | trade_licensetrade, trade_licensetradeline, trade_incentivetradeline, trade_licensetradepayment | trade_service.py (parse_date_strict, get_prefilled_invoice_number, build_trade_summary, link_trades, PartnerTradeNotFound) | /api/v1/trades/ |
| tasks | done | Internal workflow task state machine; remarks; complete/reject/reopen | task, taskremark | task_service.py | /api/v1/tasks/ |
| dashboard | done | KPI aggregation (read-only, no own models); licence utilisation, monthly activity, expiring alerts | reads from license/allotment/boe | dashboard_service.py | /api/v1/dashboard/ |
| reports | done | Async Celery report generation (balance, item, ledger, pivot); CeleryTaskTracker polling | uses CeleryTaskTracker from core | balance_report.py, item_report.py, ledger_report.py, pivot_report.py | /api/v1/reports/ |


## Frontend Feature Modules

Completeness rule: `done` requires a `pages/` directory with at least one page component and either `queries.ts` or `mutations.ts`.
`in-progress` means some files exist but the feature is not fully wired.

| Feature | Status | Routes | Key Components | API Hooks / Files |
|---|---|---|---|---|
| shared/auth | done | /login | AuthContext.tsx, ProtectedRoute.tsx, roles.ts | JWT refresh logic in shared/api/client.ts |
| shared/api | done | — | axios client with JWT refresh + envelope unwrap | client.ts, endpoints.ts, queryClient.ts |
| masters | done | /masters/companies, /masters/ports, /masters/:entity | CompanyList, PortList, MasterList, MasterSelect, MasterDataTable | queries.ts (35 TanStack hooks across all master entities) |
| licenses | done | /licenses, /licenses/:id | LicenseList, LicenseDetail, LicenseCard, LicenseBalancePanel, LicenseImportItems, LicenseStatusBadge, LicenseFilters, LicenseFormModal | api.ts, queries.ts, mutations.ts |
| allotments | done | /allotments | AllotmentList, AllotmentForm, AllotmentItemsTable, AllotmentStatusBadge | api.ts, queries.ts (CRUD + PDF generation) |
| bill-of-entry | done | /boe, /boe/:id | BOEList, BOEDetail, BOERowsTable, DisputeResolver, LedgerUpload | queries.ts, mutations.ts |
| trade | done | /trades, /trades/new, /trades/:id | TradeList, TradeForm, TradeLineTable, IncentiveLineTable, PaymentTable, TradeSummary | queries.ts (useTrades, useTrade, useTradeSummary), mutations.ts (useCreateTrade, useUpdateTrade, useDeleteTrade, useGeneratePurchaseInvoice, useGenerateBillOfSupply) |
| reports | done | /reports/* | BalanceReport, ItemReport, LedgerReport, PivotReport, ReportsIndex, LicenseSelector, ReportGenerator, ReportTaskStatus | queries.ts, mutations.ts, hooks/ (async task polling) |
| tasks | done | /tasks | TaskList, TaskCard, TaskDrawer, TaskRemarks, TaskStatusBadge | queries.ts, mutations.ts |
| dashboard | done | / | Dashboard, StatCard, ActivityChart, UtilisationChart, ExpiringLicensesTable, DashboardSkeleton | queries.ts |
| settings | pending | /settings | — | — (pages/settings exists but feature directory not in features/) |
