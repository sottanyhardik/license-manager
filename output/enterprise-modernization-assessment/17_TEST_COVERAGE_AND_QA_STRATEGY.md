# Test coverage and QA strategy

Existing execution: frontend 543/544 tests pass; lint fails; typecheck passes. Require isolated seeded DB/Redis: golden calculations; locks/idempotency/reversal; API tenant/role/direct-ID/export negatives; E2E operating flow; a11y/mobile; import/report parity; performance; backup/restore and task recovery.
