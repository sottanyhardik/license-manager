# Workflow traceability register

Status definitions follow [requirements-to-code](requirements-to-code.md). “Evidence” identifies a code-owned entry point, not a completed user-acceptance test.

| ID | Workflow | Current entry points / owners | Data and consequential rules | Authorization evidence | Tests / audit status | V1 disposition |
| --- | --- | --- | --- | --- | --- | --- |
| WF-01 | Authentication and user lifecycle | `apps.accounts.urls`, auth/password/user-management views | JWT refresh/revocation; role records | Central role permissions | Canonical suite covers auth/role paths; Partial | KEEP/IMPROVE |
| WF-02 | Licence master and items | `/api/licenses`, `LicenseDetailsViewSet`, licence models/services | Licence/item entitlement, documents, planning links | `LicensePermission` | API and app tests; Partial action contracts | IMPROVE |
| WF-03 | Licence balances and ledgers | balance calculator, ledger viewset/reports | Separate customs/financial engines, 2dp/floor-zero; ledger company grouping | Ledger permission combinations | Calculation/ledger company-isolation scenarios; owner semantics pending | IMPROVE; do not merge |
| WF-04 | Planning and SION rules | item-plan and SION planning routers/services | Plan-line caps, restriction/rule selection | Licence roles | Extensive app tests; policy partial | IMPROVE |
| WF-05 | Allotment allocation/release | allotment and allotment-actions routers | Live CIF, plan isolation, reversal/release | `AllotmentPermission` | Allocation tests; concurrency/recovery mapping partial | IMPROVE |
| WF-06 | BOE/import evidence | bill-of-entries router, parser | Rows, hidden/correction state, licence debit | `BillOfEntryPermission` | API/parser tests; correction matrix partial | IMPROVE |
| WF-07 | Trade, invoices and payments | trade/lines/payments routers | Purchases/sales, invoice/document effects on financial balance | `TradePermission` | API tests; accounting scope partial | IMPROVE |
| WF-08 | BOE/invoice reconciliation | reconciliation router | Links/merges/notes/recalculation | `ReconciliationPermission` | Action inventory complete; scenario contract partial | IMPROVE |
| WF-09 | Reports and exports | report viewsets/direct report paths | Filters, ledger/report formats, protected downloads | `ReportPermission` and per-view rules | Export tests; full consumer matrix partial | IMPROVE |
| WF-10 | Ledger package/download jobs | ledger upload/viewset and Celery jobs | Retry, package readiness, recovery | Ledger permissions | Parser/job tests; idempotency drill partial | IMPROVE |
| WF-11 | Master data and synchronization | `api/masters`, `api/sync`, MDS | Generic CRUD, export, sync conflict/feed | Company/master permissions, service tokens | Isolated CI-equivalent MDS suite passed 25/25; peer lifecycle and action contracts remain Partial | IMPROVE |
| WF-12 | Task management | `/api/tasks` | Complete/reject/reopen/remarks | Task view rules | Registered action evidence; tests partial | KEEP/IMPROVE |
| WF-13 | Activity/audit history | activity-log view, middleware/models | Async logging; durability uncertain | user/admin controls | Partial; durability decision required | IMPROVE |
| WF-14 | Administration/configuration | masters, companies, rates, users, settings | Reference data governs workflows | mixed roles/superuser | Partial policy/CRUD tests | IMPROVE |
| WF-15 | Accounting / bank reconciliation | Trade/reconciliation-adjacent surfaces | Commercial evidence exists; GL/bank model not evidenced | N/A | Requires owner scope decision | UNDECIDED |
| WF-16 | Tenant/SaaS isolation | Cross-domain queries and role system | Current tested policy permits approved multi-company reads | role-based, not proven object-scoped | Owner policy unresolved | UNDECIDED |

## Workflow completion requirement

Each row must be decomposed into route/API-operation IDs, state transitions, input/error/recovery paths, authorization policy, data mutation/transaction boundary, reports/exports, tests and acceptance criteria before implementation. The register prevents a feature-family label from being mistaken for complete workflow coverage.

The consequential backend boundaries, their direct transaction/concurrency
evidence, and their named source tests are now mapped in
[backend-critical-workflow-map.md](backend-critical-workflow-map.md). That
document is a bounded workflow map, not evidence that every API operation or
static symbol has completed action-level tracing; this register remains
`Partial` until the completion requirement above is met.
