# Feature and requirements matrix

| Capability | Current evidence/state | Priority/future acceptance |
|---|---|---|
| Licence, items, balances | Models, balance calculator and licence APIs/routes exist. | P1: golden data, lifecycle and service/report parity. |
| SION plans | Rule/plan models and auto/canonical planning services exist. | P1: single rule contract, explainable preview/commit, concurrency proof. |
| Percentage/AU restrictions | Condition pool and separate SION capacity exist; semantics are split. | P1: explicit groups/versioning/base and audited consumption. |
| Allotment/BOE/trade | CRUD/action APIs and locking exist. | P1: isolation, idempotency, allocation regression suite. |
| BOE/invoice reconciliation | Manual triage/allocation and append-only logs exist. | P2: maintain separately from bank recon. |
| Accounting | Invoices/trade payments only; no GL discovered. | P1: ledger foundation before statements/tax automation. |
| Bank reconciliation | Not discovered. | P1 after GL: import→normalise→match→review→reconcile/audit. |
| Multi-company SaaS | Company records/global roles exist; tenant boundary unproven. | P0 external: tenant isolation/membership/scoping. |
| UI system | React components, routes, tests and design docs exist. | P2: one route manifest; shared data-grid/form/error/a11y primitives. |
| QA/release | Unit/E2E assets exist; execution gaps remain. | P1: isolated seeded E2E + invariant/security gates. |

Acceptance criteria are elaborated in the domain reports; estimates are planning ranges, not delivery commitments.
