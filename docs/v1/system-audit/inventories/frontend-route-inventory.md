# Frontend route and API inventory

Source: read-only static analysis of `frontend/src` by an Explore agent (task a97e610334b1d57fa, 2026-11-01). Nothing was run or written. Endpoint strings with `${x}` are route parameters kept literal. **DYNAMIC** means the path is built by a function, variable, query string or router state. VERIFIED = confirmed by grep or read; SUSPECTED = needs a runtime check.

Lead checks (VERIFIED by grep or read on 2026-11-01): the expiring and active report endpoints use the `license/reports/` prefix (4 page and test files), and the backend mounts the license app under `api/` with `reports/...` (`backend/lmanagement/urls.py:45`, `backend/apps/license/urls.py:56-57`). The readiness link uses `request_key` (first UUID segment), while the readiness lookup filters on `job.key`, which is `YYYYMMDD-HHMMSS_<8 hex>` (`backend/apps/license/views/ledger.py:61,225,367`).

## Key findings

1. **Broken export endpoint (VERIFIED, static).** `ExpiringLicenses.tsx:12`, `ActiveLicenses.tsx:12` and `components/reports/LicenseExportPanel.tsx` call `license/reports/...`. The client base is `/api/`, so the request is `/api/license/reports/...`. No backend route matches. Runtime 404 is SUSPECTED until run.
2. **Wrong identifier in readiness links (VERIFIED, static).** `LicenseDownloadRequestDetail.tsx:7` links to `/license-ledger/package-readiness/${r.request_key}`. The readiness route is keyed by `job.key`, which is never the 8-character request key. The link is expected to 404 (runtime SUSPECTED).
3. **Two overlapping reconciliation UIs, one unlinked.** `/reconciliation-issues` has no nav link and reads the same endpoints as `/reconciliation`.
4. **Dead modules.** `layout/Sidebar.tsx` and `components/GlobalErrorBoundary.tsx` have no importers. The `routes` export in `routes/config.js` is consumed only by the dead Sidebar.

## 1. Route definitions

Sources: `frontend/src/routes/AppRoutes.tsx`, `routes/ProtectedRoute.tsx:22-45`, `routes/authorizationRoles.ts:1-8`, `routes/config.js`.

Totals: 57 route entries (56 concrete paths and `*`), from 47 `<Route>` elements. `REPORT_ROUTES` (`AppRoutes.tsx:60-72`, applied at `:151-157`) expands 11 entries from one element. No nested routes or `<Outlet/>`.

Guards: 5 auth-only, 1 superuser (`/settings`), 12 `requiredRole`, 33 `requiredAnyRole` (22 literal and 11 reports), 6 unguarded. AdminLayout on 49 entries.

| # | Path | Page component | Guard (AppRoutes.tsx line) | Layout |
|---|---|---|---|---|
| 1 | `/login` | Login | none (:79) | none |
| 2 | `/forgot-password` | PasswordReset | none (:80) | none |
| 3 | `/401` | Unauthorized | none (:81) | none |
| 4 | `/403` | Forbidden | none (:82) | none |
| 5 | `/` | Navigate to `/dashboard` | auth (:85-92) | none |
| 6 | `/dashboard` | Dashboard | auth (:95-104) | AdminLayout |
| 7 | `/licenses` | MasterList | LICENSE_MANAGER, LICENSE_VIEWER (:107) | AdminLayout |
| 8 | `/licenses/create` | MasterForm | LICENSE_MANAGER (:112) | AdminLayout |
| 9 | `/licenses/:id/edit` | MasterForm | LICENSE_MANAGER (:117) | AdminLayout |
| 10 | `/planning` | LicensePlanningWorkspace | LICENSE_MANAGER (:122) | AdminLayout |
| 11 | `/allotments` | MasterList | ALLOTMENT_MANAGER, ALLOTMENT_VIEWER (:129) | AdminLayout |
| 12 | `/allotments/create` | MasterForm | ALLOTMENT_MANAGER (:134) | AdminLayout |
| 13 | `/allotments/:id/edit` | MasterForm | ALLOTMENT_MANAGER (:139) | AdminLayout |
| 14 | `/allotments/:id/allocate` | AllotmentAction | ALLOTMENT_MANAGER (:144) | AdminLayout |
| 15 | `/reports/parle/sion-e1` | SionE1 | REPORT_ROLES (:151-157, :61) | AdminLayout |
| 16 | `/reports/parle/sion-e5` | SionE5 | REPORT_ROLES (:62) | AdminLayout |
| 17 | `/reports/parle/sion-e126` | SionE126 | REPORT_ROLES (:63) | AdminLayout |
| 18 | `/reports/parle/sion-e132` | SionE132 | REPORT_ROLES (:64) | AdminLayout |
| 19 | `/reports/expiring-licenses` | ExpiringLicenses | REPORT_ROLES (:65) | AdminLayout |
| 20 | `/reports/active-licenses` | ActiveLicenses | REPORT_ROLES (:66) | AdminLayout |
| 21 | `/reports/download-license` | DownloadLicense | REPORT_ROLES (:67) | AdminLayout |
| 22 | `/reports/item-pivot` | ItemPivotReport | REPORT_ROLES (:68) | AdminLayout |
| 23 | `/reports/item-report` | ItemReport | REPORT_ROLES (:69) | AdminLayout |
| 24 | `/reports/planned-report` | PlannedReport | REPORT_ROLES (:70) | AdminLayout |
| 25 | `/reports/license-purchase-profit` | LicensePurchaseProfitReport | REPORT_ROLES (:71) | AdminLayout |
| 26 | `/bill-of-entries` | MasterList | BOE_MANAGER, BOE_VIEWER, TL_GENERATE, ACCOUNT_ACCESS (:161) | AdminLayout |
| 27 | `/bill-of-entries/create` | MasterForm | BOE_MANAGER (:166) | AdminLayout |
| 28 | `/bill-of-entries/:id/edit` | MasterForm | BOE_MANAGER (:171) | AdminLayout |
| 29 | `/bill-of-entries/:id/generate-transfer-letter` | BOETransferLetter | BOE_MANAGER, BOE_VIEWER, TL_GENERATE (:176) | AdminLayout |
| 30 | `/trades` | MasterList | TRADE_MANAGER, TRADE_VIEWER (:183) | AdminLayout |
| 31 | `/trades/create` | TradeForm | TRADE_MANAGER (:188) | AdminLayout |
| 32 | `/trades/:id/edit` | TradeForm | TRADE_MANAGER (:193) | AdminLayout |
| 33 | `/reconciliation` | ReconciliationPanel | BOE_MANAGER, TRADE_MANAGER, ACCOUNT_ACCESS (:200) | AdminLayout |
| 34 | `/reconciliation-issues` | ReconciliationIssues | TRADE_MANAGER, TRADE_VIEWER, BOE_MANAGER, BOE_VIEWER, ACCOUNT_ACCESS, TL_GENERATE (:208) | AdminLayout |
| 35 | `/incentive-licenses` | MasterList | INCENTIVE_LICENSE_MANAGER, INCENTIVE_LICENSE_VIEWER (:215) | AdminLayout |
| 36 | `/incentive-licenses/create` | MasterForm | INCENTIVE_LICENSE_MANAGER (:220) | AdminLayout |
| 37 | `/incentive-licenses/:id/edit` | MasterForm | INCENTIVE_LICENSE_MANAGER (:225) | AdminLayout |
| 38 | `/ledger-upload` | LedgerUpload | LICENSE_MANAGER, LEDGER_MANAGER (:232) | AdminLayout |
| 39 | `/license-ledger` | LicenseLedger | LICENSE_MANAGER, TRADE_MANAGER, TRADE_VIEWER, LEDGER_MANAGER (:237) | AdminLayout |
| 40 | `/license-ledger/download-requests` | LicenseDownloadRequests | same 4 roles (:242) | AdminLayout |
| 41 | `/license-ledger/download-requests/:requestId` | LicenseDownloadRequestDetail | same 4 roles (:247) | AdminLayout |
| 42 | `/license-ledger/package-readiness/:jobId` | LicenseLedgerPackageReadiness | LICENSE_MANAGER, TRADE_MANAGER, LEDGER_MANAGER (:252) | AdminLayout |
| 43 | `/license-ledger/:licenseId/:itemId` | LicenseLedgerDetail | same 4 roles (:257) | AdminLayout |
| 44 | `/license-ledger/:licenseId` | LicenseLedgerDetail | same 4 roles (:262) | AdminLayout |
| 45 | `/licenses/:id/overview` | LicenseOverviewPage | LICENSE_MANAGER, LICENSE_VIEWER, BOE and TRADE manager or viewer (:269) | AdminLayout |
| 46 | `/licenses/:id/balance` | RedirectToLicenseOverview | none (:274) | none |
| 47 | `/pdf-viewer` | PDFViewer | auth (:278) | none |
| 48 | `/settings` | Settings | requireSuperuser (:285) | AdminLayout |
| 49 | `/profile` | Profile | auth (:290) | AdminLayout |
| 50 | `/masters/:entity` | MasterList | auth (:297) | AdminLayout |
| 51 | `/masters/:entity/create` | MasterForm | USER_MANAGER (:302) | AdminLayout |
| 52 | `/masters/:entity/:id/edit` | MasterForm | USER_MANAGER (:307) | AdminLayout |
| 53 | `/admin/users` | UserList | USER_MANAGER (:314) | AdminLayout |
| 54 | `/admin/users/create` | UserForm | USER_MANAGER (:319) | AdminLayout |
| 55 | `/admin/users/:id/edit` | UserForm | USER_MANAGER (:324) | AdminLayout |
| 56 | `/admin/activity-log` | ActivityLog | USER_MANAGER (:329) | AdminLayout |
| 57 | `*` | NotFound | none (:335) | none |

Eager imports: Login, PasswordReset, Unauthorized, NotFound, Forbidden (`AppRoutes.tsx:9-14`). All others are lazy (`:16-51`).

`routes/config.js`: `routes` (:1-59, dead Sidebar only); `masterEntities` (:62-111; TopNav, CommandPalette, Sidebar); `reportEntities` (:113-139; TopNav, CommandPalette, Sidebar), listing 5 items.

## 2. API endpoints by page

Conventions: method and literal path, then file:line. Services are under `frontend/src/services/`. Full table is in the agent output; the principal calls are below.

| Page | Endpoints | Notes |
|---|---|---|
| Login | POST `/auth/login/` (`pages/Login.tsx:61`) | |
| PasswordReset | POST `/auth/password-reset/` (:23) | |
| Dashboard | GET `dashboard/` (:231) | |
| MasterList | GET DYNAMIC list: `licenses/`, `allotments/`, `trades/`, `incentive-licenses/`, `masters/${entity}/`; BOE list via `boeApi` → GET `bill-of-entries/`. Plus delete, patch, copy, merge, export (GET DYNAMIC), link-trade, update-invoice-no, fetch-ownership, download-ledger, generate-pdf | Serves 6 routes (D11). Mounts shared balance, planning, link-trade, ownership and transfer-letter modals. |
| MasterForm + `pages/masters/hooks/*` | Base DYNAMIC from `masterFormHelpers.ts:11-16`; PATCH and POST `bill-of-entries/`, `licenses/parse-pdf/`, `bill-of-entries/parse-pdf/`; GET `bill-of-entries/fetch-allotment-details/`; GET `masters/sion-classes/${norm_class}/`; POST `import-item-suggestion/` | Same component for create and edit routes. |
| LicensePlanningWorkspace | GET `masters/sion-classes/`; `services/api/planningRuleApi.ts`: CRUD `sion-planning-rules/`, POST `…/test/`, `plan-sion/`, `preview-sion/`, `preview-scoped/`, `save-scoped/`, `reorder/`, `plan-license/`; GET `sion-planning-rules/import-items/` | |
| AllotmentAction | GET `masters/notification-numbers/`, `item-report/available-items/`, `item-report/planned-item-names/`, `allotments/${id}/`, `allotment-actions/${id}/allocation-initialization/`, `…/available-licenses/`; POST `license-actions/${licenseId}/fetch-ownership/`, `allotment-actions/${id}/allocate-items/`; DELETE `…/delete-item/${allotmentItemId}/`; GET `…/generate-pdf/`, `licenses/${licenseId}/merged-documents/`; POST `allotments/${id}/copy/` | |
| BOETransferLetter / TransferLetterForm | GET `bill-of-entries/${id}/`, `masters/transfer-letters/`, `masters/companies/`; POST DYNAMIC `/{allotment-actions,trades,bill-of-entries}/${id}/generate-transfer-letter/` | Shared by three flows. |
| TradeForm | POST DYNAMIC `trades/${id}/${action}/`; GET `bill-of-entries/${boeId}/`, `trades/${id}/`, `incentive-licenses/${id}/`, `masters/companies/${id}/`, `trades/prefill-invoice-number/`, `trades/${id}/generate-bill-of-supply/`, `…/generate-purchase-invoice/`; PATCH and POST `trades/` | |
| ReconciliationPanel | GET `reconciliation/summary/`; POST `reconciliation/recalculate/`; GET `item-pivot/task-status/${taskId}/` (poll); tab GETs: `cif-comparison/`, `qty-comparison/`, `multi-boe/`, `multi-invoice/`, `missing-boe/`, `missing-invoice/`, `duplicate-debits/`, `duplicate-boes/`, `audit-log/`; POST `note/`, `link/`, `merge-boe/` | All exist in `backend/apps/reconciliation/views.py`. |
| ReconciliationIssues | GET `reconciliation/summary/` and six tab GETs | Read-only. Same endpoints as ReconciliationPanel (D2). |
| LedgerUpload | GET `ledger-task-status/${task_id}/`; POST `upload-ledger/` (multipart) | |
| LicenseLedger | GET `license-ledger/download-package/${jobId}/`, `license-wise/`, `summary/`, `${license_id}/`; POST `license-ledger/download-package/`, `download-package-pdf/`, `download-package/${jobId}/retry/`; GET `export/` (pdf and xlsx), `${licenseId}/custom-ledger-pdf/` | |
| LicenseLedgerDetail | GET `license-ledger/${licenseId}/ledger_detail/?company=` | Backend action at `backend/apps/license/views/ledger.py:570`. |
| LicenseLedgerPackageReadiness | GET `license-ledger/download-package/${jobId}/readiness/`; POST DYNAMIC action; POST `trades/${saleId}/sales-classification-review/`; POST purchase-trade `upload/` and `recover-orphan/` | `jobId` = job key. |
| LicenseDownloadRequests | GET `license-ledger/download-requests/`; POST `…/${id}/retry/` | |
| LicenseDownloadRequestDetail | GET `license-ledger/download-requests/${id}/`; POST `…/retry/`; blob GET DYNAMIC `downloadUrl` | Readiness link uses `request_key` (Key finding 2). |
| LicenseOverviewPage (+ folder) | GET `licenses/${id}/`, `…/balance-pdf/`, `…/overview-summary/`, `…/overview-allotments/`, `…/overview-boes/`, `…/overview-invoice-ledger/`, `…/overview-items/`, `…/replan-status/`; GET `balance-ledger/`; PATCH `licenses/${id}/`; POST `…/recalculate/`, `…/auto-plan/`, `…/hide-boe/`, `…/hide-boe-bulk/`, `…/restore-boe/`, `…/restore-boe-bulk/` | |
| PDFViewer | GET DYNAMIC from `?url=` (`pages/pdfApiPath.ts:1-6` rejects absolute URLs, `//`, backslash, control chars) | Any relative API path is accepted. |
| Settings | GET `auth/users/available-roles/`, `auth/users/`, `mds/status/`; PUT, POST, DELETE `auth/users/…` | Inline calls, not via `api/users.js`. |
| Profile | POST `/auth/change-password/` (via ChangePasswordForm) | |
| UserList / UserForm (`api/users.js`) | CRUD `auth/users/`; POST `auth/users/${id}/reset-password/`; GET `auth/users/available-roles/` | |
| ActivityLog | GET `masters/activity-logs/` | |
| ItemPivotReport | GET `item-pivot/available-norms/`, DYNAMIC `reports/item-pivot/?…`, `item-pivot/task-status/${taskId}/`; POST `item-pivot/update-balance/` | |
| ItemReport / PlannedReport | GET `item-report/available-items/`, DYNAMIC `reports/item-report/?format=json…`, `planned-report/available-items/`, `reports/planned-report/?…`, `masters/notification-numbers/`; PATCH `license-items/${id}/`, `licenses/${id}/` | |
| LicensePurchaseProfitReport | GET DYNAMIC `reports/license-purchase-profit/?…` | |
| SionE1 / E5 / E126 / E132 (via SionNormReport) | GET DYNAMIC `licenses/active-dfia-report/?…` | Four wrappers differ only in props. |
| ExpiringLicenses, ActiveLicenses | GET `license/reports/expiring-licenses/?format=excel&days=N`, `license/reports/active-licenses/?…` | **No backend route matches** (Key finding 1). |
| DownloadLicense | GET `reports/expiring-licenses/?days=N`, `reports/active-licenses/?days=N`; POST `licenses/bulk-balance-excel/` (blob) | These match backend routes. |
| Shared: LicenseBalanceModal | PATCH `licenses/${id}/`; GET `…/item-usage/`, `masters/item-names/`, `…/balance-pdf/`, `…/balance-excel/`, `…/merged-documents/`; PATCH `license-items/${id}/` | Mounted by MasterList, MasterForm, LicensesTable, BalanceTab, LedgerTab. |
| Shared: PlanningEditor / LicensePlanningPanel | GET `licenses/${id}/`, `license-item-plans/`; POST `license-item-plans/bulk-upsert/`, `licenses/${id}/auto-plan/`; DELETE `license-item-plans/${planId}/` | |
| Global: AuthContext | GET `auth/me/`; POST `auth/logout/` | |
| Global: api client | POST `auth/refresh/` | |
| Global: TaskDrawer (every AdminLayout page) | GET `tasks/` (gated by `enabled: show`), GET `tasks/assignable-users/`, POST/PATCH/DELETE `tasks/…` | |

## 3. Shared infrastructure

| Concern | File | Description |
|---|---|---|
| Axios client | `api/axios.js` | `baseURL` `${VITE_API_URL}/api/` or `/api/` (:8-9). Bearer token and CSRF header (:29-39). GET coalescing (:43-83). Refresh queue (:123-151). 401 refresh-and-replay for GET/HEAD/OPTIONS only (:174-188). 5xx retry twice for replay-safe requests (:202-211). |
| Query client | `api/queryClient.ts` (:3-10) | staleTime 30 s, retry 1. |
| Auth context | `context/AuthContext.tsx` | Idle logout after 30 min. Access refresh 5 min before expiry. Superusers bypass role checks. |
| Route guard | `routes/ProtectedRoute.tsx:22-45` | Unauthenticated to `/login`; failed role to `/403`. |
| Error boundary (live) | `components/ErrorBoundary.tsx`, mounted in `App.tsx:19` | Wraps `AppRoutes` only; providers sit outside it. |
| Error boundary (dead) | `components/GlobalErrorBoundary.tsx` | Never imported. |
| Lazy loading | `utils/lazyLoad.js:17-70` | 3 retries on chunk errors; one hard reload per session on stale chunks. |
| Layout | `layout/AdminLayout.tsx:16-90` | TopNav, quick-action footer, TaskFAB. |
| Navigation | `components/TopNav.tsx` (`NAV_GROUPS` :15-37), `components/CommandPalette.tsx` (:33-79), `layout/AdminLayout.tsx:9-14` | `config.js` feeds TopNav and CommandPalette (masters and reports) and dead Sidebar. |

## 4. Duplicate or overlapping pages

| # | Candidates | Evidence | Label |
|---|---|---|---|
| D1 | `/settings` vs `/admin/users*` | Same `auth/users/` CRUD, different gating (superuser vs USER_MANAGER). | VERIFIED |
| D2 | `/reconciliation` vs `/reconciliation-issues` | Same summary and six tab endpoints. Issues page not linked. | VERIFIED |
| D3 | `/reports/expiring-licenses`, `/reports/active-licenses` vs `/reports/download-license` | Different prefixes: `license/reports/…` (broken) vs `reports/…`. Purpose overlap inferred. | VERIFIED (endpoints); SUSPECTED (purpose) |
| D4 | "License Downloads" nav vs "Download License" page | Near-identical names. | SUSPECTED |
| D5 | SionE1, E5, E126, E132 | Thin wrappers around `SionNormReport`. One parametric route would do. | VERIFIED |
| D6 | Auto-plan entry points (`/planning`, overview planning tab, LicensesTable, PlanningEditor) | All call `POST licenses/${id}/auto-plan/`. | VERIFIED |
| D7 | `/licenses/:id/overview` vs `/license-ledger/:licenseId` | Both show per-licence ledger and balance through different endpoints. | SUSPECTED |
| D8 | `components/licenseBalanceHelpers.ts` vs `pages/license-balance/licenseBalanceHelpers.ts` | Same filename, different contents, both live. | VERIFIED |
| D9 | `components/StatCard.tsx` vs `pages/license-overview/StatCard.tsx` | Name collision. Not compared. | SUSPECTED |
| D10 | `TradeTransferLetter.tsx` vs `BOETransferLetter.tsx` | Near-identical. Only BOE is routed; trade is reached via `TransferLetterModal`. | VERIFIED |
| D11 | MasterList across six routes | Intentional reuse. | VERIFIED (by design) |
| D12 | Forbidden, Unauthorized, NotFound, ServerError | Identical `ErrorScreen` wrappers. ServerError orphaned. | VERIFIED |

## 5. Dead routes and dead code

### 5a. Routes not reachable from nav or in-app links

| Route | Status | Evidence |
|---|---|---|
| `/reports/parle/sion-e1`, `sion-e5`, `sion-e126`, `sion-e132` | VERIFIED URL-only | Not in any nav registry or `navigate`/`Link`. |
| `/reports/expiring-licenses`, `/reports/active-licenses` | VERIFIED URL-only | Also has the endpoint defect. |
| `/reports/download-license` | VERIFIED URL-only | Only `hooks/usePageTitle.js:40`. |
| `/reconciliation-issues` | VERIFIED URL-only | Route line and page only. |
| `/pdf-viewer` | VERIFIED URL-only | Doc comment only. |
| `/401` | VERIFIED URL-only | ProtectedRoute redirects to `/login` instead. |
| `/bill-of-entries/:id/generate-transfer-letter` | SUSPECTED dead route; component live | Reached through `TransferLetterModal.tsx`. |

`/licenses/:id/balance` is a legacy redirect, linked from `MasterForm.tsx:1101`. `/forgot-password` is linked from `Login.tsx:211`.

### 5b. Dead code

| File | Status | Evidence |
|---|---|---|
| `layout/Sidebar.tsx` | VERIFIED dead | No importers. Data from `routes/config.js`, whose entries name `LicensePage` and `AllotmentPage`, which do not exist (`config.js:12,19`). |
| `components/GlobalErrorBoundary.tsx` | VERIFIED dead | Not imported. |
| `pages/errors/ServerError.tsx` | VERIFIED dead | No importer and no route. |
| `components/AllotmentFormModal.tsx` | VERIFIED dead | No importers. Contains 6 API calls. |
| `pages/masters/tables/BalanceTab.tsx` | VERIFIED dead | No importers. Contains 2 API calls. |
| `pages/planning/ResidualPolicyEditor.tsx` | VERIFIED dead | No importers. |
| `services/api/masterApi.js`, `services/api/allotmentApi.js` | VERIFIED dead | Re-exported only by `services/api/index.js`. |
| Test-only modules (`QuantityUtilization.tsx`, `dashboardContract.ts`, `ledgerUploadHelpers.ts`, `allocationMath.ts`, `balanceMetricContract.ts`, `planningPath.ts`) | VERIFIED | Imported only by tests. |
| `dist/assets/js/AccountingDashboard-*.js`, `AccountingSettings-*.js` | VERIFIED stale | Build output with no source. |

## Limits

Static analysis only. No dev server, browser or API request was used. Dynamic paths were resolved by reading, not execution. Route counts are from grep and read.
