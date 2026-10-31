# Test coverage and acceptance strategy

Current execution: frontend tests 543/544 PASS, one FAIL; lint FAIL 3 errors/9 warnings; typecheck PASS. No backend integration, data reconciliation, accounting, isolation or real end-to-end workflow was executed.

Build isolated seeded DB/Redis tests first. Required layers: unit golden cases/Decimal/restriction/journal invariants; integration locks/idempotency/reversal/imports; API role x tenant x direct-ID/export negatives; E2E licence->plan->allotment->BOE->trade->operational reconciliation; UI/a11y/responsive; measured reports/import performance; backup/restore/task recovery. Every P0/P1 exit needs recorded PASS evidence and business UAT.
