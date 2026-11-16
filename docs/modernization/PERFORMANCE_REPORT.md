# Performance Report (measure-only, no source edits)

Date 2026-11-16. DB: clone `lmanagement_restore_verify_live_20261116` (222 licences, 1044 BOE, 565 trades, 8159 BOE rows). Read-only (`SET TRANSACTION READ ONLY` + rollback), DRF `APIClient` + `force_authenticate` (superuser) + `CaptureQueriesContext`. `DB_NAME` verified before running. Single local machine, Redis cache cleared before cold run; "warm" = second call. Scripts live in `/tmp/perf` (not committed).

## 1. Endpoint query counts

| Endpoint | page_size 10 (queries / ms) | page_size 50 (queries / ms) | Verdict |
|---|---|---|---|
| `/api/licenses/` list | 68 / 106-468 | 267 / 185 (84 rows match default filter) | **N+1: about 5 queries per row** |
| `/api/licenses/{id}/` detail | 172 / 180-198 | n/a | heavy fan-out (38 SUM on tradeline, 21 itemplan, 12 BOE) |
| `/api/bill-of-entries/` list | page_size=1: 41, 2: 64, 5: 159 (only 5 rows match) / 123-189 | 159 / 166-189 | **N+1: about 23-30 queries per row**, extrapolates to over 1,000 per 50 rows |
| `/api/trades/` list | 52 / 210-225 | 82 / 259-261 | mild N+1 (about 0.75 per row), plus 150-175 ms planning cost |
| `/api/allotments/` list | 10 / 23 | 10 / 20 | OK (constant; only 5 rows) |
| `/api/dashboard/` | 23 cold / 52 ms, 0 warm / 2 ms | n/a | OK, cached |
| `/api/item-pivot/`, `/api/reports/item-pivot/` | 4 cold / 10-14 ms, 0 warm | same | OK, cached (8 groups) |
| `/api/inventory-balance/` viewset | 5 / 8-12 | 5 / 7-8 | OK |
| `/api/reports/inventory-balance/` | 400 (required params missing) | n/a | NOT MEASURED |
| `/api/license-items/` | 3 / 5-6 | 3 / 9 | OK |

"Balance ledger" per-licence ledger endpoints (`license-ledger`) are download/job actions, not list endpoints, and were not measured. Item pivot on a larger dataset or non-default filters was not measured.

## 2. Index and table statistics (clone)

Caveat: `pg_stat_*` on a clone reflect only restore plus my runs (stats_reset is NULL, 39,738 total index scans). "idx_scan = 0" is **weak evidence**; confirm on production stats before any drop.

| Finding | Evidence |
|---|---|
| Seq scans on larger tables | `bill_of_entry_billofentrymodel` 156 seq vs 11,815 idx scans (1044 rows, benign); `core_activitylog` 30 seq scans, 2.7M tuples read (log table, 182k rows); `core_hscodemodel` 15 seq, 13.7k rows (small). No big-table seq-scan problem. |
| Unused non-unique indexes | 504 on the clone; 12 largest are all on `core_activitylog` (about 38 MB). Mostly small tables otherwise. |
| Duplicate: `core_exchangeratemodel` | `core_exchan_date_684554_idx (date DESC)` duplicates `core_exchangeratemodel_date_key UNIQUE (date)`. A btree scans backward, so the DESC index is redundant. **Confirmed.** |
| Duplicate: `license_licenseimportitemsmodel` | `license_lic_license_d4d897_idx (license_id)` = `license_licenseimportitemsmodel_license_id_503c5ff6 (license_id)`; `license_lic_hs_code_063682_idx (hs_code_id)` = `..._hs_code_id_25f4836b`. Also covered by the prefix of the UNIQUE (license_id, serial_number). **Confirmed.** |
| Duplicate: `license_licenseitemplan` | `license_lic_license_d687ab_idx` = `license_licenseitemplan_license_id_70c40e86`; `license_lic_import__259dda_idx` = `..._import_item_id_8bf3c2c6`. **Confirmed.** |
| `license_number` | Only `license_number_key` (UNIQUE) plus `_like` (varchar_pattern_ops, serves LIKE/startswith). **No duplicate in the live DB**, so the DATABASE_ARCHITECTURE.md claim is not confirmed here (it is a different opclass). |
| Other duplicate definitions | 12 tables have 2 identical-definition indexes (allotment_allotmentitems, license_incentivelicense, licenseownership, reconciliation_boeallotmentallocation, externalinvoicelink, invoiceboeallocation, reconciliationnote, plus the three above). A full list needs a follow-up query. |

## 3. EXPLAIN (ANALYZE, BUFFERS) of the 5 slowest distinct queries

Main finding: **execution is sub-millisecond; the time is planning**.

| # | Query (endpoint) | Captured ms | Planning ms | Execution ms | Notes |
|---|---|---|---|---|---|
| 1 | `SELECT DISTINCT trade_licensetrade...` 7 joins (trade list) | 161 | 162-175 | 0.5 | Plan fine (index scan + nested loops); the planner spends 150+ ms. Large query text (6.2k chars) with many EXISTS/LEFT JOINs. |
| 2 | `SELECT DISTINCT license_licensedetailsmodel...` 8 joins (licence list) | 70 | 54 | 0.5 | Same pattern. |
| 3 | `COUNT(*)` over the DISTINCT subquery (licence list) | 19 | 1.7 | 0.4 | Seq scans on tiny tables; fine. |
| 4 | SUM tradeline.cif_fc by licence (licence list) | 14 | 1.3 | 0.2 | Seq scan on tradelines (874 rows); fine. |
| 5 | SUM BOE rowdetails.cif_fc by licence (licence list) | 11 | 2.2 | 1.1 | Seq scan on rowdetails (8159 rows, 1505 kept); fine at this size. |

Planning time is probably inflated by the DISTINCT over a wide join list. This is a hypothesis; not isolated (needs a `SET join_collapse_limit`/`from_collapse_limit` experiment or a look at the filter/queryset code).

## 4. `core_activitylog`

| Metric | Value |
|---|---|
| Rows | 182,156 (2026-05-11 to 2026-11-16) |
| Size | table 47 MB + 13 indexes 39 MB = 86 MB total |
| Growth | about 20-54k rows/month (Aug 54k, Oct 41k); about 31k/month average, about 14 MB/month all-in |
| Mix | 45% `masters VIEW` (81.5k), licences VIEW 20.7k, ledger DOWNLOAD 19.6k, trades VIEW 11.9k, ledger-task-status VIEW 7.7k |
| Indexes | 4 composite (module/action/user_id/username + timestamp) AND 5 single-column + 3 `_like` indexes on the same columns, plus a `timestamp` index. The single-column `action`, `module`, `username`, `user_id` indexes are prefixes of the composites (the `_like` ones serve only LIKE on 3 columns). `idx_scan` is 0 for all (weak evidence, see above). |
| Seq scans | 30 (2.7M tuples read) |

## Findings, fixes, gain, risk

| # | Finding | Fix | Expected gain | Class | Risk |
|---|---|---|---|---|---|
| 1 | BOE list N+1, about 23-30 queries per row (SUM aggregates per row for rowdetails, tradeline, boeallotment allocation) | Annotate or batch-compute these aggregates per page (Subquery/prefetch) in the viewset/serializer | 159 to a constant of about 10-15 queries; a page of 50 would drop from over 1,000 | SAFE in code, but touches balance/CIF values: **BUSINESS-RULE flag**, needs `cif-balance-auditor` + exact before/after equality tests | Decimal drift, filter semantics |
| 2 | Licence list N+1, 5 per row (`scheme_code`, `notification_number`, `transfer`, `export items`, `sion_norm_class`) | `select_related('scheme_code','notification_number')`, `prefetch_related('transfers','export_license', ...)` | 267 to about 20 queries at page 50; about 5x fewer round-trips | SAFE | Low; confirm serializer field names and prefetch ordering |
| 3 | Licence detail 172 queries (38 tradeline SUM, 21 itemplan, 12 BOE) | Batch per-item aggregates (one grouped query) | 172 to under 40 | SAFE in code; **BUSINESS-RULE flag** (balance math) | Same as 1 |
| 4 | Query planning 54-175 ms on DISTINCT list queries (trade, licence) | Investigate the DISTINCT + many LEFT JOINs/EXISTS in the filter backend; replace `.distinct()` with `Exists()` filters, or reduce join count | Trade list about 150-175 ms to under 20 ms; licence list about 55 ms saved | SAFE if results are identical (verify counts and ids) | Duplicate or missing rows if the join semantics change |
| 5 | Trade list mild N+1 (about 0.75 per row; 11 BOE, 11 tradeline SEL, 10 SUMs per 50 rows) | prefetch lines/BOE; annotate sums | 82 to about 25 queries | SAFE | Balance numbers, as in 1 |
| 6 | Redundant duplicate indexes (exchange rate date DESC, ImportItems license/hs_code x2, ItemPlan license/import_item x2) | Drop the redundant ones: Meta `Index` entries plus `RemoveIndex` (concurrent) | Lower write amplification and disk; read no change | **NEEDS APPROVAL** (drop; verify on prod stats first) | Low if the FK index is kept; migration must run non-atomic |
| 7 | `core_activitylog` unbounded growth (86 MB, about 14 MB/month, 45% VIEW noise) | Retention/archive job (for example, 90 days) and/or stop logging `masters VIEW`; drop redundant single-column indexes covered by the composites | Halves the size; faster inserts; fewer seq scans | **NEEDS APPROVAL** (retention/archival, index drop; audit-trail policy) | Loss of audit history; compliance |
| 8 | Additive index for activitylog `(timestamp)` use? | Already present. No additive index proposed | n/a | n/a | n/a |

## Not measured / limits
- Clone is small; per-row slope is the reliable signal, absolute ms are machine-specific.
- `/api/reports/inventory-balance/` needs params (returned 400); `license-ledger` job actions, Excel/PDF exports skipped.
- Cold first licence-list run (468 ms) includes connection/ORM warmup.
- No production stats, so every drop recommendation requires confirmation there.
