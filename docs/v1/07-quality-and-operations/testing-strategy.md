# Testing strategy

V1 release gates must include: unit/domain tests; API schema and authorization matrices; transaction/reversal/idempotency tests; golden financial/entitlement comparisons; migrations/backfills; React component/state tests; authenticated Playwright/axe smoke; download/upload/export paths; recovery and restore drills.

Critical-path thresholds are more useful than a global percentage: permissions, balance/allotment, BOE/transfer, calculation rounding and migrations each need explicit regression ownership. CI currently lacks E2E/a11y execution and an enforced coverage floor (**Verified by code**). A first local Playwright baseline ran and failed (68 passed, 54 failed, 8 skipped); see [E2E baseline](e2e-baseline.md). It must be repaired/stratified before becoming CI-required.

Current measured baseline: the canonical backend `tests/` suite passed 237/237 in 67.01 seconds and reported 20% aggregate coverage; the separate licence/core app suite passed 2,708/2,708 in 440.51 seconds; the MDS suite passed 25/25 in 0.80 seconds against a disposable PostgreSQL 16 CI-equivalent container; and mds-client passed 32/32 in 0.015 seconds using its in-memory database. These are useful smoke/regression signals, not proof of adequate financial, authorization or workflow coverage.
