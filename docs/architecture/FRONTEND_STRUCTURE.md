# Frontend structure audit (Phase 1, discovery only)

Scope: `frontend/` SPA. Evidence from `.claude/index/dependents.tsv`, `CODE_MAP.md`, and `wc`/`grep` run 2026-11-16. No source modified.

## 1. Current `src/` tree

| Dir | Files | Purpose |
|---|---|---|
| `pages/` | 201 | Route screens + colocated helpers/hooks/tests. Subdirs: `admin`, `auth`, `errors`, `license-balance`, `license-overview`, `masters` (32 incl. `tables/`, `hooks/`), `planning`, `reconciliation`, `reports` (50), `settings` |
| `components/` | 72 | Shared + domain components (flat, ~45 at top level); subdirs `ui` (18 shadcn), `primitives` (DetailTable, EntityCard), `filters` (FilterPanel), `motion`, `planning`, `reports` |
| `utils/` | 27 | Date/number format, errors, forms, downloads, ledger adapters; 13 are `.js` |
| `services/` | 14 | `services/api/{allotment,boe,license,master}Api.js`, `mdsApi.ts`, `planningRuleApi.ts`, plus ledger download helpers at `services/` root |
| `hooks/` | 14 | Generic hooks; 8 are `.js` (`hooks/index.js` barrel) |
| `api/` | 5 | `axios.js` (shared client), `queryClient.ts`, `tasks.js`, `users.js` |
| `test/` | 5 | `setup.ts` (vitest setupFiles), smoke/hook tests |
| `types/` | 3 | `canonicalLedger.ts`, `index.ts`, `reportEnvelope.ts` (very thin; page-local `types.ts` are the norm) |
| `context/` | 3 | `AuthContext`, `ParsingStatusContext`, `ThemeContext` |
| `routes/` | 5 | `AppRoutes.tsx`, `ProtectedRoute.tsx`, `authorizationRoles.ts(+test)`, `config.js` |
| `layout/` | 2 | `AdminLayout.tsx`, `Sidebar.tsx` |
| `lib/` | 2 | `utils.ts` (`cn`), `accessibility.ts` |
| `tests/` | 2 | `responsive.test.ts`, `filters/` |
| `theme/` | 2 | `tabler.css`, `tokens.js` |
| `styles/` | 1 | `tailwind.css` |
| `assets/` | 1 | |
| root | | `App.tsx`, `main.tsx`, `App.css`, `index.css`, `constants.js`, `vite-env.d.ts` |

326 `.ts/.tsx` vs 33 `.js` files under `src/`.

### Overlaps
- `api/` vs `services/api/`: both hold endpoint wrappers. `api/axios.js` is the client (110 dependents); `api/tasks.js`, `api/users.js` are endpoint wrappers living beside it, while `services/api/*` holds the rest. `services/` root also holds ledger download logic.
- `test/` vs `tests/`: `test/setup.ts` is wired in `vitest.config.ts:20`; `tests/` has 2 entries. Most tests are colocated (78 test files under `src/`).
- `theme/` vs `styles/`: `main.tsx` imports `theme/tabler.css` then `styles/tailwind.css` (Tailwind primary; tabler.css is leftover design-system overrides). `theme/tokens.js` is JS tokens.
- `utils/` vs `lib/`: `lib/utils.ts` (`cn`, 62 dependents, shadcn convention) vs 27 `utils/` modules; `lib/accessibility.ts` has no clear reason to be separate.
- `hooks/` vs page-local hooks (`pages/**/use*.ts`): ~20 domain hooks live under `pages/`.

## 2. Routing
- Router: `BrowserRouter` in `App.tsx:17` (react-router-dom ^7.9.6, `<Routes>` declarative, no data router/loaders). Single `<Suspense fallback={<PageLoader/>}>` in `routes/AppRoutes.tsx` (339 lines).
- Guard: `routes/ProtectedRoute.tsx` props `requiredRole`, `requiredAnyRole`, `requireSuperuser`; shows "Loading..." while auth loads, `/login` if no user, `/403` if unauthorised. Every route wraps `ProtectedRoute > AdminLayout > Page` inline (layout is repeated per route, not a layout route). Role constants in `routes/authorizationRoles.ts` (only `REPORT_ROLES` imported); other role arrays are inline literals in `AppRoutes.tsx`, with a parallel `utils/roleConstants.js` and `routes/config.js`.
- Lazy loading: all pages except `Login`, `PasswordReset`, `Unauthorized`, `NotFound`, `Forbidden` are lazy. Two mechanisms mixed: `lazyLoadWithRetry` (`utils/lazyLoad.js`) vs plain `React.lazy` (SionE*, ExpiringLicenses, ActiveLicenses, DownloadLicense, TradeForm, LedgerUpload, LicenseLedger, LicenseLedgerDetail, LicenseOverviewPage, LicensePlanningWorkspace, PDFViewer).

| Path | Page | Guard |
|---|---|---|
| `/login`, `/forgot-password`, `/401`, `/403` | Login, PasswordReset, Unauthorized, Forbidden | public |
| `/` | redirect to `/dashboard` | authenticated |
| `/dashboard`, `/profile` | Dashboard, Profile | authenticated |
| `/licenses`, `/licenses/create`, `/licenses/:id/edit` | MasterList / MasterForm | LICENSE_MANAGER/VIEWER (list); LICENSE_MANAGER |
| `/planning` | LicensePlanningWorkspace | LICENSE_MANAGER |
| `/allotments`, `/create`, `/:id/edit`, `/:id/allocate` | MasterList/MasterForm/AllotmentAction | ALLOTMENT_MANAGER/VIEWER; MANAGER |
| `/bill-of-entries`, `/create`, `/:id/edit`, `/:id/generate-transfer-letter` | MasterList/MasterForm/BOETransferLetter | BOE_MANAGER/VIEWER(+TL_GENERATE, ACCOUNT_ACCESS); BOE_MANAGER |
| `/trades`, `/trades/create`, `/trades/:id/edit` | MasterList / TradeForm | TRADE_MANAGER/VIEWER; TRADE_MANAGER |
| `/reconciliation`, `/reconciliation-issues` | ReconciliationPanel / ReconciliationIssues | BOE_MANAGER, TRADE_MANAGER, ACCOUNT_ACCESS (+viewers/TL_GENERATE on issues) |
| `/incentive-licenses`, `/create`, `/:id/edit` | MasterList/MasterForm | INCENTIVE_LICENSE_MANAGER/VIEWER |
| `/ledger-upload` | LedgerUpload | LICENSE_MANAGER, LEDGER_MANAGER |
| `/license-ledger`, `/download-requests`, `/download-requests/:requestId`, `/package-readiness/:jobId`, `/:licenseId/:itemId`, `/:licenseId` | LicenseLedger, LicenseDownloadRequests, ...Detail, LicenseLedgerPackageReadiness, LicenseLedgerDetail | LICENSE_MANAGER, TRADE_MANAGER/VIEWER, LEDGER_MANAGER |
| `/licenses/:id/overview` | LicenseOverviewPage | LICENSE/BOE/TRADE managers and viewers |
| `/licenses/:id/balance` | redirect to overview | none (redirect) |
| `/pdf-viewer` | PDFViewer (no AdminLayout) | authenticated |
| `/settings` | Settings | superuser |
| `/masters/:entity` (+`/create`, `/:id/edit`) | MasterList / MasterForm | authenticated; create/edit USER_MANAGER |
| `/admin/users`, `/create`, `/:id/edit`, activity log | UserList/UserForm/ActivityLog | USER_MANAGER |
| 11 `/reports/*` (parle sion-e1/e5/e126/e132, expiring-licenses, active-licenses, download-license, item-pivot, item-report, planned-report, license-purchase-profit) | data-driven via `REPORT_ROUTES` | `REPORT_ROLES` |
| `*` | NotFound | public |

(Lines 150-339 of `AppRoutes.tsx` read via grep; tail of file, ActivityLog path and wildcard not individually re-verified.)

## 3. API layer
- One axios instance: `api/axios.js:11` (`baseURL` from `VITE_API_URL` or `/api/`, CSRF header, Bearer from `localStorage.access`). Request interceptor injects token; response interceptor handles 401 with a single shared `refreshPromise` (`refreshAccessToken`, uses bare `axios.post` to `auth/refresh/`); `clearStoredAuth`, cross-tab `AUTH_SESSION_EVENT_KEY`, hard `window.location.assign('/login?...')`. Also in-flight GET dedup by monkey-patching `api.get` (`axios.js:~45-80`). Tokens in localStorage (`access`, `refresh`, `user`).
- No second axios instance found (`axios.create` appears only at `axios.js:11`). No raw `fetch(` in non-test source found by grep of API calls (matches were `refetch`). Bare `axios` is used only for the refresh call.
- Call style is mixed: 107 files import `api/axios` directly (inline calls in pages/components); 25 files import `services/api` wrappers. Wrappers: `allotmentApi.js`, `boeApi.js`, `licenseApi.js`, `masterApi.js` (JS, untyped), `mdsApi.ts`, `planningRuleApi.ts` (typed, 15 dependents, tested). Barrel `services/api/index.js` exposes namespaces + default exports.
- Typing: wrappers in JS => responses untyped; `tsconfig` `strict:false` (`tsconfig.json:23`), `allowJs:true`, `checkJs:false`. Typed response shapes exist only for ledger (`types/canonicalLedger.ts`, `reportEnvelope.ts`) and page-local `types.ts`.

## 4. State / data fetching
- Contexts: `AuthContext` (31 dependents; exports `AuthContext`, `hasRole`, `hasAnyRole`), `ParsingStatusContext`, `ThemeContext`.
- TanStack Query v5 is present: `QueryClientProvider` in `main.tsx`, `api/queryClient.ts` (`staleTime` 30s, `retry` 1). Used in 32 files (`useQuery`/`useMutation`), e.g. ledger download pages, reconciliation tabs, `MasterList`, `UserList`. The rest use `useEffect` + axios + local state (e.g. `useLicensePurchaseProfitReportData.ts`, `hooks/useApiCall.js`). No shared query-key factory observed; keys are inline strings (`LicenseDownloadRequestDetail.tsx:7`). `components/fkDetailCache.js` is a hand-rolled cache. Devtools lazy-loaded in DEV only.

## 5. Components
- shadcn primitives in `components/ui/` (18 files; `button` 56 dependents, `card` 32, `badge` 26, `input` 19, `dialog` 11); `ui/index.js` barrel. Imported via `@/` alias (in vite, vitest, tsconfig) while most other code uses relative paths.
- Legacy/non-shadcn shared pieces at `components/` root: `DataTable.tsx` (8 dependents), `AccordionTable`, `PageHeader` (22), `ConfirmDialog` (5) vs `ui/dialog` + `hooks/useConfirmDialog.tsx`, `ErrorBoundary` vs `GlobalErrorBoundary` vs `ErrorScreen`, `FormField`, `AsyncSelectField` / `DebouncedAsyncSelect` / `HybridSelect` / `item-async-select.tsx` (four async-select variants), `DataFilter` / `AdvancedFilter` / `filters/FilterPanel` / `DateRangeFilter` / `ActiveFilters`, `StatCard` (components/StatCard.tsx, 5 dependents) duplicated by `pages/license-overview/StatCard.tsx` and `SummaryCard.tsx`, `primitives/{DetailTable,EntityCard}`, modals (`LicenseBalanceModal`, `AllotmentFormModal`, `OwnershipDetailsModal`, `TransferLetterModal`). Inline tables in `LicenseDownloadRequests.tsx` hand-roll `<table>` rather than `DataTable`. Duplicate hooks: `hooks/useModal.js`, `hooks/useToast.js` (2 importers) vs sonner (61 importers).
- Largest files (lines): ItemPivotReport 1951; AllotmentAction 1833; masters/MasterList 1729; TradeForm 1644; masters/tables/LicensesTable 1441; components/planning/PlanningEditor 1265; masters/tables/LedgerTab 1159; masters/MasterForm 1137; LicenseLedger 1078; components/LicenseBalanceModal 1059; Dashboard 885; masters/NestedFieldArray 840; components/TaskDrawer 772; reports/LicensePurchaseProfitReport 699; LicenseLedgerDetail 680 (Settings 672). Note `LicenseDownloadRequests.tsx` and `LicenseDownloadRequestDetail.tsx` are minified single-line JSX (unformatted, hard to review).

## 6. Remaining legacy
- `react-toastify`: 0 files. `bootstrap-icons` imports: 0. Toasts: sonner (61 importers). Bootstrap `bi bi-*` strings: only in `components/Icon.tsx` (a `BI_TO_LUCIDE` shim, 8 importers) and `components/primitives/EntityCard.tsx:39` (mapping table). Backend/menu config may still pass `bi-*` names through these shims.
- `.js` files: 33 (constants.js; utils x13; hooks x8; api x3; services/api x5; routes/config.js; components/fkDetailCache.js, ui/index.js; theme/tokens.js). `main.tsx` comment still mentions Bootstrap Icons; `theme/tabler.css` still loaded.
- `any`: top files by `: any|as any` count: masters/MasterForm.tsx 19, reports/ItemPivotReport.tsx 17, masters/hooks/useMasterFormCalculations.ts 17, masters/hooks/useMasterFormSubmit.ts 16, itemReport/ItemReportTable.tsx 9, itemPivotReportUtils.ts 9, NestedFieldArray.tsx 6, ItemReport.tsx 5. `strict:false` hides implicit any.
- Stale root artefacts in `frontend/`: `jest.config.js` (vitest is the runner), `route-*test.mjs/.js`, many `*.md` audit docs, `dist/`.

## 7. Tests & tooling
- Vitest (`vitest.config.ts`): jsdom, globals, `setupFiles ./src/test/setup.ts`, include `src/**/*.{test,spec}.{ts,tsx}`, `@` alias. 78 test files under `src/` (colocated). Playwright: `playwright.config.ts`; specs in `e2e/` (13) and `playwright/` (1: accessibility).
- Scripts (`package.json`): `dev`, `build`, `lint` (eslint .), `format:check` (eslint --max-warnings=0), `typecheck` (tsc --noEmit), `test` (vitest run), `test:watch`, `test:e2e`, `preview`. Gate: `scripts/dev/quality-gate.sh frontend` (not run in this task).
- TS: `strict:false`, `noUnused*` false, `allowJs`, `checkJs:false`, path `@/*` -> `./src/*`. ESLint flat config `eslint.config.js` with react-hooks v7.
- Tests/typecheck/lint/build: NOT RUN (discovery only).

## 8. Proposed target structure (incremental, import-preserving)

```
src/
  app/            App.tsx, main.tsx, providers (Query, Auth, Theme), router, queryClient
  features/
    licenses/     {api,components,hooks,types,routes}  <- pages/license-overview, license-balance, components/LicenseBalanceModal, planning
    allotments/   <- AllotmentAction, AllotmentFilters, AllotmentFormModal, allotmentApi
    boe/          <- BOETransferLetter, TransferLetter*, boeApi
    trades/       <- TradeForm, TradeConfigCard, tradeFormHelpers, TradesListView
    ledger/       <- LicenseLedger*, LedgerUpload, DownloadRequests*, services/licenseLedger*, types/canonicalLedger
    reconciliation/ <- ReconciliationPanel/Issues, pages/reconciliation
    reports/      <- pages/reports, components/reports
    planning/     <- pages/planning, components/planning, planningRuleApi
    masters/      <- pages/masters (+ masterApi), entity table config
    admin/        <- pages/admin, api/users, settings
    auth/         <- Login, PasswordReset, AuthContext, ProtectedRoute, authorizationRoles
    dashboard/    <- Dashboard, dashboardContract/date utils
  components/ui/  shadcn only; plus components/shared/ (DataTable, PageHeader, EmptyState, FormField, selects, filters)
  layouts/        AdminLayout, Sidebar, TopNav
  lib/            cn, http client (api/axios), formatters (utils/dateFormatter, numberFormatter), a11y
  hooks/ types/ test/ (single test dir: setup + utilities) styles/ (single: tailwind.css + tokens)
```

### Migration path (each step independently shippable; gate after each)
1. Low risk, no import changes: delete/mark dead root artefacts (`jest.config.js`, `route-*test*`); merge `tests/` into colocated or `test/`; fold `theme/tokens.js`/`tabler.css` next to `styles/` after checking importers; stale comments.
2. Add path aliases (`@app`, `@features`, `@shared`) in `tsconfig.json`, `vite.config.js`, `vitest.config.ts` (the `@` alias already exists in all three); no code moves yet.
3. Move leaf domains first (few dependents, mostly self-contained): `pages/planning` + `components/planning` + `planningRuleApi` (15 dependents -> leave a re-export stub at old path), `pages/reports`, `pages/reconciliation`, `pages/license-overview`, `pages/admin`. Router lazy imports change one line each; leave re-export file at old location until all importers move.
4. Unify API: keep `api/axios.js` path as re-export of `lib/http`; move `api/tasks.js`/`users.js` into `features/*/api`; convert `services/api/*.js` to `.ts` with response types one file at a time (keeps `services/api/index.js` barrel). Do NOT change URLs, interceptor, or auth/refresh behaviour.
5. Route modularisation: per-feature route arrays composed in `app/router`; extract a layout route (`<ProtectedRoute><AdminLayout><Outlet/>`) and move inline role arrays to `authorizationRoles.ts`. Guard semantics must remain identical (permission surface, see safety rules).
6. Shared components: consolidate duplicates (StatCard x2, ErrorBoundary x2, async selects x4, ConfirmDialog vs useConfirmDialog, `hooks/useToast`/`useModal`) behind re-exports; remove after dependents migrate.
7. Decompose >1000-line files (ItemPivotReport, AllotmentAction, MasterList, TradeForm, LicensesTable, PlanningEditor, LedgerTab, MasterForm, LicenseLedger, LicenseBalanceModal) into feature subcomponents/hooks after tests exist; business-rule files (balance/allocation math) need `cif-balance-auditor`.
8. Turn on `strict` per-feature via a separate tsconfig (`tsconfig.strict.json` include list) and retire `any` hotspots (MasterForm family first).

### Risk map (fan-in from `dependents.tsv`)
- Low risk: `pages/reports/*`, `pages/reconciliation/*`, `pages/license-overview/*`, `pages/admin/*`, `pages/planning/*`, `components/reports`, `components/planning`, `utils/{ledgerDisplayRows,licenseCopyPdf,exportFilename,dateRangePresets}`, `hooks/useSmoothListFilters`, root cruft.
- Medium: `services/api/*` (25 importers; `planningRuleApi` 15), `components/DataTable` (8), `ConfirmDialog` (5), `StatCard` (5), `hooks/useDebounce` (8), `layout/*`, `routes/*`.
- High fan-in (move only via re-export shims, last): `api/axios.js` (110), `lib/utils.ts` (62), `components/ui/button` (56), `ui/card` (32), `context/AuthContext` (31), `ui/badge` (26), `utils/dateFormatter.js` (22), `components/PageHeader` (22), `utils/documentDownload.ts` (20), `ui/input` (19). Recommendation: keep these paths physically in place (or leave 1-line `export * from` stubs) and do not touch in early phases.
