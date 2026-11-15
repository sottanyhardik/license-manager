# 01 - System Inventory (Phase Zero discovery)

Generated 2026-11-15, branch `feature/version5`. Method: AST scan of `backend/apps` (non-migration, non-test code), `.claude/index/*.tsv`, grep. Read-only; nothing deleted. Prior "FROZEN"/"PRODUCTION READY" reports were NOT trusted; every claim below is from code. Counts marked `~` are heuristic (AST/regex) and may be off by a few.

## 1. Repository shape

| Component | Path | Stack | Non-test src LOC | Tests (def test_) |
|---|---|---|---|---|
| Backend monolith | `backend/` (`apps/`, `lmanagement/`, `shared/`, `api_utils/`) | Django 6, DRF, Celery, Redis, Postgres | ~103,700 (apps 102,295 + lmanagement 1,021 + shared 355 + api_utils 67) | 2,328 (apps 2,103 + `backend/tests/` 225) |
| Master-Data Service (MDS) | `master-data-service/` | Separate Django project, own Postgres DB `master_data` | ~1,900 incl. tests | 19 |
| MDS client | `mds-client/` | Installable Django app `mds_client` | ~2,000 incl. tests | 32 |
| Frontend SPA | `frontend/src` | React 19, TS 5.9, Vite (rolldown-vite 7.2.2), Tailwind 4, shadcn/Radix, TanStack Query 5, react-router 7 | 62,239 (359 files: 223 tsx, 103 ts, 33 js) | 78 vitest files, 13 playwright specs (`frontend/e2e`, `frontend/playwright`) |

Migrations: accounts 6, allotment 16, bill_of_entry 14, core 19, license 56, reconciliation 5, tasks 1, trade 11 (128 total).

## 2. Django apps (backend/apps)

Model counts are concrete (non-abstract) classes with fields; abstract bases listed separately.

| App | Purpose | Models (n) | Src LOC / test files / tests |
|---|---|---|---|
| `accounts` | JWT login/logout/refresh, password reset, user mgmt, role (Django Group) permissions | 2: `User`, `RevokedAccessToken` | 1,833 / 3 / 17 |
| `allotment` | Allotments of licence import items to buyers, allocation versions, shortfalls, audit | 5: `AllotmentModel`, `AllotmentItems`, `AllocationVersion`, `Shortfall`, `AuditEvent` | 5,834 / 13 / 104 |
| `bill_of_entry` | BOE + row details, PDF parse, export | 2: `BillOfEntryModel`, `RowDetails` | 3,826 / 2 / 10 |
| `core` | Master data (company, port, item, HSN, SION norms, FX...), mixins, caching, materialized views, peer sync, activity log, throttling, health, media | 30 (+4 abstract: `AuditModel`, `SyncTimestampModel`, `SyntheticUidMixin`, `MasterSyncMixin`): `MasterChange, CompanyModel, PortModel, ItemHeadModel, ItemGroupModel, ItemNameModel, HSCodeModel, HeadSIONNormsModel, SionNormClassModel, SIONExportModel, SIONImportModel, SionNormNote, SionNormCondition, ProductDescriptionModel, TransferLetterModel, UnitPriceModel, InvoiceEntity, SchemeCode, NotificationNumber, PurchaseStatus, ExchangeRateModel, CeleryTaskTracker, ActivityLog, SyncConflictLog, SyncPeer, SyncCursor, SyncEvent, SyncInboxEvent, SyncPeerDelivery, MediaSyncTask` | 23,446 / 26 / 577 |
| `license` | DFIA/Advance licence, import/export items, balances, ledger, SION planning + auto-plan, reports, incentive licences, ledger package jobs, purchases, ownership | 33: `LicenseDetailsModel, LicenseExportItemModel, LicenseImportItemsModel, LicenseReplanRequest, LicenseItemPlan, SionPlanningRule/UnitValueRow/PercentageRow/Profile/Action/OutputMapping/Run, SionInputAliasConfig, LicenseDocumentModel, StatusModel, OfficeModel, AlongWithModel, DateModel, LicenseInwardOutwardModel, LicenseTransferModel, IncentiveLicense, LicensePurchase, LicenseNotes, LicenseBalance, LicenseFlags, LicenseOwnership, LicenseLedgerPackageJob/Item, LicensePackageArtifact, LicensePackageAuditEvent, LicenseLedgerRecoveryAudit, Invoice, InvoiceItem` | 59,343 / 182 / 1,258 |
| `reconciliation` | BOE/invoice/allotment allocation reconciliation, warnings | 6: `ReconciliationNote, ReconciliationLog, InvoiceBOEAllocation, BOEAllotmentAllocation, ExternalInvoiceLink, IgnoredWarning` | 2,666 / 7 / 75 |
| `tasks` | Internal to-do tasks + remarks (not Celery) | 2: `Task`, `TaskRemark` | 424 / 1 / 2 |
| `trade` | Licence trades (sale/purchase), lines, payments, invoice docs + secure links, bill-of-supply / purchase-invoice PDFs | 9: `LicenseTrade, SaleClassificationDecision, LicenseTradeLine, IncentiveTradeLine, LicenseTradePayment, TradePairAudit, TradeInvoiceDocument, InvoiceDocumentAccessToken, InvoiceDocumentAuditEvent` | 4,923 / 10 / 60 |

Total: 89 concrete models. `AppConfig` labels are preserved (`apps.X` modules, label `X`).

### 2a. Views / serializers / services / permissions / signals per app

| App | Views (files -> main classes) | Serializers | Services (`services/`) | Signals (where) | Permissions used |
|---|---|---|---|---|---|
| accounts | `views/auth.py` (Login, Logout, Me), `password.py` (Reset req/confirm, ChangePassword), `user_management.py` (`UserManagementViewSet`) | 3 (Register, User, UserManagement) | `services.py` (single file) | `signals.py`: avatar cleanup (2 receivers) | defines 17 permission classes in `permissions.py` (`BaseRolePermission` + License, Allotment, BOE, Trade, Reconciliation, Incentive, UserMgmt, Report, LedgerUpload, LicenseLedgerView, AccountAccess, TransferLetter, ...); role = Django Group name (`accounts/models.py:110-118`) |
| allotment | `views.py` (`AllotmentViewSet`, 395), `views_actions.py` (`AllotmentActionViewSet`, 1,680), `views_export.py` (774) | 2 | 5 files: `allocation_service, allocation_availability, filter_service, paired_allocation_max, validation_service` | `signals.py` + `models/core.py` (4 receivers: stock, is_allotted) | `AllotmentPermission` |
| bill_of_entry | `views/boe.py` (`BillOfEntryViewSet`), `views/parse_pdf.py` (`BOEPdfParseView`), `views_export.py` (901) | 2 | `boe_service.py` | in `models.py` (4: stock, exchange-rate recalc) | `BillOfEntryPermission` |
| core | `views/`: `views.py` (629), `master_view.py` (907, viewset *factory*), `activity_log, health, mds_status, media, throttle_status`; `cached_views.py` | ~46 in `serializers/` (+ fields/mixins) | none (`utils/`, `reports/`, `exporters/`, `sync/` sub-packages; no `services/`) | `cache_signals.py` (11 invalidation receivers), `signals_materialized_views.py` (4), `sync/signals.py` | `MasterDataPermission` |
| license | 19 files in `views/` + `views_actions.py`, `views_incentive.py`; `item_pivot_report.py` (2,400) | 30 in `serializers/` (`license.py` 1,134, `_license_write.py` 895, `incentive.py` 671, `ledger.py`) | ~70 modules in `services/` (+ `sion_planner_config/`, `exporters/`) | `signals.py` (~23 receivers) + `models/core.py` | Permission, ReadOnly, LedgerUpload, LicenseLedgerView, Report, IncentiveLicense |
| reconciliation | `views.py` (`ReconciliationViewSet`, 316) | none (inline) | `allocation_service, boe_link_reconciler, queries, warning_service` | none | `ReconciliationPermission` |
| tasks | `views.py` (`TaskViewSet`) | 2 | `task_service.py` | none | default `IsAuthenticated` |
| trade | `views.py` (719), `views_invoice_documents.py` | 5 (`serializers.py` 634) | 5: `final_party_classification, invoice_document_service, invoice_secure_links, sale_classification_review, trade_service` | in `models.py` (4: trade-line/incentive/BOE-invoice) | `TradePermission`; invoice doc view is `AllowAny` + token (`views_invoice_documents.py:41`) |

AllowAny endpoints (non-test): `api/health/` (`core/views/health.py:20`), login + password-reset (`accounts/views/auth.py:17`, `password.py:32,80`), invoice-document token view. The docstring in `license/views/inventory_balance_viewset.py` still says "AllowAny" but the code uses `ReportPermission` (`:30`) - stale doc.

### 2b. Middleware (`lmanagement/settings.py:155-169`)
`SecurityMiddleware, WhiteNoise, CorsMiddleware, Session, Common, apps.core.middleware.DisableCSRFForAPIMiddleware, Csrf, Auth, Messages, XFrame, apps.core.middleware.ActivityLogMiddleware` (writes an `ActivityLog` row from a **daemon thread per request**, `core/middleware.py:99-135`).

### 2c. URL prefixes (`lmanagement/urls.py:30-60`)
| Prefix | Mounts |
|---|---|
| `/admin/`, `/api/health/`, `/api/mds/status/`, `/api/schema|docs|redoc/` | Django admin, health, MDS status, OpenAPI (login-gated unless DEBUG) |
| `/api/media/<path>` | `ProtectedMediaView` (auth'd media) |
| `/api/auth/` | accounts |
| `/api/` (x6, un-prefixed) | license, allotment, bill_of_entry, trade, reconciliation, tasks (router prefixes: `licenses, license-actions, license-items, license-item-plans, sion-planning-rules, license-ledger, inventory-balance, expiring-licenses, active-licenses, item-pivot, item-report, planned-report, incentive-licenses, allotments, allotment-actions, bill-of-entries, trades, lines, payments, reconciliation, tasks` + `reports/*`, `dashboard/`, `upload-ledger/`, `ledger-task-status/`) |
| `/api/masters/` | core master CRUD |
| `/api/sync/` | peer master sync |
| `^api/` | JSON 404; then SPA catch-all `^.*$` -> `index.html` |

### 2d. Celery
Broker + result backend: Redis (`settings.py:346-347`). Routes/annotations only for planning + ledger-package tasks (`:354-383`). Worker unit: `backend/deploy/celery.service` (`-Q celery,ledger`, concurrency 4).

Registered tasks (`name=`): `core.tasks.fetch_exchange_rates`; `sync.pull_from_peers|push_changes|process_media_tasks`; `planning.dispatch_replan_requests|replan_sion_batch|replan_license|recover_pending_replan_requests`; `license.process_single_license|enqueue_license_ledger_package|build_license_ledger_package_item|finalize_license_ledger_package|cleanup_expired_ledger_packages|recover_license_ledger_package_jobs`; core materialized-view tasks (5: refresh_all/dashboard/item_balance/license_balance, health check); `mds_client.sync_masters`; legacy `lmanagement/tasks.py` (`add`, `delete_license_details_by_numbers`, `dgft_shipping_details`, `fetch_data_to_model`, `fetch_file`) + `celery.py` `debug_task`.

Beat schedule (`lmanagement/celery.py`):
| Entry | Task | Schedule | Registered in code? |
|---|---|---|---|
| sync-licenses-daily-midnight-ist | `license.tasks.sync_all_licenses` | 18:30 UTC | **NO** (only referenced at `celery.py:47`) |
| update-balances-11am / 8pm-ist | `identify_licenses_needing_update` | 05:30 / 14:30 UTC | **NO** (`celery.py:59,67`) |
| cleanup-old-tasks-hourly | `cleanup_old_task_records` | hourly | **NO** (`celery.py:83`) |
| recover-pending-license-replans-every-5-min | `planning.recover_pending_replan_requests` | */5 | yes |
| cleanup-expired-license-ledger-packages-daily | `license.cleanup_expired_ledger_packages` | 02:20 | yes |
| recover-license-ledger-package-jobs-every-5-min | `license.recover_license_ledger_package_jobs` | */5 | yes |
| mds-sync-masters-every-5-min | `mds_client.sync_masters` | */5, only if `MDS_ENABLED` | yes (mds-client) |
| sync-pull-peers / push-durable-events / process-media | `sync.*` | */5, only if `SYNC_ENABLED` | yes |

Four of the 9 default beat entries point at tasks that do not exist (grep over `backend`, `mds-client`, `master-data-service` finds only the beat references). They fail at the worker as "unregistered task". The balance-refresh jobs the schedule implies are therefore not running via Celery (balances are instead maintained by signals; see 02).

### 2e. Management commands (non-test)
accounts 3 (`check_user_roles, migrate_auth, repair_user_fk_constraints`); allotment 3 (`backfill_allocation_status, update_exchange_rate, update_is_boe`); reconciliation 2 (`backfill_boe_allocations, check_allocation_health`); trade 1 (`backfill_final_party_classifications`); core ~34 (audit/merge/clean masters, `rebuild_migrations`, `reset_migration_history`, `sync_database_schema`, `sync_from_ge_server`, `export_masters_mds`, `refresh_materialized_views`, `rqworker`, `fetch_detail_*`...); license ~25 (`reconcile_license, plan_norms, update_license_ownership` (914 LOC), `delete_licenses_by_exporter`, `resync_local_to_server`, `upload_dfia_copies`, `seed_browser_2509`, ...). Total ~68. Several are one-off data repairs (`migrate_purchase_status_np_to_mi`, `correct_a3627_active_rules`) kept indefinitely; `rqworker` looks like a stale name (RQ not used; Celery is).

## 3. Other backend packages

| Package | Contents | LOC | Notes |
|---|---|---|---|
| `backend/lmanagement` | `settings.py` (620), `urls.py` (80), `celery.py` (173), `tasks.py` (127, legacy DGFT fetch tasks), `wsgi.py` | 1,021 | Single settings module, no env split (see 02) |
| `backend/shared/pdf` | `builders.py` ReportLab helpers | 355 | Imported by 2 license files only (index) |
| `backend/api_utils` | `form_schema.py` | 67 | Tiny; no tests |

## 4. master-data-service (MDS)
- Purpose: central master DB, REST `api/v1/` (`mds/urls.py:13`), `healthz`. Separate project (`mds/settings.py`, DB `master_data`, `:98-107`).
- Models (20, `masters/models.py`): `MasterModel` (abstract base) + `SyntheticKeyMixin`; `Company, Port, ItemHead, ItemGroup, ItemName, HSCode, HeadSIONNorm, SIONNormClass, SIONExport, SIONImport, SIONNormNote, SIONNormCondition, ProductDescription, UnitPrice, SchemeCode, NotificationNumber, ExchangeRate, MasterChange` (17 masters + change feed).
- Views: `MasterViewSet` (ModelViewSet base, ETag + `_meta`, `updated_since`), `MasterChangeViewSet` (read-only cursor feed); 17 viewsets via `MASTER_VIEWSETS` router (`masters/urls.py`).
- Auth: service-token Bearer with scope (`masters/auth.py`, `MDS_SERVICE_TOKENS`). Signals: `masters/signals.py` writes `MasterChange` on every save/delete. Command: `load_masters` (444 LOC). Tests: 19 (3 files). Prod server config: `master-data-service/deploy/gunicorn.conf.py`.

## 5. mds-client
Installable package: `client.py` (HTTP, 281), `sync.py` (mirror sync, 405), `model_map.py` (17-master map), `keys.py` (synthetic keys), `models.py` (`MDSSyncState`), `tasks.py` (`mds_client.sync_masters`), command `mds_sync`. 32 tests (own `runtests.py`, mirror test app). Registered into INSTALLED_APPS only when `MDS_ENABLED` and importable (`settings.py:610-620`).

## 6. Frontend (`frontend/src`)
| Dir | Files | Notes |
|---|---|---|
| `pages/` | 200 | per feature (masters, reports, license-*, planning, reconciliation, admin, auth) |
| `components/` | 72 (+ `ui/` shadcn) | |
| `services/` | 14 (+ `api/`) | typed API wrappers (ledger export/package/readiness, planning rules) |
| `hooks/` | 14 | mix of `.js` and `.ts(x)` |
| `utils/` 27, `api/` 5 (`axios.js`: 110 dependents), `context/` 3 (Auth, Theme), `routes/` 5 (`AppRoutes.tsx` 339), `types/` 3 | | 33 untyped `.js` files remain |

Tokens live in `localStorage` (`api/axios.js:30,95,126,135`). Largest: `ItemPivotReport.tsx` 1,951; `AllotmentAction.tsx` 1,833; `MasterList.tsx` 1,729; `TradeForm.tsx` 1,644; `LicensesTable.tsx` 1,441; `PlanningEditor.tsx` 1,265; `LedgerTab.tsx` 1,159. `frontend/` root also holds 11 loose docs/scripts (`CLEANUP_ANALYSIS.md`, `route-browser-test.{js,mjs}`, `route-authenticated-test.mjs`, ...).

## 7. Top 15 largest non-test source files (LOC)
| # | File | LOC |
|---|---|---|
| 1 | `backend/apps/license/models/core.py` | 2,625 |
| 2 | `backend/apps/license/views/item_pivot_report.py` | 2,400 |
| 3 | `backend/apps/license/services/balance_calculator.py` | 2,149 |
| 4 | `backend/apps/license/services/exporters/license_balance_excel.py` | 2,006 |
| 5 | `frontend/src/pages/reports/ItemPivotReport.tsx` | 1,951 |
| 6 | `frontend/src/pages/AllotmentAction.tsx` | 1,833 |
| 7 | `backend/apps/license/services/sion_planning_execution.py` | 1,741 |
| 8 | `frontend/src/pages/masters/MasterList.tsx` | 1,729 |
| 9 | `backend/apps/license/services/license_balance_ledger_builder.py` | 1,682 |
| 10 | `backend/apps/allotment/views_actions.py` | 1,680 |
| 11 | `frontend/src/pages/TradeForm.tsx` | 1,644 |
| 12 | `backend/apps/license/services/canonical_planning_service.py` | 1,449 |
| 13 | `frontend/src/pages/masters/tables/LicensesTable.tsx` | 1,441 |
| 14 | `backend/apps/license/services/canonical_ledger_service.py` | 1,367 |
| 15 | `backend/apps/license/services/exporters/license_balance_pdf.py` | 1,311 |

Backend: 103 functions >100 lines, 295 >50 lines (non-test, non-command). Longest: `add_grouped_export_action` (BOE `views_export.py:56`) 846, `get_item_filters` (`license/utils/item_matcher.py:25`) 781, `_compute_license_new_architecture` (`sion_planning_execution.py:394`) 773, `build_bulk_balance_excel` 759, `generate_bill_of_supply_pdf` 726.

## 8. Tests
| Location | Files | `def test_` |
|---|---|---|
| `backend/tests/` (canonical suite, CI-required) | 15 | 225 |
| `apps/license/tests` | 182 | 1,258 |
| `apps/core/tests` | 26 | 577 |
| `apps/allotment/tests` | 13 | 104 |
| `apps/reconciliation/tests` | 7 | 75 |
| `apps/trade/tests` | 10 | 60 |
| `apps/accounts/tests` | 3 | 17 |
| `apps/bill_of_entry/tests` | 2 | 10 |
| `apps/tasks/tests.py` | 1 | 2 |
| MDS / mds-client / frontend | 3 / 4 / 78+13 | 19 / 32 / n/a |

CI (`.github/workflows/ci.yml:108,111`) runs only `tests/` + `apps/license/tests` + `apps/core/tests`. **allotment, trade, reconciliation, accounts, bill_of_entry and tasks app tests (~268) are not run in CI**, although `backend/pytest.ini` `testpaths = tests apps` would collect them locally. (Not executed in this task; counts are static.)

## 9. Clutter candidates (DO NOT DELETE - flagged for human decision)

### 9a. Loose scripts at `backend/` root (22 ad-hoc .py; not part of suite per `.claude/rules/backend.md`)
`deep_trace.py, final_debug.py, reconciliation_detailed.py, test_all_queries.py, test_pdf_e2e_simple.py, test_pdf_parsing_e2e.py, test_persistence_debug.py, test_query_sequence.py, test_split_fix.py, test_transaction_commit.py, trace_canonical_lines.py, trace_persistence.py, trace_sql.py, verify_accounting.py, verify_balance_detail.py, verify_comprehensive.py, verify_database_integrity.py, verify_db.py, verify_freeze_gates.py (447), verify_ledger_0310833996.py, verify_license2616.py, verify_query_analysis.py` (`conftest.py` is legitimate). Also: `backend/scripts/` (10 files, incl. `test_crud_balance_updates.py`, `veg_oil_allocator.py`), `backend/setup/` (ad-hoc SQL/backup/`migrations_script.py`), `backend/DFIA_COPY`, `backend/extra/*.docx`, `backend/models.png`, 5 `.md` reports at backend root, `postcss.config.js` + `tailwind.config.js` + `theme/` (Django-Tailwind leftovers in an API-only backend). Names embed specific licence numbers (`0310833996`, `2616`) = one-off investigations.

### 9b. Loose files at repo root
- `.py` (11): `parity_extract_pdf_excel, parity_test_simple, parity_verification, reconciliation_comprehensive, reconciliation_matrix_test, reconciliation_test, run_django, test_api_reconciliation, validate_accounting, verify_ledger, verify_plans`
- `.ipynb` (2): `accounting_validation`, `verify_ledger_0310833996`; `route-browser-test.js`; `run_django.sh`
- `.txt` reports (6): `ledger_verification_report, AUDIT_STATUS, BUTTON_SYSTEM_AUDIT_SUMMARY, PHASE_1_SETUP_STATUS, QUALITY_GATES_SUMMARY, VERIFICATION_COMPLETION_SUMMARY`
- `3011009264 SONALIKA TRACTOR.pdf` - a business document at repo root (possible commercial/PII data; needs human review)
- 6 `nginx-*.conf` at root (server config, not code); `deploy-secrets.env.example`
- dirs `adf/`, `exc_pdf/`, `artifacts/`, `audit_evidence/`, `backups/`, `tests/` (root)

### 9c. Root `.md` sprawl: 258 files (+ 188 `.md` under `docs/`, 38 top-level entries in `docs/`)
| Category (by filename prefix) | Count | Examples |
|---|---|---|
| Phase/module/orchestration progress | 78 | `PHASE_*` 29, `MODULE_0x_*` 24, `ORCHESTRATION_*`, `AUTONOMOUS_*`, `MASTER_*`, `SESSION_*`, `AGENT_STATUS_TRACKER` |
| QA / verification / freeze / gate | 76 | `QA_*` 17, `RESPONSIVE_*` 11, `FILTER_*`, `ROUTE_*`, `FREEZE*`, `PRODUCTION_*`, `VISUAL_*` 6, `ACCESSIBILITY_*` 6 |
| UI / design system | 44 | `UI_*` 9, `DESIGN_*`, `*_SYSTEM_V2`, `DASHBOARD_*`, `SHELL_*` |
| Domain / other | 60 | `A3627_*`, `SION_*`, `LEDGER_*`, `AUTOPLAN_*`, `CALCULATION_*`, `BUSINESS_RULES_INVENTORY`, `KNOWN_ISSUES`, `ARCHITECTURE_AUDIT`, `MDS_REMOVAL_REPORT` |

(Categorisation is by prefix heuristic; boundaries are approximate, total is exact.)

Contradiction found: `MDS_REMOVAL_REPORT.md` ("MDS completely removed", status COMPLETE) is false. `master-data-service/`, `mds-client/`, `apps/core/mds_write.py`, `mds_payload.py`, `views/mds_status.py` and settings `MDS_*` all exist. The many `*FREEZE*` / `PRODUCTION_READY_DECLARATION` files cannot be treated as evidence. Only `CLAUDE.md`, `AGENTS.md`, `KNOWN_ISSUES.md`, `BUSINESS_RULES_INVENTORY.md`, `CALCULATION_*` look plausibly worth keeping after human review.

## 10. Scripts / ops inventory (names only)
`scripts/`: `dev/` 7 (quality-gate, doctor, services...), `development/` 6, a release-automation folder with 8 scripts (not opened - guarded path), `maintenance/` 5 (master merge/sync), `mds/` 5 (export/load/onboard), `imports/` 4 (DGFT fetch), `migration/` 3, `database/` 2, `diagnostics/` 2, `test/` + `testing/` 2, plus `dev-*.sh` 4 and `orchestrator.py`. `docker-compose.yml` is dev-only (Postgres 16 + Redis 7), `docker/postgres/initdb`.
