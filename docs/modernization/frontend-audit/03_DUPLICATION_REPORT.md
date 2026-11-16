# 03 Duplication and design-consistency report (frontend audit, read-only)

Method: grep counts over `frontend/src/**/*.tsx` (tests excluded unless stated) plus `.claude/index/dependents.tsv`, 2026-11-16. Nothing changed. Visual items (dark mode, overflow, tablet layout) are inferred from code and need a running dev server to confirm. See `01_COMPONENT_INVENTORY.md` for per-component data.

Library facts (`package.json`): **no TanStack Table, no react-hook-form, no zod/yup/formik, no date-fns/dayjs, no virtualisation**. Present: TanStack Query, react-select 5, react-datepicker 8, sonner, cmdk, Radix (checkbox, dialog, dropdown, label, popover, scroll-area, select, separator, slot, switch, tabs, tooltip), framer-motion, recharts.

## 1. Tables and data grids

Totals: **79 raw `<table>` elements in 41 files** (38 files with `<thead>`), 455 `<th>`, 341 `scope="col"`, 0 `<caption>`, **0 `aria-sort`**, no `ui/table`. Two generic table components cover only 9 files. Legacy `.table` CSS class (`theme/tabler.css:658`) is used in 8 files (39 occurrences; ItemPivotReport 15, LicenseBalanceModal 10).

### 1a. Generic components
| Implementation | File | Used by | Features |
|---|---|---|---|
| `DataTable` | components/DataTable.tsx:206 (skeleton `:39`) | ReconciliationIssues:109, DuplicateBoesTab:63, MultiLinkTab:33, DuplicateDebitsTab:54, MissingInvoiceTab:68, MissingBoeTab:68, ComparisonTab:42, MasterList (import only; AccordionTable rendered) | loading skeleton, empty (`Inbox`), inline edit, boolean toggle, row actions; no sort/filter/pagination/selection/sticky; mobile CSS turns rows into cards and hides `<thead>` (`index.css:42`) |
| `AccordionTable` | components/AccordionTable.tsx:252,362 | MasterList:1232 | expandable rows, lazy nested fetch (`api` call inside), loading, empty; no sort/pagination/sticky; 570 lines with its own 60-icon lucide map |
| `DetailTable` | components/primitives/DetailTable.tsx:46 | MasterList, TradesListView, AllotmentsTable, +1 | key/value only; inline style 4 |
| `TableSkeletonLoader` | components/LoadingFallback.tsx:36 (`<table>` at 39) | **0 external uses** | duplicate of `DataTable` `TableSkeleton` (`DataTable.tsx:36`) |

### 1b. Hand-rolled `<table>` feature matrix (files with `<table`; counts are regex hits, 0 = feature absent in file)
`sort` = sort handlers/SortableHeader; `page` = pagination state; `sel` = checkbox selection; `sticky` = sticky header; `empty/load` = empty row or EmptyState / skeleton or spinner.

| File:line of `<table>` | #tbl | sort | page | sel | sticky | empty | load | x-scroll |
|---|---|---|---|---|---|---|---|---|
| components/LicenseBalanceModal.tsx:430,497,584,635,670,715,958,993 | 8 | 0 | y | y | 0 | y | y | y |
| pages/planning/LicensePlanningWorkspace.tsx:59,78,313,368,377,378 | 6 | 0 | y | y | y | y | y | y |
| pages/reports/ItemPivotReport.tsx:248,297,931,1471,1627 | 5 | 0 | 0 | y | y (30) | y | y | y; inline style **93** |
| pages/Dashboard.tsx:541,613,711,798 | 4 | 0 | 0 | 0 | y | y | y | y |
| pages/masters/tables/BalanceTab.tsx:330,353,420,457 | 4 | 0 | 0 | 0 | 0 | y | y | y |
| pages/reports/C969EntitlementTable.tsx:70,112,184 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | y |
| pages/masters/tables/LicensesTable.tsx:501,604,704 | 3 | 0 | y (12) | 0 | y | y | y | y |
| pages/masters/tables/LedgerTab.tsx:314,425,698 | 3 | 0 | 0 | 0 | y | y | y | y |
| pages/LicenseLedger.tsx:81,162,284 | 3 | 0 (server `ordering` select at `:727`) | 0 | y | y | y | y | y |
| pages/reports/SionNormReport.tsx:358,382 | 2 | 0 | 0 | 0 | y | y (13) | y | y; `[Npx]` x45 |
| pages/reports/LicensePurchaseProfitReport.tsx:384,531 | 2 | y (private `SortableHeader:116`) | 0 | 0 | y | y | y | y |
| pages/license-overview/FinancialLedgerTable.tsx:75,104 | 2 | 0 | 0 | 0 | y | y | 0 | y |
| pages/admin/UserList.tsx:174,206 | 2 | 0 | 0 | 0 | y | y | y | y |
| pages/TradeForm.tsx:1286,1483 | 2 | 0 | 0 | 0 | 0 | y | y | y; inline **22** |
| pages/Settings.tsx:142,336 | 2 | 0 | 0 | y | y | y | y | y |
| pages/LicenseLedgerDetail.tsx:557,618 | 2 | 0 | 0 | 0 | y | y | y | y |
| license-overview tabs: AllotmentsTab:126, BoesTab:160, ItemsTab:65 | 1 each | **y (shared `SortableHeader`)** | 0 | 0 | y | y/0/y | y | y |
| license-overview: CustomsLedgerTable:346, CustomsLedgerSection:32, InvoiceLedgerTab:18, FinalReconciliationSection:26, FinancialSummarySection:29 | 1 each | 0 | 0 | 1 has sel | mixed | mixed | mixed | 2 of 5 lack overflow wrapper (Final/Summary) |
| pages/AllotmentAction.tsx:1118 | 1 | 0 | y (uses `DataPagination:1501`) | y | y | y | y | y |
| pages/admin/ActivityLog.tsx:270 | 1 | 0 | 0 | 0 | 0 | y | y | y |
| pages/reports/itemReport/ItemReportTable.tsx:76 | 1 | 0 | 0 | 0 | y (12) | y | 0 | y; inline **49**, `style={{tableLayout, minWidth:'1600px'}}` `:77` |
| pages/reports/licensePurchaseProfitReport/ItemUtilizationMatrix.tsx:86 | 1 | 0 | 0 | 0 | y | y | 0 | y |
| components/{AccordionTable,DataTable,OwnershipDetailsModal:126,TransferLetterForm:329,planning/PlanningEditor:1021,LoadingFallback,primitives/DetailTable} | 1-2 | 0 | 0 | TransferLetterForm y | 0 | mixed | mixed | AccordionTable, DataTable, DetailTable have no overflow wrapper in-file |
| Minified single-line pages: pages/LicenseDownloadRequests.tsx:14 (15 lines), LicenseDownloadRequestDetail.tsx:7 (7 lines), LicenseLedgerPackageReadiness.tsx:19, planning/SplitAllocationPreview.tsx:16, settings/MdsStatusCard.tsx:157 | 1 each | 0 | 0 | 0 | 0 | partial | partial | y |

Summary: **sorting exists in 4 files and is a client-side re-implementation twice** (license-overview `SortableHeader` x3 tabs; `LicensePurchaseProfitReport.tsx:116`). Pagination is DataPagination in 3 files; LicensesTable, TradesListView, IncentiveLicensesTable, AllotmentsTable, GenericMasterCards and LicensePlanningWorkspace each carry their own `page`/`page_size` state. Sticky header is re-implemented at 20+ sites with three different recipes: `sticky top-0 z-10 bg-muted/95`, `z-[1]`/`z-20`/`z-30`, and inline `style={{position:'sticky'...}}` (`ItemPivotReport.tsx:933`, `ItemReportTable.tsx:78`). Header backgrounds differ: `bg-muted/95` (Settings:338, UserList:176,208, AllotmentAction:1119), `bg-muted/80 backdrop-blur` (LedgerTab:699, LicensesTable:605), `bg-slate-50 ... dark:bg-slate-900/50` (Dashboard:542,614,712,799; raw palette), none (LicenseLedger:82, LicenseLedgerDetail:192).

**Consolidation target:** add `ui/table` (shadcn Table, Header/Body/Row/Head/Cell with sticky + dense variants) and one `DataGrid` built on `@tanstack/react-table` is a **new dependency (needs approval)**; without it, extract `SortableHeader` + `useSortedRows` + `StickyHead` into `components/table/` and migrate in this order: license-overview tabs (already share SortableHeader), reconciliation tabs (DataTable), Dashboard, UserList/ActivityLog/Settings, then report tables. Delete `TableSkeletonLoader` duplicate. Add `aria-sort`, `<caption class="sr-only">`, and remove the mobile `thead { display: none }` rule or add labels per cell.

## 2. Filter panels

| Component | File | Used by | Notes |
|---|---|---|---|
| `AdvancedFilter` (config-driven) | components/AdvancedFilter.tsx:133,290,300 | MasterList:940 only | 303 lines; react-select + `DateRangeFilter` + `DebouncedSearchInput`; **0 aria attributes** |
| `FilterPanel/FilterGrid/FilterField` | components/filters/FilterPanel.tsx | AdvancedFilter:300, AllotmentFilters:28 | 26 lines; the only shared shell, used by 2 |
| `AllotmentFilters` | pages/AllotmentFilters.tsx:28 | AllotmentAction | native `<input>` x7, `<select>` x4, `form-label` legacy class |
| `ItemPivotFilters` | pages/reports/ItemPivotFilters.tsx (226 lines) | ItemPivotReport | react-select, `DateRangeFilter:142`, `form-label` |
| `ItemReportFilters` | pages/reports/itemReport/ItemReportFilters.tsx (378 lines) | ItemReport, PlannedReport | react-select x4, native select x4, `form-label` |
| Inline filters | LicenseLedger.tsx:727,740,780 (`DebouncedSearchInput`, `DateRangeFilter`, native `<select id=ledger-sort>`); admin/UserList.tsx:126 (`ui/select`+input); admin/ActivityLog.tsx:154,189; license-overview/BoesTab.tsx:110; LicensePurchaseProfitReport.tsx:282,287,327 (`type=date` Inputs); LicensePlanningWorkspace.tsx:294; DownloadLicense.tsx; SionNormReport.tsx | | each re-implements search + clear + state |
| `ActiveFilters` (chips) | components/ActiveFilters.tsx | **13 pages** (LicenseLedger:1061, AllotmentAction:1817, UserList:352, ActivityLog:455, MasterList:1717, ItemPivotReport:1943, ItemReport:477, PlannedReport:372, SionNormReport:435, DownloadLicense:318, LicensePurchaseProfitReport:691, LicensePlanningWorkspace:463, LicenseExportPanel:150) | the only filter piece with broad adoption |
| `DateRangeFilter` | components/DateRangeFilter.tsx | AdvancedFilter, AllotmentFilters, LicenseLedger:780, ActivityLog:189, ItemPivotFilters:142, ItemReportFilters | native date inputs |
| `DataFilter` | components/DataFilter.tsx | **0** | dead |

Persistence: `utils/filterPersistence.js` plus per-page `useSmoothListFilters`/URL handling differ by page (not itemised).
**Target:** one `FilterBar` (extend `filters/FilterPanel.tsx`) with field components (`SearchField`, `SelectField`, `AsyncSelectField`, `DateRangeField`) and mandatory `ActiveFilters`; migrate AllotmentFilters, ItemPivotFilters, ItemReportFilters first (same markup with `form-label`), retire `DataFilter`.

## 3. Pagination
- `DataPagination` (components/DataPagination.tsx, 126 lines): 3 consumers, AllotmentAction:1501, MasterList:1573, ItemReport:294. Fixed page sizes `[10,25,50,100,200]`.
- No pagination UI in the other 11 files holding `page`/`page_size` state: LicensesTable, IncentiveLicensesTable, AllotmentsTable, GenericMasterCards, TradesListView, LicensePlanningWorkspace, LicenseBalanceModal, AllotmentFormModal, AsyncSelectField, DebouncedAsyncSelect, SionAsyncItemSelect (several are fetch-size params, not UI).
- Variance: server-driven `has_next/has_previous` (MasterList) vs derived (`currentPage > 1`, AllotmentAction:1506) vs hook `pagination.isFirstPage` (ItemReport:299).
**Target:** keep `DataPagination`, move to `ui/pagination` styling, adopt in the list tables of masters.

## 4. Forms
- Libraries: **none** (no react-hook-form/zod/formik/yup). All 9 `<form>` files use hand-rolled `useState` per field: ChangePasswordForm, AllotmentFormModal (unused), TaskDrawer, Settings, Login, TradeForm, PasswordReset, UserForm, MasterForm.
- Error state: `fieldErrors` `useState` in 5 files (AllotmentFormModal:30, TradeForm:48, UserForm:49, MasterForm:115, plus planning `formErrors` `LicensePlanningWorkspace.tsx:118`, with `ruleFormValidation.ts`).
- Helpers: `utils/formErrors.js` (used by FormField [dead], AllotmentFormModal [dead], UserForm), `utils/formValidation.js` (TradeForm, `useMasterFormSubmit`), `utils/errorUtils.js` (14 files, mostly report/reconciliation fetch errors). `FORM_ERROR_HANDLING.md` still documents Bootstrap `is-invalid` (5 `is-invalid` occurrences remain).
- Display: `aria-invalid` 25 uses in 8 files; `aria-describedby` 8; `role="alert"` 24; the shared `FormField.tsx` (22 aria hits, the only wrapper) has **0 importers**.
- Control mix: `<Input>` 54 vs raw `<input>` 95; `<Label>` 48 vs raw `<label>` 115 (33 `form-label`); `ui/Select` 20 vs native `<select>` 32 (TradeForm 22 raw inputs, AllotmentFormModal 8, AllotmentFilters 7); `ui/Textarea` 3 vs raw `<textarea>` 8.
**Target:** adopt `FormField` (label + control + error + `aria-describedby`) on top of `ui/label`/`ui/input`; schema validation would need zod (new dependency, needs approval). Without it, standardise on `formErrors.js` extraction and a shared `useFieldErrors` hook; migrate UserForm, Login, PasswordReset, ChangePasswordForm first (small), then TradeForm/MasterForm (1,644/1,137 lines, high `any`).

## 5. Modals, dialogs, confirm
- Radix `ui/dialog`: 11 files (LicenseBalanceModal, AllotmentFormModal, OwnershipDetailsModal, TransferLetterModal, LicensePlanningPanel, Settings, LedgerUpload, LinkRecordModal, UserList, CustomsLedgerTable, ItemPivotReport).
- Hand-rolled modal/drawer markup: `ConfirmDialog.tsx:124` (portal + own focus trap), `masters/BoeMergeModal.tsx:19-20`, `masters/LinkTradeModal.tsx:19-22`, `TaskDrawer.tsx:409`, `CommandPalette.tsx:99`, `TopNav.tsx:336`.
- Confirm: `ConfirmDialog` direct (Settings:19, AllotmentAction:18, LicensePlanningWorkspace:11, ExpressionTreeEditor:4), via `useConfirmDialog` (MasterList:30, ReconciliationPanel:14), and **still `window.confirm`** at TaskDrawer:365, PlanningEditor:849, TradeForm:63, AllotmentsTable:78.
- Prop convention is Bootstrap-era `show`/`onHide` (LicenseBalanceModal:123, AllotmentFormModal:11, TransferLetterModal) wrapped around Radix `open`/`onOpenChange`.
**Target:** rebuild `ConfirmDialog` on `ui/alert-dialog`-style Radix (`ui/dialog`), keep `useConfirmDialog` API, convert BoeMergeModal/LinkTradeModal, replace the 4 `window.confirm` calls.

## 6. Async selects and selects
- 19 files use react-select (`Select`, `Async`, `Creatable`, `AsyncCreatable`) in about 30 instances; `classNamePrefix="react-select"` 11, `styles={}` 19; `App.css:123-126` forces colours with `!important`.
- Wrappers: `AsyncSelectField` (7 importers: HybridSelect, LicenseLedger, InlineNormEditor, NestedFieldArray, ItemPivotFilters, LicensePurchaseProfitReport, ItemReportFilters), `DebouncedAsyncSelect` (2: AdvancedFilter, item-async-select [dead]), `HybridSelect` (6), `item-async-select.tsx` (0), `pages/planning/SionAsyncItemSelect.tsx` (own debounce `useDebouncedValue`), plus direct `AsyncSelect` in AllotmentFormModal, LicenseBalanceModal, TransferLetterForm, LedgerTab.
- Debounce implemented 3 ways: `hooks/useDebounce` (AsyncSelectField, DebouncedAsyncSelect), local `useDebouncedValue` (SionAsyncItemSelect:~20), `DebouncedSearchInput` timer.
**Target:** one `AsyncSelect` wrapper (merge AsyncSelectField + DebouncedAsyncSelect, keep recents/FK cache) with a token-driven `classNames` object replacing `styles={}` and `App.css !important`; long-term a Radix Popover+cmdk combobox (both already installed).

## 7. Stat cards
| Implementation | File | Uses |
|---|---|---|
| `StatCard` (TONE map, TW+tok 13) | components/StatCard.tsx:84 | 36 uses in 6 files: Dashboard:458-495, ReconciliationIssues:151-157, ReconciliationPanel:143-149, LicenseLedgerDetail:134-158, LicenseMetricsGrid, LicensePurchaseProfitReport:447-493 |
| `StatCard` (second, same name) | pages/license-overview/StatCard.tsx:90 | LicenseMetricsGrid:28-72 (raw palette **35**, `dark:` 7) |
| `SummaryCard` | pages/license-overview/SummaryCard.tsx:26 | CustomsLedgerTable:328-330 |
| `SummaryCard` (local, same name) | components/planning/PlanningEditor.tsx:305 | 14 uses (`:444-993`) |
| `SummaryMetric` (local) | pages/masters/tables/LedgerTab.tsx:188 | 14 uses |
| `Stat` (local) | primitives/EntityCard.tsx:132 | EntityCard |
| `LedgerSummaryCards` (local) | pages/LicenseLedgerDetail.tsx:110 | 4 cards |
**Target:** one `StatCard` (`components/StatCard.tsx`) with `tone`, `size`, `helper`, `onClick`; fold the two `SummaryCard`s, `SummaryMetric`, `Stat`.

## 8. Badges and status pills
- `ui/badge` has 7 variants; 58 `<Badge>` uses in 26 files (secondary 7, destructive 5, success 4, default 3, warning 2, outline 1, info 1 with explicit variant).
- Parallel implementations: `ConditionBadge.tsx` (hex fallback, `text-[0.6rem]`), `OverUtilisedBadge.tsx` (on Badge, fine), `PlanningEditor.tsx:291 StatusBadge`, `ItemPivotReport.tsx:181 PurchaseStatusBadge` (inline styles, palette from `theme/tokens.js`), `Settings.tsx:114 RoleBadge`, `Dashboard.tsx:171 getExpiryBadgeVariant`, `settings/MdsStatusCard.tsx:47 healthBadge`, `masters/TradeMetaBadges.tsx:11`, `EntityCard.tsx:70 HeaderChip`, `LicensesTable.tsx:224 deriveStatus`.
- Tone maps defined 7 times: `theme/tokens.js` (`TONE_MAP`), `ErrorScreen.tsx:21`, `StatCard.tsx:7`, `AlertCard.tsx:19`, `Settings.tsx:63`, `LicenseLedger.tsx:374`, `EntityCard.tsx:68`. Only `ConditionBadge`, `EntityCard`, `ItemPivotReport` import `theme/tokens`.
- Font sizes in badges: `text-[9px]` (LicenseLedger:835), `text-[0.6rem]`, `text-xs`.
**Target:** one `StatusBadge` (ui/badge + `tone`) fed by `TONE_MAP`; make `ui/badge` variants the only definition and map domain statuses to it.

## 9. Page headers
- `PageHeader` (components/PageHeader.tsx): 22 files / 25 call sites (e.g. Dashboard:318, Settings:293, MasterList:833, LicenseLedger:573, SionNormReport:278,291,305). Title `text-2xl sm:text-[1.625rem] lg:text-3xl`, padding `px-5 py-4 sm:px-6 sm:py-5`, card with `shadow-sm`, legacy `app-page-header` underline accent.
- Pages that hand-roll an `<h1>` instead: TradeForm:845 (`text-base font-bold`), UserForm:157 (`text-xl font-semibold`), LicensePlanningWorkspace:270 (`text-lg font-semibold`), LicensePurchaseProfitReport:260 (unstyled `<h1>`), Login:146 (`text-[1.5rem]`), PasswordReset:49 (`text-xl`), AllotmentAction:839 (h1 used for an error message), plus ErrorScreen:60 (`text-2xl`).
- Result: h1 sizes in use: 3xl, 1.625rem, 2xl, 1.5rem, xl, lg, base, none. App bar height: TopNav 56px (`tabler.css:1101`).
**Target:** `PageHeader` with `size="compact"|"default"` and a `form` variant; migrate the 4 route pages above.

## 10. Empty, loading, error states
- Empty: `EmptyState` has 9 uses in 6 files (AllotmentAction, Dashboard, LicenseLedger, Settings, UserList, ActivityLog). 33 files carry ad-hoc "No ... found" literals (39 occurrences), plus `LicensesTable.tsx:893 EmptyTabState`, `DataTable` `Inbox` block, table `colSpan` rows.
- Loading: `Skeleton` 62 uses in 12 files; spinners `Loader2` 62 / `animate-spin` 89 in 57 files; literal "Loading..." text in 37 places; two page loaders (`LoadingFallback.PageLoader`, per-page `role="status"` blocks at BOETransferLetter:44, TradeTransferLetter:44); `TableSkeletonLoader`, `FormSkeletonLoader`, `InlineLoader` (LoadingFallback.tsx:36,68,87) have 0 external users.
- Error: `ErrorScreen` (4 route error pages); two error boundaries (`ErrorBoundary` used in `App.tsx:19`; `GlobalErrorBoundary` unused); 29 files with inline "Failed to load" markup; `ui/alert` used by 7 files only (all in master/license-overview), 24 hand-written `role="alert"` blocks elsewhere.
**Target:** `EmptyState` + `InlineError` (ui/alert + retry) + `LoadingState` (skeleton or spinner by prop); remove `GlobalErrorBoundary`.

## 11. Toasts
Single system: **sonner** (59 files, 338 calls: error 196, success 103, warning 13, info 11, loading 1), `<Toaster duration={3500}>` once (`App.tsx:18`). Residue: `hooks/useToast.js` wrapper (barrel-only), duration set once so no per-call variance. No consolidation needed beyond deleting the hook; consider a `notify.apiError(e)` helper (196 error toasts re-derive messages).

## 12. Date pickers
- `react-datepicker`: TradeForm:1102, MasterForm:541, NestedFieldArray:352 (CSS imported 3x, overrides `App.css:98`).
- Native `type="date"`: DateRangeFilter:97,103, AllotmentFormModal:465, TaskDrawer:521,713, LicensePurchaseProfitReport:282,287.
- No date library; formatting by `utils/dateFormatter.js` (22 importers) while 54 `toLocaleString/toLocaleDateString` calls remain inline.
**Target:** one `DateField` (native input styled by `ui/input` for filters; react-datepicker only where a typed/calendar UX is required), single formatter module.

## 13. Design inconsistencies (quantified)

**Typography.** `text-xs` 781, `text-sm` 519, `text-base` 32, `text-lg` 10, `text-xl` 8, `text-2xl` 13, `text-3xl` 1, and **192 arbitrary `text-[Npx|rem]` in 30 distinct sizes** (top: `[11px]` 24, `[10px]` 24, `[13px]` 20, `[10.5px]` 20, `[12.5px]` 16, `[9.5px]` 13, `[9px]` 10, `[13.5px]` 10). Sub-12px text is common (sizes 9-11.5px), an AA readability risk. Arbitrary `px/rem` values of any property: 448 total; top files SionNormReport 45, LicenseBalanceModal 28, AllotmentAction 22, BalanceTab 18.

**Spacing.** `gap-2` 350, `gap-1` 265, `gap-3` 98, `gap-4` 48; `p-3` 102, `p-2` 91, `p-4` 44, `p-6` 20, `p-5` 12. CardContent padding mix: `p-0` 25, `p-3` 11, `pt-5` 10, `px-4` 7, `pt-4` 6, `py-5` 4. CardHeader `py-3` 16 vs `px-4` 6 vs `px-3` 4.

**Radii.** `rounded-md` 223, `rounded-lg` 165, bare `rounded` 109, `rounded-full` 101, `rounded-xl` 89, `rounded-sm` 11, `rounded-2xl` 5, `rounded-[..]` 4. Primitives themselves disagree: Button `rounded-lg`, Input `rounded-lg`, Badge `rounded-md`, Card `rounded-xl`, PageHeader `rounded-lg`. Shadows: `shadow-sm` 81, `shadow-md` 11, `shadow-lg` 4.

**Buttons.** `<Button>` 202 uses vs **199 raw `<button>` in 55 files** (TradeForm 22, AllotmentAction 16, TopNav 10, LicensesTable 9, TaskDrawer 9). Variants used: outline 111, ghost 21, secondary 18, destructive 17, default 6; `size="sm"` 87, lg 2, icon 4. Height overrides via className: `h-8` 3, `h-7` 2. Button base uses `border-2` for outline while Input/Card use 1px borders. `variant="muted|success|primary|danger|warning|info"` strings seen in the grep belong to `SummaryCard/SummaryMetric` props, not Button (Button defines only default/destructive/outline/secondary/accent/ghost/link). **Button colours are raw palette** (`button.tsx:11-22`): the one most-used primitive (55 importers) will not follow `--tb-*` or dark mode. Needs visual diff.

**Icon sizes (lucide).** `size-4` 436, `size-3.5` 196, `size-3` 50, `size-8` 30, `size-5` 27, `size-6` 16, legacy `h-4 w-4` 3, `h-3.5 w-3.5` 2. Three bi-to-lucide maps plus `Icon.tsx` shim.

**Header heights.** TopNav 56px (`tabler.css:1101`, mobile also 56px at `:2365`); `app-page-header` 4 padding recipes; Input `h-10` vs filter inputs `h-8` x2; Button default `h-10` vs `sm` `h-9`; table header recipes 5 (see 1b). Several pages put `sticky top-0` toolbars (LicensePlanningWorkspace:267 `z-30`, ItemPivotReport:293 `z-30`, :672 `z-10`, MasterForm:711 `z-20`) with no shared offset for the 56px TopNav (z-index 10/20/30/1051/1060/9999 all literal).

**Hex vs tokens.** `.ts/.tsx/.js`: 85 hex occurrences in 10 files. Outside `theme/tokens.js` (23, intended): ItemPivotReport.tsx 9 (`:400` `#f8fafc/#e2e8f0` written to DOM via `cell.style.backgroundColor`; others are `var(--tb-x, #fallback)`), TransferLetterForm.tsx 7 (`:198-203` pastel chips), NormCardGrid.tsx 4, `utils/roleConstants.ts` 3, `utils/pdfPreview.js` 3, NestedFieldArray 2, ConditionBadge 2, SionAsyncItemSelect 1, BoeMergeModal 1, Sidebar 1. CSS: `theme/tabler.css` 111 hex (153 `--tb-*` definitions, 748 `var(--tb-` uses), `App.css` 5, `index.css` 8, `tailwind.css` 7.
**Raw Tailwind palette** (non-token colours): 516 uses in 44 files, 37 files without any `dark:`. Top: Dashboard 49 (has 49 `dark:` pairs, the only file doing it properly), LedgerTab 47, license-overview/StatCard 35, LicensesTable 16, LicenseBalanceModal 11, BoeMergeModal 10, ItemPivotReport 9, ParsingStatusDisplay 8, BalanceTab 7, BoesTab 7, Login 7, LicenseLedger 7, `ui/button` 7, PlanningEditor 7. Neutral raw (`bg/text/border-white|black|gray|slate|zinc|neutral`) 198 uses, Dashboard 18, LicenseLedger 4, button 3. Dark mode: `dark:` total 97 in 10 files.

**Inline styles.** 281 `style={` (262 `style={{`). Top: ItemPivotReport 93, ItemReportTable 49, TradeForm 22, SionNormReport 10, Sidebar 9 (dead), NormCardGrid 7, MasterForm 7, LicenseBalanceModal 7, EntityCard 6, TopNav 5, TaskDrawer 5, DetailTable 4, TransferLetterForm 4. Of 45 files with inline style, the 3 top account for 164 (58%).

**Legacy CSS still in TSX.** `form-label` 33 (3 files), `className="table` 39, `tb-*` 253, `app-*` 10. 4 CSS files besides tokens: `App.css` 299 lines, `index.css` 128, `styles/tailwind.css` 449, `theme/tabler.css` 2457, plus `TradesListView.css` (18 lines).

## 14. Responsive behaviour
- Breakpoint prefixes in use: `sm:` 273, `lg:` 91, `md:` 31, `xl:` 22, `2xl:` 3, `max-*:` 0. **Tablet (`md`, 768-1023px) is under-served**: `md:` is 8x less used than `sm:`; the layout jumps from `sm` (640) to `lg` (1024). `tabler.css` handles mobile via `@media (max-width: 720px)` (`:1874`) and a `768px` rule in `index.css:40`, which do not match Tailwind breakpoints.
- Fixed widths: `min-w-[Npx]` 120 (top: SionNormReport 44, AllotmentAction 14, LicenseBalanceModal 14, BalanceTab 10), `w-[Npx]` 161 (SionNormReport 44, LicenseBalanceModal 15, AllotmentAction 14, BalanceTab 11, ActivityLog 8), inline `width/minWidth/height` px 108, `max-h-[px|vh]` 22, `vh/h-screen/min-h-screen` 50. Hard minimums: `ItemReportTable.tsx:77` `minWidth:1600px`, ItemPivotReport table `min-w-[1000px]` (`:248`), LicensePlanningWorkspace:313 `min-w-[640px]` + `max-h-[560px]`, TransferLetterModal `h-[95vh] w-[95vw]`.
- Overflow: `overflow-x-auto` 42 uses in 25 files, `overflow-auto` 19. Tables without any overflow wrapper in file: AccordionTable, DataTable (relies on `.table-responsive-mobile`), DetailTable, FinalReconciliationSection, FinancialSummarySection (and LoadingFallback skeleton).
- Mobile table mode: `.table-responsive-mobile` (`index.css:39-52`) converts rows to blocks and **hides `<thead>`**, so DataTable cells lose column labels on phones (a11y + usability).
- Tests: `tests/responsive.test.ts` defines 5 viewports (390, 768, 1024, 1366, 1440) but is a static spec, not a layout check; Playwright `e2e/` was not run in this audit.

## 15. Top offenders (composite)
1. `pages/reports/ItemPivotReport.tsx` (1951 lines): 93 inline styles, 9 hex, 9 raw palette, 5 tables, 3 sticky recipes, own badge, own header toolbar.
2. `pages/reports/itemReport/ItemReportTable.tsx`: 49 inline styles, minWidth 1600px, react-select inside table.
3. `components/LicenseBalanceModal.tsx` (1062): 8 tables, 17 raw palette, 28 arbitrary px, 7 inline, no `dark:`, 1 aria hit.
4. `pages/TradeForm.tsx` (1644): 22 inline styles, 22 raw inputs, 22 raw buttons, `window.confirm`, hand-rolled `<h1>`.
5. `pages/masters/tables/LedgerTab.tsx` (1162): 47 raw palette, 3 tables, local `SummaryMetric`, no `dark:`.
6. `pages/reports/SionNormReport.tsx`: 45 arbitrary px values, 44 `min-w`, 44 `w-[px]`, 10 inline.
7. `pages/Dashboard.tsx`: 4 tables with the slate/`dark:` pattern, 49 raw palette, 18 neutral raw.
8. `components/ui/button.tsx`: raw palette in the most-imported primitive (55).
9. `components/TransferLetterForm.tsx`: 12 hex, 7 raw palette, inline 4.
10. `pages/license-overview/StatCard.tsx`: 35 raw palette, duplicate of shared `StatCard`.

## 16. Suggested consolidation order (behaviour-preserving, each shippable)
1. Delete dead files (about 1,070 lines, 0 importers): AllotmentFormModal, FormField (or adopt it), DataFilter, Timeline, GlobalErrorBoundary, item-async-select, PageTransition (or adopt), layout/Sidebar, ui/index.js, hooks/useToast/useModal.
2. Tokenise `ui/button.tsx` and `ui/switch.tsx` thumb (visual diff in light and dark required).
3. Add `ui/table` and `SortableHeader` shared; migrate license-overview tabs, reconciliation tabs, Dashboard.
4. Merge StatCards; unify badges on `TONE_MAP`.
5. ConfirmDialog and the two hand-rolled modals onto Radix; remove 4 `window.confirm`.
6. Merge async selects, replace react-select `styles={}` with one token-driven theme.
7. Filter bar + pagination adoption in masters list tables.
8. Replace inline-style tables (ItemPivotReport, ItemReportTable) with classes; add `md:` tablet layouts.
Libraries that would help (TanStack Table, react-hook-form, zod) are **not installed and need explicit approval** (CLAUDE.md section 5).
