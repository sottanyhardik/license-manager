# 07 Route, filter-request and reuse audit (read-only)

Date 2026-11-16. Branch `feature/v5`, current working tree. Role: react-architect. Method: source and tests only.
No browser was used (Playwright auth was not supplied), so **nothing here was validated live**. Request counts
are **derived from code** unless marked "test-pinned".

Builds on and does not repeat: `00_FRONTEND_ARCHITECTURE.md` §3 (routing), §5 (server state); `01_COMPONENT_INVENTORY.md`
§7 (dead files); `03_DUPLICATION_REPORT.md` §2-3 (filter and pagination duplication); `04` §3 (list contract);
`05` §2-3 (FilterEngine and PaginationEngine spec); `06` §4 (licence request de-duplication, which stays the
authority for `/licenses/:id/overview`); `10_PACKAGE_REVIEW.md`; `DECISION_REGISTER.md`.

**Commands run in this task**
- `npx vitest run` on 10 files (useListQuery, useMasterOptions, FilterBar, Pagination, listContract, MasterList
  deeplink, licenses.filters, trades, smoke, and AppRoutes.licenseRedirect): **10 files, 51 tests passed**.
- `npx tsc -p tsconfig.json --noEmit`: **exit 0, no output**.
- `git status --short -- frontend/src`: only `components/data-table/` and `components/form/` are untracked. The
  other "new" blocks (`components/{shared,workspace,filters,pagination}`, `hooks/useListQuery.ts`,
  `fetchAllPages.ts`, `useDebouncedValue.ts`, `lib/listContract.ts`, `lib/queryKeys.ts`, `features/*`) are
  already tracked in this tree.

---

## 1. Route inventory (`src/routes/AppRoutes.tsx`, 361 lines, 57 `<Route>` elements)

Lazy legend: **R** = `lazyLoadWithRetry` (`utils/lazyLoad.js:17`, 3 retries, chunk-reload guard). **L** = plain
`React.lazy` (no retry). **E** = eager. All routes sit under one `<Suspense fallback={<PageLoader/>}>` (`:92`), with no
route-level `errorElement`. Guards come from `ProtectedRoute.tsx:23-46`: no user → `/login`, failed check →
`/403`, and superuser bypasses role checks. Role sets are defined in `authorizationRoles.ts:27-53`.

| Path (line) | Element | Guard | Lazy | Module |
|---|---|---|---|---|
| `/login` (95) | Login | public | E | auth |
| `/forgot-password` (96) | PasswordReset | public | E | auth |
| `/401` (97), `/403` (98) | Unauthorized, Forbidden | public | E | errors |
| `/` (101) | `Navigate → /dashboard` | authenticated | n/a | shell |
| `/dashboard` (111) | Dashboard | authenticated | R | dashboard |
| `/licenses` (123) | MasterList | `LICENSE_ROLES` | R | licences |
| `/licenses/create` (128), `/licenses/:id/edit` (133) | MasterForm | `LICENSE_MANAGER` | R | licences |
| `/planning` (138) | LicensePlanningWorkspace | `LICENSE_MANAGER` | **L** | planning |
| `/allotments` (145) | MasterList | `ALLOTMENT_ROLES` | R | allotments |
| `/allotments/create` (150), `/:id/edit` (155) | MasterForm | `ALLOTMENT_MANAGER` | R | allotments |
| `/allotments/:id/allocate` (160) | AllotmentAction | `ALLOTMENT_MANAGER` | R | allotments |
| 11× `/reports/*` (`REPORT_ROUTES` 76-88, mapped 167-173) | SionE1/E5/E126/E132, ExpiringLicenses, ActiveLicenses, DownloadLicense (**L**). ItemPivotReport, ItemReport, PlannedReport, LicensePurchaseProfitReport (R) | `REPORT_ROLES` | mixed | reports |
| `/bill-of-entries` (176) | MasterList | `BOE_LIST_ROLES` | R | BOE |
| `/bill-of-entries/create` (181), `/:id/edit` (186) | MasterForm | `BOE_MANAGER` | R | BOE |
| `/bill-of-entries/:id/generate-transfer-letter` (191) | BOETransferLetter | `BOE_TRANSFER_LETTER_ROLES` | R | BOE |
| `/trades` (198) | MasterList | `TRADE_ROLES` | R | trades |
| `/trades/create` (203), `/:id/edit` (208) | TradeForm | `TRADE_MANAGER` | **L** | trades |
| `/reconciliation` (215) | ReconciliationPanel | `RECONCILIATION_ROLES` | R | recon |
| `/reconciliation-issues` (223) | ReconciliationIssues | `RECONCILIATION_ISSUES_ROLES` | R | recon |
| `/incentive-licenses` (230), `/create` (235), `/:id/edit` (240) | MasterList / MasterForm | `INCENTIVE_LICENSE_ROLES` / `_MANAGER` | R | incentive |
| `/ledger-upload` (247) | LedgerUpload | `LEDGER_UPLOAD_ROLES` | **L** | ledger |
| `/license-ledger` (252) | LicenseLedger | `LEDGER_READ_ROLES` | **L** | ledger |
| `/license-ledger/download-requests` (257), `/:requestId` (262) | LicenseDownloadRequests(+Detail) | `LEDGER_READ_ROLES` | R | ledger |
| `/license-ledger/package-readiness/:jobId` (267) | LicenseLedgerPackageReadiness | `LEDGER_PACKAGE_READINESS_ROLES` | R | ledger |
| `/license-ledger/:licenseId/:itemId` (272), `/:licenseId` (277) | LicenseLedgerDetail | `LEDGER_READ_ROLES` | **L** | ledger |
| `/licenses/:id/overview` (284) | LicenseOverviewPage | `LICENSE_OVERVIEW_ROLES` | **L** | licences |
| `/licenses/:id` (290) | `RedirectToLicenseOverview` (`:70-74`) | `LICENSE_OVERVIEW_ROLES` | n/a | redirect |
| `/licenses/:id/balance` (296) | `RedirectToLicenseOverview` | **none at the route**; the target route is guarded | n/a | redirect |
| `/pdf-viewer` (299) | PDFViewer, **no AdminLayout** | authenticated | **L** | util |
| `/settings` (306) | Settings | `requireSuperuser` | R | admin |
| `/profile` (311) | Profile | authenticated | R | account |
| `/masters/:entity` (318) | MasterList | authenticated (no role) | R | masters |
| `/masters/:entity/create` (323), `/:id/edit` (328) | MasterForm | `USER_ADMIN_ROLES` | R | masters |
| `/admin/users` (335), `/create` (340), `/:id/edit` (345), `/admin/activity-log` (350) | UserList, UserForm ×2, ActivityLog | `USER_ADMIN_ROLES` | R | admin |
| `*` (357) | NotFound | public | E | errors |

Counts: 33 lazy (19 R, 14 L) and 5 eager. This matches 00 §3, so the only drift since then is line numbers.

### 1.1 Dead, orphan and hard-to-reach

| Item | Evidence | Status |
|---|---|---|
| `pages/errors/ServerError.tsx` (22 LOC) | 0 importers (grep `errors/ServerError` finds nothing). It has no route | **Dead page, no route.** It is not in D6. Propose adding it to D6 |
| `pages/masters/tables/BalanceTab.tsx` (530), `LedgerTab.tsx` (1162) | 0 importers. The only mention is a comment at `license-overview/SummaryCard.tsx:21` | Dead, already covered by **D6** |
| `pages/TradeTransferLetter.tsx` | No route. It is embedded only in `components/TransferLetterModal.tsx` | Intentional (modal body), not dead |
| `layout/Sidebar.tsx` | 0 importers (01 §7). It holds the only `/admin/users` nav link besides CommandPalette | Dead, see 01 §7 |
| `/reconciliation-issues` | No in-app link: grep finds the path only in `AppRoutes.tsx:223`. TopNav has `/reconciliation` only (`TopNav.tsx:37`) | **Reachable by typed URL only.** Its read roles (viewers, `TL_GENERATE`) are wider than `/reconciliation`'s, so those users have no way to find it |
| 7 report routes: `parle/sion-e1/e5/e126/e132`, `expiring-licenses`, `active-licenses`, `download-license` | Not in `routes/config.ts:143-158` `reportEntities` (only item-pivot, item-report, planned-report, license-purchase-profit). No `navigate`/`Link` to them. Only `hooks/usePageTitle.js` names them | **Reachable by typed URL only.** Owner decision: list them or retire them (do not assume) |
| `/pdf-viewer` | The only reference is its own doc comment (`PDFViewer.tsx:11`). Previews use `utils/pdfPreview.js` blob windows instead | Probably unused. Verify with the owner before removing |
| `/licenses/:id/balance` | Has no guard, but it only redirects to the guarded `/overview` | Safe. It leaks nothing |

---

## 2. Reusable building blocks that exist now

Counts are non-test importers (grep of `import ... from`), excluding the block's own directory.

| Concern | New block (path) | Consumers | Legacy duplicates still live (consumers) |
|---|---|---|---|
| Filters | `components/filters/FilterBar.tsx` (214, declarative `FilterDef`) | **0** | `components/AdvancedFilter.tsx` (1: MasterList); page-local `AllotmentFilters`, `ItemPivotFilters`, `itemReport/ItemReportFilters`, `licensePurchaseProfitReport/*Filters`, `licenseLedgerFilters.ts`; `DataFilter.tsx` (0, dead) |
| Filter shell | `components/filters/FilterPanel.tsx` (26) | 2 (AdvancedFilter, AllotmentFilters) | n/a |
| Active-filter chips | `components/ActiveFilters.tsx` (legacy, but the de-facto standard) | 13 | none |
| List state + URL | `hooks/useListQuery.ts` (138) + `lib/listContract.ts` (142) | **0** | MasterList's own state + URL sync (`MasterList.tsx:326-393, 565-585`); `hooks/useSmoothListFilters.ts` (2: UserList, ActivityLog); `hooks/usePagination.js` (1: ItemReport); `reconciliation/useReconTabQuery.ts` (7 tabs) |
| Pagination UI | `components/pagination/Pagination.tsx` (89) | **0** | `components/DataPagination.tsx` (4: MasterList, AllotmentAction, ItemReport, ReconPagination); `reconciliation/ReconPagination.tsx` (7) |
| Fetch-all | `hooks/fetchAllPages.ts` (24, 200/page, 50-page cap) | 2 (`useMasterOptions.ts:67,89`, `LicensePlanningWorkspace.tsx:128`) | none |
| Debounce | `hooks/useDebouncedValue.ts` (11) | 1 (useListQuery) | `hooks/useDebounce.js` (`useDebounce`:20, `useDebouncedCallback`:53, `useDebouncedFilters`:100, `useDebouncedState`:136), 6 importers. Two implementations of the same primitive |
| Master options | `hooks/useMasterOptions.ts` (module-scope cache) | 3 (AllotmentAction, ItemPivotReport, useItemReportFilters) | `LicenseLedger.tsx:713,720` and `AllotmentFilters.tsx:32` load the same masters through `AsyncSelectField`/`HybridSelect`; `LicensePlanningWorkspace.tsx:128` loads sion-classes again |
| Query keys | `lib/queryKeys.ts` (`qk`, `invalidateLicence`) | 8 | inline keys: `['entity-list', …]` (MasterList), `['allotments', id, 'info']` (`AllotmentAction.tsx:310`), `boeRecordKeys` (`features/bill-of-entry/format.ts:6`), `reconKeys`, TaskDrawer keys |
| Async select | (none new) | n/a | `AsyncSelectField.tsx` (7, has the `_fkDetailCache` + in-flight coalescing), `DebouncedAsyncSelect.tsx` (2, **no cache**), `HybridSelect.tsx` (6, wraps AsyncSelectField with `loadOnMount`) |
| Tabs | `components/workspace/DetailTabs.tsx` (56) | 3 (licence, allotment, BOE record workspaces) | `ui/tabs` used directly by 5 pages (LicenseOverviewPage, ReconciliationPanel, ReconciliationIssues, LicenseLedgerPackageReadiness, LicensePlanningWorkspace) |
| Module shell | `components/workspace/ModuleWorkspace.tsx` (159) | **0** | n/a |
| Accordion | `components/workspace/ModuleAccordion.tsx` (98) | 3 (licence OverviewTab, BoeAllotmentTab, allotment OverviewTab) | `components/AccordionTable.tsx` (1: MasterList). No `ui/accordion` |
| Tables | `components/data-table/*` (**untracked, depends on unapproved packages**, 10_PACKAGE_REVIEW) | 0 | `components/DataTable.tsx` (8); hand-rolled `<table>` in 40 non-test `.tsx` files; `license-overview/SortableHeader.tsx` (3). `ui/table.tsx` exists, consumer = data-table only |
| Forms | `components/form/*` (**untracked, unapproved packages**) | 0 | `FormField.tsx` (0, dead); every form is hand-rolled `useState` (03 §4) |
| Loading | `components/shared/LoadingState.tsx` | 3 (features) | `LoadingFallback.tsx` `PageLoader` (routes only); ad-hoc spinners per page; `ProtectedRoute.tsx:27` bare "Loading..." |
| Error | `components/shared/InlineError.tsx` | 3 (features) | `ErrorScreen.tsx` (4 error pages); `ErrorBoundary.tsx` (App); `GlobalErrorBoundary.tsx` (0, dead); per-page toasts |
| Empty | `components/shared/EmptyState.tsx` | 5 (4 feature tabs + `LicensesTable`) | `components/EmptyState.tsx` (6: Settings, Dashboard, ActivityLog, UserList, LicenseLedger, AllotmentAction) |
| Other shared | `shared/{SearchInput, DateRangePicker, ActivityTimeline, ConfirmDialog}` | **0 each** | `DebouncedSearchInput` (3), `DateRangeFilter` (6), `Timeline` (0, dead), `components/ConfirmDialog` (5) + `useConfirmDialog` (2) |
| Status/actions | `shared/{StatusBadge, ActionMenu, FieldGrid, tone}` | 3 / 2 / 5 / 3 | `ConditionBadge` (8), page-local badges (03 §8) |

Takeaway: the new list stack (`useListQuery`, `listContract`, `FilterBar`, `Pagination`, `ModuleWorkspace`,
`SearchInput`, `DateRangePicker`) is **built and tested but has zero consumers**. The record-level stack
(`DetailTabs`, `ModuleAccordion`, `FieldGrid`, `LoadingState`/`InlineError`/`EmptyState`) is adopted only in
`features/*`.

---

## 3. Global filter behaviour and request performance

### 3.1 Baseline facts

- Defaults: `staleTime` 30 s, `retry` 1, `refetchOnWindowFocus` default **true** (`api/queryClient.ts:3-10`).
  `useListQuery` opts out of focus refetch (`useListQuery.ts:102`); MasterList does not (`MasterList.tsx:454-473`).
- GET in-flight dedup (`api/axios.js:56-83`) applies only to requests without a `signal`. It coalesces
  *concurrent identical* GETs, not sequential ones.
- **Throttling (backend, applies to every request including GETs):** `BurstRateThrottle` **180/min per user** and
  `UserRateThrottle` **3000/hour per user** (`backend/lmanagement/settings.py:295-310`). Ident is `user.pk`
  (`backend/apps/core/throttling.py:39-40`). `docs/guides/RATE_LIMITING_GUIDE.md:103,279-287` is **stale**
  (it says burst 60/min and user 1000/hour).
- **No 429 handling on the client:** the response interceptor handles 401, 403, 404 and 5xx only (`axios.js:157-215`).
  TanStack `retry: 1` immediately retries a throttled query, so a 429 costs 2 requests.

### 3.2 How the main list (MasterList + AdvancedFilter) drives requests

Flow: `AdvancedFilter` local state → `onFilterChange` → `MasterList.handleFilterChange` (`:557-563`) →
`filterParams` → `queryParams` memo (`:399-429`) → `useQuery(['entity-list', entity, queryParams])` (`:454-473`).
A URL-sync effect (`:565-585`) writes filters and page into the URL. An **init effect keyed on
`[entityName, location.search]`** (`:326-393`) re-parses the URL into state.

Debounce: text fields have **two serial debounces**. `DebouncedSearchInput` waits 400 ms (`AdvancedFilter.tsx:339,378`), then
the auto-apply effect adds another 400 ms (`:118`), so a request goes out about 800 ms after the last keystroke. Selects, dates
and toggles apply "immediately" through `setTimeout(…,0)` **inside a `setState` updater** (`:122-131`). In dev
StrictMode the updater runs twice, so it emits twice. The keys are the same, so this causes no extra request but is impure.

Findings (inferred from code; F1, F2 and F3 are confirmable with the B0 tests):

| # | Finding | Evidence | Effect per occurrence |
|---|---|---|---|
| F1 | **Own URL writes re-trigger the init effect**, which forces `setPageSize(25)` | `:393` deps include `location.search`; `:368` and `:389` call `setPageSize(25)` unconditionally; page_size is never written to the URL (`:574-579`) | A page-size change is lost on the next page or filter change. That change costs **2 list GETs** (one at the chosen size, then one at 25) |
| F2 | For a list with no URL filters, a page click can reset to page 1 | `?page=2` gives `urlFilters={}` (`:351-361`) → else branch → `setCurrentPage(1)` (`:388`) unless the session "returnTo" flag is set (`utils/filterPersistence.js:70-80`) | Suspected. It applies only to entities whose list has no default/backend filters. Licences, allotments, BOE and trades always carry filters. Confirm in B0 |
| F3 | **Typed filter values become strings on the URL round-trip**, so the query key changes and the same list is fetched again | backend `default_filters` can be JSON booleans or lists (`apps/core/views/views.py:344` `{"is_active": True}`; `apps/license/api/views/license.py:131,339-342`), applied at `:502-512`; FK multi-selects emit arrays (`DebouncedAsyncSelect.tsx:166-169`). URL write `String(value)` (`:575`), re-parse as strings (`:351-361`) → new `queryParams` content | Cold `/licenses` (and `/masters/<entity>` with an `is_active` default): **up to 3 list GETs**. The first is unfiltered, the second carries typed defaults, the third the stringified defaults. **Test-pinned tolerance:** `MasterList.deeplink.test.tsx:94` asserts `≤ 3` and `:104` asserts `≤ 2`, so the suite currently allows these duplicates. Each FK multi-select change: **2 GETs** (`field[]=` array form, then `field=1,2`; the backend accepts both, `master_view.py:424-452`) |
| F4 | `DebouncedAsyncSelect` re-resolves selected ids **sequentially and uncached** on every `value` change | `:124-130` effect on `[value]` → `loadSelectedOption` → one `GET <endpoint><id>/` per id (`:75-80, 105-113`). It does not use `_fkDetailCache` (which `AsyncSelectField.tsx:4,197-219` does) | Selecting the k-th value issues k detail GETs. The F3 round-trip (array → string) repeats them. A deep link with k FK ids issues k GETs per FK field on every mount (AdvancedFilter is remounted per entity via `key`, `MasterList.tsx:953`) |
| F5 | The AdvancedFilter prop-sync effect runs on every MasterList render | `AdvancedFilter.tsx:88-107` deps `[initialFilters, defaultFilters]`. The caller passes a fresh object every render (`MasterList.tsx:957` `getDefaultFilters(...)` or `metadata.default_filters \|\| {}`) | CPU only. It is guarded by a `JSON.stringify` compare, so no request |
| F6 | The BOE list cannot be cancelled | `boeApi.fetchBOEList(queryParams)` without `signal` (`MasterList.tsx:457-459`; 00 §5) | Superseded BOE list requests still complete server-side |
| F7 | Mutations invalidate `['entity-list', entity]` only | `:531-533` | List-only. Licence cards use `invalidateLicence` separately (`useLicenceRowActions.ts:73`). OK |

### 3.3 Other hooks and pages

| # | Finding | Evidence | Estimated requests |
|---|---|---|---|
| F8 | **Planning refetches all SION classes on every URL write the page makes** | `LicensePlanningWorkspace.tsx:128` effect deps `[params]` (`useSearchParams` object); the page writes params on SION select, tab switch and rule select (`:233, 245, 246`) | 1 extra `masters/sion-classes/` fetchAllPages per tab switch, rule click or SION change. It duplicates `useSionNormOptions` (`useMasterOptions.ts:88-91`, same endpoint and params, separate cache) |
| F9 | **ItemPivot reloads a parameterless endpoint on filter change** | `ItemPivotReport.tsx:450-455` re-runs `loadAvailableNorms` when `minBalance`/`licenseStatus` change, but the URL has no params (`:460-461`) | 1 redundant `item-pivot/available-norms/` per change |
| F10 | **ItemPivot min-balance input is not debounced** | `ItemPivotFilters.tsx:91` `onChange → setMinBalance` → `loadReport` (`ItemPivotReport.tsx:523-527`) + F9 | Typing "5000" with a norm tab open: 4 report GETs (aborted client-side, but they still reach the server and count against the throttle) + 4 available-norms GETs = **8 requests** |
| F11 | **LicenseLedger legacy enrichment is an unbounded N+1** | `LicenseLedger.tsx:447-452` `Promise.allSettled` with one `license-ledger/<id>/` per licence lacking `transactions`, all in parallel, on every `paramsKey` change (`:489`) | 2 + N per filter change. With N ≥ 179 this **exceeds the 180/min burst throttle in one load**. It is a compatibility path ("server that has not yet reloaded"). Whether the current backend still triggers it is unverified |
| F12 | The same allotment is cached under two keys | `AllotmentAction.tsx:310` `['allotments', id, 'info']` vs `qk.allotments.detail(id)` (`useAllotmentDetail.ts:13`, `AllotmentMappingTab.tsx:30`); both GET `allotments/:id/` | Card → allocate page: 1 duplicate GET. AllotmentAction's invalidations (`:517, 542, 615, 642` `['allotments', id]`) do **not** match `['allotments','detail',id]`, so a card opened after an allocation can show data up to 30 s stale. Also `qk.*.detail` keeps the raw id type: number in features, string `useParams` in the page (06 §4.2 already flags this) |
| F13 | `useMasterOptions` caches a failure as `[]` for the whole session | `useMasterOptions.ts:43-46` | One transient error empties Purchase Status/SION dropdowns until a hard reload. No retry and no invalidation (it is outside TanStack) |
| F14 | `listContract` array serialisation does **not match the backend** | `listContract.ts:56` (`toQuery`) and `:138` (`writeListParams`) **repeat keys** (`f=1&f=2`; pinned by `listContract.test.ts:15`). `master_view.py:424,436` reads `params.get(field)`, which returns the last value only, or `field[]` / comma strings | **Latent wrong results** (multi-select keeps only the last value) the day `useListQuery` gets a MasterList consumer. No live impact today (0 consumers) |
| F15 | Minor `useListQuery` items | `refetch` memo deps `[query]` (`:127`), which is a new object per render, so the callback is unstable; the search `draft` is not reset on back/forward (`:106-113`) | No requests |
| F16 | Reconciliation tabs refetch on window focus | `useReconTabQuery.ts:25-34` (no `refetchOnWindowFocus:false`) on heavy detection endpoints; 50/page | 1 per focus per mounted tab after 30 s |

Missing `enabled` guards: none found that would fire with an undefined id. `useLicenseBalanceLedger.ts:46`,
`useAllotmentDetail` (only mounted for a real id), `AllotmentAction.tsx:312,330,442` and `TaskDrawer.tsx:190,196` are gated.
LicenceCard fetches its ledger only when expanded (`LicenceCard.tsx:198-213`; one card open at a time,
`LicensesTable.tsx:64`), so there is no per-row storm on the register.

### 3.4 Estimated requests per page load (code-derived, app bootstrap `auth/me/` excluded)

| Page | Cold load | Avoidable |
|---|---|---|
| `/licenses` | list ×(1-3) (F3) + k FK-detail GETs per deep-linked FK value (F4) | up to 2 + k |
| `/allotments`, `/bill-of-entries`, `/trades`, `/incentive-licenses` | list ×1 (hardcoded string defaults, `masterListConfig.ts:10-30`) | 0 on load; F1 and F3 on interaction |
| `/masters/<entity>` with `{"is_active": True}` default | list ×(1-3) | up to 2 |
| `/allotments/:id/allocate` | purchase-statuses (module cache) + notification-numbers + available-items + planned-item-names + `allotments/:id/` + allocation-initialization + available-licenses (gated) + `AllotmentFilters` HybridSelects (sion-classes, companies ×2, coalesced to 1 if concurrent) ≈ **9** | 1 (F12) when arriving from a card |
| `/reports/item-pivot` | available-norms + purchase-statuses ≈ 2, then 1 report per norm tab | F9 and F10 on interaction |
| `/reports/item-report` | purchase-statuses + sion-classes (module cache) + notification-numbers + available-items + report ≈ 5 | 0 |
| `/planning` | sion-classes (fetchAllPages, 1 page) + rules per SION ≈ 2 | +1 per interaction (F8) |
| `/license-ledger` | license-wise + summary = 2 (+N legacy, F11) | N |
| `/licenses/:id/overview` | see **06 §4.1** (5 on the Overview tab, `licenses/:id/` ×2) | covered by 06 §5 B1/B1b |

---

## 4. Practical reuse and implementation plan

Rules: every batch preserves existing workflows, permissions, fields and API params. No new dependencies. Each
batch is one owner (default `frontend-engineer`) with disjoint files where batches may run in parallel.
"Independent" means no owner decision is needed. "Blocked" names the decision.

| Batch | Scope | Files (owner) | Acceptance tests (vitest + RTL, `api.get` spy counts) | Rollback | Status |
|---|---|---|---|---|---|
| **B0** Characterisation | Pin current request counts before changing anything | **new** `pages/masters/MasterList.requests.test.tsx`, `pages/planning/LicensePlanningWorkspace.requests.test.tsx`, `pages/reports/ItemPivotReport.requests.test.tsx` (frontend-engineer) | Record today's counts for: cold `/licenses` with backend boolean/list defaults; page-size 50 then page 2; `/masters/x?page=2` with no defaults (F2); FK multi-select change; planning tab switch; typing min balance. Use `it.fails`/documented numbers so B1-B5 flip them | delete files | **Independent** |
| **B1** MasterList state loop (F1, F2) | Run the init effect only on entity change or *external* navigation: remember the last search string written by the sync effect in a ref and skip when equal; never reset `pageSize` on own writes | `pages/masters/MasterList.tsx` (frontend-engineer) | B0: page-size 50 → page 2 sends **exactly 1** GET with `page_size=50`; `/masters/x?page=2` stays on 2; existing deeplink/filters/trades/smoke suites pass; tighten `deeplink.test.tsx:94,104` to `toBe(1)` | revert file | **Independent** |
| **B2** Canonical filter values (F3) | Stringify at the MasterList boundary: `handleFilterChange` and the backend-defaults effect map arrays to `join(",")` and booleans/numbers to `String()`. This is already the steady-state wire form, so the backend sees no new param shape | `pages/masters/MasterList.tsx` (same owner, after B1) | Cold `/licenses` with boolean/list defaults: **≤ 2** list GETs (1 if the unfiltered first request is also gated, see note). FK change: **1** GET, carrying `field=1,2` | revert file | **Independent**. Note: gating the very first request until metadata defaults are known needs either a metadata endpoint or accepting the first request. Do not invent an endpoint; keep ≤ 2 |
| **B3** FK selected-label cache (F4) | `DebouncedAsyncSelect` reuses `_fkDetailCache`/`_fkInFlight` from `components/fkDetailCache.js:9-10` (as `AsyncSelectField` does) and skips lookup when the ids equal the current `selectedOption` values | `components/DebouncedAsyncSelect.tsx` (frontend-engineer) | Select 3 values → **0** detail GETs; deep link with `exporter=1,2` → 2 GETs on first mount, 0 on remount; labels unchanged | revert file | **Independent** (parallel with B1/B2) |
| **B4** ItemPivot (F9, F10) | Remove the parameterless reload effect (`ItemPivotReport.tsx:450-455`); debounce the min-balance input with the existing `useDebounce` (400 ms) | `pages/reports/ItemPivotReport.tsx`, `pages/reports/ItemPivotFilters.tsx` (frontend-engineer) | Typing "5000" → 1 report GET, 0 extra available-norms GETs; report params unchanged | revert 2 files | **Independent** |
| **B5** Planning SION list (F8) | Load sion-classes once: deps `[]` with the initial `?sion=` read from a ref, or a `useQuery` on `qk.masters("sion-classes").list(...)` with `staleTime: Infinity` | `pages/planning/LicensePlanningWorkspace.tsx` (frontend-engineer) | Tab switch, rule select and SION select → 0 sion-classes GETs; the `?sion=E5` deep link still preselects | revert file | **Independent** |
| **B6** Allotment key unification (F12) | AllotmentAction reads `qk.allotments.detail(String(id))`; invalidations add `qk.allotments.detail(String(id))`; features pass `String(id)` | `pages/AllotmentAction.tsx`, `features/allotment/useAllotmentDetail.ts`, `features/bill-of-entry/tabs/AllotmentMappingTab.tsx` (one owner) | Card expanded then navigate to allocate within 30 s → 0 extra `allotments/:id/` GETs; after an allocation the detail key is invalidated (spy on `invalidateQueries`) | revert 3 files | **Independent** (aligns with 06 §4.2 id-stringify rule) |
| **B7** Master options on TanStack (F13) | `useMasterOptions` internals → `useQuery` (`qk.masters('purchase-statuses'\|'sion-classes').list`, `staleTime: Infinity`, retry default). Public hook signature `{options, loading}` unchanged | `hooks/useMasterOptions.ts`, `hooks/useMasterOptions.test.ts` (frontend-engineer) | Two consumers mounted → 1 GET; a failed fetch retries and is not cached as `[]`; existing 3 consumers untouched | revert 2 files | **Independent**. Consumers need a `QueryClientProvider` (App already has one; check consumer tests) |
| **B8** 429 resilience | `queryClient` `retry: (n, e) => status !== 429 && n < 1`; interceptor shows one throttled toast with `Retry-After` | `api/queryClient.ts`, `api/axios.js` (frontend-engineer) | A mocked 429 → 1 request (no retry) + 1 toast; 5xx behaviour unchanged (`axios.js:203`) | revert 2 files | **Independent** for the retry rule. **Toast copy is user-visible**: get owner OK on wording. Also hand the stale `RATE_LIMITING_GUIDE.md` to docs |
| **B9a** Fix list contract before adoption (F14) | `toQuery`/`writeListParams` emit comma-joined arrays (the backend contract, `master_view.py:424-452`); update `listContract.test.ts:15` | `lib/listContract.ts`, `lib/listContract.test.ts` (frontend-engineer) | Array filter → `f=1,2`; round-trip parse returns the same list; `useListQuery.test.tsx` passes | revert 2 files | **Independent** (0 consumers, so no runtime change) |
| **B9b** First `useListQuery` + `Pagination` consumer | Migrate one *simple* list first: `useReconTabQuery` (internal state → `useListQuery` with `urlPrefix` per tab) or UserList (`useSmoothListFilters`). Keep `DataPagination` visuals by mapping props, or swap to `Pagination` (visual change) | `pages/reconciliation/useReconTabQuery.ts` **or** `pages/admin/UserList.tsx` (one owner) | Same endpoint, same params (`page`, `page_size=50`); 1 GET per page change; URL deep link restores page | revert file | **Blocked: new owner decision** (propose a register entry, e.g. "OD-RF-1 list URL shape"): putting tab page/page_size into the URL is a user-visible URL change, and swapping `DataPagination` → `Pagination` changes visuals |
| **B9c** MasterList onto `useListQuery` + `FilterBar` | Replace B1/B2 internals with `useListQuery`, map `filter_config` → `FilterDef[]`, keep `AdvancedFilter` UI until the FilterBar look is approved | `pages/masters/MasterList.tsx` (+ an adapter in `components/filters/`) | All four MasterList suites + B0 counts at 1 per interaction; the `/licenses?search=<10 digits>` → `license_number` rewrite (`MasterList.tsx:405-414`) and the trades `-invoice_date` ordering (`:425-427`) preserved | revert | **Blocked:** after B1, B2 and B9a; FilterBar presentation needs owner approval (05 §2; 04 §6.4) |
| **B10** Tables and forms | Adopt `components/data-table` / `components/form` | per 10_PACKAGE_REVIEW | n/a | 10_PACKAGE_REVIEW option C | **Blocked: 10_PACKAGE_REVIEW (A/B/C, NOT APPROVED)**. **No-dependency path:** build list tables on the existing `components/ui/table.tsx` + `license-overview/SortableHeader.tsx` (3 consumers) with server ordering through `?ordering=`; forms keep controlled `useState` + `shared/FieldGrid` for read views and a small local `useFieldErrors` helper; delete the two untracked dirs (option C) |
| **B11** Dead code | Delete `BalanceTab.tsx`, `LedgerTab.tsx` (+ `ServerError.tsx`, `Sidebar.tsx`, 01 §7 list) | per D6 | `tsc` exit 0, full vitest, index rebuild | `git revert` | **Blocked: D6** (add ServerError to D6) |
| **B12** Lazy-retry parity | Switch the 14 plain `lazy` imports (`AppRoutes.tsx:44-50,56,59-61,65-67`) to `lazyLoadWithRetry` | `routes/AppRoutes.tsx` (frontend-engineer) | `AppRoutes.licenseRedirect.test.tsx` passes; a route renders after a simulated chunk failure + retry | revert file | **Independent** |
| **B13** Nav discoverability | Link `/reconciliation-issues` and the 7 unlisted report routes, or retire them (and `/pdf-viewer`) | `routes/config.ts`, `components/TopNav.tsx` | role-filtered nav test (`TopNav.test.tsx`) | revert | **Blocked: owner decision** (a navigation/feature change; not to be assumed) |
| **B14** LicenseLedger N+1 (F11) | Confirm with the backend owner whether `license-wise/` still omits `transactions`. If not, remove the enrichment; if yes, cap concurrency (e.g. 4 at a time) | `pages/LicenseLedger.tsx` | 250-licence legacy payload → ≤ 4 concurrent detail GETs; output identical | revert file | **Blocked: backend verification** (django-architect), not a business-rule change |

Suggested order: **B0 → (B1 → B2) ∥ B3 ∥ B4 ∥ B5 ∥ B6 ∥ B9a ∥ B12 → B7 → B8**, then the blocked items as decisions
land. The B1/B2 pair is one owner on one file; all other parallel batches have disjoint files. Licence-overview
key consolidation stays in **06 §5 (B1/B1b)** and the card-planning refresh in **D5**. Neither is duplicated here.

### Hand-offs

- **a11y-architect:** if B9b/B9c adopt `Pagination`/`FilterBar`, review their focus order and live-region
  "Updating results" (today `MasterList.tsx:991` uses `role="status"` and `AdvancedFilter.tsx:353`).
- **docs owner:** `docs/guides/RATE_LIMITING_GUIDE.md` rates are stale versus `settings.py:299-310`.
- **django-architect:** B14 verification. Also: `master_view.py` ignores repeated plain keys, so document the
  multi-value wire contract (comma or `field[]`) in the API docs.

### Risks

- F2 is suspected only. B0 must prove it before B1 claims a fix.
- B2 changes the first request for FK arrays from `field[]=` to `field=1,2`. The backend accepts both in
  `master_view.py`; licence/BOE/allotment/trade viewsets with their own filter code must be checked by B0
  fixtures against the steady-state requests they already receive (the second request today is already comma form).
- B6 and B7 alter cache identity. Prefix invalidations elsewhere (`['allotments', id]`) must be extended, not replaced.
- No change here touches CIF/balance math, permissions or API response shapes. No BUSINESS-RULE, API CONTRACT or
  SCHEMA change is proposed.
