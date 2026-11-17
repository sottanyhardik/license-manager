# Shared UI standards (as implemented in Licence)

Licence is the UI reference (DR-BOE-2). This file records what the Licence code does today. Paths are under `frontend/src/`. `MasterList` line refs are at base `9fc44ad3`; WS1 is generalising these branches to `COMPACT_REGISTER = new Set(["licenses","bill-of-entries"])`, so *verify after WS1*. Token and pattern detail lives in `docs/ui-modernization/DESIGN_SYSTEM.md`; it is not repeated here.

## Tokens

| Rule | Source |
|---|---|
| Tokens are defined in `theme/tabler.css` (`--tb-*`) and bridged in `styles/tailwind.css` | DESIGN_SYSTEM §Token system |
| Use semantic Tailwind classes only (`text-foreground`, `text-muted-foreground`, `bg-card`, `bg-muted`, `border-border`). No raw hex. No Bootstrap classes. | DESIGN_SYSTEM §Semantic |
| One tone vocabulary: `primary, success, warning, danger, info, neutral` via `TONE_MAP` | `components/shared/tone.ts` |
| Outline buttons on cards use `OUTLINE_TOKENS` | `lib/display.ts:9` |
| Numbers use `tabular-nums`; counts use `toLocaleString("en-IN")`; CIF `$` uses the en-US format on the licence workspace (owner-approved) | `MasterList.tsx:1009`; DECISION_REGISTER §Approved |

## Register (list) layout — compact register

| Element | Licence implementation |
|---|---|
| Page header | No `PageHeader` for the compact register (`MasterList.tsx:952`). The title sits inside the filter toolbar. |
| Toolbar start | Breadcrumb `Home / {title}` (`text-xs text-muted-foreground`), one `h1` (`text-lg font-semibold leading-tight tracking-tight`), record count (`text-xs tabular-nums`) (`:1001-1011`) |
| Toolbar end | `headerActions` (export buttons, Add New). Secondary actions go in the shared `ActionMenu` (WS1). |
| Filter | `AdvancedFilter` with `collapsible: true` and `layout: 'grid'` (`:998-1013`) |
| Surface | `surface-card mt-3 overflow-hidden border-border/70 shadow-sm`, inner padding `p-2 sm:p-3` (`:1025-1026`) |
| List | `<ul className="flex min-w-0 flex-col gap-1.5" aria-label="Licenses">` of `LicenceCard` (`pages/masters/tables/LicensesTable.tsx:76`) |
| Row density | Card header `px-3 py-2 md:px-4`, `gap-x-4 gap-y-1`; container `rounded-lg border bg-card`; expanded state `border-ring/40` + `bg-muted/40` (`features/licenses/LicenceCard.tsx:132-141`) |
| Row actions | `ActionMenu` built from `buildLicenceActionItems` (`features/licenses/licenceActionItems.ts:29`) via `useLicenceRowActions` (`useLicenceRowActions.ts:35`) |

## Record workspace tabs

| Rule | Source |
|---|---|
| Use `DetailTabs` with a `recordKey` and an `ariaLabel` | `features/licenses/LicenseRecordWorkspace.tsx:99-106` |
| Tablist scrolls and does not wrap: `min-w-0 [&_[role=tablist]]:flex-nowrap [&_[role=tablist]]:overflow-x-auto [&_[role=tab]]:shrink-0` | `LicenseRecordWorkspace.tsx:104` (WS3 applies it to BOE) |
| Tabs can be hidden by role or state (`visible: canWrite`) | `LicenseRecordWorkspace.tsx:93-94` |
| Licence opens on `overview`. BOE opens on `import-items` today (`BoeRecordWorkspace.tsx:40`). Changing that is an owner escalation. | — |
| Each tab fetches only its own endpoint | `features/*/__tests__` workspace tests |
| Overview groups content with `ModuleAccordion` (`persistKey`) | licence `tabs/OverviewTab.tsx` |

## States

| State | Component | Usage |
|---|---|---|
| Loading | `LoadingState variant="skeleton-rows"` (has `role="status"` and `aria-label`) | tabs, lists |
| Empty | `EmptyState size="inline"` in tabs; `size="page"` for empty registers (`LicensesTable.tsx:72`) | — |
| Error | `InlineError error onRetry title` | tabs |
| Loading + error + data | `QueryBoundary` (WS3) / `DetailQueryBoundary` | detail-backed tabs |
| Destructive confirm | `confirmDangerousAction` (`hooks/useConfirmDialog.tsx:112`). Do not use `ActionMenu` `item.confirm` (the provider is not mounted). | — |
| Field/value blocks | `FieldGrid` with `FieldSpec[]` | overview and detail tabs |

## Accessibility (from DESIGN_SYSTEM and Licence)

- Use `aria-label` on lists and articles and on icon-only buttons (for example `Open License Copy PDF for {n}`).
- Mark decorative icons with `aria-hidden`.
- Keyboard: the card chevron is a button with `aria-expanded`.
- Inline inputs need an `aria-label` (WS2 applies this to the BOE invoice editor).
- Toolbar actions whose text is `hidden sm:inline` must carry `aria-label`/`title` (MasterList Add New fixed this session; axe `link-name`).
- Contrast is enforced by `frontend/e2e/boe-workflow.spec.ts` (axe serious/critical at 390/768/1440px).

## Design-token rules fixed this session

| Rule | Where | Why |
|---|---|---|
| `<Button asChild><Link>` primary buttons keep white text: `a[class~="text-white"]` | `frontend/src/styles/tailwind.css` | The unlayered `a[class*="text-"] { color: inherit }` reset beat the layered `text-white` utility, so every register's Add New rendered dark text on blue (3:1). |
| Card stat labels use `--tb-text-secondary` (same as Licence `text-muted-foreground`) | `frontend/src/theme/tabler.css` `.entity-card-stat-label` | `--tb-text-tertiary` was 3.6:1 on white (fails AA) and diverged from the Licence label token. Affects BOE, allotment and trade cards. |
| Record-detail amounts keep backend scale (INR to paise, unit price 0.001); compact cards may round | `features/bill-of-entry/format.ts` `fmtInrExact` | Detail views must not hide money precision. |
