# Complete feature and route inventory

| Module | Current status | Owner workflow | Required outcome | Priority |
|---|---|---|---|---|
| Auth/users | Partial, role-based | Login/admin/user access | tenant/company memberships, capability and audit controls | P0 |
| Masters | Implemented/partial | Reusable company/product/SION data | governed shared/company master policy, validation/dedupe | P1 |
| Licences | Implemented, complex | intake, balance, expiry, documents | canonical traceable balance/lifecycle | P0 |
| Planning/SION | Implemented/partial | rule selection/plan | explicit restrictions, explanation/concurrency safety | P1 |
| Allotments | Implemented | allocation/reversal | idempotent capacity validation/audit | P0 |
| BOEs | Implemented | capture/import/link/transfer | dependency-safe merge/delete/correction | P1 |
| Trades/invoices | Implemented/partial | purchase/sale/invoice/payment | capture-once, duplicate/cancel/reversal safety | P1 |
| Operational reconciliation | Implemented/partial | BOE-invoice triage | trusted candidate queue and remediation | P0 |
| Reports/exports | Implemented/partial | owner review/export | source parity and scoped filters | P1 |
| Accounting/bank | Missing as new domains | financial close/cash control | Option B only | P1 |

Frontend route authority is `frontend/src/routes/AppRoutes.tsx`; discoverable paths include public auth, dashboard, licence/planning, allotment, BOE, trade, reconciliation, incentive, ledger, 11 reports, masters and admin. Runtime status is only confirmed for routes listed in EV-04.
