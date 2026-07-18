# Architectural Decisions

Append only. Never delete entries. Most recent at top.

---

## 2026-07-18 — Migrate CommandPalette to cmdk

**Decision:** Replace 170-line custom command palette implementation with cmdk v1.

**Rationale:**
- cmdk was already in `package.json` but never imported
- Custom code manually managed: keyboard navigation, focus trapping, search filtering, ARIA roles
- cmdk handles all of this with better accessibility (used by Linear, Vercel, shadcn)
- Result: ~80 lines deleted, accessibility improved, zero new dependencies

**Tradeoffs:** None — same visual CSS classes retained, same command data, same role-based filtering.

**Files:** `components/CommandPalette.tsx`, `theme/tabler.css`

---

## 2026-07-18 — Install recharts for Dashboard charts

**Decision:** Add recharts ^3.9.2 and replace custom BarRow component with ResponsiveContainer + BarChart.

**Rationale:**
- BarRow was a custom CSS bar chart with text labels — no tooltip, no animation, not accessible
- recharts is the most widely adopted React charting library (2M+ weekly downloads)
- Adds tooltip, axis labels, responsive layout, proper data visualization
- Recharts uses CSS variables for colours — integrates cleanly with design tokens

**Tradeoffs:** +370KB vendor chunk (gzip: 108KB). Justified for a data-intensive enterprise app.

**Files:** `pages/Dashboard.tsx`, `package.json`

---

## 2026-07-17 — Use sticky footer instead of fixed footer

**Decision:** Changed AdminLayout footer from `position: fixed` to `sticky bottom-0`.

**Rationale:**
- Fixed footer overlays content and required `padding-bottom: 96px` on the main content area
- Sticky footer participates in document flow — no content occlusion
- Reduced main container padding-bottom from 96px → 32px

**Tradeoffs:** On very long pages, the footer scrolls with content rather than always being visible.
For a quick-action bar (New License, New Allotment, etc.), this is acceptable.

---

## 2026-07-17 — Retain EntityCard and DetailTable primitives

**Decision:** Do NOT replace EntityCard/DetailTable with a generic library component.

**Rationale:**
- These are domain-specific (expandable card with header chips, status badges, summary stats, action buttons, inline detail table)
- No mature library replicates this exact pattern
- They are used only in MasterList for BOE, Allotment, and Trade list views
- Replacing them would risk regressions in the most complex pages

**Resolution:** Direct-import from `primitives/` instead of via the legacy `ui/index.js` barrel.

---

## 2026-07-17 — Keep form-label CSS class

**Decision:** Do NOT wholesale replace all `form-label` usages with shadcn `Label`.

**Rationale:**
- `form-label` is defined in our own CSS (tabler.css, tailwind.css) — not Bootstrap
- It renders differently from shadcn `Label` (12px vs 14px, uppercase tracking vs none)
- Blanket replacement would cause visual regressions in dense forms
- Replace inline-style overrides with Tailwind; use shadcn Label in new code

---

## 2026-07-17 — text-success / text-warning are valid Tailwind utilities

**Decision:** `text-success` and `text-warning` classes should NOT be replaced.

**Rationale:**
- We defined `--color-success: var(--success)` and `--color-warning: var(--warning)` in `@theme inline`
- Tailwind v4 generates `text-success` and `text-warning` from these
- These are our design tokens, not Bootstrap's
- Only `text-danger` (→ `text-destructive`) and `text-dark`/`text-muted` (→ shadcn equivalents) needed replacement

---

## 2026-07-17 — Prioritize cmdk, recharts before React Hook Form / TanStack Table

**Decision:** Defer React Hook Form + Zod and TanStack Table migrations to future sessions.

**Rationale:**
- MasterForm is 1954 lines with deeply nested state; React Hook Form migration is high-risk
- DataTable is used on every entity list page; TanStack Table migration requires careful testing
- Both libraries are not yet in package.json
- cmdk (already installed) and recharts (small, additive) deliver higher ROI at lower risk

**Future sessions:** Add `@tanstack/react-table`, `react-hook-form`, `zod` when dedicated to those pages.
