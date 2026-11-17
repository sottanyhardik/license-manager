# 03 - Database Architecture (Phase-Zero discovery)

Scope: read-only audit of the LOCAL dev DB `lmanagement` (PostgreSQL 18.7, 122 tables, 3 matviews, 0 user triggers, 0 user functions). No writes, no DDL, `test_lmanagement` untouched. Date: 2026-11-15.

Caveats up front:
- Dev data is a partial copy of production: all 10 `trade_*` tables, `reconciliation_boeallotmentallocation`, `reconciliation_invoiceboeallocation` and `license_invoice*` have **0 rows**. Integrity probes on those are vacuous and must be re-run on a prod snapshot (section 5).
- `n_live_tup` is a planner estimate. `pg_stat_database.stats_reset` is NULL (never reset), but stats reflect one dev machine's usage, not production traffic, so "unused index" evidence is weak.
- All SQL was run via `psql -h localhost -d lmanagement`; counts are exact unless marked "approx".

## 1. Schema overview per Django app

Models live in `backend/apps/<app>/models*` (license and allotment are packages). Line refs come from the code index.

| App | Key models (file:line) | Rows (dev) | Notes |
|---|---|---|---|
| core | `ActivityLog` core/models.py:832, `AuditModel` :96, masters (Company, Port, HSCode, ItemName, SionNormClass, SionImport/Export), sync tables (`core_syncevent`, `core_syncconflictlog`, `core_synccursor`) | activitylog 334,352 | 19 migrations; masters carry `sync_version` (master-data-service sync) |
| license | `LicenseDetailsModel` license/models/core.py:91, `LicenseExportItemModel` :860, `LicenseImportItemsModel` :902, `LicenseItemPlan` :1267, `LicenseReplanRequest` :1194, `LicenseBalance` :2360, `SionPlanning*` :1396-1811, `IncentiveLicense` :2079 | licences 2,185; import items 26,818; export items 2,178; plans 2,528; replan requests 19,312 | 56 migrations (largest app) |
| allotment | `AllotmentModel` allotment/models/core.py:46, `AllotmentItems` :212; `AllocationVersion`, `AuditEvent`, `Shortfall` (own files) | 6,499 / 11,561 items | the last three tables are empty |
| bill_of_entry | `BillOfEntryModel` bill_of_entry/models.py:185, `RowDetails` :380 | BOE 14,392; row details 168,513 | `RowDetails` holds both debit (`D`) and credit (`C`) rows |
| trade | `LicenseTrade` trade/models.py:138, `LicenseTradeLine` :495, `IncentiveTradeLine` :581, `LicenseTradePayment` :650, `TradeInvoiceDocument` :693 | 0 | invoice lines live here; `license_invoice*` is a second, empty invoice model |
| reconciliation | `InvoiceBOEAllocation` reconciliation/models.py:226, `BOEAllotmentAllocation` :331, `ExternalInvoiceLink` :434, `IgnoredWarning` :518, `ReconciliationLog` | 61 (log only) | allocations are versioned (`is_current`, `version`, `superseded_by`) |
| accounts / tasks | custom user, Celery task records | - | 6 / 1 migrations |
| Non-app tables | `ebrc_*` (4 tables, ~27.7k rows), `eScrap_*` (3 tables, ~30.6k rows) | | no models under `backend/apps/*`; referenced only by `lmanagement/tasks.py` and scripts. They hold the only float-money columns (section 4) |

### Financial relationships and delete behaviour

Django enforces `on_delete` in Python (the deletion Collector). In the DB, 248 of 253 FK constraints are `NO ACTION`, 4 are `SET NULL`, 1 is `CASCADE`. So raw SQL deletes are blocked by the FK, but an ORM `.delete()` cascades according to the model values below.

| Relationship | Model on_delete (file:line) | DB-level | Risk |
|---|---|---|---|
| Licence -> ExportItem | CASCADE (license/models/core.py:861) | NO ACTION | deleting a licence removes its items |
| Licence -> ImportItem | CASCADE (:904) | NO ACTION | same |
| ImportItem -> HSCode; ExportItem -> Item / NormClass | CASCADE (:907, :864, :866) | NO ACTION | deleting a master cascades into licence items |
| Allotment -> AllotmentItems | CASCADE (allotment/models/core.py:223) | NO ACTION | |
| ImportItem -> AllotmentItems | CASCADE (:215) | NO ACTION | deleting an import item deletes allotments against it |
| BOE -> RowDetails | CASCADE (bill_of_entry/models.py:383) | NO ACTION | |
| ImportItem -> RowDetails (`sr_number`) | CASCADE (:391) | NO ACTION | deleting an import item deletes BOE history |
| Trade -> TradeLine | CASCADE (trade/models.py:514); `sr_number` PROTECT (:527) | NO ACTION | billed SRs protected |
| BOEAllotmentAllocation -> RowDetails / AllotmentItem | PROTECT (reconciliation/models.py:371, :376) | NO ACTION | protects only once allocations exist; the CASCADE rows above can still be reached first in the Collector's plan only if no allocation rows reference them |
| BOE / RowDetails `created_by`, `modified_by` | SET_NULL | SET NULL (the 4 DB-level SET NULLs) | fine |
| BOE <-> Allotment M2M | `bill_of_entry_billofentrymodel_allotment`, 6,394 rows, unique (boe, allotment) | | 0 dangling |

Finding: financial history (BOE rows, allotments) hangs off `LicenseImportItemsModel` via CASCADE. ERP-grade design wants PROTECT/RESTRICT plus soft-delete (`LicenseItemPlan` already has `is_deleted`/`is_cancelled`).

## 2. Table sizes (top 25 by `pg_total_relation_size`)

Totals: tables 152 MB + indexes 125 MB (772 indexes). Small DB; shape matters more than size.

```sql
select relname, n_live_tup, pg_size_pretty(pg_total_relation_size(relid))
from pg_stat_user_tables order by pg_total_relation_size(relid) desc limit 25;
```

| # | Table | Rows | Total size |
|---|---|---|---|
| 1 | core_activitylog | 334,352 | 157 MB |
| 2 | bill_of_entry_rowdetails | 168,513 | 32 MB |
| 3 | license_licensereplanrequest | 19,312 | 15 MB |
| 4 | license_licenseimportitemsmodel | 26,818 | 9.4 MB |
| 5 | bill_of_entry_billofentrymodel | 14,392 | 5.9 MB |
| 6 | item_balance_mv | 26,818 | 5.6 MB |
| 7 | allotment_allotmentitems | 11,561 | 4.9 MB |
| 8 | core_hscodemodel | 13,701 | 4.7 MB |
| 9 | license_licensenotes | 2,185 | 3.8 MB |
| 10 | license_licenseimportitemsmodel_items | 23,892 | 3.3 MB |
| 11 | eScrap_companylistmodel_port | 29,239 | 3.1 MB |
| 12 | core_sionimportmodel | 10,720 | 3.1 MB |
| 13 | ebrc_shippingdetails | 27,524 | 2.8 MB |
| 14 | token_blacklist_outstandingtoken | 5,749 | 2.8 MB |
| 15 | allotment_allotmentmodel | 6,499 | 2.5 MB |
| 16 | license_licenseitemplan | 2,528 | 2.4 MB |
| 17 | django_session | 3,485 | 1.7 MB |
| 18 | license_licensedetailsmodel | 2,185 | 1.3 MB |
| 19 | core_productdescriptionmodel | 3,083 | 1.2 MB |
| 20 | bill_of_entry_billofentrymodel_allotment | 6,394 | 1.1 MB |
| 21 | core_sionnormclassmodel | 2,086 | 0.8 MB |
| 22 | core_sionexportmodel | 2,098 | 0.8 MB |
| 23 | license_licenseexportitemmodel | 2,178 | 0.6 MB |
| 24 | django_admin_log | 3,619 | 0.6 MB |
| 25 | license_licensetransfermodel | 2,272 | 0.5 MB |

### core_activitylog growth (written by `ActivityLogMiddleware`, core/middleware.py:138)

`select to_char(date_trunc('month',timestamp),'YYYY-MM'), count(*) from core_activitylog group by 1`

| Month | Rows | Month | Rows |
|---|---|---|---|
| 2026-05 (from 05-11) | 13,504 | 2026-09 | 46,519 |
| 2026-06 | 35,847 | 2026-10 | 63,888 |
| 2026-07 | 69,693 | 2026-11 (15 days) | 19,963 |
| 2026-08 | 84,938 | | |

- 334,352 rows in about 6 months (~55k/month, 157 MB): larger than all licence, BOE and allotment tables combined. 334,216 rows (99.96%) have `extra = '{}'`.
- 11 secondary indexes (4 composite `(col, timestamp)` plus 7 single-column, 4 of them `_like`); the 4 composites and 7 of the singles show `idx_scan = 0`; about 55 MB of the 157 MB is indexes.
- No retention task: Celery beat (`lmanagement/celery.py:43-123`) has `cleanup_old_task_records` but nothing for the activity log, and `apps/core` has no purge for it.

## 3. Indexes

`select count(*) from pg_stat_user_indexes where idx_scan=0` = **692 of 772** (includes pkeys and uniques; dev-only usage).

| Check | Result | Evidence |
|---|---|---|
| Single-column FKs without a leading index | **0** | `pg_constraint` anti-join on `pg_index.indkey[0]` |
| Non-unique, non-PK indexes never scanned | 77.5 MB total; 11 of the top 15 are on `core_activitylog` (module 11 MB, action 10 MB, username 10 MB, user_id 10 MB) | `pg_stat_user_indexes` |
| Other notable never-scanned | `item_balance_mv_available_quantity_idx` (0.7 MB), `license_lic_availab_42a15c_idx` and `_1f176a_idx` on import items (0.7 MB each), `bill_of_entry_rowdetails_created_by_id_*` (1.2 MB) | same |
| Exact duplicate indexes (same table, columns, opclass, predicate) | **16 pairs** | `group by indrelid, indkey, indclass, indpred, indexprs having count(*)>1` |

Duplicate pairs (cause: `Meta.indexes` entries duplicating the auto FK / `db_index` / unique index):

| Table | Redundant (Meta.indexes name) | Keep |
|---|---|---|
| license_licensedetailsmodel | `license_lic_license_da9183_idx` | unique `..._license_number_key` |
| license_licenseimportitemsmodel | `license_lic_license_d4d897_idx`, `license_lic_hs_code_063682_idx` | FK indexes |
| license_licenseitemplan | `license_lic_import__259dda_idx`, `license_lic_license_d687ab_idx` | FK indexes |
| license_licenseownership | `license_lic_current_4371d8_idx` | FK index |
| license_incentivelicense | `license_inc_sold_st_6466d5_idx`, `license_inc_license_d1e17f_idx`, `license_inc_license_0c52e3_idx` | auto indexes / unique |
| allotment_allotmentmodel | `allotment_a_related_0e68da_idx` | FK index |
| allotment_allotmentitems | `allotment_a_status_0046e6_idx` | auto status index |
| core_exchangeratemodel | `core_exchan_date_684554_idx` | unique `..._date_key` |
| reconciliation (boeallotmentallocation, invoiceboeallocation, externalinvoicelink, reconciliationnote) | `reconciliat_status_*_idx` (4) | auto status index |

Other index smells:
- `*_like` (varchar_pattern_ops) indexes on low-cardinality status columns (for example `bill_of_entry_billofentr_planning_mapping_status_1630425a_like`, `reconciliation_boeallotmentallocation_status_b092247a_like`) are pure write overhead.
- `bill_of_entry_billofentrymodel` has 16 indexes for 14k rows, including `is_fetch` (boolean) and `bill_of_entry_number` alone (the unique `(number, date)` already serves prefix lookups).
- Seq-scan hot spots (`pg_stat_user_tables`): `bill_of_entry_rowdetails` 161 scans reading 25.4M tuples; `core_itemnamemodel` 12,151 seq scans; `reconciliation_reconciliationlog` 73,028 seq scans on 61 rows (harmless). Only the RowDetails scans merit an `EXPLAIN`, and the originating query is not identified here.
- Missing-index candidates need production `pg_stat_statements`, which is not available locally. None are claimed.

## 4. Constraints and types

### Decimal vs float

| Result | Evidence |
|---|---|
| All licence / allotment / BOE / reconciliation / trade money and quantity columns are `numeric` (110 numeric columns match money/qty name patterns) | `information_schema.columns` |
| Float columns exist only in non-app legacy tables: `eScrap_companylistmodel.amount`, `ebrc_ebrcdetails.realised_value`, `ebrc_exchangeratemodel.{usd,euro,gbp}_{export,import}` (8 columns) | `data_type='double precision'` |
| No `FloatField` in `backend/apps/**/models*` | grep; the only string hit is the field-type map in `validate_db_fields.py:263` |

Precision observed: `cif_fc` numeric(20,3); allocation `allocated_qty` numeric(20,4); BOE `exchange_rate` numeric(12,4).

### Nullability

| Column group | State |
|---|---|
| Licence import/export items: `cif_fc`, `cif_inr`, `quantity`, `available_*`, `debited_*`, `allotted_*`, `fob_*`, `net_quantity` | all NOT NULL |
| `allotment_allotmentitems.cif_fc/cif_inr/qty` | NOT NULL; `released_quantity`, `reactivated_quantity` nullable |
| `allotment_allotmentitems.item_id`, `allotment_id` | nullable (model `null=True`, allotment/models/core.py:215-226) though 0 rows are actually null or orphaned |
| `bill_of_entry_rowdetails.bill_of_entry_id` | nullable; **146,554 of 168,513 rows (87%) are NULL**. All are `row_type=AT, transaction_type=C`; all 21,959 `D` rows have a BOE |
| `bill_of_entry_billofentrymodel.company_id` | nullable; **2,217 of 14,392 BOEs (15%) have NULL company**. `port_id` and `bill_of_entry_date` have 0 NULLs (date is nullable in schema) |

### Constraints present

- Check constraints: 88 in `public`. Money-relevant: `boeallotmentallocation_non_negative_amounts`, `invoiceboeallocation_non_negative_amounts`, `externalinvoicelink_non_negative_amounts`, `license_invoice_non_negative_totals`, `license_invoiceitem_non_negative_values`, plus `chk_final_party_classification_valid` and `chk_from_to_companies_different` on `trade_licensetrade`. The rest are auto `>= 0` checks on positive integers and SION planning rules.
- **No check constraints** on `license_licenseimportitemsmodel`, `license_licenseexportitemmodel`, `allotment_allotmentitems` or `bill_of_entry_rowdetails` (qty/CIF >= 0, `available <= quantity`, `debited <= quantity`). There are currently 0 negative values (section 5), so adding them would validate cleanly for those columns.
- Unique: 28 unique constraints and 11 partial unique indexes. Key ones: `license_number` (licence and incentive), BOE `(number, date)`, RowDetails `(bill_of_entry, sr_number, transaction_type)`, ImportItem `(license, serial_number)`, M2M BOE-Allotment, partial `allotment_unique_item_without_plan_line`, `allotment_unique_stable_plan_identity`, `uniq_purchase_supplier_invoice`, `uniq_sale_buyer_invoice_nonblank` (trade), `one_active_replan_request_per_license`.
- Missing or weak: BOE uniqueness ignores port (`unique_together`, bill_of_entry/models.py:235); the RowDetails unique cannot constrain the 146,554 NULL-BOE credit rows (NULLs are distinct in Postgres); no unique on `LicenseExportItemModel (license, item)` (0 duplicates today); no unconditional unique on `AllotmentItems (allotment, item)` (0 duplicates today).

## 5. Data-integrity probes (read-only, dev DB)

| Probe | Result |
|---|---|
| RowDetails -> ImportItem orphan (left join on `sr_number_id`) | 0 |
| RowDetails with NULL BOE | 146,554 (credit rows; see R3) |
| AllotmentItems -> Allotment / ImportItem orphan | 0 / 0 |
| Import / Export items -> Licence orphan | 0 / 0 |
| BOE <-> Allotment M2M dangling | 0 |
| Licences with 0 import items / 0 export items | 3 / 7 |
| BOEs with no row details | 24 |
| Duplicate BOE (number, date) | 0 (constraint holds) |
| Duplicate BOE (number, date, port) | 0 |
| **BOE numbers repeated with a different date** | **17 numbers** (legitimate reuse across years/ports, or variants; needs a business ruling) |
| Duplicate licence number (case/space-insensitive) | 0 |
| Import items with negative quantity / cif_fc / available_qty / available_value / debited_qty / allotted_qty | 0 for all six |
| Import items with NULL `cif_fc` | 0 |
| BOE rows with negative qty / cif_fc / cif_inr | 0 / 0 / 0 |
| BOE rows with zero qty / zero cif_fc | 1,760 / 132,816 (the latter mostly `C` rows) |
| Allotment items with zero `cif_fc` | 22 |
| Export items: negative cif_fc / zero cif_fc / `fob_fc<=0` | 0 / 8 / 1,364 |
| (BOE, import item) pairs with more than one row (D+C pairs) | 10,704 (likely legitimate; unique includes type) |
| Import items where sum of allotment `cif_fc` exceeds item `cif_fc` (approx) | 4,196. Overstated: sums all rows (every status is `CREATED`) without release or BOE linkage. It shows allotments are not capped by CIF in the schema; it is not a defect count |
| Import items with `debited_value + allotted_value > cif_fc` (approx, cached columns) | 17 |
| Import items with `debited_quantity > quantity` or `available_quantity < 0` (approx, cached columns) | 39 |
| Licences where sum of BOE `D` `cif_fc` exceeds sum of export-item `cif_fc` (approx; ignores the canonical CIF rule in `.claude/rules/business-rules.md`) | 13 of 1,999 licences with both sides |
| Trade / invoice line / reconciliation allocation integrity | not testable locally (0 rows) |

The over-utilisation counts use cached columns and raw sums, not the canonical ledger. Treat them as "worth a `cif-balance-auditor` pass", not as confirmed defects.

## 6. Materialized views

| MV | Rows | Defined in | Notes |
|---|---|---|---|
| `license_balance_mv` | 2,185 (= licences) | `apps/core/materialized_views.py:37`; created by `core/0003_create_materialized_views` (`RunPython`, reverse = drop); `license/0005` drops them | unique index `license_balance_mv_license_id_idx` (required for CONCURRENTLY) |
| `item_balance_mv` | 26,818 (= import items) | same module | |
| `dashboard_stats_mv` | populated | same module | |

- Refresh mechanisms: `refresh_materialized_view()` (materialized_views.py:290; `REFRESH MATERIALIZED VIEW [CONCURRENTLY]` at :304); Celery tasks in `apps/core/tasks_materialized_views.py` (:21-70); management command `refresh_materialized_views`; post_save/post_delete signals in `apps/core/signals_materialized_views.py` gated by `AUTO_REFRESH_ENABLED = False` (:22).
- **Celery beat (`lmanagement/celery.py:43-123`) schedules no MV refresh** and the signals are off, so refresh is manual. Dev MVs were last refreshed 2026-11-15 15:42; the newest licence edit is 2026-11-13, so they are fresh only because someone ran a refresh today.
- A grep of `backend/apps` found no ORM or SQL reader of `item_balance_mv` / `license_balance_mv` outside the MV module and its tests. Raw SQL in `scripts/` and report SQL were not checked. If unread, staleness is moot and they are dead weight; if read by reports, staleness is unbounded (decision D2).
- Three overlapping balance stores exist: the MVs, `license_licensebalance` (2,185 rows) and cached columns on import items (`available_*`, `debited_*`, `allotted_*`), with no DB-enforced consistency.

## 7. Migration history

`manage.py showmigrations --plan` ran against the local DB: **158 applied, 0 unapplied**. `django_migrations` has 160 rows, so 2 rows are not in the on-disk plan (probably removed or renamed apps; not investigated).

| App | Applied | Latest |
|---|---|---|
| license | 56 | 0056_add_cif_restriction_percentage |
| core | 19 | 0019_increase_natural_key_length_to_2000 |
| allotment | 16 | 0015_plan_identity_to_business_dimensions |
| bill_of_entry | 14 | 0013_repair_boe_number_date_unique_constraint_columns |
| trade | 11 | 0011_tradepairaudit_survive_trade_delete |
| accounts | 6 | 0006_repoint_legacy_user_fks |
| reconciliation | 5 | 0005_alter_reconciliationlog_action |
| tasks, license_movement, mds_client | 1 each | 0001_initial |
| third-party (auth 12, token_blacklist 12, admin 3, contenttypes 2, sessions 1) | | |

- Squash candidates: `license` (56) and `core` (19). 51 migration files contain `RunPython`/`RunSQL` (including the MV migrations `core/0003` and `license/0005`), so a squash needs care and a captured prod baseline first.
- Repair-type migrations (`bill_of_entry/0013_repair_boe_number_date_unique_constraint_columns`, `accounts/0006_repoint_legacy_user_fks`) show environment drift has already happened.

## 8. Top 10 database risks / opportunities (ranked)

| # | Risk / opportunity | Evidence | Impact | Proposed fix | Human approval? |
|---|---|---|---|---|---|
| R1 | ORM CASCADE from import item and masters into BOE rows and allotments | license/models/core.py:864, :866, :907; allotment/models/core.py:215; bill_of_entry/models.py:391; DB FKs all NO ACTION | one `.delete()` on an import item, HS code or item name can wipe financial history | PROTECT on financial paths plus soft-delete, in a reviewed reversible migration; `cif-balance-auditor` review | **Yes** (alters constraint behaviour; business-rule adjacent) |
| R2 | `core_activitylog`: 157 MB, ~55k rows/month, 11 indexes (~55 MB mostly never scanned), no retention | sections 2, 3 | largest table; write amplification on every API request; unbounded growth | drop redundant single-column and `_like` indexes; add retention (for example 180 days) or monthly partitioning; archive before purge | **Yes** (index drop on shared env; data deletion) |
| R3 | 87% of `rowdetails` have NULL `bill_of_entry_id`; the unique does not constrain them | 146,554 of 168,513 rows | duplicate credit rows are not DB-preventable; two concepts (BOE line vs ledger credit) share one table | confirm the credit business key, then add a partial unique `WHERE bill_of_entry_id IS NULL`, or split credits into their own table | **Yes** (constraint on populated table; needs domain ruling) |
| R4 | No DB check constraints on core quantity/CIF columns | section 4; 0 negatives today | any bug or raw import can write negative or over-debited values undetected | add `CHECK (>= 0)` (and `debited <= quantity` if the rule holds) as `NOT VALID`, then `VALIDATE`; rule on the 39 + 17 approx rows first | **Yes** |
| R5 | MVs have no scheduled refresh; three overlapping balance stores | section 6 | stale or divergent balances if any consumer reads them | pick one source of truth; schedule `REFRESH ... CONCURRENTLY` in beat, or drop unread MVs | Confirming readers: no. Scheduling or dropping on shared env: **yes** |
| R6 | 16 exact duplicate indexes from `Meta.indexes` duplicating FK/unique indexes | section 3 | write overhead (~10-15 MB), noise | remove duplicate `Meta.indexes` entries (`RemoveIndex`, reversible) | Dev-only: no. Shared/prod: **yes** |
| R7 | 15% of BOEs have NULL company; 17 BOE numbers repeat with different dates; BOE unique ignores port | sections 4, 5 | ambiguous ownership and reporting; wrong identity key if prod has multi-port data | data audit; define natural key with the business owner; backfill company | **Yes** (data change, key change) |
| R8 | Legacy `ebrc_*` / `eScrap_*` tables (~58k rows, float money) owned by no app | sections 1, 4 | schema outside migrations; float money | confirm usage; then adopt into an app with Decimal, or archive and drop | **Yes** (drop is irreversible) |
| R9 | Dev DB cannot validate trade, invoice or allocation integrity (0 rows) | caveats, section 5 | most reconciliation constraints untested at volume | re-run section 5 probes on a sanitised prod snapshot restored locally | **Yes** (prod data access) |
| R10 | Migration chain size and drift (license 56, core 19; repair migrations; 160 vs 158 rows) | section 7 | slow fresh builds; drift between environments | run `scripts/database/audit-db-integrity.sh` per environment; squash after baseline; identify the 2 extra rows | Squash and prod audit: **yes**. Local read-only diff: no |

## Unresolved decisions for the human

- D1: Are `C` (credit) `RowDetails` with NULL BOE intended, and what is their business key (R3)?
- D2: Does anything read the MVs (reports, scripts, other services)? Delete or schedule accordingly (R5).
- D3: Is the BOE natural key `(number, date)` or `(number, date, port)`? Are the 17 repeated numbers legitimate (R7)?
- D4: Retention window and archive target for `core_activitylog` (R2).
- D5: Can a sanitised prod snapshot be provided for trade/allocation probes (R9)?
- D6: Are `ebrc_*` / `eScrap_*` still in use (R8)?
