# Security, performance and reliability

Measure performance from an isolated/staging baseline before assigning targets. Do not load-test production destructively. Profile reports/exports and high-volume BOE/licence/reconciliation queries; require pagination, bounded exports, query-count monitoring and background jobs for suitable long operations. Security/reliability evidence must cover object/company scope, file handling, secrets/logging, retry/idempotency, broker/task failure, database rollback and recovery.

