# Decision log

| ID | Decision / question | Status | Owner | Evidence / rationale |
|---|---|---|---|---|
| DEC-001 | Rebuild approach is parallel, database-first, modular monolith. | PROPOSED | Business owner / architect | Small-team maintainability; see `restructure-blueprint.md`. |
| DEC-002 | Company model: strict entity ownership versus approved shared masters. | REQUIRED | Business owner | Server-side isolation is not demonstrated. |
| DEC-003 | Restriction/AU source, base, units, pools, dates, override and historical treatment. | REQUIRED | Owner + DFIA adviser | `docs/assessment/DFIA_SION_RESTRICTION_SCOPE.md`. |
| DEC-004 | Canonical licence lifecycle: draft/reserved/posted/released/reversed. | REQUIRED | Owner/domain reviewer | Balance paths diverge in existing evidence. |
| DEC-005 | Accounting scope, CA, opening balance date, periods, tax and cutover policy. | REQUIRED | Owner + CA | No complete GL was found. |
| DEC-006 | Migration cutover: maintenance window or designed delta capture. | REQUIRED | Owner + DevOps | Restore/delta evidence unavailable. |
| DEC-007 | Historical source data correction policy. | REQUIRED | Owner | Candidate reconciliation discrepancies are not automatically defects. |

