# Rebuild quality strategy

## Existing execution baseline

- Frontend tests: 543/544 passed; one `AllocationStrategyEditor` failure.
- Lint: 3 errors and 9 warnings.
- Typecheck: passed.
- Backend test/coverage/migration/restore results: unknown.

## Required release evidence

1. Golden calculations independently approved for entitlement, units, restriction pools, AU, allocation and reversals.
2. API tenant/role/direct-ID/export/job denial tests.
3. Concurrency and idempotency tests for allocation and posting.
4. Legacy/new compatibility scenarios in isolated data.
5. Screen/API/Excel/PDF parity tests.
6. Accounting invariant tests once accounting begins.
7. Failure injection for database, broker, uploads and imports.
8. Backup restore, migration dry run, cutover and rollback/delta recovery rehearsal.

No release passes with unresolved critical/high security blockers, failing required tests, unexplained material reconciliation differences or unapproved exceptions.

