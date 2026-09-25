# UI Consistency Hotfix Work Queue

**Hotfix Branch:** `hotfix/ui-consistency-2026-09-25`  
**Master Baseline:** `6cc8c98f`  
**Design System Version:** v2.0 (Tabler + shadcn/ui unified)  
**Status:** Ready for implementation  
**Last Updated:** 2026-09-25

---

## Executive Summary

This work queue defines the component creation and page refactoring tasks needed to consolidate the License Manager UI into a unified design system. All tasks conform to the design tokens and component specifications documented in `/frontend/DESIGN_TOKENS.md` and `/frontend/COMPONENT_SPECS.md`.

The system is now **complete and validated**. All spacing, color, typography, shadow, radius, and control-sizing values have been documented with exact pixel values and CSS variable mappings.

---

## Phase 1: New Component Creation

### P1.1 FilterPanel Component

**Status:** ⏳ PENDING  
**Priority:** HIGH  
**Complexity:** Medium  
**Agent:** frontend-engineer  

**Objective:**
Create a reusable FilterPanel component that provides consistent filter UI across all data-heavy pages (Licenses, Allotments, Bill of Entries, Reports).

**Specification:**
- Collapsible header with icon, label, and active filter count badge
- Grid/flex layout (horizontal on desktop, vertical on mobile)
- Standard padding: `sp-4` (16px)
- Border radius: `r-lg` (10px)
- Shadow: `shadow-1`
- Responsive: Single column on mobile, multi-column on desktop

**Files to Create:**
- `/frontend/src/components/FilterPanel.tsx`
- `/frontend/src/components/FilterPanel.test.tsx`

**Files to Reference:**
- `/frontend/src/components/PageHeader.tsx` (as pattern example)
- `/frontend/src/pages/ItemPivotFilters.tsx` (existing filter example)

**Acceptance Criteria:**
1. Component accepts children (filter controls) and onClearFilters callback
2. Collapsible behavior with smooth transition
3. Badge shows active filter count
4. Passes accessibility audit (AA contrast, focus rings)
5. Responsive on mobile/tablet/desktop
6. Respects `prefers-reduced-motion`

---

### P1.2 EmptyState Component Enhancement

**Status:** ⏳ PENDING  
**Priority:** MEDIUM  
**Complexity:** Low  
**Agent:** frontend-engineer  

**Objective:**
Enhance the existing `EmptyState` component to fully conform to design spec (currently exists but may need refinement).

**Specification:**
- Min height: 96px
- Padding: 16px
- Icon size: 32px
- Icon color: `text-muted-foreground`
- Title: `text-sm font-semibold`
- Description: `text-xs text-muted-foreground`
- Optional action button area (right-aligned or centered)

**Files to Modify:**
- `/frontend/src/components/EmptyState.tsx`

**Acceptance Criteria:**
1. Meets sizing spec exactly
2. Title + description hierarchy clear
3. Action buttons properly spaced
4. Works in Card, Section, and inline contexts
5. Responsive and accessible

---

### P1.3 Confirmation Dialog Component

**Status:** ⏳ PENDING  
**Priority:** MEDIUM  
**Complexity:** Medium  
**Agent:** frontend-engineer  

**Objective:**
Create a specialized ConfirmDialog component (wrapper around shadcn Dialog) with consistent button ordering and spacing for destructive/confirmation actions.

**Specification:**
- Default: Outline "Cancel" + solid "Confirm" buttons
- Destructive: Outline "Cancel" + destructive "Delete"/"Confirm" buttons
- Icon (warning/check) in header for destructive actions
- Footer padding: `sp-4` (16px)
- Button gap: `sp-3` (12px)

**Files to Create:**
- `/frontend/src/components/ConfirmDialog.tsx` (or enhance existing if present)

**Files to Reference:**
- `/frontend/src/components/ui/dialog.tsx`
- `/frontend/src/pages/LicenseLedger.tsx` (for usage patterns)

**Acceptance Criteria:**
1. Configurable title, description, button labels
2. Proper button ordering (Cancel left, Action right)
3. Keyboard: Escape closes, Enter confirms on focus
4. Accessibility: Focus trap, ARIA labels
5. Works with both async and sync actions

---

## Phase 2: Page Refactoring — Major Pages

Pages in this section are heavily used and must be refactored to use the new unified component system.

### P2.1 Dashboard Page

**Status:** ⏳ PENDING  
**Priority:** HIGH  
**Complexity:** Medium  
**Agent:** frontend-engineer  

**Objective:**
Audit Dashboard.tsx and refactor spacing, cards, and typography to conform to design tokens and use unified component patterns.

**Current Issues Identified:**
- PageHeader styling may be inconsistent with spec
- StatCard padding/gap might not conform to spacing scale
- Card gaps in grid may be ad-hoc
- Table headers may have non-standard padding

**Files to Modify:**
- `/frontend/src/pages/Dashboard.tsx`

**Files to Reference:**
- `/frontend/DESIGN_TOKENS.md` (spacing, typography)
- `/frontend/COMPONENT_SPECS.md` (PageHeader, StatCard, Card)

**Specific Audit Tasks:**
1. Verify PageHeader uses correct sticky positioning and margin
2. Check StatCard uses design token colors for tone variants
3. Ensure card padding: `CardHeader px-4 py-3`, `CardContent p-4`
4. Verify table header padding: 12px, text size 11px
5. Check grid gaps use spacing scale (gap-2.5 = 10px, not standard)

**Acceptance Criteria:**
1. No hardcoded pixel values in styles
2. All colors use semantic tokens from TONE_MAP
3. All spacing uses scale (sp-1 through sp-8)
4. Tables conform to spec (sticky headers, row height, borders)
5. Responsive: tested on mobile/tablet/desktop
6. Dark mode: no visual regressions

---

### P2.2 LicenseLedger Page

**Status:** ⏳ PENDING  
**Priority:** HIGH  
**Complexity:** Medium  
**Agent:** frontend-engineer  

**Objective:**
Refactor LicenseLedger.tsx to use PageHeader, unified table styling, and consistent card/section layouts.

**Current Issues Identified:**
- Custom table styles may not conform to spacing scale
- Filter section styling may be ad-hoc
- Section titles may use inconsistent typography

**Files to Modify:**
- `/frontend/src/pages/LicenseLedger.tsx`

**Sub-Components to Create/Refactor:**
- Ensure `TransactionLedger` uses standard table styling
- Use PageHeader for page title/actions
- Refactor filter area to use new FilterPanel if needed

**Specific Audit Tasks:**
1. Check license header rows (bg-primary px-3 py-2) — standardize to design tokens
2. Verify table padding: 8px on th/td (xs content), 12px (standard)
3. Ensure card nesting uses consistent border colors
4. Verify section gaps use spacing scale

**Acceptance Criteria:**
1. PageHeader present and correctly styled
2. Table styling conforms to spec (header, body, row states)
3. All spacing uses scale
4. Responsive mobile layout uses card-based design
5. Passing accessibility audit

---

### P2.3 ItemPivotReport Page

**Status:** ⏳ PENDING (RECENT AUDIT COMPLETED)  
**Priority:** HIGH  
**Complexity:** High (complex pivot table structure)  
**Agent:** frontend-engineer  

**Objective:**
Ensure ItemPivotReport.tsx fully conforms to design tokens and uses unified component patterns. This is a complex pivot table — special care needed for frozen columns, scroll performance, and responsive behavior.

**Current Issues Identified (from recent visual audit):**
- Filter panel styling may not conform to spec
- Card padding in flex containers may be non-standard
- Badge spacing may be ad-hoc
- Table header padding may be inconsistent

**Files to Modify:**
- `/frontend/src/pages/reports/ItemPivotReport.tsx`

**Sub-Components:**
- `/frontend/src/pages/reports/ItemPivotFilters.tsx` (filter UI)
- Ensure NormCardGrid uses standard card styling

**Specific Audit Tasks:**
1. Verify frozen column offsets use dynamic measurement (already in place)
2. Check card header padding in filter area: `px-4 py-3` or `px-3 py-2`?
3. Ensure badge colors use PURCHASE_STATUS_PALETTE from tokens.js
4. Verify table cell padding: standard or compact?
5. Check responsive behavior on mobile (horizontal scroll, frozen columns)

**Acceptance Criteria:**
1. Filter area uses FilterPanel or consistent styling
2. Card padding standardized across all interior cards
3. All badges use PURCHASE_STATUS_PALETTE
4. Table spacing conforms to spec
5. Responsive: frozen columns work on mobile
6. Passing accessibility audit (focus visible on frozen columns)

---

### P2.4 Licenses List Page (if exists)

**Status:** ⏳ PENDING  
**Priority:** HIGH  
**Complexity:** Medium  
**Agent:** frontend-engineer  

**Objective:**
Refactor the licenses list/grid page to use unified component patterns.

**Files to Modify:**
- TBD (search for main licenses list page — may be LicenseLedger or separate)

**Note:** Need to confirm which page is the main "Licenses" view.

---

### P2.5 Allotments Page

**Status:** ⏳ PENDING  
**Priority:** MEDIUM  
**Complexity:** Medium  
**Agent:** frontend-engineer  

**Objective:**
Audit and refactor allotments page to use unified spacing, cards, and typography.

**Files to Modify:**
- `/frontend/src/pages/AllotmentAction.tsx` (or similar)

**Specific Audit Tasks:**
1. Verify PageHeader present
2. Check table spacing (header, row padding, borders)
3. Ensure filter area uses consistent styling
4. Verify card padding

**Acceptance Criteria:**
1. Conforms to design token spec
2. Responsive on mobile/tablet/desktop
3. Dark mode working

---

## Phase 3: Report Pages

Pages under `/frontend/src/pages/reports/` must be audited for spacing and typography consistency.

### P3.1 ActiveLicenses Report

**Status:** ⏳ PENDING  
**Priority:** MEDIUM  
**Complexity:** Low  
**Agent:** frontend-engineer  

**Objective:**
Audit and refactor spacing, cards, typography.

**Files to Modify:**
- `/frontend/src/pages/reports/ActiveLicenses.tsx`

---

### P3.2 ExpiringLicenses Report

**Status:** ⏳ PENDING  
**Priority:** MEDIUM  
**Complexity:** Low  
**Agent:** frontend-engineer  

**Objective:**
Audit and refactor spacing, cards, typography.

**Files to Modify:**
- `/frontend/src/pages/reports/ExpiringLicenses.tsx`

---

### P3.3 ItemReport

**Status:** ⏳ PENDING  
**Priority:** MEDIUM  
**Complexity:** Medium  
**Agent:** frontend-engineer  

**Objective:**
Audit table styling, card padding, filter area.

**Files to Modify:**
- `/frontend/src/pages/reports/ItemReport.tsx`

---

### P3.4 LicensePurchaseProfitReport

**Status:** ⏳ PENDING  
**Priority:** MEDIUM  
**Complexity:** Medium  
**Agent:** frontend-engineer  

**Objective:**
Audit and refactor.

**Files to Modify:**
- `/frontend/src/pages/reports/LicensePurchaseProfitReport.tsx`

---

### P3.5 SionE1 & Other Reports

**Status:** ⏳ PENDING  
**Priority:** LOW  
**Complexity:** Medium  
**Agent:** frontend-engineer  

**Objective:**
Audit all remaining reports under `/pages/reports/` for consistency.

---

## Phase 4: Component Library Audits

### P4.1 Core UI Component Audit

**Status:** ⏳ PENDING  
**Priority:** MEDIUM  
**Complexity:** Low  
**Agent:** frontend-engineer  

**Objective:**
Verify all shadcn/ui components conform to design token color/spacing/typography.

**Files to Audit:**
- `/frontend/src/components/ui/button.tsx` — Verify variants match spec
- `/frontend/src/components/ui/input.tsx` — Height, padding, border-radius
- `/frontend/src/components/ui/select.tsx` — Dropdown sizing
- `/frontend/src/components/ui/card.tsx` — Padding, border-radius
- `/frontend/src/components/ui/badge.tsx` — Sizing, padding, variants
- `/frontend/src/components/ui/dialog.tsx` — Modal sizing, padding

**Acceptance Criteria:**
1. All components use Tabler tokens (no hardcoded colors)
2. Sizing matches spec exactly
3. Focus-visible rings present
4. Dark mode working
5. No Bootstrap class fallbacks

---

### P4.2 Shared Component Audit

**Status:** ⏳ PENDING  
**Priority:** MEDIUM  
**Complexity:** Medium  
**Agent:** frontend-engineer  

**Objective:**
Audit all components in `/frontend/src/components/` (not in `ui/`) for consistency.

**Key Components to Audit:**
- `PageHeader.tsx` — Sticky positioning, margin, padding
- `StatCard.tsx` — Tone variants, icon sizing, layout
- `EmptyState.tsx` — Sizing, padding, icon
- `DataTable.tsx` — Row height, padding, sticky header
- `DateRangeFilter.tsx` — Input sizing, label spacing
- `DebouncedSearchInput.tsx` — Input sizing, label
- `Badge.tsx` (if separate from ui/badge.tsx)
- `ConfirmDialog.tsx` — Button spacing, footer padding

**Acceptance Criteria:**
1. All use design tokens
2. Spacing conforms to scale
3. Typography hierarchy correct
4. Responsive and accessible
5. Dark mode working

---

## Phase 5: Documentation & Validation

### P5.1 Design System Reference Document

**Status:** ✅ COMPLETED  
**Deliverable:** `/frontend/DESIGN_TOKENS.md`

Defines all tokens (spacing, radius, shadow, typography, color, z-index, motion, breakpoints) with exact pixel values and CSS variable mappings.

### P5.2 Component Specifications Document

**Status:** ✅ COMPLETED  
**Deliverable:** `/frontend/COMPONENT_SPECS.md`

Specifies sizing, spacing, typography, and states for 12 major component types.

### P5.3 Work Queue Document

**Status:** ✅ IN PROGRESS  
**Deliverable:** `/frontend/UI_AGENT_WORK_QUEUE.md` (this file)

Lists all refactoring tasks, their objectives, files affected, and acceptance criteria.

### P5.4 Code Quality Gates

**Status:** ⏳ PENDING  
**Agent:** qa-test-engineer

**Objective:**
Establish and run automated checks for design system compliance.

**Gates to Implement:**
1. Linting rule: No hardcoded hex colors in styles (must use token variables)
2. No inline pixel spacing (must use Tailwind scale or token variables)
3. No hardcoded shadow values (must use token variables)
4. TypeScript: All components properly typed
5. Accessibility: Automated a11y checks in CI (Axe, pa11y)

**Files to Create/Modify:**
- `.eslintrc` — Add rules for hardcoded colors/spacing
- `frontend/vitest.config.ts` — Ensure a11y checks in test suite
- CI configuration — Add accessibility scanning

---

## Implementation Roadmap

### Week 1: Component Creation & Major Page Refactoring

1. Create `FilterPanel` component (P1.1)
2. Enhance `EmptyState` (P1.2)
3. Create `ConfirmDialog` wrapper (P1.3)
4. Refactor `Dashboard` (P2.1)
5. Refactor `LicenseLedger` (P2.2)

### Week 2: Report Pages & Audits

6. Ensure `ItemPivotReport` conforms (P2.3)
7. Audit all report pages (P3.1–P3.5)
8. Refactor as needed

### Week 3: Component Audits & Validation

9. Audit core UI components (P4.1)
10. Audit shared components (P4.2)
11. Implement quality gates (P5.4)
12. Final validation & testing

### Deployment

- Merge to develop branch
- Tag as `v2.0` of design system
- Deploy to staging/production

---

## Task Template

Each agent should use this template when picking up a task:

```
# [Page/Component Name] Refactoring

## Specification
- [Link to DESIGN_TOKENS.md]
- [Link to COMPONENT_SPECS.md]

## Files
- [ ] File 1 (audit)
- [ ] File 2 (audit)
- [ ] File 3 (modify)

## Audit Checklist
- [ ] All spacing uses scale (sp-1 through sp-8)
- [ ] All colors use tokens (--tb-* or shadcn semantic vars)
- [ ] All radius values conform to spec
- [ ] All shadows use layered system
- [ ] Typography hierarchy correct
- [ ] Responsive: mobile/tablet/desktop
- [ ] Dark mode: no visual regressions
- [ ] Accessibility: AA contrast, focus-visible
- [ ] Reduced motion: respected

## Implementation
- [ ] Code changes complete
- [ ] Tests updated
- [ ] Visual diff reviewed
- [ ] Accessibility audit passed
- [ ] PR created

## Sign-Off
- [ ] Code review passed
- [ ] QA testing passed
- [ ] Ready to merge
```

---

## Success Criteria

The design system consolidation is considered **complete** when:

1. ✅ All design tokens documented with exact pixel values
2. ✅ All component specifications documented with sizing and spacing
3. ⏳ All major pages refactored to use unified components
4. ⏳ All component audits completed
5. ⏳ Quality gates implemented and passing
6. ⏳ 100% of pages pass accessibility audit (AA contrast, focus rings)
7. ⏳ Dark mode verified on all pages
8. ⏳ Responsive verified on mobile/tablet/desktop
9. ⏳ All PRs merged and deployed

---

## Notes for Agents

### Design Tokens Are the Source of Truth

- Never hardcode hex colors, pixel values, or shadows
- Always reference `--tb-*` CSS variables or Tailwind utilities
- When adding spacing, use `sp-1` through `sp-8` scale (4, 8, 12, 16, 20, 24, 32px)
- When adding shadows, use layered system (`shadow-0` through `shadow-overlay`)

### Color System

- Semantic tones (primary, success, danger, warning, info) use `TONE_MAP` in `theme/tokens.js`
- Don't add custom color palettes — extend TONE_MAP if needed
- Dark mode is automatic — no component-level dark variants needed

### Responsive Design

- Mobile-first approach: style for mobile, add Tailwind prefixes for larger screens
- Use `max-width: 768px` as mobile breakpoint in media queries
- Tables on mobile: switch to card-based vertical layout with `data-label` attributes

### Accessibility

- All interactive elements: `focus-visible` ring with `outline-offset: 2px`
- All text: minimum AA contrast ratio (4.5:1 for body, 3:1 for larger text)
- Color alone must not convey meaning — always add text/icon
- Touch targets: 44px minimum on mobile

### Performance

- Use `position: sticky` sparingly — can cause layout thrashing
- Table headers: `z-index: 1` (sticky header only), not higher
- Modal: `z-index: 1050` (modal layer)
- Dropdown: `z-index: 1000` (dropdown layer)

---

## Contact & Escalation

- **Questions about tokens?** See `/frontend/DESIGN_TOKENS.md`
- **Questions about components?** See `/frontend/COMPONENT_SPECS.md`
- **Blocked on implementation?** Escalate to `frontend-engineer` agent
- **Visual discrepancy?** Document in PR with screenshot + visual diff link

---

**Work Queue Status:** Ready for agent assignment  
**Last Updated:** 2026-09-25  
**Next Review:** After Phase 1 completion
