# Licence Canonical Calculation — Test Report (Licence 2583 stage)

Status: **Partial.** Pure arithmetic is tested. The integration regression tests that would reproduce the 2583 discrepancies inside the ledger services are **not yet written**, because they need a database fixture that does not exist. Those tests are listed in section 4 as the next step. No calculation consumer was changed, so no regression test was required to fail-then-pass.

---

## 1. Automated tests run

| Suite | Command | Result |
|---|---|---|
| Pure D-1 engine (new) | `backend/.venv/bin/python -m pytest -o addopts= -q apps/license/tests/test_financial_position.py` (run from `backend/`) | **36 passed**, 0.05 s |
| — of which licence 2583 scenarios | `… -k 2583 -v` | **3 passed** |

What the 36 tests cover (`backend/apps/license/tests/test_financial_position.py`):

| Group | Tests | Covers |
|---|---:|---|
| Approved examples | 2 | D-1 §3.2 (available 35 lakh) and §3.3 (over-utilised −15 lakh, not floored) |
| Category combinations | 9 | None, BOE only, allotment only, billed only, pairs, all categories, fully utilised, exact summation |
| Double-counting invariant | 6 | Partial and full allotment→BOE conversion, billed→BOE, partial and full cancellation, reversal |
| Over-utilisation | 4 | Negative shown; exactly at limit is not over; one paisa over; zero original has no % |
| Precision | 4 | Decimal arithmetic (0.30 exact), half-up rounding (8.995 → 9.00), two-place output, large values |
| Input validation | 7 | Float, bool, non-numeric, NaN, Infinity, negative category, blank currency all rejected |
| Metadata | 3 | Currency carried without conversion, warnings returned, timezone-aware timestamp |
| Licence 2583 scenarios | 3 | Hidden BOE counted → 1,913.61; hidden excluded → 23,583.38; engine = customs − billed |

Not run in this stage: the existing licence backend suites, the frontend suites, lint, typecheck and the production build. No production code or frontend code changed, so these were not re-run. Earlier results for those suites are in the prior stage reports and are not repeated here.

---

## 2. Read-only reproductions (not tests, but evidence)

Executed against the `lmanagement` database with the existing calculators. Nothing was written.

| Measure | Result | Reproduces |
|---|---:|---|
| `calculate_financial_balance` (list/overview Balance CIF) | 1,913.61 | Page "Balance CIF" ✓ |
| `build_financial_ledger(lic)` computed balance (plain rows) | 1,913.61 | Ledger rows agree with the engine ✓ |
| `build_financial_ledger(lic, canonical_data=…)` (API path) | **401,583.40** | Page "Current Balance" ✓ — **differs from its own rows** |
| `calculate_balance` (customs) | 411,473.61 | Page "Customs Available" ✓ |
| `calculate_boe_debit_total` | 182,856.60 | Page "Debited CIF" ✓ |
| `calculate_hidden_boe_debit_total` | 21,669.77 | Customs − Debited ✓ |
| `calculate_purchase_credit` | 994,000.00 | Part of "Previous Owner Utilisation" ✓ |
| `calculate_trade` (sales) | 592,416.60 | = 182,856.60 (BOE-matched) + 409,560.00 (unmatched) ✓ |
| Canonical opening seed for this licence | 0 (valid purchase present) | RC-1 |
| Engine opening (`credit − hidden − purchase`) | −399,669.79 | RC-1 |

Cross-licence comparison (all 222 licences, `licence-management-v2-engine-comparison.csv`):

| Measure | Result |
|---|---:|
| Licences where API final ≠ engine | 111 |
| Combined absolute gap | 17,455,579.83 USD |
| Of which involve purchases | 95 |
| Of which do not involve purchases (unexplained) | 16 |
| Licences with a hidden BOE | 97 |
| Licences with purchase credit | 201 |

---

## 3. Browser and UI verification

| Check | Result |
|---|---|
| Overview page loads for licence 2583 (single session, one login) | Yes. Page text captured (`/tmp`, not in repo) |
| API calls behind the page | `GET /api/licenses/2583/`, `overview-summary/`, `balance-ledger/`, `replan-status/`. All 200 |
| Screenshots at 1920, 1440, 1280, 1024, 390 px | Captured: `docs/09-module-implementation/v2/screenshots/2583-overview-{width}.png` |
| Visual review of 1440 px | Done. Defects L1–L6 recorded in the UI design |
| Visual review of 1920, 1280, 1024, 390 px | **Not done** |
| Interaction tests (expand, toggles, Recalculate, PDF, Excel) | **Not done** |
| Console errors and unexpected 404s | Not systematically checked. The four API calls returned 200 |

Note on the login: the test harness logs in once per run. Repeated logins are throttled by the API (`Request was throttled`), which occurred during the earlier listing work.

---

## 4. Integration regression tests still to write

These need a database fixture. The test database has no licence 2583 and no trade or BOE data, so each test must build its own. The tests should be written **first**, expected to fail, and then the calculation fixed once the business questions are answered.

| Test | Asserts | Expected now |
|---|---|---|
| `test_financial_ledger_final_equals_its_last_running_balance` | `computed_balance` equals the last row's `running_balance`, for a purchase-bearing licence | **Fails** (401,583.40 vs 1,913.61). RC-2 |
| `test_canonical_and_engine_agree_on_opening_for_purchase_with_hidden_boe` | Canonical seed equals engine opening rule | **Fails** (0 vs −399,669.79). RC-1 |
| `test_customs_available_equals_engine_plus_billed_without_boe` | customs − engine = billed-without-BOE sales | Passes once the fixture is built |
| `test_debited_cif_excludes_hidden_and_customs_includes_it` | Overview debited = customs BOE − hidden | Passes once the fixture is built |
| `test_item_balances_sum_to_licence_balance_when_billed_attributed_to_item` | Verified SR remaining sums to licence balance | Passes once the fixture is built |
| `test_stored_item_available_value_is_item_specific` | `available_value` per SR is not a copy of the licence balance | **Fails** on SR 4, 5, 6, 8. RC-6 |
| `test_trade_line_without_inr_is_flagged_unverified` | Lines 846, 1229, 1246 raise an unverified-currency warning | **Fails** (no warning exists). RC-4 |
| `test_multi_boe_invoice_line_warning_is_per_aggregate` | Multi-BOE warnings compare aggregates, not single lines | **Fails** (per-line false positive). RC-7 |
| `test_hidden_boe_counted_in_canonical_utilisation` | Canonical path includes hidden BOE, pending Q-05 | Depends on Q-05 |
| `test_purchase_round_trip_or_duplicate_documented` | Line 1246 classification is an explicit flag, not implicit | Depends on Q-02 |

Fixture requirements (to build with the existing models, in an isolated test database): one licence with an exporter, port, purchase status and scheme; six import items including one with no HS code; one purchase trade and two-sided purchase/sale pair; five sales with BOE links (including one multi-BOE invoice); two unmatched sales with zero INR; one hidden BOE on the unmapped item; the matching `RowDetails` debit and credit rows; and the `BillOfEntryModel` M2M to the trade lines.

---

## 5. Not tested

- Permission enforcement on the overview and balance endpoints. Only the authorised session was used.
- PDF and Excel for licence 2583. The forensic audit notes that they were not run. They must be checked against the verified figures once the canonical figure is fixed.
- The 16 non-purchase licences in the cross-licence gap. Their cause is unknown.
- Concurrency and reversal behaviour through the API.
- Performance of the overview and ledger endpoints for this licence.

---

## 6. Changes made under test

| File | Change | Test status |
|---|---|---|
| `backend/apps/license/services/financial_position.py` | New pure D-1 calculator (earlier stage) | 36 tests pass |
| `backend/apps/license/tests/test_financial_position.py` | New, with 2583 scenarios appended | 36 tests pass |
| Documentation under `docs/09-module-implementation/` | New, read-only artefacts | Not applicable |

No database rows, calculator code, ledger code, serializer, view or frontend component was modified in this stage.
