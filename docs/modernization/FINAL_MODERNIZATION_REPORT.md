# Modernization Report — Phase 1 (Discovery) + Plan

**Status: Phase 1 COMPLETE · Phase 2 local backup DONE and verified · Phases 3–9 NOT STARTED (awaiting owner decisions).**
Date 2026-11-16 · branch `feature/v5` · No application code, migration, or business record was changed.

## 1. Deliverables

| Doc | Content | Author |
|---|---|---|
| `docs/modernization/PROJECT_ARCHITECTURE.md` | Architecture diagram, backend apps, app dependency map + cycles, API, Celery, infra, repo hygiene | discovery agent (backend) |
| `docs/modernization/FRONTEND_STRUCTURE.md` | src tree, routes, API layer, duplicates, target feature structure + migration path | discovery agent (frontend) |
| `docs/modernization/DATABASE_ARCHITECTURE.md` | Per-model schema, constraints, precision, findings | discovery agent (DB, static) |
| `docs/modernization/DATABASE_ER_DIAGRAM.md` | Mermaid ER: overview + 7 domain clusters | discovery agent (DB) |
| `docs/modernization/MIGRATION_REGISTER.md` | Per-app migration history, data migrations, reversibility | discovery agent (DB) |
| `docs/modernization/DATA_INTEGRITY_REPORT.md` | **Live** baseline: row counts, constraints, balance reconciliation | orchestrator (live DB, read-only) |
| `docs/modernization/DATABASE_SAFETY.md` | Env identification, guardrails, legacy tables | orchestrator |
| `docs/modernization/BACKUP_AND_RECOVERY.md` | Verified backup + restore/rollback procedure | orchestrator |

Static docs were written by agents from code. Live-DB facts were verified by the orchestrator. Where they differ, the live facts win.

## 2. Current state in one screen

- **Backend:** 8 Django apps (accounts, allotment, bill_of_entry, core, license, reconciliation, tasks, trade), 82 models (+7 core sync). license and core are hubs with **cyclic imports** (core→license 17 edges, license→core 122). There is no selectors layer. About 24 files exceed 800 LOC (license/models/core.py 2625, item_pivot_report.py 2400, balance_calculator.py 2149). settings.py is a single 620-line file. There is no API versioning.
- **Frontend:** 326 TS + 33 JS files, a single axios instance (110 dependents), TanStack Query used in only 32 files, `strict:false`, and duplicate components (StatCard, error boundaries, 4 async-selects, 3 filter components).
- **DB (live):** PG 18.7 local, 290 MB, 119 tables, 743k rows, 253 FKs all validated, 0 invalid indexes, migrations consistent (no drift, 0 unapplied).
- **Repo hygiene:** 258 tracked root-level report `.md` files, 35 ad-hoc scripts, 217 MB of licence PDFs tracked (`backend/DFIA_COPY`), 5 near-duplicate nginx confs, triplicated Celery process definitions.

## 3. Critical findings (ranked)

| # | Finding | Evidence | Class |
|---|---|---|---|
| 1 | **Negative balances floored at 0**: 35 licences over-utilised by −6.96M CIF FC are shown as 0 | DATA_INTEGRITY_REPORT §3 | BUSINESS-RULE (owner decision open since 2026-11-15) |
| 2 | **Customs vs financial engine disagree on 13 licences** with no trade data | §3 | BUSINESS-RULE, needs root cause |
| 3 | 3 stale stored `LicenseBalance` values | §3 | data refresh = write, needs approval |
| 4 | No current-row uniqueness on allocation tables (duplicate-debit risk) | reconciliation/models.py:226,331,434 | schema (expand-only) |
| 5 | CASCADE on financial history rows (BOE rows, allotment items, invoices, trade lines) | DATABASE_ARCHITECTURE findings | schema (PROTECT; no DDL) |
| 6 | No DB non-negativity CHECKs on debit tables (data clean today) | §4a | schema (NOT VALID → VALIDATE) |
| 7 | CIF precision mismatch: BOE 15,3 vs licence/allotment 15,2 vs trade 20,2 | §4 | schema, behaviour-sensitive |
| 8 | Legacy unowned tables with data + FKs into live tables (eScrap/ebrc/shipping_bill, auth_user) | DATABASE_SAFETY §4 | never drop without approval |
| 9 | Local DB has **0 trades / 0 allocations**, so billed-CIF term untestable locally | §1 | blocks Phase 6 rehearsal for trade/reconciliation |
| 10 | Celery beat entries that may point to non-existent tasks; `ledger` queue with no routes | PROJECT_ARCHITECTURE §Celery | runtime behaviour |
| 11 | JWT accepted via query param (log leakage) | core.authentication | security |
| 12 | `core_activitylog` = 57% of DB (334k rows), no retention | row counts | ops/perf |

## 4. Modernization plan (expand-and-contract, gated)

Each wave runs: verified dump, rehearsal on `lmanagement_restore_verify_20261116`, before/after integrity scripts (row counts, PK sets, FK validity, balance-baseline CSV diff = 0), tests, review, then owner sign-off.

| Wave | Scope | Risk | Needs approval? |
|---|---|---|---|
| **0 Tooling** | Check in the read-only integrity/baseline scripts (`scripts/dev/db_integrity/`) and add characterization tests for both balance engines pinned to the baseline | none | no |
| **1 Hygiene (no runtime change)** | Move root reports to `docs/archive/`, stray scripts to `scripts/adhoc/`, untrack `.DS_Store`/`models.png`; consolidate nginx/Celery configs into documented templates; fix MDS doc contradiction | low | yes (large file moves, user-visible) |
| **2 Safe schema hardening** | `on_delete` CASCADE→PROTECT on financial history (state-only), non-negativity CHECKs `NOT VALID`→`VALIDATE`, partial unique on `is_current` allocation rows (after duplicate audit), drop duplicate indexes only after usage check | low-med | yes (schema change; index drops) |
| **3 Business-rule decisions** | Negative-balance floor; engine divergence (13 licences); stored-balance refresh; CIF precision policy | **high** | **owner decision required** |
| **4 Backend structure** | Break core↔license cycle; add `selectors/` + service layer per app; split >800-LOC modules behind re-exporting `__init__`s; settings split. Imports and API contracts are preserved. No app renames or table renames (the target domain list maps onto existing apps; no new apps until an ADR) | med | per-PR review |
| **5 Frontend structure** | Plan in FRONTEND_STRUCTURE §8: aliases + re-export stubs, leaf features first, typed API wrappers, route modularisation, de-duplication, per-feature `strict` | med | per-PR review |
| **6 Ops** | Production backup/PITR, activitylog retention (archive, not delete), Celery beat/queue fixes, docker-compose PG 16→18 parity | med | yes (prod/infra) |

The target domain list in the brief (companies, customers, imports, exports, accounting, planning, notifications, integrations, …) is **not** mapped to new Django apps. Creating apps means moving models, which means table renames or `db_table` pinning plus migration-history surgery. That risk is disproportionate, so the domains are realised as packages inside the existing apps unless an ADR approves otherwise.

## 5. Owner decisions needed before Waves 2–6

1. Negative balances: keep the floor, or expose negatives plus an over-utilisation flag? (affects 35 licences / API values)
2. Should 13 customs≠financial divergences be root-caused now (read-only `cif-balance-auditor` task)?
3. Refresh 3 stale `LicenseBalance` rows (reversible from baseline CSV)?
4. Can a sanitised production-like copy (with trades/allocations) be provided for rehearsal?
5. Approve Wave 1 file moves and Wave 2 schema hardening?
6. Legacy tables (eScrap/ebrc/shipping_bill/auth_user): keep as-is (default), or archive to a separate schema?
7. Provenance and retention of `~/lm_backups/remote_db_backup_20261115_*.sql` (possible production data on a laptop).

## 6. Acceptance criteria status (Phase 9)

Records preserved ✅ (nothing written) · Backup restoration verified ✅ (local) · Migration state consistent ✅ ·
FK integrity ✅ · Balances reconcile ❌ (findings 1–3, pre-existing) · Tests/typecheck/build: NOT RUN (no code changed).
