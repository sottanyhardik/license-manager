# Data integrity

## Verified preservation invariants

These are **verified by static code/test evidence** and are V1 no-regression candidates, not yet owner-approved data policy:

| Invariant | Evidence | Required migration/reconciliation check |
| --- | --- | --- |
| BOE and allocation corrections affect balances differently from an ordinary delete. | Hidden BOE logic and allocation version/release tests; declared correction/version fields. | Compare old/new customs and financial balance engines for visible, hidden, reversed and restored records. |
| A licence import-item serial is the operational identity within a licence. | Declared unique tuple in `LicenseImportItemsModel`. | Find duplicates/nulls before importing or constraining historical data. |
| Reconciliation allocations are versioned/superseded rather than simply overwritten. | `InvoiceBOEAllocation` / `BOEAllotmentAllocation` source relations and constraints. | Reconcile active allocations and preserve all supersession chains. |
| Sync delivery is idempotent by source/event and peer/event identity. | Sync model uniqueness plus passing sync tests. | Run replay/out-of-order/duplicate tests against backup-restored and migrated copies. |
| Ledger package requests/items use unique/idempotency-oriented identities. | Package job/item constraints and 2,708-test licence/core baseline. | Verify duplicate submission/retry recovery before changing queue, storage or key fields. |
| Audit/activity is not equivalent to an immutable compliance ledger. | Activity logging is asynchronous; domain audit records vary by aggregate. | D6 owner decision must state retention, immutability and recovery requirements. |

## Integrity risks requiring explicit treatment

- There are multiple representations of balance and availability (customs calculation, financial calculation, caches/materialized views and workflow records). Their outputs must be compared, never merged by a generic data cleanup.
- Multiple migration branches/merge migrations exist in licence, allotment and BOE histories. Treat graph topology as a deployment dependency.
- Company references exist across licences, BOEs, allotments, trades and documents, but current authorization is role-oriented. Do not add a tenant FK constraint or backfill company ownership before D1 is approved.
- Hard relational cascades coexist with business correction/reversal models. A technically valid cascade can still violate retention or financial traceability.

## Required validation sequence

1. Take and verify a restorable backup in an approved non-production rehearsal environment.
2. Export live schema and migration graph; compare to model state without applying changes.
3. Produce duplicate/null/orphan reports for each proposed constraint, with a correction policy approved by the data owner.
4. Execute additive/backfill work in resumable batches with row counts, checksums and audit output.
5. Recompute dual balances, allocation capacity, ledger/report outputs and sync identities against golden cases.
6. Retain dual-read/compatibility paths until reconciled results and rollback/forward recovery drills are accepted.

No destructive cleanup, table/field/migration deletion, or balance consolidation is authorized in this audit phase.
