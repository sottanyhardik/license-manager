# Database Architecture (Phase 1 discovery, static analysis only)

Source: AST scan of `models.py` / `models/` packages + migration files. **No DB was touched**; applied state and live schema are NOT verified.
Paths relative to `backend/apps/`. Postgres, Django 6. Default PK is implicit `BigAutoField` unless stated.

## Global facts
- No model sets `db_table` or `managed=False` (all tables are Django default `<app>_<model>`). No `FloatField` anywhere in app models. No `simple_history`/`HistoricalRecords`.
- Base classes: `AuditModel` (`core/models.py:96`: `created_on` auto_now_add, `created_by` FK->AUTH_USER SET_NULL, `modified_on` auto_now, `modified_by` FK SET_NULL), `SyncTimestampModel` (`core/models.py:141`: `created_on` default now, `modified_on` auto_now **nullable**), `SyntheticUidMixin` (`:158` `uid` UUID null unique), `MasterSyncMixin` (`core/sync/mixins.py:76`: `master_uid` UUID unique null, `sync_version`, `is_tombstone` (soft delete), `origin_server`, `synced_at`).
- AUTH_USER_MODEL = `accounts.User` (custom; legacy `auth_user` FKs repointed by `accounts/migrations/0006`, `license/migrations/0008`).
- Soft delete: `MasterSyncMixin.is_tombstone` (masters); `LicenseItemPlan.is_deleted/is_cancelled/is_active` (`license/models/core.py:1365-1369`); reconciliation allocation tables use `is_current`+`status`+`superseded_by` (supersede, never delete: `reconciliation/models.py:226-300`).
- DB views: 3 materialized views created via RunPython in `core/migrations/0003_create_materialized_views.py` from `core/materialized_views.py`: `license_balance_mv` (:37; unique idx on license_id), `item_balance_mv` (:115; unique idx on item_id), `dashboard_stats_mv` (:194). Refresh: `core/tasks_materialized_views.py`, `core/signals_materialized_views.py`. These are not Django models.
- Model counts (concrete): accounts 2, allotment 5, bill_of_entry 2, core 23 (+7 sync models in `core/sync/models.py`), license 33, reconciliation 6, tasks 2, trade 9 = 82 (+7 = 89).
- Decimal usage: all money/qty are `DecimalField` (see precision table at the end).

## accounts (`accounts/models.py`)
| Model | Notes |
|---|---|
| `User` :42 (AbstractBaseUser+PermissionsMixin) | `username` unique; `email` unique null; M2M `groups`, `user_permissions` (custom related_names); `avatar` ImageField; no AuditModel; `date_joined`. |
| `RevokedAccessToken` :127 | `jti` unique + redundant `db_index`; Index(`expires_at`); `revoked_at`. |

## tasks (`tasks/models.py`)
- `Task` :8 (AuditModel): `assigned_to`, `rejected_by` FK->User SET_NULL; indexes (status,-created_on), (assigned_to,status), (created_by,status).
- `TaskRemark` :80: `task` FK CASCADE; `created_by` SET_NULL; own `created_on` auto_now_add (not AuditModel).

## core (`core/models.py`) - masters, all sync-aware
| Model (line) | Keys / constraints / FKs |
|---|---|
| `MasterChange` :192 | Index(model_label, at); db_index on label/natural_key/at. |
| `CompanyModel` :226 (MasterSync+Audit) | `iec` unique(10). pan/gst nullable, no unique. |
| `PortModel` :292 | `code` unique; unique_together(name, code) (redundant). |
| `ItemHeadModel` :307 (deprecated) | name unique; FK restriction_norm->SionNormClass SET_NULL; `unit_rate` Dec(15,2). |
| `ItemGroupModel` :345 | name unique. |
| `ItemNameModel` :359 | name unique; FK group CASCADE (null); FK sion_norm_class SET_NULL; M2M norms->SionNormClass; `normalized_name` indexed; `restriction_percentage` Dec(5,2); `display_order` int (comment says unique per norm class; no DB constraint). |
| `HSCodeModel` :415 | hs_code unique(8); `unit_price` Dec(15,2). |
| `HeadSIONNormsModel` :440 | Sync-timestamp base; `name` not unique. |
| `SionNormClassModel` :453 | `norm_class` unique; FK head_norm CASCADE. |
| `SIONExportModel` :469 / `SIONImportModel` :494 | FK norm_class CASCADE; SIONImport FK hsn_code SET_NULL (db_column hsn_code_id); `quantity` Dec(15,2); no unique (norm_class, serial_number). |
| `SionNormNote` :530 / `SionNormCondition` :555 | FK sion_norm CASCADE. |
| `ProductDescriptionModel` :580 | FK hs_code PROTECT. |
| `TransferLetterModel` :598, `UnitPriceModel` :612 (Dec 15,2), `InvoiceEntity` :641, `SchemeCode` :674 (code unique), `NotificationNumber` :685 (code unique), `PurchaseStatus` :696 (code unique) | simple masters. |
| `ExchangeRateModel` :714 | `date` unique; usd/euro/gbp/cny Dec(10,4); Index(-date) redundant with unique. |
| `CeleryTaskTracker` :775 | task_id unique; Index(status,completed_at), (task_name,status); own `created_at`. |
| `ActivityLog` :832 | FK user SET_NULL + `username` snapshot; 4 composite indexes; `timestamp` indexed. |
| Sync (`core/sync/models.py`) | `SyncConflictLog`:17, `SyncPeer`:40 (server_id unique), `SyncCursor`:70, `SyncEvent`:101 (event_id unique), `SyncInboxEvent`:130 (unique source_server,event_id), `SyncPeerDelivery`:145 (unique peer,event; both CASCADE), `MediaSyncTask`:164. All `app_label="core"`. |

## license (`license/models/core.py`, `license/models/invoice.py`)
| Model (line) | Keys / constraints / FKs |
|---|---|
| `LicenseDetailsModel` :91 (Audit) | `license_number` unique(50) + redundant Index; FK purchase_status/scheme_code/notification_number/port PROTECT (null); FK exporter->Company SET_NULL; indexes file_number, (exporter,license_date), (port,license_date), license_date, expiry. Money/flags moved to 1:1 child tables (:2339-2428). |
| `LicenseExportItemModel` :860 | FK license CASCADE; FK item, norm_class CASCADE (null); net_quantity/old_quantity/fob/cif Dec(15,2); `fob_exchange_rate` Dec(15,6). |
| `LicenseImportItemsModel` :902 | FK license CASCADE (db_index); FK hs_code CASCADE (null); M2M items->ItemName; unique_together(license, serial_number) :940; indexes license, hs_code, available_quantity, available_value. Qty Dec(15,3); cif/value Dec(15,2). **Denormalised**: `available_quantity/value`, `debited_*`, `allotted_*` (:919-926). |
| `LicenseReplanRequest` :1194 | FK license CASCADE; partial UniqueConstraint(license) WHERE status in (pending,queued,running,retry_pending). |
| `LicenseItemPlan` :1267 (Audit) | FKs import_item CASCADE, item_name SET_NULL, license CASCADE (null), planning_rule PROTECT; CheckConstraint active-not-deleted/cancelled; Dec(15,3)/(15,2); **cached** `remaining_quantity/remaining_cif_fc` (:1327-1331), `baseline_used_*` (:1348-1351). |
| `SionPlanningRule` :1396 | FK sion PROTECT; FK import_item PROTECT; partial UniqueConstraint(sion, stable_key, version); `max_unit_price` Dec(15,2); percentage Dec(5,2); cif_restriction Dec(4,2). |
| `SionPlanningUnitValueRow` :1495, `SionPlanningPercentageRow` :1542 | FK rule CASCADE, import_item PROTECT; unique(rule, import_item); checks. |
| `SionInputAliasConfig` :1580 | FK sion/output_item CASCADE (null); 3 indexes. |
| `SionPlanningProfile` :1660 / `Action` :1700 / `OutputMapping` :1743 / `Run` :1811 | uid/run_uid UUID unique; partial unique active profile per sion; FKs PROTECT; OutputMapping conversion_factor/rate Dec(20,8). |
| `LicenseDocumentModel` :1859 | FK license CASCADE. |
| `StatusModel` :1878, `OfficeModel` :1885, `AlongWithModel` :1892, `DateModel` :1899, `LicenseInwardOutwardModel` :1906 | lookup + log; all FKs CASCADE (license nullable :1908). |
| `LicenseTransferModel` :2019 | FK license CASCADE; from/to company SET_NULL; user FKs SET_NULL. |
| `IncentiveLicense` :2079 (Audit) | FK exporter, port_code CASCADE; license_value/sold_value/balance_value Dec(15,2) (:2104-2120; sold/balance "auto-calculated"). |
| `LicensePurchase` :2215 (Audit) | FK license CASCADE; Dec(15,2), exchange_rate/markup Dec(15,6), quantity_kg Dec(15,3). |
| `LicenseNotes` :2339, `LicenseBalance` :2360, `LicenseFlags` :2384, `LicenseOwnership` :2410 | OneToOne license **primary_key=True** CASCADE; `LicenseBalance.balance_cif` Dec(15,2) with MinValue 0 validator (:2370), Index. |
| `LicenseLedgerPackageJob` :2436 | `public_id` UUID unique; FK requested_by PROTECT; `created_at/updated_at` (not AuditModel). |
| `LicenseLedgerPackageItem` :2492 | unique(job, license); job CASCADE; license PROTECT. |
| `LicensePackageArtifact` :2550, `LicensePackageAuditEvent` :2572 | FKs CASCADE; actor PROTECT. |
| `LicenseLedgerRecoveryAudit` :2584 | FK trade PROTECT; created_by PROTECT. |
| `Invoice` :53 (invoice.py) | `invoice_number` unique(50); FK bills_of_entry->BOE **CASCADE** null; FK from_entity->InvoiceEntity CASCADE; CheckConstraint non-negative totals; total_qty Dec(12,3), money Dec(15,2). |
| `InvoiceItem` :168 | FK invoice CASCADE; FK sr_number->ImportItems **CASCADE**; qty Dec(12,3) null; cif/fob Dec(15,2) null; check non-negative-or-null. |

## allotment (`allotment/models/`)
| Model | Keys / constraints / FKs |
|---|---|
| `AllotmentModel` (core.py:46) | FK company PROTECT, related_company PROTECT null, port PROTECT null, planning_target_item PROTECT null; `required_quantity` Dec(15,**2**); `unit_value_per_unit` Dec(15,3); `cif_fc/cif_inr` Dec(15,2) null; `exchange_rate` Dec(15,6) null; `invoice` is a free-text CharField (:95, indexed); 7 indexes. |
| `AllotmentItems` (core.py:212) | FK item->ImportItems **CASCADE null** (:213); FK allotment **CASCADE null** (:221); planning_target_item/plan_line/previous_version SET_NULL; `cif_inr/cif_fc` Dec(15,2); `qty` Dec(15,3); UniqueConstraints (item, allotment, allocation_basis[, planning_target_item]) split by NULL-ness of target (:338-350); indexes status, (allotment,status), stable identity. `search_mode` duplicates `allocation_basis` shape. |
| `AllocationVersion` (allocation_version.py:5) | FK allocation_item PROTECT; snapshot qty Dec(15,3)/cif Dec(15,2); FK company SET_NULL; no (item, version) unique. |
| `AuditEvent` (audit_event.py:8) | FK allocation_item PROTECT null; actor->`User` SET_NULL (:43); before/after Dec; JSON details. |
| `Shortfall` (shortfall.py:6) | FK license CASCADE (:26); Dec(15,3)/(15,2). |

## bill_of_entry (`bill_of_entry/models.py`)
- `BillOfEntryModel` :185: FK company PROTECT null (:189), port PROTECT null, planning_target_item PROTECT null; **unique_together(bill_of_entry_number, bill_of_entry_date)** :235 with date NULLABLE (:197); M2M allotment->AllotmentModel (:212, implicit through, no per-row quantity); `exchange_rate` Dec(12,4); `failed` int.
- `RowDetails` :380: FK bill_of_entry CASCADE null (:381); FK sr_number->ImportItems **CASCADE** (:389); unique_together(bill_of_entry, sr_number, transaction_type) :429; `cif_inr/cif_fc` Dec(15,**3**) (:395-401); `qty` Dec(15,3); `is_frozen`, `is_dispute` flags.

## trade (`trade/models.py`)
- `LicenseTrade` :138 (Audit): `direction` indexed; `invoice_number` char(128) default "" (:217); FK from/to company SET_NULL null (:190,197); final_party PROTECT; incentive_license SET_NULL; M2M boes->BOE (:183); self FKs linked_trade SET_NULL, copied_from PROTECT, O2O counterpart PROTECT; `transaction_pair_uuid`; subtotal/roundoff/total Dec(20,2). Constraints (:309-340): from!=to check; partial unique (from_company, invoice_number, direction) for PURCHASE non-blank; partial unique (to_company, invoice_number, direction) for SALE non-blank; final-party classification check.
- `LicenseTradeLine` :495: FK trade CASCADE (:513); FK sr_number PROTECT (:525); O2O counterpart_line self CASCADE; qty_kg Dec(20,4), cif_fc Dec(20,2), exc_rate Dec(12,4), rate Dec(20,3), pct Dec(9,3). No check/unique.
- `IncentiveTradeLine` :581 (trade CASCADE, incentive_license PROTECT); `LicenseTradePayment` :650 (trade CASCADE; amount Dec(20,2)); `SaleClassificationDecision` :476 (trade PROTECT, decided_by PROTECT); `TradePairAudit` :668 (FKs SET_NULL + BigInt id snapshots, survives trade delete); `TradeInvoiceDocument` :693 (unique trade+version_hash); `InvoiceDocumentAccessToken` :723 (UUID pk); `InvoiceDocumentAuditEvent` :751 (UUID pk).

## reconciliation (`reconciliation/models.py`)
- `ReconciliationNote` :23, `ReconciliationLog` :95: FKs to trade/BOE/license_item all **SET_NULL** (logs lose their subject on delete); JSON before/after.
- `InvoiceBOEAllocation` :226: FK trade_line PROTECT (:263), row_details PROTECT (:268); allocated_qty Dec(20,4), cif_fc/cif_inr Dec(20,3); CheckConstraint >=0; `superseded_by` self SET_NULL; `status`, `is_current` indexed individually. **No unique constraint.**
- `BOEAllotmentAllocation` :331: FK row_details PROTECT (:369), allotment_item PROTECT (:374); same shape/precision; **no unique constraint**.
- `ExternalInvoiceLink` :434: FK row_details PROTECT; qty Dec(20,4), cif Dec(20,3); Index invoice_number; **no unique**.
- `IgnoredWarning` :518: unique(license, warning_type, entity_type, entity_id); FK license CASCADE.

## master-data-service (`master-data-service/masters/models.py`, 362 lines, 1 migration `0001_initial`)
Mirror of core masters: `MasterModel` base(:35), `SyntheticKeyMixin` (uid UUID unique, :51), Company(iec unique), Port(unique code + unique_together name,code), ItemHead, ItemGroup, ItemName, HSCode, HeadSIONNorm, SIONNormClass, SIONExport/Import, SIONNormNote/Condition, ProductDescription, UnitPrice, SchemeCode, NotificationNumber, ExchangeRate (date unique; Dec(10,4)), MasterChange(:318). Same decimal precisions as core. No auth FK found by grep.

## Precision map (money / quantity)
| Concept | Where: (digits,dp) |
|---|---|
| Quantity | Allotment.required_quantity (15,2) `allotment/models/core.py:56`; AllotmentItems.qty (15,3) :241; RowDetails.qty (15,3) `bill_of_entry/models.py:407`; ImportItems qty (15,3) `license/models/core.py:912`; Invoice total_qty (12,3); allocations (20,4) `reconciliation/models.py:280,383,474`; TradeLine.qty_kg (20,4) `trade/models.py:536` |
| CIF FC | ImportItems (15,2) :916; AllotmentItems (15,2) :235; **RowDetails (15,3)** BOE:401; allocations (20,3); TradeLine (20,2) |
| Exchange rate | Allotment (15,6) :84; BOE (12,4) :205; TradeLine (12,4); ExchangeRateModel (10,4); LicensePurchase (15,6) |

## Findings (ranked by risk). All remedies are proposals; none implemented.

1. **HIGH - no DB uniqueness on current allocations (duplicate debit risk).** `reconciliation/models.py:226,331,434` (`InvoiceBOEAllocation`, `BOEAllotmentAllocation`, `ExternalInvoiceLink`). Only CHECK >=0 and single-column indexes; duplicates of the same (trade_line,row_details) / (row_details,allotment_item) with `is_current=True, status=ACTIVE` are prevented only by app code. Remedy: expand = read-only duplicate audit query on local DB; contract = partial `UniqueConstraint(fields=[...], condition=Q(is_current=True, status="ACTIVE"))` added via `AddIndexConcurrently` (non-atomic) after any duplicates are reconciled by a human; reverse = drop index. Also replace `Index(status)`/`Index(is_current)` with composite partial indexes.
2. **HIGH - BOE identity uniqueness bypassed by NULL date.** `bill_of_entry/models.py:235` with nullable date `:197`; Postgres treats NULLs as distinct, so duplicate (number, NULL) BOEs are allowed. History of drift: migrations 0012/0013 "repair" the constraint columns, indicating DB != state on some deployments. Remedy: partial unique index on `bill_of_entry_number WHERE bill_of_entry_date IS NULL` (CONCURRENTLY), or backfill + `NOT NULL` later; verify live constraint columns read-only first.
3. **HIGH - CASCADE on financial/debit history.** `bill_of_entry/models.py:381,389` (RowDetails -> BOE, ImportItem), `allotment/models/core.py:213,221` (AllotmentItems -> ImportItem, Allotment), `license/models/invoice.py:54,170` (Invoice->BOE, InvoiceItem->SR), `license/models/core.py:904` (ImportItems->License), `trade/models.py:513,656` (TradeLine, Payment -> Trade), `allotment/models/shortfall.py:26`. Deleting a parent removes debit/allotment/payment rows silently (partially shielded by PROTECT on reconciliation allocations `:263,268,369,374`, and by `PROTECT` on `AllocationVersion/AuditEvent.allocation_item`). Remedy: AlterField `on_delete=PROTECT` (Django-level only, no DDL; zero data risk) in a reviewed migration, after checking admin/delete flows and tests that rely on cascade.
4. **MEDIUM-HIGH - redundant/denormalised balance columns with several sources of truth.** `license/models/core.py:919-926` (available/debited/allotted on import item), `:2370` (`LicenseBalance.balance_cif`), `:2112-2120` (IncentiveLicense sold/balance), `:1327-1351` (plan remaining/baseline), plus 3 materialized views (`core/materialized_views.py:37,115,194`). Drift cannot be detected by constraints. Remedy: do not change semantics; add read-only drift-check queries/management command; optional CHECK (`available_quantity >= 0`) NOT VALID then VALIDATE after cleanup. Needs `cif-balance-auditor`.
5. **MEDIUM - inconsistent decimal precision for CIF/qty.** See precision map: Allotment qty 2dp vs items 3dp (`allotment/models/core.py:56` vs :241); RowDetails CIF 3dp (`bill_of_entry/models.py:395,401`) vs ImportItems/Allotment 2dp; allocations 3-4dp; exchange rate 4 vs 6 dp. Silent rounding at hand-offs. Remedy: widen-only (expand) where a narrower source feeds a wider sink; never narrow; document canonical rounding in business-rules, add tests.
6. **MEDIUM - DB-level non-negativity missing on core debit tables.** `AllotmentItems.qty/cif_*` (`allotment/models/core.py:229-245`), `RowDetails` (`bill_of_entry/models.py:395-407`), `LicenseImportItemsModel` (`license/models/core.py:912-926`; no validators at all), `LicenseTradeLine` (`trade/models.py:536-547`) rely on validators (bypassed by `bulk_create`, `update`, raw SQL). Remedy: `CheckConstraint(..., name=..)` added `NOT VALID` via RunSQL then `VALIDATE CONSTRAINT`; confirm business rule first (available_* may legitimately be negative on over-debit).
7. **MEDIUM - nullable FK / NULL-bypassed uniqueness on key joins.** `allotment/models/core.py:213,221` (AllotmentItems.item/allotment nullable but part of unique constraints :338-350), `bill_of_entry/models.py:381` (RowDetails.bill_of_entry nullable, in unique_together :429), `trade/models.py:190,197` (from/to company null -> partial uniques :309-320 do not fire when NULL), `license/models/core.py:1908` (LicenseInwardOutward.license). Remedy: audit NULL counts locally; if zero, SET NOT NULL via check-constraint-first pattern.
8. **MEDIUM - irreversible data migrations that delete rows** (see MIGRATION_REGISTER): `allotment/migrations/0015` (sums + deletes duplicate AllotmentItems, `:43`), `core/migrations/0014/0015/0016`, `license/migrations/0039/0040` (delete duplicate ItemNameModel after repointing). Reverse is noop. Historical data protection: confirm backups before any environment applies them.
9. **MEDIUM - legacy auth_user FK remnants.** `accounts/migrations/0006_repoint_legacy_user_fks.py` and `license/migrations/0008` repair constraints only where they still reference `auth_user`; legacy join tables `auth_user_groups`, `auth_user_user_permissions` are deliberately left. Fresh DBs vs old DBs may differ. Remedy: read-only `information_schema` check on local DB; keep reverse noop.
10. **LOW-MEDIUM - audit/log FK on_delete inconsistency.** `reconciliation/models.py:139-165` and `allotment/models/audit_event.py:43` use SET_NULL (history loses subject/actor) while `license/models/core.py:2578,2597` and `trade/models.py:484` use PROTECT. `ActivityLog` keeps a `username` snapshot (`core/models.py:868`); others do not. Remedy: standardise on PROTECT for subject FKs / snapshot columns for actors (expand: add snapshot columns, backfill, then switch).
11. **LOW - duplicate/redundant indexes (write amplification).** `license/models/core.py` LicenseDetails Index(license_number) vs unique; ImportItems Index(license) (:940 area) vs FK index + unique_together prefix, Index(hs_code) vs FK; LicenseItemPlan Index(license)/(import_item) vs `db_index=True`; `core/models.py:719` Index(-date) vs unique; `PortModel` unique_together(name,code) beside unique code; AllotmentItems Index(status) vs `db_index`. Remedy: `RemoveIndex` after `pg_stat_user_indexes` check on local only.
12. **LOW - timestamp inconsistency.** `created_on/modified_on` (AuditModel) vs `created_at/updated_at` (`license/models/core.py:2485`, `core/models.py:803`) vs `timestamp` (`core/models.py:879`); `SyncTimestampModel.modified_on` nullable (`core/models.py:152`). Cosmetic; do not rename (API-visible).
13. **LOW - business-key text columns without constraints.** `AllotmentModel.invoice` free text (`allotment/models/core.py:95`) instead of FK; `ItemNameModel.display_order` "must be unique per norm class" (`core/models.py:387`) not enforced by DB; `SIONImport(norm_class, serial_number)` not unique. Recommend only.
14. **INFO - FK indexes.** Every `ForeignKey` without `db_constraint=False` gets an automatic Postgres index from Django; no missing FK indexes found on hot paths statically. Missing-index claims require `EXPLAIN` on the local DB (not run in discovery).
