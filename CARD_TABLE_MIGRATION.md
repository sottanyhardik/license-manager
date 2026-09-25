# Card & Table Migration Guide

**Last Updated:** 2026-09-25  
**Target:** V2 systems (CARD_SYSTEM_V2.md, TABLE_SYSTEM_V2.md, DATA_PRESENTATION.md)  
**Effort:** ~3 sprints (backend review + frontend updates + testing)

---

## Overview

This document outlines the step-by-step migration from V1 (current) card and table patterns to V2 (spec'd). V2 delivers:

- Proper enterprise density (compact, scannable)
- Consistent styling via tokens (no hardcoded values)
- Professional visual hierarchy
- Better accessibility and dark mode support

---

## Phase 1: UI Primitives (Week 1)

### 1.1 Fix Card Component

**File:** `frontend/src/components/ui/card.tsx`

**Current Issue:**
- `rounded-xl` (16px) is too round; data cards look oversized

**Fix:**
```tsx
// Line 10: Change from:
"bg-card text-card-foreground flex flex-col rounded-xl border shadow-sm",
// To:
"bg-card text-card-foreground flex flex-col rounded-lg border shadow-sm",
```

**Verification:**
- Build: `npm run build` ✓
- Visual: Check CardHeader/CardContent/CardFooter padding looks correct
- Test: No breaking changes (component is widely used)

### 1.2 Document StatCard

**File:** `frontend/src/components/StatCard.tsx` (no changes needed)

**Verification:**
- Already follows V2 principles
- Shadow, padding, typography all correct
- Run tests: `npm run test StatCard`

### 1.3 Add Card Variants (Optional, Future)

**Approach:** Create variant prop (default, raised, flat, accent)

```tsx
// Future enhancement
function Card({ variant = "default", ...props }) {
    const variantClasses = {
        default: "shadow-sm border",
        raised: "shadow-md border hover:shadow-lg",
        flat: "border",
        accent: "border-l-4 border-l-primary",
    };
    return <div className={variantClasses[variant]} {...props} />;
}
```

**Decision:** Defer to Phase 4 (non-blocking for V2)

---

## Phase 2: EntityCard & Layout (Week 1–2)

### 2.1 Update EntityCard Padding

**File:** `frontend/src/theme/tabler.css` (lines 947–1015)

**Changes:**

```css
/* Before */
.entity-card-header {
    padding: 5px 12px !important;  /* Too tight */
}
.entity-card-body {
    padding: 6px 12px !important;  /* Too tight */
}
.entity-card + .entity-card {
    margin-top: 4px;  /* Too tight */
}

/* After */
.entity-card-header {
    padding: 12px 16px !important;  /* Proper breathing room */
}
.entity-card-body {
    padding: 12px 16px !important;  /* Proper breathing room */
}
.entity-card + .entity-card {
    margin-top: 16px;  /* Scannable spacing */
}
```

**Visual Impact:**
- Cards appear less cramped
- Header/body sections more readable
- Spacing between cards more spacious (easier to scan)

**Verification:**
- Check all pages using EntityCard:
  - Allotment list
  - BOE list
  - Trade list
  - Planning panel
- Screenshot before/after on mobile and desktop

### 2.2 Add StatCard to More Pages

**Targets:** Dashboard, Reconciliation views, Planning panel

**Example:**
```tsx
// In LicensePlanningPanel or ReconciliationIssues
<div className="grid grid-cols-1 md:grid-cols-3 gap-4">
  <StatCard label="Total Debited" value={totalDebited} icon={Download} />
  <StatCard label="Available" value={available} icon={Box} />
  <StatCard label="Pending" value={pending} icon={Clock} />
</div>
```

**Decision:** Per-page decision; not blocking V2 core work

---

## Phase 3: Table Refactor (Week 2–3)

### 3.1 Review DataTable Component

**File:** `frontend/src/components/DataTable.tsx`

**Current State (Good):**
- Row height ~44px ✓
- Header ~44px ✓
- Padding 12px horizontal ✓
- Numeric columns right-aligned ✓
- Hover state defined ✓
- Empty state implemented ✓
- Loading skeleton implemented ✓

**Minor Improvements (Optional):**

1. **Sticky Header:** Add sticky positioning for long lists
```css
.app-data-table thead th {
    position: sticky;
    top: 0;
    z-index: var(--tb-z-sticky, 20);
}
```

2. **Keyboard Navigation:** Improve Tab/Arrow key support
```tsx
// Add to table rows:
<tr role="row" tabIndex={0}>
```

3. **Focus Ring:** Add visible focus indication
```tsx
<td role="gridcell" tabIndex={editable ? 0 : -1}>
  {/* Add focus-visible ring on edit mode */}
</td>
```

**Decision:** Keep as is for V2; focus on other tables

### 3.2 Apply DataTable Pattern to Other List Pages

**Current Usage:**
- Allotment list: ✓ Using DataTable-like pattern
- BOE list: ��� Using DataTable-like pattern
- Trade list: ✓ Using DataTable-like pattern

**Check:** Do any pages use old Django table patterns? (unlikely, but audit)

**Verification:** Grep for `.table` class usage across frontend

```bash
grep -r "className.*table" frontend/src/pages --include="*.tsx"
```

### 3.3 Document Table Responsive Behavior

**File:** `TABLE_SYSTEM_V2.md` (already documented)

**Implementation Check:**
- Mobile: Card layout responsive? (< 720px)
- Tablet: Column hiding works? (720px–1023px)
- Desktop: Full table display? (≥ 1024px)

**Test Devices:**
- iPhone SE (375px)
- iPad (768px)
- Desktop (1024px+)

---

## Phase 4: Data Formatting & Polish (Week 3–4)

### 4.1 Implement Currency Formatter

**File:** `frontend/src/utils/currencyFormatter.js` (create if missing)

```typescript
export const formatCurrency = (amount: number | string, currency: "INR" | "USD" = "INR", decimals: number = 2): string => {
    if (amount === null || amount === undefined) return "—";
    
    const num = typeof amount === "string" ? parseFloat(amount) : amount;
    if (isNaN(num)) return "—";
    
    return new Intl.NumberFormat("en-IN", {
        style: "currency",
        currency,
        minimumFractionDigits: decimals,
        maximumFractionDigits: decimals,
    }).format(num);
};

// Usage:
// formatCurrency(1269044300, "INR", 2) → "₹ 1,26,90,44,300.00"
// formatCurrency(5000.5, "USD", 2) → "$ 5,000.50"
```

**Audit:** Search for hardcoded currency display
```bash
grep -r "toLocaleString\|\.toFixed\|toString" frontend/src --include="*.tsx" | grep -i "currency\|amount\|inr\|usd"
```

**Replace with:** `formatCurrency()` utility

### 4.2 Verify Date Formatting

**File:** `frontend/src/utils/dateFormatter.js` (likely exists)

**Check:**
- ISO format in tables (YYYY-MM-DD)
- Relative dates in activity logs ("2h ago")
- Full dates in tooltips (on hover)

**Audit:**
```bash
grep -r "new Date\|toDateString\|toISOString" frontend/src --include="*.tsx" | head -20
```

### 4.3 Apply Semantic Colors to Status Badges

**File:** `frontend/src/theme/tokens.js` (reference)

**Pattern:**
```tsx
import { TONE_MAP } from "@/theme/tokens";

const StatusBadge = ({ status }) => {
    const t = TONE_MAP[status] || TONE_MAP.neutral;
    return (
        <span
            style={{
                backgroundColor: t.bg,
                color: t.fg,
                border: `1px solid ${t.border}`,
            }}
            className="inline-flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium"
        >
            {/* Icon + text */}
        </span>
    );
};
```

**Audit:** Replace hardcoded status colors
```bash
grep -r "bg-red\|bg-green\|bg-yellow\|bg-blue" frontend/src --include="*.tsx"
```

### 4.4 Add `tabular-nums` to Numeric Columns

**Target:** All tables with numeric data

```css
.table td.numeric,
.table .tabular-nums {
    font-variant-numeric: tabular-nums;
}
```

**Usage:**
```tsx
<td className="text-right tabular-nums">
  {formatCurrency(value)}
</td>
```

---

## Phase 5: Accessibility & Dark Mode (Week 4)

### 5.1 Accessibility Audit

**Run IntelliJ Inspection:**
```bash
npm run lint
```

**Manual Checks:**
1. Focus rings: Tab through all interactive elements
2. Screen reader: Test with NVDA or JAWS on key pages
3. Keyboard navigation: No mouse required to complete workflows
4. Color contrast: Use WebAIM contrast checker

**Fixes:**
- Add `aria-label` to action buttons
- Add `role="row"`, `role="gridcell"` to table elements
- Add `aria-busy="true"` to loading states

### 5.2 Dark Mode Verification

**Test with:** `[data-theme="dark"]` on root element

**Pages to Check:**
- Dashboard
- License list
- Allotment list
- BOE list
- Planning panel
- Reports

**Common Issues:**
- Borders too dark (use `--tb-border` token, not hardcoded)
- Text too dark (use `--tb-text`, not hardcoded)
- Card backgrounds not switching

**Fixes:** Replace hardcoded colors with tokens

---

## Phase 6: Testing & QA (Week 4–5)

### 6.1 Unit Tests

**Update existing tests to match new expectations:**

```typescript
// Example: EntityCard spacing
describe("EntityCard", () => {
  it("renders with 12px header padding", () => {
    const { container } = render(<EntityCard title="Test" />);
    const header = container.querySelector(".entity-card-header");
    expect(window.getComputedStyle(header).padding).toBe("12px 16px");
  });

  it("has 16px spacing between cards", () => {
    const { container } = render(
      <div>
        <EntityCard title="Card 1" />
        <EntityCard title="Card 2" />
      </div>
    );
    const cards = container.querySelectorAll(".entity-card");
    const spacing = cards[1].offsetTop - (cards[0].offsetTop + cards[0].offsetHeight);
    expect(spacing).toBe(16);
  });
});
```

### 6.2 Visual Regression Tests

**Setup:** Use Percy or similar tool

```bash
npm run test:visual
```

**Captures:**
- Card component (all variants)
- EntityCard (all tones)
- StatCard (all tones)
- DataTable (desktop, mobile)
- Empty state
- Loading state
- Dark mode (all above)

### 6.3 Manual Testing

**Test Plan:**

| Page | Devices | Checks |
|------|---------|--------|
| Dashboard | Desktop, Mobile | Stat cards aligned, shadow on hover |
| License List | Desktop, Mobile | Table rows 44px, numeric right-aligned |
| Allotment List | Desktop, Mobile | Entity cards, 16px spacing |
| BOE Detail | Desktop, Mobile | Detail table, form sections |
| Planning Panel | Desktop, Mobile | Card sections, buttons aligned |
| Reports | Desktop, Mobile | Data presentation, formatting |

**Checklist:**
- [ ] Card shadows appear on hover
- [ ] Padding looks balanced (not cramped, not excessive)
- [ ] Fonts are readable (size, weight, contrast)
- [ ] Colors render correctly in dark mode
- [ ] Mobile responsive (<720px) switches to card layout
- [ ] Keyboard navigation works (Tab, Arrow, Enter, Escape)
- [ ] Focus rings visible on all interactive elements

---

## Phase 7: Rollout & Monitoring (Week 5+)

### 7.1 Create Feature Flag (Optional)

If deploying in stages:

```python
# backend/apps/core/features.py
FEATURE_V2_CARDS_TABLES = os.getenv("FEATURE_V2_CARDS_TABLES", "false").lower() == "true"
```

**Frontend:**
```tsx
const isV2Enabled = useFeatureFlag("v2_cards_tables");
return isV2Enabled ? <EntityCardV2 /> : <EntityCard />;
```

### 7.2 Communicate with Design/Product

- [ ] Share before/after screenshots
- [ ] Get sign-off on spacing/sizing changes
- [ ] Document in release notes

### 7.3 Monitor After Deploy

**Metrics:**
- No console errors related to cards/tables
- Page load performance unchanged
- No spike in bug reports
- User engagement unchanged (tables/cards still scannable)

---

## Breaking Changes Summary

### Visual Changes (Non-Breaking)

1. **Card border radius:** 16px → 8px (subtle, improves appearance)
2. **Entity card padding:** 5–6px → 12px (more breathing room)
3. **Entity card spacing:** 4px → 16px (better scannability)

**User Impact:** Minimal; tables/cards look more professional

### API/Logic Changes

**None.** V2 is purely cosmetic/styling. No business logic changes.

---

## Rollback Plan

If issues arise post-deploy:

1. **CSS:** Revert `tabler.css` changes
2. **Components:** Revert `card.tsx` changes
3. **Branch:** `git revert` the commit
4. **Deploy:** Hotfix to production

**Risk:** Low. Changes are isolated to styling layer.

---

## Files Modified Summary

### New Files
- `CARD_SYSTEM_V2.md` (spec)
- `TABLE_SYSTEM_V2.md` (spec)
- `DATA_PRESENTATION.md` (spec)
- `CARD_TABLE_MIGRATION.md` (this file)

### Modified Files
| File | Changes |
|------|---------|
| `frontend/src/components/ui/card.tsx` | `rounded-xl` → `rounded-lg` |
| `frontend/src/theme/tabler.css` | EntityCard padding, spacing updates |
| `frontend/src/utils/currencyFormatter.js` | Create/update (if missing) |
| `frontend/src/utils/dateFormatter.js` | Verify ISO format usage |
| Various pages | Replace hardcoded colors with tokens |

---

## Success Criteria

**Checklist for V2 completion:**

- [ ] Card border radius is 8px (not 16px)
- [ ] Entity card padding is 12px (not 5–6px)
- [ ] Entity card spacing is 16px (not 4px)
- [ ] All currency values formatted via `formatCurrency()`
- [ ] All dates in ISO format (YYYY-MM-DD) in tables
- [ ] Status badges use `TONE_MAP` (no hardcoded colors)
- [ ] Numeric columns right-aligned with `tabular-nums`
- [ ] DataTable component works on mobile (<720px)
- [ ] Accessibility: Tab/keyboard navigation works
- [ ] Dark mode: All tokens used, no hardcoded hex
- [ ] Tests pass: `npm run test && npm run lint && npm run build`
- [ ] Visual regression tests pass (if using Percy)
- [ ] Manual QA sign-off on key pages

---

## Timeline Estimate

- **Phase 1:** 1 day (UI primitives)
- **Phase 2:** 1 day (EntityCard)
- **Phase 3:** 1 day (Table review)
- **Phase 4:** 2 days (Data formatting)
- **Phase 5:** 2 days (A11y & dark mode)
- **Phase 6:** 3 days (Testing)
- **Phase 7:** 1 day (Rollout)

**Total:** ~11 days (~2.2 weeks for 1 developer)

---

## Notes

- V2 is **not blocking**; V1 continues to work
- Recommend phased rollout: Dashboard → Lists → Detail pages
- Defer optional enhancements (card variants, sticky header) to Phase 4
- No backend changes needed; front-end only

---

## Contact & Questions

- **Design Lead:** Product Designer (this agent)
- **Frontend Lead:** Frontend Engineer agent
- **QA Lead:** QA Test Engineer agent

See `.claude/agents/README.md` for how to engage specialists.
