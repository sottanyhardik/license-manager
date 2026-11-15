# 07 - Performance Baseline (Phase Zero, measure-only)

Date 2026-11-15, branch `feature/version5`. **No source file was modified.** All measurements are against the local dev DB `lmanagement` (localhost), GET requests only, no writes, no migrations, no materialized-view refresh, no Celery dispatch. Nothing in this document is an estimate unless it is labelled "expected" (those are derived from query counts, not measured).

## 1. Method and environment

| Item | Value |
|---|---|
| Hardware | Apple M5 Pro, 18 cores, 24 GiB RAM, macOS 26 (Darwin 25.6) |
| Stack | Python 3.14.10, Django 6, DRF, PostgreSQL 18.7 (Homebrew, same host), Redis 127.0.0.1 (not used during measurement, see below) |
| Harness | in-process `rest_framework.test.APIClient` with `force_authenticate` on the lowest-id active superuser (user id 1). No HTTP server, no network, no gunicorn: numbers are server-side compute + serialisation + JSON render only. Real latency in production adds TLS/network and, for payloads over 1 MB, transfer time |
| Query capture | `CaptureQueriesContext` (count, per-query time). `queries_log` cleared before each run |
| Duplicates | `dup_pattern` = sum of (n-1) over SQL statements that repeat after literals/IN-lists are normalised to `?` (the N+1 signal). `dup_exact` (byte-identical SQL repeated) is in the JSON and in the appendix script output |
| Runs | 3 cold runs per endpoint, **median reported**; cache cleared before each. One extra primed "warm" run (reports whether the view caches). One more run under `tracemalloc` for peak Python memory (not used for timing, tracemalloc slows execution) |
| Cache isolation | `override_settings(CACHES=LocMem)`: Redis was neither read nor written, so every "cold" figure is the true uncached cost; "warm" shows the effect of view-level caches that exist today |
| Activity log | `TESTING=true` disables `ActivityLogMiddleware`'s writer thread (otherwise every request would INSERT into `core_activitylog`). Its cost is therefore **not** in the numbers (see bottleneck 10) |
| Safety | script asserts `DB_HOST in (localhost,127.0.0.1)` and `NAME == lmanagement`; `test_lmanagement` untouched; EXPLAIN ANALYZE only issued for statements starting with SELECT/WITH |
| Payload | `len(response.content)` of the first cold run, KiB |

### Dataset (rows, from `pg_stat_user_tables` / counts)

| Table | Rows |
|---|---|
| licences (`license_licensedetailsmodel`) | 2,185 |
| licence import items | 26,818 |
| bills of entry | 14,392 |
| BOE row details | 168,513 (of which **146,554 have no BOE**, i.e. ledger-sourced debit rows; only 21,959 are attached to a BOE; max 42 rows on one BOE) |
| allotments / allotment items | 6,499 / 11,561 |
| **trades / trade lines** | **0 / 0** |
| activity log | 334,352 |
| materialized views | `license_balance_mv` 2,185 rows, `item_balance_mv` 26,818, `dashboard_stats_mv` 1 |

Representative licences (ids only): **large** = licence 1775 (1,325 BOE debit rows, 56 import items); **typical** = licence 729 (median, 24 BOE rows). Allotment 6578 (large licence), BOE 20412 (BOE on the large licence, 42 queries) and BOE 27150 (most rows on one BOE: 42). Reports used `sion_norm=E5` (most frequent norm on export lines).

### Limits of this baseline (read before trusting a number)

1. **No trades exist in the local DB**, so trade/invoice list and detail could not be measured (list returns an empty page in 2 ms, detail has no id to fetch). Any trade-line query inside other endpoints (`calculate_purchase_credit`, `calculate_trade`, SALE sums) hits an empty table here: their *counts* are valid, their *milliseconds* are understated versus production.
2. Single-user, single-process, warm Postgres buffers (all plans showed `shared hit`, no reads). Production under concurrency and cold cache will be slower; relative ranking should hold because the dominant cost is query count, not query time (no individual query exceeded ~20 ms).
3. `GET /api/reports/license-purchase-profit/` returned 400 and `GET /api/reports/inventory-balance/` without `sion_norm` returned 400 (required params; the call with `sion_norm=E5` is reported). License-purchase-profit was not measured with valid params.
4. Redis behaviour, gunicorn/nginx compression, and the browser were not measured (no running server stack; frontend section is static analysis plus `dist/` sizes).

## 2. Results (cold = median of 3, cache cleared)

Columns: SQL queries, repeated-pattern queries (N+1 signal), total SQL ms, wall ms, warm ms (view cache primed), peak Python MiB (tracemalloc), payload KiB. Endpoints are GET under `/api/`.

| Endpoint | HTTP | Queries | Dup pattern | SQL ms | Wall ms | Warm ms | Peak MiB | KiB |
|---|---|---|---|---|---|---|---|---|
| license list (default page) | 200 | 118 | 99 | 66 | 105 | 101 | 0.8 | 43 |
| license list (page_size=100) | 200 | 490 | 469 | 75 | 208 | 207 | 5.9 | 890 |
| license list (search=5-char prefix) | 200 | 134 | 115 | 58 | 105 | 94 | 1.9 | 284 |
| license detail (typical) | 200 | 158 | 97 | 28 | 117 | 165 | 1.2 | 44 |
| license detail (large) | 200 | 289 | 229 | 156 | 339 | 327 | 3.9 | 101 |
| license nested-items (large) | 200 | 771 | 733 | 202 | 786 | 750 | 6.1 | 67 |
| license overview-summary (large) | 200 | 47 | 25 | 54 | 84 | 72 | 0.3 | 1 |
| license overview-boes (large) | 200 | 4 | 0 | 17 | 22 | 22 | 0.2 | 2 |
| license overview-allotments (large) | 200 | 5 | 0 | 11 | 15 | 15 | 0.1 | 2 |
| license overview-items (large) | 200 | 3 | 0 | 10 | 15 | 15 | 0.2 | 14 |
| license overview-invoice-ledger (large) | 200 | 3 | 0 | 10 | 13 | 12 | 0.1 | 0 |
| balance-ledger (typical) | 200 | 81 | 40 | 28 | 92 | 114 | 0.7 | 19 |
| balance-ledger (large) | 200 | 85 | 44 | 103 | 155 | 169 | 0.8 | 23 |
| balance-excel (typical) | 200 | 180 | 129 | 139 | 289 | 286 | 1.4 | 16 |
| balance-excel (large) | 200 | 423 | 372 | 251 | 534 | 632 | 2.6 | 17 |
| balance-pdf (typical) | 200 | 253 | 206 | 144 | 338 | 324 | 3.2 | 28 |
| balance-pdf (large) | 200 | 701 | 654 | 243 | 642 | 697 | 4.5 | 47 |
| allotment list | 200 | 55 | 47 | 65 | 141 | 125 | 5.9 | 72 |
| allotment detail | 200 | 20 | 15 | 17 | 30 | 27 | 0.6 | 15 |
| BOE list | 200 | 1208 | 1182 | 526 | 1168 | 1211 | 2.7 | 46 |
| BOE detail (large licence) | 200 | 42 | 17 | 25 | 50 | 44 | 0.3 | 1 |
| BOE detail (most rows) | 200 | 849 | 824 | 483 | 963 | 902 | 2.3 | 16 |
| trade list | 200 | 1 | 0 | 1 | 2 | 2 | 0.2 | 4 |
| trade detail (no trades in DB) | 404 | - | - | - | - | - | - | - |
| dashboard | 200 | 19 | 0 | 31 | 40 | 0 | 0.2 | 2 |
| reconciliation summary | 200 | 152 | 140 | 12 | 57 | 53 | 1.2 | 0 |
| reconciliation missing-boe | 200 | 1 | 0 | 1 | 3 | 2 | 0.2 | 0 |
| reconciliation missing-invoice | 200 | 146 | 140 | 5 | 46 | 49 | 1.2 | 8 |
| reconciliation cif-comparison | 200 | 1 | 0 | 0 | 1 | 1 | 0.1 | 0 |
| reconciliation qty-comparison | 200 | 1 | 0 | 0 | 1 | 1 | 0.1 | 0 |
| reconciliation duplicate-debits | 200 | 1 | 0 | 1 | 2 | 1 | 0.1 | 0 |
| report item-pivot | 200 | 202 | 175 | 229 | 856 | 32 | 66.8 | 15920 |
| report item-report | 200 | 17 | 0 | 219 | 1000 | 1065 | 209.0 | 61027 |
| report inventory-balance | 400 | 0 | 0 | 0 | 0 | 0 | 0.0 | 0 |
| report inventory-balance (sion_norm=most common) | 200 | 5 | 0 | 29 | 183 | 171 | 12.2 | 11 |
| report item-pivot (sion_norm=most common) | 200 | 71 | 46 | 108 | 279 | 10 | 19.6 | 4734 |
| report active-licenses | 200 | 7034 | 7013 | 1886 | 5835 | 5582 | 43.5 | 3835 |
| report expiring-licenses | 200 | 234 | 213 | 86 | 217 | 216 | 1.4 | 83 |
| report planned-report | 200 | 12 | 0 | 91 | 227 | 225 | 34.9 | 10184 |
| report license-purchase-profit | 400 | 0 | 0 | 0 | 0 | 0 | 0.0 | 0 |
| item-pivot available-norms | 200 | 1 | 0 | 0 | 1 | 1 | 0.1 | 0 |

Notes on the table:
- `balance-ledger` (the workspace API) is comparatively healthy: 85 queries / 155 ms on the largest licence. The expensive balance paths are the callers that recompute balance per row (bottlenecks 1-2).
- Dashboard: 19 queries / 40 ms cold, **0.4 ms warm** (Redis-cached 5 min, `dashboard.py:57-83`). Item-pivot: 856 ms cold, 32 ms warm (cached 300 s, `item_pivot_report.py:581-595`). `item-report`, `active-licenses`, `planned-report`, `expiring-licenses` show warm = cold: **not cached**.
- Overview tab endpoints (`overview-boes/allotments/items/invoice-ledger`) are cheap (3-5 queries, 13-22 ms): the licence overview page is dominated by `GET /licenses/{id}/` (see 6.3 and bottleneck 3).

## 3. Top 10 bottlenecks (ranked by user-visible cost x frequency)

"Expected gain" is derived from the measured query counts; it is **not** measured. "Output risk" = could the fix change numbers/response shape.

### 1. Active-licenses report: 7,034 queries, 5.8 s, uncached
- Evidence: 7,034 queries (7,013 repeated patterns), SQL 1,886 ms, wall 5,835 ms, 45.6 MiB, 3.8 MB payload; warm run 5,582 ms (no cache).
- Repeated SQL and location:
  - x2,614 `SELECT core_itemnamemodel.id, name FROM core_itemnamemodel INNER JOIN license_licenseimportitemsmodel_items ... WHERE importitem_id = ?` at `backend/apps/license/views/active_licenses_report.py:225` (`import_item.items.values('id','name')` inside `for import_item in import_items`, called from `_get_items_with_balances` <- `_build_license_data:173`). About 37% of all queries, 816 ms.
  - x396-404 each of `calculate_credit` (`backend/apps/license/services/balance_calculator.py:106`), `calculate_hidden_boe_debit_total` (`:584`), `calculate_purchase_credit` (`:1112`), `calculate_trade` (`:1084`) plus about 7 more per licence, reached through `license_obj.get_balance_cif` at `active_licenses_report.py:113` -> `backend/apps/license/models/core.py:349` -> `LicenseBalanceCalculator.calculate_financial_balance` (`balance_calculator.py:1576`). One full financial-balance recomputation (about 11 queries) per licence for ~400 licences.
- EXPLAIN ANALYZE of the slowest single query (the prefetch of item names, 19.9 ms in the tracer): Index Only Scan on `license_licenseimportitemsmodel_items` + Hash Joins, execution about 4 ms, `Heap Fetches: 0`. The DB is not the problem; call count is.
- Proposed fix: (a) `prefetch_related('import_license__items')` and read `.all()` instead of `.values()` per item (pure N+1 removal); (b) compute balances through a batched/bulk balance map (the codebase already has batched siblings, e.g. `calculate_debited_quantity_for_items`, `available_value_bulk_map`) or read the persisted `LicenseBalance` row, instead of per-licence recomputation; (c) add a view cache with the existing `view:active_licenses*` invalidation pattern (already emitted by `cache_signals.py:50-56` but nothing sets that key today).
- Expected gain: (a) alone about -37% queries; (a)+(b) to well under 500 queries, 5.8 s -> about 0.3-0.6 s; (c) makes repeat hits about 1 ms.
- Output risk: (a) none. (b) **BUSINESS-RULE-ADJACENT**: it touches the CIF balance path; must keep `calculate_financial_balance` results byte-identical and needs `cif-balance-auditor` review plus a before/after diff of the report JSON on this dataset. (c) staleness window equals cache TTL unless trade/allotment/BOE signals also invalidate it (trade models have no invalidation receiver today, see 9).

### 2. Bill-of-entry list and detail: 1,208 queries / 1.17 s per page of 25; 849 queries / 0.96 s for a 42-row BOE
- Evidence: list: 1,208 queries (1,182 repeated), SQL 526 ms, wall 1,168 ms. Detail (BOE 27150, 42 rows): 849 queries, 963 ms. About 48 queries per BOE on the list and about 20 per row on detail. (BOE 20412 detail: 42 queries, 50 ms, because its rows share fewer distinct licences.)
- Repeated SQL and location: `balance_calculator.py:106/584/1084/1112/1529` x78-84 each, all reached via `backend/apps/bill_of_entry/serializers.py:52` and `:97` (`authoritative_available_cif` -> `effective_source_row_cif_available(licence=item.license, ...)` in `backend/apps/license/services/effective_cif_mode.py:123` -> `project_effective_item_cif:85` -> `LicenseDetailsModel.get_balance_cif` `models/core.py:349`). Every BOE row recomputes the whole licence financial balance; nothing is memoised per licence within the request. Same pattern exists in `backend/apps/trade/serializers.py:114,155` (not measurable here, no trades).
- EXPLAIN: slowest single query is the list SELECT DISTINCT at 2.1 ms (Limit/Unique/Sort over 71 rows, 97 buffer hits): fine.
- Proposed fix: memoise the per-licence balance in serializer context (key = licence id, computed once per request) or batch it in the viewset; also `select_related('sr_number__license')`. Longer term, serve from `LicenseBalance`.
- Expected gain: about 1,200 -> 100-150 queries; 1.17 s -> about 0.15-0.25 s (about 85-90%).
- Output risk: low if memoised per request (same function, same inputs, a licence does not change mid-GET). **Touches the effective-CIF/balance path -> `cif-balance-auditor` review mandatory**; compare list/detail JSON before/after.

### 3. Licence detail and `nested_items`: 289 queries / 339 ms (large), 771 queries / 786 ms (large); detail fetched twice by the UI
- Evidence: `GET /licenses/1775/`: 289 queries (229 repeated), SQL 156 ms, wall 339 ms, 101 KiB. Typical licence: 158 queries / 117 ms. `GET /licenses/1775/nested_items/`: 771 queries (733 repeated), 786 ms.
- Repeated SQL and location (detail): x56 SALE trade-line CIF sum at `backend/apps/license/serializers/license.py:382`, x56 SALE trade-line qty sum at `:417`, x56 `obj.utilization_plans.all()` at `:451`: per import item (56 items) with no prefetch/annotation. nested_items: `serializers/license.py:244/251/454` and `balance_calculator.py:2027` each x56-59 (the "batched" quantity helper is evidently invoked once per item).
- Frontend multiplier: the overview page calls `GET licenses/{id}/` under two different React-Query keys, `["license-balance-customs-ledger", id]` (`frontend/src/pages/license-overview/LicenseOverviewPage.tsx:77`, shared with `CustomsLedgerSection.tsx:22`) and `["license-sion-norm", id]` (`useLicenseSionNorm.ts:44`, used only for `export_license`). Two identical retrieves = 2 x 289 queries on the large licence.
- Proposed fix: replace per-item aggregates by one grouped query / `Subquery` annotation on the import-item queryset, `prefetch_related('utilization_plans')`; unify the SION-norm hook onto the existing key (select `export_license` from the shared query with `select`).
- Expected gain: detail 289 -> about 30 queries, 339 ms -> about 80-100 ms; page makes one retrieve instead of two.
- Output risk: low (same aggregates). The SALE-without-BOE sums feed displayed balances, so route through `cif-balance-auditor` and diff JSON.

### 4. Balance PDF / Excel export: 701 queries / 642 ms (PDF), 423 queries / 534 ms (Excel) on the large licence
- Evidence: PDF large 701 q (654 repeated), 4.7 MiB; Excel large 423 q (372 repeated); typical licence 253 q / 338 ms and 180 q / 289 ms. Both are synchronous in the request thread.
- Location: PDF `backend/apps/license/services/exporters/license_balance_pdf.py:784,787,828` (x56 each: `item.items.exists()`, `item.items.all()`, per-item lookups inside `for item in license_obj.import_license.all()`); Excel `.../license_balance_excel.py:837,842,860` in `_write_reconciliation_sheet` (x56 each, 82 ms + 66 ms + 22 ms). Both also rebuild the ledger (`balance-ledger` itself is 85 q).
- Proposed fix: prefetch `items`, `hs_code` etc. once; avoid `.exists()` + `.all()` double query; share one ledger build between sheets. For bulk Excel (`bulk-balance-excel`, POST, not measured) move to the existing Celery job path.
- Expected gain: about -85% queries, 640 ms -> about 250 ms (the rest is reportlab/openpyxl CPU).
- Output risk: none expected (layout-only reads); diff generated files' cell values.

### 5. Item report: 61 MB JSON, 219 MiB peak, 1.0 s, uncached
- Evidence: 18 queries, SQL 219 ms, wall 1,000 ms, **payload 61,027 KiB**, peak 219 MiB Python memory; warm 1,065 ms. Item pivot: 15.9 MB / 70 MiB; planned-report: 10.2 MB / 37 MiB.
- Slowest query (106.9 ms, `item_report.py:301`): EXPLAIN ANALYZE = Sort (20.5 ms) over Hash Left Joins returning 3,104 rows x ~3.5 kB width, 6,190 buffer hits; the cost is the width of the row set and Python-side shaping, not the plan.
- No `GZipMiddleware` in `lmanagement/settings.py` `MIDDLEWARE` (nginx compression was not inspected, `backend/deploy` out of scope).
- Proposed fix: paginate or require filters by default; send only needed columns; enable gzip at nginx or Django; cache with the existing invalidation patterns.
- Expected gain: payload -85-90% with gzip alone (JSON compresses well); peak memory proportional to row count.
- Output risk: gzip none; pagination/column trimming **changes the API shape** (frontend contract, Excel/PDF export consumers).

### 6. Licence list N+1: 118 queries per page of 25 (4.7 per row); page_size=100 gives 490 queries, 890 KiB
- Evidence: default page 118 q (99 repeated), 105 ms, 43 KiB; `page_size=100` 490 q, 208 ms, 890 KiB; search variant 134 q.
- Location (page_size=100, x100 each): `backend/apps/license/models/core.py:290` (`get_norm_class` iterates `export_license.all()` and reads `e.norm_class`, FK not `select_related`), `core.py:846` (`latest_transfer`: `.order_by().exists()` then `.first()` = 3 statements per licence), `backend/apps/license/serializers/license.py:915` (per-licence `available_value_bulk_map`).
- Proposed fix: `Prefetch('export_license', queryset=...select_related('norm_class'))`, `prefetch_related` of transfers ordered once, compute `latest_transfer` from the prefetched list, build the bulk map once per page.
- Expected gain: 118 -> about 25 queries per page; 105 ms -> about 50 ms.
- Output risk: none (read-path prefetch).

### 7. Item-pivot cold path: 202 queries / 856 ms (E5: 71 q / 279 ms)
- Evidence: x169 `transfers ORDER BY transfer_date DESC` at `models/core.py:846` via `backend/apps/license/services/item_pivot_service.py:572` (`latest_transfer`), x3 `__str__` lookups `core.py:2061-2062`. Slowest single query 35.5 ms (`bill_of_entry_rowdetails` Nested Loop with a correlated SubPlan filter on `invoice_no = 'OTH'`, 775 rows, 4,844 buffer hits). 5-minute cache hides it on repeat (32 ms warm) but every invalidation (any licence/BOE/allotment save) restarts at 856 ms.
- Proposed fix: same prefetch as 6 for transfers; replace the correlated `SubPlan` filter with a join/`Exists` and index review.
- Expected gain: 856 -> about 400 ms cold.
- Output risk: none for prefetch; the filter rewrite must keep the HIDE_BOE semantics (business rule), test on this dataset.

### 8. Reconciliation summary / missing-invoice: 153 and 146 queries (small absolute cost)
- Evidence: summary 153 q (140 repeated), 57 ms; missing-invoice 146 q, 46 ms, 8.5 KiB. x71 each at `backend/apps/bill_of_entry/models.py:293` (`get_total_fc`) and `:300` (`get_total_quantity`), `aggregate()` per BOE on `item_details_cached`.
- Proposed fix: one grouped aggregate (`annotate(Sum)`) in `reconciliation/services/queries.py`.
- Expected gain: about 150 -> about 10 queries; 57 -> about 15 ms. The counts grow linearly with the number of unmatched BOEs (production likely larger).
- Output risk: low; Decimal quantisation must match (`get_total_fc` quantizes to `DEC_0`).

### 9. Caching: only two of the measured views cache; balance is not cached; materialized views are unused
- Redis (`django_redis`, db 1, `settings.py:389`) is used by: dashboard (`view:dashboard:v2:<roles>`, 300 s), item-pivot (`view:item_pivot:...`, 300 s) and DRF throttling. `core/cached_views.py` and the `cache_view`/`cache_query`/`cache_method` decorators in `core/cache_utils.py` are **not used by any view or model** (grep of `apps/`, excluding tests). Licence list/detail, BOE, allotment, reconciliation, item-report, active/expiring licences, planned-report are uncached.
- Invalidation: `core/cache_signals.py` (post_save/post_delete on licence, import/export items, BOE, RowDetails, allotment, allotment items, company, item, HSN, purchase status) calls `delete_pattern` for `view:license*`, `view:dashboard*`, `view:item_report*`, `view:active_licenses*`, `view:expiring_licenses*`, `license_balance:<id>`. For balances specifically: the `license_balance:<id>` and `LicenseDetailsModel:*:<id>:*` keys it deletes are **never written** (no producer found), i.e. balance caching does not exist today; the invalidation is dead code that likely costs one Redis `delete_pattern` (key scan) per pattern on every save (not measured). There is **no invalidation receiver for trade/trade-line models**, so any future cache over trade-dependent balances would go stale.
- Materialized views: `license_balance_mv` (2,185 rows, 496 kB), `item_balance_mv` (26,818 rows, 5.5 MB), `dashboard_stats_mv` (1 row). Nothing in `apps/` reads them (only `core/materialized_views.py`, `tasks_materialized_views.py`, `signals_materialized_views.py`, a management command). Auto-refresh is **off** (`signals_materialized_views.py:25` `AUTO_REFRESH_ENABLED = False`) and there is **no Celery beat entry** for the refresh tasks (`lmanagement/celery.py` beat list). Locally all three show `last_refreshed` 2026-11-15 10:12 UTC; with auto-refresh off and no beat entry they only change on a manual refresh, and no measured endpoint depends on them. Refresh cost (not executed): `EXPLAIN (ANALYZE)` of the defining SELECTs (pure SELECT) took 37.6 ms (`license_balance_mv`), 34.5 ms (`item_balance_mv`), 2.1 ms (`dashboard_stats_mv`), so `REFRESH ... CONCURRENTLY` is cheap on this dataset (add unique-index maintenance and write amplification; expected well under 1 s). Production size is unknown.
- Proposed fix: decide per view: cache the heavy reports with TTL + the existing signal patterns and add trade receivers; either wire the MVs into the balance reads (with a refresh schedule and an explicit staleness contract) or delete them; remove the dead `license_balance:*` invalidation or add its producer.
- Expected gain: repeat hits of reports go from 0.2-5.8 s to about 1 ms.
- Output risk: **caching balances changes freshness semantics** (stale CIF visible to users) and is a business-rule decision; MV-backed reads would also change numbers whenever the MV lags. Needs product sign-off and `cif-balance-auditor`.

### 10. Transport and frontend: no response compression, per-request audit thread, bundle and fetch patterns
- `ActivityLogMiddleware` (`backend/apps/core/middleware.py:138-153`, `_start_log_thread:99`): every authenticated `/api/` request, including GETs, starts a daemon thread that opens its own DB connection and INSERTs into `core_activitylog` (334,352 rows already). **Not measured** (needs writes, excluded here); expected effect: extra connection churn on the DB and one write per request under load. Fix options: batch writes via queue/Celery, skip safe GET polling endpoints, or drop connection-per-thread.
- No `GZipMiddleware` (see 5).
- Frontend `dist/` (measured after the CI-equivalent gate's `npm run build` PASSED, `/tmp/lm-baseline/gate-all.log`): total JS 2,070 KB raw / 622 KB gzip over 147 files; CSS 271 KB raw / 39 KB gzip over 3 files. **Initial load** (`index.html` entry + modulepreloads): `index` 66 KB / 20 KB gz, `app-shell` 346 KB / 113 KB gz, `vendor-react` 175 KB / 55 KB gz, `index.css` 243 KB / 35 KB gz = **830 KB raw / about 223 KB gzip**. Largest lazy chunks (raw/gzip KB): `navigationUtils` 158/38, `MasterList` 128/33, `LicensePlanningWorkspace` 92/24, `useStateManager` (react-select) 81/28, `ItemPivotReport` 79/19, `MasterForm` 79/22, `ItemsTab` 63/16, `AllotmentAction` 57/14, `TradeForm` 53/11, `LicenseLedger` 51/13. `exceljs`/`jspdf` are not in the entry chunk (no `exceljs`/`jspdf` string in `app-shell`). `index.html` loads Google Fonts through a render-blocking `<link rel="stylesheet">` to `fonts.googleapis.com`.
- Data fetching: 92 source files call axios directly vs 14 using `useQuery` (`frontend/src/api/queryClient.ts`: `staleTime` 30 s, `retry` 1), so most screens get no request dedupe or caching. Static duplicates found: (a) `licenses/{id}/` x2 on the licence overview page (bottleneck 3); (b) `reconciliation/summary/` fetched independently in `pages/ReconciliationIssues.tsx:135` and `pages/ReconciliationPanel.tsx:56` (separate pages, but no shared cache, 153 queries each); (c) `pages/TradeForm.tsx:280,302` fetches `masters/companies/{id}/` for from/to company (different ids, but also refetched on every change, no cache); (d) `Dashboard.tsx:231` single fetch (fine, server-cached). Polling: `ReplanStatus.tsx:28` `refetchInterval`, `LedgerUpload.tsx:164` `setInterval`. Not profiled in a browser.
- Expected gain: gzip about -70-80% bytes on JSON; font preconnect/self-host removes a render-blocking third-party request; query-key unification removes one 100 KB retrieve.
- Output risk: none for compression/fonts/key unification.

## 4. Quick-win order (lowest risk first)

1. Gzip for API JSON (bottlenecks 5/10), no business risk.
2. Prefetch/select_related fixes in licence list, item-pivot, PDF/Excel exporters, `active_licenses_report.py:225` (6, 7, 4, 1a).
3. Single-source `licenses/{id}/` on the overview page (3).
4. Per-request memoised licence balance in BOE/trade serializers (2) and bulk balance in reports (1b): **balance-path, needs `cif-balance-auditor`**.
5. Cache policy + trade invalidation + MV decision (9): needs a product decision.

## 5. Not measured

- Trade/invoice list and detail, trade PDF/bill-of-supply (no trades in local DB; endpoints responded, counts empty).
- `reports/license-purchase-profit` (400 without valid params), bulk Excel (POST), planning/auto-plan (POST), ledger upload (POST).
- Redis hit-rate/latency, nginx/gunicorn behaviour, concurrent load, production-size data, browser render/profiler timings.
- ActivityLog middleware overhead and the real `REFRESH MATERIALIZED VIEW` time (both need writes).
- Ledger exports: only licence `balance-excel` / `balance-pdf` were measured; `license-ledger/export/` was not exercised.

## Appendix A. Re-run for after-measurements

Scripts live outside the repo in `/tmp/lm-perf/` (copies below). Run from `backend/`:

```
cd backend
PYTHONPATH=$PWD TESTING=true DB_HOST=localhost DJANGO_SETTINGS_MODULE=lmanagement.settings \
  .venv/bin/python /tmp/lm-perf/measure.py /tmp/lm-perf/results-after.json     # whole table (~4 min)
ONLY="BOE list" PYTHONPATH=$PWD TESTING=true .venv/bin/python /tmp/lm-perf/measure.py out.json   # subset by name substring
PYTHONPATH=$PWD TESTING=true .venv/bin/python /tmp/lm-perf/trace.py "/api/bill-of-entries/"   # call sites + EXPLAIN ANALYZE
PYTHONPATH=$PWD .venv/bin/python /tmp/lm-perf/mv.py                            # MV defining-query cost
```

Compare `nq`, `dup_pattern`, `wall_ms`, `peak_mb`, `kb` per endpoint. Representative ids are re-derived each run (largest licence by BOE rows, median licence, etc.), so they stay stable while data is unchanged. Re-run on the same machine with Postgres idle (the first cold run can include connection setup; the median absorbs it).

### A.1 `/tmp/lm-perf/measure.py`

```python
"""Read-only API perf baseline for License Manager.
Run:  cd backend && PYTHONPATH=$PWD TESTING=true DB_HOST=localhost \
        DJANGO_SETTINGS_MODULE=lmanagement.settings .venv/bin/python /tmp/lm-perf/measure.py [out.json]
Safety: local DB only (asserts host), GET only, APIClient.force_authenticate (no session/last_login write),
TESTING=true disables ActivityLog writer thread, Redis replaced by in-process LocMem cache (no Redis traffic).
"""
import os, sys, re, json, time, statistics, tracemalloc, collections
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lmanagement.settings")
os.environ["DB_HOST"] = "localhost"; os.environ["TESTING"] = "true"
import django; django.setup()
from django.conf import settings
from django.db import connection
from django.db.models import Count
from django.test.utils import CaptureQueriesContext, override_settings
from django.core.cache import cache
assert settings.DATABASES["default"]["HOST"] in ("localhost", "127.0.0.1")
assert settings.DATABASES["default"]["NAME"] == "lmanagement"
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
from apps.license.models import LicenseDetailsModel
from apps.bill_of_entry.models import RowDetails
from apps.allotment.models import AllotmentItems

OUT = sys.argv[1] if len(sys.argv) > 1 else "/tmp/lm-perf/results.json"
RUNS = 3
LOC = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "lmperf"}}
_lit = re.compile(r"'(?:[^']|'')*'|\b\d+(?:\.\d+)?\b")
_in = re.compile(r"IN \([^)]*\)")
def norm(sql):
    return _in.sub("IN (?)", _lit.sub("?", sql))

def pick_ids():
    big = RowDetails.objects.values("sr_number__license_id").annotate(n=Count("id")).order_by("-n")[0]
    counts = list(RowDetails.objects.values("sr_number__license_id").annotate(n=Count("id")).order_by("n"))
    typ = counts[len(counts) // 2]
    out = {"big_lic": big["sr_number__license_id"], "big_lic_boe_rows": big["n"],
           "typ_lic": typ["sr_number__license_id"], "typ_lic_boe_rows": typ["n"]}
    a = AllotmentItems.objects.filter(item__license_id=out["big_lic"]).values_list("allotment_id", flat=True).first()
    out["allotment"] = a or AllotmentItems.objects.values_list("allotment_id", flat=True).first()
    b = RowDetails.objects.filter(sr_number__license_id=out["big_lic"], bill_of_entry__isnull=False).values_list("bill_of_entry_id", flat=True).first()
    out["boe"] = b
    mx = RowDetails.objects.filter(bill_of_entry__isnull=False).values("bill_of_entry_id").annotate(n=Count("id")).order_by("-n")[0]
    out["boe_rows_max"] = mx["n"]; out["boe_big"] = mx["bill_of_entry_id"]
    out["rowdetails_null_boe"] = RowDetails.objects.filter(bill_of_entry__isnull=True).count()
    from apps.trade.models import LicenseTrade as T
    out["trade"] = T.objects.order_by("-id").values_list("id", flat=True).first()
    out["trade_count"] = T.objects.count()
    from apps.license.models import LicenseExportItemModel as E
    top = E.objects.exclude(norm_class__isnull=True).values("norm_class__norm_class").annotate(n=Count("id")).order_by("-n").first()
    out["norm"] = top["norm_class__norm_class"] if top else None
    return out

def run_once(client, url, mem=False):
    connection.queries_log.clear()
    if mem: tracemalloc.start()
    with CaptureQueriesContext(connection) as ctx:
        t0 = time.perf_counter()
        r = client.get(url, SERVER_NAME="localhost")
        body = b"".join(r.streaming_content) if getattr(r, "streaming", False) else r.content
        wall = time.perf_counter() - t0
    peak = None
    if mem:
        peak = tracemalloc.get_traced_memory()[1]; tracemalloc.stop()
    qs = ctx.captured_queries
    ex = collections.Counter(q["sql"] for q in qs)
    pt = collections.Counter(norm(q["sql"]) for q in qs)
    pt_time = collections.defaultdict(float)
    for q in qs: pt_time[norm(q["sql"])] += float(q["time"])
    return dict(status=r.status_code, wall=wall, nq=len(qs), sql_time=sum(float(q["time"]) for q in qs),
                dup_exact=sum(c - 1 for c in ex.values() if c > 1), dup_pattern=sum(c - 1 for c in pt.values() if c > 1),
                bytes=len(body), peak=peak, ctype=r.headers.get("Content-Type", ""),
                top_patterns=[(c, round(pt_time[p], 4), p[:700]) for p, c in pt.most_common(3) if c > 1],
                slowest=sorted(((float(q["time"]), q["sql"]) for q in qs), reverse=True)[:1])

def measure(client, name, url):
    res = []
    with override_settings(CACHES=LOC):
        for i in range(RUNS):
            cache.clear(); res.append(run_once(client, url))
        cache.clear(); run_once(client, url)            # prime
        warm = run_once(client, url)                      # warm (cache hit if view caches)
        cache.clear(); mem = run_once(client, url, mem=True)
    med = lambda k: statistics.median(r[k] for r in res)
    worst = max(res, key=lambda r: r["wall"])
    return dict(name=name, url=url, status=res[0]["status"], nq=med("nq"), dup_pattern=med("dup_pattern"),
                dup_exact=med("dup_exact"), sql_ms=round(med("sql_time") * 1000, 1), wall_ms=round(med("wall") * 1000, 1),
                walls_ms=[round(r["wall"] * 1000, 1) for r in res], warm_ms=round(warm["wall"] * 1000, 1),
                warm_nq=warm["nq"], peak_mb=round(mem["peak"] / 1e6, 1), kb=round(res[0]["bytes"] / 1024, 1),
                ctype=res[0]["ctype"][:40], top_patterns=worst["top_patterns"], slowest=worst["slowest"])

def main():
    U = get_user_model()
    user = U.objects.filter(is_superuser=True, is_active=True).order_by("id").first()
    if not user: print("NO SUPERUSER"); return
    client = APIClient(); client.force_authenticate(user=user)
    ids = pick_ids(); print(ids)
    sample_no = LicenseDetailsModel.objects.filter(pk=ids["typ_lic"]).values_list("license_number", flat=True).first() or "0"
    B, T_ = ids["big_lic"], ids["typ_lic"]
    eps = [
     ("license list (default page)", "/api/licenses/"),
     ("license list (page_size=100)", "/api/licenses/?page_size=100"),
     ("license list (search=5-char prefix)", f"/api/licenses/?search={sample_no[:5]}"),
     ("license detail (typical)", f"/api/licenses/{T_}/"),
     ("license detail (large)", f"/api/licenses/{B}/"),
     ("license nested-items (large)", f"/api/licenses/{B}/nested_items/"),
     ("license overview-summary (large)", f"/api/licenses/{B}/overview-summary/"),
     ("license overview-boes (large)", f"/api/licenses/{B}/overview-boes/"),
     ("license overview-allotments (large)", f"/api/licenses/{B}/overview-allotments/"),
     ("license overview-items (large)", f"/api/licenses/{B}/overview-items/"),
     ("license overview-invoice-ledger (large)", f"/api/licenses/{B}/overview-invoice-ledger/"),
     ("balance-ledger (typical)", f"/api/licenses/{T_}/balance-ledger/"),
     ("balance-ledger (large)", f"/api/licenses/{B}/balance-ledger/"),
     ("balance-excel (typical)", f"/api/licenses/{T_}/balance-excel/"),
     ("balance-excel (large)", f"/api/licenses/{B}/balance-excel/"),
     ("balance-pdf (typical)", f"/api/licenses/{T_}/balance-pdf/"),
     ("balance-pdf (large)", f"/api/licenses/{B}/balance-pdf/"),
     ("allotment list", "/api/allotments/"),
     ("allotment detail", f"/api/allotments/{ids['allotment']}/"),
     ("BOE list", "/api/bill-of-entries/"),
     ("BOE detail (large licence)", f"/api/bill-of-entries/{ids['boe']}/"),
     ("BOE detail (most rows)", f"/api/bill-of-entries/{ids['boe_big']}/"),
     ("trade list", "/api/trades/"),
     ("trade detail", f"/api/trades/{ids['trade']}/"),
     ("dashboard", "/api/dashboard/"),
     ("reconciliation summary", "/api/reconciliation/summary/"),
     ("reconciliation missing-boe", "/api/reconciliation/missing-boe/"),
     ("reconciliation missing-invoice", "/api/reconciliation/missing-invoice/"),
     ("reconciliation cif-comparison", "/api/reconciliation/cif-comparison/"),
     ("reconciliation qty-comparison", "/api/reconciliation/qty-comparison/"),
     ("reconciliation duplicate-debits", "/api/reconciliation/duplicate-debits/"),
     ("report item-pivot", "/api/reports/item-pivot/"),
     ("report item-report", "/api/reports/item-report/"),
     ("report inventory-balance", "/api/reports/inventory-balance/"),
     ("report inventory-balance (sion_norm=most common)", f"/api/reports/inventory-balance/?sion_norm={ids['norm']}"),
     ("report item-pivot (sion_norm=most common)", f"/api/reports/item-pivot/?sion_norm={ids['norm']}"),
     ("report active-licenses", "/api/reports/active-licenses/"),
     ("report expiring-licenses", "/api/reports/expiring-licenses/"),
     ("report planned-report", "/api/reports/planned-report/"),
     ("report license-purchase-profit", "/api/reports/license-purchase-profit/"),
     ("item-pivot available-norms", "/api/item-pivot/available-norms/"),
    ]
    only = os.environ.get("ONLY")
    results = []
    for name, url in eps:
        if only and only not in name: continue
        try:
            r = measure(client, name, url)
        except Exception as e:
            r = dict(name=name, url=url, error=f"{type(e).__name__}: {str(e)[:200]}")
        results.append(r)
        print(json.dumps({k: v for k, v in r.items() if k not in ("top_patterns", "slowest")}), flush=True)
        json.dump(dict(ids=ids, results=results), open(OUT, "w"), indent=1, default=str)

main()
```

### A.2 `/tmp/lm-perf/trace.py`

```python
"""Locate N+1 call sites + EXPLAIN ANALYZE the slowest pure SELECT. Read-only.
Run: cd backend && PYTHONPATH=$PWD TESTING=true DB_HOST=localhost DJANGO_SETTINGS_MODULE=lmanagement.settings \
     .venv/bin/python /tmp/lm-perf/trace.py "<url>" [more urls...]"""
import os, sys, re, traceback, collections, time
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "lmanagement.settings")
os.environ["DB_HOST"] = "localhost"; os.environ["TESTING"] = "true"
import django; django.setup()
from django.conf import settings
assert settings.DATABASES["default"]["HOST"] in ("localhost", "127.0.0.1") and settings.DATABASES["default"]["NAME"] == "lmanagement"
from django.db import connection
from django.test.utils import override_settings
from rest_framework.test import APIClient
from django.contrib.auth import get_user_model
APPS = os.path.join(os.getcwd(), "apps") + os.sep
_lit = re.compile(r"'(?:[^']|'')*'|\b\d+(?:\.\d+)?\b"); _in = re.compile(r"IN \([^)]*\)")
norm = lambda s: _in.sub("IN (?)", _lit.sub("?", s))
LOC = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "lmtrace"}}
user = get_user_model().objects.filter(is_superuser=True, is_active=True).order_by("id").first()
c = APIClient(); c.force_authenticate(user=user)
for url in sys.argv[1:]:
    sites = collections.defaultdict(lambda: [0, 0.0, None]); allq = []
    def wrap(execute, sql, params, many, context):
        t = time.perf_counter(); r = execute(sql, params, many, context); dt = time.perf_counter() - t
        fr = [f for f in traceback.extract_stack() if f.filename.startswith(APPS)]
        loc = f"{fr[-1].filename[len(os.getcwd())+1:]}:{fr[-1].lineno}" if fr else "?"
        k = (loc, norm(sql)[:160]); s = sites[k]; s[0] += 1; s[1] += dt; s[2] = s[2] or [f"{f.filename[len(os.getcwd())+1:]}:{f.lineno} {f.name}" for f in fr[-6:]]
        allq.append((dt, sql, params)); return r
    with override_settings(CACHES=LOC), connection.execute_wrapper(wrap):
        resp = c.get(url, SERVER_NAME="localhost")
    print(f"\n=== {url}  status={resp.status_code} queries={len(allq)}")
    for (loc, pat), (n, t, _) in sorted(sites.items(), key=lambda kv: -kv[1][0])[:4]:
        print(f"  x{n:<5} {t*1000:7.1f}ms  {loc}\n     {pat}"); print("     chain: " + " <- ".join(reversed(_)))
    dt, sql, params = max(allq, key=lambda x: x[0])
    print(f"  slowest single query {dt*1000:.1f}ms: {sql[:300]}")
    if sql.lstrip().upper().startswith(("SELECT", "WITH")):
        with connection.cursor() as cur:  # pure SELECT only (guarded above)
            cur.execute("EXPLAIN (ANALYZE, BUFFERS) " + sql, params)
            print("  EXPLAIN ANALYZE:"); [print("   ", r[0]) for r in cur.fetchall()[:14]]
```

### A.3 `/tmp/lm-perf/mv.py`

```python
"""EXPLAIN ANALYZE (SELECT only) of each materialized view's defining query = proxy for REFRESH cost. No refresh executed."""
import os; os.environ["TESTING"]="true"; os.environ["DB_HOST"]="localhost"; os.environ["DJANGO_SETTINGS_MODULE"]="lmanagement.settings"
import django; django.setup()
from django.db import connection
with connection.cursor() as c:
    c.execute("select count(*) from pg_settings where false")
    for mv in ("license_balance_mv","item_balance_mv","dashboard_stats_mv"):
        c.execute("select pg_get_viewdef(%s::regclass), pg_total_relation_size(%s::regclass)", [mv, mv]); d, size = c.fetchone()
        c.execute(f"select count(*) from {mv}"); n = c.fetchone()[0]
        c.execute(f"select max(last_refreshed) from {mv}"); lr = c.fetchone()[0]
        sql = d.rstrip().rstrip(";"); assert sql.lstrip().upper().startswith("SELECT")
        c.execute("EXPLAIN (ANALYZE) " + sql); rows = [r[0] for r in c.fetchall()]
        print(mv, "rows", n, "size_kB", size//1024, "last_refreshed", lr, [r for r in rows if "Execution Time" in r or "Planning Time" in r])
```
