# SAT — Architecture, Backend/API, Database and Performance Audit (Phases 1, 2, 8)

- Date: 2026-11-20 · Branch `feature/v5` · HEAD `ec3604cb` · working-tree diff hash `6f1712e03000` (`git diff | shasum | cut -c1-12`, identical at start and end; no application file touched)
- Agent: `sat-api-perf` · Evidence root: `~/lm_sat_evidence/api/` (scripts, logs, JSON, throwaway pytest in `tests/`)
- DB row counts at start (`lmanagement@localhost`, read-only): licences 2,185 · import items 26,818 · export items 2,178 · BOEs 14,425 · BOE rows 168,629 · allotments 6,526 · allotment items 11,610 · trades 0 · accounting vouchers 0 · users 10 · activity log 348,918 · replan requests 32,897 · companies 1,023.

## Methodology

- Phase 1: URL resolver iterated read-only (`p1_urls.py` -> `urls.json`); frontend client paths extracted by regex from non-test `frontend/src` (`p1_diff.py`) and diffed against the backend path set. Heuristic: dynamic bases (`${basePath}…`) cannot be resolved statically, so "orphan" = last static path segment appears nowhere in non-test frontend source (strict list); the looser exact-match list is far noisier and not reported as defects.
- Phase 2 write paths: pytest only, DB `test_lmanagement_sat_api` (created/destroyed by pytest), file `~/lm_sat_evidence/api/tests/test_sat_api.py` (77 tests), fixtures reused from `backend/conftest.py`. Throttling disabled in the harness only. Read-only DB probes on `lmanagement` inside `SET TRANSACTION READ ONLY` + rollback.
- Phase 8: DRF `APIClient.force_authenticate(superuser)` against `lmanagement` inside `atomic()` + `SET TRANSACTION READ ONLY` + rollback (all GETs returned 200, so none of the measured GETs writes). Throttling disabled and cache replaced by LocMem (cleared before every run) in the harness only. Each URL run twice: "cold" = first, "warm" = second (cache cleared in between, so both measure real work). Query counts via `CaptureQueriesContext` (query-log deque enlarged; first run was invalid above 9,000 queries and was discarded/re-run). Memory = `tracemalloc` peak of the request. Machine: local dev laptop, Postgres 18, single process; absolute times are baselines for this machine only.
- Not re-audited (per brief): CIF math, exports, deep security.

## 1. Phase 1 — Architecture / module discovery

| ID | Area | Status | Evidence / result |
|---|---|---|---|
| SAT-ARCH-001 | URL inventory | PASS | `urls.json` (exit 0): 1,254 resolved patterns; 670 under `/api` incl. `.json` format-suffix duplicates -> **375 unique API paths** served by **129 distinct view classes**; ~570 are Django-admin paths. Largest groups: masters 123, item-pivot 87 (incl. matching sub-API), licenses 73, license-ledger 51, accounting 50, trades 37, reconciliation 28, sion-planning-rules 25, bill-of-entries 23, auth 17, tasks 13 |
| SAT-ARCH-002 | Permission class per view | PASS | 129 views: AccountingPermission 49, IsAuthenticated 15, ReportPermission 15, MasterDataPermission 13, AllowAny 8, LicensePermission 7, UserManagementPermission 3, TradePermission 3, IsAdminUser 3, LedgerUploadPermission 2, AllotmentPermission 2, none 1 (`TokenRefreshView`, expected). AllowAny: health, 3 OpenAPI views, login, password-reset request/confirm, `InvoiceDocumentView` (token-based public document view — deep review belongs to the security agent). Default is `IsAuthenticated` |
| SAT-ARCH-003 | Frontend -> endpoint map | PASS-EXC | 207 distinct frontend client call literals; 135 backend paths matched statically; remainder are dynamic-base calls (`${base}bulk/`, master CRUD helpers) that cannot be resolved statically. Frontend entry points: `frontend/src/api/*.ts` (+ deprecated shim `frontend/src/services/api/*` re-exporting `@/api/*`); ~49 `path=` routes in `routes/AppRoutes.tsx` |
| SAT-ARCH-004 | Frontend calls to non-existent endpoints | FAIL | 14 exported client functions call paths with no backend route and **no caller anywhere** (dead code) -> D01 |
| SAT-ARCH-005 | Backend endpoints with no frontend caller | PASS-EXC | 28 strict orphan candidates (list in D02), several are intentional (docs/redoc/health/auth root) |
| SAT-ARCH-006 | Duplicate/legacy implementations | PASS-EXC | (a) two balance code paths: `LicenseBalanceCalculator`/`balance_snapshot` (`apps/license/services/`) vs `apps/core/scripts/calculate_balance.py` (`update_balance_values`, 8 production importers: allotment models/views, BOE models, license items/serializer/ledger views) — financial audit already covers equivalence (0 diffs); (b) `apps/reconciliation/services/allocation_service.py` is LIVE (imported by license ledger builder + reconciliation app + `/api/reconciliation/*` used by frontend), not orphaned; (c) frontend `services/api/*` shims duplicate `api/*`; (d) frontend `/api/reports/*` and legacy un-prefixed report routes (`/api/active-licenses/`, `/api/expiring-licenses/`, `/api/inventory-balance/`) both exist (see D02) |
| SAT-ARCH-007 | Financial calculation sites | PASS | `license/services/balance_calculator.py` (`LicenseBalanceCalculator`, `ItemBalanceCalculator`), `balance_snapshot.py` (`get_snapshot_bulk`), `core/scripts/calculate_balance.py`, `license/services/e126_plan.py`/`e132_plan.py` (wastage rebalance), `bill_of_entry/services/boe_service.py`, `reconciliation/services/allocation_service.py`, materialized views `license_balance_mv`/`item_balance_mv` (`core/materialized_views.py`) |
| SAT-ARCH-008 | Exports inventory | PASS | covered by `SAT_EXPORT_AUDIT.md` (25 families); not repeated |
| SAT-ARCH-009 | Local DB schema == code | FAIL | Migration `license.0067_import_item_mapping_approval` is **unapplied** on `lmanagement`; tables `license_importitemmappingapproval(version)` do not exist -> D03 |

## 2. Phase 2 — Backend / API

Run: `p2_api_pytest.log` — **77 tests: 70 passed, 7 failed, exit 1**. The 7 failures map to 5 defects below (each is a real finding; none is a harness error, one is a documented design-gap probe). Observations: `p2_observations.jsonl`.

| ID | Area | Status | Evidence |
|---|---|---|---|
| SAT-BE-001 | Auth required (15 list endpoints + garbage token) | PASS | 16/16 return 401 (`test_be001*`); exit 1 file-level only due to other IDs |
| SAT-BE-002 | Pagination shape/limits/ordering/filter/search/empty | PASS | all pass: `{count,next,previous,results}` on 7 resources; page_size cap 200 (default 25); out-of-range page 404 `{"detail":"Invalid page."}`; `ordering=±license_number` correct; unknown ordering 200 (ignored); search hit/miss; empty DB -> count 0 |
| SAT-BE-003 | Validation -> 400 shapes | FAIL | 9 of 10 create endpoints return 400 field-map; `POST /api/payments/` returns **500** (D04); malformed JSON 400 `{"detail":"JSON parse error …"}` on 7/7; wrong types 400; unknown FK ids 400; negative qty 400; expiry<issue 400 |
| SAT-BE-004 | Duplicate prevention | PASS | duplicate licence number, company IEC, username, BOE (number+date) -> 400 (BOE via `non_field_errors` "unique set"); DB unique (licence, serial) enforced |
| SAT-BE-005 | CRUD lifecycle (licences, masters, allotments, BOEs, 404s) | PASS-EXC | licence POST/GET/PATCH/PUT(empty->400)/DELETE(204)/404 OK; companies CRUD OK; allotment/BOE create 201; unknown id 404 on 7 resources. Exception: D05 (company delete) |
| SAT-BE-006 | Transaction rollback | PASS | nested validation failure -> 400, no licence row; injected failure inside `_create_import_item` after header save -> nothing persisted (`rollback-midflight persisted=false`) |
| SAT-BE-007 | Concurrent update probe | PASS-EXC | 2 simultaneous PATCHes on one licence: both 200, no deadlock/500, last write wins (final 2031-01-01). No `select_for_update`/version check on licence update (only BOE merge, allocation, accounting services lock rows) -> D06 (no optimistic locking) |
| SAT-BE-008 | Error envelope uniformity | PASS-EXC | no custom `EXCEPTION_HANDLER`; 400 = DRF field map everywhere, 404/401 = `{"detail"}`; deviations: accounting voucher 400 gives a bare string (`{"entity":"This field is required."}`, not a list) and voucher 404 adds `code`; unhandled 500 returns an HTML debug/error page, not JSON (D04 evidence) -> D07 |
| SAT-BE-009 | Permission matrix (light) | PASS | plain authenticated user without role: 403 on users, licences, vouchers, companies, trades, allotments, BOEs. Deep RBAC left to security agent |
| SAT-BE-010 | Date format symmetry | FAIL | outputs are `DD-MM-YYYY`; licence input accepts DD-MM-YYYY and ISO; BOE and trade accept **ISO only** (reject their own output format) -> D08 |
| SAT-BE-011 | Celery tasks eager (core/MV, sync, license) | PASS-EXC | MV tasks (5) SUCCESS incl. health `{'status':'healthy','views_checked':3}`; sync tasks no-op "Sync disabled"; `recover_pending_replan_requests` idempotent (1st dispatched 1, 2nd 0); `cleanup_expired_*` and `recover_*package_jobs` SUCCESS and repeatable; `replan_license_task` returns `{'status':'failed'}` for unknown id; `finalize_license_ledger_package_job` for unknown id ends **FAILURE** (unhandled DoesNotExist) while `enqueue_…` returns `dispatched:0` (inconsistent, Low, D09). `core.tasks.fetch_exchange_rates` (outbound HTTP) deliberately NOT RUN. Retry policy read: package item builder has exponential backoff `countdown=2**retries` with `PACKAGE_MAX_RETRIES`; MV tasks log+reraise with no retry; `acks_late+reject_on_worker_lost` on license tasks |
| SAT-BE-012 | Redis unavailable | FAIL | cache = `django_redis` (`CACHES`, no `IGNORE_EXCEPTIONS`), Celery broker/result also Redis. With Redis unreachable (test override to a dead port): licences, licence detail, companies, item-report, auth/me 200; **`/api/dashboard/` and `/api/item-pivot/` return 500** (hard cache dependency, no fallback) -> D10 |
| SAT-BE-013 | DB: orphan FKs | PASS | 371 FK columns checked on `lmanagement` (`p2_integrity.log`, exit 0): 0 orphans; 0 NOT VALID FKs; 0 disabled triggers; 6 "errors" are D03 |
| SAT-BE-014 | DB: negative / NULL business values | PASS | no negative import-item qty/CIF, BOE-row qty/CIF, allotment-item qty/CIF, licence balance; no NULL cif_fc/cif_inr/qty on import items or BOE rows (`p2_probes.log`, exit 0) |
| SAT-BE-015 | DB: data-quality probes | FAIL | licence **2101** number `'0'` with NULL dates/exporter (junk row); licence **2107** expiry date `0011-12-18` (< issue 2009-06-19); 46 licences with NULL expiry, 4 with NULL exporter, 7 without export items, 3 without import items, 24 BOEs without rows (e.g. `7713622-old`), 3,368 import items with NULL HS code (policy-permitted "Not verified") -> D11 |
| SAT-BE-016 | DB: decimal precision of CIF columns | PASS-EXC | `bill_of_entry_rowdetails.cif_inr/cif_fc` are `numeric(15,3)`; import/allotment/export-item/licence-balance/shortfall CIF are `numeric(15,2)`; `trade_licensetradeline.cif_fc` `numeric(20,2)`. 0 BOE-row values exceed 2 dp today, but the scale mismatch is a latent rounding-boundary risk -> D12 (Low) |
| SAT-BE-017 | DB: index coverage of hot filter columns | PASS | 23 hot columns checked (licence number/expiry/exporter/purchase status, BOE date/company/port/number, rows by BOE and import item, allotment company/date, allotment item, import item licence/HS, activity log timestamp/user, replan status/licence, transfer licence): all have a leading-column index (1,048 indexes total); 2 names did not exist (`is_active`, `item_id`) so were not testable. Seq-scan vs idx-scan on big tables healthy (BOE rows 3,857 seq / 6.74 M idx) |

## 3. Phase 8 — Performance baselines (measured, `p8_perf.log` exit 0, `p8_perf.json`)

All HTTP 200. Default list filters apply (licence list count 329 of 2,185; BOE list count 73 of 14,425 — default status/date filters; allotments 4,889 of 6,526).

| ID | Endpoint | cold s | warm s | queries | page | tracemalloc peak | payload |
|---|---|---|---|---|---|---|---|
| SAT-PERF-001 | licences ps=10 | 1.402 | 0.124 | 16 | 10 rows | 38.4 MB (cold start) | 21 KB |
| SAT-PERF-001 | licences ps=100 | 0.278 | 0.283 | 16 | 100 rows | 6.6 MB | 916 KB |
| SAT-PERF-001 | licences default (25) | 0.171 | 0.156 | 16 | 25 | 1.0 MB | 45 KB |
| SAT-PERF-002 | licence detail, largest (id 1775, 56 import items) | 0.853 | 0.858 | **290** | — | 5.2 MB | 107 KB |
| SAT-PERF-002 | licence detail, id 1 | 0.391 | 0.449 | **143** | — | 1.1 MB | 34 KB |
| SAT-PERF-003 | licence balance-ledger (1775) | 0.374 | 0.307 | 85 | — | 1.4 MB | 23 KB |
| SAT-PERF-003 | licence overview-summary (1775) | 0.201 | 0.185 | 47 | — | 0.4 MB | 0.6 KB |
| SAT-PERF-004 | BOE list ps=10 | 1.387 | 1.319 | **431** | 10 | 1.7 MB | 27 KB |
| SAT-PERF-004 | BOE list ps=100 (73 rows) | 9.46 | 10.98 | **3,578** | 73 | 8.3 MB | 161 KB |
| SAT-PERF-005 | allotment list ps=10 | 0.350 | 0.343 | 30 | 10 | 6.0 MB | 36 KB |
| SAT-PERF-005 | allotment list ps=100 | 0.807 | 0.793 | **179** | 100 | 12.1 MB | 268 KB |
| SAT-PERF-006 | item-pivot (`sion_norm=E5`) | 3.709 | 3.802 | 109 | — | 45.0 MB | 11.2 MB |
| SAT-PERF-007 | item-report (all) | 4.381 | 4.667 | 17 | — | **229.8 MB** | **65.3 MB** |
| SAT-PERF-008 | dashboard | 0.097 | 0.077 | 19 | — | 0.3 MB | 2.4 KB |
| SAT-PERF-009 | planned-report | 0.811 | 0.839 | 12 | — | 37.0 MB | 10.5 MB |
| SAT-PERF-010 | masters companies ps=10 / ps=100 | 0.019 / 0.035 | 0.011 / 0.031 | 2 / 2 | 10 / 100 | 0.3 / 0.5 MB | 7 / 56 KB |
| SAT-PERF-011 | license-items ps=100 | 0.054 | 0.057 | 3 | 100 | 0.8 MB | 18 KB |
| SAT-PERF-012 | license-ledger list / inventory-balance summary / trades ps=100 | 0.010 / 0.017 / 0.010 | 0.005 / 0.017 / 0.008 | 2 / 4 / 1 | — | <0.5 MB | <4 KB |

N+1 assessment (queries at page 10 vs 100): licences **flat 16/16 — no N+1**; masters flat 2/2; **BOE list scales ~43 -> 49 queries per row (431 for 10 rows, 3,578 for 73) — N+1, FAIL (D13)**; allotments 30 -> 179 (~1.7 queries/row, mild N+1, D14); licence detail 143 -> 290 queries scales with item count (D15). Status: PERF-001/003/006/008/009/010/011/012 PASS (baselines recorded; item-pivot 3.7 s and planned-report 0.8 s are a single un-paginated payload of 11 MB / 10 MB); PERF-002 PASS-EXC (D15); PERF-004 FAIL (D13); PERF-005 PASS-EXC (D14); PERF-007 FAIL-EXC (D16, 65 MB response / 230 MB RSS-equivalent peak, 4.4 s).

Suggested regression thresholds (derived from these baselines, not business-approved): licence list <= 20 queries and flat in page size; BOE list <= 20 queries flat; licence detail <= 150 queries; item-pivot(E5) < 5 s; item-report < 6 s.

## 4. Defect list

| ID | Sev | Category | Module | Summary |
|---|---|---|---|---|
| SAT-API-D01 | Low | Dead code / contract | frontend `api/licenseApi.ts`, `api/allotmentApi.ts` | 14 client functions call non-existent endpoints, no callers |
| SAT-API-D02 | Low | Orphan endpoints | backend urls | 28 strict-orphan endpoints (+ duplicate legacy report routes) |
| SAT-API-D03 | Medium | Environment / schema | local DB | migration `license.0067` unapplied on `lmanagement` |
| SAT-API-D04 | High | Error handling | trade `/api/payments/` | any POST returns 500 (IntegrityError) |
| SAT-API-D05 | Medium | Referential integrity | core master delete / trade | deleting a company silently NULLs trade parties and licence exporter (204) |
| SAT-API-D06 | Low | Concurrency | licence update | no optimistic locking; last write silently wins |
| SAT-API-D07 | Low | Consistency | accounting / 500 pages | error shape deviations; HTML 500 |
| SAT-API-D08 | Medium | API contract | BOE, trade serializers | input date format ISO-only while output is DD-MM-YYYY |
| SAT-API-D09 | Low | Celery | license tasks | finalize job task fails on missing job vs graceful siblings |
| SAT-API-D10 | Medium | Resilience | dashboard, item-pivot | HTTP 500 when Redis is down |
| SAT-API-D11 | Medium | Data quality | local data | junk/invalid licence rows and dates |
| SAT-API-D12 | Low | Precision | BOE rows | CIF stored 3 dp vs 2 dp elsewhere |
| SAT-API-D13 | High | Performance | BOE list | N+1: ~43-49 queries per row, 9.5-11 s for 73 rows |
| SAT-API-D14 | Low | Performance | allotment list | ~1.7 queries per row |
| SAT-API-D15 | Medium | Performance | licence detail | 143-290 queries, scales with items |
| SAT-API-D16 | Medium | Performance | item-report | 65 MB response, 230 MB peak, un-paginated |

### Detail

**SAT-API-D01 (Low) — Dead frontend clients for non-existent endpoints.** Repro: grep `frontend/src/api/*.ts`. Expected: every client function maps to a route. Actual: `fetchLicenseImportItems`, `fetchLicenseExportItems`, `fetchLicenseBalance`, `exportLicenseLedgerPDF` (`licenses/{id}/ledger-pdf/`), `exportLicenseItemReport`, `fetchLicenseTransactions`, `fetchLicenseAllocations`, `updateLicenseFlags` (`api/licenseApi.ts` ~l.54-147) and `allocateItem` (`allocate-item/`; backend has `allocate-items/`), `updateAllocation`, `deleteAllocation`, `exportAllotmentPDF`, `exportAllotmentExcel`, `convertToBOE` (`api/allotmentApi.ts` l.40-147) hit paths absent from the resolver; none has a non-test caller (verified by name grep). Evidence `p1_diff.json`. Root cause: backend actions renamed/removed, client not pruned. Impact: latent 404 if anyone wires them; misleading API surface. Remediation: delete or repoint. Business approval: N.

**SAT-API-D02 (Low) — Orphan backend endpoints (no non-test frontend reference to the last path segment).** `/api/accounting/cost-centres/`, `accounting/entities/{}/financial-years/`, `accounting/lower-deduction-certificates/`, `auth/password-reset-confirm/`, `inventory-balance/` and `/{}/`, `item-pivot/matching/admin/rollback/`, `item-pivot/matching/decide-products/`, `item-pivot/recommendations/`, `license-actions/update-license-transfer/`, `license-actions/bulk-update-license-transfer/`, `license-actions/{}/fetch-ledger/`, `license-item-plans/planning-norms/`, `license-ledger/download-requests/{}/download-zip/`, `…/licenses/{}/draft-download/`, `license-ledger/{}/financial-ledger-pdf/`, `licenses/parle-report/`, `licenses/{}/balance-excel-unused/`, `masters/throttle-{health,reset,stats,status,status/{}}/`, `reports/inventory-balance/`, `sync/delete-check/`, `trades/{}/resolve-final-party/`, plus `/api/`, `/api/redoc/` (intentional). Heuristic limits apply (dynamic URL building could hide callers). Also duplicate legacy route families: `/api/active-licenses|expiring-licenses|inventory-balance/*` vs `/api/reports/*`. Remediation: owner confirm; deprecate. Approval: Y (removal of API surface).

**SAT-API-D03 (Medium) — Local DB behind code by one migration.** Repro: `MigrationExecutor.migration_plan` -> `[('license','0067_import_item_mapping_approval')]`; orphan probe errors `relation "license_importitemmappingapproval" does not exist`. Expected: dev DB migrated to HEAD (migration is in the tree; `makemigrations --check` clean). Actual: ImportItemMappingApproval/Version tables absent, so any local request touching mapping approvals (`/api/item-pivot/matching/item-name-mapping/import/approvals/*`) will 500 against `lmanagement`. Evidence `p2_integrity.log`. Root cause: migration not applied locally (not run by this audit by rule). Remediation: owner applies `migrate` to local DB. Approval: Y (migrate is approval-gated).

**SAT-API-D04 (High) — `POST /api/payments/` always returns HTTP 500.** Repro: authenticated superuser, `POST /api/payments/ {}` or `{"trade":<id>,"amount":"100.00","date":"2025-01-01"}`. Expected: 400 validation, or 201 for a valid trade. Actual: `IntegrityError: null value in column "trade_id" of relation "trade_licensetradepayment"` -> 500 HTML (`payments-empty-real`, `payment-create` = 500). Evidence `p2_api_pytest.log` (3 failing tests: `test_be003[payments]`, `test_be003f`, `test_be005e`), `p2_observations.jsonl`. Root cause: `TradePaymentViewSet` (`apps/trade/api/views.py:698`, generic `MasterViewSet.create_viewset`) uses `LicenseTradePaymentSerializer` (`apps/trade/api/serializers.py:54-60`, fields `id,date,amount,note` — no `trade`) so the required FK is never populated. Payments are only writable nested under trades. Impact: unauthenticated-to-500 noise, unhandled DB errors, endpoint unusable; no data written. Remediation: make the viewset read-only/ remove create, or add a validated `trade` field. Approval: Y (API contract).

**SAT-API-D05 (Medium) — Master delete silently orphans trade parties / licence exporter.** Repro (test DB): `DELETE /api/masters/companies/{to_company_id}/` for a company used as `to_company` of a trade -> 204; trade `to_company_id` becomes NULL (`company-delete-trade-party`). Same for licence `exporter` (SET_NULL) — production data has 4 licences with NULL exporter. Expected: protected like BOE/allotment (`PROTECT`, 400 with message). Actual: `LicenseTrade.from_company/to_company` and `LicenseDetailsModel.exporter` are `SET_NULL`; only `LicenseOwnership.current_owner`, BOE, allotment, `final_party` are PROTECT. Root cause: model FK `on_delete` choices (`apps/license/models/header.py:70-74`, trade model `from_company/to_company`). Impact: loss of invoice counterparties (financial records) after a master delete. Remediation: PROTECT or soft-delete. Approval: Y (business rule/schema).

**SAT-API-D06 (Low) — No optimistic concurrency.** Two concurrent PATCHes both succeed, last write wins; no version/etag field in licence payload (`optimistic-lock-field present=false`), no `select_for_update` in licence write path (`apps/license/api/serializers/_license_write.py`). Impact: lost updates between editors. Remediation: `updated_at` precondition or row lock. Approval: Y.

**SAT-API-D07 (Low) — Error envelope deviations.** Accounting voucher 400 returns a string not a list (`{"entity":"This field is required."}`), voucher 404 adds `code`; unhandled exceptions return an HTML page. No project exception handler (`REST_FRAMEWORK` lacks `EXCEPTION_HANDLER`). Impact: client error rendering has to special-case. Remediation: common handler returning JSON. Approval: Y (contract).

**SAT-API-D08 (Medium) — Date input/output asymmetry.** Output `DD-MM-YYYY` (`DATE_FORMAT`), licence accepts both; `bill-of-entries` and `trades` reject `01-01-2024` ("Use one of these formats instead: YYYY-MM-DD") (`date-in-ddmmyyyy-rejected`: licences false, BOE true, trades true). Round-tripping a GET payload into PUT fails. Root cause: BOE/trade serializers lack `input_formats` that licence serializer sets (`apps/core/serializers/fields.py` is peer-modified, uncommitted). Remediation: shared date field. Approval: Y.

**SAT-API-D09 (Low) — Celery finalize on missing job fails.** `finalize_license_ledger_package_job(99999999)` -> FAILURE `LicenseLedgerPackageJob matching query does not exist.` (`apps/license/tasks.py:482-483`), while `enqueue_…` returns `{'dispatched': 0}` and `replan_license_task` returns a failed-status dict. Impact: noisy worker errors on stale ids; no retry storm (no autoretry). Approval: N.

**SAT-API-D10 (Medium) — Redis outage -> 500 on dashboard and item-pivot.** Repro: `CACHES.default.LOCATION=redis://127.0.0.1:1/1` (test settings override) then GET `/api/dashboard/`, `/api/item-pivot/?sion_norm=E5` -> 500 (`redis-down`); other tested endpoints 200. Root cause: direct `cache.get/set` (`apps/license/api/views/dashboard.py:9`, `item_pivot_report.py:19,125`) with django-redis and no `IGNORE_EXCEPTIONS` (`lmanagement/settings.py:410-419`). Impact: reporting outage whenever Redis is down (Celery also needs it). Remediation: `DJANGO_REDIS_IGNORE_EXCEPTIONS=True` or fallback. Approval: N.

**SAT-API-D11 (Medium) — Data-quality rows in local data.** Licence 2101 (`license_number='0'`, NULL dates/exporter), licence 2107 expiry `0011-12-18` (before issue 2009-06-19, likely typo), 46 NULL expiry dates, 4 NULL exporters, 24 BOEs without rows (incl. `7713622-old`), 3 licences without import items, 7 without export items. The API's own validation rejects expiry<issue on create (BE-003e), so these came from import/sync/legacy. Impact: wrong expiry/active filters, reports. Remediation: owner data clean-up (no agent DB writes). Approval: Y.

**SAT-API-D12 (Low) — CIF scale mismatch.** `RowDetails.cif_inr/cif_fc` numeric(15,3) vs 15,2 on licence/allotment items. 0 current values exceed 2 dp. Latent rounding boundary when summing 3 dp rows against 2 dp balances. Financial audit found 0 diffs today. Approval: Y (business rule).

**SAT-API-D13 (High) — BOE list N+1.** `GET /api/bill-of-entries/?page_size=10` 431 queries / 1.39 s; `page_size=100` (73 rows) 3,578 queries / 9.5-11.0 s; ~43-49 queries per BOE. Expected: constant query count. Root cause: BOE serializer per-row related lookups/balance computation (`apps/bill_of_entry/api/serializers.py`, `views.py` queryset prefetch incomplete) — exact line not isolated (no profiler run beyond counts). Impact: unusable at larger page sizes / data volume (14,425 BOEs total; unfiltered list would be ~20 min of DB time). Remediation: prefetch/annotate. Approval: N.

**SAT-API-D14 (Low) — Allotment list** 30 q (10 rows) -> 179 q (100 rows), ~1.7 q/row. Approval N.

**SAT-API-D15 (Medium) — Licence detail** 143 queries (id 1) and 290 (id 1775, 56 items); 0.85 s. Scales with item count. Approval N.

**SAT-API-D16 (Medium) — Item-report** returns 65.3 MB JSON, peak 229.8 MB, 4.4-4.7 s for default filters, un-paginated; item-pivot(E5) 11.2 MB / 3.7 s; planned-report 10.5 MB. Risk for multi-user memory pressure. Approval: N.

## 5. Business ambiguities (owner decision needed)

1. Should deleting a company/port referenced by trades or licences be blocked (PROTECT) or soft-deleted (D05)?
2. Should BOE row CIF stay at 3 dp or be normalised to 2 dp (D12)?
3. Are `/api/payments/` and the legacy un-prefixed report routes meant to stay public API (D02/D04)?
4. Is junk licence `0` / year-0011 expiry on licence 2107 to be corrected by the owner (D11)?

## 6. Limitations

- Frontend mapping is static/regex based; dynamic URL builders limit exact matching (counts are indicative, defects D01/D02 were verified by name grep).
- Perf on one local machine/one process; no concurrent load; cache replaced by LocMem; BOE list measured with default filters (73 of 14,425 BOEs); trade/payment/voucher/accounting perf not measurable (0 rows). Memory = Python tracemalloc peak only (not RSS).
- Write-path tests ran on a freshly created test DB with factory fixtures, not production-shaped data; trades/accounting happy paths beyond create/validation are covered by the existing 4,140-test suite, not re-run.
- Throwaway tests (`~/lm_sat_evidence/api/tests/`) are not in the repo; the first harness runs had assertion/payload mistakes of my own (list-only endpoints, date formats) that were corrected; only final-run results are reported (run 1 log overwritten, observations kept as `p2_observations.run1.jsonl`).
- Not run: `fetch_exchange_rates` (outbound HTTP), real Celery worker/broker retry behaviour, DB migration (D03), Redis-down for Celery tasks, load/soak tests, concurrency beyond a 2-writer probe.
- Security depth (IDOR/XSS/CSRF/JWT) deliberately excluded.
