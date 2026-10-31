# Option A implementation roadmap

| Phase | Objective | Likely days | Exit gate |
|---|---|---:|---|
| 0 | Evidence confirmation, test harness, metric semantics | 18 | Baseline/decisions approved. |
| 1 | Company scoping, destructive-action containment, P0 tests | 45 | Negative access and recovery tests pass. |
| 2 | Canonical balances/rounding/report parity | 65 | Golden examples agree across UI/API/export. |
| 3 | Versioned restrictions and concurrency-safe planning | 70 | Shared pools cannot overspend. |
| 4 | BOE/invoice/transfer hardening and remediation queues | 95 | Corrections have dependency/audit/reversal paths. |
| 5 | Owner dashboard, reporting and UX foundation | 85 | Owner UAT completes daily/month-end scenarios. |
| 6 | Security/performance/restore/UAT/release | 67 | Staging release gate and rollback drill pass. |

Do not combine tenant backfill, restriction redesign and financial calculation migration in a single release.
