# Licence Sale ↔ BOE — Test Report

Status: **Pure-calculation tests pass. Integration, API, frontend and database-backed tests are not written.** No consumer was changed, so no existing balance was affected by this stage.

## 1. Tests executed

Command (from `backend/`):

```
/Users/drushahardiksottany/Developer/projects/license-manager/.venv/bin/python -m pytest -o addopts= -q \
  apps/license/tests/test_sale_boe_allocation.py apps/license/tests/test_financial_position.py
```

Result: **66 passed** (0.07 s).

| Suite | Tests | Result | Covers |
|---|---:|---|---|
| `test_sale_boe_allocation.py` (new) | 30 | pass | Brief §13 table for CIF and quantity; over-linking; cancellation; partial reversal; multi-sale split; identity across scenarios; invariant guards; independence of CIF and quantity |
| `test_financial_position.py` (earlier stage) | 36 | pass | D-1 utilisation and over-utilisation |

### 1.1 Expected outcomes pinned

| Brief §13 test | Original | Sale | Linked BOE | Uncovered BOE | Expected available | Result |
|---|---:|---:|---:|---:|---:|---|
| Sale only | 1,000 | 500 | 0 | 0 | 500 | pass |
| Partial linked BOEs | 1,000 | 500 | 190 | 0 | 500 | pass |
| Fully linked sale | 1,000 | 500 | 500 | 0 | 500 | pass |
| Additional uncovered BOE | 1,000 | 500 | 190 | 30 | 470 | pass |
| BOE linked after creation | 1,000 | 500 | 220 | 0 | 500 | pass |
| BOE unlinked | 1,000 | 500 | 190 | 30 | 470 | pass |

The quantity equivalents (kg) pass for the same cases.

### 1.2 Other cases pinned

Over-linking (excess counted, flagged); cancelled sale (BOEs become uncovered, available 780); sale reduced within linked amount (600); sale reduced below linked amount (excess 40, available 810); one BOE split across two sales (utilised 160, available 840); multiple customers; negative available reported (−200, not floored); decimal exactness (0.80); quantity quantised to 3 places; outstanding allotment reduces available; a BOE cannot cover more than its amount; unknown sale or BOE rejected; duplicate link id rejected; float, negative and unknown-measure inputs rejected; CIF and quantity independent; item balances require matching inputs; the identity `utilised = sold + uncovered + over-linked + allotment` holds across scenarios.

## 2. Tests not executed

| Area | Status | Why |
|---|---|---|
| Database-backed service tests (link, unlink, cancel, reverse, concurrent link requests) | **Not written** | No canonical service exists yet, and the fixture needs trade, BOE and allocation rows |
| Integration tests against the existing ledger builders | **Not written** | No consumer uses the new calculation |
| Concurrency tests (`select_for_update` on link operations) | **Not written** | Requires the service above |
| API contract tests (calculation breakdown and transaction references in responses) | **Not written** | No API change made |
| Permission and financial audit-log tests | **Not written** | No write path added |
| Frontend tests and browser checks | **Not run** | No frontend change made |
| PDF and Excel consistency | **Not run** | No export change made |
| Lint, typecheck, production build | **Not run** | Not required for a new pure module and test file; should be run before merge |
| Existing licence backend suites | **Not re-run** | No existing module was modified |

## 3. Read-only audit execution

`licence-sale-boe-audit.py` ran against `lmanagement` across all 222 licences: 0 errors. Results are in `licence-sale-boe-calculation-audit.md` and `licence-sale-boe-audit.csv`.

Nothing was written. The database was read through a cursor and the ORM's read paths only.

## 4. Historical data

- Historical sales, BOE rows, allocation rows and membership rows: **unchanged**.
- Historical balances: **unchanged**. No consumer calls the new calculation.
- Licences whose sale/BOE utilisation would differ under the rule: **40** (audit only, not applied).

## 5. Gaps to close before any consumer change

1. Write the database-backed service tests for every lifecycle case (link, unlink, cancel, reverse, over-link, duplicate link, concurrent link) against real PostgreSQL. Expected to fail first on the over-link and cross-item cases.
2. Write the 2406 and 2469 regression tests as failing tests, to pin DEF-1 and DEF-2 before the fix.
3. Resolve decisions D-1 to D-4 (see `licence-sale-boe-open-business-decisions.md`), which change expected values.
4. Re-run the full licence suite and the reconciliation suite after the consumer change.
