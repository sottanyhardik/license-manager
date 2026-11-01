# Decisions required

| ID | Decision | Why blocked | Recommended default | Impact |
| --- | --- | --- | --- | --- |
| D1 | Company/entity isolation policy | Role gates are verified; canonical tests explicitly permit documented legitimate roles to read multiple companies, but end-to-end object/company scoping is not demonstrated. | Treat application as internal multi-company until an owner approves tenant/membership semantics. | P0 security/data visibility |
| D2 | Customs vs Financial balance meaning | Two intentional engines have different debits and outputs. | Retain both named outputs and expose provenance; do not merge. | P0 financial correctness |
| D3 | Restriction/SION pool semantics | Existing free-text percentage grouping and exception paths require domain validation. | Freeze current output with golden datasets pending owner rules. | P0 entitlement correctness |
| D4 | Auth token architecture | JWT localStorage and download-token compatibility have security trade-offs. | Complete protected-media cutover, then approve cookie/CSP posture. | P1 security |
| D5 | Accounting scope | Trade invoices/payments exist; full GL/bank domain not found. | Limit V1 to commercial/accounting evidence until double-entry requirements are approved. | P1 scope |
| D6 | Audit durability requirement | Activity logging uses asynchronous daemon work. | Specify compliance/durability requirement before calling logs authoritative. | P2 auditability |

Each row is **Requires owner approval**. Evidence links are in [financial rules](../04-domain-and-business-rules/financial-rules.md) and [security](../05-target-architecture/security-and-auditability.md).

## Approval briefs

### D1 — company/entity access

Options: (A) formally retain internal multi-company visibility by role; (B) scope selected workflows to company membership; or (C) establish tenant isolation everywhere. Recommendation: A until a business owner supplies membership/tenant rules, because current tested legitimate roles read multiple companies. Consequence: B/C require query, mutation, export, download, job and audit migration plus compatibility tests; they cannot be inferred from a ledger grouping test.

### D2 — balance meaning

Options: expose only Customs, only Financial, or expose both named outputs. Recommendation: retain both named/provenanced outputs; formulas intentionally differ. Consequence: selecting one as a universal replacement without golden reconciliation can change entitlement, allocation or financial presentation.

### D3 — restriction/SION semantics

Options: preserve existing rules, approve a formal policy table, or replace rules after parity. Recommendation: characterize and approve a policy table before replacement. Consequence: shared pools, AU/restriction bases and priority determine available quantity/value; no engineering simplification may choose them silently.

### D4 — authentication/download-token posture

Options: retain localStorage JWT plus scoped query-token compatibility, move to HTTP-only cookies, or retain JWT with CSP/XSS hardening and complete protected-media migration. Recommendation: finish protected-media consumer inventory first, then approve the security trade-off. Consequence: cookie migration changes CSRF/session behavior; premature query-token removal can break downloads.

### D5 — accounting scope

Options: limit V1 to commercial invoice/payment evidence, introduce a double-entry ledger, or add bank matching. Recommendation: limit V1 to evidenced commercial scope unless accounting owners approve chart-of-accounts, posting, periods, reversals and reconciliation rules. Consequence: reports must not be labelled as a general ledger or bank reconciliation without those contracts.

### D6 — audit durability

Options: best-effort activity history or compliance-grade durable audit events. Recommendation: declare the required assurance level. Consequence: compliance-grade audit requires durable delivery/retry/retention/access rules; asynchronous daemon logging alone is insufficient proof.


D1. We don�t need company level access for now remove this from scope and all related code completelely
D2. In this if that license boe has bill then financial is important else boe is important so custom and financial both work together and it can help us better to know pending invoices or additial invoices if made by us like if custom balance is more then financial then we can come to know what additional have we sold and if its less then we come to know which invoice is pending
D3. Recommendation: characterize and approve a policy table before replacement.
D4. Best AI decision 
D5. limit V1 to commercial invoice/payment evidence
D6. best-effort activity history or compliance-grade durable audit events.
