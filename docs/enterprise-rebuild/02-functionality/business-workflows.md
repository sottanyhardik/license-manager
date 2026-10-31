# Business workflow inventory - current evidence and rebuild contract

| Workflow | Current evidence | Rebuild compatibility contract | Audit status |
|---|---|---|---|
| Licence management | Licence UI/local screens and backend domain evidenced | Preserve status, validity, items, balance history and reporting links | PARTIAL |
| SION planning / restrictions | Planning screen and separate condition-pool/SION percentage logic evidenced | Versioned norm/rule source, named pools, AU conditions and explainable decision | PARTIAL |
| Allotment/allocation | Allotments screen/domain evidenced | Draft/reservation/post/release/reversal lifecycle; concurrent safety | PARTIAL |
| BOE and trade | BOE/trade screens and domains evidenced | Preserve links, quantities, documents, corrections and downstream impact | PARTIAL |
| Operational reconciliation | Reconciliation screen and metrics evidenced | Candidate semantics, disposition, tolerance and audit trail; no automatic data repair | PARTIAL |
| Reporting/export | Existing reports/export code documented in prior audit | Same approved filters/totals; canonical read model; format parity | PARTIAL |
| User/admin | Authentication and routes evidenced; `/admin/users` route collision observed | Explicit route ownership and server-side company/role checks | PARTIAL |
| Accounting | Invoice/trade payments found; full GL/bank domain not found | New accounting workstream after operational trust gates | PARTIAL |

Each workflow needs a route/API/service/model/test card before code implementation begins.

