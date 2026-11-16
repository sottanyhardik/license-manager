# Migration Register (Phase 1 discovery, static analysis only)

**Applied state vs. DB is NOT verified** (no DB access in discovery; `showmigrations`/`django_migrations` not consulted). Everything below is derived from migration files in `backend/apps/<app>/migrations/` via AST/regex scan. `AlterField` narrowing was not exhaustively classified (see section at end).

Squash status: **no migration in any scanned app declares `replaces`; no squashed migrations exist** (license has 56 live files). Merge migrations are those with >1 same-app dependency.

| App | Files | Latest | Merge migrations | Notes |
|---|---|---|---|---|
| accounts | 6 | `0006_repoint_legacy_user_fks` | none | deps: core.0001 |
| allotment | 16 | `0015_plan_identity_to_business_dimensions` | `0010_merge_20260818_2005` (two `0009_*` leaves) | duplicate number 0009 |
| bill_of_entry | 14 | `0013_repair_boe_number_date_unique_constraint_columns` | `0011_merge_20260818_2005` | duplicate number 0009 |
| core | 19 | `0019_increase_natural_key_length_to_2000` | none (many `0006-0016` are data steps, linear) | |
| license | 56 | `0056_add_cif_restriction_percentage` | none by AST | heaviest data-migration load |
| reconciliation | 5 | `0005_alter_reconciliationlog_action` | none | schema-only |
| tasks | 1 | `0001_initial` | none | |
| trade | 11 | `0011_tradepairaudit_survive_trade_delete` | none | |
| masters (MDS) | 1 | `master-data-service/masters/migrations/0001_initial` | none | separate service/DB |

## Cross-app dependencies (migration graph; note cycles resolved by `*_initial` / `0002_initial` splits)
- accounts -> core.0001
- core -> license.0005 + bill_of_entry.0002 (`0003_create_materialized_views`); core `0014/0015/0016` -> license, bill_of_entry, allotment (data merges across apps)
- license -> bill_of_entry.0001, core (0002,0003,0011,0012), allotment (0014), accounts.0001 (0008), trade.0009 (0053)
- bill_of_entry -> allotment.0001, core.0001/0011/0016, license.0001/0014
- allotment -> core.0001/0011/0016, license.0001/0017
- reconciliation -> allotment.0003, bill_of_entry.0003, license.0014, trade.0003
- trade -> bill_of_entry.0001, core.0001/0012, license.0001
- Cycles: core<->license, license<->bill_of_entry, license<->trade (resolved only through ordering; a squash would need care). Allotment/BOE/license data migrations reference `core.0016` and `bill_of_entry.0008/0009`, `allotment.0008/0009`.

## Data migrations (RunPython / RunSQL)
Legend: **R** = real reverse function; **noop** = reverse is `RunPython.noop` / noop function (migration unapplies but data changes are NOT undone); **IRREV-DEL** = forward deletes rows, noop reverse (effectively irreversible).

### accounts
- `0006_repoint_legacy_user_fks` RunPython; reverse noop (documented in file: re-pointing back would reintroduce the bug). Touches FK constraints only.

### allotment
- `0009_allotment_parent_planning_target` RunPython `promote_detail_targets` - noop
- `0015_plan_identity_to_business_dimensions` (**atomic=False**): `copy_plan_dimensions` noop; `consolidate_master_rows` **IRREV-DEL** (sums qty/cif of duplicate AllotmentItems into keeper and deletes the others, `:43`). **Human approval required before running on real data.**

### bill_of_entry
- `0009_billofentry_parent_planning_target` `promote_detail_targets` - noop
- `0012_repair_boe_number_date_unique_constraint` `repair_constraint` / `reverse_repair_constraint` - **R** (alters unique constraint only; docstring: no data changed; fails if conflicting BOEs)
- `0013_repair_boe_number_date_unique_constraint_columns` `repair_constraint` - noop reverse

### core
- `0002_remove_companymodel_address` `backfill_address_line_1` - R (noop_reverse function), followed by RemoveField
- `0003_create_materialized_views` `_create_views` / `_drop_views` - **R** (creates `license_balance_mv`, `item_balance_mv`, `dashboard_stats_mv`)
- `0004_headsionnormsmodel_created_on_and_more` `backfill_modified_on` - noop
- `0006_backfill_master_uids` backfill/unbackfill - R
- `0007`/`0008`/`0009_seed_e132_*`, `0010_sync_e132_display_order`, `0011_split_milk_into_swp_dwp_wpc` seed/unseed pairs - R (seed data in masters)
- `0013_item_name_multi_norms` populate/reverse_populate - R
- `0014_merge_norm_suffixed_item_names` forward/reverse - reverse function present but deletes duplicate ItemNameModel (`:79,85`) after repointing FKs across license/BOE/allotment: treat as **IRREV-DEL** unless reverse proven
- `0015_normalize_single_norm_and_common_item_names` - noop reverse, **IRREV-DEL** (`:57-62`)
- `0016_merge_numbered_norm_suffixed_item_names` - noop reverse, **IRREV-DEL** (`:49-54`)
- `0017_hash_sync_peer_credentials` `hash_existing_peer_credentials` - noop (one-way hashing; irreversible by nature)

### license
- `0002_scheme_and_notification_to_fk` (atomic=False) `populate_and_backfill` - R (noop_reverse fn) + RemoveField x2 + RenameField x2
- `0005_licensebalance_licenseflags_licensenotes_and_more` (atomic=False): `copy_and_verify` (noop_reverse fn), RunSQL (reverse_sql present); RemoveField x18 moving columns from `LicenseDetailsModel` to 1:1 child tables
- `0006_drop_obsolete_scheme_notification_columns`, `0007_drop_obsolete_subtable_columns` RunSQL (reverse_sql present; DROP COLUMN-style, data of dropped columns not restorable)
- `0008_repoint_user_fk_to_accounts_user` RunSQL (reverse_sql present)
- `0014_backfill_licenseitemplan_baseline_used`, `0016_backfill_licenseitemplan_remaining_balance` - noop_reverse (backfills balance-cache columns; CIF-sensitive)
- `0019_sion_rule_priority_and_provenance`, `0023`, `0024`, `0025`, `0036`, `0046`, `0047`, `0048`, `0049`, `0054` - noop reverse (rule/profile/replan-state data)
- `0029_populate_sion_input_aliases`, `0030_populate_rule_types`, `0033_backfill_strategy_field` - R (pairs)
- `0037_backfill_actual_usage_planning_targets` - R pair; `0038`, `0041`, `0042` actual-usage target mapping on BOE/Allotment - noop
- `0039_merge_approved_planning_item_aliases`, `0040_merge_explicit_planning_item_aliases_v2` - noop, **IRREV-DEL** (delete merged ItemNameModel `:49`, `:72`)
- `0052_license_ledger_server_ready_states` RunSQL x2 (positional reverse SQL present; status completed<->server_ready)

### reconciliation
- none (schema-only; `AlterField` x4 on log `action` choices - choices-only, no DDL)

### tasks
- none

### trade
- `0003_licensetrade_boe_to_boes_m2m` `copy_boe_fk_to_boes_m2m` / `copy_boes_m2m_to_boe_fk` - **R**; followed by RemoveField of the old FK (lossy on reverse if a trade has >1 BOE)
- `0007_licensetrade_final_party_classification` `classify_known_intermediate_sales` - noop
- `0008_final_party_vocabulary_provenance_constraints` (atomic=False) `migrate_vocabulary` - noop
- `0011_tradepairaudit_survive_trade_delete` `backfill_trade_ids` - noop

## Destructive operations (RemoveField / DeleteModel / Rename / AlterField)
- DeleteModel: **none found** in scanned apps.
- RemoveField: accounts `0004_remove_user_company` (x1); allotment `0011_remove_allotmentitems_planning_mapping_fields` (x3); bill_of_entry `0005` (x6 incl. index entries), `0009_remove_rowdetails_planning_mapping_source_and_more` (x3); core `0002` (x1, after backfill); license `0002` (x2 + 2 RenameField), `0005` (x18, copy_and_verify first), `0032_rename_output_item_to_import_item` (x1); trade `0003` (x1, after M2M copy).
- RenameField: license `0002` (x2). RenameModel/AlterModelTable: none.
- RunSQL drops: license `0006`, `0007` (obsolete columns).
- AlterField counts (not individually classified for narrowing): accounts 0002; allotment 0003 (x2), 0004 (x3), 0008; BOE 0006 (x2), 0008, 0010; core 0017, 0019 (key length widened to 2000 = widening); license 0002, 0004, 0010, 0011 (x13, "harden invoice validation" - **needs review for narrowing/validators**), 0017, 0022, 0031 (x4), 0046, 0047, 0052 (x2), 0053, 0054, 0055 (x3 index renames); reconciliation 0002-0005; trade 0002, 0008-0011.
  Action for Phase 2: diff `max_digits/decimal_places/max_length` per AlterField to classify narrowing (not done here).

## Other observations
- Duplicate-number leaves in allotment/BOE (0009) were healed by merge migrations dated `20260818_2005`.
- Non-atomic migrations (`atomic = False`): allotment 0015, license 0002/0005, trade 0008 (plus any CONCURRENTLY usage not grepped).
- BOE `0012/0013` are "repair" migrations (state vs physical constraint drift) - evidence environments have diverged; verify with `showmigrations` + constraint inspection on local DB only in a later phase.
- License migration chain relies on data migrations importing model state; none were executed here.
