# Filter System V2

**Status:** Design Specification (Implementation pending)  
**Date:** 2026-09-25  
**Designer:** Product Design (25yr enterprise SPA specialist)

---

## Overview

The Filter System provides a structured, professional interface for applying filters to data tables and lists. Filters are **not floating cards** — they are fixed, compact panels with clear visual hierarchy, organized field groups, and active filter indicators.

Key principle: **High density, scannable, responsive, professional.**

---

## FilterPanel Container

The main filter wrapper component.

```tsx
<FilterPanel 
  activeCount={3}
  isUpdating={false}
  onClear={handleClearFilters}
  clearDisabled={false}
>
  {/* Filter fields */}
</FilterPanel>
```

### Visual Structure

```
┌──────────────────────────────────────────────────────┐
│ Filter                             3 active    Clear   │ ← Header (border-bottom)
├──────────────────────────────────────────────────────┤
│ License Status: Active, Expiring                     │
│ Quantity Range: 100-1000                            │
│ Exporter: ACME Inc, Global Traders                  │
│                                                      │ ��� Content area
│ [Checkbox] Only Show Warnings                       │
│ [Toggle] Highlight Low Stock                        │
└──────────────────────────────────────────────────────┘
```

### Header Structure

```
┌────────────────────────────────────────┐
│ ⛓ Filters    3 active    ⟳ Updating...   │
│                          [× Clear Filters] │
└────────────────────────────────────────┘
```

**Components:**
- **Filter icon:** lucide-react `Filter` (16px)
- **"Filters" text:** 14px, font-weight: 600 (semibold)
- **Active count:** 12px, gray text (only if > 0)
- **Loading indicator:** Spinner + "Updating" text (12px, right side, if isUpdating)
- **Clear Filters button:** Ghost variant, right-aligned, disabled when no active filters

### Styling

```
border border-border/70 bg-card shadow-sm rounded-lg

Header:
- min-h-11 (44px)
- px-3 py-2 (12px padding)
- border-b border-border/60
- flex items-center gap-2
- bg: inherit

Content:
- p-3 (12px padding all sides)
- bg: inherit
```

---

## FilterGrid & FilterField

Responsive grid layout for filter fields.

```tsx
<FilterGrid>
  <FilterField>
    <Label>License Status</Label>
    <Select>...</Select>
  </FilterField>
  
  <FilterField wide={true}>
    {/* Wide field spans 2 columns on XL */}
  </FilterField>
</FilterGrid>
```

### FilterGrid

```
grid grid-cols-1 gap-3
sm:grid-cols-2
xl:grid-cols-4
```

**Breakpoints:**
- **Mobile (< sm):** 1 column (100% width)
- **Small (sm):** 2 columns (50% width each)
- **Extra Large (xl):** 4 columns (25% width each)

**Gap:** 12px (3-unit spacing from tokens)

### FilterField

```
<div className="space-y-1.5">
  {children}
</div>
```

**Props:**
- `wide?: boolean` — If true, spans 2 columns on XL (`xl:col-span-2`)

**Internal spacing:**
- Between label and control: 6px (`mb-1.5`)
- Auto-adjusts for nested elements

---

## Filter Field Types

### Single Select
Filter by one value from a dropdown.

```tsx
<FilterField>
  <Label>License Status</Label>
  <Select value={status} onValueChange={setStatus}>
    <SelectTrigger size="sm">
      <SelectValue placeholder="All statuses" />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="">All</SelectItem>
      <SelectItem value="active">Active</SelectItem>
      <SelectItem value="expiring">Expiring Soon</SelectItem>
      <SelectItem value="expired">Expired</SelectItem>
    </SelectContent>
  </Select>
</FilterField>
```

**Visual:**
- Height: 36px (`size="sm"`)
- Placeholder: "All statuses" (lighter color)
- When selected: Show value (darker)

### Multi-Select Checkbox Group
Filter by multiple values (checkboxes).

```tsx
<FilterField>
  <Label>Condition Type</Label>
  <div className="space-y-2">
    <div className="flex items-center gap-2">
      <Checkbox 
        id="au" 
        checked={conditions.includes("AU")}
        onCheckedChange={(checked) => toggleCondition("AU", checked)}
      />
      <Label htmlFor="au" className="font-normal">AU</Label>
    </div>
    <div className="flex items-center gap-2">
      <Checkbox 
        id="2pct" 
        checked={conditions.includes("2%")}
        onCheckedChange={(checked) => toggleCondition("2%", checked)}
      />
      <Label htmlFor="2pct" className="font-normal">2%</Label>
    </div>
  </div>
</FilterField>
```

**Visual:**
- Checkbox size: 16px
- Spacing between items: 8px
- Label: 14px, normal weight (not bold)
- Gap between checkbox and label: 8px

### Text Input / Search
Filter by text pattern.

```tsx
<FilterField>
  <Label>License Number</Label>
  <Input 
    placeholder="e.g., DFIA-2024-001"
    value={licenseNumber}
    onChange={(e) => setLicenseNumber(e.target.value)}
    size="compact"
  />
</FilterField>
```

**Visual:**
- Input height: 36px (`size="compact"`)
- Placeholder: Lighter gray
- Real-time filtering (debounced, optional)

### Number Range
Filter by numeric range (min/max).

```tsx
<FilterField wide={true}>
  <Label>Quantity Range</Label>
  <div className="grid grid-cols-2 gap-2">
    <Input 
      type="number" 
      placeholder="Min"
      value={minQty}
      onChange={(e) => setMinQty(e.target.value)}
      size="compact"
    />
    <Input 
      type="number" 
      placeholder="Max"
      value={maxQty}
      onChange={(e) => setMaxQty(e.target.value)}
      size="compact"
    />
  </div>
</FilterField>
```

**Visual:**
- Two inputs side-by-side
- Gap: 8px
- Each: 50% width, 36px height
- Use `wide={true}` so they have room (spans 2 grid columns on XL)

### Date Range
Filter by date range (from/to).

```tsx
<FilterField wide={true}>
  <Label>License Issue Date</Label>
  <div className="grid grid-cols-2 gap-2">
    <Input 
      type="date" 
      value={startDate}
      onChange={(e) => setStartDate(e.target.value)}
      size="compact"
    />
    <Input 
      type="date" 
      value={endDate}
      onChange={(e) => setEndDate(e.target.value)}
      size="compact"
    />
  </div>
</FilterField>
```

**Visual:**
- Same as number range (two inputs, 50% width, 8px gap)
- Date pickers: Native browser (mobile: mobile picker, desktop: calendar)

### Toggle / Switch
Binary on/off filter.

```tsx
<FilterField>
  <div className="flex items-center justify-between gap-2">
    <Label>Show Warnings Only</Label>
    <Switch 
      checked={showWarnings}
      onCheckedChange={setShowWarnings}
    />
  </div>
</FilterField>
```

**Visual:**
- Label on left, switch on right
- Switch size: 40px wide × 24px tall
- Flexbox with justify-between

### Autocomplete / Async Select
Filter with dynamic options (API search).

```tsx
<FilterField>
  <Label>Exporter</Label>
  <DebouncedAsyncSelect 
    options={exporterOptions}
    onChange={setExporter}
    placeholder="Search exporters..."
    isClearable
    isMulti
  />
</FilterField>
```

**Visual:**
- Input-like trigger with dropdown
- Loading state: spinner while fetching options
- Selected: Show badge/chip for each value (if multi)
- Clear: X icon to clear

---

## Active Filter Indicators

Show which filters are currently active (applied).

### In Header
```
3 active
```

**Visual:**
- Display only if activeCount > 0
- Text: 12px, gray (`text-muted-foreground`)
- Position: Header, left side after "Filters" text

### As Badges (Optional)
Show active filters as removable badges.

```tsx
<div className="flex flex-wrap gap-1 mb-2">
  {activeFilters.map((filter) => (
    <div key={filter.key} className="inline-flex items-center gap-1 bg-brand-50 border border-brand-100 rounded-md px-2 py-1 text-xs">
      <span>{filter.label}: {filter.value}</span>
      <button 
        onClick={() => removeFilter(filter.key)}
        className="hover:opacity-70"
      >
        <X className="size-3" />
      </button>
    </div>
  ))}
</div>
```

**Visual:**
- Background: `--tb-brand-50` (#EFF6FF, light blue)
- Border: `--tb-brand-100` (#DBEAFE)
- Text: 12px, dark blue
- Icon: 12px X to remove
- Margin-right: 4px between badges
- Padding: 4px vertical, 8px horizontal

---

## Clear Filters Button

```tsx
<Button 
  type="button" 
  variant="ghost" 
  size="sm" 
  onClick={onClear}
  disabled={clearDisabled}
>
  <X className="size-3.5" />
  Clear Filters
</Button>
```

**States:**
- **Default:** Visible, clickable (if any filters active)
- **Disabled:** When no filters active or isUpdating (grayed out)
- **Hover:** Subtle background (ghost variant)
- **Active:** Scale down slightly

**Position:** Header, right-aligned (`ml-auto`)

---

## Responsiveness

### Desktop (xl+)
```
4 columns (25% width each)
Multiple fields fit horizontally
Wide fields span 2 columns
```

### Tablet (sm-lg)
```
2 columns (50% width each)
Some wide fields break to 100%
Compact layout
```

### Mobile (< sm)
```
1 column (100% width)
All fields stack vertically
Full-width inputs
```

**Adaptive behavior:**
- FilterGrid handles grid responsive automatically
- Inputs adapt to their container width
- Labels remain single-line
- No horizontal scroll

---

## Filter Behavior & Logic

### Apply Filters
Filters apply **in real-time** or on **explicit Apply action** (depending on page).

**Real-time (preferred):**
- User changes filter value
- Immediately triggers query refetch (debounced 300ms)
- Show "Updating..." state during refetch
- No separate Apply button

**Explicit Apply:**
- User changes filter values
- Filter panel shows "Apply" button (disabled until changes made)
- User clicks Apply
- Query refetches
- Panel returns to default state

### Clear Filters
```
onClick: Clear all active filters
Action: Reset all filter fields to initial state
Query: Refetch with no filters
```

### Filter Persistence
- URL query params: Optionally persist filters in URL (`?status=active&exporter=ACME`)
- Local state: Always available for current session
- LocalStorage: Optional for user preference (save/load filter presets)

---

## Common Filter Patterns

### License List Page
```tsx
<FilterPanel activeCount={activeCount} onClear={handleClear}>
  <FilterGrid>
    <FilterField>
      <Label>Status</Label>
      <Select value={status} onValueChange={setStatus}>
        {/* Options */}
      </Select>
    </FilterField>
    
    <FilterField>
      <Label>Condition</Label>
      <div className="space-y-2">
        <Checkbox /> AU
        <Checkbox /> 2%
        <Checkbox /> ...
      </div>
    </FilterField>
    
    <FilterField>
      <Label>License Number</Label>
      <Input placeholder="DFIA-2024-*" />
    </FilterField>
    
    <FilterField wide={true}>
      <Label>Issue Date</Label>
      <div className="grid grid-cols-2 gap-2">
        <Input type="date" placeholder="From" />
        <Input type="date" placeholder="To" />
      </div>
    </FilterField>
  </FilterGrid>
</FilterPanel>
```

### Allotment List Page
```tsx
<FilterPanel activeCount={activeCount} onClear={handleClear}>
  <FilterGrid>
    <FilterField>
      <Label>License</Label>
      <DebouncedAsyncSelect options={licenseOptions} />
    </FilterField>
    
    <FilterField>
      <Label>Item Code</Label>
      <Input placeholder="e.g., 8704.10" />
    </FilterField>
    
    <FilterField>
      <Label>Quantity Range</Label>
      <div className="grid grid-cols-2 gap-2">
        <Input type="number" placeholder="Min" />
        <Input type="number" placeholder="Max" />
      </div>
    </FilterField>
    
    <FilterField>
      <div className="flex items-center justify-between">
        <Label>Active Only</Label>
        <Switch checked={activeOnly} onCheckedChange={setActiveOnly} />
      </div>
    </FilterField>
  </FilterGrid>
</FilterPanel>
```

---

## Accessibility (WCAG AA)

### Labels
- Every filter field has a `<Label>`
- Label text is clear and concise
- Labels linked to inputs via `htmlFor` (for Select/Input)

### Keyboard Navigation
- Tab: Move between filter fields
- Shift+Tab: Move backward
- Enter: Submit form (if Apply button exists)
- Arrow keys: Navigate select options

### ARIA
- Filter panel: `aria-label="Filters"` on `<section>`
- Active count: `aria-live="polite"` to announce count change
- Clear button: Disabled state via `disabled` attribute (not `aria-disabled`)

### Visual Indicators
- Focus ring: 3px on all inputs
- Active filters: Clear visual badge/indicator
- Updating state: Loading spinner + text

### Color & Contrast
- All labels: 4.5:1 contrast minimum
- Filter inputs: Same as standard inputs (AA contrast)
- Active badges: Sufficient contrast (dark text on light bg)

---

## Filter Panel API

```typescript
interface FilterPanelProps {
  children: ReactNode;
  activeCount: number;           // Number of active filters
  isUpdating?: boolean;          // Show "Updating..." state (default: false)
  onClear: () => void;           // Clear all filters
  clearDisabled?: boolean;       // Disable clear button (default: false)
}

interface FilterGridProps {
  children: ReactNode;
}

interface FilterFieldProps {
  children: ReactNode;
  wide?: boolean;                // Span 2 columns on XL (default: false)
}
```

---

## Current vs V2

| Current | V2 | Changes |
|---------|----|----|
| FilterPanel wrapper | FilterPanel + FilterGrid + FilterField | Split into composed components |
| Grid layout | Fixed 4-col XL, 2-col sm, 1-col mobile | Standardized responsive |
| Field spacing | Manual | Use FilterField wrapper (auto-spacing) |
| Wide fields | Manual `xl:col-span-2` | `wide={true}` prop |
| Active count | Display in header | Keep (right side) |
| Clear button | Ghost variant | Keep (right-aligned) |
| Loading state | Support existing | Keep + document |
| Responsive | Good | Confirm on mobile |

---

## Implementation Checklist

**Components to create/update:**
1. ✓ FilterPanel — reuse existing (no changes needed)
2. ✓ FilterGrid — reuse existing (no changes needed)
3. ✓ FilterField — reuse existing (document `wide` prop)
4. Create: FilterMultiSelect (checkbox group helper)
5. Create: FilterDateRange (date pair helper)
6. Create: FilterNumberRange (number pair helper)
7. Update: DebouncedAsyncSelect (ensure compact size support)

---

## File Changes

**Update existing:**
- `frontend/src/components/filters/FilterPanel.tsx` — Document API, add TypeScript

**Create new:**
- `frontend/src/components/filters/FilterMultiSelect.tsx`
- `frontend/src/components/filters/FilterDateRange.tsx`
- `frontend/src/components/filters/FilterNumberRange.tsx`

---

## Token References

- `--tb-border`: Border color (#E4E7EC)
- `--tb-border-soft`: Light border (#EEF0F4)
- `--tb-card-bg`: Panel background (white)
- `--tb-text`: Label color (#111827)
- `--tb-text-tertiary`: Muted text (#9CA3AF)
- `--tb-brand-50`: Active badge background (#EFF6FF)
- `--tb-brand-100`: Active badge border (#DBEAFE)
- `--tb-sp-3`: 12px (filter gap)
- `--tb-r-md`: 8px (filter border-radius)

---

**END OF SPECIFICATION**
