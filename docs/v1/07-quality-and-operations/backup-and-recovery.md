# Backup and recovery

No production backup or restore evidence was observed. The V1 branch and audit preserve source/documentation history; that is not a substitute for data recovery.

## Required recovery contract

| Scenario | Required proof | V1 recovery decision |
| --- | --- | --- |
| Database corruption or failed migration | Encrypted backup restoration to an isolated environment; migration state, counts, constraints, balance/report samples and application health reconciled | Prefer forward recovery for additive migrations; use restore only under a documented outage/data-loss decision. |
| Backfill defect | Batch identifier, before/after row count/checksum, reversible/compensating procedure and retained old representation | Stop/resume safely and preserve correction/reversal history; never delete old financial/allocation evidence during cutover. |
| Worker/broker outage | Ledger package, replan and sync duplicate/retry/recovery drills against durable state | Demonstrate idempotency keys, owner scope and failed/stuck-job operator workflow. |
| File/document loss | Storage backup/restore plus protected-media authorization verification | Confirm restored object integrity and that no unauthorized URL/token bypass emerges. |
| Sync divergence | Peer cursor/event/delivery replay, duplicate/out-of-order and delete-safe verification | Preserve source/event and peer/event uniqueness; recover by replay rather than inventing a new cursor. |
| Bad deployment | Tested artefact rollback and compatible database forward-recovery plan | Do not equate app rollback with schema rollback; every migration specifies one safe path. |

## Acceptance record

The release evidence must name environment, backup timestamp/identifier (without credentials), executor, elapsed time, restored commit/schema state, count/checksum results, critical workflow results, unresolved differences and approving owner. Until such a record exists, recovery is **unverified**.
