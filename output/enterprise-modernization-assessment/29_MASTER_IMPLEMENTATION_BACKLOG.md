# Master implementation backlog

| ID | Epic | Outcome | Priority | Likely days | Dependency |
|---|---|---|---|---:|---|
| LM-001 | Isolation | tenant-scoped service/query/export/job access | P0 | 45 | company policy |
| LM-002 | Calculations | canonical balance/Decimal/report parity | P0 | 65 | golden examples |
| LM-003 | Reconciliation | candidate semantics and remediation queue | P0 | 50 | read-only baseline |
| LM-004 | Restrictions | versioned shared pools/AU/explanation/locking | P1 | 70 | domain decision |
| LM-005 | BOE/trade | safe correction/reversal/dependency preview | P1 | 45 | LM-002 |
| LM-006 | UX/report | owner work queues, lists, export parity | P2 | 85 | LM-002/003 |
| LM-007 | Operations | test/recovery/observability/release | P1 | 67 | test environment |
| LM-101 | Accounting | journals/chart/periods/invariants | P1 | 120 | LM-001/002 + CA |
| LM-102 | Accounting | AR/AP/source posting/bank reconciliation | P1 | 155 | LM-101 |

Every backlog issue needs route/API/model files, tests, migration/rollback and acceptance refinement during Phase 0.
