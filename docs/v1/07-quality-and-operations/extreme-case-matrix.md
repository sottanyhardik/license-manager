# Extreme-case matrix (traceable)

Status: **partial.** This matrix begins with the high-risk invariants and maps each to an existing test or a named gap. It is not a claim of complete coverage. Coverage is evidenced only by the test IDs listed. A scenario marked **Blocked (D#)** cannot be implemented until the owner decision named in the risk register is made.

Status values: **Covered** (a passing test asserts it), **Partial** (some assertions exist), **Missing**, **Blocked (decision)**, **Characterized** (current behaviour pinned, not approved).

| ID | Area | Invariant or scenario | Expected behaviour | Evidence (test or doc) | Status |
| --- | --- | --- | --- | --- | --- |
| AUTH-01 | Auth | Anonymous list request to critical endpoints | 401 or 403, no data | `apps/license/tests/test_critical_api_anonymous_access.py::test_anonymous_list_is_rejected` (7 paths) | Covered |
| AUTH-02 | Auth | Anonymous write rejected before validation | 401 or 403, not 400 | `test_anonymous_write_is_rejected_before_validation` (5 paths) | Covered |
| AUTH-03 | Auth | Authenticated user with no role | 403 on list | `test_role_less_user_is_forbidden_on_list` (7 paths) | Covered |
| AUTH-04 | Auth | Anonymous detail id reveals no existence | Same status for existing and missing ids | `test_anonymous_detail_does_not_reveal_existence` (3 ids) | Partial: checks status only, not body |
| AUTH-05 | Auth | Anonymous and role-less pivot (JSON and Excel) | 401/403 | `test_item_pivot_authorization.py` (4 cases) | Covered |
| AUTH-06 | Auth | Report viewer reads permitted report | 200 with `grand_total` | `test_report_viewer_can_read_json` | Covered |
| AUTHZ-01 | Cross-company | Report viewer reads a licence from an unassigned company | Policy-dependent | `test_d1_current_behaviour_report_viewer_sees_licence_from_unassigned_company` | **Characterized (D1)**. Not approved. |
| AUTHZ-02 | Cross-company | Object-level read/write for licence, allotment, BOE, trade across companies | Policy-dependent | None | **Blocked (D1)** |
| AUTHZ-03 | Cross-company | Export of another company's data | Policy-dependent | None | **Blocked (D1)** |
| BAL-01 | Balance | Customs balance excludes nothing; financial excludes hidden rows via opening rule | Documented formulas | `test_balance_semantics_d2_characterization.py` (6 tests) | **Characterized (D2)** |
| BAL-02 | Balance | Snapshot `customs_balance` vs customs ledger on a hidden-BOE licence | Unresolved; diverges (93,000 vs 63,000 on the synthetic fixture) | `test_snapshot_customs_balance_diverges_from_customs_ledger` | **Characterized (D2)** |
| BAL-03 | Balance | Zero balance, exact and partial consumption, overconsumption | Floored at zero, no negative available | `apps/license/tests/test_balance_calculator.py::test_calculate_balance_zero`, `::test_calculate_balance_exact_zero`, `::test_calculate_all_components_negative_balance`, `::test_partially_allocated_allotment_only_leaves_remainder_quantity` | Partial. Overconsumption through the allocation path (a second allocation against an exhausted balance) has no dedicated test. |
| BAL-04 | Balance | Decimal precision: 2 dp quantisation and rounding boundaries | Quantised to 2 dp | `test_balance_calculator.py::TestEdgeCases::test_precision_in_calculations` | Partial |
| BAL-05 | Balance | Concurrent consumption of the same balance | No overallocation under contention | None found in this pass | **Missing** |
| BAL-06 | Balance | Reversal or cancellation restores the balance | Balance returns to the pre-allocation value | None found in this pass | **Missing** |
| BAL-07 | Balance | Stored `balance_cif` equals financial calculation after save | Equal | `apps/license/tests/test_balance_cif_single_source.py` (file exists; assertions not re-read in this pass) | Partial |
| TX-01 | Transactions | Partial failure rolls back allocation | No partial writes | Named in backend workflow map, not re-verified here | Unverified |
| TX-02 | Transactions | Repeated submission is idempotent | Single effect | Not verified in this pass | Unverified |
| VAL-01 | Validation | Malformed or missing fields on writes | 400 with stable error body | Existing API tests (not enumerated here) | Partial |
| VAL-02 | Validation | Sensitive internal details absent from 500 responses | No traceback or SQL in body | Observed: a stale-schema 500 returned a database message in the body (see SEED and E2E notes); not yet fixed | **Open (P2)** |
| SEED-01 | Fixtures | Browser seed assigns purchase status to all seeded licences | No licence with null status | `test_seed_browser_2509_command.py` assertion | Covered |
| HARN-01 | Test infra | Browser harness refuses an occupied port | Exit 2 before touching a database | Manual verification (exit 2 with port 8000 occupied) | Partial: no automated test |
| UI-01 | Frontend | Sticky stack alignment under scroll | Within 2 px | `e2e/item-pivot.sticky.spec.ts` (guarded; passes 3/3 through the harness) | Covered (guarded) |
| UI-02 | Frontend | Shell and filter controls have accessible names (4 rules) on 6 routes at 2 widths | Zero violations for the fixed rules | `e2e/shell-and-filter.accessibility.spec.ts` (guarded) | Covered (guarded) |
| UI-03 | Frontend | Failed API response shows an error state, not a blank screen | Error message | Not verified in this pass | Missing |
| IMP-01 | Imports | Malformed upload rejected with a validation error | 400, no partial import | Not verified in this pass | Missing |
| EXP-01 | Exports | Export honours the same filters as the list view | Matching totals | Partial: pivot JSON and Excel share the generator (not asserted for every field) | Partial |
| JOB-01 | Background jobs | Duplicate delivery of a ledger package job | Idempotent | Named in backend workflow map | Unverified |
| DB-01 | Migrations | Migration graph has no drift | `makemigrations --check` clean | Re-run this session: no changes detected | Covered |

## Open items this matrix exposes

1. **D1 blocks AUTHZ-02 and AUTHZ-03.** Object-level tests cannot be written until the owner states the policy.
2. **BAL-05 and BAL-06 are missing.** These are the highest-risk financial gaps and need a concurrency test on a real database with `select_for_update` or equivalent. They must be designed before implementation.
3. **VAL-02 needs a fix, not a test.** A 500 response returned a raw database message. Production should return a generic error. Confirm with a test after the fix.
4. **HARN-01 has no automated test.** Add one if the harness script is ever run in CI.

## How to refresh this matrix

1. Run the listed test files, not the full suite, when a row changes.
2. Update the status and evidence columns. Do not mark a row Covered without a passing assertion.
