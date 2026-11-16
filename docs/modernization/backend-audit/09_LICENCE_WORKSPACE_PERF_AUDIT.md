# 09 - Licence workspace backend performance audit

Status: MEASURE-ONLY. No production code, migration or DB change was made.
Branch feature/v5. Date 2026-11-16. Prior work not repeated: licence list 268 to 21,
BOE list partial fix (PERFORMANCE_REPORT.md), commit 968e4bfc, `test_license_list_query_count.py`.

## Method
- Tests: `backend/apps/license/tests/test_licence_workspace_query_budget.py` (14 characterization tests, all PASS).
- Fixture: one licence with `n` import items, each with 1 BOE debit row, 1 allotment item, and 2 trades
  (purchase + sale, 1 line + 1 payment each). Measured at n=1 and n=6 with `CaptureQueriesContext`,
  superuser, cache cleared. Postgres test DB only (pytest-django throwaway DB, run with a unique
  `TEST_DB_NAME=test_lmanagement_wsperf` because the default `test_lmanagement` was in use by another runner).
- Counts are SQL statements, not time. Wall-clock on realistic data volume needs a populated DB: NOT MEASURED.
- Not covered: `merged-documents` (file merge, IO bound), sion-norm card (served by retrieve's `export_license__norm_class`),
  `fetchAllPages`-style use (no unpaginated call found on this page; the page uses licence-scoped non-paginated actions).

## Measured query counts

| Endpoint | n=1 | n=6 | Scaling |
|---|---|---|---|
| GET licenses/:id/ (retrieve; also the only source of documents) | 100 | 115 | ~3/row + 100 fixed |
| GET licenses/:id/overview-summary/ | 47 | 47 | flat, high fixed cost |
| GET licenses/:id/overview-items/ | 3 | 3 | flat |
| GET licenses/:id/overview-items/?include_canonical=1 | 24 | 39 | N+1, ~3/item |
| GET licenses/:id/overview-boes/ | 4 | 4 | flat |
| GET licenses/:id/overview-allotments/ | 5 | 5 | flat |
| GET licenses/:id/overview-invoice-ledger/ | 9 | 29 | N+1, 4/trade-pair (2 per trade) |
| GET licenses/:id/balance-ledger/ | 83 | 137 | N+1, ~11/row |
| GET licenses/:id/plan-utilization/ | 32 | 37 | ~1/row + 32 fixed |
| GET license-actions/:id/ownership-data/ | 2 | 2 | flat |
| GET bill-of-entries/?is_invoice=all&page_size=50 (n BOEs in table) | 19 | 48 | N+1, ~6/BOE |
| GET bill-of-entries/ (default is_invoice filter) | 19 | 48 | same |
| GET allotments/?is_boe=all&type=AT&is_allotted=all | 4 | 4 | flat |
| GET allotments/ (default filters) | 4 | 4 | flat |

Overview tab first paint at n=1 (retrieve + summary + items + boes + allotments + invoices) is about 168 queries; with the
Ledger tab (balance-ledger) about 250. None of these endpoints use `core/cache_signals.py` caching.

## Per-endpoint findings

### retrieve  (`apps/license/api/views/license.py:346-486`, queryset `:570`)
- 100 queries at 1 row. Breakdown at n=6 (115): trade_licensetradeline 30, licenseitemplan 14, rowdetails 11,
  licenseexportitemmodel 10, invoiceboeallocation 7, reconciliationlog 7, allotmentitems 6.
- Sources: `plan_utilization_rows` (`services/plan_utilization.py:50`, per-plan-group `plan_status_for`),
  `plan_status_for_items`, `aggregate_license_usage` (`services/planning_usage_reconciliation.py:81`),
  `reconcile_license_plans` (`:221`, called after `aggregate_license_usage` which loads the same data),
  `LicensePlanPresentationService.get_license_plan`, `get_balance_cif` property, and `LicenseExportItemModel.values_list`
  re-queried at line ~437 even though `export_license` is prefetched.
- The Overview page uses this endpoint only for `license_documents` (see `LicenseOverviewPage.tsx:75-80`, comment says
  "no documents-only endpoint") and header fields: ~100 queries to read 0-3 document rows.
- No pagination/filter concerns (single object).

### overview-summary (`api/views/license_overview.py:34`, `services/license_overview_summary.py:get_overview_counts`)
- Flat, but 47 queries: the docstring claim "O(1)" is true, the constant is not small. Most of them (table mix: rowdetails 11, tradeline 9, exportitems 7, BOE 7; exact split not isolated) come from
  `balance_snapshot.get_snapshot` (`services/balance_snapshot.py:288`) -> `get_snapshot_bulk` (`:63`) for a single licence
 .
- Same balance is computed again by retrieve (`get_balance_cif`), plan-utilization and balance-ledger.

### overview-items (`services/license_overview_items.py:34`)
- Legacy path: flat (3). `include_canonical=1`: `project_effective_item_cif` (`services/effective_cif_mode.py:61`) is called per
  item and issues ~3 queries each (licence balance + individual-item balance re-derived per row; `license_balance_cif` is the
  same for all rows).  Frontend (`useLicenseOverviewItems.ts`) passes the flag, so this is the live path.

### overview-boes / overview-allotments
- Flat and already batched (grouped aggregate + one header query). No change needed. `RowDetails.sr_number__license` filter
  join is covered by existing FK indexes; not EXPLAINed (no DB access allowed).

### overview-invoice-ledger (`services/license_overview_invoices.py:build_invoice_ledger`, `_status_label`)
- `prefetch_related("payments")` is defeated: `LicenseTrade.paid_or_received` (`apps/trade/models.py:351`) calls
  `self.payments.aggregate(Sum)` (always a query), and `_status_label` reads both `due_amount` and `paid_or_received`
  (due_amount itself reads `paid_or_received`) = 2 queries per trade. `lines` prefetch is not used by the row builder.
- Fix: sum `t.payments.all()` in Python when prefetched, or annotate `Sum(payments__amount)`; must keep `q2` rounding.

### balance-ledger (`api/views/license_balance_ledger.py:63`, `services/license_balance_ledger_builder.py:1597 build`)
- 83 at 1 row, +11/row. n=6 breakdown: invoiceboeallocation 30, tradeline 29, boeallotmentallocation 18,
  reconciliationlog 17, trade 9, importitems 8, itemnamemodel 7.
- Builders each re-query the same licence data: `build_financial_ledger` (`:194`), `build_customs_ledger` (`:726`),
  `build_invoice_boe_relationships` (`:1001`), `build_boe_allotment_relationships` (`:1168`, per BOE debit row),
  `build_timeline` (`:1293`), `build_warnings` (`:1527`), plus `CanonicalLedgerService.build_canonical_ledger_dataset`
  (already threaded as `canonical_data`). `license_obj.import_license.all()` iterated twice in `build()` (no prefetch).
- CIF/balance math lives here: any change needs cif-balance-auditor.

### plan-utilization (`api/views/license_overview.py:78`)
- 32 fixed + ~1/row. Duplicates `plan_utilization_rows` work already done in retrieve (same page load for Planning tab).

### ownership-data (`apps/license/views_actions.py:394`)
- 2 queries, well built. Note: no object-level company scoping (`get_object_or_404` on all licences with `LicensePermission`) -
  security note, out of perf scope.

### BOE list (`apps/bill_of_entry/api/views.py:135`, serializer `apps/bill_of_entry/api/serializers.py:40-62, 232-245`)
- 19 at 1 BOE, +~6 per BOE. Queryset prefetches are correct and totals are seeded from the prefetch. Remaining per-row work:
  `get_authoritative_available_cif` (`serializers.py:50`) -> `effective_source_row_cif_available`
  (`services/effective_cif_mode.py:114`) -> `LicenseImportItemsModel.available_value_calculated` (`models/items.py:215`),
  which runs SUMs over `RowDetails`, `BOEAllotmentAllocation` and trade lines per BOE row (two RowDetails SUMs +
  two allocation sums per BOE observed).
- Pagination: standard page_size count query (1 extra). Search includes `item_details__sr_number__license__license_number`
  (3-table join + DISTINCT risk on large data; not measured). Indexes on BOE: company+date, port+date, date exist
  (`bill_of_entry/models.py:240`); `invoice_no` (default `is_invoice` filter `invoice_no IS NULL OR = ''`) has no index in the model: unverified, needs EXPLAIN.
- CIF math: `available_value_calculated` is balance logic; batching needs cif-balance-auditor.

### Allotment list (`apps/allotment/api/views.py:171-298`)
- Flat at 4 queries: annotations (`_list_*`) plus two prefetches. Good. One thing to watch: the Sum/Count annotations
  join `allotment_details` and `allotment_details__item__license` (fan-out guarded by `distinct=True` for counts; the Sum
  columns are on a single join so not inflated here, but adding a second multi-row join would inflate them).
  Default filters `is_boe=False, type='AT', is_allotted=True` hit existing indexed booleans (not EXPLAINed).

## Duplicate work across one page load
| Computation | Endpoints repeating it |
|---|---|
| Licence balance / `get_snapshot` | overview-summary, retrieve (`get_balance_cif` x2), plan-utilization (`get_balance_cif`), balance-ledger (canonical + financial) |
| `plan_utilization_rows` | retrieve, plan-utilization (and Balance Excel export) |
| `aggregate_license_usage` + `reconcile_license_plans` | retrieve (sequential, overlapping data) |
| `self.get_object()` licence queryset with 7 select_related | every action (1-3 queries each, fine) |
| Trade/BOE rows for the licence | invoice-ledger, balance-ledger (x3 builders), summary snapshot, retrieve |

## Existing services/selectors to reuse
- `services/balance_snapshot.py:get_snapshot_bulk` (batched balance) - pass pre-fetched data instead of per-call `get_snapshot`.
- `services/condition_pool.py:compute_condition_pools` (documented for bulk contexts, `models/items.py:234`).
- `LicenseBalanceCalculator.calculate_financial_balance_for_licenses` (bulk live balance).
- `services/canonical_ledger_service.py:CanonicalLedgerService.build_canonical_ledger_dataset` (already threaded in ledger builder).
- `services/license_balance_ledger_builder.py:boe_invoice_allocation_map / boe_external_invoice_map` (already batch maps).
- `annotate_and_exclude_hidden` (`bill_of_entry/models`), grouped-aggregate pattern used in `license_overview_boes.py`.

## Ranked fixes (none implemented)

| # | Fix | Impact | Risk | Files | CIF math / auditor |
|---|---|---|---|---|---|
| 1 | Add a documents-only endpoint or slim retrieve variant (`?fields=documents`/lightweight action) and point `LicenseOverviewPage.tsx:77` at it. Avoids ~100 queries per page open | Very high (-100 q/page) | Low (additive endpoint; frontend change) | `api/views/license.py`, `useLicenseDetail.ts`, `LicenseOverviewPage.tsx` | No (adds API; flag API CONTRACT) |
| 2 | BOE list: compute per-row `authoritative_available_cif` in batch (bulk SUM annotate/maps per licence) instead of `available_value_calculated` per BOE | High (48 -> ~15 at 6 BOEs; page of 50 ~300 -> ~15) | Medium-high | `bill_of_entry/api/serializers.py`, `services/effective_cif_mode.py`, `models/items.py` | YES |
| 3 | Invoice ledger: sum prefetched payments in Python / annotate; remove 2 q/trade | Medium-high (29 -> ~9 at 6 trade-pairs; large licences with 100s of trades) | Low (keep `q2`) | `services/license_overview_invoices.py` (+ optionally `trade/models.py` property) | No (settlement amounts, not CIF) but verify rounding |
| 4 | `include_canonical` items: compute licence balance once and pass into `project_effective_item_cif` per row | Medium (3 q/item) | Medium | `services/license_overview_items.py`, `services/effective_cif_mode.py` | YES |
| 5 | Share one `balance_snapshot` / `plan_utilization_rows` / usage aggregate across retrieve, summary, plan-utilization via a per-request memo (request-scoped, not Redis) | Medium-high (removes duplicate ~40-60 q) | Medium (invalidation is per-request so safe) | `balance_snapshot.py`, `plan_utilization.py`, `planning_usage_reconciliation.py`, `api/views/license.py` | YES |
| 6 | balance-ledger builders: prefetch `import_license`, reuse `alloc_map` in `build_invoice_boe_relationships`, batch `build_boe_allotment_relationships` (per-BOE-row queries) | High on large licences (+11 q/row) | High (ledger/reconciliation) | `license_balance_ledger_builder.py` | YES |
| 7 | Drop duplicate `reconcile_license_plans` after `aggregate_license_usage` in retrieve (shared query) and `LicenseExportItemModel.values_list` re-query | Low-medium | Medium | `api/views/license.py:430-460` | YES |
| 8 | Verify indexes with EXPLAIN on real data: BOE `invoice_no` default filter, BOE search join, `AllotmentModel.is_boe/type/is_allotted` | Unknown | Low | `deploy-indexes.sh` | No |

## Tests
`cd backend && TEST_DB_NAME=test_lmanagement_wsperf python -m pytest apps/license/tests/test_licence_workspace_query_budget.py -q --no-cov`
Result: 14 passed. Caps are upper bounds at current measured counts (+small headroom); flat endpoints also assert
`large <= small + 1`. When a fix lands, tighten the caps in the same commit.
