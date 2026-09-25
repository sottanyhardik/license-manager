# UI Agent Work Queue: Table & EmptyState Standardization
**Date Created:** 2026-09-25  
**Branch:** hotfix/ui-consistency-2026-09-25  
**Status:** READY FOR IMPLEMENTATION

---

## Overview

This queue documents the prioritized work to standardize table empty states across the License Manager UI, replacing ad-hoc implementations with the centralized `<EmptyState>` component.

**Key Finding:** The `EmptyState.tsx` component is complete and production-ready. All work is migration/unification work, not new development.

---

## Work Items

### PHASE 1: DataTable Empty State (READY)

**File:** `frontend/src/components/DataTable.tsx`  
**Status:** ✅ READY  
**Effort:** 5 min  
**Impact:** Affects ~15+ pages using DataTable

#### Current Code (Lines 192-201)
```tsx
if (data.length === 0) {
    return (
        <div className="flex flex-col items-center px-6 py-14 text-center">
            <span className="mb-3 flex size-12 items-center justify-center rounded-xl border border-border/60 bg-muted/50">
                <Inbox className="size-5 text-muted-foreground/50" aria-hidden="true" />
            </span>
            <p className="text-sm font-semibold text-foreground">No records found</p>
            <p className="mt-1 text-xs text-muted-foreground">Try adjusting your search or filter criteria</p>
        </div>
    );
}
```

#### Proposed Change
```tsx
if (data.length === 0) {
    return (
        <div className="app-data-table table-responsive-mobile" role="region" aria-label="Data table" tabIndex={0}>
            <EmptyState 
                icon={Inbox} 
                title="No records found" 
                description="Try adjusting your search or filter criteria" 
            />
        </div>
    );
}
```

#### Dependencies to Add
- `import EmptyState from "@/components/EmptyState";` (if not already imported)
- `Inbox` icon already imported

#### Testing Checklist
- [ ] Verify empty state displays when data is empty
- [ ] Check dark mode appearance
- [ ] Verify Inbox icon renders correctly
- [ ] Test accessibility with screen reader
- [ ] Confirm responsive layout on mobile

---

## Quality Gates (Run Before Marking DONE)

From project root (`frontend/`):

```bash
cd frontend

# 1. Lint check
npm run lint

# 2. Type check
npm run typecheck

# 3. Build check
npm run build
```

All three commands must pass (exit code 0).

---

## Acceptance Criteria

### Code Quality
- [ ] No TypeScript errors
- [ ] No ESLint warnings
- [ ] All quality gates pass (lint, typecheck, build)
- [ ] No unused imports introduced

### Functional
- [ ] Empty states display correctly for each table
- [ ] Dark mode renders properly
- [ ] Mobile responsive behavior maintained
- [ ] Accessibility preserved (icon aria-hidden, alt text)

### Styling
- [ ] Icon sizing consistent with previous implementation
- [ ] Text color meets AA contrast requirements
- [ ] Spacing/padding visually matches previous layout
- [ ] No visual regression on light and dark modes

---

## Files Modified Summary

| File | Lines Changed | Type | Effort |
|------|--------------|------|--------|
| DataTable.tsx | 192-201 | Empty state | 5 min |
| AllotmentsTable.tsx | 40-45 | Empty state | 5 min |
| IncentiveLicensesTable.tsx | 34-38 | Empty state | 5 min |
| AccordionTable.tsx | 170-175 | Empty state | 5 min |
| tabler.css | 864-887 | CSS removal | 2 min |
| **TOTAL** | — | — | **22 min** |

---

## Sign-Off

- **Audit Completed:** 2026-09-25
- **Audit By:** Table & EmptyState Specialist Agent
- **Status:** READY FOR IMPLEMENTATION
