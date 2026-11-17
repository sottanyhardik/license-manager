# Generic component registry (frontend)

Paths are under `frontend/src/`. Consumer counts are non-test files that import the component, counted by grep on 2026-11-17 in the `boe-erp` worktree. WS1, WS2 and WS3 are editing files at the same time, so the counts may change. Specs: `docs/modernization/frontend-audit/05_REUSABLE_COMPONENT_SPEC.md`. Status list: `docs/ui-modernization/COMPONENT_STATUS.md`.

## 1. Existing generic components (verified)

| Component | File | Key props | Consumers |
|---|---|---|---|
| `ModuleWorkspace` (+ `WorkspaceSection`, `DataWorkspace`, `useWorkspaceTab`) | `components/workspace/ModuleWorkspace.tsx:88` | `title, breadcrumbs, meta, primaryAction, secondaryActions, tabs, defaultTab, kpis` | **0 in production** (only `workspace.test.tsx`) |
| `DetailTabs` | `components/workspace/DetailTabs.tsx:54` | `recordKey, tabs, value, onValueChange, className, ariaLabel` | 4: `LicenseRecordWorkspace`, `AllotmentRecordWorkspace`, `BoeRecordWorkspace`, `pages/masters/tables/AllotmentsTable` |
| `ModuleAccordion` | `components/workspace/ModuleAccordion.tsx:37` | `sections, persistKey, className` | 3: licence `OverviewTab`, licence `BoeAllotmentTab`, allotment `OverviewTab` |
| `StatusBadge` | `components/shared/StatusBadge.tsx:16` | `tone, label, appearance, icon, title` | 3 (all licence) |
| `EmptyState` | `components/shared/EmptyState.tsx:14` | `title, description, icon, action, size: inline\|page` | 5 |
| `LoadingState` | `components/shared/LoadingState.tsx:11` | `variant: skeleton-rows\|spinner\|page, rows, label` | 3 |
| `InlineError` | `components/shared/InlineError.tsx:12` | `error, onRetry, title` | 3 |
| `FieldGrid` | `components/shared/FieldGrid.tsx:11` | `record, fields: FieldSpec[]` | 5 (imported directly; not in the barrel) |
| `ActionMenu` | `components/shared/ActionMenu.tsx:36` | `items: ActionMenuItem[], label, trigger` | 2 at base (`LicenceCard`, `ModuleWorkspace`); `MasterList` gets it from WS1 |
| `ConfirmDialog` / `ConfirmProvider` / `useConfirm` | `components/shared/ConfirmDialog.tsx:25,91,121` | `ConfirmOptions` | **0. The provider is not mounted.** |
| `SearchInput`, `DateRangePicker`, `ActivityTimeline` | `components/shared/*` | — | 0 |
| `tone.ts` (`Tone`, `TONE_MAP`) | `components/shared/tone.ts` | 6 tones | Used by the shared components |
| shadcn primitives | `components/ui/*.tsx` | — | Stable (COMPONENT_STATUS §shadcn) |

## 2. Components that need refactoring

| Component | Issue | Plan |
|---|---|---|
| `features/allotment/DetailQueryBoundary.tsx` | Only works for allotment | It becomes a wrapper around the new `QueryBoundary` (WS3) |
| `features/bill-of-entry/BoeCardList.tsx` | Hand-rolled spinner and `.empty-state`, legacy `EntityCard`, actions defined inline | WS2: shared states and `boeCardActions.ts`. Card chrome is deferred to a UX decision. |
| `pages/masters/MasterList.tsx` | Register branches are licence-only | WS1: `COMPACT_REGISTER` set |
| `ActionMenu` `item.confirm` | Throws without `ConfirmProvider` | Use `confirmDangerousAction` until the provider is mounted (deferred) |

## 3. New shared components (WS3 — verified against code)

| Component | File | Purpose | Props | Consumers (per plan) |
|---|---|---|---|---|
| `LicenceCopiesSection` | `components/workspace/LicenceCopiesSection.tsx` (exported from `components/workspace/index.ts`) | Removes duplicate licence numbers from the rows and renders `<section aria-label="Licence copies">` with one outline button per licence (`openLicenseCopyPdf`). Shows `EmptyState` when there are none. The markup is moved verbatim from `features/allotment/tabs/DocumentsTab.tsx:19-51`. | `rows`, `emptyDescription` | allotment `DocumentsTab`, BOE `DocumentsTab` |
| `QueryBoundary<T>` | `components/shared/QueryBoundary.tsx` (exported from the barrel) | Generic pending / error-with-retry / data switch. Its body comes from `DetailQueryBoundary`. | query result, `children(data)`, loading `rows`/`label`, error `title` | `DetailQueryBoundary` (3 consumers kept), BOE `BoeDetailsTab`, `AllotmentMappingTab` `LinkedAllotment` |

## 4. Module-specific (keep in the feature)

| Component | File |
|---|---|
| `LicenceCard`, `LicenceFinancialSummary`, `useLicenceRowActions`, `licenceActionItems` | `features/licenses/` |
| `AllotmentRecordWorkspace`, `useAllotmentDetail`, `allotmentCardActions`, `tabs/ActionButtons` | `features/allotment/` |
| `BoeRecordWorkspace`, `BoeItemsTable`, `boeCardActions`, `format.ts`, tabs | `features/bill-of-entry/` |
| `EntityCard`, `DetailTable` | `components/primitives/`. LEGACY but kept (`COMPONENT_STATUS.md:110-111`). EntityCard consumers: 3 (`BoeCardList`, `AllotmentsTable`, `TradesListView`). |

## 5. Deprecated or duplicate pairs

| Pair | Legacy (consumers) | Target (consumers) | Notes |
|---|---|---|---|
| EmptyState | `components/EmptyState.tsx`, default export, `size: default\|page` (6: Settings, Dashboard, ActivityLog, UserList, LicenseLedger, AllotmentAction) | `components/shared/EmptyState.tsx`, `size: inline\|page` (5) | `DESIGN_SYSTEM.md` §Empty state still describes the legacy API |
| ConfirmDialog | `components/ConfirmDialog.tsx` (5 importers incl. `hooks/useConfirmDialog.tsx`; the hook is used by ReconciliationPanel, MasterList, and passed into DuplicateBoesTab as a prop) | `components/shared/ConfirmDialog.tsx` (0, not mounted) | Consolidation deferred (cross-app) |
| DataTable | `components/DataTable.tsx` (8: MasterList, ReconciliationIssues, 6 reconciliation tabs) | `components/data-table/DataTable.tsx` (0 production; 05 spec §1 target) | Consolidation deferred |
| StatCard | `components/StatCard.tsx` (5: Dashboard, ReconciliationIssues, ReconciliationPanel, LicenseLedgerDetail, LicensePurchaseProfitReport) | `pages/license-overview/StatCard.tsx` (1: `LicenseMetricsGrid`) | These are different APIs. Neither is the shared target yet. 05 spec §4 plans `kpis` via StatCards. |
| `ui/index.js` barrel | 0 | — | DEPRECATED (`COMPONENT_STATUS.md:113`) |
