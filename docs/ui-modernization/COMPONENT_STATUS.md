# Component Status

Tracks shared components that affect multiple routes.
Update this file whenever a component is modified.

**Status:**
- `LEGACY` — Bootstrap/inline-style patterns present, needs work
- `IN_PROGRESS` — actively being modernized
- `MODERN` — uses shadcn/Tailwind, no Bootstrap dependencies
- `STABLE` — modern + well-tested, low risk

---

## Layout

| Component | File | Status | Last Updated | Notes |
|-----------|------|--------|--------------|-------|
| AdminLayout | `layout/AdminLayout.tsx` | MODERN | 2026-07-17 | Footer sticky, Tailwind, ARIA live region |
| TopNav | `components/TopNav.tsx` | MODERN | 2026-07-17 | ChevronDown animation, cmdk search |

---

## Navigation & Search

| Component | File | Status | Last Updated | Notes |
|-----------|------|--------|--------------|-------|
| CommandPalette | `components/CommandPalette.tsx` | STABLE | 2026-07-18 | **Migrated to cmdk v1** — removed 80 lines of manual keyboard/focus code |

---

## Page structure

| Component | File | Status | Last Updated | Notes |
|-----------|------|--------|--------------|-------|
| PageHeader | `components/PageHeader.tsx` | STABLE | 2026-07-17 | items-center, tracking-widest pretitle, shrink-0 actions |
| EmptyState | `components/EmptyState.tsx` | STABLE | 2026-07-17 | Added size prop (default/page), icon in bordered container |
| ErrorScreen | `components/ErrorScreen.tsx` | MODERN | 2026-07-17 | Used by 401/403/404 pages, Framer Motion |
| ErrorBoundary | `components/ErrorBoundary.tsx` | LEGACY | — | Needs review |
| GlobalErrorBoundary | `components/GlobalErrorBoundary.tsx` | LEGACY | — | Needs review |

---

## Data display

| Component | File | Status | Last Updated | Notes |
|-----------|------|--------|--------------|-------|
| DataTable | `components/DataTable.tsx` | MODERN | 2026-07-17 | Bootstrap toggle → accessible switch; skeleton → shadcn Skeleton; table-hover added; action buttons standardized |
| AccordionTable | `components/AccordionTable.tsx` | MODERN | 2026-07-18 | form-switch → accessible toggle |
| DataPagination | `components/DataPagination.tsx` | MODERN | 2026-07-17 | Clean Tailwind, WCAG pagination |
| StatCard | `components/StatCard.tsx` | STABLE | 2026-07-17 | **Removed border-l-[3px]**, gradient wash, ring hover |

---

## Feedback & state

| Component | File | Status | Last Updated | Notes |
|-----------|------|--------|--------------|-------|
| ConfirmDialog | `components/ConfirmDialog.tsx` | STABLE | 2026-07-17 | **Full rewrite** — Bootstrap icons → Lucide, inline styles → Tailwind, typed |
| LoadingFallback | `components/LoadingFallback.tsx` | STABLE | 2026-07-17 | All inline styles → Tailwind; .skeleton → shadcn Skeleton |

---

## Forms

| Component | File | Status | Last Updated | Notes |
|-----------|------|--------|--------------|-------|
| FormField | `components/FormField.tsx` | STABLE | 2026-07-18 | **Rewritten** — TW_INPUT string → shadcn Input/Textarea/Label; useId for a11y; typed interfaces |
| AdvancedFilter | `components/AdvancedFilter.tsx` | MODERN | 2026-07-17 | h6 → div, shadcn Card |
| DebouncedSearchInput | `components/DebouncedSearchInput.tsx` | MODERN | 2026-07-17 | Clean Tailwind |
| HybridSelect | `components/HybridSelect.tsx` | LEGACY | — | react-select wrapper, needs styling review |
| AsyncSelectField | `components/AsyncSelectField.tsx` | LEGACY | — | Needs review |
| DebouncedAsyncSelect | `components/DebouncedAsyncSelect.tsx` | LEGACY | — | Needs review |

---

## Tasks

| Component | File | Status | Last Updated | Notes |
|-----------|------|--------|--------------|-------|
| TaskFAB | `components/TaskFAB.tsx` | LEGACY | — | Inline styles with legacy tokens |

---

## Settings sub-components

| Component | File | Status | Last Updated | Notes |
|-----------|------|--------|--------------|-------|
| MdsStatusCard | `pages/settings/MdsStatusCard.tsx` | MODERN | 2026-07-18 | Bootstrap card/table → shadcn Card; raw button → Button ghost; inline styles → Tailwind; scope="col" added |
| TaskDrawer | `components/TaskDrawer.tsx` | MODERN | 2026-07-18 | Bootstrap badge classes → Tailwind; form-check-input → native; flex-grow-1 → flex-1 |

---

## Domain components

| Component | File | Status | Last Updated | Notes |
|-----------|------|--------|--------------|-------|
| LicenseBalanceModal | `components/LicenseBalanceModal.tsx` | LEGACY | — | 25+ inline styles with CSS variables |
| OwnershipDetailsModal | `components/OwnershipDetailsModal.tsx` | LEGACY | — | Needs review |
| TransferLetterModal | `components/TransferLetterModal.tsx` | LEGACY | — | Needs review |
| TransferLetterForm | `components/TransferLetterForm.tsx` | LEGACY | — | Needs review |
| AllotmentFormModal | `components/AllotmentFormModal.tsx` | MODERN | 2026-07-18 | text-danger → text-destructive |
| ConditionBadge | `components/ConditionBadge.tsx` | LEGACY | — | Inline styles, token-based colours — low priority (works correctly) |

---

## Primitives (legacy barrel — migration complete)

| Component | File | Status | Notes |
|-----------|------|--------|-------|
| EntityCard | `primitives/EntityCard.tsx` | LEGACY | Domain-specific, not a library duplicate — keep |
| DetailTable | `primitives/DetailTable.tsx` | LEGACY | Domain-specific, keep |
| Surface, IconChip, StatusBadge, etc. | `primitives/*.tsx` | LEGACY | Imported via `ui/index.js` barrel — barrel now has zero callers |
| `ui/index.js` barrel | `components/ui/index.js` | DEPRECATED | Zero callers remaining. Safe to delete in Phase 4. |

---

## shadcn/ui components (all STABLE)

`button`, `badge`, `card`, `checkbox`, `dialog`, `input`, `label`, `select`,
`separator`, `skeleton`, `sonner`, `switch`, `tabs`, `textarea`, `tooltip`

All properly typed, dark-mode aware, keyboard accessible.
