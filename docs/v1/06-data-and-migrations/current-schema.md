# Current schema

## What is verified

**Verified by static source inspection, not by a live database.** The model/migration inventory contains 127 migration modules and the concrete entity families listed in [data-model inventory](../01-discovery/data-model-inventory.md). `manage.py makemigrations --check --dry-run` passed at the V1 baseline, which proves no currently detected model-state change needs a new migration; it does **not** prove that a target database has applied the graph or matches its physical schema.

## High-consequence declared constraints and lifecycle rules

| Area | Source-declared evidence | V1 consequence |
| --- | --- | --- |
| BOE identity | BOE number/date is `unique_together`; row identity is BOE/import-item/transaction-type `unique_together` (`apps/bill_of_entry/models.py:234`, `:427`). | Duplicate repair migrations already exist. Capture duplicate and null cases before changing/importing data. |
| Licence item identity | Import item `(license, serial_number)` is unique (`apps/license/models/core.py:940`). | Use this identity in BOE/allotment/reconciliation backfills rather than display names. |
| Ledger package | Package item has unique `(job, license)` and job/status/request indexes (`apps/license/models/core.py:2539`). | Idempotency and retry recovery depend on retaining these keys. |
| Sync durability | Inbox source/event and peer/event delivery uniqueness are declared (`apps/core/sync/models.py:140`, `:159`). | Do not bulk-copy or restore sync rows without preserving deduplication identity. |
| Reconciliation lineage | Both allocation models have constraints/indexes and a `superseded_by` relation (`apps/reconciliation/models.py:307`, `:410`). | A migration must preserve current-versus-historical semantics and reconcile derived balances. |
| Allocation lineage | Allotment items have declared constraints/indexes and predecessor/version/audit links (`apps/allotment/models/core.py:335`; `allocation_version.py:37`). | Concurrency and release/reversal history require characterization tests before structural work. |
| Financial validation | Licence invoices/items and trade entities declare constraints (`apps/license/models/invoice.py:153`, `:240`; `apps/trade/models.py:302`). | Confirm deployed checks and historical bad-data population before hardening. |

## Explicit non-claims

The audit has not connected to, queried, modified, or inferred a production database. It therefore does not claim current table sizes, physical index definitions, constraint validity, applied migration state, collation, row-quality, backup viability, materialized-view freshness, or whether data migrations can replay safely. These must be measured in a production-like controlled environment under the migration readiness gate.

## Required live-schema record

For each concrete model/table, the future schema evidence must include:

1. Django migration graph and `showmigrations` state.
2. `information_schema`/catalog export for columns, types, nullability, default, FK action, checks, unique constraints and indexes.
3. Counts of rows, null/duplicate/orphan candidates for every proposed constraint.
4. Ownership, retention, source-of-truth classification and dependent report/export/job fields.
5. Backup identifier, restoration rehearsal and post-restore integrity checks.

Until that record exists, all schema recommendations remain proposed rather than approved DDL.
