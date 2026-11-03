# Licence Item CIF & Quantity Balance — Test Report

Status: **Pure-calculation tests pass. Integration, API, UI and export tests are not written or run.** No consumer was changed, so no balance shown in the application changed.

## 1. Tests executed

Command (from `backend/`):

```
/Users/drushahardiksottany/Developer/projects/license-manager/.venv/bin/python -m pytest -o addopts= -q \
  apps/license/tests/test_licence_item_balance.py \
  apps/license/tests/test_sale_boe_allocation.py \
  apps/license/tests/test_financial_position.py
```

Result: **83 passed** (0.08 s).

| Suite | Tests | Status | Covers |
|---|---:|---|---|
| `test_licence_item_balance.py` (new) | 17 | pass | Brief §2 quantity example (balance 200) and CIF equivalent; sale-covered BOE inside invoiced; uncovered BOE debited; over-linked excess debited and flagged; cancelled allotment; negative available shown; unit normalisation; `mts` unverified; missing unit; unmapped amount reported and not deducted; float rejected; negative rejected; item aggregation keeps identity; CIF and quantity not aggregated together; mixed units refused; unmapped carried to licence total |
| `test_sale_boe_allocation.py` (earlier stage) | 30 | pass | Sale/BOE rule, CIF and quantity; §13 table; over-linking; lifecycle; invariant guards |
| `test_financial_position.py` (earlier stage) | 36 | pass | D-1 utilisation and over-utilisation; licence 2583 arithmetic |

### 1.1 Brief test list coverage

| Brief # | Case | Covered by | Status |
|---|---|---|---|
| 1 | 1,000 − 540 − 160 − 100 = 200 | `BriefExampleTests.test_quantity_example_balances_to_200` | pass |
| 2 | Equivalent CIF | `test_cif_equivalent_uses_cif_amounts_not_quantity` | pass |
| 3 | Sale $500 from $1,000 | sale/BOE suite, §13 table | pass |
| 4 | Multiple BOEs linked to a sale | sale/BOE suite | pass |
| 5 | Partially linked BOE | sale/BOE suite (over-link and split) | pass |
| 6 | Uncovered BOE | `test_uncovered_boe_is_debited` | pass |
| 7 | Over-linked excess | `test_over_linked_excess_is_debited_and_flagged` | pass |
| 8 | Multiple customer allotments | **not written** (allotments are a single input here) | — |
| 9 | Invoice already included in allotment | **not written**; cannot be tested in pure code (depends on the allotment–sale relation, O-4) | — |
| 10 | Invoice linked to BOE | sale-covered BOE test | pass (pure) |
| 11 | Sale cancellation | sale/BOE suite | pass (pure) |
| 12 | Allotment cancellation | `test_cancelled_allotment_releases_reservation` | pass (pure) |
| 13 | BOE unlinking | sale/BOE suite (case F) | pass (pure) |
| 14 | BOE relinking | sale/BOE suite (case E) | pass (pure) |
| 15 | Partial reversals | sale/BOE suite (cases H and reduction below link) | pass (pure) |
| 16 | Negative available | `test_negative_available_is_shown_and_flagged` | pass |
| 17 | Duplicate allocations | sale/BOE suite (BOE over-allocated raises) | pass (pure) |
| 18 | Cross-item mapping | **not in the pure suite**; detected only by the audit (88 items) | audit only |
| 19 | Unmapped items | `test_unmapped_amount_is_reported_and_not_deducted` | pass (pure) |
| 20 | Different quantity units | unit tests and mixed-unit refusal | pass (pure) |
| 21 | CIF currency conversion | **not written**; no conversion is performed in the calculator (labels only) | — |
| 22 | Licence/item aggregation | `AggregationTests` | pass (pure) |
| 23 | API output | **not written**; no endpoint exists | — |
| 24 | PDF and Excel consistency | **not written**; no export changed | — |
| 25 | Permission and audit logging | **not written**; no write path exists | — |

Rows 8, 9, 18, 21, 23, 24 and 25 are the gaps. Rows 9 and 18 need the database-backed tests; 21 needs a conversion rule (O-9 in the open decisions); 23–25 need the endpoint and exports.

## 2. Read-only audit execution

- Item audit: 2,348 items, 0 calculation errors. Results in `licence-cif-quantity-balance-audit.md` and `licence-cif-quantity-item-audit.csv`.
- Unit validation: queries on `unit` fields and median CIF per unit (§3.6 of the audit).
- Nothing was written to the database.

## 3. Tests not executed

| Area | Status | Why |
|---|---|---|
| Database-backed item tests against the real models | **Not written** | Requires fixtures for trades, BOEs, allocations, allotments and items |
| Concurrency (locking on link and allotment) | **Not written** | Canonical write path not built |
| API contract | **Not written** | No endpoint |
| Frontend (item table, ledger, responsive layout) | **Not run** | No frontend change |
| Browser verification | **Not run** | No frontend change |
| PDF / Excel | **Not run** | No export change |
| Permissions and audit log | **Not written** | No write path |
| Existing licence backend suites | **Not re-run** | No existing module modified |
| Lint, typecheck, build | **Not run** | Not required for a new pure module; run before merge |

## 4. Historical data

- No historical record was changed. No backfill was run.
- The audit classified 2,348 items. Items whose recalculated values differ from the stored columns: 1,652 for available CIF, 255 for debited CIF (listed in the CSV). They are not corrected.

## 5. Gaps to close before consumer migration

1. Database-backed tests for the item calculation, against PostgreSQL, including zero-original items, cross-item links and allotment residue.
2. Regression tests pinned to the audit cases: item 37436 (over-use), item 27317 (stored value wrong), item 27318 (zero original), and the two `mts` items (unit status).
3. Decisions O-1 to O-4 and O-8 (units, cross-item, attribution, allotment overlap, hidden BOEs). These change expected values.
4. API, PDF and Excel tests once a canonical endpoint exists.
