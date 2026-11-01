# V1 scope and non-goals

## In scope

- Contract and regression coverage for licences, licence items, BOEs, allotments, planning, trade, reconciliation, reports, document flows, roles and administrative masters.
- Explicit balance/financial ownership, entity-access policy, auditability, durable background processing, data-preserving incremental migrations, and a coherent enterprise UX.
- Performance, security and operational release gates grounded in measured baselines.

## Explicit non-goals unless approved

- Replacing Django, PostgreSQL or the monolith with microservices.
- Declaring tenancy/company isolation, a general ledger, bank reconciliation, or external SaaS scope implemented merely because adjacent concepts exist.
- Deleting legacy models, migrations, documentation or data in the audit phase.
- Wholesale UI rewrite before workflow contracts and risk decisions are settled.

Classification: **Proposed for V1**; current absence of GL/bank domain is **Inferred from static inspection**.
