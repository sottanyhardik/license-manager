# 05 Reusable component spec (contracts, not implementations)

Date 2026-11-16. Companion to `04_UI_UX_MODERNIZATION_PLAN.md` (04). Evidence for "replaces" comes from `01_COMPONENT_INVENTORY.md` (01) and `03_DUPLICATION_REPORT.md` (03). These are prop sketches. Names are final, but internals are left to the implementer. Code is meant to compile under `strict` (04 §6.5). Visuals use only the tokens in 04 §1. Tests use vitest + RTL. "PW" = Playwright, "axe" = `@axe-core/playwright` via `e2e/accessibilityHelpers.ts`. Libraries marked (approval) are pending (04 §6.1).

Shared types (`src/types/list.ts`, `src/types/ui.ts`):
```ts
type Id = number | string;
type Tone = 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'neutral';      // = TONE_MAP keys, theme/tokens.js:13
type Density = 'compact' | 'default';
type FilterValue = string | number | boolean | string[] | { from?: string; to?: string } | null;
interface ListParams { page: number; pageSize: number; search?: string; ordering?: string; filters: Record<string, FilterValue> }
interface ListResult<T> { rows: T[]; count: number; page: number; pageSize: number; totalPages: number; hasNext: boolean; hasPrevious: boolean }
type Role = import('@/routes/authorizationRoles').Role;
```

---

## 1. DataTable (`components/data-table/DataTable.tsx`, on `@tanstack/react-table` (approval) + new `ui/table.tsx`)

**Purpose.** One table for every list. It is server-driven by default. It renders states and never fetches.

```ts
interface DataTableProps<T> {
  columns: ColumnDef<T, unknown>[];          // TanStack ColumnDef; meta: { align?: 'start'|'end'; numeric?: boolean; sticky?: 'start'; hideBelow?: 'md'|'lg' }
  data: T[];
  getRowId: (row: T) => string;
  caption: string;                           // rendered sr-only <caption>
  state: { status: 'loading' | 'error' | 'success'; error?: unknown; isFetching?: boolean };
  onRetry?: () => void;
  empty?: { title: string; description?: string; action?: React.ReactNode };
  sorting?: { value: SortingState; onChange: (s: SortingState) => void };   // server: maps to `ordering`; omit = not sortable
  manual?: boolean;                           // default true (server sort/paging); false = client-side for small bespoke payloads
  selection?: { value: RowSelectionState; onChange: (s: RowSelectionState) => void; bulkActions?: (ids: string[]) => React.ReactNode };
  columnVisibility?: { value: VisibilityState; onChange: (v: VisibilityState) => void; storageKey?: string };
  resizable?: boolean;                        // default false
  rowActions?: (row: T) => ActionMenuItem[]; // rendered through ActionMenu
  onRowClick?: (row: T) => void;              // whole row is a link-like target only if provided
  renderSubRow?: (row: T) => React.ReactNode; // expansion (replaces AccordionTable / LicensesTable inline panels)
  density?: Density;                          // default 'default'
  stickyHeader?: boolean;                     // default true; top offset = var(--app-sticky-offset)
  footer?: React.ReactNode;                   // slot for <Pagination>; totals row via column meta `footer`
}
```
**Replaces.** `components/DataTable.tsx` (8 importers), `components/AccordionTable.tsx` (570 lines, fetches inside the view; nested fetch moves to the caller's query), `LoadingFallback.tsx` `TableSkeletonLoader`, `license-overview/SortableHeader.tsx` and the private copy at `LicensePurchaseProfitReport.tsx:116`, the 20+ sticky-header recipes, and the 79 raw `<table>` in 41 files (03 §1) as phases reach them. `primitives/DetailTable.tsx` (key/value) is **not** replaced. It moves to `ui/table` styling instead.
**Non-goals.** No built-in fetching, filtering UI, pagination UI or export. Those are separate components and server endpoints. No inline cell editing framework: editable cells are column `cell` renderers using Form-kit fields. No pivot, grouping or aggregation engine (the ItemPivotReport shape stays a column definition). No virtualisation unless `@tanstack/react-virtual` is approved and measured. No drag-reorder of columns.
**a11y.** Native `<table>` semantics. `scope="col"`. `aria-sort` on sorted headers, with the sort control as a `<button>` inside `<th>`. `<caption class="sr-only">`. `aria-busy` while `isFetching`. Selection checkboxes are labelled ("Select row {id}", "Select all on page"). Row actions are one tab stop. Below `md` the table scrolls horizontally with a sticky first column. Cells are never turned into cards, so headers are not hidden (fixes `index.css:42`).
**Tests.** RTL: renders loading skeleton, error with retry, empty. Header click cycles `asc → desc → none` and calls `sorting.onChange`, and `aria-sort` updates. Select-all selects only the current page, and bulk actions receive ids. Hidden columns persist to `storageKey`. Numeric columns are end-aligned with `tabular-nums`. axe on a story fixture. PW: reconciliation and overview tabs in Phase 2.

## 2. FilterEngine (`components/filters/FilterBar.tsx`, extends `filters/FilterPanel.tsx`)

**Purpose.** Render a declared set of filters, edit a draft, and emit a `filters` object. Chips come from `ActiveFilters`.

```ts
type FilterDef =
  | { kind: 'text';        key: string; label: string; placeholder?: string }
  | { kind: 'select';      key: string; label: string; options: Option[] }
  | { kind: 'multiSelect'; key: string; label: string; options: Option[] }
  | { kind: 'asyncSelect'; key: string; label: string; load: (q: string, signal: AbortSignal) => Promise<Option[]>; multi?: boolean }
  | { kind: 'status';      key: string; label: string; options: (Option & { tone: Tone })[] }   // segmented / chips
  | { kind: 'dateRange';   key: string; label: string; presets?: DatePreset[] }                  // emits key_from / key_to
  | { kind: 'numberRange'; key: string; label: string; min?: number; max?: number; step?: number }; // emits key_min / key_max as today's params
interface Option { value: string; label: string }
interface FilterBarProps {
  defs: FilterDef[];
  value: Record<string, FilterValue>;         // applied filters (from useListQuery)
  defaults?: Record<string, FilterValue>;     // module defaults (getDefaultFilters)
  onApply: (next: Record<string, FilterValue>) => void;
  applyMode?: 'instant' | 'explicit';         // default 'instant' for <=4 simple fields; 'explicit' shows Apply
  presets?: { id: string; label: string; value: Record<string, FilterValue> }[];  // static, code-defined; selecting writes URL
  primary?: string[];                         // keys shown inline; rest go into "More filters" popover/sheet (sheet < md)
}
```
- Search is not a filter def. It is the toolbar's `SearchInput`, bound to `useListQuery.search`.
- `Clear` empties one field. `Reset` returns to `defaults`, not to empty (MasterList behaviour, `AdvancedFilter` `resetToDefaults`). `Apply` appears only in explicit mode.

**Replaces.** `AdvancedFilter.tsx` (303 lines, 0 aria), `pages/AllotmentFilters.tsx`, `reports/ItemPivotFilters.tsx`, `reports/itemReport/ItemReportFilters.tsx`, the inline filter blocks listed in 03 §2 (LicenseLedger, UserList, ActivityLog, BoesTab, LicensePurchaseProfitReport, LicensePlanningWorkspace, DownloadLicense, SionNormReport), and `DataFilter.tsx` (dead). It keeps `ActiveFilters.tsx` (13 consumers) as the chip row and `DateRangeFilter` logic inside `DateRangePicker` (§7).
**Non-goals.** No user-saved views and no server-stored presets (that would be a new feature). No boolean query builder or AND/OR groups. No renaming of param keys: each def's `key` is the backend filterset param in use today. No per-field validation framework.
**a11y.** Every control has a visible `<label>`. The group is a `<form role="search" aria-label="{module} filters">`. Active count is announced through `aria-live="polite"`. The "More filters" popover is Radix (focus trap, Esc). Chips are buttons named "Remove filter {label}: {value}".
**Tests.** RTL: each `kind` serialises to exactly today's query string for the migrated screen (snapshot per screen). Reset restores defaults. Instant mode debounces text (fake timers). Explicit mode doesn't emit until Apply. A preset writes its values. Labels are queryable by role. PW: AllotmentAction filters round-trip through the URL.

## 3. PaginationEngine: `useListQuery` + `<Pagination>`

**Purpose.** Own list state in the URL, fetch through TanStack Query, and render page controls. It implements 04 §3.

```ts
interface UseListQueryOptions<T> {
  key: (p: ListParams) => QueryKey;                         // from qk factory (04 §4)
  fetcher: (p: ListParams, signal: AbortSignal) => Promise<ListResult<T>>;
  defaults?: Partial<Omit<ListParams, 'page'>>;             // pageSize default 25
  filterKeys: string[];                                     // allow-list of URL params owned by this list
  urlPrefix?: string;                                       // for two lists on one page, e.g. 'avail_'
  persistKey?: string;                                      // opt-in localStorage fallback (filterPersistence.js), URL wins
  maxPageSize?: number;                                     // default 200; 100 for hand-rolled endpoints (available-licenses)
}
interface UseListQueryResult<T> {
  params: ListParams;
  result: ListResult<T> | undefined;
  status: 'loading' | 'error' | 'success'; isFetching: boolean; error: unknown; refetch: () => void;
  setPage: (n: number) => void; setPageSize: (n: number) => void;
  setSearch: (s: string) => void;                            // debounced 300ms internally
  setFilters: (f: Record<string, FilterValue>) => void;      // resets page to 1
  setOrdering: (o: string | undefined) => void;              // resets page to 1
  reset: () => void;
}
interface PaginationProps {
  page: number; totalPages: number; count: number; pageSize: number;
  hasPrevious: boolean; hasNext: boolean;
  onPageChange: (n: number) => void; onPageSizeChange?: (n: number) => void;
  pageSizes?: readonly number[];                            // default [25,50,100,200]
}
```
**Replaces.** `components/DataPagination.tsx` (restyled and kept as `<Pagination>`, 3 consumers), `hooks/usePagination.js` (only ItemReport client slicing, kept until a paginated endpoint exists), the local `page`/`page_size` state in LicensesTable, TradesListView, IncentiveLicensesTable, AllotmentsTable, GenericMasterCards and LicensePlanningWorkspace (03 §3), the URL sync in `MasterList.tsx:335-380,566-574`, and the 3 `has_next` variants. It fixes `useReconTabQuery.ts` truncation (04 §3.4).
**Non-goals.** No infinite scroll, no cursor/offset modes (none used, 00 §7.1), no client-side paging of server lists, and no "load all" (use `fetchAllPages` for option lists, 04 §3.4).
**a11y.** `<nav aria-label="Pagination">`. Prev/next/first/last are buttons with names. The current page has `aria-current="page"`. "Rows x-y of N" is a polite live region. The page-size select is labelled.
**Tests.** RTL (MemoryRouter): URL parses to params and serialises back. Defaults are left out of the URL. Filter, search or page-size change sets `page=1`. `pageSize > max` is clamped to 200. `urlPrefix` isolates two lists. `signal` is aborted on param change. Envelope variants (StandardPagination, MasterViewSet, `{count,results}`) normalise identically. PW: reload `?page=3&status=x` restores the view.

## 4. ModuleWorkspace (`components/workspace/`)

**Purpose.** The page shell in 04 §2.

```ts
interface ModuleWorkspaceProps {
  title: string;
  breadcrumbs?: { label: string; to?: string }[];
  meta?: React.ReactNode;                                    // badges, ids, StatusBadge
  primaryAction?: React.ReactNode;                           // at most one
  secondaryActions?: ActionMenuItem[];                       // collapse into ActionMenu below lg
  kpis?: React.ReactNode;                                    // <KpiStrip> of StatCards (0-6)
  tabs?: WorkspaceTab[];                                     // omit = no tab bar
  children?: React.ReactNode;                                // used when tabs omitted
}
interface WorkspaceTab { id: string; label: string; count?: number; anyRole?: Role[]; render: () => React.ReactNode }  // render is lazy: only active tab mounts
function useWorkspaceTab(tabs: WorkspaceTab[], defaultId: string): [active: string, set: (id: string) => void]; // ?tab=, replace:true, preserves other params, unknown/forbidden → default
interface WorkspaceSectionProps { title: string; description?: string; actions?: React.ReactNode; collapsible?: boolean; defaultOpen?: boolean; children: React.ReactNode }
interface DataWorkspaceProps { toolbar: React.ReactNode; table: React.ReactNode; pagination?: React.ReactNode }  // layout only
```
**Replaces.** `PageHeader.tsx` (22 files; kept as the internal header, `size: 'compact'` default), the hand-rolled `<h1>` at TradeForm:845, UserForm:157, LicensePlanningWorkspace:270, LicensePurchaseProfitReport:260 (03 §9), the tab plumbing in `LicenseOverviewPage.tsx:65-129` and `ReconciliationPanel.tsx:154`, the sticky toolbars with literal z-index (03 §13), and `AdminLayout` `QUICK_ACTIONS` placement concerns (actions become role-gated header actions).
**Non-goals.** No routing (it doesn't create routes). No data fetching. No layout config DSL. No side navigation. Sections don't persist open state. No per-tab URLs other than `?tab=`.
**a11y.** One `<h1>`. Breadcrumb `<nav aria-label="Breadcrumb">` with `aria-current="page"`. Radix Tabs (roving focus, `aria-controls`). The sticky tab bar doesn't cover focused content (`scroll-margin-top`). Collapsible section header is a `<button aria-expanded aria-controls>`. Focus moves to the panel heading on tab change only when triggered from the keyboard.
**Tests.** RTL: `?tab=boes` opens BOEs. Switching tabs keeps `page`/filters. Unknown tab falls back. A tab whose `anyRole` fails is absent and its URL falls back. Only the active tab renders. A single h1. axe on licence overview (existing `license-overview a11y` PW spec stays green).

## 5. Form kit (`components/form/`, `react-hook-form` + `zod` + `@hookform/resolvers` (approval))

**Purpose.** Labelled, accessible fields bound to RHF, with server-error mapping.

```ts
interface FormProps<S extends z.ZodTypeAny> {
  schema: S; defaultValues: z.input<S>;
  onSubmit: (values: z.output<S>) => Promise<void>;          // throw axios error → mapped to fields
  children: React.ReactNode; id?: string;
}
interface FieldBaseProps { name: string; label: string; description?: string; required?: boolean; disabled?: boolean }
// Fields: TextField, NumberField (decimal-safe string in, number out; precision prop), TextareaField, SelectField (Radix, static options),
//         AsyncSelectField (wraps the one async select, §2 load signature), DateField (§7 single), CheckboxField, SwitchField
interface SubmitBarProps { submitLabel: string; cancelTo?: string; onCancel?: () => void }  // disables while submitting; shows pending state
function mapServerErrors(err: unknown, setError: UseFormSetError<any>): string | null;      // DRF {field: [msg]} → fields; non_field_errors/detail → returned banner text
```
**Replaces.** The hand-rolled `useState` field state and `fieldErrors` in AllotmentFormModal (dead), TradeForm:48, UserForm:49, MasterForm:115, `LicensePlanningWorkspace.tsx:118` (03 §4). It reuses the a11y pattern of `FormField.tsx` (0 importers) and replaces `utils/formErrors.js` + `utils/formValidation.js` as callers migrate. Raw `<input>`/`<label>`/`<select>` and `form-label` go with them.
**Non-goals.** No schema-driven form generator (MasterForm's `entitySections.ts` config stays the caller's concern). No multi-step wizard. No autosave. No client re-implementation of server business rules (CIF/balance checks stay server-side; zod covers shape/required/format only). No dynamic field arrays beyond RHF `useFieldArray` used directly by callers.
**a11y.** `<label htmlFor>`. `aria-invalid`. `aria-describedby` linking description and error ids. Errors are `role="alert"` text, not colour alone. On a failed submit, focus goes to the first invalid field. Required fields are marked visually and with `aria-required`. The submit button gets `aria-busy` while pending.
**Tests.** RTL: required error shows on submit and focus moves to it. DRF 400 `{field:[..]}` lands on the field, `detail` lands in the banner. Double-submit is blocked while pending. NumberField keeps precision (no float drift on `"12.345"`). Labels are reachable by `getByLabelText`. UserForm migration keeps the existing tests green.

## 6. SearchInput (`components/SearchInput.tsx`)

**Purpose.** A text box that emits a debounced value.
```ts
interface SearchInputProps { value: string; onChange: (debounced: string) => void; label: string; placeholder?: string; delay?: number /* 300 */; size?: 'sm' | 'default' }
```
**Replaces.** `DebouncedSearchInput.tsx` (3 consumers, no label, `style` prop), the `AdvancedFilter.tsx:15` 400 ms debounce, the local `useDebouncedValue` in `SionAsyncItemSelect`, and ad hoc timers (03 §6). Debounce lives in a single `hooks/useDebouncedValue`.
**Non-goals.** No suggestions dropdown (that is the async select). No search-history, no `style` prop, and no field-scoped search syntax.
**a11y.** `type="search"`. `aria-label={label}` (visually hidden label allowed). The clear button is named "Clear search". Esc clears. The pending indicator is `aria-hidden`.
**Tests.** RTL + fake timers: emits once after `delay`. Clear emits `''` immediately. External `value` change syncs. Labelled.

## 7. DateRangePicker (`components/DateRangePicker.tsx`) and DateField

**Purpose.** From/to dates as ISO `YYYY-MM-DD`, with optional presets.
```ts
interface DateRangePickerProps { label: string; value: { from?: string; to?: string }; onChange: (v: { from?: string; to?: string }) => void; presets?: DatePreset[]; min?: string; max?: string }
interface DatePreset { id: string; label: string; range: () => { from?: string; to?: string } }
```
**Replaces.** `DateRangeFilter.tsx` (6 consumers; logic and preset support carried over), the native `type="date"` pairs in `LicensePurchaseProfitReport.tsx:282,287` and `TaskDrawer`. For single dates, `DateField` replaces `react-datepicker` in TradeForm:1102, MasterForm:541 and NestedFieldArray:352, removing that library later (04 §6.2). Display formatting stays in `utils/dateFormatter.js`.
**Non-goals.** No time-of-day, no timezones (the server receives dates), no custom calendar grid (native inputs), and no fiscal-year logic unless a preset in the code already exists.
**a11y.** Two labelled inputs ("{label} from" / "to") in a `fieldset` with `legend`. Presets are buttons with `aria-pressed`. If `from > to`, an inline `role="alert"` error appears and nothing is emitted.
**Tests.** RTL: emits ISO strings. Preset sets both ends. Invalid order is blocked. Clearing one end keeps the other. Snapshot of `_from/_to` params via FilterBar.

## 8. StatusBadge (`components/StatusBadge.tsx`, on `ui/badge`)

```ts
interface StatusBadgeProps { tone: Tone; label: string; appearance?: 'soft' | 'solid' | 'outline' /* soft */; icon?: LucideIcon; title?: string }
// domain helpers in src/lib/statusTone.ts return { tone, label } from existing derivers; components never pick colours
```
**Replaces.** The 7 tone maps (`theme/tokens.js` stays canonical, then `theme/tones.ts`; the maps at `ErrorScreen.tsx:21`, `StatCard.tsx:7`, `AlertCard.tsx:19`, `Settings.tsx:63`, `LicenseLedger.tsx:374`, `EntityCard.tsx:68` go). Also the parallel badges `ConditionBadge.tsx`, `PlanningEditor.tsx:291 StatusBadge`, `ItemPivotReport.tsx:181 PurchaseStatusBadge`, `Settings.tsx:114 RoleBadge`, `MdsStatusCard.tsx:47 healthBadge`, `TradeMetaBadges.tsx:11`, `EntityCard.tsx:70 HeaderChip`, and `text-[9px]`/`[0.6rem]` badge sizes (03 §8). `OverUtilisedBadge` stays (business flag with test) but is re-based on StatusBadge.
**Non-goals.** No custom colours or hex, no sizes beyond `text-2xs`, no click behaviour (wrap in a button if needed), and no new domain statuses.
**a11y.** The text label is always rendered (tone is never the only signal). Contrast is AA for every tone in both themes (checked by axe). Icon is `aria-hidden`.
**Tests.** RTL: each tone gets token classes and no raw palette. `statusTone` helpers return the same tone/label as the old derivers for a fixture table (parity test). axe in light and dark.

## 9. ConfirmDialog (`components/ConfirmDialog.tsx` rebuilt on Radix `ui/dialog`; `useConfirm` hook)

```ts
interface ConfirmOptions { title: string; description?: React.ReactNode; confirmLabel?: string; cancelLabel?: string; tone?: 'default' | 'danger'; requireText?: string /* type-to-confirm for destructive bulk ops */ }
function useConfirm(): (opts: ConfirmOptions) => Promise<boolean>;    // mount <ConfirmProvider> once in App
interface ConfirmDialogProps extends ConfirmOptions { open: boolean; onOpenChange: (o: boolean) => void; onConfirm: () => void | Promise<void> }  // controlled form for existing callers
```
**Replaces.** The hand-rolled `ConfirmDialog.tsx` (portal, own focus trap, `z-[1060]`, 5 importers), `hooks/useConfirmDialog.tsx` (2 consumers, kept as a thin alias during migration), and **`window.confirm`** at TaskDrawer:365, PlanningEditor:849, TradeForm:63, AllotmentsTable:78 (03 §5).
**Non-goals.** No arbitrary form content (use a Dialog), no stacking of multiple confirms, no auto-confirm timers.
**a11y.** Radix `role="alertdialog"`, title and description wired. Initial focus on Cancel for `danger`, on Confirm otherwise. Esc means cancel (`false`). Focus returns to the trigger. The confirm button gets `aria-busy` while an async `onConfirm` is pending.
**Tests.** RTL: `useConfirm` resolves `true`/`false`. Esc gives `false`. Danger focuses Cancel. `requireText` gates the button. Async confirm disables both buttons until settled. The ratchet ensures 0 `window.confirm`.

## 10. ActionMenu (`components/ActionMenu.tsx`, on `ui/dropdown-menu`)

```ts
interface ActionMenuItem { id: string; label: string; icon?: LucideIcon; onSelect?: () => void; to?: string; tone?: 'default' | 'danger'; disabled?: boolean; disabledReason?: string; anyRole?: Role[]; confirm?: ConfirmOptions; separatorBefore?: boolean }
interface ActionMenuProps { items: ActionMenuItem[]; label: string /* aria-label of trigger, e.g. "Actions for BOE 1234" */; trigger?: 'icon' | 'button' }
```
**Replaces.** The per-row action button clusters in `DataTable.tsx` (`ActionIcon`), `AccordionTable`, `MasterList.tsx:1445-1482` (edit/copy/allocate), `TradesListView`, and secondary header actions. It also absorbs part of the 199 raw `<button>` (03 §13).
**Non-goals.** No nested submenus, no item search, no custom item renderers.
**a11y.** Radix menu (arrow keys, typeahead, Esc). The trigger has a contextual `aria-label`. A disabled item exposes `disabledReason` via tooltip and `aria-describedby`. Items failing `anyRole` are not rendered (UI hint only; the backend is authoritative, 00 §9).
**Tests.** RTL: role filtering. `confirm` routes through `useConfirm` before `onSelect`. `to` renders a link. Keyboard open/select.

## 11. DocumentViewer (`components/DocumentViewer.tsx`)

**Purpose.** Show one authenticated PDF or image (licence copy, merged documents, transfer letter preview) in a Dialog or panel, with download.
```ts
interface DocumentViewerProps { source: { path: string } | { blobUrl: string }; title: string; kind?: 'pdf' | 'image' /* inferred from content-type */; open: boolean; onOpenChange: (o: boolean) => void; downloadName?: string }
```
**Replaces.** The fetch-blob-and-display logic in `AuthedImage.tsx`, the `/pdf-viewer` page's viewer (`PDFViewer`; the route stays and renders this component full-page), `utils/pdfPreview.js` callers, and the `h-[95vh] w-[95vw]` `TransferLetterModal` viewer shell (03 §14).
**Non-goals.** No annotation, no page thumbnails, no editing, no in-app PDF rendering library (use the browser viewer via `<iframe>`/`<object>` on a blob URL), no multi-document tabs.
**a11y.** Dialog titled with `title`. `<iframe title>`. A download link is always available as a fallback for screen-reader users. Loading and error states announced.
**Tests.** RTL: blob is fetched with the auth header via the axios instance (mocked). Object URL is revoked on close. Error shows retry and download fallback.

## 12. ActivityTimeline (`components/ActivityTimeline.tsx`)

```ts
interface ActivityItem { id: Id; at: string /* ISO */; actor?: string; action: string; detail?: React.ReactNode; tone?: Tone }
interface ActivityTimelineProps { items: ActivityItem[]; state: { status: 'loading' | 'error' | 'success' }; emptyLabel?: string; onRetry?: () => void }
```
**Replaces.** `components/Timeline.tsx` (dead, 0 importers, keeps its `<ol>` semantics) and the list rendering in `reconciliation/ReconciliationAuditLog`. Optionally also task remarks in `TaskDrawer` (where it renders a history list). `ActivityLog` stays a DataTable (tabular, filterable).
**Non-goals.** No fetching, no pagination (callers slice), no grouping by day beyond a simple date header, no real-time updates.
**a11y.** `<ol>` with `<time dateTime>`. Tone has a text label. Empty state is `role="status"`.
**Tests.** RTL: order preserved. Dates formatted via `utils/dateFormatter.js`. Loading, empty and error states.

## 13. EmptyState (`components/EmptyState.tsx`, extended) + `InlineError`, `LoadingState`

```ts
interface EmptyStateProps { title: string; description?: string; icon?: LucideIcon; action?: React.ReactNode; size?: 'inline' | 'page' }
interface InlineErrorProps { error: unknown; onRetry?: () => void; title?: string }      // message via utils/errorUtils.getErrorMessage
interface LoadingStateProps { variant: 'skeleton-rows' | 'spinner' | 'page'; rows?: number; label?: string }
```
**Replaces.** 39 ad hoc "No ... found" literals in 33 files, `LicensesTable.tsx:893 EmptyTabState`, the `DataTable` `Inbox` block, the 29 inline "Failed to load" blocks and 24 hand-written `role="alert"` blocks (03 §10), and the `LoadingFallback` duplicates `FormSkeletonLoader`/`InlineLoader` (0 users). `PageLoader` stays as the Suspense fallback.
**Non-goals.** No illustrations, no marketing copy, no more than one action.
**a11y.** EmptyState `role="status"`. InlineError uses `ui/alert` (`role="alert"`) with a named retry button. LoadingState uses `role="status"` with `aria-label`/`label`, skeletons are `aria-hidden`, and spinners respect reduced motion.
**Tests.** RTL: roles present. Retry calls `onRetry`. DRF error payload renders its message. Reduced-motion class applied.

## 14. ErrorBoundary (`components/ErrorBoundary.tsx`, rebuilt)

```ts
interface ErrorBoundaryProps { scope: 'app' | 'route' | 'panel'; resetKeys?: unknown[]; fallback?: (e: { error: Error; reset: () => void }) => React.ReactNode; children: React.ReactNode }
```
- `app` wraps the providers as today (`App.tsx:19`). `route` is placed inside `AdminLayout` around `<main>` content, so a render error keeps TopNav (00 §8 says the current boundary removes the nav). `panel` wraps each workspace tab and resets on `resetKeys` (tab id, params). It integrates with TanStack `QueryErrorResetBoundary`.

**Replaces.** The current `ErrorBoundary.tsx` (Bootstrap fallback classes `container mt-5 alert alert-danger`, 00 §8) and `GlobalErrorBoundary.tsx` (dead). The fallback reuses `ErrorScreen` (route/app) and `InlineError` (panel).
**Non-goals.** No remote error reporting (no logging dependency or endpoint exists). No handling of async/API errors, which are Query state.
**a11y.** Fallback heading and message are focusable. Focus moves to the fallback heading. Retry button is named.
**Tests.** RTL: a throwing child renders the fallback. Reset re-renders children. `resetKeys` change auto-resets. Route scope keeps a sibling nav rendered.

## 15. PermissionGate (`components/PermissionGate.tsx`, typed) + `usePermission`

```ts
interface PermissionGateProps { anyRole?: Role[]; allRoles?: Role[]; superuser?: boolean; fallback?: React.ReactNode; children: React.ReactNode }
function usePermission(): { can: (check: { anyRole?: Role[]; allRoles?: Role[]; superuser?: boolean }) => boolean };
```
- Role sets come only from `routes/authorizationRoles.ts` (`ROLES` + the 14 named sets). Write-capability sets that live in components today (`ENTITY_WRITE_ROLES` inside `MasterList.tsx:114-120`, inline arrays at `Dashboard.tsx:187-196`) move there **with identical contents**. Superuser bypass matches `AuthContext.tsx:240-248`.

**Replaces.** The current untyped `PermissionGate.tsx` (props `role`/`anyRole`, 1 consumer). `role: string` becomes `anyRole: [ROLES.X]`. It also replaces the ad hoc `hasRole/hasAnyRole` conditionals in MasterList, Dashboard, license-overview and OverviewTab (00 §9), and gives the gating for `AdminLayout` `QUICK_ACTIONS`, which are unfiltered today.
**Non-goals.** No object-level or field-level permissions, no new roles, no fetching of permissions from the server, and no change to route guards (`ProtectedRoute` stays authoritative for navigation). It is a UI hint only, because the backend enforces (`apps/accounts/permissions.py`). Any role-set content change is an **API/permission change** and must be escalated.
**a11y.** Renders nothing (or `fallback`) when access fails. Hidden actions are not rendered, rather than disabled, unless the caller passes a fallback with an explanation.
**Tests.** RTL: matrix test over each named role set × representative users (manager, viewer, ACCOUNT_ACCESS, TL_GENERATE, superuser). Parity test: the moved `ENTITY_WRITE_ROLES` and Dashboard arrays equal their previous literals. The existing `authorizationRoles.test.ts` stays green.

---

## Cross-cutting test and review plan
- Each component lands with its own RTL test file in the same folder (there are 6 component tests today, 01 legend). Ratchet test counts are updated in the same PR.
- Run axe through PW on the first screen adopting each component, in light and dark.
- A handoff to `a11y-architect` is needed for: DataTable sticky first column + horizontal scroll at 390px, FilterBar sheet below `md`, `?tab=` focus management.
- Risks: (1) `normalizeList` must accept every envelope listed in 00 §7.1, or lists break silently. Test each envelope. (2) Server-sort parity: `ordering` field names must match each viewset's `ordering_fields`. (3) `PermissionGate` migration must not widen or narrow visibility. Use the parity tests.

---

## 16. ExpandableDataTable + DetailTabs + ModuleAccordion (record-level workspace)

**Builds on what exists.** `masters/tables/LicensesTable.tsx` already expands a row inline (Ledger/Balance tabs), and `/licenses/:id/overview` (`license-overview/*`, 6 tabs) already has per-licence endpoints. The record workspace re-hosts those tab bodies inside the expanded row. The `/overview` page stays as the deep-link target; no route is removed.

```ts
interface ExpandableDataTableProps<T extends { id: number }> extends DataTableProps<T> {
  renderExpanded: (row: T) => React.ReactNode;   // usually <RecordWorkspace id={row.id} .../>
  expandedId?: number | null;                     // controlled; URL key ?expanded=<id>
  onExpandedChange?: (id: number | null) => void;
  singleExpand?: boolean;                         // default true
}
interface DetailTabsProps {
  recordKey: string;                              // e.g. `license:${id}`; part of every query key
  tabs: { id: string; label: string; visible?: boolean; render: () => React.ReactNode }[];
  value?: string; onValueChange?: (id: string) => void; // URL key ?tab=
}
interface ModuleAccordionProps {
  sections: { id: string; title: string; defaultOpen?: boolean; render: () => React.ReactNode }[];
  persistKey?: string;                            // open state per record+tab, in sessionStorage
}
```

**Rules:**
- Row identity is `row.id` (getRowId).
- Every detail query key includes `recordKey`, and tab bodies mount lazily (Radix `forceMount` off). Data loads on first open and is cached per `(record, tab)`. Switching records unmounts the old panel, so stale data is impossible by construction.
- Mutations invalidate `qk.<module>.detail(id)` plus the list.
- One expanded row by default.
- Accordions are one level deep only.
- Expand control: `<button aria-expanded aria-controls>`, and the expanded region has `role="region"` labelled by the row.

**Non-goals:**
- No editing state machine inside the table.
- No nested ExpandableDataTables more than 1 level deep.
- No client-side computing of balances: the backend stays authoritative, and values are rendered as received.

### Licence record tabs → existing data sources (no invented information)

| Requested tab | Existing source | Status |
|---|---|---|
| Overview (accordions: details, entitlement, utilisation, available balance, dates) | `licenses/:id/overview-summary` + existing `OverviewTab` / KPI cards | ✅ exists |
| Import Item | `licenses/:id/overview-items`, `item-usage`, `SionNormCard` | ✅ exists |
| BOE & Allotment | `overview-boes`, `overview-allotments`, `hide-boe*`/`restore-boe*` | ✅ exists |
| Invoices | `overview-invoice-ledger` | ✅ exists |
| Reconciliation | No per-licence endpoint. Reconciliation endpoints are global (`/reconciliation/*`) | ⚠️ **gap**: needs a backend `?license=` filter on existing detections (additive API, approval) or the tab is omitted |
| Planning | `PlanningEditor` (already embedded in the overview Planning tab), `replan-status` | ✅ exists |
| Edit Options | existing actions only: edit (`/licenses/:id/edit`), recalculate, hide/restore BOE, individual-item CIF override, gated by `LICENSE_MANAGER` | ✅ exists |
| Documents | `licenses/:id/merged-documents`, `LicenseDocumentModel` | ✅ exists |
| Activity / Audit History | `core_activitylog` (request-level) has no per-record API | ⚠️ **gap**: needs an additive, filtered activity endpoint (approval) or the tab is omitted |

The BOE (10 tabs) and Allotment (10 tabs) record workspaces follow the same table. They must be mapped against `02` before their phase. Tabs without an existing data source are listed as gaps, not built.

### Data-presentation preservation (applies to every migrated table)

Before and after each migration, a Playwright snapshot for a fixed set of records compares: header labels and order; cell text, i.e. formatted numbers, dates and currency, exactly; default sort and filters; page size; and the visible actions per role. Any diff fails the phase.
