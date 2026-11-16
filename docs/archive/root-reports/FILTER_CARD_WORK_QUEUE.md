# Filter & Card System Implementation Queue

**Hotfix Branch:** hotfix/ui-consistency-2026-09-25  
**Status:** AUDIT COMPLETE — READY FOR IMPLEMENTATION  
**Last Updated:** 2026-09-25  
**Audit Document:** See `FILTER_CARD_SYSTEM_AUDIT.md` for complete analysis

---

## QUEUE SUMMARY

**Total Work Items:** 8  
**Total Estimated Time:** 12–15 hours  
**Complexity:** MEDIUM  
**Blast Radius:** 15+ dependent files (filters), 40+ (cards)  
**Risk:** LOW-MEDIUM (styling + structure changes, no behavior changes to data flow)

---

## FILTER SYSTEM WORK ITEMS

### ITEM 1: Standardize AllotmentFilters Field Heights
**Status:** READY  
**File:** `frontend/src/pages/AllotmentFilters.tsx`  
**Type:** Component Refactor (Styling)  
**Effort:** 1 hour  
**Complexity:** LOW  

**Changes:**
- Update all input field heights from `h-8` (32px) → `h-9` (36px)
- Ensure consistent padding: `px-3 py-1` (12px H, 4px V)
- Verify label spacing: `mb-2` (8px below label)
- Test responsive behavior on sm/md/lg viewports

**Acceptance Criteria:**
- [ ] All 16 filter fields render at h-9 (36px) height
- [ ] Field alignment matches ItemPivotFilters (custom panel)
- [ ] Labels have 8px gap below
- [ ] Responsive layout still works (sm: 2 cols, xl: 4 cols)
- [ ] Form submission unchanged
- [ ] Passes lint, typecheck, and build

**Dependencies:** None  
**Blocks:** ITEM 2 (filter standardization baseline)

**Measurement Reference:**
```css
/* Current (wrong) */
.input { height: h-8; /* 32px */ }

/* Target (standardized) */
.input { height: h-9; /* 36px */ }

/* Label spacing */
label { margin-bottom: 0.5rem; /* 8px */ }
```

---

### ITEM 2: Enhance FilterPanel with Label Component
**Status:** READY  
**File:** `frontend/src/components/filters/FilterPanel.tsx`  
**Type:** Component Enhancement  
**Effort:** 1.5 hours  
**Complexity:** MEDIUM  

**Changes:**
1. Create internal `FilterLabel` component with:
   - Icon support (optional LucideIcon)
   - Bold font-weight option
   - Consistent mb-2 spacing
   - Flex layout for icon + text

2. Update FilterPanel exports:
   - Export `FilterLabel` alongside `FilterPanel`, `FilterGrid`, `FilterField`

3. Add inline documentation with measurement table

**Example Usage:**
```typescript
// Instead of:
<label className="form-label text-[11px]">License Number</label>

// Use:
<FilterLabel icon={FileText}>License Number</FilterLabel>
```

**Acceptance Criteria:**
- [ ] FilterLabel renders with optional icon
- [ ] Icon size is consistent (size-4)
- [ ] Font weight correct (normal or bold option)
- [ ] Spacing (mb-2) applied automatically
- [ ] AllotmentFilters updated to use FilterLabel
- [ ] ItemPivotFilters/ItemReportFilters compatible (optional enhancement)
- [ ] Passes lint, typecheck, and build

**Dependencies:** None  
**Blocks:** ITEM 3, ITEM 4

**Code Location:**
```
frontend/src/components/filters/FilterPanel.tsx
- Line 5: Add FilterLabel component
- Line 27: Export FilterLabel
```

---

### ITEM 3: Refactor LicenseLedger Filters into FilterPanel
**Status:** QUEUED  
**File:** `frontend/src/pages/LicenseLedger.tsx`  
**Type:** Component Extraction + Refactor  
**Effort:** 3-4 hours  
**Complexity:** MEDIUM-HIGH  

**Current State:**
- Filters scattered through page component
- No unified FilterPanel structure
- Mix of inline state management

**Changes:**
1. Extract filter UI into separate sub-component: `LicenseLedgerFilterPanel.tsx`
2. Implement FilterPanel + FilterGrid structure
3. Apply FilterLabel component to all fields
4. Standardize field heights (h-9) and spacing
5. Move filter state management to new component
6. Ensure filter state changes update URL params

**Files to Create:**
```
frontend/src/pages/components/LicenseLedgerFilterPanel.tsx
```

**Files to Update:**
```
frontend/src/pages/LicenseLedger.tsx (remove inline filter UI, import LicenseLedgerFilterPanel)
```

**Acceptance Criteria:**
- [ ] New filter panel component created
- [ ] All 12+ filter fields in FilterPanel structure
- [ ] Field heights consistent (h-9)
- [ ] Labels use FilterLabel component
- [ ] Filters still persist to URL params
- [ ] Active filter count displayed
- [ ] Clear filters button works
- [ ] Responsive behavior tested
- [ ] Passes lint, typecheck, and build

**Dependencies:** ITEM 2  
**Blocks:** ITEM 5 (documentation)

**Measurement Reference:**
```
Current structure: Inline scattered elements
Target structure: FilterPanel → FilterGrid → FilterField → Input/Select/AsyncSelect
```

---

### ITEM 4: Evaluate ItemPivot & ItemReport Filters for Migration/Standardization
**Status:** QUEUED  
**File:** `frontend/src/pages/reports/ItemPivotFilters.tsx`, `frontend/src/pages/reports/itemReport/ItemReportFilters.tsx`  
**Type:** Analysis + Component Enhancement  
**Effort:** 2-3 hours  
**Complexity:** MEDIUM  

**Analysis Questions:**
1. Can these migrate to FilterPanel + FilterGrid without losing functionality?
2. Is the active filters badge display (ItemPivotFilters) essential UX?
3. Do custom grid layouts (sm:col-span-2, lg:col-span-4) work with FilterPanel?
4. Should multi-row grid (3 rows) be standardized in FilterPanel?

**Decision Points:**
- **Option A:** Migrate both to FilterPanel + FilterLabel (if compatible)
- **Option B:** Standardize styling in-place (apply same padding/spacing as FilterPanel)
- **Option C:** Leave as custom (document reasoning)

**Acceptance Criteria:**
- [ ] Analysis document created (decision matrix)
- [ ] If migrating: filters work identically to original
- [ ] If standardizing in-place: spacing measurements aligned with FilterPanel
- [ ] Active filter badges preserved or marked for UX review
- [ ] Responsive behavior tested (sm, md, lg)
- [ ] Passes lint, typecheck, and build

**Dependencies:** ITEM 2  
**Blocks:** ITEM 5 (documentation)

**Analysis Scope:**
```
ItemPivotFilters:
  - Custom header (matches FilterPanel)
  - 6 main filter rows
  - Active filters badge (full-width alert)
  - Question: Can this badge move to FilterPanel status area?

ItemReportFilters:
  - Custom header (matches FilterPanel)
  - 3 rows of filters (different grouping)
  - Active filters inline (not badge)
  - Question: Can inline display work with FilterPanel?
```

---

### ITEM 5: Document Filter System Measurement Standards
**Status:** QUEUED  
**Type:** Documentation  
**Effort:** 1 hour  
**Complexity:** LOW  

**Deliverables:**
1. Add measurement table to `FilterPanel.tsx` component comments
2. Create `docs/FILTER_SYSTEM.md` with:
   - Filter architecture overview
   - Measurement reference table (copy from FILTER_CARD_SYSTEM_AUDIT.md)
   - Usage examples (AllotmentFilters, LicenseLedger)
   - When to use FilterPanel vs. custom panel

**Files to Create/Update:**
```
frontend/src/components/filters/FilterPanel.tsx (add JSDoc comments)
docs/FILTER_SYSTEM.md (new)
```

**Acceptance Criteria:**
- [ ] All measurements documented
- [ ] Usage examples clear
- [ ] Linked from README or main docs index
- [ ] No technical errors

**Dependencies:** ITEMS 1-4  
**Blocks:** None (informational)

---

## CARD SYSTEM WORK ITEMS

### ITEM 6: Standardize Card Usage in Reports
**Status:** QUEUED  
**Files:** 
- `frontend/src/pages/reports/ItemPivotReport.tsx`
- `frontend/src/pages/reports/ItemReport.tsx`
- `frontend/src/pages/reports/PlannedReport.tsx`  
**Type:** Component Refactor (Styling)  
**Effort:** 2-2.5 hours  
**Complexity:** MEDIUM  

**Current State:**
- Mix of Card (shadcn/ui) and custom card divs
- Inconsistent padding (some px-4 py-3, some px-5 py-4)
- Some pages missing border/shadow

**Changes:**
1. Audit card usage in each report file
2. Replace custom card divs with Card/CardHeader/CardContent
3. Ensure consistent padding: px-5 py-4 (20px horizontal, 16px vertical)
4. Apply border and shadow consistently
5. Use CardHeader for section titles (not custom divs)

**Example Migration:**
```typescript
// Before (custom div)
<div className="rounded-lg border bg-card p-4">
  <h3>{title}</h3>
  {content}
</div>

// After (shadcn/ui)
<Card>
  <CardHeader>
    <CardTitle>{title}</CardTitle>
  </CardHeader>
  <CardContent>
    {content}
  </CardContent>
</Card>
```

**Acceptance Criteria:**
- [ ] All report cards use shadcn/ui Card component
- [ ] Padding consistent (px-5 py-4)
- [ ] Border and shadow applied
- [ ] Report data unchanged
- [ ] Responsive behavior tested
- [ ] Passes lint, typecheck, and build

**Dependencies:** None  
**Blocks:** ITEM 8 (documentation)

---

### ITEM 7: Document Card System Patterns
**Status:** QUEUED  
**Type:** Documentation  
**Effort:** 1 hour  
**Complexity:** LOW  

**Deliverables:**
1. Create `docs/CARD_SYSTEM.md` with:
   - Card architecture (Card vs. StatCard vs. EntityCard)
   - When to use each type
   - Padding/spacing measurements
   - Tone system (StatCard)
   - Code examples
   - Properties reference

2. Update `docs/README.md` to link to Card system doc

**Files to Create/Update:**
```
docs/CARD_SYSTEM.md (new)
docs/README.md (add link)
```

**Acceptance Criteria:**
- [ ] All card types documented
- [ ] Usage patterns clear
- [ ] Tone system explained
- [ ] Examples provided
- [ ] No technical errors
- [ ] Linked from main docs

**Dependencies:** ITEMS 1-6  
**Blocks:** None (informational)

---

### ITEM 8: Quality Gate Checks
**Status:** READY (post-implementation)  
**Type:** QA/Validation  
**Effort:** 0.5 hours  
**Complexity:** LOW  

**Checks:**
```bash
cd frontend
npm run lint      # ESLint
npm run typecheck # TypeScript strict mode
npm run build     # Vite build
```

**Acceptance Criteria:**
- [ ] `npm run lint` exits with code 0
- [ ] `npm run typecheck` exits with code 0
- [ ] `npm run build` exits with code 0
- [ ] No new warnings or errors

**Dependencies:** All work items  
**Blocks:** PR submission

---

## IMPLEMENTATION PRIORITY & SEQUENCE

### Phase 1 (Foundation) — 2–3 hours
1. **ITEM 1:** AllotmentFilters h-9 standardization (1h) — Quick win
2. **ITEM 2:** FilterPanel FilterLabel component (1.5h) — Enables standardization

### Phase 2 (Refactoring) — 5–6 hours
3. **ITEM 3:** LicenseLedger filter extraction (3-4h) — Medium complexity
4. **ITEM 4:** ItemPivot/ItemReport evaluation (2-3h) — Analysis work
5. **ITEM 6:** Report cards standardization (2-2.5h) — Parallel possible

### Phase 3 (Documentation & Validation) — 2–3 hours
6. **ITEM 5:** Filter measurement documentation (1h)
7. **ITEM 7:** Card system documentation (1h)
8. **ITEM 8:** Quality gates (0.5h)

### Recommended Parallelization
- Phase 1: Sequential (foundation)
- Phase 2: Items 3, 4, 6 can run in parallel (different files)
- Phase 3: Sequential (depends on all Phase 2 items)

---

## MEASUREMENT REFERENCE (For Implementation)

### Input Fields
```
Height:        h-9 (36px)
Padding:       px-3 py-1 (12px H, 4px V)
Border radius: rounded-md (6px)
Border:        border-input
Font size:     text-sm (14px)
```

### Labels
```
Font size:     text-sm (14px)
Font weight:   normal (400) or bold (700) for emphasis
Spacing below: mb-2 (8px)
Icon size:     size-4 (16px)
Icon + label:  flex items-center gap-2
```

### Filter Panels
```
Container padding:    px-3 py-3 (12px) or px-3 py-3 sm:px-4 sm:py-4 (responsive)
Row gap (FilterGrid): gap-3 (12px)
Header height:        min-h-11 (44px)
Border radius:        rounded-lg (8px)
Border:               1px border-border/70
Shadow:               shadow-sm
Background:           bg-card
Grid columns:         1 / 2 / 4 (responsive)
```

### Cards
```
Padding (header):     px-5 pt-5 (20px H, 20px V)
Padding (content):    px-5 pb-5 (20px H, 20px V)
Padding (footer):     px-5 pb-5 (20px H, 20px V)
Border radius:        rounded-xl (12px)
Border:               1px border-border
Shadow:               shadow-sm
Background:           bg-card
Gap (header):         gap-1.5 (6px)
```

---

## FILES IMPACTED

### Core Components
- `frontend/src/components/filters/FilterPanel.tsx` (ITEM 2 — enhancement)
- `frontend/src/components/ui/card.tsx` (ITEM 6 — reference only)

### Pages (Filters)
- `frontend/src/pages/AllotmentFilters.tsx` (ITEM 1 — styling update)
- `frontend/src/pages/LicenseLedger.tsx` (ITEM 3 — extraction/refactor)
- `frontend/src/pages/reports/ItemPivotFilters.tsx` (ITEM 4 — analysis)
- `frontend/src/pages/reports/itemReport/ItemReportFilters.tsx` (ITEM 4 — analysis)

### Pages (Cards)
- `frontend/src/pages/reports/ItemPivotReport.tsx` (ITEM 6 — standardization)
- `frontend/src/pages/reports/ItemReport.tsx` (ITEM 6 — standardization)
- `frontend/src/pages/reports/PlannedReport.tsx` (ITEM 6 — standardization)

### New Files
- `frontend/src/pages/components/LicenseLedgerFilterPanel.tsx` (ITEM 3 — new)
- `docs/FILTER_SYSTEM.md` (ITEM 5 — new)
- `docs/CARD_SYSTEM.md` (ITEM 7 — new)

---

## BLAST RADIUS ANALYSIS

### Filter Components (15+ dependents)
- **FilterPanel:** Used by AllotmentFilters, AdvancedFilter
- **FilterField:** Used by AllotmentFilters, AdvancedFilter
- **DateRangeFilter:** Used by AllotmentFilters, ItemPivotFilters, ItemReportFilters, LicenseLedger
- **AsyncSelectField:** Used by ItemPivotFilters, ItemReportFilters, LicenseLedger, AllotmentFilters

**Risk:** LOW — styling and structure changes only; no behavior changes to filtering logic

### Card Components (40+ dependents)
- **Card:** Widely adopted (Dashboard, Admin, Reports, etc.)
- **StatCard:** 5+ dependents (metrics display)
- **EntityCard:** 3+ dependents (list items)

**Risk:** LOW-MEDIUM — Card usage is standardized; changes to Report cards are localized

---

## SIGN-OFF

**Audit Complete:** 2026-09-25  
**Status:** Ready for frontend-engineer implementation  
**Next Step:** Launch frontend-engineer with this queue and FILTER_CARD_SYSTEM_AUDIT.md

**Key Success Factors:**
1. Standardize field heights to h-9 across all filters
2. Extract LicenseLedger filters into FilterPanel structure
3. Document measurements for future consistency
4. Replace custom cards with shadcn/ui Card component
5. Pass all quality gates (lint, typecheck, build)

---

**Questions?** See `FILTER_CARD_SYSTEM_AUDIT.md` for detailed analysis and findings.
