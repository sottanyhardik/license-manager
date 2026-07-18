# Changelog

Append only. Most recent session at top.

---

## Session 3 — 2026-07-18

### Route: `/settings` — Settings.tsx + MdsStatusCard.tsx

**Settings.tsx** — full UI modernization

- Removed: all inline `style={}` props (40+ occurrences), Bootstrap `card`/`card-header`/`card-body` classes, `badge bg-success`/`badge bg-secondary`, custom 120-line inline-style modal, `window.confirm()` delete prompt
- Added: shadcn `Card`/`CardHeader`/`CardContent` for both cards; shadcn `Dialog`/`DialogContent`/`DialogHeader`/`DialogFooter`/`DialogTitle` replacing custom modal; `ConfirmDialog` for delete with `severity="danger"` replacing `window.confirm()`
- `SectionBox`: inline styles → pure Tailwind with `TONE_CLASSES` map; typed `SectionBoxProps` interface; left-border accent preserved via `border-l-[3px] border-l-{tone}` Tailwind utilities
- `RoleBadge`: new sub-component — replaces `getRoleBadgeProps` Bootstrap class return with shadcn `<Badge>` variants; preserves `ROLE_BADGE_STYLE` inline styles for custom-colour roles (TL_GENERATE, LEDGER_MANAGER, ACCOUNT_ACCESS); maps bootstrap color names → shadcn variants for standard roles
- `fmtDate`: typed `(val: string | null | undefined): string`
- All `UserRecord`, `FormData` state: fully typed TypeScript interfaces replacing `any`
- User avatar: inline styles → `from-primary to-primary/70` Tailwind gradient classes
- User count badge: inline `style={}` → `<Badge variant="secondary">`
- Status badges in table: `badge bg-success`/`badge bg-secondary` → `<Badge variant="success">` / `<Badge variant="secondary">`
- `EmptyState` component for zero-user state (replaces basic inline-styled `<td>` text)
- `<th scope="col">` added to all 7 table headers — fixes WCAG 1.3.1 (B004 partially addressed)
- Error handling: typed error catch instead of untyped `catch (err)`

**pages/settings/MdsStatusCard.tsx** — full UI modernization

- Removed: Bootstrap `card`/`card-header`/`card-body`, `table table-hover table-responsive` classes, raw `<button>` with inline styles, all 25+ inline `style={}` props
- Added: shadcn `Card`/`CardHeader`/`CardContent`; shadcn `Button variant="ghost" size="icon"` for refresh; `Button variant="outline" size="sm"` for retry
- Loading/error/disabled states: inline styles → Tailwind text-center/flex/gap utilities
- Base URL `<code>` element: inline styles → `rounded-md border border-border/60 bg-muted` Tailwind classes
- `<th scope="col">` added to all 3 table headers (WCAG 1.3.1)
- Refresh button spinner: `className` conditional → `cn("size-4", loading && "animate-spin")`

**Build results:** ✅ 0 TypeScript errors · 0 lint errors · 416ms build

### Routes: `/401`, `/403`, `*` (404) — No changes — FROZEN

All three are pure wrappers of `ErrorScreen` (already MODERN in Session-1):
- `pages/errors/Unauthorized.tsx` — 15 lines, clean, typed, Lucide icons
- `pages/Forbidden.tsx` — 15 lines, clean, typed, Lucide icons
- `pages/errors/NotFound.tsx` — 15 lines, clean, typed, Lucide icons

No modifications needed. Frozen directly.

### Route: `/profile` — Profile.tsx

- Avatar gradient: `style={{ background: "linear-gradient(...)" }}` → `bg-gradient-to-br from-primary to-primary/70` Tailwind
- Roles display: raw codes (e.g. `LICENSE_MANAGER`) → `ROLE_LABELS` human-readable names via `<Badge>` with `title={code}` tooltip; removed `font-mono` styling
- Error banner: added `role="alert"`, `type="button"` on dismiss, `aria-hidden` on icons, focus ring on dismiss button
- Success banner: added `role="status"`, dismiss button (parity with error banner), `type="button"`
- Account Details CardHeader: `flex-row items-center justify-between` override → inner div with explicit flex layout (avoids Tailwind v4 flex-col/flex-row cascade ambiguity)
- Assigned Roles CardHeader: removed stale indentation inconsistency

### Route: `/pdf-viewer` — PDFViewer.tsx

- `useState(null)` → `useState<string | null>(null)` for `pdfUrl` and `error` (TypeScript correctness)
- `catch (err)` → `catch (err: unknown)` with typed `axiosErr` cast; proper conditional for `err.message`
- Floating refresh FAB: raw `<button>` → shadcn `<Button>` (inherits focus ring, keyboard operability)

**Build results:** ✅ 0 TypeScript errors · 0 lint errors · 375ms build

### Routes: `/reports/parle/sion-*`, `/reports/expiring-licenses`, `/reports/active-licenses`, `/reports/download-license` — No changes — FROZEN

All 7 report routes reviewed and found production-ready:
- `SionE1/E5/E126/E132` — pure `SionNormReport` delegates (already modern)
- `ExpiringLicenses`, `ActiveLicenses` — pure `LicenseExportPanel` delegates (already modern)
- `DownloadLicense` — shadcn Card/Button/Input/Textarea/Badge, typed, aria-pressed toggles, `useId` accessibility

### Route: `/admin/activity-log` — ActivityLog.tsx

- `ACTION_META`: all CSS var `bg`/`color` string references → Tailwind `chipClass` strings
  (`bg-success/10 text-success`, `bg-destructive/10 text-destructive`, etc.)
- `fmtDate`: typed `(ts: string | null | undefined): string`
- State types: `ActivityLogEntry` interface; `FilterState` type; `useState<ActivityLogEntry[]>([])`;
  `useRef<AbortController | null>(null)` replacing untyped refs
- `handleFilter`: typed `(key: keyof FilterState, value: string)`
- `catch (err: unknown)` + typed cast for AbortError check
- Action summary chips: `aria-pressed`, `ring-2 ring-current ring-offset-1` for active state visual,
  `type="button"`, `cn()` class composition; removed inline `style={{ background, color }}`
- Clear filters: `type="button"`, `focus-visible:underline`
- User avatar: `style={{ background: "linear-gradient()" }}` → `bg-gradient-to-br from-primary to-primary/70`
- Error row highlight: `style={isError ? { background: ... } : {}}` → `cn("...", isError && "bg-destructive/5")`
- Action badge: inline styles → `cn(m.chipClass, ...)`
- Status code badge: template literal string → `cn()` conditional
- `th scope="col"` added to all 7 table headers (WCAG 1.3.1 — B004 further addressed)
- Empty state: custom div → `EmptyState` component with icon, title, description
- Refresh `cn()`: `size-4 ${loading ? "animate-spin" : ""}` → `cn("size-4", loading && "animate-spin")`
- Label for Action select: added `htmlFor="f-action"` + `id="f-action"` on `SelectTrigger`

**Build results:** ✅ 0 TypeScript errors · 0 lint errors · 412ms build

### Routes: `/admin/users`, `/admin/users/create`, `/admin/users/:id/edit`

**UserList.tsx:**
- `UserRecord` interface added (all API fields typed)
- `BOOTSTRAP_TO_BADGE` map added: Bootstrap color names → shadcn Badge variants
- `useState` typed: `UserRecord[]`, `UserRecord | null`
- `handleDelete` param typed: `(userId: number)`
- `catch (err: unknown)` in both catch blocks
- `getRoleBadgeProps` usage removed; role badges now use `ROLE_BADGE_STYLE`/`ROLE_BADGE_COLOR` with shadcn `<Badge>` or custom `<span>` for special roles
- Loading state: bare text div → 5-row skeleton table with matching columns
- Empty state: bare icon div → `EmptyState` component with Add User CTA
- `scope="col"` on all 5 `<th>` elements (WCAG 1.3.1)
- `EmptyState` and `Skeleton` imports added

**UserForm.tsx:**
- `UserFormData` type added covering all form fields
- `emptyForm` annotated as `const emptyForm: UserFormData`
- `availableRoles` state: `useState([])` → `useState<string[]>([])`
- `handleChange` typed: `React.ChangeEvent<HTMLInputElement>`
- `setFlag` typed: `(name: keyof UserFormData, checked: boolean)`
- `toggleRole` typed: `(code: string)`
- `handleSubmit` typed: `async (e: React.FormEvent)`
- `FieldError` typed: `({ name }: { name: string })`
- All 3 catch blocks: `catch (err: unknown)` with typed cast
- Role picker: template literal className → `cn()` with `border-primary/50 bg-primary/10` checked state
- `cn` import added from `@/lib/utils`

**Build results:** ✅ 0 TypeScript errors · 0 lint errors · 425ms build

### Route: `/bill-of-entries/:id/generate-transfer-letter` — BOETransferLetter.tsx

Already clean; minor type improvements:
- `Detail` component: typed `{ label: string; value: ReactNode }`
- `boe` state: `null` → `Record<string, any> | null`
- `error` state: typed `string`

### Route: `/licenses/create` and all MasterForm routes — MasterForm.tsx (32 inline styles)

- `cn` import added
- Template literals → `cn()` on DatePicker/file-input errorClass and tab button isActive
- `container-fluid` + `style={{ minHeight: '100vh', ... }}` → `min-h-screen bg-background` (×2)
- `h4 style={{ color: var(--tb-text) }}` → `className="text-foreground"`
- `ms-2` → `ml-2` on BOE number links; inline fontSize/fontWeight/color → Tailwind
- `text-muted` → `text-muted-foreground` (×2)
- `alert alert-danger` → Tailwind destructive alert with `role="alert"`
- `alert alert-info` → Tailwind info alert
- BOE copy section: `surface-card mb-4 style={{padding:16}}` → `rounded-md border bg-card p-4 shadow-sm`; all inner inline styles → Tailwind/cn()
- `form-label` + inline → `mb-1.5 block text-[12px] font-semibold text-muted-foreground`
- `text-danger` → `text-destructive` on required asterisk
- Error div: redundant inline style removed
- Help text: `form-text` + inline → Tailwind
- Section boxes: static CSS var properties → Tailwind (dynamic `section.color` border kept inline)
- "Other Fields" section box: all CSS vars → Tailwind
- Tab `<ul>`: `style={{ marginBottom: 0 }}` → `mb-0`
- Tab panel container: all CSS var inline styles → `rounded-b-xl border border-t-0 border-border/60 bg-card p-4`
- Inner flex spans: `display:inline-flex` inline style → Tailwind
- Dynamic `entityColor` styles preserved as inline (cannot be Tailwind)

**Build results:** ✅ 0 TypeScript errors · 0 lint errors · 437ms build

### Routes: All MasterList routes — MasterList.tsx (75 inline styles)

- `cn()` import added
- Root wrapper: inline `minHeight`/`background` → `min-h-screen bg-[--tb-body-bg]`
- Breadcrumb: inline styles → `text-inherit no-underline`; separator `mx-1.5 opacity-50`
- Surface card padding: `style={{ padding: '14px 16px' }}` → `p-3.5`
- 6 empty `style={{}}` on chip spans removed; template literals → `cn()`
- BOE inline-edit chip: input/save/cancel inline styles → Tailwind
- BOE detail table: color inline styles → `text-destructive` + `cn()`
- License card outer: multi-property `style={{ display, background, border, borderLeft, ... }}` → `cn()` with Tailwind for expired/planned/default states
- License card rows 1/2/3: all inline flex/grid divs → Tailwind (1.4fr grid kept inline — no Tailwind utility)
- License card action buttons (8): all inline styles → Tailwind + `cn()`
- Trade card: italic span + 9 detail divs → Tailwind
- Trade pair container: border/radius/shadow/header/badges → Tailwind + `cn()`
- 6 `window.confirm` → `confirmDangerousAction()` via existing `useConfirmDialog` hook
- Bootstrap `bi-arrow-repeat` icon → `RefreshCw` Lucide (already imported)

### Route: `/allotments/:id/allocate` — AllotmentAction.tsx (106 inline styles)

- `cn()`, `ConfirmDialog`, `EmptyState` imports added
- Bootstrap `card`/`card-header`/`card-body` → Tailwind `border border-border bg-card` pattern
- Bootstrap `pagination`/`page-item`/`page-link` → Tailwind `inline-flex h-8` buttons
- Bootstrap `placeholder`/`placeholder-glow` skeleton → `animate-pulse bg-muted` Tailwind
- ~100 of 106 inline styles removed via `cn()` + Tailwind: progress bar colors, stat grid, item card rows, serial/HS/condition badges, labels, confirm button gradient, outer wrapper, table cell whitespace, tfoot, pagination, success alert
- 2 inline styles intentionally kept: runtime pixel width and dynamic `%` progress
- `window.confirm` ×2 → `ConfirmDialog` with `deleteConfirm`/`copyConfirm` state
- `EmptyState` component for "No available license items found"
- `scope="col"` on all `<th>` elements (WCAG 1.3.1)
- All template literal classNames → `cn()`

**Build results:** ✅ 0 TypeScript errors · 0 lint errors · 513ms build

---

## Session 2 — 2026-07-18

### Modernization migrations

**CommandPalette → cmdk**
- `components/CommandPalette.tsx` — replaced 170-line custom implementation with cmdk v1
- Removed: manual keyboard nav, focus management, search filtering, ARIA boilerplate
- Retained: role-based command list, existing CSS classes, same API contract
- `theme/tabler.css` — added `[aria-selected="true"]` and `[data-cmdk-*]` selectors

**Dashboard → Recharts**
- `pages/Dashboard.tsx` — replaced custom BarRow CSS chart with recharts BarChart + ResponsiveContainer
- Added: tooltips, axis labels, responsive container, animated bars with brand colours
- Removed: BarRow component (~15 lines), maxBoe computed variable
- `package.json` — added recharts ^3.9.2

### Legacy barrel cleanup

**Settings.tsx, MasterList.tsx, AllotmentsTable.tsx** — migrated away from `components/ui/index.js` barrel
- Direct imports from `@/components/PageHeader`, `@/components/ui/button`, etc.
- `Settings.tsx` — fixed Skeleton variant mismatch, Button variant `"primary"` → default, `"outline-secondary"` → `"outline"`
- `MasterList.tsx`, `AllotmentsTable.tsx` — now import EntityCard/DetailTable from `primitives/` directly

### Bootstrap form control replacements

**AccordionTable.tsx** — form-check form-switch → custom accessible toggle (consistent with DataTable pattern)

**TaskDrawer.tsx** — form-check-input → native checkbox with Tailwind; `flex-grow-1` → `flex-1`

**Settings.tsx** — `form-check form-switch` active-user toggle → shadcn `Switch`; role checkbox → native `accent-primary`

### FormField rewrite

**`components/FormField.tsx`** — full rewrite
- Removed: `TW_INPUT` hardcoded class string
- Added: shadcn `Input`, `Textarea`, `Label` components; `useId` for accessible `htmlFor` linkage
- Added: `aria-required`, `aria-invalid`, `aria-describedby`; typed interfaces with `Omit<>` to prevent TS conflicts
- Added: `<p role="alert">` for error messages

### Bootstrap colour class eradication

All `text-danger` → `text-destructive`:
- `pages/TradeForm.tsx` (4 occurrences)
- `pages/TradeConfigCard.tsx` (2 occurrences)
- `pages/masters/MasterForm.tsx` (1 occurrence)
- `components/AllotmentFormModal.tsx` (2 occurrences)

`form-label` inline styles → Tailwind (`text-xs font-semibold text-muted-foreground`):
- `pages/TradeForm.tsx`
- `pages/TradeConfigCard.tsx`
- `pages/masters/MasterForm.tsx`

### TaskDrawer badge improvements

**`components/TaskDrawer.tsx`** — STATUS_BADGE and PRIORITY_BADGE
- Removed: Bootstrap `bg-warning text-dark`, `bg-info text-dark`, `bg-success`, `bg-secondary`, `bg-danger`, `bg-light text-dark border`
- Added: Tailwind semantic utilities with opacity modifiers (`bg-warning/15 text-warning border border-warning/25` etc.)
- Badge elements: replaced `badge {Bootstrap classes}` with `inline-flex items-center rounded-full` pattern

### PasswordReset fix

**`pages/auth/PasswordReset.tsx`** — inline gradient → `bg-gradient-to-br from-blue-700 to-blue-600`

### LicenseLedger improvements

**`pages/LicenseLedger.tsx`**
- `container-fluid` + inline bg → `min-h-screen` (Tailwind)
- `text-muted` → `text-muted-foreground`; `mb-0` → removed
- `h4` + inline color style → `text-foreground flex items-center gap-2`
- Duplicate `handleBulkExportPDF` + `handleBulkExportExcel` → shared `handleBulkExport(format)` (~25 lines deleted)

**Build results:** ✅ 0 TypeScript errors · 0 lint errors · 419ms build

---

## Session 1 — 2026-07-17

### Design system improvements

**`components/StatCard.tsx`** — removed dated `border-l-[3px]` left-border accent
- Added: subtle `before:` gradient wash from tone color, ring-on-hover system, `size-[18px]` icon
- Removed: `border-l-primary/60` and all tone accent variants

**`components/PageHeader.tsx`** — improved visual hierarchy
- `items-end` → `items-center`; pretitle `tracking-widest opacity-70`; `shrink-0` on actions

**`components/EmptyState.tsx`** — redesign
- Added: `size` prop (`"default"` | `"page"`); icon in bordered container; `strokeWidth={1.5}`

**`theme/tabler.css`** — two targeted fixes
- Active nav trigger: `box-shadow: inset 0 -2px 0 0 var(--tb-brand)` bottom indicator
- Container padding-bottom: `96px` → `32px` (footer is sticky, not fixed)

### Login page redesign

**`pages/Login.tsx`** — major visual improvements
- Left panel: grid texture overlay, "TRADE OPERATIONS PLATFORM" pill badge (emerald dot), centered content, SVG checkmark feature list, copyright footer
- Right panel: `--tb-body-bg` gray background, form in white card with shadow (Linear/Stripe pattern)

### Navigation improvements

**`components/TopNav.tsx`**
- ChevronDown rotates 180° on open (CSS transition-transform)
- Search button: inline styles → Tailwind `gap-1`/`ml-2` pattern

### DataTable improvements

**`components/DataTable.tsx`**
- Bootstrap `form-check`/`form-switch` → custom accessible toggle (native checkbox + `sr-only peer`)
- `Math.random()` skeleton widths → deterministic `SKELETON_WIDTHS` array
- `.skeleton` CSS class → shadcn `<Skeleton>` component
- Added `table-hover` class for row hover states
- Empty state: icon in bordered rounded container
- Inline edit pencil: `opacity-0 group-hover/cell:opacity-100` (hidden by default)
- Action buttons: `size-7` icon buttons with proper hover rings

### Layout & Footer

**`layout/AdminLayout.tsx`**
- Footer: `position: fixed` → `sticky bottom-0 bg-card/95 backdrop-blur-sm`
- Quick action buttons: `h-7` height, cleaner gap handling

### ConfirmDialog rewrite

**`components/ConfirmDialog.tsx`** — full rewrite
- ~190 lines of inline styles → Tailwind classes
- Bootstrap icons (exclamation-triangle-fill etc.) → Lucide (AlertTriangle, XOctagon, Info, CheckCircle)
- Footer: muted background `bg-muted/30`, typed `ConfirmDialogProps` interface
- Behavior preserved: focus trap, Escape/Enter, scroll lock

### LoadingFallback cleanup

**`components/LoadingFallback.tsx`**
- All inline styles → Tailwind utilities
- `.skeleton` divs → shadcn `<Skeleton>`
- FullPageLoader: `animate-pulse` on brand mark

### Legacy barrel migration (partial)

**`components/ui/index.js` barrel** — now has 0 callers (safe to delete in Phase 4)

**Build results:** ✅ 0 TypeScript errors · 0 lint errors · 338ms build
