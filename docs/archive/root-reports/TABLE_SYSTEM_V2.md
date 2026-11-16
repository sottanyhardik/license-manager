# Table System V2

**Last Updated:** 2026-09-25  
**Owner:** Product Designer  
**Scope:** All data tables, data grids, and list presentations

## Overview

The table system defines compact, enterprise-grade data presentations with clear hierarchy, sortable columns, and professional interactions. Tables are the primary way users browse, search, and act on data in the License Manager.

## Design Principles

- **Enterprise density:** Row height 44px, header 44px, optimized for scanning dense datasets
- **Clear hierarchy:** Headers distinct from body, visual separation between rows
- **Scannable alignment:** Numeric columns right-aligned with tabular numerals, text left-aligned
- **Interactive feedback:** Hover, selection, sort, focus states all defined
- **Token-driven:** All colors/spacing from design tokens, never hardcoded values

---

## Table Structure

### Header Row

**Height:** 44px (tight, professional)  
**Padding:** 12px horizontal, 12px vertical (total ~48px with borders)  
**Background:** `--tb-sunken` (light background to distinguish from body)  
**Typography:**
- Font size: 12px (`--tb-fs-sm`)
- Font weight: 600 (`--tb-fw-semibold`)
- Color: `--tb-text`
- Transform: uppercase
- Letter spacing: 0.06em

**Styling:**
```css
.table > thead > tr > th {
    background: var(--tb-sunken);
    color: var(--tb-text);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    font-weight: var(--tb-fw-semibold);
    font-size: 12px;
    padding: 12px 16px;
    border-bottom: 1px solid var(--tb-border);
    white-space: nowrap;
}
```

**Features:**
- Sticky positioning (optional, but recommended for tall tables)
- No hover effect on headers
- Clear visual separation from body via bottom border

### Data Row

**Height:** 44px (compact, scannable)  
**Padding:** 12px horizontal, 12px vertical (~48px total with borders)  
**Background:** `--tb-card-bg` (matches card backgrounds)  
**Typography:**
- Font size: 13px (`--tb-fs-base`)
- Font weight: 400 (normal)
- Color: `--tb-text`
- Line height: 1.5

**Styling:**
```css
.table > tbody > tr > td {
    padding: 12px 16px;
    border-bottom: 1px solid var(--tb-border-soft);
    vertical-align: middle;
    font-size: 13px;
    line-height: 1.5;
}
```

**Features:**
- Consistent padding across all cells
- Subtle bottom border between rows
- Proper vertical centering for mixed content

---

## Row States

### Default

- Background: `--tb-card-bg`
- Border-bottom: 1px `--tb-border-soft`
- Cursor: `default` (unless clickable)

### Hover

- Background: `var(--row-hover-bg)` or `--tb-sunken`/`--tb-brand-50`
- Transition: `background-color var(--tb-tx-fast)` (100ms)
- Box-shadow: optional `inset 0 0 0 1px rgba(var(--tb-primary-rgb), 0.1)`
- Cursor: `pointer` (if clickable)

**CSS:**
```css
.table-hover > tbody > tr:hover > td {
    background: var(--tb-sunken);
    transition: background-color var(--tb-tx-fast);
}
```

### Selected

- Background: `--tb-brand-50` or lighter tint
- Border-left: 3px `--tb-brand` (accent)
- Font weight: optional semibold
- Checkbox: checked state visible

### Focus (Keyboard Navigation)

- Outline: `--tb-ring` around the row or cell
- Box-shadow: combine with existing shadow
- Tab stops on actionable cells only

### Loading

- Entire table: skeleton rows with pulse animation
- Spinner icon in top-left corner
- Prevent interaction until loaded

### Empty State

- Message centered in table body area
- Icon + heading + description
- Optional "Create" or "Import" button

---

## Column Types

### Text Columns (Left-aligned)

```css
.table td {
    text-align: left;
}
```

- Default alignment for all text content
- Line-clamp to prevent overflow on long strings
- Tooltip on hover if truncated

### Numeric Columns (Right-aligned)

```css
.table td.numeric,
.table td .tabular-nums {
    text-align: right;
    font-variant-numeric: tabular-nums;
}
```

**Rules:**
- Right-aligned for scannability
- Tabular numerals (consistent-width digits for tables)
- Used for: amount, price, rate, cost, total, quantity, balance, etc.
- Currency: formatted with separators (1,26,90,443.00)
- No wrapping; truncate if necessary with tooltip

**Detection in DataTable component:**
```javascript
const NUMERIC_PATTERNS = [
    "amount", "price", "rate", "cost", "total", "subtotal",
    "quantity", "qty", "weight", "count", "inr", "usd",
    "fc", "cif", "fob", "balance", "pct", "percent"
];
```

### Date Columns

```css
.table td.date {
    text-align: left;
    font-family: var(--tb-font-mono);
    font-size: 12px;
}
```

- Format: YYYY-MM-DD or per locale (ISO standard)
- Monospace font for clarity
- Centered (optional) for visual grouping

### Status/Badge Columns

- Center-aligned (optional)
- Use `TONE_MAP` colors from `theme/tokens.js`
- Badge or chip component (small, compact)
- Example: `<span className="inline-flex ... bg-success/10 text-success">Active</span>`

### Action Columns

- Right-aligned or center-aligned
- Icons only, no text (save space)
- Grouped in a single column at the end
- Minimum 32px × 32px hit target per button

---

## Sorting & Filtering

### Sort Indicators

**Header column with sort:**
```tsx
<th className="cursor-pointer select-none group">
  Column Name
  <ChevronUp className="inline ml-1 opacity-0 group-hover:opacity-100" />
</th>
```

**Indicators:**
- Up arrow: ascending
- Down arrow: descending
- No arrow: unsorted
- Appear on hover; stay visible when active

**Styling:**
- Icon color: `--tb-text-tertiary`
- Active: `--tb-brand`
- Transition: `opacity var(--tb-tx-fast)`

### Filter State

- Filter button in header (optional global filter)
- Visual indicator: badge on column header (e.g., "Active filters: 3")
- Clear all / reset button near table controls

---

## Pagination

**Location:** Below table  
**Height:** ~44px (including spacing)  
**Components:**
- Previous/Next buttons
- Page number input or selectors
- "Showing X–Y of Z" text
- Optional: items-per-page selector (10, 25, 50, 100)

**Styling:**
```tsx
<div className="flex items-center justify-between px-4 py-3 border-t border-border">
  <span className="text-sm text-muted-foreground">
    Showing 1–25 of 500
  </span>
  <div className="flex gap-2">
    <Button variant="outline" size="sm">Previous</Button>
    <Button variant="outline" size="sm">Next</Button>
  </div>
</div>
```

---

## Sticky Header

For scrollable tables (especially tall data):

```css
.table-sticky-head thead th {
    position: sticky;
    top: 0;
    z-index: var(--tb-z-sticky);
}
```

**Notes:**
- Header stays visible when scrolling
- Shadows help distinguish sticky header from scrolling content
- Works best with compact row heights

---

## Empty State

Display when table has no data after filters/search:

```tsx
<div className="flex flex-col items-center px-6 py-12 text-center">
  <span className="mb-3 flex size-12 items-center justify-center rounded-lg border border-border/60 bg-muted/50">
    <Inbox className="size-5 text-muted-foreground/50" />
  </span>
  <p className="text-sm font-semibold text-foreground">No records found</p>
  <p className="mt-1 text-xs text-muted-foreground">
    Try adjusting your search or filter criteria
  </p>
</div>
```

**Styling:**
- Icon: 48px container, `--tb-border`, light background
- Heading: 13px semibold
- Subtext: 12px, muted color
- Full table width, centered, 40–48px top/bottom padding

---

## Loading State

Skeleton rows with placeholder content:

```tsx
<table>
  <thead>
    <tr>
      {columns.map(() => (
        <th><Skeleton className="h-2.5 w-3/5" /></th>
      ))}
    </tr>
  </thead>
  <tbody>
    {[...Array(6)].map((_, i) => (
      <tr key={i}>
        {columns.map(() => (
          <td><Skeleton className="h-3 w-2/3" /></td>
        ))}
      </tr>
    ))}
  </tbody>
</table>
```

**Features:**
- Skeleton height: 10px text, 12px for larger content
- Randomized widths (60%, 70%, 80%) to feel natural
- Pulse animation: `animate-pulse` Tailwind utility
- Full table height: 6–8 rows

---

## Inline Actions

Cells that allow direct editing without modal:

### Single-click Edit

```tsx
// Read mode
<td onClick={() => setEditing(true)}>
  <span className="group relative">
    {value}
    <Pencil className="ml-1 opacity-0 group-hover:opacity-100" size={14} />
  </span>
</td>

// Edit mode
<td>
  <div className="flex items-center gap-1">
    <input type="text" className="... h-8 px-2 py-1" value={editValue} />
    <button className="... bg-success text-white"><Check size={16} /></button>
    <button className="... bg-muted text-muted-foreground"><X size={16} /></button>
  </div>
</td>
```

**Features:**
- Pencil icon appears on cell hover
- Click to activate inline input
- Confirm/cancel buttons visible
- On blur or Enter: save; on Escape: cancel
- Disabled state during save

### Boolean Toggle

```tsx
<td onClick={() => handleToggle(item, column)}>
  <label className="inline-flex cursor-pointer items-center">
    <input type="checkbox" role="switch" checked={value} />
    <span className="... w-9 h-5 rounded-full transition-colors" />
  </label>
</td>
```

---

## Custom Renderers

Cells can use custom rendering logic:

```tsx
customCellRender={{
  status: (item, value) => (
    <span className="inline-flex items-center rounded-full bg-success/10 px-2 py-1 text-xs text-success">
      {value}
    </span>
  ),
  amount: (item, value) => (
    <span className="tabular-nums text-right">{formatCurrency(value)}</span>
  ),
}}
```

**Uses:**
- Status badges with semantic colors
- Currency/number formatting
- Links to detail pages
- Progress bars
- Custom icons

---

## Responsive Behavior

### Desktop (≥1024px)

- Full table displayed
- All columns visible
- Horizontal scroll if necessary (with indication)
- Sticky header on scroll

### Tablet (720px–1023px)

- Some columns may hide (e.g., descriptions)
- Action buttons stack vertically
- Font size: 12px (slightly smaller)
- Padding: 10px (slightly tighter)

### Mobile (<720px)

- Table switches to card layout (`.table-responsive-mobile`)
- Each row becomes a stacked card
- Column label (`data-label`) appears before value
- Single action button per row
- Full width with left/right padding

```css
@media (max-width: 720px) {
    .table-responsive-mobile tbody tr {
        display: flex;
        flex-direction: column;
        gap: 8px;
        margin-bottom: 12px;
        border: 1px solid var(--tb-border);
        border-radius: var(--tb-r-md);
        padding: 12px;
    }
    .table-responsive-mobile td {
        display: flex;
        justify-content: space-between;
    }
    .table-responsive-mobile td::before {
        content: attr(data-label);
        font-weight: var(--tb-fw-semibold);
        text-transform: uppercase;
        font-size: 10px;
    }
}
```

---

## Accessibility

### Keyboard Navigation

- Tab through headers (if sortable)
- Tab through action buttons only, not data cells (unless editable)
- Arrow keys: skip to next/previous row (optional)
- Enter: open row detail or activate action
- Escape: close detail or cancel edit

**Implementation:**
```tsx
<table role="grid">
  <thead role="row">
    <th role="columnheader" tabIndex={sortable ? 0 : -1}>...</th>
  </thead>
  <tbody>
    <tr role="row">
      <td role="gridcell" tabIndex={editable ? 0 : -1}>...</td>
    </tr>
  </tbody>
</table>
```

### Screen Readers

- `<table>` with proper `<thead>`, `<tbody>`, `<th>`/`<td>`
- `aria-label` on table (e.g., "License list")
- `scope="col"` on `<th>`
- `scope="row"` on first column (if applicable)
- Action buttons: `aria-label="Edit row"`, `aria-label="Delete row"`

### Focus Ring

- Outline: `--tb-ring` or `--tb-ring-danger` on destructive
- Visible on header sort buttons, data cell edit buttons, pagination

### Color & Contrast

- Never rely on color alone for status
- Use icon + text + color (e.g., red X icon + "Error" text)
- Minimum 4.5:1 contrast for text, 3:1 for graphics

---

## Dark Mode

All table styling automatically adapts:
- `--tb-card-bg` → dark in dark mode
- `--tb-sunken` → darker background for header
- `--tb-border` → light border in dark mode
- `--tb-text` → light text
- Hover background uses appropriate dark-mode color

Test with `[data-theme="dark"]` on root element.

---

## Performance Considerations

- **Virtual scrolling:** For 1000+ rows, use virtualization library (e.g., `react-window`)
- **Lazy loading:** Paginate data; load page on demand
- **Memoization:** Use `React.memo` on table components to avoid re-renders
- **Stable sort:** Use server-side sorting for large datasets
- **Debounce search:** Wait 300–500ms before querying API

---

## Common Patterns

### Basic Data Table

```tsx
<DataTable
  columns={["license_number", "exporter", "amount", "balance"]}
  data={licenses}
  onEdit={(item) => openDetail(item)}
  onDelete={(item) => deleteItem(item)}
/>
```

### Sortable & Filterable Table

```tsx
<div>
  <div className="mb-4 flex gap-2">
    <input
      placeholder="Search licenses..."
      onChange={(e) => setSearch(e.target.value)}
    />
    <button onClick={() => setSortBy("date")}>Sort by Date</button>
  </div>
  <DataTable
    columns={["number", "date", "qty", "value"]}
    data={filteredData}
  />
</div>
```

### Inline Editable Table

```tsx
<DataTable
  columns={["name", "email", "active"]}
  data={users}
  inlineEditable={["email", "active"]}
  onInlineUpdate={(id, field, value) => updateUser(id, field, value)}
/>
```

### Responsive Card Layout (Mobile)

Automatically converts on mobile via `.table-responsive-mobile` class.

---

## Component Reference

**File:** `frontend/src/components/DataTable.tsx`

**Props:**
- `data`: array of objects
- `columns`: array of column names
- `onEdit`: function(item) — edit button callback
- `onDelete`: function(item) — delete button callback
- `customActions`: array of { icon, label, onClick }
- `loading`: boolean — show skeleton
- `inlineEditable`: array of column names that can be edited
- `onInlineUpdate`: function(id, field, value) — save callback
- `customCellRender`: object mapping column to render function
- `getRowStyle`: function(item) — conditional row styling

---

## Validation Checklist

Before shipping table designs:

- [ ] Row height is 44px (not oversized)
- [ ] Header height is 44px with 12px padding
- [ ] All borders use `--tb-border` token
- [ ] Header background is `--tb-sunken`
- [ ] Numeric columns are right-aligned with `tabular-nums`
- [ ] Hover state includes background transition
- [ ] Focus ring is `--tb-ring`
- [ ] Empty state displays friendly message
- [ ] Loading state shows skeleton rows
- [ ] Sticky header works on scroll
- [ ] Keyboard navigation works (Tab, Arrow, Enter, Escape)
- [ ] Screen reader labels present (`aria-label`, `scope`)
- [ ] Mobile responsive tested (<720px)
- [ ] Dark mode tested with `[data-theme="dark"]`
- [ ] Action buttons have min 32px hit target
- [ ] Sorting/filtering UI clear and accessible

---

## Files to Update

- `frontend/src/components/DataTable.tsx` — Main table component
- `frontend/src/theme/tabler.css` — Table styling (already good, verify)
- Mobile table CSS — ensure `.table-responsive-mobile` works as expected
