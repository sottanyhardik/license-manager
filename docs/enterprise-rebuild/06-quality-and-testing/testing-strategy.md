# Testing strategy

Existing confirmed local baseline: frontend tests 543/544 passed, one AllocationStrategyEditor failure; lint had 3 errors/9 warnings; typecheck passed. Backend execution, migration checks, performance, production and recovery tests are unknown.

The release suite requires unit/service/API/UI/E2E tests, independently approved calculation examples, company/permission negatives, concurrency/idempotency, failure injection, import/export/report parity, accounting invariants, migration reconciliation and restore/rollback rehearsal. Tests do not pass merely because they run; each critical rule needs independent expected outcomes.

