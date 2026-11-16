# 01 Component inventory (frontend audit, read-only)

Scope: `frontend/src/components/**`, `components/ui/**`, `layout/**`, shared hooks that render UI, and page-local components reused by 2+ pages. Static analysis only (grep + `.claude/index/dependents.tsv`, 2026-11-16). Nothing under `frontend/` was changed. Dark mode and a11y findings are from code reading and **need a visual diff / axe run on a running server**.

Legend
- **Fan-in** = distinct non-test importers from `dependents.tsv` (index counts can differ by 1 from earlier docs, e.g. `button` 55 vs 56). Entries marked `0*` were also confirmed by `grep` for the symbol name: no importer anywhere in `src/`.
- **Styling**: `TW+tok` = Tailwind using semantic tokens (`bg-card`, `text-muted-foreground`, ... aliased to `--tb-*` in `styles/tailwind.css`); `raw-pal` = raw Tailwind palette (`bg-white`, `slate-*`, `blue-600`); `hex` = literal hex; `inline` = `style={{}}`; `legacy-css` = classes from `theme/tabler.css`/`index.css` (`table`, `form-label`, `tb-nav`, `app-*`). Numbers are occurrences in that file.
- **Dark**: `Y` = tokens only, flips via `[data-theme="dark"]` (`styles/tailwind.css:28`). `N` = raw palette without `dark:` variants, will not flip (Tailwind default palette is not remapped; no `--color-white/slate` overrides in `tailwind.css`). `P` = partial.
- **Tests**: only 6 component test files exist (`CommandPalette`, `LicenseBalanceModal`, `OverUtilisedBadge`, `TopNav`, `planning/PlanningEditor.reconciliation`, `reports/LicenseExportPanel`). "-" = no colocated test (some are exercised indirectly by page smoke tests, e.g. `MasterList.smoke`, `ReconciliationPanel.smoke`).

## 1. shadcn primitives (`components/ui/`, new-york, 18 files)

| Path | Purpose | Props surface | Fan-in | Styling | a11y | Dark | Tests |
|---|---|---|---|---|---|---|---|
| ui/button.tsx | Button (cva, `asChild`) | `variant` default/destructive/outline/secondary/accent/ghost/link; `size` default(h-10)/sm(h-9)/lg/icon | 55 | **raw-pal 7 lines** (`bg-blue-600`, `bg-white`, `border-slate-300`, `bg-slate-100`; `button.tsx:11-22`), not tokens; `focus-visible:ring-[3px]` | focus ring OK; `active:scale-95` ignores reduced motion | **N** (outline renders white, secondary/ghost slate-100 in dark) | - |
| ui/card.tsx | Card, CardHeader/Title/Description/Action/Content/Footer | div props | 32 | TW+tok, `rounded-xl shadow-sm` | n/a (div) | Y | - |
| ui/badge.tsx | Badge (cva) | `variant` default/secondary/destructive/success/warning/info/outline, `asChild` | 27 | TW+tok (`bg-success/10`) | no color-only guard | Y | - |
| ui/input.tsx | Input | input props | 19 | TW+tok, `h-10 rounded-lg` | `aria-invalid` styling hook | Y | - |
| ui/label.tsx | Label (Radix) | label props | 15 | TW+tok | correct `htmlFor` primitive | Y | - |
| ui/dialog.tsx | Dialog (Radix) + Header/Footer/Title/Description | `showCloseButton` | 11 | TW+tok, 1 raw-pal | Radix focus trap/ESC; close button labelled | Y | - |
| ui/skeleton.tsx | Skeleton | div props | 12 | TW+tok | no `aria-busy` (callers add) | Y | - |
| ui/alert.tsx | Alert | `variant` | 7 | TW+tok, `dark:` x4 | `role="alert"` | Y | - |
| ui/switch.tsx | Switch (Radix) | switch props | 8 | TW+tok, thumb `bg-white` | Radix | Y | - |
| ui/tabs.tsx | Tabs (Radix) | - | 5 | TW+tok | Radix | Y | - |
| ui/select.tsx | Select (Radix) | - | 3 (LicenseLedger, ActivityLog, UserList) | TW+tok | Radix | Y | - |
| ui/textarea.tsx | Textarea | - | 3 | TW+tok | - | Y | - |
| ui/checkbox.tsx | Checkbox (Radix) | - | 2 | TW+tok | Radix | Y | - |
| ui/dropdown-menu.tsx | DropdownMenu (Radix) | - | 1 | TW+tok | Radix | Y | - |
| ui/separator.tsx | Separator | - | 1 | TW+tok | decorative | Y | - |
| ui/sonner.tsx | `<Toaster>` wrapper | sonner props | 1 (`App.tsx:18`, `duration={3500}`) | TW+tok | sonner live region | Y | - |
| ui/tooltip.tsx | Tooltip (Radix) | - | 1 | TW+tok | Radix | Y | - |
| ui/index.js | **Dead legacy barrel**: re-exports `../primitives/{Surface,EmptyState,Skeleton,IconChip,StatusBadge,SectionHeader,PageHeader,Button,Toolbar,FilterBar,StatCard,Card}` which **do not exist** (only `primitives/DetailTable.tsx` and `EntityCard.tsx` exist) | - | 0* | - | - | - | - |

Gaps: no `ui/table`, `ui/popover`, `ui/scroll-area`, `ui/form`, `ui/pagination`, `ui/calendar` even though `@radix-ui/react-popover` and `react-scroll-area` are installed (`package.json:23`, `:22`). `cmdk` is used directly in `CommandPalette`.

## 2. Shared components (`components/`, flat)

| Path | Purpose | Props surface | Fan-in | Styling | a11y | Dark | Tests |
|---|---|---|---|---|---|---|---|
| PageHeader.tsx | Page title card (h1 + pretitle/description/actions) | `pretitle,title,description,actions,children,className` | 22 | TW+tok 5; legacy `app-page-header` (accent underline in `tabler.css:2004`) | renders the only shared `<h1>`; no landmark/breadcrumb nav | Y | - |
| StatCard.tsx | KPI tile | `icon,title,value,tone,...` (TONE map: primary/success/...) | 5 | TW+tok 13 | no semantic grouping; value not announced as label+value pair | Y | - |
| AlertCard.tsx | Toned alert tile (Dashboard) | tone, title, body | 1 | TW+tok 8 | none (`role` absent) | Y | - |
| EmptyState.tsx | Empty state | `icon,title,description,action,className,size(default/page)` | 6 (9 uses) | TW+tok 5 | none (no `role=status`) | Y | - |
| ErrorScreen.tsx | Full-page error (401/403/404/500) | `code,icon,tone,...` | 4 | TW+tok 13 | h1; OK | Y | - |
| ErrorBoundary.tsx | Root boundary (`App.tsx:19`) | children | 1 | no styling classes (class component) | - | - | - |
| GlobalErrorBoundary.tsx | Second boundary, renders bare `<h1>` | children | **0*** | unstyled | - | - | - |
| LoadingFallback.tsx | `PageLoader`, `FullPageLoader`, `TableSkeletonLoader`, `FormSkeletonLoader`, `InlineLoader` | `text,rows,columns,fields` | 1 (`AppRoutes.tsx:6`) | TW+tok 7, raw-pal 1, inline 2; contains `<table>` | `role="status"` + `aria-label` | P | - |
| ConfirmDialog.tsx | Hand-rolled modal (portal, own focus trap, ESC/Enter) | severity danger/warning/..., `onConfirm/onCancel` | 5 (+`useConfirmDialog`) | TW+tok 17; `text-white` 4; inline 2; `fixed inset-0 z-[1060]` | focus trap + restore, `aria-modal`; separate from Radix dialog (two modal systems) | P | - |
| DataTable.tsx | Generic record table | `data,columns,onEdit,onDelete,customActions,loading,inlineEditable,onInlineUpdate,customCellRender,getRowStyle` | 8 | TW+tok 32, legacy `table`/`app-data-table`/`table-responsive-mobile`; numeric-column detection by name regex | `scope=col`, `aria-busy` skeleton, labelled actions; **mobile CSS hides `<thead>` (`index.css:42`)**, no `aria-sort` | Y | - |
| AccordionTable.tsx | Expandable-row master table (nested arrays, lazy nested fetch) | `data,columns,loading,onDelete,basePath,nestedFieldDefs,nestedListDisplay,customActions,...` | 1 (MasterList) | TW+tok 20; 570 lines, own icon map (60+ lucide imports + `LUCIDE_MAP`) | chevron toggles; `api` calls inside a view component | Y | - |
| DataPagination.tsx | Page nav + page-size select | `currentPage,totalPages,pageSize,hasNext,hasPrevious,onPageChange,onPageSizeChange,totalItems,showPageSize` | 3 | TW+tok 21 | `aria-label` prev/next | Y | - |
| ActiveFilters.tsx | Removable filter chips | `filters,onRemove,onClearAll,showCount,compact` | 13 | TW+tok 12, raw-pal 8, `dark:` 4 | buttons labelled | P | - |
| AdvancedFilter.tsx | Config-driven filter panel for masters (react-select + date range + debounced search) | `filterConfig,searchFields,onFilterChange,initialFilters,defaultFilters,resetToDefaults,isUpdating` | 1 (MasterList) | TW+tok 23 | **0 aria attrs** in 303 lines | Y | - |
| filters/FilterPanel.tsx | `FilterPanel`, `FilterGrid`, `FilterField` layout shell | `children,activeCount,isUpdating,onClear` | 2 (AdvancedFilter, AllotmentFilters) | TW+tok 6 | 3 aria hits | Y | - |
| DataFilter.tsx | Legacy simple filter | - | **0*** | no tokens | - | - | - |
| DateRangeFilter.tsx | From/to native `type=date` + presets | `label,icon,hint,fromValue,toValue,onFromChange,onToChange,presets,onClear,fromId,toId` | 6 | TW+tok | labelled inputs (ids) | Y | - |
| DebouncedSearchInput.tsx | Debounced text input | `value,onChange,delay=500,placeholder,className,style,showPendingIndicator` | 3 | TW+tok 6, inline 2 (`style` prop) | no label prop / `aria-label` | Y | - |
| AsyncSelectField.tsx | react-select Async for FK fields, recents in localStorage, FK detail cache | fieldMeta-driven | 7 | TW+tok 4, inline 1 | relies on react-select ARIA | P (styles prop + `App.css` `!important` overrides) | - |
| DebouncedAsyncSelect.tsx | react-select Async, debounced | `loadOptions` style props | 2 | inline 1 | as above | P | - |
| HybridSelect.tsx | Static or async select switch | `fieldMeta,value,onChange,isMulti,staticOptions,...` | 6 | TW+tok 1 | as above | P | - |
| item-async-select.tsx | `ItemNameAsyncSelect` thin wrapper | `value,onChange,disabled,placeholder` | **0*** | - | - | - | - |
| FormField.tsx | Labelled field with field-error display (uses `utils/formErrors`) | `label,name,type,fieldErrors,required,id` | **0*** | TW+tok 8 | 22 aria hits (best-practice impl, unused) | Y | - |
| ChangePasswordForm.tsx | Profile password form | - | 1 | TW+tok 12 | 7 aria hits | Y | - |
| Icon.tsx | Bootstrap-name to lucide shim (`BI_TO_LUCIDE`) | `name,className` | 7 | none | decorative | Y | - |
| ConditionBadge.tsx | Licence-condition chip | `type,size` | 8 | **hex 2 fallback** (`#E5E7EB/#374151`), inline 1, `text-[0.6rem]`, palette from `theme/tokens.js` | no text alt | P | - |
| OverUtilisedBadge.tsx | "Over-utilised" badge (business flag, uses `ui/badge`) | `balance,isOverUtilised,className` | 5 | TW+tok | `aria-label` | Y | yes |
| IndividualItemCifSwitch.tsx | CIF override switch (writes via react-query) | `licenseId,override,canWrite` | 2 | TW+tok 1 | 2 aria hits | Y | - |
| PermissionGate.tsx | Role gate | `role,anyRole,fallback` | 1 | - | - | - | - |
| LicenseBalanceModal.tsx | 1062-line balance modal (8 `<table>`, AsyncSelect/Select) | `show,onHide,licenseId,...` | 2 | TW+tok 97, **raw-pal 17, inline 7, `[Npx]` 28**, no `dark:` | Radix Dialog; 1 aria hit in 1062 lines | **N** | yes |
| AllotmentFormModal.tsx | Allotment create/edit modal | `show,onHide,...` | **0*** | TW+tok 63, raw-pal 5 | 12 aria hits | P | - |
| OwnershipDetailsModal.tsx | Ownership dialog | - | 1 | TW+tok 22, inline 2 | 0 aria | P | - |
| TransferLetterModal.tsx / TransferLetterForm.tsx | Transfer-letter dialog + form | `show,onHide,type,entityId` | 2 / 3 | Modal: inline gradient header, `text-white`; Form: **hex 12** (`TransferLetterForm.tsx:198-203` pastel chips), inline 4, raw-pal 7 | 1 aria hit | **N** | - |
| TaskDrawer.tsx / TaskFAB.tsx | Global task drawer + floating button | `show,onClose` / `bottomOffset` | 1 / 1 | TW+tok 80, raw-pal 3, inline 5 / inline 3; hand-rolled `role=dialog` (no focus trap seen), `window.confirm` at `:365` | `aria-label="Tasks"` | P | - |
| TopNav.tsx | Top navigation, command-palette trigger | - | 1 | legacy `tb-nav top-nav--premium` + TW 4, inline 5; height 56px (`tabler.css:1101`; mobile rule at `:2365` also 56px, 48px override `:1888` inside the max-width 720px block) | 47 aria hits, `aria-label="Main navigation"` | Y | yes |
| CommandPalette.tsx | cmdk palette (hand-rolled `role=dialog`) | - | 1 | TW+tok 1 | 5 aria hits | Y | yes |
| ParsingStatusDisplay.tsx | Parse progress strip (AdminLayout) | context-driven | 1 | **raw-pal 9**, inline 1 | 1 aria hit, no `role=status` | **N** | - |
| Timeline.tsx | Timeline list | `items,emptyMessage` | **0*** | TW+tok 7 | `<ol>` | Y | - |
| AuthedImage.tsx | Blob image via axios | `path,alt,style,className` | 1 | inline 2 | alt prop | - | - |
| fkDetailCache.js | Module-level FK cache | - | 2 | - | - | - | - |
| motion/PageTransition.tsx | framer-motion wrapper | - | **0*** | - | respects `useReducedMotion` | - | - |
| primitives/DetailTable.tsx | Key/value table | - | 4 | TW+tok 3, **inline 4** | `<table>` w/o `<caption>`/`<th scope>` | Y | - |
| primitives/EntityCard.tsx | Master record card, tone chips from `theme/tokens.js` | - | 4 | TW+tok 4, **inline 6**, `bi-*` icon map `:39` | 1 aria hit | Y | - |
| planning/PlanningEditor.tsx | 1268-line planning editor (domain) | - | 4 | TW+tok 112, raw-pal 13; local `StatusBadge:291`, `SummaryCard:305` | 18 aria hits | P | partial (`.reconciliation.test`) |
| planning/LicensePlanningPanel.tsx | Dialog host for editor | - | 3 | - | - | - | - |
| reports/LicenseExportPanel.tsx | Export controls | - | 2 | TW+tok 2 | 2 aria | Y | yes |

## 3. Layout (`layout/`)

| Path | Purpose | Fan-in | Styling | a11y | Dark | Tests |
|---|---|---|---|---|---|---|
| layout/AdminLayout.tsx | App shell: TopNav + `<main id="main-content" tabIndex=-1>` + TaskFAB + ParsingStatusDisplay; iframe suppression; per-route wrapper | 1 (`AppRoutes.tsx`, applied per route) | TW+tok 12, legacy `app-shell*`, inline 1 | skip target `main-content`, 6 aria hits | Y | - |
| layout/Sidebar.tsx | Legacy sidebar | **0*** (not imported by AdminLayout) | inline **9**, hex 1 (`:24 '#fff'`) | 4 aria | - | - |

## 4. UI-rendering hooks (legacy vs current)

| Path | Fan-in | Note |
|---|---|---|
| hooks/useConfirmDialog.tsx | 2 (MasterList, ReconciliationPanel) | Wraps hand-rolled `ConfirmDialog`; 3 other callers use `ConfirmDialog` directly (Settings, AllotmentAction, LicensePlanningWorkspace, ExpressionTreeEditor) |
| hooks/useModal.js | 1 (barrel `hooks/index.js` only; no real consumer) | Legacy `show/open/close` state; the modal components still use `show/onHide` Bootstrap-style props |
| hooks/useToast.js | 1 (barrel only) | Thin wrapper over `sonner`; real code calls `toast.*` directly (59 files, 338 calls) |

## 5. Page-local components reused by 2+ pages

| Path | Reused by | Notes |
|---|---|---|
| pages/reports/SionNormReport.tsx | SionE1, SionE5, SionE126, SionE132 | 443 lines, inline 10, `min-w/w-[Npx]` x44 each |
| pages/reports/itemReport/{ItemReportFilters,ItemReportTable,ItemReportTotalsBar,useItemReportFilters} | ItemReport, PlannedReport | ItemReportTable: inline **49**, `<table>` + react-select inside table |
| pages/license-overview/SortableHeader.tsx | AllotmentsTab, BoesTab, ItemsTab | Only reusable sortable header; second private copy at `pages/reports/LicensePurchaseProfitReport.tsx:116` |
| pages/reconciliation/LinkRecordModal.tsx | MissingBoeTab, MissingInvoiceTab | uses `ui/dialog` |
| pages/AllotmentAction.tsx, BOETransferLetter.tsx | route + `TransferLetterModal` | not really shared UI |
| Name collision | `components/licenseBalanceHelpers.ts` vs `pages/license-balance/licenseBalanceHelpers.ts` | two different files, same name |

## 6. Legacy primitives vs shadcn primitives

**shadcn (keep, extend):** `ui/{alert,badge,button,card,checkbox,dialog,dropdown-menu,input,label,select,separator,skeleton,sonner,switch,tabs,textarea,tooltip}`.

**Legacy / non-shadcn shared pieces (consolidation candidates):**

| Legacy | shadcn / target | Status |
|---|---|---|
| `components/ConfirmDialog.tsx` (hand-rolled portal + focus trap) | `ui/dialog` (Radix) | 5 importers; 2 modal systems coexist, plus 4 more hand-rolled `role="dialog"` (`TaskDrawer:409`, `CommandPalette:99`, `TopNav:336`, `masters/BoeMergeModal:19`, `masters/LinkTradeModal:19`) |
| `components/DataTable.tsx`, `AccordionTable.tsx`, `primitives/DetailTable.tsx` + 79 raw `<table>` | missing `ui/table` | legacy `.table` CSS class (`tabler.css:658`) in 8 files, 39 occurrences |
| `react-select` x19 files | no shadcn combobox (`ui/select` Radix used in 3 files) | styled by `App.css` `!important` and 19 `styles={}` props |
| `react-datepicker` (3 files) + native `type=date` (4 files) | no `ui/calendar` | `App.css:98` overrides |
| `components/Icon.tsx` (+ `AccordionTable` `LUCIDE_MAP`, `DataTable` `ActionIcon`, `EntityCard` map) | lucide direct | 3 separate bi-to-lucide maps |
| `components/StatCard.tsx` vs `pages/license-overview/{StatCard,SummaryCard}.tsx` | one `ui`-level stat card | see 03 report |
| `hooks/useToast.js`, `hooks/useModal.js` | `sonner` `toast`, Radix `Dialog open` | barrel-only |
| `ui/index.js` barrel | delete | broken re-exports of non-existent `primitives/*` |
| `form-label` (33), `table` (39 `className="table`), `tb-*` (253 occurrences), `app-*` (10) legacy CSS classes; `theme/tabler.css` 2457 lines, 153 `--tb-*` defs, 111 hex | tokens + Tailwind | `tabler.css` is the token source of truth, so it stays until tokens move to `styles/` |

## 7. Dead or unreferenced files (0 importers, confirmed by symbol grep)

`components/AllotmentFormModal.tsx` (524), `FormField.tsx` (203), `DataFilter.tsx` (68), `Timeline.tsx` (48), `GlobalErrorBoundary.tsx` (15), `item-async-select.tsx` (30), `motion/PageTransition.tsx` (24), `layout/Sidebar.tsx` (155), `ui/index.js`. Total about 1,070 lines. (`framer-motion` is imported only by `ErrorScreen`, `Login`, `PasswordReset` and the unused `PageTransition`.)

## 8. Headline numbers
- 18 shadcn primitives; ~45 flat shared components; 6 component test files in total.
- Raw Tailwind palette utilities: 516 uses in 44 files; 37 of those files have no `dark:` variant (305 uses). `dark:` appears only 97 times in 10 files, 49 in `Dashboard.tsx`.
- Inline `style={}`: 281 in `.tsx` (262 `style={{`).
- Hex literals in `.ts/.tsx/.js`: 85 in 10 files (23 are intended token definitions in `theme/tokens.js`).
