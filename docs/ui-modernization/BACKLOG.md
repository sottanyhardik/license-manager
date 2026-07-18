# Backlog

Improvements identified but deferred. Review before each session.

Format: `Priority | Area | Description | Why deferred`

---

## P0 — High impact, address soon

| # | Area | Description | Notes |
|---|------|-------------|-------|
| B001 | Tables | Install `@tanstack/react-table` and migrate `DataTable.tsx` | High risk — affects every list page; needs dedicated session |
| B002 | Forms | Install `react-hook-form` + `zod`; migrate `MasterForm.tsx` | 1954-line file; highest complexity in codebase |
| B003 | Components | `LicenseBalanceModal.tsx` — 25+ inline styles with CSS variables | Large modal used in license detail views |
| B004 | Accessibility | Add `scope="col"` to all `<th>` in DataTable, AccordionTable, LicenseLedger | Quick win, high a11y value — ✅ Partially done: Settings + MdsStatusCard in Session-3; DataTable/AccordionTable/LicenseLedger still pending |

## P1 — Medium impact

| # | Area | Description | Notes |
|---|------|-------------|-------|
| B005 | Components | `HybridSelect.tsx` — react-select wrapper; review styling against our tokens | react-select menus use Bootstrap-era class names |
| B006 | Components | `TaskFAB.tsx` — inline styles with legacy tokens (`--surface-raised`, `--elevation-2`) | Minor, visible on every page |
| B007 | Components | `LicenseLedger.tsx` — 50+ remaining inline styles in `LicenseWiseLedger` sub-component | Complex financial table rendering |
| B008 | Forms | `AllotmentAction.tsx` — 13+ filter fields in `useState`; consider `useReducer` | Fragile form state |
| B009 | A11y | `ActivityLog.tsx` — table `<th>` elements missing `scope` attributes | WCAG 1.3.1 |
| B010 | Performance | `MasterList.tsx` — virtual scrolling for large entity lists (> 200 rows) | TanStack Virtual |

## P2 — Nice to have

| # | Area | Description | Notes |
|---|------|-------------|-------|
| B011 | DX | Install `react-hotkeys-hook`; centralize keyboard shortcut registration | Currently scattered useEffect handlers |
| B012 | UX | `PasswordReset.tsx` — add countdown before auto-redirect to login on success | Minor UX polish |
| B013 | DX | Delete `components/ui/index.js` barrel (zero callers) | Phase 4 cleanup |
| B014 | DX | Delete or review `components/primitives/` legacy components | After MasterList migration |
| B015 | Charts | Add more recharts visualizations to Dashboard (e.g. license utilization donut) | Design approval needed |
| B016 | Animation | `TaskFAB.tsx` expand-on-hover label could use Framer Motion for smoother transition | Currently CSS transition + `maxWidth` hack |
| B017 | A11y | `ErrorBoundary.tsx` / `GlobalErrorBoundary.tsx` — review ARIA and fallback UI | Unknown state |
| B018 | Components | `TransferLetterModal.tsx`, `TransferLetterForm.tsx` — review for Bootstrap patterns | Not yet inspected |
| B019 | Components | `OwnershipDetailsModal.tsx` — review for Bootstrap patterns | Not yet inspected |
| B020 | Tables | `AccordionTable.tsx` — consider `colSpan` accessibility attributes on nested tables | Minor |

## P3 — Future exploration

| # | Area | Description | Notes |
|---|------|-------------|-------|
| B021 | React Day Picker | Replace `react-datepicker` with React Day Picker (more accessible, shadcn integration) | Works fine today, risky migration |
| B022 | React Virtuoso | Virtual scrolling for ledger detail views with many rows | Performance measurement first |
| B023 | React Hook Form | Migrate `TradeForm.tsx` (complex nested form) | After RHF is proven on simpler forms |
| B024 | Feature | Add keyboard shortcut overlay (show all ⌘K commands with ? key) | Product feature, not refactor |
