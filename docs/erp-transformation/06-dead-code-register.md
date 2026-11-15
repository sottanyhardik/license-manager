# 06 - Dead-Code Register (Phase Zero discovery)

Date: 2026-11-15. Branch: feature/version5. Method: read-only. Evidence from `.claude/index/dependents.tsv` (470 of 1004 indexed files have no importer; those were triaged), then grep over `backend/`, `frontend/`, `scripts/`, `.github/`, `backend/deploy/`, `docker-compose.yml`, `docs/`. `knip` / `ts-prune` are not installed in `frontend/node_modules`, so frontend analysis is grep-based. Nothing was deleted or edited. Migrations are never listed for removal.

Dynamic-use legend: none = no string/dispatch path possible; low = only a name-based path that was checked; med = plausible runtime/external path; high = likely used at runtime.
"Confidence" = confidence in the non-use claim.

## (A) Safe to remove with high confidence

| Item | Type | Evidence of non-use | Dynamic-use risk | Recommendation | Confidence |
|---|---|---|---|---|---|
| `frontend/src/layout/Sidebar.tsx` (155 lines) | FE component | Zero importers in `src`/`e2e` (layout uses TopNav); not in any lazy()/routes; no dependents in index | none | remove | High |
| `frontend/src/components/DataFilter.tsx` (68) | FE component | Zero references in `src` other than itself | none | remove | High |
| `frontend/src/components/FormField.tsx` (203) | FE component | Only unrelated name collisions (`validateFormFieldAccessibility`, `effectiveFormFields`); no import | none | remove | High |
| `frontend/src/components/Timeline.tsx` (48) | FE component | No importer (name hits are `types.ts` type names only) | none | remove | High |
| `frontend/src/components/item-async-select.tsx` (30) | FE component | No importer | none | remove | High |
| `frontend/src/components/AllotmentFormModal.tsx` (524) | FE component | No importer; no lazy()/dynamic import | none | remove | High |
| `frontend/src/components/ui/index.js` (21) | FE barrel | No `from "@/components/ui"` / `ui/index` import; consumers import per file | none | remove | High |
| `frontend/src/pages/errors/ServerError.tsx` (22) | FE page | Not referenced in `routes/AppRoutes.tsx` (only NotFound, Unauthorized imported) | none | remove | High |
| `frontend/src/pages/masters/tables/BalanceTab.tsx` (528) | FE component | No importer | none | remove | High |
| `frontend/src/pages/planning/ResidualPolicyEditor.tsx` (97) | FE component | No importer | none | remove | High |
| `frontend/src/utils/canonicalLedgerAdapter.js` (162) | FE util | No importer | none | remove | High |
| npm dep `dompurify` | npm | 0 imports in `src`, `e2e`, configs | none | remove from package.json (dependency change: human OK) | High |
| npm deps `jspdf`, `jspdf-autotable` | npm | 0 imports; PDFs are generated server-side (reportlab) | none | remove | High |
| npm dep `jwt-decode` | npm | 0 imports | none | remove | High |
| npm dep `exceljs` + `resolve.alias['exceljs']` in `vite.config.js:93` | npm + config | 0 imports in `src`; only the alias references it | none | remove dep and alias together | High |
| npm deps `@radix-ui/react-popover`, `@radix-ui/react-scroll-area` | npm | 0 imports (`popover` grep hits are only the CSS token `bg-popover`; no `ui/popover.tsx` or `ui/scroll-area.tsx`) | none | remove | High |
| npm dep `recharts` | npm | Only appearance is `vi.mock("recharts")` in `Dashboard.test.tsx`; no real import in `src` | low (stale mock must go too) | remove dep and the mock | High |
| `backend/apps/core/management/commands/rqworker.py` | mgmt cmd | Lazily imports `django_rq`; `django_rq`/`rq` not in requirements or INSTALLED_APPS; project uses Celery | low | remove | High |
| `backend/apps/license/services/item_pivot_aggregation.py` (202) | BE module | `ItemPivotAggregationService` has zero references anywhere in Python (apps, tests, scripts) | none | remove | High |
| `backend/apps/license/item_report.py` (732) | BE module | Zero importers; the live module is `apps/license/views/item_report.py` (different file) | low | remove (see C: django-tables2 chain) | High |
| `backend/apps/core/signals_materialized_views.py` + `tasks_materialized_views.py` | BE modules | Only import each other; neither registered in any `apps.py ready()`; `enable_auto_refresh` has no caller; Celery autodiscovery only loads modules named `tasks.py`, so those `@shared_task`s are never registered. Refresh is done by command `refresh_materialized_views` + `materialized_views.py` (kept) | low | remove both (update `docs/architecture/MATERIALIZED_VIEWS_GUIDE.md`) | High |
| `backend/lmanagement/tasks.py` | BE Celery tasks | `lmanagement` is not in INSTALLED_APPS so `autodiscover_tasks(INSTALLED_APPS)` never imports it; no reference in code/deploy; `backend/deploy/celery.service` runs `-A lmanagement` only | low | remove (its only imports, `backend/scripts/dgft_shipping_bill.py` and `boe.py request_bill_of_entry`, then lose their caller: see C) | High |

## (B) Archive (clutter; move to `legacy/` or `docs/archive/`)

| Item | Type | Evidence of non-use | Dynamic-use risk | Recommendation | Confidence |
|---|---|---|---|---|---|
| ~256 root `*.md` status/audit/QA/freeze/phase reports (258 total, all tracked; e.g. `MODULE_05_*`, `QA_*`, `PHASE_*`, `RESPONSIVE_*`, `FREEZE*`, `AUTOPLAN_*`) | docs | Point-in-time agent output; not referenced by scripts, CI, `.claude/settings.json`, CLAUDE.md. Only 2 prose mentions (`docs/modules/MODULE_1_FREEZE_GUIDE.md`, `.claude/agents/licence-domain-expert.md`) | none | archive to `docs/archive/root-reports/` | High |
| Keep at root: `CLAUDE.md`, `AGENTS.md`. Review before archiving: `KNOWN_ISSUES.md`, `BUSINESS_RULES_INVENTORY.md`, `CALCULATION_REFERENCE.md`, `CALCULATION_FLOW.md`, `DJANGO_RUNSERVER.md` | docs | May be the only record of business rules | none | distill into `docs/`, then move | Med |
| Root txt reports: `AUDIT_STATUS.txt`, `BUTTON_SYSTEM_AUDIT_SUMMARY.txt`, `PHASE_1_SETUP_STATUS.txt`, `QUALITY_GATES_SUMMARY.txt`, `VERIFICATION_COMPLETION_SUMMARY.txt`, `ledger_verification_report.txt` | docs | Same | none | archive | High |
| Root one-off scripts: `parity_extract_pdf_excel.py`, `parity_test_simple.py`, `parity_verification.py`, `reconciliation_comprehensive.py`, `reconciliation_matrix_test.py`, `reconciliation_test.py`, `test_api_reconciliation.py`, `validate_accounting.py`, `verify_ledger.py`, `verify_plans.py` | scripts | No importers; not in CI, `scripts/`, package.json; not collected by pytest (`testpaths = tests apps`) | none | archive to `legacy/scripts/` | High |
| `run_django.py`, `run_django.sh` | scripts | No references in scripts/, CI, docs/claude; superseded by `scripts/dev-start.sh` | low | archive | Med |
| `accounting_validation.ipynb`, `verify_ledger_0310833996.ipynb` | notebooks | Unreferenced | none | archive | High |
| Backend-root one-offs: `deep_trace.py`, `final_debug.py`, `reconciliation_detailed.py`, `trace_canonical_lines.py`, `trace_persistence.py`, `trace_sql.py`, `verify_accounting.py`, `verify_balance_detail.py`, `verify_comprehensive.py`, `verify_database_integrity.py`, `verify_db.py`, `verify_freeze_gates.py`, `verify_ledger_0310833996.py`, `verify_license2616.py`, `verify_query_analysis.py`, `test_all_queries.py`, `test_pdf_e2e_simple.py`, `test_pdf_parsing_e2e.py`, `test_persistence_debug.py`, `test_query_sequence.py`, `test_split_fix.py`, `test_transaction_commit.py` (all under `backend/`) | scripts | No importers, not collected by pytest, not in CI; hardcoded licence numbers | none | archive to `legacy/backend-scripts/` | High |
| `backend/scripts/{capture_dynamic_planning_baseline,golden_master_balance_exporters,verify_e5_plan,test_crud_balance_updates}.py`, `backend/setup/create_norm_specific_items.py` | scripts | No importers, no deploy/CI refs. `golden_master_*` / `capture_*baseline` are regression helpers: keep unless superseded by tests | low | archive (golden_master: needs human) | Med |
| `backend/{CANONICAL_LEDGER_VERIFICATION,E126_E132_SEMANTICS_EXTRACTION,GENERIC_SION_RULE_ENGINE,QA_RECONCILIATION_REPORT,RECONCILIATION_TESTS_SUMMARY}.md`, root `RECONCILIATION_REPORT_0310833996.md` | docs | Report output; the E126/E132 and GENERIC_SION docs may hold domain rules | none | archive after extracting rules | Med |
| `frontend/*.md` (13: `CLEANUP_ANALYSIS`, `MIGRATION_*`, `UI_*`, `REFACTORING_GUIDE`, etc.) | docs | Migration trackers; keep `README.md`, `COMPONENT_SPECS`, `DESIGN_TOKENS` | none | archive trackers | High |
| `frontend/route-browser-test.js`, `route-browser-test.mjs`, `route-authenticated-test.mjs`, `route-detailed-filter-test.mjs`; root `route-browser-test.js` | scripts | Not in package.json, playwright/vitest config, or CI | none | archive (superseded by `frontend/e2e`) | High |
| `backend/models.png` | image | Unreferenced; stale ER diagram | none | archive (or regenerate into docs) | High |
| `3011009264 SONALIKA TRACTOR.pdf` (root), `adf/` (18 PDFs, 3.1M), `exc_pdf/` (59 files, 1.6M), `artifacts/` (94 tracked, 19M), `backend/artifacts/`, `audit_evidence/` (54 files incl. `skeptic_check*.py`) | sample data / evidence | Tracked in git; no code path references. Real licence documents (possible commercial data) | none | move out of repo; consider history purge (needs human) | High |
| `backend/DFIA_COPY/` (210 tracked PDFs, 217M) | sample data | Tracked; only the `upload_dfia_copies` command takes a path argument, no hard-coded reference | low | move out of repo, keep as fixtures elsewhere | Med |
| Root `nginx-*.conf` x6 | deploy config | Referenced by `scripts/deployment/auto-deploy.sh`: do not remove | med | keep (could move to a `deploy/nginx/` dir together with the script) | High |
| Ignored/untracked: `backups/` (39M), `backend/media` (1.1G), `frontend/dist`, `backend/staticfiles` | local data | gitignored or untracked | n/a | no repo action | High |

## (C) Needs human confirmation

| Item | Type | Evidence | Dynamic-use risk | Recommendation | Confidence |
|---|---|---|---|---|---|
| Celery beat entries `sync-licenses-daily-midnight-ist` -> `license.tasks.sync_all_licenses`, and `update-balances-11am-ist` / `update-balances-8pm-ist` -> `identify_licenses_needing_update` in `backend/lmanagement/celery.py:43-70` | beat config | No task with either name is registered anywhere (`apps/*/tasks.py`, `core/sync/tasks.py`). Beat enqueues unregistered tasks that workers reject. Nightly licence sync and twice-daily balance refresh are therefore likely not happening | high (prod may run different code) | needs human: remove the entries or restore the tasks. This is a functional gap, not clutter | High |
| `backend/scripts/dgft_shipping_bill.py`; `request_bill_of_entry` / `be_details` in `apps/bill_of_entry/scripts/boe.py` | BE modules | After `lmanagement/tasks.py` is removed there is no live caller. DGFT WAF blocks server IPs (comment in celery.py) so probably dead, but may be run manually | med | needs human | Med |
| pip `django-tables2` + `apps/license/tables.py`, `table_columns.py`, `tests/test_tables.py` | pip dep + modules | Only importer of `tables.py` is the dead `item_report.py`; `table_columns.py` only used by `tables.py` | low | remove with item_report.py after confirming no template uses `render_table`; dependency removal needs approval | Med |
| `apps/core/cached_views.py` (146) | BE module | No runtime consumer (phase-05 audit says the same); documented in `REDIS_CACHING_GUIDE.md` | low | needs human (kept as future infra?) | Med |
| `apps/license/services/report_service.py` | BE module | No Python importer found; its template `license/report_pdf.html` presumably belongs to it; mentioned in `docs/operations/PURCHASE_STATUS_FK_MIGRATION.md` | med | verify no `import_module` string use before removal | Med |
| `apps/core/scripts/company_names.py` | BE script | Zero importers (name hits are local variables); uses `bs4` | low | needs human | Med |
| One-off data-fix management commands with no reference in scripts/deploy/CI: `merge_cardamom_item_names`, `update_sugar_items`, `update_aluminium_foil_items`, `clean_item_names`, `clean_duplicate_rowdetails`, `audit_item_name_merge`, `correct_a3627_active_rules`, `audit_restricted_olive_oil`, `backfill_parent_actual_targets`, `backfill_planning_actual_targets`, `reconcile_item_pivot`, `update_is_boe`, `update_exchange_rate`, `fetch_detail_bisc`, `fetch_detail_conf`, `report_fetch`, `sync_from_ge_server`, `update_dgft_descriptions`, `convert_license_table`, `check_db_structure`, `validate_db_fields`, `sync_database_schema`, `reset_migration_history`, `clearcache`, `check_user_roles`, `backfill_allocation_status`, `audit_ledger_orphan_documents`, `audit_license_item_plan_lifecycle`, `license/.../test_ledger_api.py` | mgmt cmds | Auto-discovered by Django, so callable by ops by name; no automated caller. Many are completed migrations/backfills. `reset_migration_history` and `delete_licenses_by_exporter` are destructive | med | archive completed backfills; review destructive helpers (needs human) | Med |
| Endpoints with no frontend caller (external use unknown): `unit-prices`, `scheme-codes` (core), `inventory-balance` viewset and `reports/inventory-balance/` (used only by `tests/e2e/test_api_smoke.py`), `throttle-status/`, `throttle-status/<scope>/`, `throttle-reset/`, `throttle-stats/`, `throttle-health/`, `licenses/<id>/replan-status/`, `password-reset-confirm/`, sync `delete-check/`, `media/download/`, trade `invoice-documents/view/<token>/` | API | No match in `frontend/src`. Throttle endpoints are probably ops/curl tools; password-reset-confirm is the email-link flow; sync endpoints are peer-server calls; invoice view is a tokenised external link | med-high | unknown external use: keep until API consumers are inventoried; sync, password-reset and invoice-view must stay | Med |
| Single-hit endpoints (verify not stale): `activity-logs`, `head-norms`, `import-item-suggestion/`, `license-item-plans`, `product-descriptions`, `sion-planning-rules`, `ledger-task-status/<id>/`, `bill-of-entries/parse-pdf/`, `licenses/parse-pdf/`, `change-password/` | API | One frontend reference each; in use | low | keep | High |
| `backend/requirements_python314.txt` | pip freeze | Pinned superset differing from `requirements.txt` (adds `lxml`, `python-dateutil`, etc.); CI uses `requirements.txt` | low | choose one source of truth | Med |
| `backend/extra/_consent_letter.docx`, `_request_letter.docx` | templates | May be loaded via docxtpl by path (not verified) | med | keep until checked | Low |
| npm devDep `baseline-browser-mapping` | npm | 0 imports; usually a browserslist-related hint | low | likely removable | Med |
| `master-data-service/` vs in-tree `apps/core/sync` + `mds-client` | architecture | `MDS_REMOVAL_REPORT.md` at root hints at partial removal; `INSTALLED_APPS += ["mds_client"]` is conditional | high | architecture decision, out of scope here | Low |

## (D) Looked dead but is used (do not remove)

| Item | Why it looked dead | Why it is live |
|---|---|---|
| All `backend/apps/*/urls.py`, `admin.py`, `apps.py`, `core/sync/urls.py` | No importer | Loaded via `ROOT_URLCONF` / admin autodiscover / INSTALLED_APPS |
| `apps/core/openapi.py` | No importer | `CoreConfig.ready()` imports it (drf-spectacular extensions) |
| `apps/core/cache_signals.py` | Only self/tests | `CoreConfig.ready()` calls `connect_m2m_signals()` |
| `apps/*/signals.py` (accounts, allotment, license), `master-data-service/masters/signals.py` | No importer | Imported in `ready()` |
| `apps/core/tasks.py`, `apps/license/tasks.py`, `apps/accounts/tasks.py`, `apps/core/sync/tasks.py` | Names only appear in strings | Celery autodiscover + beat names (`planning.recover_pending_replan_requests`, `license.cleanup_expired_ledger_packages`, `license.recover_license_ledger_package_jobs`) |
| `apps/core/materialized_views.py` | Few importers | Used by migration `0003_create_materialized_views` and command `refresh_materialized_views` |
| `apps/license/services/balance_snapshot.py` | Zero direct importers in index | `license_overview_summary.py` uses `from apps.license.services import balance_snapshot`; tests patch it |
| `apps/tasks/services/task_service.py` | No dependents in index | `apps/tasks/views.py` imports it package-style |
| `apps/reconciliation/services/queries.py` | No dependents | `from .services import queries as ...` in views, tests, `check_allocation_health` |
| `backend/scripts/parse_ledger.py`, `parse_ledger_htm.py`, `veg_oil_allocator.py` | Loose scripts | Imported by `license/views/ledger_upload.py`, `license/tasks.py`, `tests/test_ledger_parser.py` |
| `apps/core/scripts/license_script.py` | No importers | Lazy import at `license_script.py:87` |
| `__init__.py` markers (`exporters/*`, `utils`, `services`, `sion_planner_config`) | No dependents | Package markers / re-exports |
| `frontend/src/main.tsx` | No importer | Vite entry (`index.html`) |
| `Icon.tsx`, `DetailTable.tsx`, `GlobalErrorBoundary.tsx`, `ErrorBoundary.tsx`, `StatCard`, `EntityCard`, `components/primitives/*` | "Legacy primitives" suspicion | Have live importers. ErrorBoundary vs GlobalErrorBoundary and `primitives/` vs `ui/` overlap conceptually, but both sides are imported |
| `react-datepicker`, `react-select`, `cmdk`, `framer-motion`, `sonner`, `tw-animate-css`, `@tanstack/react-query-devtools`, `esbuild` | Suspected leftovers | Imported (`TradeForm`, `CommandPalette`, `PageTransition`, `main.tsx`, `tailwind.css`) or required by `vite.config.js` (`minify: 'esbuild'`) |
| npm `bootstrap-icons`, `react-toastify` | Memory said removable | Already absent from package.json; no residual imports |
| pip `numpy`, `docxtpl`, `pyzbar`, `pytesseract`, `pdf2image`, `redis`, `django-redis`, `whitenoise`, `django-extensions` | Few imports | Each has an importer or a settings string (`django_redis.cache.RedisCache`, WhiteNoise middleware, INSTALLED_APPS). `django-tables2` is live only via the dead chain in (C) |
| `frontend/src/test/*`, `src/tests/*` | No importers | Vitest globs |

## Other findings

- Missing pip deps: `backend/requirements.txt` lacks `beautifulsoup4` (imported by `scripts/dgft_shipping_bill.py`, `update_dgft_descriptions.py`, `core/scripts/company_names.py`) and `lxml`. `python-dateutil` and `python-docx` are present only transitively (celery, docxtpl). A fresh venv from `requirements.txt` fails on the bs4 commands.
- Commented-out code: only 3 lines of `// import|const|...` in `frontend/src`; negligible. Backend not scanned.
- `rqworker` command and `lmanagement/tasks.py` are leftovers from earlier queue designs (RQ, then Celery with a different app layout).

## Counts

- (A) 22 rows (11 FE files, 8 npm dep rows, 3 backend rows plus the rqworker/item_report/pivot rows: 22 total)
- (B) 17 rows (about 256 root md plus about 45 loose scripts/notebooks plus data directories)
- (C) 13 rows
- (D) 17 rows

## Suggested order

1. Frontend dead files and unused npm deps (verify with `typecheck`, `vitest`, `build`).
2. Backend dead modules in (A) after `scripts/dev/quality-gate.sh backend`.
3. Resolve the beat-schedule gap first: it is a functional issue, not clutter.
