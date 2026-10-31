# Implementation progress log

## 31 October 2026 - AR-003 evidence recovery and AR-002 canonical contract

- **AR-003 characterization:** isolated `test_lmanagement_codex_ar003_rerun_20261031` run passed 71/71 in 16.43s, exit 0. Durable output and status are retained at `tmp/ar003-characterization-20261031.log` and `.exit`. This verifies current calculator behavior only; no balance semantics changed.
- **AR-002 canonical contract:** added a v1 response characterization to `test_item_pivot_planned_import_item.py`. It verifies `report_version`, non-empty `groups`, and source-row identity/decimal-string fields. The first run exposed an incorrect new expectation (`25` versus established `25.000` serialization); after correcting the characterization, an isolated fresh database run passed 5/5 in 11.02s, exit 0. Evidence: `tmp/ar002-contract-20261031.log/.exit` and `tmp/ar002-contract-rerun-20261031.log/.exit`.
- **Compatibility boundary remains:** active `CanonicalPivot` consumes `groups`; legacy/fallback/export paths retain `planned_import_items`. No adapter, rename, field removal, or response behavior change is justified without a compatibility owner/version decision.

## 31 October 2026 - Parallel architecture closure evidence

- **AR-001 verified current contract:** routes, permissions, actions and tests establish a global-role application, not company tenancy. The retired user-company FK, global ViewSet querysets, and `test_idor_fixes_p0_p1.py` confirm authorised users may read records across companies. Direct allotment and BOE lookups/hard deletion are implementation risks, but no documented tenant or retention policy establishes them as regressions. Required owner decision: global-role versus scoped-membership model, privileged exception/audit behaviour, historic access, and delete/cancel/reversal policy.
- **AR-003 verified distinct balance concepts:** customs, financial and item-physical balances have intentionally different inputs; snapshots compose existing bulk calculator maps. No duplicate calculation was proven safe to merge. Required owner decision: ARO, hidden-BOE, purchase/sale, reversal/reservation, rounding/event-ordering and snapshot authority. Existing calculator, ledger, direct-sale and parity tests remain the characterisation boundary.
- **AR-002 verified compatibility boundary:** live JSON is `canonical-item-pivot-v1` with `groups` and source-lineage `source_items`; the active frontend canonical branch consumes that DTO. `planned_import_items` remains in legacy/fallback/export logic. Preserve both until a compatibility owner approves version/deprecation. Safe future additions are canonical API and frontend branch fixtures; no public contract changed.

## 31 October 2026 - Phase 19 evidence closure and narrow lint correction

- **Protected baseline:** branch and HEAD remain `codex/baseline-regression` / `d2cb2446ba01e0e23e6ef3570f6449bdd001cf65`; pre-existing tracked edits, untracked documentation/artifacts, and local `runserver` processes were retained. No pytest process was active before this work.
- **AR-001 traced, not changed:** `User` provides global group roles and no company/membership relationship; `AllotmentModel` owns a company FK; `AllotmentPermission` is role-only. `destroy_allotment` and several BOE actions use direct model lookups. This proves an unscoped implementation pattern, not a demonstrated cross-company exploit: the repository has no approved tenant scope to test or enforce. The exact owner decision remains the company/membership ownership model plus delete-versus-correction/audit-retention policy.
- **AR-003 traced, not changed:** `balance_calculator.py` has 57 static dependents. Its documented current paths intentionally differ: customs balance, financial balance, and item physical quantity each have separate BOE, allotment, purchase/sale, hidden-row, and direct-sale terms. No formula was consolidated because no owner-approved lifecycle, reversal, rounding, reservation or snapshot authority exists.
- **AR-002 traced, not changed:** the live `/api/reports/item-pivot/` JSON path returns `ItemPivotService.build(...)`, `report_version: canonical-item-pivot-v1`, and `source_items`; the active `CanonicalPivot` renders `groups` directly. `planned_import_items` belongs to the legacy/export/fallback projection. Therefore there is no evidence that the canonical UI loses source identity, but compatibility/version ownership is still required before any rename or unification.
- **Lint safe batch:** added the existing Node/CommonJS `route-browser-test.js` executable as a file-specific ESLint override. `npm run lint` now exits 0 with nine pre-existing warnings and no errors; `npm test` passed 544/544 (78 files). Strict `npm run format:check` still exits 1 because its `--max-warnings=0` gate rejects those nine warnings; none was changed in this scoped batch.

## 31 October 2026 - Phase 20 frontend quality closure

- **Strict lint closure:** removed unused Playwright/Vitest values and an unused request result, and used two narrowly-scoped `react-refresh/only-export-components` exceptions for the existing context-provider/hook and component/helper modules. These exceptions document why splitting the co-exports would add UI dependency complexity without a refresh-safety benefit. `npm run format:check` exited 0 with zero warnings/errors.
- **Frontend regression:** `npm test` completed with 544/544 tests across 78 files. No API, routing, permissions, financial calculation, or component behavior changed.
- **Architecture status:** AR-001 remains blocked on a company/membership plus correction/retention decision; AR-003 remains blocked on approved balance lifecycle semantics; AR-002 needs a compatibility/version owner before any public pivot field change. AR-004 and AR-006 have no independently justified implementation seam beyond the safe work already completed.

## 31 October 2026 - Phase 12/13 architecture audit and first safe batch

- **Baseline revalidated:** `codex/baseline-regression` remained at `d2cb2446ba01e0e23e6ef3570f6449bdd001cf65`; the existing tracked edits, untracked documents/artifacts, and local development servers were preserved.
- **Index validation:** `manifest.json` contains 1,545 entries; `symbols.tsv` contains 9,868 symbols; `imports.tsv` and `dependents.tsv` each contain 2,932 edges. A structural comparison found zero missing reverse edges and zero orphan reverse edges. The rebuild after the code batch reported one changed source file.
- **Architecture findings:** the authoritative register is `04-target-architecture/architecture-findings-register.md`. It records scope-bypass patterns, competing pivot source-lineage DTOs, balance-calculator coupling, intentional lazy import cycles and frontend transport coupling without misclassifying static evidence as runtime proof.
- **Target boundary:** `04-target-architecture/target-architecture.md` now defines incremental ownership and allowed dependency directions. AR-001 and AR-003 require company/deletion and balance-lifecycle owner decisions; no unsafe authorization or financial refactor was attempted.
- **AR-005 completed:** removed `LicenseDetailsViewSet.update`, whose entire implementation logged raw request/document values and returned `super().update(...)`. This preserves API, authorization, validation, transaction and response behavior while eliminating unnecessary payload logging.
- **AR-005 verification:** `tests/test_api_license.py` plus `apps/license/tests/test_license_items_view.py` passed 25/25 using isolated `TEST_DB_NAME=test_lmanagement_codex_archrefactor_20261031`; `manage.py check` passed with no issues; `manage.py makemigrations --check --dry-run` reported no changes. No migration, dependency, production, balance, accounting or API-contract change was made.
- **Phase 17/18 validation:** final backend command `TEST_DB_NAME=test_lmanagement_codex_archfinal_20261031 .venv/bin/python -m pytest --no-cov -q --reuse-db --junitxml=../tmp/backend-architecture-final-20261031.xml --html=../tmp/backend-architecture-final-20261031.html --self-contained-html` started `2026-10-31T10:27:11.727872+00:00` and passed 3,203/3,203 tests, with zero failures, errors or skips, exit 0, in 466.225 seconds. JUnit and HTML evidence are retained under `tmp/`.
- **Frontend validation:** `npm test` passed 544/544 and `npm run typecheck` passed. Strict `npm run format:check` exited 1 on three pre-existing `require`-global errors in `frontend/route-browser-test.js`, plus nine warnings in untouched files. No frontend behavior was changed to mask that separate lint issue.
- **Final index reconciliation:** two successive `.claude/index/build_index.py` runs each reported `1545 files, 0 changed`; the final static graph contains 9,867 symbols and equal 2,932-edge forward/reverse inventories. The symbol decrease from the earlier 9,868 count is the removed `update` override.

## 31 October 2026 - Auditable source-index reconstruction

- **Baseline protection:** reconstruction ran on `codex/baseline-regression` at `d2cb2446ba01e0e23e6ef3570f6449bdd001cf65`; all pre-existing tracked/untracked work remained in place and `git diff --check` remained clean.
- **Canonical available implementation:** `.Codex/index/` is absent, but the repository supplies the equivalent documented indexer `.claude/index/build_index.py`. It is stdlib-only and indexes tracked source via `git ls-files`; it does not change application behavior or source files.
- **Command and result:** `/Users/drushahardiksottany/Developer/projects/license-manager/.venv/bin/python .claude/index/build_index.py` generated `manifest.json`, `symbols.tsv`, `imports.tsv`, `dependents.tsv`, and `CODE_MAP.md` beneath `.claude/index/`: 1,545 tracked indexed files, 9,868 symbol records, 2,932 resolved internal import edges, and 2,932 reverse-dependency edges.
- **Validation:** all inventories have their expected headers; `CODE_MAP.md` reports the same file/symbol totals. An immediate second command run reported `index: 1545 files, 0 changed`, establishing deterministic incremental reproduction. The generated artifacts are Git-ignored and therefore do not pollute the protected worktree.
- **Coverage and limits:** Python, JavaScript, JSX, TypeScript, and TSX receive regex-level symbol and static-import extraction; shell, SQL, HTML, CSS/SCSS/LESS, and Vue are inventoried without symbols. The graph resolves only internal static Python/JS imports among tracked files. Dynamic imports, runtime registration, template references, external packages, untracked files, and semantic call relationships remain outside this index and must be checked separately during architecture analysis.
- **Status:** RB-001 is unblocked and complete for an auditable repository source inventory. Architectural dependency analysis may begin, but must retain the stated static-analysis limitations.

## 31 October 2026 - Backend regression baseline complete

- **Protected baseline:** branch `codex/baseline-regression` at `d2cb2446ba01e0e23e6ef3570f6449bdd001cf65`; all pre-existing tracked edits and untracked `docs/assessment/`, `docs/enterprise-rebuild/`, `output/`, and `tmp/` artifacts were preserved. Local `runserver` processes were not touched.
- **Isolation:** application database setting remained `lmanagement`; all current verification used explicit databases beginning `test_lmanagement_codex_`, never a production system.
- **Focused regression gate:** E132/E1 sequence modules 50/50, export trio 39/39, planned-import plus plan-utilization 16/16, related consumers 21/21, and parser plus complete allotment suite 116/116 passed. Migration consistency reported `No changes detected`; `manage.py check` reported no issues.
- **Initial full run:** `TEST_DB_NAME=test_lmanagement_codex_fullbackend_20261031 .venv/bin/python -m pytest --no-cov -q --reuse-db --junitxml=../tmp/backend-full-initial-20261031.xml --html=../tmp/backend-full-initial-20261031.html --self-contained-html` started `2026-10-31T10:01:06.941059+00:00`, collected 3,203 tests, and exited 1 after 427.598 seconds: 3,202 passed and one failed.
- **RB-BE-011 completed:** `TestSionRuleResolverBasics.test_resolve_canonical_input_with_legacy_fallback` was an order-dependent fixture. It expected a hardcoded legacy fallback that the resolver has never implemented; its documented hierarchy is output+SION, SION, global alias, then `UNMAPPED`. The migration-seeded global aliases may be absent temporarily in a reused suite database. The test now creates the two required global alias records with `get_or_create` and still asserts the `PKO` mapping. This is a self-contained, data-driven fixture correction; no resolver or production behavior changed. Git commit `908bd8da` introduced both the data-driven resolver and the contradictory test wording.
- **RB-BE-011 verification:** focused resolver plus generic integration modules passed 24/24 on `test_lmanagement_codex_siondiag_20261031`; migration consistency again reported no changes.
- **Final full run:** `TEST_DB_NAME=test_lmanagement_codex_fullbackend_final_20261031 .venv/bin/python -m pytest --no-cov -q --reuse-db --junitxml=../tmp/backend-full-final-20261031.xml --html=../tmp/backend-full-final-20261031.html --self-contained-html` started `2026-10-31T10:09:43.948008+00:00`, collected and passed 3,203/3,203 tests, with zero failures, errors, or skips, exit 0, in 457.723 seconds. Both initial and final JUnit/HTML artifacts are retained under `tmp/`.
- **Index limitation at this point in time:** `.Codex/index/` was absent and `.claude/index/` generated artifacts were unavailable. This was resolved by the later source-index reconstruction entry above.

## 31 October 2026 - Phase 0/1 baseline

- **Protected branch:** `codex/baseline-regression`, created from reference `develop` commit `d2cb2446ba01e0e23e6ef3570f6449bdd001cf65`.
- **Source inventory:** this earlier count is historical only. At final verification `.Codex/index/` was absent and `.claude/index/` did not contain its generated symbol/import/dependent artifacts; see the backend-regression baseline entry above.
- **Migration consistency:** `backend/manage.py makemigrations --check --dry-run` passed with `No changes detected`.
- **Backend balance regression:** `apps/license/tests/test_balance_calculator.py` passed 50/50 using isolated `TEST_DB_NAME=test_lmanagement_codex_baseline_20261031`.
- **Frontend baseline before implementation:** 543/544 tests passed; the failing `AllocationStrategyEditor` test expected an obsolete percentage-row payload.
- **RB-FE-001 completed:** updated the test contract to include the current `strategy` and `cif_restriction_percentage: null` fields. Evidence: `frontend/src/services/api/planningRuleApi.ts` defines the optional field and `backend/apps/license/migrations/0056_add_cif_restriction_percentage.py` persists it. No production/business calculation changed.
- **Frontend verification after RB-FE-001:** targeted test 8/8 passed; full suite 544/544 passed; typecheck passed; lint passed.
- **Backend full suite:** collection stopped after 3,198 tests were discovered because `apps/license/tests/test_parse_pdf_hs_autocreate.py` imports missing `SAMPLE_PDF_DATA` from its package `conftest`. This is recorded as a baseline failure; it was not changed in this task.

## RB-BE-001 - PDF parser HS-code auto-create test contract

**Root cause:** `test_parse_pdf_hs_autocreate.py` imported `SAMPLE_PDF_DATA`, but the symbol was never defined in its `conftest.py` and was never used by the module. The introducing commit `701e3a71` added the unused import without adding a fixture. After collection was restored, the test exposed two additional fixture-setup defects: its user had no `LICENSE_MANAGER` group despite a POST endpoint guarded by `LicensePermission`, and raw bytes did not populate `request.FILES` for the multipart upload gate.

**Correction:** removed the unused import; assign `LICENSE_MANAGER` in test setup using the project-standard Django `Group`; use one fresh `SimpleUploadedFile` per request through a test helper. The parser remains mocked in every case, so the small PDF byte sequence is a transport fixture only; it does not substitute parser input or weaken any HS-code creation assertion.

**Evidence:** `backend/apps/accounts/permissions.py` requires `LICENSE_MANAGER` for `LicensePermission` writes; comparable tests use that group. `backend/test_pdf_parsing_e2e.py` uses `SimpleUploadedFile`. `backend/apps/license/views/parse_pdf.py` requires `request.FILES["file"]`. Git history shows the unused import was present from the test's introduction.

**Verification:** targeted module 5/5 pass; full collection 3,203 tests succeeds; migration consistency reports no changes. A persistent local run completed from `2026-10-31T08:22:26Z` to `2026-10-31T08:30:06Z` using the isolated database `test_lmanagement_codex_rb_be_001_confirmed_20261031_b`:

```sh
TEST_DB_NAME=test_lmanagement_codex_rb_be_001_confirmed_20261031_b .venv/bin/python -m pytest --no-cov -q --reuse-db
```

It exited `1`: 3,194 passed, 9 failed, 0 errors, and 0 skipped (3,203 collected). The complete result is retained in the local evidence artifact `tmp/rb-be-001-confirmed-b.log`. The failures are outside the changed parser test module and are classified as **unresolved independent baseline failures**, not RB-BE-001 regressions: one plan-mode query-budget assertion, one allocation-pair validation assertion, three Excel/pivot-export fixture assertions, two planned-import pivot-source assertions, and one plan-utilization response-shape assertion. No application or production code was changed to address them.

**Status:** Done - fixture-contract, targeted-test, collection, migration-consistency, and complete-suite-execution evidence are recorded. The nine non-RB-BE-001 failures require separately scoped triage before a clean backend release gate can pass.

## Next task

No individual failure from the historical nine remains untriaged. The next baseline task is a persistent isolated full-backend-suite verification run to establish the post-correction status; do not infer a clean suite from focused results.

## RB-BE-010 - Plan-utilization item-name response shape

**Selected failure:** `apps/license/tests/test_plan_utilization.py::test_falls_back_to_item_names_then_id_for_description`.

**Observed failure:** the fallback descriptions were correct, but the exact `item_names` assertion omitted `hs_code`. Actual entries were `{"id": ..., "name": "borax", "hs_code": null}` and `{"id": ..., "name": "Rutile", "hs_code": null}`.

**Contract verified:** `plan_utilization_rows` uses the following precedence: trimmed import-item description; otherwise case-insensitively name-sorted joined item names; otherwise `ID:<representative import-item id>`. An isolated diagnostic confirmed `Explicit description`, `borax, Rutile`, and `ID:<id>` for these three cases. Commit `7a1371ac` intentionally added `hs_code` to each `item_names` response entry so the Planning Editor can show the source HSN; absence of an HSN serializes as `null`.

**Classification:** outdated test expectation after an intentional response-shape extension; not a fallback-logic or serialization regression.

**Correction:** updated only the expected `item_names` dictionaries to include `hs_code: None`. The test continues to verify both name and ID fallback levels; existing grouping tests cover a present description. No application, data, API behavior, financial, licence, accounting, migration, or production behavior changed.

**Verification:** focused node passed 1/1; full plan-utilization module passed 12/12; licence-detail plan-utilization, planned-pivot, and response-cache modules passed 8/8; migration consistency passed (`No changes detected`). All commands used `TEST_DB_NAME=test_lmanagement_codex_planutil_20261031`, distinct from configured application database `lmanagement`.

**Status:** Done. The historical full-suite result remains 3,194 passed / 9 failed because it predates all focused corrections; no updated full-suite claim has been made.

## RB-BE-009 - Planned versus unplanned pivot-source aggregation

**Selected failure:** `apps/license/tests/test_item_pivot_planned_import_item.py::CanonicalPivotSourceTests::test_source_items_identify_only_the_planned_import_row`.

**Observed failure:** the original test expected only planned import HSN `11010090`, but its canonical pivot cell contained `11010000, 11010090`.

**Contract verified:** the fixture has an unplanned row (serial 1, `11010000`, `Batch A`, quantity `50`) and a planned row (serial 2, `11010090`, `Batch B`, quantity `200`, plan quantity `150`, planned CIF `750`). Both classify to the same product-category/SION key. Commit `0a155e89` intentionally changed planned and unplanned pivot keys to `product_category:sion` so every licence import item is visible and same-category rows aggregate into one column. `_merge_plan_cell` retains separate `source_items` records while summing the physical totals. The isolated result retained both source IDs and descriptions, total quantity `250`, plan quantity `150`, planned CIF `750`, and remaining quantity `100`.

**Classification:** legitimate aggregation; stale test expectation. The extra HSN enters in the unplanned-item pass after the planned cell is created, because both rows have the same category/SION key; it is not a lost or substituted planned source.

**Correction:** renamed the test to describe the actual category-level aggregation and asserted both source IDs, all source identity fields, the joined display HSN/description, and the distinct physical versus planned totals. No application, data, API, export, financial, licence, accounting, migration, or production behavior changed.

**Verification:** focused renamed node passed 1/1; complete planned-import pivot module passed 4/4; response-cache, balance-consistency, notification-summary, and generic Excel-export modules passed 24/24; migration consistency passed (`No changes detected`). All commands used `TEST_DB_NAME=test_lmanagement_codex_pivotselection_20261031`, distinct from configured application database `lmanagement`.

**Status:** Done. The historical full-suite result remains 3,194 passed / 9 failed because it predates this correction; no updated full-suite claim has been made.

## RB-BE-008 - Planned-pivot source display description

**Selected failure:** `apps/license/tests/test_item_pivot_planned_import_item.py::CanonicalPivotSourceTests::test_distinct_sources_remain_traceable_and_do_not_string_concatenate`.

**Observed failure:** the original assertion expected an empty cell description, but the generated canonical pivot cell returned `PP A, PP B`.

**Contract verified:** `source_items` is the authoritative per-import-item lineage list in the canonical pivot projection. The isolated projection retained separate records for both import-item IDs, serial numbers, and descriptions (`PP A`, `PP B`), and its plan quantity remained `300`. Commit `ff021e741` explicitly changed the human-readable merged-cell display from blank to a case-insensitively deduplicated comma-separated description summary, while preserving individual source records. The pivot service returns this canonical projection directly; the Excel export renders its own separate source lines where applicable. The current frontend component refers to legacy `planned_import_items`, not `source_items`; end-to-end UI consumption of the canonical lineage field is unverified and was not changed.

**Classification:** outdated test expectation, not a source-traceability regression. Distinct identity was neither lost nor merged in the source-record contract; only the summary display is joined.

**Correction:** renamed the test to describe the current behavior and changed the display assertion to `PP A, PP B`. It now additionally asserts that `source_items` retains both individual source descriptions as well as both IDs. No application, data, API, export, financial, licence, accounting, migration, or production behavior changed.

**Verification:** focused renamed node passed 1/1; related generic pivot Excel-export, response-cache, and balance-consistency modules passed 11/11; migration consistency passed (`No changes detected`). The planned-import module was run and produced 3 passed / 1 failed: `test_source_items_identify_only_the_planned_import_row` is a separately scoped source-selection failure and was not changed. All commands used `TEST_DB_NAME=test_lmanagement_codex_pivotsource_20261031`, distinct from configured application database `lmanagement`.

**Status:** Done. The historical full-suite result remains 3,194 passed / 9 failed because it predates this correction; no updated full-suite claim has been made.

## RB-BE-007 - E1 pivot Excel category-header coordinate

**Selected failure:** `apps/license/tests/test_e1_classification_sequence.py::test_excel_headers_follow_the_same_e1_order`.

**Observed failure:** the unchanged baseline test raised `AssertionError: E1 licence not found in the Excel export` because it searched dynamic product-category headers in row 1.

**Report contract verified:** `ItemPivotReportView.export_to_excel_streaming` writes its notification title in row 1, merged product-category headers in row 2, field headers in row 3, and data from row 4. An isolated generated workbook contained the E1 fixture categories in row 2 from column 10: `OTHER CONFECTIONERY`, `APPLE DIES`, `PP`, `PAPER`, `CMC`, and `SUGAR`; row 1 was empty in that dynamic range. `NORM_DISPLAY_SEQUENCES["E1"]` explicitly configures the first five fixture categories in that order. `SUGAR` is not configured for E1 and correctly follows the configured sequence under the fallback order. The neighboring JSON pivot-order test asserts the same semantic order.

**Classification:** outdated test coordinate, not a fixture, sequence, or Excel-export regression.

**Correction:** changed only the test's category-header row from 1 to 2 and added an accurate layout comment. The complete expected category assertion and `APPLE DRIES` exclusion remain unchanged. No exporter, classification, business calculation, data model, migration, financial, accounting, or production behavior changed.

**Verification:** focused node passed 1/1; full E1 classification-sequence module passed 23/23; generic Excel-export, E132 display-sequence, and A3627 pivot modules passed 61/61; migration consistency passed (`No changes detected`). All commands used `TEST_DB_NAME=test_lmanagement_codex_e1diag_20261031`, distinct from configured application database `lmanagement`.

**Status:** Done. The historical full-suite result remains 3,194 passed / 9 failed because it predates this correction; no updated full-suite claim has been made.

## RB-BE-006 - E132 pivot Excel category-header coordinate

**Selected failure:** `apps/license/tests/test_e132_display_sequence.py::test_excel_columns_follow_the_same_e132_order`.

**Observed failure:** the baseline test raised `AssertionError: E132 licence not found in the Excel export` because it searched dynamic product-category headers in row 1.

**Report contract verified:** `ItemPivotReportView.export_to_excel_streaming` writes the notification title in row 1, merged product-category headers in row 2, field headers in row 3, and data from row 4. An isolated generated workbook contained the E132 categories in row 2 from column 10: `FOOD FLAVOUR`, `YEAST`, `PKO`, `CHEESE`, `APPLE DIES`, `CEREALS`, `CMC`, `ALUMINIUM FOIL`, `PP`, and `RBD PAL`; row 1 was empty in that dynamic range. `NORM_DISPLAY_SEQUENCES["E132"]` and the neighboring JSON-order test establish the first nine categories as the authoritative configured sequence, with `RBD PAL` following under the fallback ordering.

**Classification:** outdated test coordinate, not an Excel export or E132 display-sequence regression.

**Correction:** changed only the test's category-header row from 1 to 2 and corrected its comment. The exact expected ordering and misspelling assertions for `CERELS` and `APPLE DRIES` remain unchanged. No report generation, business calculation, data model, migration, financial, accounting, or production behavior changed.

**Verification:** focused node passed 1/1; full E132 display-sequence module passed 27/27; related generic Excel-export, dynamic-field, and A3627 pivot modules passed 39/39; migration consistency passed (`No changes detected`). All commands used `TEST_DB_NAME=test_lmanagement_codex_e132diag_20261031`, distinct from configured application database `lmanagement`.

**Status:** Done. The prior full-suite evidence remains 3,194 passed / 9 failed because it predates this correction; no updated full-suite claim has been made.

## RB-BE-002 - Plan-mode query-budget diagnostic

**Observed failure:** the full eight-row PLAN candidate response used 17 captured SQL queries while the test's ceiling was 16.

**Evidence and breakdown:** an isolated SQL trace against `test_lmanagement_codex_querydiag_20261031` recorded 18 queries for the first one-row request (including a one-time exchange-rate lookup) and 17 for the subsequent eight-row request. The eight-row request contains authentication/permission (3), allotment plus prefetched detail (2), plan query and its prefetches (5), grouped PLAN-debit aggregate (1), physical-source discovery (1), and three constant serializer balance maps: direct-sale CIF, direct-sale quantity, and BOE-debited quantity. The extra query relative to the former 16-query budget is the direct-sale **quantity** aggregate from `billed_no_boe_qty_bulk_map`; it was added with the Customs Ledger response field in commit `b192ee10`. Its SQL groups all page item IDs in one query, so it does not grow per plan row. Query 17 itself is the necessary batched BOE-debit aggregate, shifted by the new quantity aggregate.

**Classification:** outdated test contract, not a performance regression. The response serializer now legitimately exposes both direct-sale CIF and direct-sale quantity. The N+1 guard remains: the one-row request had 18 queries and the eight-row request had 17, so query volume did not grow with the page's seven additional rows.

**Correction:** `test_available_licenses_plan_mode.py` now permits 17 fixed queries and documents the added serializer batch. The row-growth assertion remains unchanged; no endpoint, serializer, permission, licence, accounting, or migration behaviour changed.

**Verification:** focused test 1/1 passed; plan-mode plus neighboring availability-filter modules 25/25 passed; `apps/allotment/tests` produced 110 passed and the already-independent `test_16_pair_mismatch_rejected` failure; migration consistency passed (`No changes detected`). Diagnostic SQL is retained locally as `tmp/rb-be-002-query-trace.log`.

**Status:** Done. The remaining allotment failure is out of scope and requires its own allocation-validation investigation.

## RB-BE-003 - Allocation CIF-pair mismatch fixture

**Observed failure:** `test_16_pair_mismatch_rejected` submitted Qty `10` at unit price `10.000` with CIF `99.99`, expected HTTP 400, and received HTTP 201.

**Rule verified:** `_allocate_items_atomic` calculates canonical CIF as `qty × unit_price`, rounded up to two decimals, and rejects a positive-price pair only when its absolute difference exceeds `0.01`, except for the separately documented final-settlement path. Commit `d89d9d91` deliberately introduced this ±0.01 tolerance for real-world rounding differences. Therefore `99.99` is a valid one-cent tolerance case for canonical `100.00`; `99.98` is a mismatched pair and must be rejected.

**Reproduction:** the original test failed 1/1 with HTTP 201. An isolated diagnostic against `test_lmanagement_codex_pairdiag_20261031` confirmed that the `99.99` request persisted one `AllotmentItems` record (`qty=10.000`, `cif_fc=99.99`). A separately constructed `99.98` request returned HTTP 400 with `ALLOCATION_PAIR_MISMATCH` and persisted zero records.

**Classification:** fixture defect. The implementation enforces the intended tolerance, while the historical test input no longer represents a mismatch.

**Correction:** changed only the test input to `99.98` and documented why it lies outside the permitted tolerance. No application, financial, licence, accounting, migration, or dependency behaviour changed.

**Verification:** focused scenario 1/1 passed; the allocation scenario, CIF-validation, and PLAN-mode modules passed 47/47; the complete allotment suite passed 111/111; migration consistency passed (`No changes detected`).

**Status:** Done.

## RB-BE-005 - RUTILE pivot Excel header and field order

**Selected failure:** `apps/license/tests/test_a3627_item_pivot_e2e.py::test_excel_rutile_block_has_unit_price_after_balance_qty` (the prompt's `test_item_pivot_excel_export.py` path did not contain this node).

**Observed failure:** the test reported no RUTILE block because it searched category headers in row 1. After correcting that coordinate, it also assumed every optional RUTILE field existed and expected `BALANCE QTY`/`UNIT PRICE` at absolute offsets 9/10.

**Report contract verified:** the exporter writes title in row 1, category headers in row 2, field headers in row 3, and data from row 4. `_pivot_item_fields` inserts `UNIT PRICE` immediately after `BALANCE QTY` for RUTILE. It also intentionally removes optional fields whose values are empty or zero; the A3627 fixture therefore produces `HSN CODE`, `DESCRIPTION`, `TOTAL QTY`, `BALANCE QTY`, `UNIT PRICE` in its RUTILE block. The relevant dynamic-field tests confirm this omission rule.

**Classification:** outdated test coordinates and fixed-offset expectation; not a workbook column-order regression.

**Correction:** updated the test to locate the RUTILE category in row 2, read its fields in row 3, derive the category span from the next category header, and assert that `UNIT PRICE` immediately follows `BALANCE QTY`. This retains the exact ordering requirement without requiring unrelated empty fields to be emitted. No report-generation, financial, licence, accounting, migration, or production behaviour changed.

**Verification:** focused node passed 1/1. A3627 end-to-end, general pivot Excel-export, A3627 classifier, and dynamic-field modules passed 40/40. Migration consistency passed (`No changes detected`).

**Status:** Done.

## RB-BE-004 - A3627 pivot Excel category fixture

**Selected failure:** `apps/license/tests/test_a3627_item_pivot_e2e.py::test_excel_export_places_each_line_under_its_category`.

**Observed failure:** the test could not find HSN `32061190` for the first A3627 fixture in its exported workbook row, even though the JSON classifier and report data resolve the line to `RUTILE`.

**Evidence:** an isolated workbook diagnostic against `test_lmanagement_codex_pivotdiag_20261031` found the fixture row in sheet `Unknown-1`, with HSN `32061190` at column 10 beneath the `RUTILE` category. The exporter writes notification title in row 1, category headers in row 2, field headers in row 3, and data starting row 4. The helper instead inspected the superseded row-1/row-2/row-3 layout. Exporter comments and implementation at `apps/license/views/item_pivot_report.py::ItemPivotReportView.export_to_excel_streaming` establish the current layout; Git history attributes the current row contract to the category-header redesign.

**Classification:** outdated test helper/fixture contract. The workbook content and category assignment were correct; only the helper's row coordinates were stale.

**Correction:** updated `_excel_categories_for_licence` to use the current category, field, and data rows. It still asserts the exact HSN-to-category mapping and does not weaken report-content verification. No report generator, business calculation, data model, migration, or production behaviour changed.

**Verification:** selected node passed 1/1. The A3627 end-to-end, pivot Excel-export, and A3627 classifier modules produced 34 passes and one separately scoped existing failure: `test_excel_rutile_block_has_unit_price_after_balance_qty`, which still expects the old header rows and was not changed. Migration consistency passed (`No changes detected`).

**Status:** Done.

