# Modernization — Dependency Map and Verification Log

Scope: five modules — Licences, License Ledger, Planning Workbench, Incentive Licences, Ledger Upload.
Status: **partial**. Endpoints and browser loads are verified for all five. Internal service/model tracing is verified for Licences (CIF) and Incentive Licences (sold status) only.

Field-level financial dictionary, CIF reconciliation and incentive ownership findings: `financial-field-dictionary-and-reconciliation.md`.

## 1. Business rules in force

- **Original CIF** = the original CIF entitlement granted or endorsed on the import licence. It is not adjusted by purchase credits or trade debits. See `licence-cif-quantity-balance-business-rules.md` §1.1.
- **Utilised CIF** = BOE CIF + ALLOTMENT CIF + BILLED CIF WITHOUT BOE. **Available CIF** = Original CIF − Utilised CIF. Negative values are shown, never floored.
- The D-1 engine `services/financial_position.py` stays separate from the live calculator. No consumer migrates between engines until purchase-credit and trade-debit treatment is formally decided. A guard test enforces this.

## 2. Verified endpoints by module

| Module | Page route | Verified API calls (browser, 200 unless noted) |
|---|---|---|
| Licences | `/licenses` | `GET /api/licenses/?is_expired=False&flags__is_null=False&page=1&page_size=25`; `GET /api/masters/purchase-statuses/` |
| License Ledger | `/license-ledger` | `GET /api/license-ledger/license-wise/?license_type=ALL&…`; `GET /api/license-ledger/summary/?…` (pending at capture); `GET /api/masters/companies/` (pending at capture) |
| Planning Workbench | `/planning` | `GET /api/sion-planning-rules/dashboard/`; `GET /api/masters/sion-classes/?is_active=true` |
| Incentive Licences | `/incentive-licenses` | `GET /api/incentive-licenses/?page=…` |
| Ledger Upload | `/ledger-upload` | No data call on load. Upload: `POST /api/upload-ledger/`. Status poll: `GET /api/ledger-task-status/<task_id>/` |

## 3. Calculation paths

| Calculation | Live path | Notes |
|---|---|---|
| Item balance (CIF, qty) | `licence_balance_report._item_report` → `licence_item_balance.build_item_balance` → `sale_boe_allocation.compute_utilisation` | Canonical. Allotment residue via `licence_balance_report.allotment_link`. |
| Licence list `available_cif` | Serializer `canonical_available_map` (canonical path) | Not clamped. Drives the list card "Available Balance CIF". |
| Licence list `balance_cif` | Serializer `live_balance_map` (legacy `LicenseBalanceCalculator`) | **Clamped: `_clamp` returns 0.00 for any value ≤ 0** (see §5). |
| Incentive `sold_status` | `IncentiveLicense.update_sold_status` writes cache from sale lines; serializer and filter read the same `derive_sold_status` rule | Row-locked recalculation, triggered by trade-line save/delete and trade-link changes. |
| D-1 engine | `services/financial_position.py` | Not used by any consumer. Retained by decision. |

## 4. Verification evidence

| Check | Command / method | Result |
|---|---|---|
| CIF formula numerical tests | `pytest apps/license/tests/test_cif_utilisation_formula.py -o addopts=` | **20 passed** |
| Sold-status contract | `pytest apps/license/tests/test_incentive_sold_status_contract.py -o addopts=` | **9 passed** (incl. filter choices = `{NO, YES, PARTIAL}`) |
| Incentive "missing status" fix | Same test against original `HEAD` vs fixed | Fails on `HEAD` (1 of 4), passes after fix (4 of 4) |
| Licences API vs display | In-page fetch compared to rendered cards | Record 0811016774: `available_cif` −461,464.94; rendered "−4,61,464.94" in red (`rgb(248,81,73)`). Match. |
| Incentive labels vs API | Page-1 API `sold_status` compared to rendered card labels | 25 of 25 match (`YES`→Sold). Zero mismatches. |
| Browser console | Every route loaded | No errors or warnings on any of the five routes |

## 5. Open findings (not changed — need a business or product decision)

1. **Two live balances disagree (P0 candidate).** Across the 48 non-expired licences on page 1, 9 have negative `available_cif` (canonical), and all 9 show a positive `balance_cif` (legacy). Example: 0811016774 — canonical −461,464.94, legacy 323,386.15. Over-utilised licences therefore look healthy in the legacy field.
2. **`balance_cif` clamps negatives to zero.** `serializers/license.py` `_clamp` breaks the "never clamp a negative" rule. Fixing it changes reported values, so it waits for approval.
3. **Zero-balance licences show "Available".** Some licences have `sold_value = 0` and `balance_value = 0`, so `derive_sold_status` returns `NO` and the card shows "Available". Nothing sold is shown as available, but a zero-balance licence is. Needs a product decision.
4. **Ledger Upload accepts only CSV and HTM/HTML.** The spec asks for Excel as well. Not implemented.
5. **Ledger summary and companies requests were still pending** at capture time. Their response bodies are not yet verified.
6. **Pre-existing backend test failures:** 10 (see §6). `SAMPLE_PDF_DATA` import error is also pre-existing.

## 6. Backend baseline (before any change in this session)

`pytest` over `apps` and `tests`, with `apps/license/tests/test_parse_pdf_hs_autocreate.py` excluded because of the pre-existing `SAMPLE_PDF_DATA` import error:

**10 failed, 3658 passed, 1 skipped, 2 xfailed** (8m41s).

Nine of the 10 were run against clean `HEAD` (commit `34d7b967`) and fail there too. The tenth (`test_available_licenses_plan_mode.py::…::test_plan_candidate_query_count_is_constant_for_a_paginated_response`) also fails at `HEAD`. So none of the 10 come from the uncommitted working tree.

Failing tests:
- `apps/allotment/tests/test_available_licenses_plan_mode.py::TestPlanModeSplitRows::test_plan_candidate_query_count_is_constant_for_a_paginated_response`
- `apps/allotment/tests/test_module3_allocation_scenarios.py::TestCanonicalAllocationScenarios::test_16_pair_mismatch_rejected`
- `apps/license/tests/test_a3627_item_pivot_e2e.py::test_excel_export_places_each_line_under_its_category`
- `apps/license/tests/test_a3627_item_pivot_e2e.py::test_excel_rutile_block_has_unit_price_after_balance_qty`
- `apps/license/tests/test_e132_display_sequence.py::test_excel_columns_follow_the_same_e132_order`
- `apps/license/tests/test_e1_classification_sequence.py::test_excel_headers_follow_the_same_e1_order`
- `apps/license/tests/test_item_pivot_planned_import_item.py::CanonicalPivotSourceTests::test_distinct_sources_remain_traceable_and_do_not_string_concatenate`
- `apps/license/tests/test_item_pivot_planned_import_item.py::CanonicalPivotSourceTests::test_source_items_identify_only_the_planned_import_row`
- `apps/license/tests/test_license_overview_summary_view.py::LicenseOverviewSummaryViewTests::test_returns_header_fields_and_summary_cards`
- `apps/license/tests/test_plan_utilization.py::test_falls_back_to_item_names_then_id_for_description`

Note: the wrapper command reported exit code 0 because it piped through `tail`. The pytest summary above is the source of truth.

## 7. Changed files in this session

- `frontend/src/pages/masters/tables/IncentiveLicensesTable.tsx` — status label fallback (explicit `NO` only as Available; missing or unknown shows Unknown).
- `frontend/src/pages/masters/tables/IncentiveLicensesTable.test.tsx` — new, 4 tests.
- `backend/apps/license/tests/test_cif_utilisation_formula.py` — new, 20 tests.
- `backend/apps/license/tests/test_incentive_sold_status_contract.py` — new, 9 tests.
- `docs/09-module-implementation/licence-cif-quantity-balance-business-rules.md` — added §1.1 (Original CIF definition, component mapping).
- This file — new.

No existing uncommitted change was reverted, overwritten, or staged. The `git status` count went from 85 to 91: those 85 plus six files: four new (the two backend test files, the frontend test file, and this map) and two edited (the incentive table and the business-rules doc). Nothing was committed.
