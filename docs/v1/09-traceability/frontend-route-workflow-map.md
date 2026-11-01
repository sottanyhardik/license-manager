# Frontend route workflow map

**Evidence scope.** This register reconciles every `UI-*` row in the generated [frontend route register](frontend-route-register.tsv) with its routed component, static client-side gate, and the frontend's directly visible API-client calls. It was derived from `frontend/src/routes/AppRoutes.tsx` and the listed component/service sources on 2026-10-31. Two rows now also contain a narrowly scoped, read-only running-application observation; all other entries remain static source evidence. None is server-authorization proof or a completed API contract. `ProtectedRoute` redirects an unauthenticated user to `/login` and a client-side role failure to `/403`; it is a usability guard, not an authorization boundary.

`S` means static source evidence; `T` names a current frontend component or E2E test; `—` means no route-specific test was found in this pass. Every row remains **Partial** until its backend operation IDs, server permission result, request/response/error contract and browser state are reconciled.

## Shared state evidence and acceptance gate

`AppRoutes` wraps lazy pages in `Suspense` with `PageLoader` (`role=status`, "Loading"). `ProtectedRoute` itself renders a plain `Loading...` text while the auth context loads, and redirects denied users. `ErrorBoundary` is global recovery only (console logging plus refresh instruction); it does not establish route-level retry/error behavior. The individual page source below provides static evidence of calls, local loading/error/empty branches where present; no live-browser result is claimed unless a named E2E test exists.

For each row, the V1 acceptance requirement is: prove the listed API calls against their exact `API-*` operation records, exercise allowed and denied server responses, and demonstrate loading, empty, validation, success and failure states in an authenticated browser test. Export/download rows additionally require a protected-file authorization test.

| ID / route | Routed page and client gate (S) | API/client dependency evidence (S) | State/test evidence | V1 action / priority / status |
| --- | --- | --- | --- | --- |
| UI-001 `/reports/parle/sion-e1` | `SionE1`; `REPORT_ROLES` | `SionNormReport` uses its E1 report path via Axios | Page local state; `SionNormReport.test.tsx`; no browser result | Contract-test report response/export and role denial; P1; Partial |
| UI-002 `/reports/parle/sion-e5` | `SionE5`; `REPORT_ROLES` | `SionNormReport` uses its E5 report path via Axios | Same shared component/test | Same as UI-001; P1; Partial |
| UI-003 `/reports/parle/sion-e126` | `SionE126`; `REPORT_ROLES` | `SionNormReport` uses its E126 report path via Axios | Same shared component/test | Same as UI-001; P1; Partial |
| UI-004 `/reports/parle/sion-e132` | `SionE132`; `REPORT_ROLES` | `SionNormReport` uses its E132 report path via Axios | Same shared component/test | Same as UI-001; P1; Partial |
| UI-005 `/reports/expiring-licenses` | `ExpiringLicenses`; `REPORT_ROLES` | `GET license/reports/expiring-licenses/?format=excel&days=` | `ExpiringLicenses.test.tsx`, `LicenseExportPanel.test.tsx` | Verify download authorization, zero results and blob failure; P1; Partial |
| UI-006 `/reports/active-licenses` | `ActiveLicenses`; `REPORT_ROLES` | `GET license/reports/active-licenses/?format=excel&days=` | `ActiveLicenses.test.tsx`, shared panel test | Verify download authorization, zero results and blob failure; P1; Partial |
| UI-007 `/reports/download-license` | `DownloadLicense`; `REPORT_ROLES` | `GET reports/{active|expiring}-licenses/`; `POST licenses/bulk-balance-excel/` | Local loading/error; `DownloadLicense.test.tsx` | Bind both endpoint variants and invalid/bulk input errors; P1; Partial |
| UI-008 `/reports/item-pivot` | `ItemPivotReport`; `REPORT_ROLES` | item-pivot report, `item-pivot/update-balance/`, task-status, master options | Local loading/error; `ItemPivotReport.render.test.tsx`, `item-pivot.sticky.spec.ts`, responsive E2E | Contract-test update task and server denial; P1; Partial |
| UI-009 `/reports/item-report` | `ItemReport`; `REPORT_ROLES` | item-report JSON/export, `item-report/available-items/`, `PATCH license-items/:id/` | Local loading/empty; item-report unit tests, responsive E2E | Separate report-read from inline mutation policy; P1; Partial |
| UI-010 `/reports/planned-report` | `PlannedReport`; `REPORT_ROLES` | planned-report JSON/export, `planned-report/available-items/` | Local loading/empty via shared hook | Add route/component and API failure tests; P1; Partial |
| UI-011 `/reports/license-purchase-profit` | `LicensePurchaseProfitReport`; `REPORT_ROLES` | purchase-profit report API via `useLicensePurchaseProfitReportData` | Local loading/empty; `LicensePurchaseProfitReport.test.tsx`, responsive E2E | Freeze calculation/provenance and denied/export tests; P1; Partial |
| UI-012 `/login` | `Login`; public | `POST /auth/login/` | Running-app observation: labelled username/password fields, visibility control, reset link and submit control rendered (read-only; 2026-10-31); `Login.test.tsx`, login visual/a11y E2E | Verify refresh/session failure, throttling and redirect behavior; P1; Partial |
| UI-013 `/forgot-password` | `PasswordReset`; public | `POST /auth/password-reset/` | Local success/error source; — | Add generic-response/no-account-enumeration test; P1; Partial |
| UI-014 `/401` | `Unauthorized`; public | None (static error screen) | Static only; — | Test navigation and recovery wording; P2; Partial |
| UI-015 `/403` | `Forbidden`; public | None (static error screen) | Static only; — | Test client redirect and server-denied origin context; P1; Partial |
| UI-016 `/` | protected redirect | No page call; redirects to `/dashboard` | `ProtectedRoute` source | Test unauthenticated and post-login redirect; P2; Partial |
| UI-017 `/dashboard` | `Dashboard`; authenticated | `GET dashboard/` | Local loading/error; `Dashboard.test.tsx`, contract test, authenticated-shell responsive E2E | Contract metrics/as-of time and denied/error behavior; P1; Partial |
| UI-018 `/licenses` | `MasterList`; LICENSE_MANAGER or LICENSE_VIEWER | Dynamic `apiPath` for licence list; actions include ownership, downloads and mutations | `MasterList.smoke.test.tsx`; responsive/data E2E | Split read/list actions from manager actions; P1; Partial |
| UI-019 `/licenses/create` | `MasterForm`; LICENSE_MANAGER | Dynamic licence metadata/create; `POST licenses/parse-pdf/` where used | `MasterForm.smoke.test.tsx`; responsive E2E only | Test upload/parse validation and create error recovery; P1; Partial |
| UI-020 `/licenses/:id/edit` | `MasterForm`; LICENSE_MANAGER | Dynamic licence detail/update; parse/document calls | Shared form test | Contract permission/object scope and stale update behavior; P1; Partial |
| UI-021 `/planning` | `LicensePlanningWorkspace`; LICENSE_MANAGER | SION rule CRUD/preview/plan endpoints; `GET masters/sion-classes/`; `POST licenses/:id/auto-plan/` | Loading/error source; `LicensePlanningWorkspace.test.tsx` | Test plan/replan side effects, conflicts and policy D3; P0/P1; Partial |
| UI-022 `/allotments` | `MasterList`; ALLOTMENT_MANAGER or ALLOTMENT_VIEWER | Dynamic allotment list plus copy/PDF actions | Shared list source; responsive/data E2E | Separate viewer-safe list/export from mutation controls; P1; Partial |
| UI-023 `/allotments/create` | `MasterForm`; ALLOTMENT_MANAGER | Dynamic allotment create and supporting master options | Shared form source | Test invalid capacity and form/server validation; P1; Partial |
| UI-024 `/allotments/:id/edit` | `MasterForm`; ALLOTMENT_MANAGER | Dynamic allotment detail/update | Shared form source | Contract live-CIF/stale edit failure; P1; Partial |
| UI-025 `/allotments/:id/allocate` | `AllotmentAction`; ALLOTMENT_MANAGER | allotment detail, allocation initialization/available licences, allocate/delete/copy/PDF, ownership and docs | Local loading/error; `AllotmentAction.test.tsx`, data E2E | Characterize allocation/release concurrency and exact manager denial; P0/P1; Partial |
| UI-026 `/bill-of-entries` | `MasterList`; BOE roles/TL_GENERATE/ACCOUNT_ACCESS | Dynamic BOE list; dispute/product-name/bulk update actions | Running-app observation: shell, search, filters, active-filter removal, exports, create, row actions, pagination and updating status rendered (read-only; 2026-10-31); shared list source; responsive/data E2E | Contract which listed roles may invoke each action; P1; Partial |
| UI-027 `/bill-of-entries/create` | `MasterForm`; BOE_MANAGER | Dynamic BOE create; `POST bill-of-entries/parse-pdf/` | Shared form source | Verify file validation/parse failure and draft recovery; P1; Partial |
| UI-028 `/bill-of-entries/:id/edit` | `MasterForm`; BOE_MANAGER | Dynamic BOE get/patch; allotment details support | Shared form source | Test correction/visibility effects and races; P1; Partial |
| UI-029 `/bill-of-entries/:id/generate-transfer-letter` | `BOETransferLetter`; BOE/TL roles | `GET bill-of-entries/:id/` (transfer generation follows page workflow) | Local error source; — | Map generated-document endpoint/download policy; P1; Partial |
| UI-030 `/trades` | `MasterList`; TRADE_MANAGER or TRADE_VIEWER | `GET trades/`; link/approve/reject/delete/download actions conditionally exposed | `MasterList.trades.test.tsx`; trade a11y/performance E2E | Contract viewers versus managers and action confirmations; P1; Partial |
| UI-031 `/trades/create` | `TradeForm`; TRADE_MANAGER | `POST trades/`; BOE/licence/company lookup; invoice prefill | Loading/error source; `TradeForm.smoke.test.tsx` | Test invoice/purchase/sale validation and idempotency; P1; Partial |
| UI-032 `/trades/:id/edit` | `TradeForm`; TRADE_MANAGER | `GET/PATCH trades/:id/`; action and PDF endpoints | Shared form test | Test correction/reversal effects on financial balance; P0/P1; Partial |
| UI-033 `/reconciliation` | `ReconciliationPanel`; BOE_MANAGER, TRADE_MANAGER or ACCOUNT_ACCESS | `GET reconciliation/summary/`; `POST reconciliation/recalculate/`; task status | Local loading/error; `ReconciliationPanel.smoke.test.tsx`, data E2E | Map tab mutations and exact pair-role policy; P1; Partial |
| UI-034 `/reconciliation-issues` | `ReconciliationIssues`; read roles | `GET reconciliation/summary/` plus tab queries | Local loading/error; — | Prove portfolio read policy and empty/error behavior; P1; Partial |
| UI-035 `/incentive-licenses` | `MasterList`; incentive roles | Dynamic incentive-licence list | Shared list source | Map exact master endpoint and read/mutation gates; P1; Partial |
| UI-036 `/incentive-licenses/create` | `MasterForm`; INCENTIVE_LICENSE_MANAGER | Dynamic incentive-licence create | Shared form source | Add required-field/error test; P2; Partial |
| UI-037 `/incentive-licenses/:id/edit` | `MasterForm`; INCENTIVE_LICENSE_MANAGER | Dynamic incentive-licence get/update | Shared form source | Map data effects and server object scope; P2; Partial |
| UI-038 `/ledger-upload` | `LedgerUpload`; LICENSE_MANAGER or LEDGER_MANAGER | `POST upload-ledger/`; `GET ledger-task-status/:id/` | Local progress/error; `LedgerUpload.test.tsx` | Test file validation, asynchronous retry/cancel and download policy; P1; Partial |
| UI-039 `/license-ledger` | `LicenseLedger`; listed ledger roles | licence-wise/summary/detail ledger reads; export/package creation/download services | Local loading/error; `LicenseLedger.test.tsx`, ledger/package E2E | Contract filtering, package idempotency and export authorization; P1; Partial |
| UI-040 `/license-ledger/download-requests` | `LicenseDownloadRequests`; listed ledger roles | `GET/POST license-ledger/download-requests/` | Service source; — | Test list pagination/create/idempotency and owner scope; P1; Partial |
| UI-041 `/license-ledger/download-requests/:requestId` | `LicenseDownloadRequestDetail`; listed ledger roles | `GET request/:id/`; `POST :id/retry/`; protected blob download | Service source; — | Negative owner/download/retry policy tests; P1; Partial |
| UI-042 `/license-ledger/package-readiness/:jobId` | `LicenseLedgerPackageReadiness`; manager/trade/ledger roles | package job status/actions; classification/recovery/upload services | Service source; — | Test state machine, retry and owner/object scope; P1; Partial |
| UI-043 `/license-ledger/:licenseId/:itemId` | `LicenseLedgerDetail`; listed ledger roles | ledger item read/export service | Local loading/error; three `LicenseLedgerDetail.*.test.tsx` suites | Confirm item belongs to licence and server denial; P1; Partial |
| UI-044 `/license-ledger/:licenseId` | `LicenseLedgerDetail`; listed ledger roles | Same component; licence-scoped ledger read/export | Same unit suites | Same as UI-043; P1; Partial |
| UI-045 `/licenses/:id/overview` | `LicenseOverviewPage`; licence/BOE/trade roles | licence, overview summary/items/BOEs/allotments/invoice ledger, balance-PDF, replan/SION, hide/restore BOE | Local query/error states; documents unit test, licence a11y/data E2E | Prove dual-balance provenance, mutation guards and tab failures; P0/P1; Partial |
| UI-046 `/licenses/:id/balance` | redirect; no gate wrapper | No API; redirects to UI-045 preserving query | `license-overview.accessibility.spec.ts` | Preserve bookmark redirect; P2; Verified redirect only |
| UI-047 `/pdf-viewer` | `PDFViewer`; authenticated | Axios GET of allowlisted/normalized requested protected file | Local loading/error; `PDFViewer.test.tsx`, document security tests | Test server file ACL and malformed URL denial; P1; Partial |
| UI-048 `/settings` | `Settings`; superuser | available roles; `GET/POST/PUT/DELETE auth/users/`; MDS status card | Local loading/error source; — | Reconcile duplicate user admin with UI-053–055; server superuser policy test; P1; Partial |
| UI-049 `/profile` | `Profile`; authenticated | `PATCH /auth/me/` | Local submit/error; `Profile.test.tsx` | Test self-only and validation/server errors; P2; Partial |
| UI-050 `/masters/:entity` | `MasterList`; authenticated client-side | Dynamic `masters/:entity/` metadata/list path | `MasterList.smoke.test.tsx` | Enumerate entity allowlist and backend permissions; P1; Partial |
| UI-051 `/masters/:entity/create` | `MasterForm`; USER_MANAGER | Dynamic master metadata/create and related lookup paths | `MasterForm.smoke.test.tsx` | Verify per-entity create policy, not just generic UI role; P1; Partial |
| UI-052 `/masters/:entity/:id/edit` | `MasterForm`; USER_MANAGER | Dynamic master detail/update and related lookup paths | Shared form test | Verify per-entity update/object policy; P1; Partial |
| UI-053 `/admin/users` | `UserList`; USER_MANAGER | users API module: list/filter/delete actions | `UserList.test.tsx`, responsive E2E | Contract user-manager versus superuser capabilities; P1; Partial |
| UI-054 `/admin/users/create` | `UserForm`; USER_MANAGER | users API module create/role fields | `UserForm.test.tsx` | Test role assignment/escalation controls; P1; Partial |
| UI-055 `/admin/users/:id/edit` | `UserForm`; USER_MANAGER | users API module get/update/role fields | `UserForm.test.tsx` | Test self/privileged-user edit constraints; P1; Partial |
| UI-056 `/admin/activity-log` | `ActivityLog`; USER_MANAGER | `GET masters/activity-logs/` with filters | Local loading/error; — | Verify audit-read scope, pagination and async durability notice; P2; Partial |
| UI-057 `*` | `NotFound`; public fallback | None | Static only; — | Test unknown route and no sensitive route disclosure; P2; Partial |

## Reconciled counts

| Measure | Count | Meaning |
| --- | ---: | --- |
| Declared route expressions | 57 | Matches the generated register exactly. |
| Routes with a routed component and client gate recorded | 57 | Static `AppRoutes` evidence only. |
| Routes with a frontend API dependency/disposition recorded | 57 | Direct Axios/service call, redirect/no-call, or a documented dynamic dependency. |
| Routes with named unit/component/E2E evidence | 38 | A named test is not proof of endpoint contract or browser execution in this audit. |
| Routes with observed running-application UX evidence | 0 | No local browser session was run for this audit. |
| Completed server endpoint contracts | 0 | Endpoint/action-level authorization, response/error and consumer reconciliation is still an M1 gate. |

The former unqualified route/API gap is now bounded at the route-client boundary. It does **not** reduce the separate 354-operation API action audit requirement.
