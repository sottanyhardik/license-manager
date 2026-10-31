# Data retention and deletion policy - proposed approval baseline

| Data class | Default target policy | Rationale |
|---|---|---|
| Licences, entitlement items, BOEs, trades, allocations | Append-only fact/history; correction through linked reversal/amendment | Regulatory/financial traceability and balance reconstruction |
| Planning drafts/reservations | Status lifecycle with retain/archive policy | Preserve decision history while distinguishing non-posted plans |
| Documents | Immutable original with hash, access control and retention classification | File integrity and evidence linkage |
| Users/roles | Deactivate rather than delete where audit references exist | Preserve historical actor context |
| Audit/reconciliation events | Append-only, retention period subject to owner/legal policy | Evidence for corrections and review |
| Calculated snapshots/caches | Regenerable but versioned and reconcilable | Performance without making cache the only truth |
| Accounting journals | Never ordinary-delete after posting; linked reversal | Financial audit trail |

Retention durations, privacy requirements, document-storage region/backup policy and lawful disposal must be approved by the business and advisers; none were verified in this audit.

