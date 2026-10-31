# Confirmed bug and risk register

| ID | Priority | Classification | Evidence / affected workflow | Required action |
|---|---|---|---|---|
| R-01 | P0 | CONFIRMED display + unverified meaning | 1,699 duplicate-debit candidates in Reconciliation | Baseline/export/classify candidates before correction. |
| R-02 | P0 | CONFIRMED static | Unscoped/global company role risk | Tenant/membership and scoped reads/writes/exports/jobs. |
| R-03 | P1 | CONFIRMED static | Restriction free-text grouping / split systems | Versioned canonical restriction resolver. |
| R-04 | P1 | CONFIRMED display | 2 matches against displayed BOE/invoice totals | Reproduce query semantics; prioritised reconciliation queue. |
| R-05 | P1 | CONFIRMED display | 109 Missing DGFT alert | Required field definition and remediation queue. |
| R-06 | P1 | CONFIRMED static | No GL/bank model despite invoices/payments | Do not call it accounting; Option B foundation. |
| R-07 | P2 | CONFIRMED | stale frontend test/lint errors | Fix after API contract decision; clean release gate. |
| R-08 | P2 | CONFIRMED live | Dense opaque filters/text defects and unavailable planning metadata | UX standardisation and data quality repair. |
