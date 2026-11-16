# Data Integrity Report — baseline (Phase 1)

Date **2026-11-16** · DB `lmanagement`@localhost (PG 18.7) · all queries ran in READ ONLY transactions.
This is the **"before" baseline** for every later migration. Raw inventory: `/tmp/lm_discovery/`, now copied
into this doc. Balance CSV: `~/lm_backups/balance_baseline_20261116.csv`.

## 1. Structural integrity

| Check | Result |
|---|---|
| Tables / rows | 119 public tables, **743,007 rows**, 290 MB |
| Migration state | 160 applied rows. `makemigrations --check` reports no changes. `showmigrations` shows 0 unapplied. `manage.py check` reports 0 issues |
| Applied vs repo | accounts 6, allotment 16, bill_of_entry 14, core 19, license 56, reconciliation 5, tasks 1, trade 11 (matches repo files). Extra: `license_movement` 1 and `mds_client` 1 (apps not in backend INSTALLED_APPS repo tree, or external) |
| FK constraints | 253, **all validated**, so DB-level referential integrity holds and orphans are impossible on FK columns |
| On-delete at DB level | 248 no-action, 4 set-null, 1 cascade (Django emulates CASCADE in Python; the DB-level picture differs from model `on_delete`, see DATABASE_ARCHITECTURE.md) |
| Check / unique / PK | 88 / 91 / 119, all validated |
| Indexes | 772, **0 invalid** |
| Matviews | `license_balance_mv`, `dashboard_stats_mv`, `item_balance_mv`, all populated |
| Backup restore parity | 0 row or hash mismatches (see BACKUP_AND_RECOVERY.md) |

### Row counts, business tables (before)

| Table | Rows |
|---|---|
| core_activitylog | 334,393 (165 MB, 57% of DB) |
| bill_of_entry_rowdetails | 168,513 |
| license_licenseimportitemsmodel | 26,818 |
| license_licenseimportitemsmodel_items | 23,892 |
| license_licensereplanrequest | 19,312 |
| bill_of_entry_billofentrymodel | 14,392 |
| core_hscodemodel | 13,701 |
| allotment_allotmentitems | 11,561 |
| core_sionimportmodel | 10,720 |
| allotment_allotmentmodel | 6,499 |
| bill_of_entry_billofentrymodel_allotment | 6,394 |
| license_licenseitemplan | 2,528 |
| license_licensetransfermodel | 2,272 |
| license_licensedetailsmodel / _balance / _flags / _ownership / _notes | 2,185 each (1:1 complete) |
| license_licenseexportitemmodel | 2,178 |
| core_companymodel | 1,023 |
| **trade_licensetrade / tradeline** | **0 / 0** |
| **reconciliation_boeallotmentallocation / invoiceboeallocation** | **0 / 0** |

**Consequence:** the local DB has no trades or allocations, so the BILLED-CIF-WITHOUT-BOE term and
allocation-aware BOE exclusion **cannot be exercised on local data**. Migration rehearsal for trade
and reconciliation tables needs a production-like copy, or fixtures (owner decision).

## 2. Uniqueness / duplicate-debit protection (DB level)

| Table | DB uniqueness |
|---|---|
| license_licensedetailsmodel | `UNIQUE(license_number)` |
| license_licenseimportitemsmodel | `UNIQUE(license_id, serial_number)` |
| bill_of_entry_billofentrymodel | `UNIQUE(bill_of_entry_number, bill_of_entry_date)` |
| bill_of_entry_rowdetails | `UNIQUE(bill_of_entry_id, sr_number_id, transaction_type)` |
| allotment_allotmentitems | partial unique on (item, allotment, allocation_basis[, planning_target_item]) |
| trade_licensetrade | partial unique invoice_number per company+direction; counterpart unique; party-status CHECKs |
| **allotment_allotmentmodel** | **none** |
| **license_licenseexportitemmodel** | **none** |
| **license_licensebalance** | **none** (data is clean: exactly one row per licence, see §3) |

## 3. Licence balance reconciliation (before)

All 2,185 licences ran through every `LicenseBalanceCalculator` term with 0 errors.

| Check | Result |
|---|---|
| LicenseBalance rows per licence | exactly 1 for all 2,185 (no duplicates, none missing) |
| `calculate_trade` non-zero | 0 licences (no trade data locally) |
| BOE raw total ≠ allocation-aware debit | 0 licences |
| **Raw balance < 0 (over-utilised), hidden by 0-floor** | **35 licences, total −6,957,414.63 CIF FC** |
| Worst | 0310827509 (−3,447,851.40), 0310833304 (−1,977,787.36), 0310499297 (−453,371.85), 0310836031 (−203,018.37), 0910061510 (−118,303.61) |
| Balance displayed as 0 | 45 (customs) / 45 (financial) |
| **Customs engine ≠ financial engine** | **13 licences**, even though the trade term is 0 everywhere (e.g. 0311052122: 5,427,238.15 vs 2,649,495.02; 0511002494: 768,992.85 vs 204,896.85). Root cause not investigated (read-only phase) |
| **Stored `LicenseBalance.balance_cif` stale vs financial engine** | **3**: 0310834962 (142,937.32 vs 179,688.20), 0511040275 (278,802.32 vs 396,049.96), 3411008581 (0.00 vs 159,370.68) |

### Escalations (not fixed, per `.claude/rules/business-rules.md`)

1. **Negative balances floored at 0.** This violates the stated rule "preserve negative balances / flag over-utilisation". It affects 35 licences and −6.96M CIF FC. Owner decision is already open in `.claude/memory/decisions.md` (2026-11-15).
2. **Two engines disagree on 13 licences** with no billed term present. This needs `cif-balance-auditor` root-cause analysis before any consolidation.
3. **3 stale stored balances.** Refreshing them would overwrite stored values. That is reversible from the baseline CSV, but it is still a write and needs approval.

## 4. Precision consistency

| Column family | Precision |
|---|---|
| licence import/export `cif_fc`, allotment `cif_fc`, `LicenseBalance.balance_cif` | numeric(15,2) |
| **bill_of_entry_rowdetails `cif_fc`/`cif_inr`/`qty`** | **numeric(15,3)** |
| trade line `cif_fc` | numeric(20,2) |
| exchange rates | (12,4) BOE/trade, (15,6) allotment/export |
| quantities | (15,3) mostly; export `net_quantity` (15,2) |

No float columns on these tables. BOE CIF carries 3 dp while every bucket it is subtracted from carries 2 dp.
Widening is safe. Narrowing to 2 dp would **lose data** and must not happen without approval.

## 4a. Live verification of static-analysis risks (DATABASE_ARCHITECTURE.md findings)

| Static finding | Live data today |
|---|---|
| BOE uniqueness bypassable by NULL date | 0 BOEs with NULL date, so the risk is latent and the data is clean |
| BOE numbers repeated | 17 numbers appear under different dates. This is probably legitimate (number series per port/year); domain expert to confirm before any uniqueness change |
| No non-negativity CHECKs on debit tables | 0 negative qty/CIF in allotment items, BOE rows and import items, so a CHECK can be added `NOT VALID` → `VALIDATE` safely |
| BOE CIF at 3 dp | 0 rows use the 3rd decimal, so precision alignment is lossless today (re-check before migrating) |
| Allocation tables lack current-row uniqueness | Tables are empty locally; production needs a duplicate audit first |

## 5. Re-running this baseline

The three read-only scripts used here (inventory, restore parity, balance baseline) are reproduced
inline in the session record. They will be checked in under `scripts/dev/db_integrity/` once Phase 2
tooling is approved, and every migration must re-run them before and after.

## 6. INCIDENT 2026-11-16 ~10:45 IST — live local DB replaced (not by Claude)

- Between the baseline (10:39–10:41) and 10:47 the live `lmanagement` DB was replaced. Rows went from 743,007 to **310,522**, licences from 2,185 to **222**, trades from 0 to **565**, trade lines from 0 to 874, and applied migrations from 160 to 169.
- Matching artefact: `remote_db_backup_20261116_104535.sql`, written at 10:45 by `scripts/database/db-tools.sh` (`download_db` / `sync_db`). `sync_db` asks for an interactive "yes", then wipes and restores local.
- Schema is consistent with the repo: all repo migrations are applied. The 9 extra rows are legacy apps (eScrap 7, ebrc, shipping_bill, license_movement, mds_client).
- **The previous local dataset is preserved**, both in the verified dump `~/lm_backups/local_lmanagement_pre_modernization_20261116.dump` and in the clone DB `lmanagement_restore_verify_20261116`.
- Sections 1–4 describe the **pre-incident** dataset. All balance findings (35 negative licences, 13 engine mismatches, 3 stale balances) refer to it, not to the current live DB.
- Work paused pending owner confirmation of which dataset is authoritative.
