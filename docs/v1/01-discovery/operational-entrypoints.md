# Operational entry-point inventory

## Evidence and denominator

**Verified by static source discovery.** The repository contains **73 Django management-command modules** (excluding `__init__.py`) and **11 signal/task modules** across the main backend, master-data service (MDS), and MDS client. They are part of the product’s mutation and integration surface even though they do not appear in OpenAPI.

The purpose/risk column below is deliberately classified from the command name and indexed symbols unless a cited source inspection establishes more. It must not be used as authorization to run a command against a shared database.

## Management commands

| Owner | Commands (all discovered modules) | Initial disposition / V1 control |
| --- | --- | --- |
| Accounts (3) | `check_user_roles`, `migrate_auth`, `repair_user_fk_constraints` | Role inspection/legacy migration/FK repair. **P0/P1 operator-only.** Require dry-run, backup and row-count/constraint proof before a shared environment run. |
| Allotment (3) | `backfill_allocation_status`, `update_exchange_rate`, `update_is_boe` | Backfill/reference-data recalculation. **P1.** Characterize idempotency and balance/allocation effects before scheduling. |
| Core audit/read diagnostics (10) | `audit_database_integrity`, `audit_item_name_merge`, `audit_masters`, `cache_stats`, `check_master_quality`, `diff_masters`, `report_fetch`, `validate_db_fields`, `verify_item_name_merge`, `check_db_structure` | Inspection/report commands; `check_db_structure` has a `_fix_missing_tables` symbol, so it is not automatically read-only. **P1.** Document flags/defaults and make mutation opt-in. |
| Core master import/repair/merge (16) | `auto_import_masters`, `clean_duplicate_rowdetails`, `clean_item_names`, `convert_docx_to_pdf`, `convert_license_table`, `export_masters_mds`, `fetch_detail_bisc`, `fetch_detail_conf`, `fetch_exchange_rates`, `merge_cardamom_item_names`, `merge_item_name_duplicates`, `merge_masters`, `merge_norm_suffixed_item_names`, `seed_e132_plan_items`, `sync_from_ge_server`, `update_aluminium_foil_items` | Imports, transformations, merges, seeds or external fetches. **P0/P1.** No scheduled/production use until inputs, dry-run/rollback, idempotency, source provenance and affected models are recorded. |
| Core platform/migration/cache (10) | `_item_linking`, `clearcache`, `rebuild_migrations`, `reconcile_masters`, `refresh_materialized_views`, `reset_migration_history`, `rqworker`, `sync_database_schema`, `update_dgft_descriptions`, `update_sugar_items` | `_item_linking` is a command base/helper; remaining commands include cache/migration/schema/worker/master change surfaces. **P0/P1.** `rebuild_migrations`, `reset_migration_history`, and `sync_database_schema` require explicit change-control exclusion from ordinary operations. |
| Licence audit/planning (12) | `audit_ledger_orphan_documents`, `audit_license_item_plan_lifecycle`, `audit_restricted_olive_oil`, `compare_all_sion_planners`, `compare_sion_planner`, `link_packaging_items`, `migrate_sion_planners_to_db`, `parse_existing_license_copies`, `plan_norms`, `populate_license_items`, `reconcile_item_pivot`, `reconcile_license` | Audit/reconciliation and consequential planning/import transformations. **P0/P1.** Characterize output/balance effects, SION policy D3 and document/file retention before use. |
| Licence correction/backfill/synchronization (14) | `backfill_parent_actual_targets`, `backfill_planning_actual_targets`, `correct_a3627_active_rules`, `delete_licenses_by_exporter`, `migrate_purchase_status_np_to_mi`, `repair_license_subtables`, `resync_local_to_server`, `seed_browser_2509`, `sync_licenses`, `test_ledger_api`, `update_balance_cif`, `update_license_expiry`, `update_license_ownership`, `upload_dfia_copies` | Includes destructive-looking delete, data correction/backfill, external synchronization, document upload and balance recomputation. **P0.** Require exact selection, backup, dry-run/no-op proof, approval, transaction/batch behavior and forward recovery. `seed_browser_2509` is test/disposable-environment-only by name and indexed guard symbols. |
| Reconciliation (2) | `backfill_boe_allocations`, `check_allocation_health` | Allocation ledger backfill and health audit. **P0/P1.** Existing tests prove some dry-run/idempotency behavior; preserve that as a release gate before any data run. |
| Trade (1) | `backfill_final_party_classifications` | Trade classification migration. **P1.** Define historical classification, undo/forward recovery and finance impact. |
| MDS (1) | `load_masters` | Master load service command. **P1.** Require source-file schema validation, idempotency and service-token/deployment policy. |
| MDS client (1) | `mds_sync` | Mirror synchronization command. **P1.** Require peer token/configuration, cursor/retry and rollback/replay contract. |

**Count reconciliation:** 3 + 3 + 10 + 16 + 10 + 12 + 14 + 2 + 1 + 1 + 1 = **73**. The command denominator comes from `rg --files`, not an inferred estimate.

## Signals and task modules

| Module | Indexed entry points / effect class | V1 audit status |
| --- | --- | --- |
| `apps/accounts/signals.py` | Avatar cleanup on user delete/change | Partial: file-storage deletion/retention and failure behavior need proof. |
| `apps/accounts/tasks.py` | Registered module with no indexed callable symbol | Partial: determine whether intentionally empty/compatibility-only or dynamically registered. |
| `apps/allotment/signals.py` | Updates `is_allotted` on save/delete | Partial: characterize consistency with allocation versions and cache/live balance. |
| `apps/core/sync/signals.py` | Outbox save/delete emission and master signal connection | Partial: P0/P1 idempotency/order/replay contract; core sync tests provide named evidence. |
| `apps/core/sync/tasks.py` | Peer pull, media processing, change push | Partial: peer credential, retry and failure observability need integration drill. |
| `apps/core/tasks.py` | Exchange-rate fetch | Partial: external source/SLA/error policy not verified. |
| `apps/core/tasks_materialized_views.py` | All/licence/item/dashboard materialized-view refresh and health check | Partial: schedule/staleness/alert/fallback contract not verified. |
| `apps/license/signals.py` | Licence flag recalculation, validation guards and replan enqueue/snapshots | Partial: high-consequence balance/planning side effects; map signal trigger/mutation order per workflow before refactor. |
| `apps/license/tasks.py` | Ledger-package processing, replan dispatch/recovery and related tasks | Partial: strongest existing idempotency/recovery test evidence, but worker/storage drill remains open. |
| `master-data-service/masters/signals.py` | MDS master create/update/delete change-feed recording | Partial: 25 MDS unit tests passed; multi-peer/operational replay still unverified. |
| `mds-client/mds_client/tasks.py` | Celery wrapper/sync masters | Partial: 32 mds-client unit tests passed; schedule/worker/integration behavior not verified. |

## Mandatory operator-control contract

Before V1 permits a command/task to run outside a disposable test environment, its record must state: invoking identity/environment, input source and selection, dry-run default, mutation flag, transaction/batch semantics, idempotency/retry, affected models/files/external services, output/audit artifact, authorization, backup/recovery procedure, tests, and rollback/forward-recovery action. This command register provides the denominator, not proof that these controls currently exist.
