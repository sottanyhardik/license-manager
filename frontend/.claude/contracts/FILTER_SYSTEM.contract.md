# FILTER SYSTEM Contract (FROZEN)

**Status:** LOCKED — No changes to component signatures or hierarchy after initial build.  
**Location:** `/frontend/src/components/filters/`  
**Built:** 2026-09-28

---

## Visual Hierarchy (IMMUTABLE)

```
Page Header
     ↓
Global Search (TextField with SearchIcon)
     ↓
Filters (MUI Grid with child components)
     ↓
Active Filters (Chips with individual × removal)
     ↓
Clear All Button
     ↓
DataGrid / Content
```

---

## Components

### FilterPanel

**File:** `/frontend/src/components/filters/FilterPanel.tsx`

Wraps all filter controls and renders search + filters + active filters + clear all.
Provides FilterContext to child components via FilterProvider.

**Props:**
```tsx
interface FilterPanelProps {
  children: React.ReactNode;        // Filter field components (FilterSelect, FilterAutocomplete, etc.)
  onFiltersChange?: () => void;     // Callback fired when any filter or search changes
}
```

**Usage:**
```tsx
<FilterPanel onFiltersChange={handleDataRefresh}>
  <FilterSelect label="Status" filterKey="status" options={[...]} />
  <FilterAutocomplete label="Port" filterKey="port" options={[...]} />
  <FilterDateRange label="Date" filterKey="date" />
</FilterPanel>
```

**Rendered Structure:**
```
Paper (elevation: 0)
├── Search TextField (MUI TextField with SearchIcon)
├── Grid (filter controls — spacing={2})
├── Active Filters Box (ALWAYS VISIBLE if filters exist)
│   ├── Typography "Active Filters:"
│   ├── Chips (one per active filter + search)
│   │   └── Chip onDelete removes that filter
│   └── Clear All Button
```

---

### FilterSelect

**File:** `/frontend/src/components/filters/FilterSelect.tsx`

Static dropdown filter using MUI Select.

**Props:**
```tsx
interface FilterSelectProps {
  label: string;                              // Display label
  filterKey: string;                          // Unique key in filters object
  options: Array<{value: string; label: string}>;  // Dropdown options
  multiple?: boolean;                         // Allow multi-select (default: false)
  helperText?: string;                        // Optional helper text
  required?: boolean;                         // Mark as required (default: false)
  disabled?: boolean;                         // Disable the select (default: false)
  size?: 'small' | 'medium';                  // MUI size (default: 'small')
  gridSize?: 12 | 6 | 4 | 3;                  // Responsive column span (default: 12)
}
```

**Responsive Behavior:**
- Mobile (xs): 12 columns (full width)
- Tablet (sm/md): 6 columns (50%)
- Desktop (lg): gridSize prop value

**Usage:**
```tsx
<FilterSelect
  label="Status"
  filterKey="status"
  options={[
    { value: 'active', label: 'Active' },
    { value: 'inactive', label: 'Inactive' },
  ]}
/>
```

---

### FilterAutocomplete

**File:** `/frontend/src/components/filters/FilterAutocomplete.tsx`

Searchable dropdown filter using MUI Autocomplete.

**Props:**
```tsx
interface FilterAutocompleteProps {
  label: string;                              // Display label
  filterKey: string;                          // Unique key in filters object
  options: Array<{value: string; label: string}>;  // Options list
  multiple?: boolean;                         // Allow multi-select (default: false)
  searchable?: boolean;                       // Enable search (default: true)
  helperText?: string;                        // Optional helper text
  required?: boolean;                         // Mark as required (default: false)
  disabled?: boolean;                         // Disable autocomplete (default: false)
  size?: 'small' | 'medium';                  // MUI size (default: 'small')
  gridSize?: 12 | 6 | 4 | 3;                  // Responsive column span (default: 12)
  freeSolo?: boolean;                         // Allow custom text (default: false)
  loading?: boolean;                          // Show loading state (default: false)
}
```

**Responsive Behavior:** Same as FilterSelect

**Usage:**
```tsx
<FilterAutocomplete
  label="Port"
  filterKey="port"
  options={[
    { value: 'port1', label: 'Nhava Sheva' },
    { value: 'port2', label: 'Mundra' },
  ]}
  searchable={true}
/>
```

---

### FilterDateRange

**File:** `/frontend/src/components/filters/FilterDateRange.tsx`

Date picker filter using MUI TextField with `type="date"`.

**Props:**
```tsx
interface FilterDateRangeProps {
  label: string;                    // Display label
  filterKey: string;                // Unique key in filters object (e.g., "startDate")
  helperText?: string;              // Optional helper text
  required?: boolean;               // Mark as required (default: false)
  disabled?: boolean;               // Disable date field (default: false)
  size?: 'small' | 'medium';        // MUI size (default: 'small')
  gridSize?: 12 | 6 | 4 | 3;        // Responsive column span (default: 12)
  minDate?: string;                 // Min selectable date (YYYY-MM-DD)
  maxDate?: string;                 // Max selectable date (YYYY-MM-DD)
}
```

**Responsive Behavior:** Same as FilterSelect

**Usage:**
```tsx
<FilterDateRange label="From Date" filterKey="startDate" />
<FilterDateRange label="To Date" filterKey="endDate" />
```

---

## Hook: useFilters()

**File:** `/frontend/src/components/filters/FilterContext.tsx`

Access filter state and actions inside any child of FilterPanel.

**Signature:**
```tsx
function useFilters(): FilterContextType {
  state: FilterState;                    // Current filter state
  setSearch: (search: string) => void;   // Update search text
  setFilter: (key: string, value: any, label?: string) => void;  // Set a filter
  removeFilter: (key: string) => void;   // Remove a filter by key
  clearAllFilters: () => void;           // Clear all filters and search
  onFiltersChange?: () => void;          // Callback (from FilterPanel prop)
}
```

**FilterState:**
```tsx
interface FilterState {
  search: string;                         // Global search text
  filters: Record<string, any>;           // All filter values by key
  activeFilters: Array<{
    key: string;                          // Filter key
    label: string;                        // Display label
    value: string;                        // Display value
  }>;
}
```

**Usage:**
```tsx
function MyFilterChild() {
  const { state, setFilter, removeFilter } = useFilters();
  
  console.log(state.search);              // Search text
  console.log(state.filters);             // All filters
  console.log(state.activeFilters);       // For custom UI
  
  setFilter('status', 'active', 'Active'); // Update filter
  removeFilter('status');                  // Remove filter
}
```

---

## Layout Rules (IMMUTABLE)

### Responsive Grid Breakpoints

```
Mobile (xs: 0px):      Grid cols=12  → 1 filter per row
Tablet (sm: 600px):    Grid cols=6   → 2 filters per row
Desktop (md: 900px):   Grid cols=4   → 3 filters per row (default)
Wide (lg: 1200px):     Grid cols=3   → 4 filters per row (or custom gridSize)
```

### Active Filters Display Rules

1. **Always Visible:** Active Filters box renders when any filter or search is set
2. **Search Chip:** Displays as `Search: <text>` with delete handler
3. **Filter Chips:** Displays as `<Label>: <Value>` with delete handler
4. **Individual Removal:** Each chip has an × button (onDelete)
5. **Clear All Button:** Present when any active filters exist
   - Clears search AND all filters in one action
   - Aligns right in the active filters box

### Container & Spacing

- **FilterPanel:** Paper with `elevation: 0`, `border: 1px solid`, `p: 2`
- **Search section:** `p: 2`, `borderBottom: 1px solid`
- **Filter Grid:** `spacing: 2` (16px gap)
- **Active Filters box:** `p: 2`, `backgroundColor: action.hover`
- **Chips:** `size: small`, `variant: outlined`, `gap: 1`

---

## Callback Behavior

**onFiltersChange:** Fires whenever:
- Search text is updated
- Any filter value changes
- Any filter is removed
- Clear All is clicked

Allows parent pages to refetch data or update UI in response to filter changes.

---

## Type Exports

All TypeScript interfaces are exported from `/frontend/src/components/filters/index.ts`:

```tsx
// Components
export { FilterPanel, FilterSelect, FilterAutocomplete, FilterDateRange };

// Context & Hook
export { FilterProvider, useFilters, FilterContext };

// Types
export type {
  FilterPanelProps,
  FilterSelectProps,
  FilterSelectOption,
  FilterAutocompleteProps,
  FilterAutocompleteOption,
  FilterDateRangeProps,
  FilterContextType,
  FilterState,
  ActiveFilter,
  FilterProviderProps,
};
```

---

## Usage Pattern on a Page

```tsx
import { useState, useCallback } from 'react';
import { DataGrid } from '@mui/x-data-grid';
import {
  FilterPanel,
  FilterSelect,
  FilterAutocomplete,
  FilterDateRange,
} from '@/components/filters';

export function MyLicensePage() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(false);

  const handleFiltersChange = useCallback(() => {
    // Fetch data with current filters
    setLoading(true);
    // Call API with filters from useFilters() inside FilterPanel's children
    // Then setData(...)
    // setLoading(false);
  }, []);

  return (
    <>
      <PageHeader title="Licenses" />
      
      <FilterPanel onFiltersChange={handleFiltersChange}>
        <FilterSelect
          label="Status"
          filterKey="status"
          options={[
            { value: 'active', label: 'Active' },
            { value: 'inactive', label: 'Inactive' },
          ]}
        />
        <FilterAutocomplete
          label="Port"
          filterKey="port"
          options={[...]}
          searchable={true}
        />
        <FilterDateRange label="From Date" filterKey="startDate" />
        <FilterDateRange label="To Date" filterKey="endDate" />
      </FilterPanel>

      <DataGrid rows={data} columns={columns} loading={loading} />
    </>
  );
}
```

---

## Immutable Contract Rules

1. **Component signatures** (props) cannot change after this build
2. **FilterContext API** (useFilters hook) is locked
3. **Active Filters display** must remain visible (not hidden/optional)
4. **Responsive grid layout** must follow the breakpoint rules
5. **Callback behavior** must fire on every filter/search change
6. **Individual chip removal** × buttons are mandatory
7. **Clear All button** is mandatory when filters exist
8. **Search field always at top** of filter panel

---

## Files Created

- `/frontend/src/components/filters/FilterContext.tsx` — Context + useFilters hook
- `/frontend/src/components/filters/FilterPanel.tsx` — Main wrapper component
- `/frontend/src/components/filters/FilterSelect.tsx` — Static dropdown
- `/frontend/src/components/filters/FilterAutocomplete.tsx` — Searchable dropdown
- `/frontend/src/components/filters/FilterDateRange.tsx` — Date picker
- `/frontend/src/components/filters/index.ts` — Export barrel

---

## MUI Components Used

- `Box` — Container layout
- `Paper` — Elevated surface for filter panel
- `Grid` — Responsive column layout
- `TextField` — Search input and date picker
- `Select` — Static dropdown
- `MenuItem` — Select options
- `FormControl` — Select wrapper
- `Autocomplete` — Searchable dropdown
- `Chip` — Active filter display
- `Button` — Clear All action
- `Typography` — "Active Filters:" label
- `FormHelperText` — Optional helper text
- Icons: `SearchIcon`, `ClearIcon`

---

## Breaking Changes Policy

If a change is absolutely necessary:

1. **Notify all consuming pages** (see dependents.tsv)
2. **Increment contract version** (v1 → v2)
3. **Provide migration guide** for existing usage
4. **Run full test suite** for all consuming pages
5. **Update all affected pages** in the same PR

Current version: **1.0 (FROZEN)**

---

## QA Verification Checklist

- [ ] TypeScript: `npx tsc --noEmit` passes (0 errors in filters)
- [ ] ESLint: `npm run lint -- src/components/filters/` passes
- [ ] Build: `npm run build` succeeds (no warnings in filters code)
- [ ] Search field: Updates state and appears in Active Filters
- [ ] FilterSelect: Single/multi-select works, value displays in chip
- [ ] FilterAutocomplete: Search works, selection displays in chip
- [ ] FilterDateRange: Date picker works, value displays in chip
- [ ] Chip removal: Individual × buttons remove that filter
- [ ] Clear All: Removes all filters and search in one click
- [ ] onFiltersChange: Callback fires on every change
- [ ] useFilters hook: Works inside child components
- [ ] Responsive: Tested at 375px, 768px, 1200px viewports
- [ ] Dark mode: Active Filters box uses theme colors correctly
- [ ] Accessibility: Keyboard navigation works, labels linked to inputs

---

**DO NOT ITERATE after build completion. This is the frozen specification.**
