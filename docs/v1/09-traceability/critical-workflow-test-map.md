# Critical workflow test map

This map ties named test *modules/classes* to the workflow IDs in
`workflow-register.md` and the backend boundaries in
`backend-critical-workflow-map.md`. It is a traceability aid, not a coverage
calculation: a test class can contain many assertions, while a passing module
does not prove every registered endpoint, permission branch, UI state or
production integration.

## Counting method and measured baseline

The map contains **16 workflow rows**, **12 backend-boundary references**,
and **at least 58 named test evidence groups**. A group is a named test class,
file, or E2E spec—not a claim about the number of individual test functions.
All 16 workflow rows
have at least one named test group. This is `named-test evidence: 16/16`, not
`workflow-complete: 16/16`.

Measured on the current V1 worktree:

| Executed scope | Result | How it applies |
| --- | --- | --- |
| `TESTING=true pytest tests/ -p no:cacheprovider` | 237 passed in 67.01s | Root/canonical API, permissions and integration subset. |
| `TESTING=true pytest apps/license/tests apps/core/tests --import-mode=importlib -p no:cacheprovider` | 2,708 passed in 440.51s | Licence/core, balance, planning, job, protected-media and sync evidence. |
| Frontend `npm test` | 544 tests / 78 files passed | Frontend unit/component evidence; this does not execute Playwright specs. |
| Frontend lint, typecheck, build | Passed | Build quality only; not behavior/authorization proof. |
| MDS pytest | 25 passed in 0.80s | Ran against a disposable PostgreSQL 16 CI-equivalent container on `127.0.0.1:55432`; the initial default-local role failure was not remediated in place. |
| mds-client `runtests.py` | 32 passed in 0.015s | Ran with the PyCharm module-local environment and its in-memory Django database. |
| Playwright/axe specs | 68 passed / 54 failed / 8 skipped in 3.6m | Local browser evidence is now measured but failing; see `07-quality-and-operations/e2e-baseline.md`. |

## Workflow-to-test matrix

| Workflow ID / backend boundary | Named backend/root/MDS evidence | Named frontend/E2E evidence | Evidence status and required closure |
| --- | --- | --- | --- |
| WF-01 Authentication and user lifecycle / BW-01 | `backend/tests/test_all_conditions.py::TestAuthentication`; `backend/tests/test_api_integration.py::TestAuthenticationIntegration`; `backend/tests/test_authentication_query_param.py`; `backend/tests/test_authorization_permissions.py::LicenseActionAuthorizationTests` | `frontend/src/pages/Login.test.tsx`; `frontend/src/test/useAuth.test.tsx`; `frontend/e2e/login.accessibility.spec.ts`; `login.visual.spec.ts` | Backend/unit evidence executed; E2E only discovered. Add refresh/revocation/session-expiry and denial matrix per endpoint. |
| WF-02 Licence master and items / BW-02 | `backend/tests/test_api_license.py::{TestLicenseAPI,TestLicenseItemAPI,TestLicenseDocumentsUpload}`; `backend/tests/test_api_integration.py::TestLicenseAPIIntegration`; `apps/license/tests/test_individual_item_cif_override_action.py::IndividualItemCifOverrideActionTests`; `apps/license/tests/test_parse_pdf_hs_autocreate.py` | `frontend/src/pages/masters/MasterForm.smoke.test.tsx`; `MasterList.smoke.test.tsx`; `NestedFieldArray.test.tsx`; `license-overview/LicenseOverviewPage.documents.test.tsx` | Partial. Characterize generated CRUD/nested serializer errors, document upload rollback and every licence action. |
| WF-03 Licence balances and ledgers / BW-03 | `apps/license/tests/test_balance_calculator.py::{TestLicenseBalanceCalculator,TestItemBalanceCalculator,TestHiddenBoeExclusion}`; `test_balance_cif_single_source.py`; `test_balance_ledger_views.py::{BalanceLedgerGetTests,CustomsLedgerTests,FinancialLedgerGroupingTests,HideBoeRestoreBoeViewTests}`; `test_ledger_characterization_option_c.py`; `test_ledger_dual_run.py::DualRunVerificationTests` | `frontend/src/components/LicenseBalanceModal.test.tsx`; `pages/license-balance/balanceMetricContract.test.ts`; `pages/LicenseLedger*.test.tsx`; `e2e/financial-ledger-invoices.spec.ts`; `e2e/license-overview.accessibility.spec.ts` | Strong characterization evidence, but policy D2 and browser execution remain open. Explicitly map every report’s balance engine and source time. |
| WF-04 Planning and SION rules / BW-04, BW-09 | `apps/license/tests/test_canonical_planning.py::{TestWritesAreTransactional,TestLiveBalanceIsRespected,TestGoldenCompanyIsolation}`; `test_sion_generic_rule_engine.py`; `test_sion_planning_rule_redesign.py`; `test_planning_single_entry_point.py`; `test_replan_requests.py::TestLicenseReplanRequests` | `frontend/src/pages/planning/LicensePlanningWorkspace.test.tsx`; `LicensePlanningWorkspace.regression.test.tsx`; `components/planning/PlanningEditor.reconciliation.test.tsx` | Partial. Preserve output parity and plan constraints; test queued/retry/worker-loss recovery and D3 policy. |
| WF-05 Allotment allocation/release / BW-04 | `apps/allotment/tests/test_allocate_items_cif_validation.py::TestAllocateItemsUsesLiveBalance`; `test_allocate_items_plan_line_balance.py::TestPlanLineLedgerResidual`; `test_allocate_items_group_plan_cap.py::TestPlanLineCapIsNotDoubleCounted`; `test_module3_allocation_scenarios.py::TestCanonicalAllocationScenarios`; `backend/tests/test_api_allotment.py::TestAllotmentAPI` | `frontend/src/pages/AllotmentAction.test.tsx`; `AllotmentFilters.test.tsx` | Partial. Existing tests exercise stale cache/caps but not a documented public concurrent-submission matrix or browser recovery UI. |
| WF-06 BOE/import evidence / BW-05, BW-11 | `backend/tests/test_api_boe.py::{TestBillOfEntryAPI,TestBOEIntegration}`; `apps/bill_of_entry/tests/test_boe_hide_service.py::{BillOfEntryNestedRowUpdateTests,HideBoeBalanceImmediacyTests,HideBoeIdempotencyTests,HideBoeReconciliationLogTests}`; `backend/tests/test_authorization_permissions.py::BOEPdfParseAuthorizationTests`; `apps/core/tests/test_protected_media_view.py::TestBillOfEntryDocumentAccess` | No named BOE-specific frontend component test located in the indexed frontend test-module inventory. | Partial. Add BOE screen state/error/parser/retry tests; link correction/hidden state to exact endpoint contracts. |
| WF-07 Trade, invoices and payments / BW-06 | `backend/tests/test_api_trade.py::{TestTradeAPI,TestTradeBillOfSupply,TestLicenseLedgerAPI}`; `apps/trade/tests/test_trade_service.py::{CounterpartCopyTests,LinkTradesTests,StampBoeInvoiceFromTradeHiddenGuardTests}`; `test_paired_trade_serializer.py::TestPairedTradeCifValidation`; `apps/core/tests/test_protected_media_view.py::TestTradeDocumentAccess` | `frontend/src/pages/TradeForm.smoke.test.tsx`; `masters/TradesListView.test.tsx`; `tradeFormHelpers.test.ts`; `e2e/trades.accessibility.spec.ts`; `e2e/trades.performance.spec.ts` | Partial. Payment lifecycle and documents have named evidence; bank/GL behavior is not implied or tested. |
| WF-08 BOE/invoice reconciliation / BW-07 | `apps/reconciliation/tests/test_allocation_service.py::{InvoiceBOEAllocationTests,BOEAllotmentAllocationTests,ReverseAllocationDispatcherTests}`; `test_boe_link_reconciler.py::BoeLinkReconcilerTests`; `test_reconciliation.py::{ReconciliationWriteActionTests,SummaryQueryTests}`; `test_external_invoice_service.py::ExternalInvoiceLinkTests` | `frontend/src/pages/ReconciliationPanel.smoke.test.tsx`; `components/planning/PlanningEditor.reconciliation.test.tsx` | Partial. Capture public write action validation/status codes and run negative role/company/race scenarios. |
| WF-09 Reports and exports / BW-03, BW-08 | `apps/license/tests/test_balance_excel_export.py`; `test_balance_pdf_endpoint.py::BalancePdfEndpointTests`; `test_license_report_view.py`; `test_item_report_view.py`; `test_active_dfia_report_view.py`; `backend/tests/test_authorization_permissions.py::DirectReportAuthorizationTests` | `frontend/src/components/reports/LicenseExportPanel.test.tsx`; `pages/reports/{ActiveLicenses,ExpiringLicenses,ItemPivotReport,ItemReport,LicensePurchaseProfitReport}.test*`; `utils/reportErrorHandling.test.ts` | Partial. Export contents have selected tests; require generated-file authorization/provenance and download recovery E2E. |
| WF-10 Ledger package/download jobs / BW-08, BW-09 | `apps/license/tests/test_license_ledger_package.py`; `test_license_ledger_package_jobs.py`; `test_ledger_package_recovery.py`; `backend/tests/test_api_license.py::TestLicenseLedgerUpload` | `frontend/src/services/licenseLedgerExport.test.ts`; `services/licenseLedgerPackageDownloads.test.ts`; `pages/LedgerUpload.test.tsx`; `e2e/custom-ledger-download.spec.ts` | Partial. Backend job suite executed; browser package-download evidence is discovered but unexecuted. Add storage/worker crash drill. |
| WF-11 Master data and synchronization / BW-10, BW-12 | `apps/core/tests/test_master_sync.py::{TestSyncService,TestBatchSync,TestChangeFeed,TestMediaSync}`; `test_sync_api.py::{TestPushEndpoint,TestPullEndpoint,TestDeleteCheckEndpoint,TestMediaDownloadEndpoint}`; `test_sync_failures.py::{TestReplayAndDuplicates,TestOutOfOrderConvergence,TestEveryRegisteredMasterIsTransportable}`; `master-data-service/masters/tests/test_api.py::{TestAuth,TestBulkUpsert,TestDeltaAndEtag}`; `mds-client/tests/test_sync.py::{MirrorUpsertTests,ChangeFeedDeleteTests}` | `frontend/src/pages/masters/MasterList.smoke.test.tsx`; `MasterForm.smoke.test.tsx` | Core sync, isolated MDS and MDS-client suites executed green. Peer lifecycle and deployment integration remain open. |
| WF-12 Task management / BW-09 | `apps/tasks/tests.py::TaskModelTests`; task-related API operations are registered but exact action tests have not yet been linked. | No named task-page test located in the indexed frontend test-module inventory. | **Partial with gap.** Add status-transition, permissions, comments/remark and failure-recovery test contract. |
| WF-13 Activity/audit history / BW-07, BW-12 | `apps/core/tests/test_activity_log_connections.py::StartLogThreadReleasesConnectionTests`; reconciliation/allocation tests above verify `ReconciliationLog` effects; BOE hide log tests. | No named activity-log UI test located. | Partial. The daemon-thread activity log is not proven durable; D6 plus termination/retry/audit-query tests are required. |
| WF-14 Administration/configuration / BW-01, BW-12 | `backend/apps/accounts/tests.py::{MigrateAuthCommandTests,RepairUserFKConstraintsCommandTests}`; `backend/tests/test_authorization_permissions.py::{MasterDataAuthorizationTests,CompanyPermissionAuthorizationTests}`; `apps/core/tests/test_masterdata_delete_protection.py::{TestCompanyDeleteProtection,TestMasterViewSetApiDeleteProtection}`; `apps/core/tests/test_reconcile_masters.py` | `frontend/src/pages/admin/{UserForm,UserList}.test.tsx`; `pages/masters/masterListConfig.test.ts`; `masterFormHelpers.test.ts` | Partial. Add admin negative tests, command dry-run/backup assertions and deployment-role enforcement. |
| WF-15 Accounting / bank reconciliation / BW-06, BW-07 | Trade/payment and reconciliation tests in WF-07/WF-08 demonstrate commercial ledger/reconciliation behavior only. No model/test evidence was found for bank-statement or GL reconciliation. | No bank/accounting-specific frontend test located. | **Undecided.** D5 must set scope before requirements or acceptance tests are invented. |
| WF-16 Tenant/SaaS isolation / BW-01, BW-03, BW-07 | `apps/license/tests/test_idor_fixes_p0_p1.py::{P0_IDORRetrieveEndpointTest,P0_IDORLedgerDetailEndpointTest,P0_DataLeakageSummaryEndpointTest,P1_AggregationDataLeakageCompanyWiseTest,UserWithoutCompanyTest}`; `test_canonical_planning.py::TestGoldenCompanyIsolation`; authorization suite. | `frontend/src/routes/authorizationRoles.test.ts` exercises client gates only. | Partial/ambiguous. Some tests validate calculation/grouping or selected IDOR fixes; they do not establish approved tenant isolation for all API reads/writes. D1 is required. |

## Test-gap closure rules

1. A test group can close an acceptance criterion only when it names the
   relevant operation/route, role or object scope, input, observable outcome
   and failure/recovery condition.
2. A frontend client-side role test cannot close server authorization; an API
   response/negative test must do so.
3. Unit tests of a service do not prove task dispatch, file storage, browser
   download or external integration behavior. Use a controlled integration or
   E2E test for that claim.
4. Disabled tests and historical runs are excluded from green evidence. The
   MDS unit row is current green evidence; Playwright and deployment-level
   integration remain limitations until their prescribed environments execute.

## Required next mapping increment

For M1, add operation IDs from `api-operation-register.tsv` and route IDs from
`frontend-route-register.tsv` to this matrix. Every P0/P1 operation must have
one positive, one authorization-negative, and one error/recovery test (or an
approved documented exclusion). That is the gate from named-test evidence to
implementation-ready functional coverage.
