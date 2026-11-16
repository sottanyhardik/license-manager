# Frontend architecture audit (read-only)

Date 2026-11-16. Scope `frontend/` (React 19.2, TS 5.9, rolldown-vite 7.2.2, Tailwind v4, shadcn/Radix, TanStack Query 5, react-router-dom 7.9). No source modified. Builds on `docs/modernization/FRONTEND_STRUCTURE.md`; section 0 lists what is now stale. Evidence is `file:line` or the command named. `npm run build` was run (output in section 10); tests, lint and typecheck were NOT run.

## 0. Corrections to FRONTEND_STRUCTURE.md

| Stale statement | Now |
|---|---|
| `api/` has 5 files (`axios.js`, `queryClient.ts`, `tasks.js`, `users.js`); wrappers live in untyped `services/api/*.js` | `src/api/` has 13 files: `axios.js`, `queryClient.ts`, `index.ts`, and typed `allotmentApi.ts`, `boeApi.ts`, `licenseApi.ts`, `masterApi.ts`, `mdsApi.ts`, `planningRuleApi.ts`, `tasks.ts`, `users.ts` (+2 tests). Commit 40198342. `services/api/*.ts` are 2-3 line deprecated shims (`services/api/index.ts:1` "Deprecated shim: moved to `@/api`") |
| `routes/config.js`; only `REPORT_ROLES` imported from `authorizationRoles.ts`; other role arrays inline | `routes/config.ts` (typed). `authorizationRoles.ts:7-53` is the single typed source (`ROLES` const, `Role` type, 14 named role sets); `AppRoutes.tsx:14-30` imports them all, no inline literals remain. `ProtectedRoute` props typed with `Role` (`ProtectedRoute.tsx:6-11`). Commits 40198342, b68ec7fd |
| 33 `.js` files under `src/` | 24 `.js` (349 `.ts/.tsx`, 379 files total) |
| `AppRoutes.tsx` 339 lines | 355 lines; 45 `<Route>` literals + 11 mapped report routes = 56 rendered routes |
| `layout/Sidebar.tsx` listed as part of the shell | Sidebar is orphaned: no importer (`grep Sidebar src` outside its own file and `ui/sidebar` is empty; `dependents.tsv` lists only Sidebar's own imports). The live nav is `components/TopNav.tsx` (384 lines) |
| `ErrorBoundary` vs `GlobalErrorBoundary` | `GlobalErrorBoundary.tsx` has no importer; only `ErrorBoundary` is mounted (`App.tsx:19`) |
| `AllotmentFormModal` listed as a live modal | zero importers outside its own file |
| 78 test files | 79 unit test files, 440 `it/test` blocks |
| 107 files import `api/axios`; 25 import wrappers | 82 non-test files import `api/axios` (8 inside `src/api`); 16 files outside `src/api` import typed wrapper modules (section 4) |

## 1. Current tree with counts (`find src -type f`)

| Dir | Files | Notes |
|---|---|---|
| `pages/` | 201 | 44 at root (incl. 16 tests); `admin` 5, `auth` 1, `errors` 3, `license-balance` 7, `license-overview` 32, `masters` 32, `planning` 16, `reconciliation` 10, `reports` 50, `settings` 1 |
| `components/` | 74 | 46 at root, `ui` 18 (shadcn), `planning` 3, `reports` 3, `primitives` 2, `filters` 1, `motion` 1 |
| `utils/` | 27 | |
| `hooks/` | 14 | `index.js` barrel; `useApiCall`, `useModal`, `useToast`, `usePagination`, `useDebounce` are `.js` |
| `api/` | 13 | typed endpoint wrappers + axios client + queryClient |
| `services/` | 13 | `services/api/` shims 7; ledger download helpers 6 |
| `types/` | 8 | `canonicalLedger.ts`, `reportEnvelope.ts`, `index.ts`, `api/` |
| `test/` + `tests/` | 5 + 2 | `test/setup.ts` wired in `vitest.config.ts`; `tests/` leftover |
| `context/` 3, `routes/` 5, `layout/` 2, `lib/` 2, `theme/` 2, `styles/` 1, `assets/` 1 | | |

Largest files (LOC, `wc -l`): ItemPivotReport 1951, AllotmentAction 1833, masters/MasterList 1730, TradeForm 1644, masters/tables/LicensesTable 1444, components/planning/PlanningEditor 1268, masters/tables/LedgerTab 1162, masters/MasterForm 1137, LicenseLedger 1078, Dashboard 872, masters/NestedFieldArray 840, reports/LicensePurchaseProfitReport 699, LicenseLedgerDetail 680, Settings 672, masters/hooks/useMasterFormSubmit 642, LedgerUpload 633. `LicenseDownloadRequests.tsx` (15 lines) and `LicenseDownloadRequestDetail.tsx` (7 lines) are minified single-line JSX.

TS config: `strict:false`, `allowJs:true`, `checkJs:false` (`tsconfig.json:19-23`).

## 2. App shell

Provider order (`main.tsx`, `App.tsx:14-31`):
`StrictMode > QueryClientProvider(queryClient) > App > ThemeProvider > AuthProvider > ParsingStatusProvider > BrowserRouter > Toaster(3500ms) + ErrorBoundary > AppRoutes`. Query devtools lazy-loaded only if `import.meta.env.DEV` (`main.tsx:19-21`). CSS order: `index.css`, `theme/tabler.css`, `styles/tailwind.css`. `main.tsx:10` keeps a stale "Bootstrap Icons" comment.

Layout is not a layout route. `AdminLayout` (`layout/AdminLayout.tsx`, 90 lines, `children` untyped) is wrapped inside each `<Route element>` (45 times in `AppRoutes.tsx`). It renders: `TopNav` (hidden when running in an iframe, `:18-26`), `<main id="main-content">`, an `aria-live` `#form-announcements` region (`:36-42`), a sticky footer with `ParsingStatusDisplay` and 4 hard-coded quick-action buttons (`QUICK_ACTIONS`, `:9-14`: New License, New Allotment, New BOE, Reports; not role-gated, so a viewer sees "New License" and is sent to `/403`), and `TaskFAB` (`:87`).

`TopNav` (`components/TopNav.tsx`): two role-filtered groups `NAV_GROUPS` (`:18-39`): Licenses (Licenses, Auto Plan, Incentive Licenses, License Ledger, Ledger Upload) and Operations (Allotments, Bill of Entry, Trade In & Out, Reconciliation); a Reports menu gated by `hasAnyRole(REPORT_ROLES)` (`:226`, `:356`); an admin menu gated by superuser or `USER_ADMIN_ROLES` (`:303`); `CommandPalette` lazy (`:15`). Role filter uses `hasAnyRole` (`:150`). Routes not in the nav groups: `/dashboard`, `/reconciliation-issues`, `/license-ledger/download-requests` (only through `reportEntities`, `routes/config.ts:136-141`, and a link at `LicenseLedger.tsx:580`), `/masters/*`.

## 3. Routing (`routes/AppRoutes.tsx`, 355 lines)

Single `<Suspense fallback={<PageLoader/>}>` around all `<Routes>` (`:92`). `ProtectedRoute` (`ProtectedRoute.tsx:23-46`): bare `"Loading..."` div while auth loads, `/login` (with `state.from`) if no user, `/403` for a failed superuser/role/any-role check. Superuser bypasses role checks (`AuthContext.tsx:240-248`).

Lazy loading: 33 lazy pages, 19 via `lazyLoadWithRetry` (`utils/lazyLoad.js:17`, 3 retries) and 14 via plain `React.lazy` (SionE1/E5/E126/E132, ExpiringLicenses, ActiveLicenses, DownloadLicense, TradeForm, LedgerUpload, LicenseLedger, LicenseLedgerDetail, LicenseOverviewPage, LicensePlanningWorkspace, PDFViewer). Eager: Login, PasswordReset, Unauthorized, NotFound, Forbidden (`:9-13`).

| Path (line) | Page | Guard |
|---|---|---|
| `/login` (95), `/forgot-password` (96), `/401` (97), `/403` (98) | Login, PasswordReset, Unauthorized, Forbidden | public |
| `/` (101) | redirect `/dashboard` | authenticated |
| `/dashboard` (111) | Dashboard | authenticated |
| `/licenses` (123) | MasterList | `LICENSE_ROLES` (manager, viewer) |
| `/licenses/create` (128), `/licenses/:id/edit` (133) | MasterForm | `LICENSE_MANAGER` |
| `/licenses/:id/overview` (284) | LicenseOverviewPage | `LICENSE_OVERVIEW_ROLES` (license, BOE, trade managers and viewers) |
| `/licenses/:id/balance` (290) | `RedirectToLicenseOverview` | none (redirect only) |
| `/planning` (138) | LicensePlanningWorkspace | `LICENSE_MANAGER` |
| `/allotments` (145) | MasterList | `ALLOTMENT_ROLES` |
| `/allotments/create` (150), `/:id/edit` (155) | MasterForm | `ALLOTMENT_MANAGER` |
| `/allotments/:id/allocate` (160) | AllotmentAction | `ALLOTMENT_MANAGER` |
| `/bill-of-entries` (176) | MasterList | `BOE_LIST_ROLES` (BOE mgr/viewer, TL_GENERATE, ACCOUNT_ACCESS) |
| `/bill-of-entries/create` (181), `/:id/edit` (186) | MasterForm | `BOE_MANAGER` |
| `/bill-of-entries/:id/generate-transfer-letter` (191) | BOETransferLetter | `BOE_TRANSFER_LETTER_ROLES` |
| `/trades` (198) | MasterList | `TRADE_ROLES` |
| `/trades/create` (203), `/trades/:id/edit` (208) | TradeForm | `TRADE_MANAGER` |
| `/reconciliation` (215) | ReconciliationPanel | `RECONCILIATION_ROLES` (BOE mgr, trade mgr, ACCOUNT_ACCESS) |
| `/reconciliation-issues` (223) | ReconciliationIssues | `RECONCILIATION_ISSUES_ROLES` (read set incl. viewers, TL_GENERATE) |
| `/incentive-licenses` (230) / `/create` (235) / `/:id/edit` (240) | MasterList / MasterForm | `INCENTIVE_LICENSE_ROLES`; create/edit `INCENTIVE_LICENSE_MANAGER` |
| `/ledger-upload` (247) | LedgerUpload | `LEDGER_UPLOAD_ROLES` (license mgr, ledger mgr) |
| `/license-ledger` (252) | LicenseLedger | `LEDGER_READ_ROLES` |
| `/license-ledger/download-requests` (257), `/:requestId` (262) | LicenseDownloadRequests, LicenseDownloadRequestDetail | `LEDGER_READ_ROLES` |
| `/license-ledger/package-readiness/:jobId` (267) | LicenseLedgerPackageReadiness | `LEDGER_PACKAGE_READINESS_ROLES` (no viewer) |
| `/license-ledger/:licenseId/:itemId` (272), `/:licenseId` (277) | LicenseLedgerDetail | `LEDGER_READ_ROLES` |
| 11 `/reports/*` (167-173): parle/sion-e1, e5, e126, e132, expiring-licenses, active-licenses, download-license, item-pivot, item-report, planned-report, license-purchase-profit | data-driven `REPORT_ROUTES` (`:76-88`) | `REPORT_ROLES` |
| `/pdf-viewer` (293) | PDFViewer (no AdminLayout) | authenticated |
| `/settings` (300) | Settings | `requireSuperuser` (and in-page redirect `Settings.tsx:286`) |
| `/profile` (305) | Profile | authenticated |
| `/masters/:entity` (312) | MasterList | authenticated, no role (backend `MasterDataPermission` allows any authenticated read, `master_view.py:44-52`) |
| `/masters/:entity/create` (317), `/:id/edit` (322) | MasterForm | `USER_ADMIN_ROLES` |
| `/admin/users` (329), `/create` (334), `/:id/edit` (339), `/admin/activity-log` (344) | UserList, UserForm, UserForm, ActivityLog | `USER_ADMIN_ROLES` |
| `*` (351) | NotFound | public |

Observations: (a) `MasterList` is mounted on 8 path families and `MasterForm` on 6; behaviour is chosen from the entity in the URL (see 02_MODULE_RESPONSIBILITY.md). (b) `TradeTransferLetter` page has no route; it is only embedded through `TransferLetterModal.tsx:6`. (c) `/pdf-viewer` has no layout and no role. (d) Declarative `BrowserRouter` only: no loaders, no route-level `errorElement`.

## 4. API layer

- One axios instance: `api/axios.js:11` (`baseURL` = `VITE_API_URL` + `/api/`, or `/api/` via the Vite proxy, `:9-10`). Bare `axios` is imported only in `axios.js:1`; `users.ts`/`tasks.ts` import it only for the `AxiosResponse` type. No `fetch(` calls in non-test source.
- Request interceptor (`:30-44`): `Bearer` from `localStorage.access`, `X-CSRFToken` from cookie.
- GET in-flight dedup by monkey-patching `api.get` (`:56-93`); skipped when `signal`, `cancelToken` or `_noDedupe` is passed. Key is url + `JSON.stringify(params, Object.keys(params).sort())`; passing a key array as the replacer is an allow-list applied at every depth, so nested params lose inner keys in the key (latent collision, not exercised by current flat params).
- Response interceptor (`:157-215`): aborts passed through; no-response gives a "Network error" toast; 401 refresh-and-replay only for replay-safe requests (GET/HEAD/OPTIONS or `retrySafe`) through one shared `refreshPromise` (`:128-155`); 403 toast "Access denied"; 404 toast "Resource not found"; replay-safe 5xx retried twice with backoff, then toast. Mutations get no 5xx retry (deliberate, comment `:167-170`). Failed refresh hard-redirects with `window.location.assign('/login?...')` (`:101-110`).
- Tokens in `localStorage` (`access`, `refresh`, `user`); cross-tab `AUTH_SESSION_EVENT_KEY`.

Typed wrappers vs inline axios (grep counts, non-test):

| Metric | Count |
|---|---|
| Files outside `src/api` importing `api/axios` | 74 (54 pages, 10 components, 4 services, 3 utils, 2 hooks, 1 context) |
| Inline call sites (`api.<verb>(`) in `pages`, `components`, `hooks`, `context`, `utils` | 186 |
| Call sites inside `src/api` and `src/services` | 107 |
| All `api.<verb>(` call sites | 293 (158 get, 88 post, 29 patch, 12 delete, 6 put) |
| Typed generics on calls (`api.get<T>(`) | 3 |
| Files outside `src/api` importing a wrapper module | 16: `TaskDrawer`, `components/planning` (1), `pages/admin` (2), `license-overview` (1), `masters` (1), `planning` (9), `settings` (1) |
| Wrapper exports | allotmentApi 13, boeApi 9, licenseApi 22, masterApi 12, mdsApi 1, planningRuleApi 16, tasks 12, users 7 |

About 64% of call sites (186 of 293) bypass the wrapper layer. Planning is the only module consistently on wrappers. Response typing is mostly absent (`api.get(...)` is `any`; ledger services cast, e.g. `licenseDownloadRequests.ts:8-9`). `api/index.ts` re-exports allotment/master/license/boe/mds only (not `planningRuleApi`, `tasks`, `users`); `services/api/*` shims remain.

## 5. Server state (TanStack Query)

`api/queryClient.ts`: `staleTime` 30 s, `retry` 1; no `gcTime`, no `QueryCache.onError`, `refetchOnWindowFocus` left at default (true).

Usage: 31 non-test files contain `useQuery/useMutation/useQueryClient` (20 `useQuery(` calls, 10 `useMutation(` calls in 5 files). 48 non-test files call the API without any TanStack Query (29 of those use `useEffect`).

| Style | Pages/areas |
|---|---|
| TanStack Query | MasterList (`:444`), UserList (`:56`), AllotmentAction (6 queries), ReconciliationPanel/Issues + 6 recon tabs via `useReconTabQuery`, all license-overview hooks + OverviewTab/ReplanStatus/CustomsLedger*, TradeForm (edit load `:156`), LicenseDownloadRequests(+Detail), LicenseLedgerPackageReadiness, TaskDrawer, planning `SionAsyncItemSelect` |
| `useEffect` + axios + local state | Dashboard, LicenseLedger (`:439-440`), LicenseLedgerDetail (`:290-307`), LedgerUpload (polling `:164`), all report pages (ItemPivotReport, ItemReport via `useItemReportData`, PlannedReport, SionNormReport `:40-61`, LicensePurchaseProfitReport hook, DownloadLicense), ActivityLog, Settings, Profile, LicensePlanningWorkspace, MasterForm (`useMasterFormData/Submit`), BOETransferLetter, TradeTransferLetter, PDFViewer, AuthContext, AsyncSelectField/DebouncedAsyncSelect, LicenseBalanceModal |

Query-key conventions: none shared. Factories exist in 4 places only: `licenseOverviewKeys` (`useLicenseOverviewSummary.ts:11`), `licenseBalanceKeys` (`useLicenseBalanceLedger.ts:19`), `licenseSionNormKeys` (`useLicenseSionNorm.ts:19`), `reconKeys` (`reconciliationHelpers.ts:72`). Others are inline arrays with ad hoc names: `['entity-list', entityName, params]`, `['admin-users', filters]`, `['allotments', id, 'info']`, `['allotment-available-licenses', ...]`, `['trades', id]`, `["license-download-requests"]`, `["license-package-readiness", jobId]`, `["tasks"]`, `["license-replan-status", id]`. Dead key: `["licenses"]` is invalidated at `IndividualItemCifSwitch.tsx:35` but no query uses it (the list key is `entity-list`). `["license-balance-customs-ledger", id]` is declared in two files (`LicenseOverviewPage.tsx:78`, `CustomsLedgerSection.tsx:22`).

Invalidation after mutations: present in license-overview (summary, items, planning, balance ledger), reconciliation tabs (tab + summary), MasterList (`['entity-list', entityName]` `:522`; optimistic `setQueryData` with rollback `:664-691`), AllotmentAction (`['allotments', id]`), UserList (`:78`). Gap: the form pages (MasterForm via `useMasterFormSubmit`, TradeForm save, AllotmentAction create) use imperative axios, not `useMutation`; no invalidation of `['entity-list', ...]` was found in them (grep `invalidateQueries` hits only the files listed above). After a save the list can serve cached data until `staleTime` (30 s) elapses; inferred from code, not reproduced. OverviewTab edits do not invalidate `["entity-list","licenses"]`; only `LicensesTable.tsx:1073` does.

Cancellation: `signal` is forwarded in 6 places: MasterList (`:446-458`), UserList (`:57-62` through `listUsers(params, signal)`), AllotmentAction available-licenses (`:441`), ActivityLog (`AbortController` ref `:104`), ItemPivotReport (`:497`), LicensePurchaseProfit hook (`:77`). Other `useQuery` calls ignore `signal`. `boeApi.fetchBOEList` (`api/boeApi.ts:13-16`) takes no `signal`, so the BOE branch of the MasterList queryFn (`MasterList.tsx:447-449`) is not cancellable. Passing a signal also disables GET dedup (`axios.js:58-60`).

Polling: `refetchInterval` in `LicenseDownloadRequestDetail.tsx:7` (3 s while processing) and `ReplanStatus.tsx:28`; `setInterval` in `LedgerUpload.tsx:164`; ItemPivotReport polls `item-pivot/task-status/:id/` manually (`:557`).

## 6. Client state

| Mechanism | Detail |
|---|---|
| `AuthContext` (`context/AuthContext.tsx`, 31 dependents) | user, loading, login/logout, `hasRole/hasAnyRole/isSuperAdmin/canManageUsers` (`useCallback` `:238-253`; value `useMemo` `:260-269`); token refresh lifecycle |
| `ParsingStatusContext` | one `ParsingStatus` object for the footer `ParsingStatusDisplay` |
| `ThemeContext` | theme in `localStorage.theme` |
| Global store libraries | none (no Redux/Zustand/Jotai in `package.json`) |
| Persisted filter state | `utils/filterPersistence.js` (`saveFilterState/restoreFilterState`) used by MasterList and LicensesTable; URL query wins when present (`MasterList.tsx:335-380`) |
| Hand-rolled cache | `components/fkDetailCache.js` |
| Local state | everything else is `useState` inside 600-1900 line pages |

URL as state: MasterList syncs `page` and filters to the query string (`:566-574`); license-overview tab id is a `useSearchParams` value (`LicenseOverviewPage.tsx:30-41`); report filters are local state.

## 7. Pagination: every implementation and the API contract

### 7.1 Backend contract (verified in `backend/`)

| Class | Location | Params | Default / max | Envelope |
|---|---|---|---|---|
| Global default `StandardPagination` | `lmanagement/settings.py:284-285`, `apps/core/pagination.py:22-54` | `page`, `page_size` | 25 / 200 | `{count, next, previous, page_size, total_pages, current_page, results}` |
| `MasterViewSet.pagination_class` (a second, local `StandardPagination`) | `apps/core/views/master_view.py:36-40,98` | `page`, `page_size` | 25 / 200 | DRF default envelope, then `MasterViewSet.list` adds `total_pages`, `current_page`, `page_size`, `has_next`, `has_previous` (`master_view.py:570-640`) |
| `ReconciliationResultsPagination` | `apps/reconciliation/api/views.py:37-61` | `page`, `page_size` | 50 / 500 | DRF default envelope |
| Hand-rolled slicing | `license/api/views/ledger.py:71` (download-requests list), `:89` (request items), `allotment/api/views_actions.py:507-508`, `:875-876` (available-licenses) | `page`, `page_size` | 20 / 100 (items 44 / 100) | requests list `{count,page,page_size,results}`; items `{count,results}` |
| `ActivityLogViewSet` | `core/views/activity_log.py:27` (`pagination_class=None`; the comment "use DRF default" is wrong) and `:62-68` | `limit` | 100 / 1000 | plain list, queryset slice |
| Defined but unreferenced | `LargePagination`, `CompactPagination`, `CursorPagination`, `LimitOffsetPaginationWithCount`, `UnlimitedPagination`, `OptimizedCursorPagination` in `core/pagination.py` (no view references found by grep) | | | |

Client-visible families: page-number (`page`, `page_size`), `limit` on the activity log, and unpaginated bespoke endpoints. No cursor or `offset` in use. `LicenseViewSet.paginate_queryset` is overridden to batch live balances for the page (`license/api/views/license.py:291`).

Filter/search contract by family: licenses `LicenseFilterSet` with `CombinedFilterBackend`, `EnhancedSearchFilter`, `AdvancedOrderingFilter` (`license.py:250-251`); allotments `AllotmentFilterSet` (`allotment/api/views.py:165-166`); BOE `BOEFilterSet` (`bill_of_entry/api/views.py:115-116`); incentive licences `IncentiveLicenseFilter` (`license/views_incentive.py:10,31`); masters `CaseInsensitiveSearchFilter` + `OrderingFilter`, `ordering_fields="__all__"` (`master_view.py:99-100`), `search` param. Ordering via `ordering=`; date ranges via `__gte/__lte` (MasterList converts UI `_from/_to`, `MasterList.tsx:400-412`).

### 7.2 Frontend implementations

| # | Where | Type | Params sent | UI | Matches contract |
|---|---|---|---|---|---|
| 1 | `pages/masters/MasterList.tsx:390` (licenses, allotments, BOE, trades, incentive, masters) | server | `page`, `page_size` (25) + filters + `ordering` (trades forced `-invoice_date` `:411`) | `DataPagination` | yes; reads `total_pages`, `has_next`, `has_previous` (`:466-470`); synced to URL |
| 2 | `pages/AllotmentAction.tsx:384` available-licenses | server | `page`, `page_size` + filters | `DataPagination` | yes (backend cap 100, default 20) |
| 3 | `pages/reports/ItemReport.tsx:71-85` | client | none: loads the full `reports/item-report/` JSON then `licenseGroups.slice` | `DataPagination` + `hooks/usePagination.js` (its only consumer) | report endpoint unpaginated |
| 4 | `LicenseDownloadRequests.tsx:11` | none | none | none | backend paginates 20/page; only page 1 shown, `count` unused |
| 5 | Download request detail items | none | none | none | backend `/items` default 44/page; UI uses `r.items` from the detail payload |
| 6 | Reconciliation tabs (`useReconTabQuery.ts:16-21`, `unwrapList` `reconciliationHelpers.ts:24-30`) | none | none | `DataTable` (no pagination support) | MISMATCH: every detection endpoint paginates at 50/page (`reconciliation/api/views.py:37-69`), the client keeps `results` only. A tab with more than 50 rows silently shows 50 while the summary card shows the true total |
| 7 | `ReconciliationIssues.tsx` | none | none | `DataTable` | reads `reconciliation/summary/` only |
| 8 | `components/TaskDrawer.tsx:204` | none | filters only | list | tasks use the global default: first 25 only |
| 9 | `ActivityLog.tsx:87-103` | server `limit` | `limit` (default "200") | one scrolling table | backend max 1000; no next page |
| 10 | `UserList.tsx:58-62` | none | `search`, `role`, `is_active` | table | if `auth/users/` falls under the global default (not read in this audit) only 25 users show, and stat cards are computed from the loaded page (`UserList.tsx:71`) |
| 11 | Async selects (`AsyncSelectField.tsx:180,296`, `DebouncedAsyncSelect.tsx:138`, `item-async-select`) | server, first page | `page_size` 10/50 + `search` | react-select | fine for lookups |
| 12 | Bulk option loads: `useMasterOptions.ts:68,91` (200 / 500), `LicensePlanningWorkspace.tsx:128` (500), `useItemReportFilters.ts:61` (200), `allotmentApi.ts:80` (200), `AllotmentAction.tsx:273` (200) | server "load all" | `page_size` up to 500 | none | 500 exceeds the 200 cap of `StandardPagination` (`master_view.py:36-40`); the sion-classes/related request for 500 returns at most 200 rows, silently |
| 13 | `LicenseLedger.tsx:439-440` `license-ledger/license-wise` and `summary` | none | filters in querystring | cards | backend builds the whole dataset (`ledger.py:610-640`), unpaginated |
| 14 | License-overview tabs (`overview-boes`, `-items`, `-allotments`, `-invoice-ledger`) | none | none | local tables | not verified as paginated |
| 15 | Dashboard `dashboard/` | none | none | aggregate | |

`DataPagination` is imported by 3 pages (MasterList, AllotmentAction, ItemReport).

## 8. Error, loading and empty handling; boundaries; toasts

- Error boundary: one class `ErrorBoundary` wrapping all routes (`App.tsx:19`). It is above the layout, so a render error removes the nav too; the fallback uses Bootstrap classes (`container mt-5 alert alert-danger`, `ErrorBoundary.tsx:25-29`) although Bootstrap CSS was removed. `GlobalErrorBoundary` and `ErrorScreen` exist; `GlobalErrorBoundary` is unmounted. No per-route `errorElement`; `throwOnError` unused.
- Toasts: sonner only (59 importing files, 329 `toast.success/error/warning/info` calls); `react-toastify` 0. 37 `console.error/log` calls in non-test source. 6 native `alert/confirm` uses remain.
- Server error text: `utils/errorUtils.js` `getErrorMessage`, `utils/formErrors.js`, `utils/reportErrorHandling.ts`, applied inconsistently; 20 files keep a `setError(` local state next to toasts.
- Loading: `PageLoader` Suspense fallback (`LoadingFallback.tsx`); `ProtectedRoute` bare text; `Skeleton` in 15 files; `EmptyState` in 9 files; plain "Loading request..." text in `LicenseDownloadRequestDetail.tsx:7`. No shared wrapper that maps query `isLoading/isError/empty` to one component.
- The interceptor's global 403/404/5xx/network toasts fire in addition to page-level handling (section 4).
- Confirmations: `ConfirmDialog` component, `hooks/useConfirmDialog.tsx`, `ui/dialog` and native `confirm()` coexist.

## 9. Permissions and action visibility

Client checks are hints; the backend is authoritative (`apps/accounts/permissions.py`).
1. Route: `ProtectedRoute` on 45 route elements (section 3) with named role sets.
2. Nav: `TopNav` filters by the same sets (`:150`, `:226`, `:303`); `CommandPalette` filters by roles (`CommandPalette.tsx:68-79`). `AdminLayout` `QUICK_ACTIONS` is unfiltered.
3. In-page: `hasRole/hasAnyRole/isSuperAdmin` in MasterList (`canWrite` from `ENTITY_WRITE_ROLES`, `:113-128`; ACCOUNT_ACCESS may edit BOE invoice number only), Dashboard tiles (`Dashboard.tsx:182-196`), license-overview (`LicenseOverviewPage.tsx:64,231`, `OverviewTab.tsx:43-57`, `SionNormCard.tsx:28-43`, `LicenseOverviewContent.tsx:15`), Settings/UserList/UserForm/ActivityLog/Profile (`is_superuser`).
- `PermissionGate` (`components/PermissionGate.tsx`, props `role`/`anyRole`/`fallback`) has one consumer (`LicenseOverviewPage.tsx:174`); elsewhere gating is ad hoc conditionals.
- Duplicated role knowledge: `ENTITY_WRITE_ROLES` lives inside the MasterList component body (`:114-120`) and repeats the write roles of the route guards; `Dashboard.tsx:187-196` builds inline role arrays not named in `authorizationRoles.ts`.
- AllotmentAction, TradeForm, LicenseLedger and others rely on route guards alone; they have no read-only variant for viewer roles (viewers cannot reach those routes).

## 10. Performance

### 10.1 Build (`npm run build`, 2026-11-16, 2978 modules, "built in 413ms"; no warnings printed)

Entry payload (`dist/index.html`): `index-DO46YS7_.js` 67.25 kB (gzip 20.94), `app-shell-B_P7f3SD.js` 355.84 kB (gzip 118.07), `vendor-react-Bt-jsGsl.js` 179.95 kB (gzip 57.24), `rolldown-runtime` 0.77 kB (gzip 0.44); CSS `index-C4TYXu8p.css` 249.13 kB (gzip 36.99). Eager JS about 604 kB raw, about 197 kB gzip, plus an external Google Fonts stylesheet.

148 JS chunks emitted. Largest (raw kB / gzip kB):

| Chunk | Raw | gzip |
|---|---|---|
| app-shell | 355.84 | 118.07 |
| vendor-react | 179.95 | 57.24 |
| navigationUtils (shared bundler-chosen chunk, misleading name) | 162.74 | 39.58 |
| MasterList | 132.16 | 34.08 |
| LicensePlanningWorkspace | 94.68 | 24.75 |
| useStateManager (react-select) | 83.04 | 29.14 |
| MasterForm | 81.63 | 23.20 |
| ItemPivotReport | 81.63 | 19.70 |
| index (entry) | 67.25 | 20.94 |
| ItemsTab (license-overview) | 65.12 | 16.99 |
| AllotmentAction | 59.22 | 14.69 |
| TradeForm | 54.56 | 11.62 |
| LicenseLedger | 52.26 | 13.63 |
| PlanningEditor | 39.24 | 9.99 |

Findings:
- `app-shell` (356 kB) is much larger than shell code: `vite.config.js:51-58` pins `/layout/`, `Icon`, `TopNav`, `LoadingFallback`, `ErrorScreen`, `GlobalErrorBoundary` into it, and their transitive imports come along. It is under `chunkSizeWarningLimit` 1000 (`:41`), so no warning appears.
- `navigationUtils` (163 kB, with a 28.7 kB CSS file) is a shared chunk the bundler named after an arbitrary module; the name is unstable for cache analysis. Manual chunking separates React only (`:46-52`); Radix, TanStack Query, axios, recharts, exceljs, jspdf, framer-motion, react-select, react-datepicker are not split explicitly. They do not appear among the top chunks, which suggests dynamic imports; not verified per import.
- `MasterList` is a single 132 kB chunk holding all entity tables (licenses, allotments, trades, incentive, generic) although each route needs one.
- `emptyOutDir:false` (`vite.config.js:36`): `dist/assets/js` holds 842 files versus 148 emitted this build (intentional for open tabs, grows unbounded).
- react-select is bundled (83 kB) alongside Radix Select (`select` 23.5 kB).

### 10.2 Runtime patterns (grep evidence)

- Tables: 40 files use raw `<table>`; `DataTable` is used by 8 (7 reconciliation + MasterList) and has no sorting/pagination/virtualisation. No virtualisation library in `package.json`.
- Memoisation: `React.memo` in 1 file; `useMemo` in 35, `useCallback` in 32. LicensesTable memoises per-row handlers (`:1050-1070`); MasterList memoises trade grouping (`:507`). LicenseLedger (1078 lines) renders every licence card from the whole unpaginated response.
- Debounce: filter text 400 ms (`AdvancedFilter.tsx:15`, `DebouncedSearchInput`), async selects 300 ms, AllotmentAction debounced description/licence/hs, UserList, ActivityLog, report filters, `SionAsyncItemSelect`, trade link modal 350 ms (`MasterList.tsx:542`). `useDeferredValue/useTransition` are not used (`hooks/useSmoothListFilters.ts` is the only smoothing helper).
- Client-side filtering/sorting of large sets: `.filter(`/`.sort(` in 44 page/component files; notable are ItemReport group slicing, ItemPivotReport norm tabs/rows from the full JSON, LicenseLedger grouping, `UserList` stats.
- `Settings.tsx` (672 lines) and `UserList.tsx` implement overlapping user admin, both on `auth/users/`.
- 29 `useEffect` fetch files lack cancellation; only ItemPivotReport and LicensePurchaseProfit guard against out-of-order responses with `AbortController`.

## 11. Tests, quality tooling, a11y

| Item | Evidence |
|---|---|
| Vitest | `vitest.config.ts`: jsdom, globals, setup `src/test/setup.ts` (only `@testing-library/jest-dom/vitest`), include `src/**/*.{test,spec}.{ts,tsx}`; no coverage config, no coverage package (`grep coverage package.json vitest.config.ts` empty) |
| Unit tests | 79 files, 440 `it/test` blocks. pages/reports 18, pages root 16, masters 9, utils 7, planning 6, test/ 4, components 4, license-overview 2, license-balance 2, admin 2, services 2, api 2, 1 each in routes, hooks, tests/, components/reports, components/planning |
| RTL | `@testing-library/react` 16, `user-event` 14, `jest-dom` 6 |
| Playwright | `playwright.config.ts` (chromium only, baseURL 127.0.0.1:41731, webServer); 13 specs in `e2e/` + 1 in `playwright/`, 44 `test(` blocks: authenticated-shell responsive, custom-ledger-download, data-bearing.real, financial-ledger-invoices, item-pivot sticky, license-overview a11y, login a11y/visual, package-download, responsive, trades a11y/performance, accessibility |
| a11y tooling | `@axe-core/playwright` 4.13 (devDependency) used by `e2e/accessibilityHelpers.ts` and a11y specs. No `eslint-plugin-jsx-a11y`, no `vitest-axe`. ARIA live region `AdminLayout.tsx:36-42`; `lib/accessibility.ts`; `#main-content` target exists, no skip link found in AdminLayout |
| Lint | flat `eslint.config.js` with `react-hooks` 7, `react-refresh`; `format:check` = `eslint --max-warnings=0` |
| Typecheck | `tsc -p tsconfig.json --noEmit` with `strict:false` |

Coverage gaps (no colocated test found): `routes/AppRoutes.tsx`, `ProtectedRoute.tsx` (only `authorizationRoles.test.ts`), `layout/AdminLayout`, `ReconciliationIssues`, the 6 reconciliation tab components (smoke test on the panel only), `Settings`, `ActivityLog`, `LicenseDownloadRequests(+Detail)`, `LicenseLedgerPackageReadiness`, `BOETransferLetter`, `TradeTransferLetter`, `PlanningEditor` (one reconciliation test), license-overview tabs except `QuantityUtilization` and `LicenseOverviewPage.documents`, `masters/tables/*`, `useMasterFormSubmit/Calculations`, `DataTable`, `DataPagination`, `ErrorBoundary`, `PermissionGate`, and `api/{allotment,boe,license,master,tasks,users}Api.ts` (only `planningRuleApi.test.ts` and `axios.refresh.test.ts` exist). Page smoke tests exist for MasterList, MasterForm, TradeForm, ReconciliationPanel.

## 12. Findings summary (ranked; no changes made)

1. Reconciliation tabs silently truncate at 50 rows (7.2 #6) and 500-row option loads are capped at 200 (7.2 #12): client/API contract mismatches.
2. 64% of API call sites bypass the typed `src/api` wrappers; `strict:false` hides response typing.
3. Server state split: 31 files on TanStack Query, 48 on `useEffect`+axios; `signal` forwarded in 6 places; BOE list not cancellable.
4. No query-key convention (4 factories, many inline keys); dead key `["licenses"]` invalidated; form saves do not invalidate `entity-list`.
5. One error boundary above the nav with a Bootstrap-styled fallback; orphaned `GlobalErrorBoundary`, `Sidebar`, `AllotmentFormModal`.
6. `app-shell` chunk 356 kB eager; `MasterList` chunk 132 kB bundles every entity.
7. Layout and guard repeated on 45 route elements; quick-action footer ignores roles.
8. Interceptor 403/404 global toasts duplicate page-level error UI.
9. No coverage tooling; routing, shell, reconciliation tabs, master tables and 6 of 8 API wrappers have no tests.
