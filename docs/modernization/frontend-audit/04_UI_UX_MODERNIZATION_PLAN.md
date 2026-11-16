# 04 UI/UX modernization plan (design, docs only)

Date 2026-11-16. Built on `00_FRONTEND_ARCHITECTURE.md` (00), `01_COMPONENT_INVENTORY.md` (01), `02_MODULE_RESPONSIBILITY.md` (02), `03_DUPLICATION_REPORT.md` (03). Component contracts are in `05_REUSABLE_COMPONENT_SPEC.md` (05). No source changed; no gate run. Nothing here adds a route, an endpoint or a business feature. Every change is UI-only and must keep API calls, role gates and data flow the same (`.claude/rules/frontend.md` "Preserve business logic"). Where a phase touches allocation, reconciliation or balance screens, it changes presentation and fetching only. Balance math stays server-side (`LicenseBalanceCalculator`, ARCHITECTURE_RULES #4).

## 0. Principles

- Restraint, as in Linear, Stripe and Vercel. Content sits on the page background with 1px borders. A card is used only when it is a separate object (KPI tile, dialog, side panel), never as a wrapper for a whole section. Headers are small (title 20px). There is one primary action per view. Motion is limited to 150 ms opacity/transform on overlays and is off under `prefers-reduced-motion`.
- Build on what exists. `--tb-*` in `src/theme/tabler.css` stays the token source (01 §6). shadcn variables already bridge onto it (`src/styles/tailwind.css:35-96`). Dark mode stays `[data-theme="dark"]` (`tailwind.css:28`, `tabler.css:259`). We add tokens. We don't rename or replace any.
- Ratchet, don't big-bang. Each phase migrates named files. A grep-based vitest ratchet (no new dependency, same idea as the backend ratchets in ARCHITECTURE_RULES) stops raw palette, arbitrary `text-[..]`, hex, `style={{` and `window.confirm` counts from growing. Counts may only fall.

## 1. Design system

### 1.1 Typography: 30 arbitrary sizes collapse to 6 steps
03 §13 found 192 arbitrary `text-[..]` uses in 30 sizes, and sub-12px text is common. Existing tokens: `--tb-fs-xs..2xl` = 11/12/13.5/14.5/16/20/26 (`tabler.css:70-76`).

| Step | Token (new, in `tabler.css`, aliased in `@theme`) | Size / line-height | Use | Absorbs |
|---|---|---|---|---|
| `text-2xs` | `--tb-fs-2xs` = `--tb-fs-xs` | 11 / 16 | badges, table meta, KPI labels (uppercase only with tracking) | `[9px]`..`[11.5px]`, `[0.6rem]`. Sizes below 11 are removed |
| `text-xs` | `--tb-fs-sm` | 12 / 16 | dense table cells, helper/error text, chips | `[12px]`, `[12.5px]` |
| `text-sm` | `--tb-fs-base` (13.5 to **13**) | 13 / 20 | default body, table body, forms, menus | `[13px]`, `[13.5px]` |
| `text-base` | `--tb-fs-md` (14.5 to **14**) | 14 / 20 | prose, dialog body, input text on touch (`md` and below) | `[14px]`..`[15px]` |
| `text-lg` | `--tb-fs-lg` | 16 / 24 | section and tab-panel titles, dialog title | `[16px]`..`[18px]` |
| `text-xl` | `--tb-fs-xl` | 20 / 28 | page title (ModuleWorkspace h1), KPI value | `text-2xl`, `[1.625rem]`, `text-3xl` (PageHeader), `[1.5rem]` |

- Tailwind v4 lets the `--text-*` theme vars be overridden in `@theme inline`, so the 781 `text-xs` and 519 `text-sm` uses (03 §13) re-map with no class edits. This shifts sizes by about 1px, so it needs a visual diff (light and dark) and is a Phase 1 risk.
- `text-2xl` and larger are allowed only on `Login`, `PasswordReset` and `ErrorScreen`. Weights: 400 body, 500 labels and table headers, 600 titles. Nothing heavier than 600. Numbers use `tabular-nums` in every numeric column and KPI.

### 1.2 Spacing and density
- Scale (Tailwind 4px grid): `0.5, 1, 1.5, 2, 3, 4, 6, 8` (2 to 32px). `p-5`, `p-6` and arbitrary `[Npx]` paddings are migrated to this scale (03 §13: 448 arbitrary px values).
- Layout rhythm: page gutter `px-4 md:px-6`. Section gap `gap-6`. Gap inside a toolbar or form row: `gap-2`. Form field stack: `gap-1.5` (label to control) and `gap-4` (between fields).
- Density, chosen per table with the `density` prop (05 DataTable):

| Density | Row height | Cell padding | Header | Default for |
|---|---|---|---|---|
| `compact` | 32px (`h-8`) | `px-2 py-1` | 32px, `text-xs font-medium` | ledgers, reconciliation, reports, available-licences |
| `default` | 40px | `px-3 py-2` | 36px | masters, users, activity log |

- Control heights: `h-8` (sm/compact: toolbars, filters, table actions) and `h-9` (default: forms, dialogs). `h-10` is retired, which is part of the Button/Input change in §6.4.

### 1.3 Radii (one scale)
The `--tb-r-*` values (`tabler.css:102-106`) and `--radius-*` (`tailwind.css:89-92`) already resolve to the same 6/8/10/14 values. Allowed:

| Class | px | Use |
|---|---|---|
| `rounded-sm` | 6 | badge, chip, checkbox, kbd |
| `rounded-md` | 8 | button, input, select, menu item, popover |
| `rounded-lg` | 10 | card, dialog, table container, KPI tile |
| `rounded-full` | pill | avatar, status dot, switch |

Retired: bare `rounded` (109), `rounded-xl` (89, includes `ui/card`), `rounded-2xl`, `rounded-[..]` (03 §13). Button and Input go from `rounded-lg` to `rounded-md`, and Card from `rounded-xl` to `rounded-lg` (visual diff, §6.4).

### 1.4 Borders and elevation
- Borders are always 1px `border-border`. Inner dividers use `border-border/60` (or the existing `--tb-border-soft`). Button outline goes from `border-2` to 1px (03 §13).
- Elevation maps onto the existing `--tb-shadow-*` (`tabler.css:109-113`):

| Level | Token | Use |
|---|---|---|
| 0 | none + border | page sections, tables, cards (default) |
| 1 | `--tb-shadow-1` | sticky table header or toolbar while scrolled, KPI tile hover |
| 2 | `--tb-shadow-2` | popover, dropdown, combobox list |
| overlay | `--tb-shadow-overlay` | dialog, sheet, command palette |

`shadow-sm` on cards (81 uses) is removed step by step as files are migrated. `backdrop-blur` is used only on the sticky tab bar.

### 1.5 Semantic status tones (7 maps become 1)
- Canonical map: `TONE_MAP` in `src/theme/tokens.js:13-20` (tones `primary, success, warning, danger, info, neutral`, already on `--tb-*-soft/-text/-border`). It moves to typed `src/theme/tones.ts` (re-exported from `tokens.js` for compatibility). New `@theme` aliases expose it to Tailwind: `--color-{tone}-soft`, `--color-{tone}-text`, `--color-{tone}-border`, which gives `bg-success-soft text-success-text border-success-border`.
- `ui/badge` variants become the only visual definition (`tone` + `appearance: soft|solid|outline`). Retire the local maps at `ErrorScreen.tsx:21`, `StatCard.tsx:7`, `AlertCard.tsx:19`, `Settings.tsx:63`, `LicenseLedger.tsx:374`, `EntityCard.tsx:68` and `CHIP_TONE_MAP`/`ACTION_TONE_MAP` (03 §8).
- Domain mapping: existing status derivers move unchanged into `src/lib/statusTone.ts`, one function per domain. Mapped: `LicensesTable.tsx:224 deriveStatus`, `Dashboard.tsx:171 getExpiryBadgeVariant`, `ItemPivotReport.tsx:181 PurchaseStatusBadge`, `MdsStatusCard.tsx:47 healthBadge`, `Settings.tsx:114 RoleBadge`, `ConditionBadge`, `PlanningEditor.tsx:291`. No new status values are invented. Tone is never the only signal: every badge has a text label (01 notes `ui/badge` has no colour-only guard).

### 1.6 Icons
lucide only (`.claude/rules/frontend.md`). Sizes: `size-3.5` (in dense rows, badges, `text-xs` buttons), `size-4` (default: buttons, menus, inputs), `size-5` (page-title adornment, KPI icon), `size-8` (EmptyState). `size-3`, `size-6` and `h-4 w-4` are migrated (03 §13). The three bi-to-lucide maps (`Icon.tsx`, `AccordionTable` `LUCIDE_MAP`, `EntityCard` map) are retired as their callers migrate. Decorative icons get `aria-hidden`. Icon-only buttons need `aria-label`.

### 1.7 Light/dark parity rules
1. Migrated code uses only semantic utilities (`bg-card`, `text-muted-foreground`, tone utilities). Raw palette and hex are banned, enforced by the ratchet. Today: 516 raw palette uses in 44 files, 37 of them with no `dark:` (01 §8).
2. `dark:` variants are allowed only where a token can't express the need, e.g. chart series. The Dashboard pattern (49 slate/`dark:` pairs) is migrated to tokens, not copied.
3. Colour assigned in JS, such as `cell.style.backgroundColor = '#f8fafc'` (`ItemPivotReport.tsx:400`), is replaced by a class toggle.
4. react-select and react-datepicker themes are driven by tokens through `classNames`. The `App.css:98,123-126` `!important` overrides go away (03 §6, §12).
5. Every phase's Playwright run screenshots each touched screen in both themes (§5).

### 1.8 Focus and keyboard
- One focus recipe: `outline-none focus-visible:ring-[3px] focus-visible:ring-ring/50` (the Button recipe in 01 §1, equal to `--tb-ring`). Applied to every interactive primitive, including table rows that can be activated and tab triggers.
- Add a skip link to `#main-content` in `AdminLayout` (00 §11 reports none). Overlays all use Radix (focus trap, Esc, focus restore). The hand-rolled ones (`ConfirmDialog`, `BoeMergeModal`, `LinkTradeModal`, `TaskDrawer`) are moved onto Radix (03 §5).
- Tables: header sort buttons are focusable and carry `aria-sort` (0 uses today, 03 §1). Each row-actions menu is one tab stop. Bulk-selection checkboxes have labels. Tabs use Radix roving focus.
- Motion: `active:scale-95` on Button goes under `motion-safe:` (01 §1).

### 1.9 Breakpoints: closing the sm to lg gap
Tailwind defaults stay: `md` 768, `lg` 1024, `xl` 1280. Supported targets are the 5 viewports already listed in `tests/responsive.test.ts` (390, 768, 1024, 1366, 1440).

| Range | Layout contract |
|---|---|
| < 768 (phone) | read-first. Single column, tabs scroll horizontally, toolbar collapses to search + "Filters" button that opens a sheet. Tables scroll horizontally with a sticky first column. Rows are not turned into cards |
| 768-1023 (tablet, `md`) | **required**. KPI strip 3 columns, forms 2 columns, filters 2-3 per row, header actions collapse into ActionMenu except the primary |
| >= 1024 (desktop) | full toolbar, KPI strip up to 6, forms 2-3 columns |

Rules: any layout that changes at `lg:` must also state its `md:` behaviour (`md:` is 8x rarer than `sm:`, 03 §14). Replace `tabler.css` `@media (max-width:720px)` (`:1874`) and the `index.css:40` 768px rule with Tailwind breakpoints. Delete the `.table-responsive-mobile` `thead { display:none }` rule (`index.css:39-52`). Fixed minimums (`minWidth:1600px` `ItemReportTable.tsx:77`, `min-w-[1000px]` `ItemPivotReport.tsx:248`) move into DataTable column `size` definitions, inside a horizontal-scroll container.

## 2. ModuleWorkspace pattern

Contract in 05 §4. Structure:

```
ModuleWorkspace
├─ Header        breadcrumb (nav aria-label="Breadcrumb") · h1 title (text-xl) · meta/badges · primary action · secondary actions (ActionMenu)
├─ KpiStrip?     0-6 StatCards, compact, optional
├─ Tabs?         Radix Tabs, sticky under TopNav (56px offset token --app-topbar-h)
└─ Panel(s)
   ├─ Section*   optional collapsible (native button + aria-expanded/aria-controls; no new Radix dep)
   └─ DataWorkspace   Toolbar (FilterEngine + bulk actions) · DataTable · Pagination
```

### 2.1 Route strategy: **`?tab=`** on the existing URLs
- Precedent: `LicenseOverviewPage.tsx:51,65-129` already keeps the tab in `?tab=` and drops it for the default tab. Tabs fetch lazily on activation (`:46-48`).
- Rules: (a) No route path is added, removed or renamed. (b) The default tab has no param, so every current bare URL renders exactly what it renders today. (c) Tab changes use `replace` and preserve all other params (filters, page). (d) An unknown or unauthorised `tab` falls back to the default without a 403. The route guard stays authoritative, and tab gates mirror it (05 PermissionGate). (e) Where 02 proposes merging pages that currently have their own routes (ledger, admin), the old routes stay. Each mounts the same workspace with its tab preselected, so deep links, bookmarks and `state.from` login returns are unchanged.
- Why not nested child routes: they would add paths (e.g. `/allotments/:id/allocate` as a child of a new `/allotments/:id`) that don't exist today (00 §3). They would also require turning the 45 per-route `AdminLayout` wrappers into a layout route. That refactor is worth doing separately (00 §12 #7) but isn't needed here.

### 2.2 Per-module tab and section map (only from 02 §3)

| Module (02 ref) | Workspace URL (existing) | Tabs (default first) | KPI strip | Notes / gates |
|---|---|---|---|---|
| Licences (3.1) | `/licenses/:id/overview` | Overview, BOEs, Allotments, Planning, Items, Invoice Ledger (all six exist), then **Ledger** (`LicenseLedgerDetail` content, same `license-ledger/:x` API) | existing overview summary | 02 names the workspace `/licenses/:id`, but that route doesn't exist (`AppRoutes.tsx` has `/edit`, `/overview`, `/balance` only), so the existing overview URL is used. "Edit details" stays the `/licenses/:id/edit` route and is linked from the header (moving the 1137-line `MasterForm` into a tab is deferred, high risk). "Documents" is a header secondary action over the existing `merged-documents` call, not a new tab. Edit/planning edit stay `LICENSE_MANAGER` |
| Licence list (3.1) | `/licenses` | none. The inline Ledger/Balance expand panels remain as row expansion | none | dedupe `LedgerTab`/`BoesTab` BOE rendering (02 3.1) |
| BOE (3.2) | `/bill-of-entries/:id/edit` | Details (form), Transfer letter (`TransferLetterForm`, gate `BOE_TRANSFER_LETTER_ROLES`) | none | `/bill-of-entries/:id/generate-transfer-letter` stays and preselects the tab. Merge stays a dialog action (it is an action, not a view). `ACCOUNT_ACCESS` invoice-only edit unchanged |
| Allotments (3.3) | `/allotments/:id/edit` | Details, Allocate (`AllotmentAction`, `ALLOTMENT_MANAGER`) | allocation totals already on AllotmentAction | `/allotments/:id/allocate` stays as its own route mounting the Allocate tab. Exports are header actions, not a tab |
| Reconciliation (3.4) | `/reconciliation` | existing 7 tabs + Audit log, tab moved to `?tab=` (today local state, `ReconciliationPanel.tsx:154`) | existing 7 StatCards (`:143-149`) | `/reconciliation-issues` stays (different, wider read gate `RECONCILIATION_ISSUES_ROLES`). Folding it in needs a role decision (approval item §6.5) |
| Trades / invoices (3.5) | `/trades/:id/edit` | Details (`TradeForm`), Counterpart (read view of `counterpart_info`) | none | Documents (bill of supply, purchase invoice) remain header actions, as today. Write `TRADE_MANAGER` |
| Incentive licences (3.6) | unchanged | none | none | list/form only (02: "keep as is") |
| Ledger (3.7) | `/license-ledger` | Browse, Upload (`LEDGER_UPLOAD_ROLES`), Package requests (list, then detail/readiness drill-down; readiness `LEDGER_PACKAGE_READINESS_ROLES`) | none | `/ledger-upload`, `/license-ledger/download-requests[/:id]`, `/package-readiness/:jobId` stay as routes that mount the matching tab |
| Planning (3.8) | `/planning` | Rules (existing workspace tabs), Licence plan (`PlanningEditor`) | none | `LICENSE_MANAGER` |
| Reports (3.9) | each `/reports/*` stays | report selector in header grouped as 02 3.9 (Stock/Balance, SION norms, Licence status, Profit), driven by `REPORT_ROUTES` | per report | Navigation regrouping only. Each report keeps its own URL, so there are no tabs that hold state. Gate `REPORT_ROLES` |
| Masters (3.10) | `/masters/:entity` | entity selector from `masterEntities` (9) as nav, not tabs | none | Customers/suppliers = `companies` master |
| Dashboard (3.11) | `/dashboard` | none (entry surface) | existing tiles | quick actions role-filtered (00 §2) |
| Admin (3.12) | `/admin/users` | Users, Activity log, MDS status | none | `/admin/activity-log` stays and preselects. Merging with `/settings` user CRUD is **blocked on owner decision** (02 3.12) |

## 3. Data contract

### 3.1 Backend facts (00 §7.1)
`StandardPagination` (`apps/core/pagination.py:39-41`): `page`, `page_size`, default 25, **max 200**. Envelope `{count, next, previous, page_size, total_pages, current_page, results}`. `MasterViewSet.list` adds `has_next`, `has_previous` (`master_view.py:570-640`). Reconciliation: default 50, max 500 (`reconciliation/api/views.py:39-41`), DRF envelope. Filters: django-filter field params, `search`, `ordering` (`-field`), date ranges as `__gte/__lte`. Hand-rolled slices (ledger requests 20/100, available-licences 20/100) and `ActivityLog` `limit` (max 1000) are exceptions, not targets.

### 3.2 One frontend list contract (`src/api/list.ts`, types in `src/types/list.ts`)
```ts
interface ListParams { page: number; pageSize: number; search?: string; ordering?: string; filters: Record<string, FilterValue> }
interface ListResult<T> { rows: T[]; count: number; page: number; pageSize: number; totalPages: number; hasNext: boolean; hasPrevious: boolean }
function toQuery(p: ListParams): URLSearchParams          // page, page_size (clamped to 200), search, ordering, filters (+ _from/_to → __gte/__lte, as MasterList.tsx:400-412 does today)
function normalizeList<T>(raw: unknown, sent: ListParams): ListResult<T> // accepts StandardPagination, DRF default, MasterViewSet, {count,results}, or plain array
```
- `hasNext` and `hasPrevious` come from `has_next`/`next` when present and otherwise from `page < totalPages`. This removes the three variants in 03 §3.
- `PAGE_SIZE_MAX = 200` lives on the client. Allowed sizes `[25, 50, 100, 200]`. Default 25 matches the server default. `DataPagination`'s `10` is dropped; changing a user's page size is a visible behaviour change, so it is noted per phase.
- Endpoint wrappers in `src/api/*Api.ts` take `(params: ListParams, signal?: AbortSignal)` and return `ListResult<T>`. Typed generics replace `any` (00 §4: 3 typed calls of 293).

### 3.3 URL query sync
- Encoding: `?page=2&page_size=50&search=abc&ordering=-invoice_date&<filter>=<v>&tab=boes`. Multi-select values are repeated keys (`status=a&status=b`). Ranges use the existing `_from/_to` UI names and are mapped to `__gte/__lte` only in `toQuery`, which keeps current MasterList URLs valid.
- Precedence: URL first, then saved state (`utils/filterPersistence.js`, kept for MasterList/LicensesTable as today, 00 §6), then module defaults (`getDefaultFilters(entity)`). Default values are left out of the URL.
- Writes use `setSearchParams(..., {replace: true})` for typing and filter edits, and push for page changes, so Back steps through pages, not keystrokes. Any filter, search or page-size change resets `page` to 1. `tab` and unrelated params are preserved.
- Mechanism: `useListQuery` (05 §3) owns parse, serialize and debounce. Pages don't call `useSearchParams` for list state.

### 3.4 Defects fixed in the first batch (shipped with Phase 1)
1. **Reconciliation tabs show only 50 rows.** `useReconTabQuery.ts:16-21` and `unwrapList` (`reconciliationHelpers.ts:24-30`) keep `results` only, but the backend paginates at 50/page (00 §7.2 #6). A tab with more than 50 rows looks complete while the summary card shows the true total. Fix: `useReconTabQuery` uses `useListQuery` (page/page_size, page size up to 200), `DataPagination` is rendered under each recon `DataTable`, and "showing x-y of count" is shown. No API change. Test: MSW-style mocked 120-row response gives 3 pages and the count label matches.
2. **`page_size=500` silently capped at 200.** `useMasterOptions.ts:91` (500) and `LicensePlanningWorkspace.tsx:128` (500) exceed `max_page_size` 200 (00 §7.2 #12), so rows past 200 are dropped without notice. Fix: a `fetchAllPages(endpoint, params, signal)` helper in `src/api/list.ts` that requests `page_size=200` and follows `next` up to a hard limit, with a dev warning when the limit is hit. Apply it to the 500 call sites, and to the 200 call sites when `count > 200` (`useMasterOptions.ts:68`, `useItemReportFilters.ts:61`, `allotmentApi.ts:80`, `AllotmentAction.tsx:273`). No API change. Test: mocked 450-row source returns 450 options, and 3 requests were made.

## 4. Server-state standard

- **TanStack Query for all server state.** The 48 files on `useEffect`+axios (00 §5) migrate module by module in §5. `useEffect` fetching is banned in new and migrated code (ratchet counts `useEffect` files that import `api/axios`).
- **Query-key factory**, one per resource, in `src/api/keys.ts` (extends the 4 existing factories, 00 §5):
  ```ts
  export const qk = {
    licenses: { all: ['licenses'] as const, list: (p: ListParams) => [...qk.licenses.all, 'list', p] as const, detail: (id: Id) => [...qk.licenses.all, 'detail', id] as const, overview: (id: Id, part: string) => [...qk.licenses.all, 'detail', id, 'overview', part] as const },
    // boes, allotments, trades, incentiveLicenses, masters(entity), recon (reuse reconKeys), ledger, planning, reports, users, tasks
  };
  ```
  Shape: `[resource, 'list'|'detail', ...]`. `['entity-list', entity, params]` (MasterList) moves to `qk[entity].list(params)`. A compatibility period keeps the old prefix invalidated as well, until every reader has moved. This fixes the dead `["licenses"]` key (`IndividualItemCifSwitch.tsx:35`) and the duplicate `license-balance-customs-ledger` declarations.
- **Mutations** use `useMutation` (form pages included: `useMasterFormSubmit`, TradeForm save, AllotmentAction create, which are imperative today, 00 §5). `onSuccess` invalidates `qk.<res>.all` for list and detail, plus related resources from a small documented table, e.g. allocation invalidates the allotment, the licence overview of affected licences, and recon summary. Optimistic updates only where they exist today (MasterList `:664-691`).
- **Cancellation:** every `queryFn` forwards `signal` (`({signal}) => api.list(params, signal)`). Fix `boeApi.fetchBOEList` (`boeApi.ts:13-16`), which has no signal. Note: passing `signal` disables axios GET dedup (`axios.js:58-60`), which is acceptable because Query dedupes.
- **Debounced search:** one `useDebouncedValue(value, 300)` in `hooks/` replaces the 3 debounce implementations (03 §6). The debounced value goes into the query key, and `placeholderData: keepPreviousData` stops the table flashing.
- **Defaults** (`api/queryClient.ts`): keep `staleTime` 30s and `retry` 1. Add `refetchOnWindowFocus: false` for lists (ERP users switch tabs often; documented as a behaviour change) and a `QueryCache.onError` that does nothing, because the axios interceptor already toasts (00 §8). Page-level error UI is the `InlineError` state of DataTable/EmptyState (05).

## 5. Phased implementation plan (owner's order)

Each phase ships on its own with the frontend gate (`scripts/dev/quality-gate.sh frontend`: lint, typecheck, vitest, build). Tests use vitest + RTL (skill `react-testing`). Playwright and axe use the existing `@axe-core/playwright` setup (`e2e/accessibilityHelpers.ts`). Screenshots: 768/1024/1440, light and dark. Owners follow the orchestration protocol: `frontend-engineer` implements, `a11y-architect` reviews a11y, and `code-reviewer` reviews every phase.

| # | Phase | Scope | Main files | Risk | Tests | Exit criteria |
|---|---|---|---|---|---|---|
| 1 | Design tokens + first-batch defects | §1 tokens. `ui/button`/`input`/`card`/`badge`/`switch` tokenised. Typography remap. Tone utilities. Focus recipe. Skip link. Ratchet test. **Plus §3.4 defects 1 and 2** | `theme/tabler.css`, `styles/tailwind.css`, `theme/tones.ts`, `components/ui/{button,input,card,badge,switch}.tsx`, `layout/AdminLayout.tsx`, `hooks/useReconTabQuery.ts`, `reconciliation/*Tab.tsx`, `api/list.ts`, `masters/hooks/useMasterOptions.ts`, `planning/LicensePlanningWorkspace.tsx` | **High visual blast radius**: button 55 importers, card 32, badge 27 (01 §1). Needs visual diff approval (§6.4) | RTL: button/badge variants render token classes. Ratchet test. Recon pagination and fetchAllPages tests. Playwright: screenshot baseline before and after in both themes. axe on login, dashboard, licence overview | approved visual diff. No raw palette in `ui/*`. Recon shows all rows. No request with `page_size>200` |
| 2 | DataTable | `components/data-table/` on `@tanstack/react-table` (needs approval) + `ui/table` | new `components/ui/table.tsx`, `components/data-table/*`. Pilot migration: license-overview tabs (AllotmentsTab, BoesTab, ItemsTab, which already share `SortableHeader`) and the 6 recon tabs (old `DataTable`) | Medium: recon and overview are core screens. Sorting must stay server-side where the server sorts | RTL: sort sets `aria-sort` and `ordering`, select-all/bulk, loading/empty/error, sticky header class. Playwright: overview tabs, recon. axe | old `components/DataTable.tsx` has 0 importers outside MasterList. `TableSkeletonLoader` deleted. Mobile thead rule removed |
| 3 | FilterEngine | 05 §2. Built on `filters/FilterPanel.tsx` + `ActiveFilters` | `components/filters/*`. Migrate `AllotmentFilters`, `ItemPivotFilters`, `ItemReportFilters` (03 §2 order) | Medium: filter param names must not change (backend filtersets) | RTL: param serialisation snapshot per migrated screen equals today's query string. Clear/reset/apply. Labels | 3 filter components migrated. `form-label` count falls. `DataFilter` deleted |
| 4 | Pagination | `useListQuery` + `DataPagination` restyle (05 §3). Adopt in the 11 files with local `page` state that have a UI need (03 §3) | `hooks/useListQuery.ts`, `components/DataPagination.tsx`, LicensesTable, TradesListView, IncentiveLicensesTable, AllotmentsTable, GenericMasterCards | Medium: URL format must stay backward-compatible | RTL: URL to params round-trip, filter change resets page, first/last. Playwright: deep link `?page=3` reload | one list contract. `hooks/usePagination.js` only kept if ItemReport client slicing still needs it |
| 5 | ModuleWorkspace | 05 §4 shell + `?tab=` helper, PageHeader compact variant, StatCard merge (03 §7) | `components/workspace/*`, `PageHeader.tsx`, `StatCard.tsx`, delete `license-overview/StatCard.tsx` after migration | Low-medium | RTL: tab in URL, unknown tab falls back, gated tab hidden, breadcrumb landmark. axe | used by licence overview with no URL change |
| 6 | Licences | Overview to ModuleWorkspace (+Ledger tab). LicensesTable/LedgerTab/BalanceTab tables to DataTable. MasterForm licence fields to the Form kit (licence branch only). `LicenseBalanceModal` restyle | `license-overview/*`, `masters/tables/{LicensesTable,LedgerTab,BalanceTab}.tsx`, `LicenseBalanceModal.tsx` | **High**: balance displays. Values must be identical (presentation only). `cif-balance-auditor` review of any displayed-figure change | RTL: rendered figures equal fixture values. Playwright: create/edit/overview flows, `?tab=` deep links. axe | no raw palette in these files. Existing overview URLs work |
| 7 | BOE | BOE edit as workspace (Details, Transfer letter). `BoeMergeModal` to Radix. Invoice inline edit kept | `MasterForm` BOE branch, `BOETransferLetter.tsx`, `TransferLetterForm.tsx` (12 hex), `masters/BoeMergeModal.tsx` | Medium: `ACCOUNT_ACCESS` invoice-only path | RTL: role matrix (manager / ACCOUNT_ACCESS / TL_GENERATE). Playwright: BOE create, then transfer letter via both URLs | old TL route renders the tab |
| 8 | Allotments | workspace (Details, Allocate). AllotmentAction tables to DataTable. AllotmentFilters done in P3 | `AllotmentAction.tsx`, `masters/tables/AllotmentsTable.tsx` (`window.confirm` `:78`) | **High**: allocation writes. Mutations unchanged, only moved to `useMutation` + invalidation | RTL: allocate mutation invalidates allotment + overview keys. Playwright: allocate flow. axe | `/allotments/:id/allocate` unchanged |
| 9 | Allocations | allocation views outside the allotment page: available-licences table pagination (backend cap 100, hand-rolled) and the licence-side Allotments tab. No separate route exists (02 3.4) | `AllotmentAction` available-licences block, `license-overview/AllotmentsTab.tsx` | Medium | RTL: page_size clamped to 100 for this endpoint (exception in contract) | consistent table + pagination |
| 10 | Invoices (= Trades) | TradesListView to DataTable (grouped rows kept). TradeForm to Form kit (payments sub-table included). `window.confirm` `:63` replaced. Counterpart tab | `masters/TradesListView.tsx`, `TradeForm.tsx`, `masters/LinkTradeModal.tsx` | **High**: 1644-line form, `any`-heavy. Payment/line math must stay server-side or identical | RTL: TradeForm smoke extended for validation messages. Playwright: purchase/sale pair, link/unpair | 0 raw `<button>`/`<input>` in TradeForm |
| 11 | Accounting/Banking | **N/A as a module.** No accounting, banking, customer or supplier frontend exists (02 §1 matrix: no such routes). Accounting-relevant surfaces are covered elsewhere: `ACCOUNT_ACCESS` BOE invoice-number edit (P7), reconciliation (P12), trade payments inside TradeForm (P10). Customers/suppliers = `/masters/companies` (Masters, migrated with P4/P5 generic masters). Phase reduced to a check that these role paths still work | none new | Low | Playwright role check for `ACCOUNT_ACCESS` | confirmation only. Any new accounting UI would be a product decision (out of scope) |
| 12 | Reconciliation | panel tab to `?tab=`. Row actions keep navigating to trade/BOE edit (opening in place is deferred). LinkRecordModal on Form kit. `ConfirmDialog` replaced | `ReconciliationPanel.tsx`, `ReconciliationIssues.tsx`, `reconciliation/*` | Medium: write actions need trade AND BOE roles (02 3.4) | RTL per tab. Playwright: link/merge/note | tab deep links work |
| 13 | Planning | `/planning` workspace tabs (Rules, Licence plan). PlanningEditor local `StatusBadge`/`SummaryCard` to shared. `window.confirm` `:849` replaced. Tables to DataTable | `planning/*`, `components/planning/PlanningEditor.tsx` | Medium-high: plan save/preview flows | existing `PlanningEditor.reconciliation.test` stays green. RTL for confirm | 0 `window.confirm` repo-wide |
| 14 | Reports | report selector in header. ItemPivotReport (93 inline styles), ItemReportTable (49), SionNormReport (45 px) to DataTable `compact` + tokens. Report fetches to TanStack Query with signal. ItemReport keeps client slicing until a paginated endpoint exists (none today) | `pages/reports/**` | High visual: wide tables, sticky columns (existing e2e `item-pivot sticky`) | Playwright: existing item-pivot sticky spec, export buttons. axe | inline styles in reports < 10. All report URLs unchanged |

Dead-code removal (§6.3) can ship any time after Phase 1 as its own commit.

## 6. Approval items (human decision required)

### 6.1 New dependencies (CLAUDE.md §5: dependency additions need approval)
Sizes are approximate published min+gzip figures. Verify with the build output delta before merging.

| Package | Purpose | Approx gzip | Justification | Alternative if refused |
|---|---|---|---|---|
| `@tanstack/react-table` v8 | headless DataTable (sort, selection, visibility, sizing, server mode) | ~15 kB | replaces 79 hand-rolled tables and 2 generic ones with 0 sort/aria-sort support (03 §1). Same vendor as Query, headless so it fits shadcn | extract `SortableHeader`/`useSortedRows` (03 §1 fallback). Column visibility, resizing and selection get hand-built |
| `react-hook-form` | form state | ~10 kB | 9 hand-rolled forms, 5 `fieldErrors` copies (03 §4). Uncontrolled inputs help the 1137/1644-line forms | `useFieldErrors` hook + `FormField` (03 §4 fallback) |
| `zod` (v4) | schema validation, typed form values | ~13 kB (smaller with `zod/mini`) | one schema gives both TS types and client validation. Server stays authoritative | hand validators in `utils/formValidation.js` |
| `@hookform/resolvers` | RHF + zod bridge | ~1 kB (zod resolver only, tree-shaken) | required glue | none needed if zod refused |
| `@tanstack/react-virtual` (optional) | row virtualisation | ~4 kB | only if `LicenseLedger` card list or report tables stay unpaginated and slow (00 §10.2). Defer until measured | pagination |

These load only in lazy route chunks, not in the eager shell (00 §10.1, eager about 197 kB gzip). Removing react-select later (§6.2, 83 kB raw / 29 kB gzip chunk) more than offsets them.

### 6.2 Removing duplicate libraries (later, after Phase 14)
- `react-select` (19 files): replace with a Radix Popover + `cmdk` combobox. Both are already installed (03 §6).
- `react-datepicker` (3 files): replace with native date inputs styled by `ui/input` (03 §12).
- Each removal is its own approved PR with a parity checklist (recents, FK cache, creatable).

### 6.3 Dead code to delete (01 §7, 03 §16; 0 importers)
`components/AllotmentFormModal.tsx` (524), `FormField.tsx` (203; delete it or reuse its aria pattern in the Form kit), `DataFilter.tsx` (68), `Timeline.tsx` (48; ActivityTimeline replaces it, 05), `GlobalErrorBoundary.tsx` (15), `item-async-select.tsx` (30), `motion/PageTransition.tsx` (24), `layout/Sidebar.tsx` (155), `components/ui/index.js`, `hooks/useToast.js`, `hooks/useModal.js` (barrel-only), and `LoadingFallback` `TableSkeletonLoader`/`FormSkeletonLoader`/`InlineLoader` (0 external users). About 1,070+ lines. Deleting files prompts (`rm` is `ask`).

### 6.4 Button / Input / Card token change (visual diff needed)
`ui/button.tsx:11-22` uses raw palette (`bg-blue-600`, `bg-white`, `border-slate-300`), so it ignores dark mode (01 §1). The change: tokens (`bg-primary`, `bg-card`, `border-border`), 1px outline border, `rounded-md`, heights `h-9`/`h-8`, `motion-safe` press scale. Card goes to `rounded-lg` with no shadow, and Input to `h-9 rounded-md`. Every screen is affected. Approval is based on a Playwright before/after screenshot set (5 key screens × 3 widths × 2 themes).

### 6.5 Owner decisions (flagged in 02, not assumed)
- Which user-admin UI and guard prevails (`/settings` superuser modal vs `/admin/users` USER_MANAGER), from 02 3.12.
- Whether `/reconciliation-issues` (wider read roles) folds into `/reconciliation`. This changes who sees the panel.
- `refetchOnWindowFocus: false` and dropping page size 10 are small visible behaviour changes.
- `tsconfig` `strict:false` (00 §1) contradicts `.claude/rules/frontend.md` "strict via tsconfig". New `components/data-table`, `filters`, `workspace` and `form` code should compile under `strict`. Flipping the global flag is a separate decision.
