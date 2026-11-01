# Data and migration plan

**Proposed for V1.** Audit-only phase makes no schema/data changes.

1. Freeze migration graph and obtain backup/restore proof in a production-like environment.
2. Inventory schema from migration state plus live schema; reconcile merge migrations and data-migration assumptions.
3. Add constraints/indexes only with duplicate scans, query evidence and backwards-compatible deploy ordering.
4. Backfill additive representations with resumable, logged jobs and dual-read comparison.
5. Reconcile balance/allocation/report outputs against golden datasets and retained exports.
6. Cut over behind explicit compatibility window; retain forward recovery and rollback/restore runbook.

No deletion of models, fields, tables, migrations or records is planned. Proposed source-of-truth changes need data affected, backfill, validation, owner approval and recovery procedure.
