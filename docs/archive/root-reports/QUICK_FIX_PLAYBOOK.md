# Quick-Fix Playbook — Common Blocking Issues & Resolutions

**Purpose:** Pre-planned fixes for issues likely to be found by agents

---

## ISSUE #1: ActiveFilters Not Displaying on Page

**Symptom:** Page loads, filters work, but ActiveFilters component doesn't appear

**Root Causes:**
1. Component not imported
2. activeFilters array is empty
3. Component returns null (no active filters)
4. JSX syntax error
5. Component not rendered

**Quick Fix:**
```tsx
// 1. Verify import
import ActiveFilters, { type ActiveFilterItem } from '@/components/ActiveFilters';

// 2. Build activeFilters array properly
const activeFilters: ActiveFilterItem[] = useMemo(() => {
  const items: ActiveFilterItem[] = [];
  if (filter1 !== defaultFilter1) {
    items.push({
      key: 'filter1',
      label: 'Filter 1',
      value: filter1Value,
    });
  }
  return items;
}, [filter1, defaultFilter1]);

// 3. Don't early return null
// Return component even if empty (it handles hiding)
return (
  <div>
    <ActiveFilters
      filters={activeFilters}
      onRemove={handleRemove}
      onClearAll={handleClearAll}
    />
    {/* Rest of page */}
  </div>
);
```

**Fix Time:** 2-5 minutes per page

---

## ISSUE #2: Test Failures in LicenseLedger

**Symptom:** Tests fail with "Cannot find element" or "Element not found"

**Root Cause:** Page DOM changed with ActiveFilters implementation, test fixtures outdated

**Quick Fix:**
```bash
# 1. Run failing test
npm run test -- LicenseLedger

# 2. Read assertion failure (e.g., "expect(screen.findByText('Company')).toBe...")

# 3. Update test fixture to match new DOM
# Open test file, find failing assertion
# Check actual DOM in browser to see what changed
# Update assertion to match new structure

# Example:
// OLD:
expect(screen.getByText('Company')).toBeInTheDocument();

// NEW: (if Company is now in a different div)
expect(screen.getByText('Company')).toBeInTheDocument(); // Still valid
// But if parent changed:
expect(screen.getByRole('heading', { name: /Company/i })).toBeInTheDocument();
```

**Fix Time:** 5-10 minutes per test file

---

## ISSUE #3: Console Errors on Page Load

**Symptom:** Page loads but browser console shows errors

**Common Errors & Fixes:**

### Error: "Cannot read property 'length' of undefined"
```tsx
// Problem:
activeFilters.length // when activeFilters is undefined

// Fix:
activeFilters?.length ?? 0
// OR
if (!activeFilters || activeFilters.length === 0) return null;
```

### Error: "Missing dependency in dependency array"
```tsx
// Problem:
useMemo(() => { ... }, []) // Missing dependencies

// Fix:
useMemo(() => { ... }, [filters, defaultFilters, ...]) // Include all deps
```

### Error: "Type 'unknown' is not assignable"
```tsx
// Problem:
const item: ActiveFilterItem = getFilterFromAPI(); // Type mismatch

// Fix:
const item: ActiveFilterItem = {
  key: getFilterKey(),
  label: getFilterLabel(),
  value: getFilterValue(),
};
```

**Fix Time:** 2-5 minutes per error

---

## ISSUE #4: Lint Errors (Unused Variables)

**Symptom:** Lint reports warnings or errors in new code

**Quick Fix:**
```bash
# Option 1: Remove unused import
- import { useMemo } from 'react';
+ // useMemo not needed

# Option 2: Use the variable
- const position = props.position;
+ const position = props.position ?? 'default';
// Then use 'position' in JSX

# Option 3: Rename parameter with underscore
- onRemove={({ key }) => ...}
+ onRemove={({ _key }) => ...}
// ESLint allows unused params starting with _
```

**Fix Time:** 1 minute per warning

---

## ISSUE #5: Filter Removal Not Working

**Symptom:** Click × button, filter doesn't remove

**Root Causes:**
1. onRemove callback not connected
2. Callback doesn't update filter state
3. Default value wrong

**Quick Fix:**
```tsx
// Verify onRemove callback:
const handleRemoveFilter = (key: string) => {
  const defaultValue = defaultFilters()[key];
  updateFilter(key, defaultValue);
};

// In ActiveFilters component:
<ActiveFilters
  filters={activeFilters}
  onRemove={handleRemoveFilter} // ← Must be connected
  onClearAll={clearAllFilters}
/>

// Verify updateFilter works:
const updateFilter = (key: string, value: any) => {
  setFilters({ ...filters, [key]: value });
  // MUST refetch results
};
```

**Fix Time:** 3-5 minutes

---

## ISSUE #6: Dark Mode Colors Wrong

**Symptom:** Dark theme shows hardcoded colors, not design system colors

**Quick Fix:**
```tsx
// Check for hardcoded colors:
// BAD:
<div style={{ color: '#333' }}>

// GOOD:
<div className="text-foreground">
// OR
<div style={{ color: 'var(--tb-foreground)' }}>

// Use Tailwind classes instead:
className="text-foreground dark:text-foreground-dark"
// (Tailwind handles both light/dark automatically)
```

**Fix Time:** 2-5 minutes per instance

---

## ISSUE #7: Responsive Layout Broken on Mobile

**Symptom:** Page works on desktop but overlaps/hides on mobile

**Quick Fix:**
```tsx
// Check for hardcoded widths:
// BAD:
<div style={{ width: '200px' }}>

// GOOD:
<div className="w-full sm:w-[200px]">

// Check for flex issues:
// BAD:
<div className="flex flex-row gap-4">
  <div style={{ width: '200px' }}>
  <div style={{ width: '200px' }}>
</div>

// GOOD:
<div className="flex flex-col sm:flex-row gap-4">
  <div className="w-full sm:w-[200px]">
  <div className="w-full sm:w-[200px]">
</div>
```

**Fix Time:** 3-5 minutes per instance

---

## ISSUE #8: All Filters Show in ActiveFilters (Including Defaults)

**Symptom:** ActiveFilters shows filters that are set to default values

**Root Cause:** isActive check is wrong

**Quick Fix:**
```tsx
const isActive = (key: keyof Filters) => {
  const value = filters[key];
  const defaultValue = defaultFilters()[key];
  
  // Check if DIFFERENT from default
  if (Array.isArray(value)) return value.length > 0;
  if (typeof value === 'boolean') return value !== false;
  if (value === null || value === undefined) return false;
  
  return value !== defaultValue; // ← KEY CHECK
};
```

**Fix Time:** 2-3 minutes

---

## ISSUE #9: Build Bundle Size Regression

**Symptom:** Build bundle > 5% larger than baseline

**Root Cause:** Unused imports or duplicate code

**Quick Fix:**
```bash
# Check imports
grep -n "import" src/pages/ModifiedPage.tsx | grep -E "unused|duplicate"

# Remove unused imports:
- import { unneededComponent } from '@/components';

# Check for duplicate logic:
# Move to shared utility if needed
```

**Fix Time:** 5-10 minutes

---

## ISSUE #10: Some SION Reports Missing ActiveFilters

**Symptom:** SionE1, SionE5, etc. don't have ActiveFilters but should

**Root Cause:** Agent didn't implement on all SION pages

**Quick Fix:**
```tsx
// Copy pattern from SionNormReport (already done)
// Implement same way on SionE1.tsx, SionE5.tsx, etc.

// 1. Import ActiveFilters
// 2. Build activeFilters array from report filters
// 3. Render component after filter controls
// 4. Test
```

**Fix Time:** 5 minutes per page

---

## FIX PRIORITY WHEN MULTIPLE ISSUES

**Order:**
1. **CRITICAL (Blocks all):** Build fails, lint errors, TypeScript errors
2. **HIGH (Breaks functionality):** Tests fail, filters don't work, pages don't load
3. **MEDIUM (Visual/responsive):** Console warnings, dark mode issues, responsive issues
4. **LOW (Polish):** Unused imports, lint warnings, minor inconsistencies

---

## EXECUTION STRATEGY

When issue identified:

1. **Identify severity** (Critical/High/Medium/Low)
2. **Use quick fix above** (if applicable)
3. **Verify fix works:**
   ```bash
   npm run lint  # Should pass
   npm run build # Should pass
   npm run test  # Should pass
   # Test in browser
   ```
4. **Continue to next issue**

---

**Use this playbook when agents report issues.**
