# Risk register

| ID | Priority | Risk | Closure evidence |
| --- | --- | --- | --- |
| R1 | P0 | Wrong consolidation of two balance engines | Approved semantics + golden output comparisons |
| R2 | P0 | Undocumented company/object access policy | Owner decision + negative authorization suite |
| R3 | P0 | Restriction/SION policy inferred from code | Domain approval + accepted examples |
| R4 | P1 | Dynamic DRF actions omitted from inventory | Generated/verified endpoint catalog |
| R5 | P1 | Job retry/recovery regression | Idempotency/recovery tests and operational drill |
| R6 | P1 | Browser/a11y gaps absent from CI | Seeded Playwright/axe smoke gate |
| R7 | P2 | Audit event loss in daemon logging | Approved durability design/test |
| R8 | P1 | OpenAPI has 22 warnings / six warning classes, including ambiguous Ledger operation IDs | Annotate path parameters, resolve operation IDs, regenerate and contract-test schema |
| R9 | P1 | MDS unit test environment was initially blocked by a missing default-local role; isolated CI-equivalent run now passes, but peer/deployment integration is unverified | Preserve disposable CI-equivalent MDS gate; add peer lifecycle and deployment integration drill |
| R10 | P1 | Browser gate currently fails: 51 deterministic navigation/screenshot harness assertions, one unguarded seeded-fixture assertion, and one distinct serious WCAG AA contrast defect reproduced twice | Repair fixture/harness, correct contrast token pairing, then run stratified local/seeded browser suites in CI |
