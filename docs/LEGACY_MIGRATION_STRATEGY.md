# License Manager — Legacy Archive & New Implementation Strategy

**Status:** Approved direction; execution gated  
**Created:** 2026-11-14  
**Baseline branch:** develop  
**Migration branch:** legacy/archive-baseline-2026-11-14

## 1. Objective

Retire the current License Manager implementation as the active development target, preserve it as a read-only legacy reference, and build the replacement implementation in a controlled new structure.

The existing PostgreSQL database and all historical business records remain authoritative throughout the migration. This is an application/code migration, **not** a database reset or data migration by default.

## 2. Non-negotiable safeguards

1. Never drop, truncate, recreate, or bulk-reseed production or historical tables.
2. Preserve every existing primary key, foreign key, relationship, document reference, audit record, and transaction history.
3. Do not run destructive or irreversible migrations without a separately reviewed migration plan, verified backup, and explicit approval.
4. Do not change production deployment, DNS, routing, or worker entrypoints during the archive preparation phase.
5. Do not delete existing tests to make the new baseline pass. Keep legacy tests and record their status.
6. Do not overwrite or discard uncommitted local work. Inspect and safely preserve the local working tree before any file move.
7. Do not make the new implementation write to production data until read-only parity and reconciliation checks pass.
8. All financial/CIF calculations use decimal-safe arithmetic; never use binary floating point for money or entitlement quantities.

## 3. Branch and archive policy

- Keep develop unchanged as the pre-migration reference until the migration PR is reviewed.
- Work only on legacy/archive-baseline-2026-11-14 for migration preparation.
- Before moving source files, create a dated, immutable Git tag for the exact source commit and record the commit SHA in the migration log.
- Preserve original Git history. Use Git moves/renames from a local clone (not delete-and-recreate through a web API).
- The legacy snapshot must include application source, migrations, tests, configuration examples, operational scripts, and documentation needed to understand or restore the old system. Exclude secrets, credentials, production data dumps, virtual environments, caches, and generated build artifacts.
- Keep a legacy runbook explaining how to inspect the old code and restore the old deployment.
- Do not physically relocate Django apps or migration modules until import paths, Django app labels, migration discovery, task registration, management commands, and deployment entrypoints have been mapped. Moving Django packages blindly can break migration history and installed-app loading.

## 4. Database preservation and ownership

### 4.1 Existing database remains authoritative

The replacement must initially connect to the existing database using a least-privilege account. Its first database milestone is **read-only**.

Before any environment is pointed at the existing database:
- identify the exact database and environment;
- capture schema/table inventory and row counts for critical tables;
- capture migration state (django_migrations) and installed app labels;
- verify backup completion and perform a restore test in a non-production environment;
- record database version, extensions, collation, timezone, and relevant constraints/indexes.

### 4.2 One schema owner

There must be one canonical owner for each existing table and its migration history. Do not create a second set of Django models that independently claims the same tables.

The initial replacement should consume existing data through a clearly defined compatibility/data-access boundary. If ORM models are reused, import them from one canonical Django app/package. If a new service needs unmanaged mappings, document that explicitly and keep schema migrations owned by the original app until an approved ownership-transfer plan exists.

No table rename, app-label change, primary-key conversion, or schema rewrite is part of the initial archive step.

### 4.3 Data validation

For each migrated feature, compare old and new read results using:
- total row counts and grouped counts;
- primary-key coverage and orphan checks;
- key business totals and status distributions;
- document/file reference coverage;
- audit/history completeness;
- representative record-level comparisons.

Any unexplained mismatch blocks cutover.

## 5. Target repository layout (proposed)

This is a target direction, not permission to move files before the dependency inventory is complete:

    /
    ├── legacy/
    │   └── current-license-manager/   # frozen source snapshot; history retained
    ├── apps/                          # new application modules
    ├── backend/                       # new Django project/configuration
    ├── frontend/                      # new React application
    ├── docs/
    │   ├── legacy/                    # old-system map and restore runbook
    │   └── migration/                 # decisions, evidence, parity reports
    └── infra/                         # reviewed deployment/configuration

The final layout must be reconciled with the actual repository tree before implementation. Do not duplicate or relocate existing directories based on this illustrative layout alone.

## 6. Migration phases and exit gates

### Phase 0 — Protect and baseline
- Confirm the migration branch is based on the intended develop commit.
- Inspect local git status; preserve all uncommitted work and running test output.
- Capture source commit SHA and create an immutable archive tag.
- Verify database backup and restore in a non-production environment.
- Record backend/frontend test, lint, type-check, and build baselines without running conflicting duplicate suites.

**Exit gate:** source baseline, local changes, test state, database identity, backup, and restore evidence are recorded.

### Phase 1 — Legacy discovery and archive manifest
- Inventory all tracked files and classify runtime code, migrations, tests, configuration, scripts, generated assets, and secrets.
- Map Django apps, app labels, model/table ownership, migration dependencies, signals, tasks, API routes, permissions, and management commands.
- Map React routes, API clients, feature modules, shared components, and build/deployment entrypoints.
- Generate a dependency/import map and identify code that cannot be moved without compatibility shims.
- Create docs/legacy documentation and an archive manifest.

**Exit gate:** every production entrypoint and database-owned app is accounted for; no unknown migration or runtime dependency remains.

### Phase 2 — Establish the replacement shell
- Create a separately bootable new backend/frontend shell with independent settings and health checks.
- Keep the existing application deployable and recoverable.
- Connect the replacement to a sanitized/staging copy of the existing database first.
- Start with read-only data access; no write paths or schema migrations.
- Establish error logging, request IDs, audit logging, configuration validation, and CI checks.

**Exit gate:** new shell boots independently and reads a staging copy without modifying its schema or records.

### Phase 3 — Feature-by-feature rebuild
Implement one bounded feature at a time. For each feature:
1. Document current behavior and source-of-truth tables.
2. Define acceptance criteria and API/data contracts.
3. Implement the smallest reusable solution.
4. Add unit, API, integration, and UI tests as applicable.
5. Run parity comparisons against legacy behavior and historical data.
6. Update docs/IMPLEMENTATION_STATUS.md and migration evidence.
7. Mark COMPLETE only when acceptance criteria and tests pass.

Recommended order:
1. Authentication, users, permissions, and application shell.
2. Customer/master data and licence read views.
3. Licence create/edit and item-link workflows.
4. Allotments and reservation balances.
5. BOE import, mapping, and reconciliation.
6. Invoice import, matching, and billed-CIF-without-BOE logic.
7. Trade pairing, unpairing, and audit history.
8. SION/item summaries and reports.
9. Planning/allocation workbench.
10. Canonical balance engine and dashboards.
11. Exports, PDFs, alerts, admin, and operational tooling.

Do not parallelize dependent financial workflows before their shared contracts are stable.

### Phase 4 — Shadow validation
- Run the replacement in read-only shadow mode against a staging replica or approved read replica.
- Compare feature outputs, counts, balances, and exception lists.
- Validate representative historical records and known edge cases.
- Reconcile all differences; document accepted differences with explicit business approval.

**Exit gate:** all critical data and financial parity checks pass; no unexplained discrepancy remains.

### Phase 5 — Controlled write enablement and cutover
- Define the write freeze/maintenance window and rollback owner.
- Take and verify a final backup.
- Enable writes only after transaction, concurrency, idempotency, audit, and rollback tests pass.
- Use a controlled cutover (feature flag or routing switch) with monitoring.
- Keep the legacy system and its data intact and available for rollback until the agreed stabilization period ends.
- Never run both systems as independent writers to the same records unless a tested ownership/locking strategy explicitly permits it.

**Exit gate:** business owner signs off, monitoring is healthy, reconciliation is clean, and rollback remains viable.

### Phase 6 — Retire legacy runtime
- Disable legacy writes and scheduled jobs only after cutover acceptance.
- Preserve the archived source, migrations, test evidence, deployment instructions, and restore runbook.
- Remove obsolete runtime infrastructure only after retention and rollback requirements are met.
- Do not delete historical database tables as part of code retirement.

## 7. Canonical licence balance rules to preserve

The replacement must retain the approved business semantics:

- Available CIF = Original CIF − Utilised CIF.
- Utilised CIF = BOE CIF + outstanding CIF reservation against allotments (excluding BOE-represented amounts) + billed CIF without BOE (excluding duplicates).
- Show each component separately.
- Show negative balances and flag over-utilisation; do not silently clamp values to zero.
- BOE CIF comes from BOE transactions.
- Billed CIF without BOE means invoiced CIF not yet represented by a BOE, excluding duplicates.

These rules must be covered by explicit examples and regression tests before balance-engine cutover.

## 8. Known migration risks

- Django app relocation can change import paths, migration discovery, app labels, and content types.
- Existing migrations may import application code or depend on historical module paths.
- Background Celery tasks, scheduled jobs, signals, and management commands may be missed by a UI-only inventory.
- New and old writers can create lost updates or double utilisation if both write concurrently.
- Existing historical data may contain duplicates, orphan references, inconsistent units, or legacy business exceptions. Preserve and report them; do not silently normalize or delete them during archive.
- Current test-monitor output and uncommitted local changes may exist outside GitHub and must be captured locally before source moves.

## 9. Immediate execution checklist

- [ ] Confirm this branch and baseline commit locally.
- [ ] Capture current local Git status and preserve uncommitted work.
- [ ] Collect the running backend test monitor's final result; do not start a duplicate suite while it is active.
- [ ] Verify database backup and restore in staging.
- [ ] Build the full tracked-file and runtime-entrypoint manifest.
- [ ] Build Django app/model/table/migration ownership map.
- [ ] Build frontend route/API dependency map.
- [ ] Resolve the SAMPLE_PDF_DATA test fixture collection issue without deleting tests.
- [ ] Resolve AllocationStrategyEditor against the actual backend payload contract.
- [ ] Keep the active/expiring licence export fix and its regression tests.
- [ ] Do not move source directories until Phase 1 exit gate passes.

## 10. Execution boundary

This document records the approved archive-first strategy. Creating the migration branch and this plan does **not** mean source files have been moved, a database has been backed up, tests have run, or production has changed. Those actions require the local repository, database environment, and test-monitor evidence to be inspected directly.
