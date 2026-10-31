# Test coverage and verification

## Inventory (file counts, not coverage)

- 251 backend test files; 78 frontend unit test files; 13 Playwright specs; 2 Python E2E files (discovery counts vary from broad file searches; neither is a coverage metric).

## Commands actually executed on 2026-10-31

| Command | Result | Evidence |
|---|---|---|
| `cd frontend && npm test -- --reporter=verbose` | **FAIL** | 77/78 files, 543/544 tests passed; `AllocationStrategyEditor.test.tsx:70` expected an older payload shape. |
| `cd frontend && npm run lint` | **FAIL** | 3 errors (`route-browser-test.js:7-9`, ESM `require` undefined), 9 warnings. |
| `cd frontend && npm run typecheck` | **PASS** | Exit 0. |
| Selected local Playwright login/mock checks | **PARTIAL/BLOCKED** | Initial mock checks passed; port 41731 later refused connections/timed out. |

No backend test, live database, migration, real-data E2E, restriction/accounting/bank workflow or full accessibility suite was executed. Managed E2E requires isolated DB/Redis, migration and seed harness; it was deliberately not run in this read-only assessment. Existing frontend tests mostly mock Axios. `playwright/accessibility.spec.ts` contains commented Axe assertions.

## Required release gates

Unit Decimal/restriction/accounting invariants; integration locking/idempotency/isolation; API validation/role/tenant negatives; isolated seeded E2E critical journeys; report/export parity; accessibility/keyboard/mobile; migration/backfill/rollback rehearsals; measured performance benchmarks; restore and security checks.
