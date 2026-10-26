# A3627 Classification Test Report

Environment: local PostgreSQL `lmanagement`, Python 3.14.6, pytest 8.3.4, Django 6.0.4. Interpreter: project `.venv`.

## Targeted suites (final code)

| Suite | Result |
|---|---|
| `test_a3627_classifier.py` (new registry tests: Sr. 1, 6, 11, 17, 22, serial invariance, norm isolation, pivot parity) | all pass |
| `test_item_pivot_a3627_classifiers.py` (end-to-end pivot on a real-shaped A3627 licence) | pass |
| `test_product_classification_hsn_boundaries.py` | pass |
| `test_item_matcher.py`, `test_sion_legacy_configurations.py`, `test_olive_oil_norm_restriction.py` | pass |
| `test_sion_planning_rules.py`, `test_sion_rule_engine_qa.py`, `test_plan_grouping.py` | pass |

Focused total: 337 passed (after the final registry change), then 216 passed on the matcher/registry subset after the last matcher change.

## Full backend suite (final code)

`pytest --continue-on-collection-errors` over `tests` and `apps`:

- **2,899 passed**
- **12 failed**
- **1 collection error**
- Duration: 511 s

### Failures and their status

All 12 failures and the collection error also occur on a clean checkout of `HEAD` (worktree, no uncommitted changes), so they predate this work:

| Test | Cause observed |
|---|---|
| `test_item_pivot_excel_export.py` (2) | Assertion: first Excel header is `SR NO`; test expects `Notification Number: PIVN1` |
| `test_item_pivot_planned_import_item.py` (2) | Assertions: merged description is `PP A, PP B` (expected `""`); merged HSN is `11010000, 11010090` (expected `11010090`) |
| `test_item_pivot_totals_and_selection_rule.py` (1) | `decimal.InvalidOperation` reading the Excel total cell |
| `test_plan_utilization.py` (1) | Output `item_names` include an `hs_code` key the test does not expect |
| `test_module3_allocation_scenarios.py::test_16_pair_mismatch_rejected` | Expected 400 `ALLOCATION_PAIR_MISMATCH`, got 201 |
| `test_available_licenses_plan_mode.py` (1) | Query count 17 vs limit 16 |
| `test_dgft_ownership.py` (4) | Live DGFT network calls through an unreachable proxy (`proxy.example`) in this sandbox |
| `test_parse_pdf_hs_autocreate.py` | Imports `SAMPLE_PDF_DATA` from `conftest.py`, which does not define it |

None of these tests is in the classification path. They were not modified.

## Expectations changed in this work (and why)

| Test | Old expectation | New expectation | Reason |
|---|---|---|---|
| `test_product_classification_hsn_boundaries.py` A3627 parity | `TITANIUM DIOXIDE`, `None` for "Soda Ash with rutile formers" | `Titanium Dioxide`, `Soda Ash` | Labels follow the requested names. "Soda Ash" matches the approved matcher rule. |
| `test_olive_oil_norm_restriction.py` | `classify_product("15091000","PP GRANULES 1509","A3627") is None` | `!= "OLIVE OIL"` | The guard is about Olive Oil. The line now falls to the generic PP rule, which the matcher also gives. |

No test was weakened to pass a real regression.

## Cross-module and cross-norm coverage

- Pivot path: `ItemPivotService` calls `classify_product(..., default_sion)`. Covered by `test_item_pivot_a3627_classifiers.py` and by the parity test.
- Matcher (linking): covered by `test_item_matcher.py` A3627 table, including the new RUTILE HSN and "other than" cases.
- Norm isolation: `test_a3627_products_do_not_leak_into_other_norms` checks E1, E5, E126, E132.
- Serial invariance: parametrized over serials 1, 6, 11, 17, 22, 99.

Not covered by an automated test: the Excel export and the frontend display of the new categories, planning/allocation and entitlement calculations for A3627 lines, and background jobs. The pivot's Excel uses the same category values, but I did not add a test that compares Excel cells against the registry for these categories.

## Lint

- `pyflakes` on the changed modules and tests: clean.
- `ruff` is not installed in the project venv, so it was not run.

## Database

No database rows were changed. The classification is computed on demand, so no backfill was run (see audit §10).

## Round 2 (uppercase labels, endpoint, Excel, cache)

Final code, actual results:

- Targeted suites (A3627 classifier, pivot classifiers, E2E, hsn boundaries, matcher, Olive Oil guard): 244 passed.
- New end-to-end file `test_a3627_item_pivot_e2e.py`: 26 passed. Covers each fixture line through the registry, the `/api/reports/item-pivot/` JSON endpoint, the Excel exporter (cell placement), obsolete-label checks, and cache invalidation on a registry-version change.
- Full backend suite: **2,926 passed, 12 failed, 1 collection error** (507 s). The 12 failures and the collection error are the same pre-existing set documented above; none is in the classification path.
- Frontend `tsc -p tsconfig.json --noEmit`: exit 0.
- Real data (1,200 A3627 lines): HEAD classifier vs current registry: 999 changed, 201 unchanged. Changes are unclassified to RUTILE/ALUMINIUM OXIDE/TITANIUM DIOXIDE/SODA ASH/SILICA/BORAX, OLIVE OIL to PP (37) and OLIVE OIL to WOODEN (11), and 74 unclassified to WOODEN. Chapter-48 lines previously PAPER stay PAPER (a first attempt moved 84 of them to PP; that was reverted and covered by a test).
- Excel workbook generated from the live database by the current exporter: all 220 A3627 licences present; 1,194 lines with an HSN checked against the registry, 1,194 matched (6 blank-HSN rows cannot be checked by HSN). No mixed-case obsolete labels in any header.
