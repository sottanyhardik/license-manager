# 09 - UI/UX and Frontend Architecture Assessment (Phase Zero, read-only)

Scope: `frontend/src` (326 TS/TSX + 33 JS files, ~62k LOC incl. tests; 78 vitest files; 17 playwright specs).
Date of measurement: 2026-11-15, branch `feature/version5`. All numbers come from grep/wc run in this task.
Prior memory (`.claude/memory/graph-state.md`, dated 2026-06-17) is partly stale: MasterList is now 1729 LOC (was 2153), MasterForm 1137 (was 2455), routes 36+ with Overview/Planning/Reconciliation pages added, and `styles/designSystem.js` no longer exists.

## 1. Route map (`src/routes/AppRoutes.tsx`)

Single file, ~330 LOC, every route hand-wrapped in `<ProtectedRoute><AdminLayout>...` (no layout route, no route objects, no loaders). Pages are lazy via two different mechanisms: `lazyLoadWithRetry` (utils/lazyLoad.js) for ~20, bare `React.lazy` for ~14 (inconsistent; only the first retries on chunk failure). Login, PasswordReset, 401/403/404 are eager. `ProtectedRoute` loading state is a bare `<div>Loading...</div>` (ProtectedRoute.tsx:25). Role arrays are inlined per route (duplicated 6+ times for the ledger family) and mirrored in `authorizationRoles.ts`, `utils/roleConstants.js` and Sidebar (3 sources of role truth).

| Surface | Routes | Page component | Notes |
|---|---|---|---|
| Dashboard | /dashboard | Dashboard (885) | own tables, own StatCard usage |
| Licences | /licenses, /create, /:id/edit | MasterList / MasterForm | generic god-components keyed by `entityName` |
| Licence overview | /licenses/:id/overview (+ `/balance` redirect) | LicenseOverviewPage (244) | already a 6-tab workspace: overview, boes, allotments, planning, items, invoice-ledger |
| Planning | /planning | LicensePlanningWorkspace (473) + PlanningEditor (1265) | planning also embedded as a tab in overview |
| Allotments | /allotments, /create, /:id/edit, /:id/allocate | MasterList / MasterForm / AllotmentAction (1833) | allocate is a separate bespoke page |
| BOE | /bill-of-entries, /create, /:id/edit, /:id/generate-transfer-letter | MasterList / MasterForm / BOETransferLetter | |
| Trades | /trades, /create, /:id/edit | MasterList (+TradesListView) / TradeForm (1644) | TradeForm is NOT MasterForm although MasterForm also has `entityName==='trades'` branches (MasterForm.tsx:762,971) |
| Incentive licences | /incentive-licenses (+create/edit) | MasterList / MasterForm | |
| Reconciliation | /reconciliation, /reconciliation-issues | ReconciliationPanel (201) + 7 tab files, ReconciliationIssues (281) | two entry points over the same domain |
| Ledger | /ledger-upload, /license-ledger, /license-ledger/:licenseId[/:itemId], /download-requests[/:id], /package-readiness/:jobId | LicenseLedger (1078), LicenseLedgerDetail (680), 4 small pages | |
| Reports | 11 routes via `REPORT_ROUTES` array | see below | |
| Admin | /admin/users (+create/edit), /admin/activity-log, /settings, /profile, /masters/:entity (+create/edit) | UserList/UserForm (bespoke, not MasterList), ActivityLog, Settings | /masters/:entity create/edit gated USER_MANAGER only |
| Misc | /pdf-viewer (no AdminLayout), /401 /403 /404 | | |

Near-duplicate / mergeable pages
- SionE1 / SionE5 / SionE126 / SionE132: 10-line wrappers around `SionNormReport` (443). Collapse to one route `/reports/sion/:norm` (keep old paths as redirects).
- ActiveLicenses (25) and ExpiringLicenses (24) are thin wrappers; they and DownloadLicense (326) are the same "licence list + filters + export" shape. One `LicenceListReport` config.
- ItemReport (485) vs ItemPivotReport (1951) vs PlannedReport (380) vs LicensePurchaseProfitReport (699): all "filter -> table -> totals -> export"; ItemPivot and ItemReport share filter concepts (`ItemPivotFilters` vs `itemReport/ItemReportFilters`) but have separate filter components and query-string builders.
- LicenseLedgerDetail (680, route `/license-ledger/:licenseId/:itemId`) vs License Overview (items/invoice-ledger/customs ledger tabs) vs `masters/tables/LedgerTab` (1159) + `BalanceTab` (528) (inline accordion detail in MasterList) vs `LicenseBalanceModal` (1059): four different renderings of the same licence balance/ledger data from different endpoints (`licenses/:id/balance-ledger/`, `overview-*`, ledger detail). This is the biggest merge opportunity (section 7).
- ReconciliationPanel vs ReconciliationIssues vs the Overview "FinalReconciliationSection".
- UserList/UserForm and ActivityLog re-implement list/filter/pagination instead of using MasterList; `/masters/:entity` already covers simple masters.
- LicenseDownloadRequests (15) / Detail (7): tiny, fine; could be tabs of the ledger page.

## 2. Component inventory

### 2.1 UI primitives
- `components/ui/` (shadcn, 17 files): alert, badge, button, card, checkbox, dialog, dropdown-menu, input, label, select (react-select based, not Radix Select), separator, skeleton, sonner, switch, tabs, textarea, tooltip. Missing: table, form, popover (dep installed), scroll-area (dep installed), sheet/drawer, accordion, pagination, combobox, radio, date picker, command (cmdk used ad hoc), breadcrumb, data-grid.
- `components/ui/index.js` is a broken legacy barrel: it re-exports `../primitives/{Surface,EmptyState,Skeleton,IconChip,StatusBadge,SectionHeader,PageHeader,Button,Toolbar,FilterBar,StatCard,Card}` but `components/primitives/` contains only `DetailTable.tsx` and `EntityCard.tsx`. No one imports it (all 56 button dependents import `ui/button` directly). Dead; delete.
- Legacy primitives still alive: `components/primitives/DetailTable` (85) and `EntityCard` (245), used by MasterList/TradesListView/AllotmentsTable only.
- Memory says "react-toastify to sonner done"; verified: 0 react-toastify imports, 61 sonner importers, dependency gone from package.json. `bootstrap-icons`: 2 files still contain `bi bi-` strings (those icons render blank per decisions.md).

### 2.2 Table / list implementations (not one; at least 9 patterns + 40 files with raw `<table>`)

| Implementation | LOC | Consumers | Notes |
|---|---|---|---|
| `components/DataTable.tsx` | 342 | MasterList, ReconciliationIssues, 6 reconciliation tabs | closest thing to a shared table; client-side; no virtualization |
| `components/AccordionTable.tsx` | 570 | MasterList only | expandable rows, hosts LedgerTab/BalanceTab |
| `pages/masters/MasterList.tsx` | 1729 | 5 entity routes + /masters/:entity | 30 useState, 47 `entityName ===` branches, list + filters + export + pagination + bulk actions + cards view |
| `masters/tables/LicensesTable` | 1441 | MasterList | bespoke licence table with accordion |
| `masters/tables/LedgerTab` / `BalanceTab` | 1159 / 528 | accordion rows | duplicate ledger/balance views, own math |
| `masters/tables/IncentiveLicensesTable`, `AllotmentsTable`, `GenericMasterCards` | 249 / 195 / 114 | MasterList | one table component per entity |
| `masters/TradesListView` | 291 | MasterList | grouped linked trades |
| `license-overview/*Table` (Customs 533, Financial 192, Sortable header 48) + tabs | ~1000 | Overview | own sortable header, own StatCard |
| Reports: ItemPivotReport 1951, ItemReportTable 413, SionNormReport 443, C969EntitlementTable 222, ItemUtilizationMatrix 188, PlannedReport | | | each own table markup |
| Others with raw `<table>`: AllotmentAction 1833, TradeForm 1644, PlanningEditor 1265, LicenseLedger 1078, LicenseBalanceModal 1059, Dashboard 885, ActivityLog, UserList, Settings, etc. | | | |

Pagination: `DataPagination` (126) used by only 3 pages; `usePagination` hook used by 1; others hand-roll.
Sorting: `SortableHeader` exists only inside license-overview; elsewhere ad hoc.

### 2.3 Form implementations
- `MasterForm` (1137) + `hooks/useMasterFormData|Submit|Calculations` (642 submit) + `NestedFieldArray` (840) + `entitySections.ts`: generic form for licences, allotments, BOE, incentive licences, masters; 16 `entityName ===` branches here, 10 more in submit hook.
- `TradeForm` (1644): bespoke; includes inline calculation logic.
- `AllotmentFormModal` (524), `TransferLetterForm` (432), `UserForm` (293), `ChangePasswordForm`, `Login`, `PasswordReset`, `Settings` (672), `AllotmentAction` filters, `LinkRecordModal`, `LinkTradeModal`, `BoeMergeModal`, `InlineNormEditor`: each own state handling.
- 9 files use raw `<form>`. No react-hook-form, zod, formik, yup anywhere (grep: 0). Validation is hand-rolled in `utils/formValidation.js`, `formErrors.js`, per-form code. `components/FormField.tsx` (203) is imported by nobody (dead), even though FORM_SYSTEM_V2.md specifies it.
- Selects: 3 layered async-select components (`AsyncSelectField` 426, `DebouncedAsyncSelect` 213, `HybridSelect` 145, plus `item-async-select`, `SionAsyncItemSelect`) all on react-select; date input: react-datepicker in 3 files only, native `<input type=date>` elsewhere.

### 2.4 Filter implementations
`AdvancedFilter` (303, MasterList only), `FilterPanel` (26, wraps), `DataFilter` (68, dead - 0 importers), `DateRangeFilter` (108, 6 users), `ActiveFilters` (179, 13 users), `DebouncedSearchInput`, plus bespoke filter bars: AllotmentFilters, ItemPivotFilters, ItemReportFilters, LicenseLedger filters (`licenseLedgerFilters.ts`), AllotmentAction inline filter state (defaults duplicated 3 times, lines 197/1259/1283/1619), `useSmoothListFilters`, `utils/filterPersistence.js`. Result: ActiveFilters chips are shared; the filter definitions and query-string builders (`reportQueryString.ts`, `buildLicensePurchaseProfitReportPath.ts`, `reportPaths.ts`, `itemPivotFilterHelpers.ts`) are not.

### 2.5 Modal / drawer / accordion
- Radix `ui/dialog` consumers (12): LicenseBalanceModal (1059), AllotmentFormModal, OwnershipDetailsModal, TransferLetterModal, LinkRecordModal, LedgerUpload, Settings, UserList, CustomsLedgerTable, ItemPivotReport, LicensePlanningPanel.
- Hand-rolled overlays (`fixed inset-0`/`role=dialog`, 7): ConfirmDialog (197, also `useConfirmDialog`), CommandPalette, TaskDrawer (772), TopNav, LinkTradeModal, BoeMergeModal, LoadingFallback. Focus trap / Esc behaviour therefore varies by overlay.
- Accordion: bespoke in AccordionTable, LicensesTable, BalanceTab, ItemsTab, MasterList (no shadcn accordion).
- Drawer: only TaskDrawer (custom). No Sheet primitive.

## 3. API client layer, data fetching, state

- Single axios instance `api/axios.js` (217 LOC, plain JS, `checkJs:false`): request interceptor, shared single-flight refresh (`refreshAccessToken`, lines 86-150), cross-tab auth events. Good. Only other `axios` import is the refresh call itself. Tokens in `localStorage` (api/axios.js:96,126).
- 107 files import `api/axios`; 293 raw `api.get/post/put/patch/delete` call sites across 81 files. URLs are string literals scattered through pages.
- Typed service layer is minimal and inconsistent: `services/api/{licenseApi 229, allotmentApi 159, boeApi 100, masterApi 131}.js` (untyped JS, 1-2 importers each - effectively dead/duplicate), `mdsApi.ts`, `planningRuleApi.ts` (12 importers, the one healthy module), `services/license*.ts` (ledger export/readiness/download requests), `api/tasks.js`, `api/users.js`. No generated API types / OpenAPI client. Response shapes are `any` (181 `: any`/`as any` hits).
- TanStack Query v5 IS present and provided in `main.tsx:27` (staleTime 30s, retry 1), used in 32 non-test files (reconciliation tabs, license-overview hooks, AllotmentAction, MasterList (1 query), TradeForm (1)). But 36 files still combine `useEffect` + api calls and 31 use `setLoading/setError` state: hybrid, not migrated. Heavy pages (ItemPivotReport: 17 useState, 6 useEffect, 0 useQuery; LicenseLedger; MasterForm data hook) remain hand-rolled. Query key factories exist in 4 places only (`reconKeys`, `licenseBalanceKeys`, `licenseOverviewKeys`, `licenseSionNormKeys`); other queries use inline arrays.
- Dead hooks: `useApiCall`, `useModal`, `useToast` (0 importers outside hooks/); `usePagination` and `useFileUpload` (515 LOC + 404 LOC test) have 1 importer each.
- Contexts: `AuthContext` (275; 31 dependents), `ParsingStatusContext` (80), `ThemeContext` (28). No global UI/store lib (good). Routing state in URL is used well in Overview (`?tab=`).

## 4. Forms/validation, errors, loading, empty states

- Validation: no schema library; per-form imperative checks; server field errors via `utils/formErrors.js` (see FORM_ERROR_HANDLING.md). TradeForm/MasterForm duplicate field-level calc and validation.
- Error handling: `GlobalErrorBoundary` + `ErrorBoundary` (App.tsx only), `ErrorScreen`, `errorUtils.js` `extractApiError` (toast.error pattern used widely). No per-route error element, no query-level error component; error display is ad hoc (toast vs inline banner vs nothing).
- Loading: `PageLoader` (LoadingFallback) for Suspense, `Skeleton` used in 13 files, spinner/"Loading..." text in 59 files, ProtectedRoute plain text. Inconsistent.
- Empty: `EmptyState` component used by only 6 pages; 30 files hand-write "No ... found" text.
- Toasts: sonner everywhere (consistent).

## 5. Design tokens, dark mode, accessibility

- Tokens: three layers coexist: shadcn CSS vars + Tailwind v4 (`styles/tailwind.css` 449 LOC), legacy `--tb-*` Tabler vars (`theme/tabler.css` 2457 LOC, `theme/tokens.js` 115, `index.css` 128, `App.css` 299) bridged so "both styling systems render pixel-identical" (tailwind.css:14). 26 TSX files still use `var(--tb-*)`; 41 files use inline `style={{}}`; only 7 files with raw hex. `tabler.css` still carries Bootstrap-era class rules (`.badge.text-dark !important`, tailwind.css:237) and Toastify CSS in index.css:116 for a removed lib.
- Dark mode: `[data-theme="dark"]` on `<html>` (index.css:8, tailwind.css:28 `@custom-variant dark`), `ThemeContext`. Works for tokens; documented defects: soft-token-as-text contrast in LicenseLedger (decisions.md), invalid `${var}20` CSS in several pages (fixed in some).
- Design docs at repo root (TABLE_SYSTEM_V2, FORM_SYSTEM_V2, FILTER_SYSTEM_V2, BUTTON/CARD/INPUT_SYSTEM_V2, DESIGN_SYSTEM_V2_*; 258 root .md files in total) are specifications, NOT implementation: `components/ui` has no table, no form-field (FormField.tsx exists but unused), no filter bar; the `ui/index.js` barrel referencing Surface/FilterBar/Toolbar points to files that do not exist. Treat these as intent only.
- Accessibility (sample): 99 files use aria-*; 55 live-region/role=alert hits; 3 non-test files still attach `onClick` to div/tr/span (helper `utils/clickable.ts` exists); 1 `<img>` without alt; hand-rolled overlays (7) bypass Radix focus management; react-select a11y varies; `lib/accessibility.ts` (584 LOC) is a large helper of unclear usage; there are axe-based e2e specs (login, trades, license-overview) but none for MasterList/AllotmentAction/Reports. Hand to `a11y-architect` for a real audit.

## 6. Business calculations in the frontend (CRITICAL - list for cif-balance-auditor)

Rule in `canonicalLedgerAdapter.js:9` says the UI "Must NOT recalculate balances, commissions, or totals"; the following code contradicts it to varying degrees (client-side arithmetic that can drift from backend).

| Location | What it computes | Risk |
|---|---|---|
| `pages/AllotmentAction.tsx:680-773` (`calculateMaxAllocation`, line 736 `qty*unitPrice` rounded to 2dp, 739 cap pairing), 1350-1356 actual vs plan position | allocation max qty/CIF, value from qty*unit price | HIGH - drives allotment writes; backend must re-validate |
| `pages/license-balance/allocationMath.ts:64-116` (+ test) | invoice remaining CIF vs allocated CIF, over-allocation EPS check | HIGH |
| `components/planning/PlanningEditor.tsx:258,332,405,431-436,681-692,721,768,800,893-896,1038-1046,1238-1242` | sums of planned qty/CIF, original/used/remaining per group, utilisation, totals row, `qty*unit` | HIGH - 61 matches; plan totals computed client-side |
| `pages/masters/tables/LedgerTab.tsx:235-254,364-382,510-525,715` | totals of BOE/allotment CIF and qty, rate = cif/qty, import totals (allotted, debited, billed_no_boe, balance), chooses license-level vs summed item balance (502-517) | HIGH - duplicates balance rules; comment at 502 documents a known double-count trap |
| `pages/masters/tables/BalanceTab.tsx:315,476` | total import balance reduce | MED |
| `pages/TradeForm.tsx:417-521` (`cif_inr = cif_fc*exc_rate` toFixed(2) at 456; exc_rate = cif_inr/cif_fc 464; amount/rate/pct forward and reverse 481-507; `calculateTotal` 517-521; displayed toFixed(2) at 1445,1557) | trade line amounts, rates, % | HIGH - money math with parseFloat/Math.round, different rounding rules (whole rupee 503-507, 3dp rates 429/487/492/497, 2dp elsewhere) |
| `pages/masters/hooks/useMasterFormCalculations.ts:133-193` | allotment cif_fc <-> unit_value_per_unit (`Math.ceil(x/qty*1000)/1000`, 155,172,193), `cif_inr = cif_fc*rate` 182; dates: registration, expiry (+1y / +2y incentive, lines 29-52) | HIGH - ceil rounding is a business rule; expiry derivation is a licence rule |
| `pages/masters/NestedFieldArray.tsx:133-157` | `cif_inr = value*rate`, trade-line `qty*rate` toFixed(2) | HIGH - duplicates TradeForm and useMasterFormCalculations (3 copies of the CIF INR formula) |
| `components/AllotmentFormModal.tsx` (7 hits), `components/LicenseBalanceModal.tsx` (4), `pages/reports/ItemPivotReport.tsx:1523` (+16 hits), `itemReport/ItemReportTotalsBar.tsx` (4), `ItemReportTable.tsx` (6), `license-overview/{OverviewTab,LicenseDetailsHeader,CustomsLedgerSection,ItemsTab,AllotmentsTab}.tsx` and `types.ts` (mostly field names/labels; verify), `ReconciliationPanel.tsx` (22 hits, mostly "recalculate" polling text, not math) | totals/percentages for display | MED/LOW - needs line-level audit |
| `utils/canonicalLedgerAdapter.js:37-122` | declared no-recalculation adapter | OK by design |

Note: per-line grep is coarse (358 pattern matches); items marked MED/LOW were not read line by line. Any move of this math to the backend, or to a single shared `lib/money` module, is a BUSINESS-RULE-adjacent change requiring `cif-balance-auditor` and tests.

## 7. Largest files (top 15 by LOC, excl. tests)

1. pages/reports/ItemPivotReport.tsx 1951
2. pages/AllotmentAction.tsx 1833
3. pages/masters/MasterList.tsx 1729
4. pages/TradeForm.tsx 1644
5. pages/masters/tables/LicensesTable.tsx 1441
6. components/planning/PlanningEditor.tsx 1265
7. pages/masters/tables/LedgerTab.tsx 1159
8. pages/masters/MasterForm.tsx 1137
9. pages/LicenseLedger.tsx 1078
10. components/LicenseBalanceModal.tsx 1059
11. pages/Dashboard.tsx 885
12. pages/masters/NestedFieldArray.tsx 840
13. components/TaskDrawer.tsx 772
14. pages/reports/LicensePurchaseProfitReport.tsx 699
15. pages/LicenseLedgerDetail.tsx 680
(then Settings 672, useMasterFormSubmit 642, LedgerUpload 633, accessibility.ts 584, AccordionTable 570.) Top 15 sum ~17.9k LOC (~29% of src).

## 8. Tests and type safety

- 78 vitest files (pages 55, utils 7, components 5, test/ 4, services 3, api/hooks/routes/tests 1 each); jsdom + `src/test/setup.ts`; no coverage thresholds configured. 52 non-test page files have no sibling test. Untested heavyweight: LicensesTable, LedgerTab, BalanceTab, TradeForm (smoke only), MasterForm (smoke only), MasterList (smoke + trades), ItemReport, Settings, ActivityLog, LicenseBalanceModal (1 test), TaskDrawer. Good tests exist for allocationMath, balanceMetricContract, planningRuleApi, licenseLedger*, Dashboard contract, SionE* reports.
- 17 playwright specs (e2e/ + playwright/): axe, responsive, visual login, real-data, ledger download.
- `tsconfig.json`: `strict: false` (line 23), `allowJs: true`, `checkJs: false` (19-20): 33 JS files, incl. the core `api/axios.js`, utils, services, hooks, are unchecked. 181 `any`. 0 `@ts-ignore`. 14 `eslint-disable`. `jest.config.js` is a leftover (project uses vitest).

## 9. Feasibility assessment

### (1) One generic list engine - FEASIBLE, HIGH value, MEDIUM-HIGH risk
Why feasible: server-side filtering/pagination already exists for the master lists; `DataTable` + `ActiveFilters` + `DataPagination` + `useSmoothListFilters` + `masterListConfig.ts` + `filterPersistence.js` are the seeds. Reports share the pattern filter -> query-string -> table -> totals -> export.
Why hard: MasterList carries entity-specific behaviours (BOE merge/parse, trade grouping and link/unlink, licence balance accordion, export formats, role-gated bulk actions, 47 branches). Approach: a headless `useListQuery(config)` (URL-synced filters/sort/page via TanStack Query) + presentational `<DataGrid columns rowActions expandedRow>`; entity behaviour supplied as config objects (`columns`, `filters`, `rowActions`, `expandedRow`, `exports`), with the 3 bespoke views (trades grouped, licence accordion, allotment cards) as `renderRow`/`expandedRow` plugins, not forks. Reports and admin lists (UserList, ActivityLog, reconciliation tabs) migrate first as they are simplest. Virtualization needed for ledger/pivot (not present today).

### (2) One generic form engine - FEASIBLE for ~70%, PARTIAL overall
MasterForm already is a config-driven engine (`entitySections.ts`, NestedFieldArray, calculations hook) but is coupled to entity names (31 branches across 4 files) and mixes calculations with UI. TradeForm (direction-dependent lines, CIF/incentive modes) and AllotmentAction (allocation, not CRUD) are workflow screens, not forms. Recommendation: adopt `react-hook-form` + `zod` (NEW DEPENDENCIES - requires human approval per safety.md) with a `<FormEngine schema sections>`; extract all derived-field math to pure, unit-tested `lib/calculations/*` functions with one rounding policy before touching forms; keep TradeForm as a composed form on the same primitives (FormField, FieldArray), not forced into the schema engine.

### (3) Licence Workspace (detail + ledger + allotments + BOE + invoices + reconciliation) - FEASIBLE, LOW-MEDIUM risk, partially done
`/licenses/:id/overview` (LicenseOverviewPage) already has tabs overview, boes, allotments, planning, items, invoice-ledger, deep-linkable via `?tab=`, per-tab queries (`useLicenseOverview*` hooks, `overview-*` endpoints), key factories and invalidation (LicenseOverviewPage.tsx:76-99). Missing from it: licence detail/edit (still MasterForm at `/licenses/:id/edit`), per-item ledger (`LicenseLedgerDetail`, `/license-ledger/:licenseId/:itemId`), reconciliation (separate pages, though `FinalReconciliationSection` exists), documents/TL (documents partially loaded in the header), the BalanceTab/LedgerTab accordion in MasterList, and `LicenseBalanceModal` (1059). The data layer is already server-driven per tab, so the merge is mostly route + composition work: add tabs `ledger`, `reconciliation`, `documents`, `details`; redirect `/license-ledger/:licenseId/:itemId` and `/licenses/:id/edit` into tabs; replace accordion/modal consumers with links into the workspace tab; delete LedgerTab/BalanceTab/LicenseBalanceModal after parity. Risk is in data parity (three views compute balance differently, see section 6) - do parity tests against the backend balance contract before deleting any view.

## 10. Top 10 UI/UX and frontend-architecture problems

1. Entity god-components: MasterList (1729, 47 entity branches) and MasterForm (1137, 31 branches across 4 files) are switch-on-entity monoliths; TradeForm/AllotmentAction/ItemPivotReport 1.6-2.0k each.
2. Financial arithmetic duplicated in the UI (section 6): CIF-INR formula in 3 places, 4 different rounding policies (whole rupee, 2dp, 3dp, `Math.ceil`), plan/ledger totals recomputed client-side despite the "UI must not recalculate" contract. Highest business risk.
3. Four competing representations of licence balance/ledger (Overview tabs, LedgerTab/BalanceTab accordion, LicenseBalanceModal, LicenseLedgerDetail) from different endpoints; users see the same licence through 4 navigation paths.
4. No shared table/list system: 9+ implementations and 40 files with raw `<table>`; inconsistent sort, pagination (3 users of DataPagination), sticky headers, empty/loading/error rendering.
5. Type safety is switched off: `strict:false`, 33 unchecked JS files including the axios core and untyped service modules; 181 `any`; no generated API types, so response-shape drift is invisible.
6. Data fetching is half-migrated: TanStack Query in 32 files vs 36 files of hand-rolled `useEffect`+axios and 293 scattered raw calls; query keys mostly inline; dead typed-service JS modules.
7. Forms: no schema/validation library, 9 raw `<form>`s, 5+ select variants on react-select, per-form validation and error mapping; FormField spec exists but is not implemented.
8. Three styling layers (shadcn vars, `--tb-*`/tabler.css 2457 LOC, inline styles in 41 files) plus dead Toastify/Bootstrap CSS; dark mode correct only where tokens used; the V2 design docs describe components that do not exist, and `ui/index.js` re-exports missing modules.
9. Inconsistent overlays and a11y: 12 Radix dialogs vs 7 hand-rolled overlays, no Sheet/Accordion primitives, residual clickable divs, a11y e2e coverage on only 3 pages.
10. Routing/auth plumbing: one 330-line hand-wrapped route table, mixed `lazy` vs `lazyLoadWithRetry`, role lists in 3 places (routes, `roleConstants.js`, Sidebar), plain-text auth loading state, no per-route error boundary, tokens in localStorage; report routes not data-driven (4 SION wrappers).

## 11. Recommended target architecture

```
frontend/src/
  app/            providers (Query, Auth, Theme, Toaster), router.tsx (route objects, layout routes, errorElement)
  design-system/  ui/ (shadcn: + table, form, popover, sheet, accordion, pagination, combobox), tokens.css (single token layer)
  lib/
    api/          client.ts (typed axios + refresh), generated types, per-domain modules (licences, allotments, boe, trades, reports, planning, recon)
    query/        keys.ts (factories), hooks per domain (useLicences, useLedger...)
    calculations/ money.ts (one decimal + rounding policy), cif.ts, allocation.ts, trade.ts  (pure, unit-tested, parity-tested vs backend)
    auth/         roles.ts (single source), permissions hooks, <Can/>
  engines/
    list/         useListQuery, DataGrid, FilterBar, ActiveFilters, Pagination, ExportMenu
    form/         FormEngine, FormField, FieldArray, AsyncSelect (one), DateField, schemas
  features/       licences (Workspace + tabs), allotments, boe, trades, reconciliation, ledger, reports, planning, admin, masters
  shared/         PageHeader, StatCard, EmptyState, ErrorState, LoadingState, ConfirmDialog, DocumentViewer
```
Set `strict:true` incrementally per folder (`lib/` and `engines/` strict from day one); convert `api/axios.js` and `services/api/*.js` first.

### Core generic components to build first (in order)
1. `lib/calculations` (money + CIF/trade/allocation pure functions with parity tests) - de-risks everything else, no UI change.
2. Typed API client + query-key factories + `lib/auth/roles` single source (kill the 3 role lists).
3. `DataGrid` (headless `useListQuery` + table, sort, pagination, sticky header, empty/loading/error, optional virtualization).
4. `FilterBar` + URL-synced filter state (replaces AdvancedFilter/ItemPivotFilters/ItemReportFilters/AllotmentFilters).
5. `FormField` + one `AsyncSelect` + `FieldArray` (then `FormEngine` if the dependency is approved).
6. `AsyncState` trio: `LoadingState` / `ErrorState` / `EmptyState` wired to TanStack Query status, plus route `errorElement`.
7. `Sheet`/`Dialog`/`ConfirmDialog` on Radix only (retire hand-rolled overlays, add `Accordion`).
8. `LicenceWorkspace` shell (tabbed, URL-driven) built on 1-7.

### Migration order by risk (lowest first)
1. Housekeeping, no behaviour change: delete dead code (`ui/index.js`, DataFilter, FormField(unused), useApiCall/useModal/useToast, jest.config.js, dead `services/api/*.js`, Toastify CSS), unify `lazy` usage, collapse 4 SION wrappers and ActiveLicenses/ExpiringLicenses to config routes.
2. Types: strict per folder, convert JS core to TS, API client + keys.
3. Extract calculations to `lib/calculations` with characterization tests of current behaviour (including the rounding differences) before any consolidation; cif-balance-auditor sign-off.
4. Admin and read-only lists (UserList, ActivityLog, reconciliation tabs, reports) onto DataGrid/FilterBar.
5. Async-state components and overlay unification.
6. Licence Workspace: add tabs, redirect legacy routes, parity-test, then remove LedgerTab/BalanceTab/LicenseBalanceModal/LicenseLedgerDetail.
7. MasterList to config-driven DataGrid per entity (licences last: accordion/balance).
8. Forms: MasterForm to FormEngine; TradeForm and AllotmentAction last (highest money risk; move math server-side or to the audited module first).

Open questions / escalations: (a) adding `react-hook-form`/`zod` needs human approval; (b) any change to where CIF/trade math executes is a BUSINESS-RULE CHANGE requiring human decision; (c) confirm which of the ledger views is the canonical balance contract before the Workspace merge.
