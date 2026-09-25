# License Manager - Component Specifications

## Overview

This document specifies the standard component patterns used across the License Manager application. All new features and refactored pages must conform to these specifications.

**Last Updated:** 2026-09-25  
**Components Location:** `/frontend/src/components/`  
**UI Primitives:** `/frontend/src/components/ui/` (shadcn-based)

---

## 1. PageHeader Component

Standard header for all major pages. Provides breadcrumb, title, description, and action buttons in a unified surface.

### Location
`/frontend/src/components/PageHeader.tsx`

### Props

```tsx
interface PageHeaderProps {
    pretitle?: React.ReactNode;      // Breadcrumb/section label
    title?: React.ReactNode;          // Main heading
    description?: React.ReactNode;    // Subtitle or status info
    actions?: React.ReactNode;        // Right-aligned action buttons
    children?: React.ReactNode;       // Custom content (rare)
    className?: string;               // Additional classes
}
```

### Sizing & Spacing

| Aspect | Value | Token |
|--------|-------|-------|
| **Height** | 60–68px (responsive) | Auto-sizing |
| **Padding** | 16px (mobile), 24px (desktop) | `px-4 sm:px-6 py-4 sm:py-5` |
| **Border Radius** | 8px | `r-md` |
| **Shadow** | Minimal (shadow-1) | `shadow-sm` |
| **Gap (flex)** | 20px (x-axis), 16px (y-axis) | `gap-x-5 gap-y-4` |
| **Margin Below** | 24px | `mb-6` |
| **Sticky Top** | 8px | Sticky positioning |
| **Z-Index** | 20 | `--tb-z-sticky` |

### Typography

| Element | Size | Weight |
|---------|------|--------|
| **Pretitle** | `text-[10px]` | `font-bold` |
| **Title** | `text-2xl` (mobile), `text-3xl` (lg) | `font-bold` |
| **Description** | `text-sm` | `font-normal` |

### Visual States

- **Default:** Card with light border, minimal shadow
- **Sticky:** Stays at top-8 on scroll (desktop only)
- **On Mobile:** Position static, full width
- **Dark Mode:** Auto-inverts via Tabler tokens

### Usage Example

```tsx
<PageHeader
    pretitle="Administration"
    title="License Ledger"
    description="Download and manage complete license transactions"
    actions={<Button size="sm">Download</Button>}
/>
```

### Common Issues to Avoid

- Do NOT hardcode padding — use Tailwind spacing scale
- Do NOT override the sticky behavior on desktop
- Do NOT use inline styles for colors — use token variables

---

## 2. FilterPanel Component

Collapsible section for filters, search, and sorting controls.

### Spec (To be implemented)

| Aspect | Value | Notes |
|--------|-------|-------|
| **Container Padding** | 16px | `sp-4` |
| **Section Gap** | 16px | `sp-4` |
| **Label Font Size** | 12px | `fs-sm` |
| **Input Height** | 36px | Control md |
| **Border Radius** | 6px | `r-sm` (inputs), `r-md` (buttons) |
| **Background** | `var(--tb-card-bg)` | Card surface |
| **Border Color** | `var(--tb-border)` | Standard border |
| **Shadow** | `var(--tb-shadow-1)` | Minimal elevation |

### Layout

- **Desktop:** Horizontal grid or flex layout
- **Mobile:** Stacked vertical layout (single column)
- **Collapsible Header:** Icon + label + badge (count of active filters)

### Components Within

- Text search input (DebouncedSearchInput)
- Date range picker (DateRangeFilter)
- Select/multi-select dropdowns
- Clear Filters button

### Props Pattern

```tsx
interface FilterPanelProps {
    isOpen?: boolean;                 // Expanded state
    onToggle?: (open: boolean) => void;
    activeFilterCount?: number;        // Show badge on header
    onClearFilters?: () => void;
    children?: React.ReactNode;       // Filter controls
}
```

### Usage Example

```tsx
<FilterPanel activeFilterCount={3} onClearFilters={handleClear}>
    <DebouncedSearchInput value={search} onChange={setSearch} />
    <DateRangeFilter value={dateRange} onChange={setDateRange} />
    <Select value={status} onValueChange={setStatus}>...</Select>
</FilterPanel>
```

---

## 3. Card Component

General-purpose card for grouping content. Based on shadcn `<Card>`.

### Location
`/frontend/src/components/ui/card.tsx`

### Sizing

| Aspect | Value | Token |
|--------|-------|-------|
| **Border Radius** | 10px | `r-lg` |
| **Border Width** | 1px | Standard |
| **Border Color** | `var(--tb-border)` | `border-border/60` (with opacity) |
| **Background** | `var(--tb-card-bg)` | `bg-card` |
| **Shadow** | `var(--tb-shadow-1)` | `shadow-sm` |
| **Padding (CardContent)** | 16px | `p-4` |

### Sub-Components

#### CardHeader

| Property | Value |
|----------|-------|
| **Padding** | 12px 16px (top/bottom/left/right) |
| **Border Bottom** | 1px solid `var(--tb-border)` |
| **Background** | `var(--tb-card-bg)` |
| **Min Height** | Auto (flexible) |

#### CardContent

| Property | Value |
|----------|-------|
| **Padding** | 16px |
| **Min Height** | Auto |

#### CardFooter

| Property | Value |
|----------|-------|
| **Padding** | 16px |
| **Border Top** | 1px solid `var(--tb-border-soft)` |
| **Background** | `var(--tb-sunken)` |

### Usage Example

```tsx
<Card>
    <CardHeader className="border-b px-4 py-3">
        <h2 className="text-lg font-bold">Title</h2>
    </CardHeader>
    <CardContent className="p-4">
        {/* Content */}
    </CardContent>
</Card>
```

### Common Variants

- **Compact:** Reduce padding to `p-3`, gap to 2px
- **Elevated:** Use `shadow-2` instead of `shadow-1`
- **With Icon Header:** Left icon (12px margin-right) + title + right action

---

## 4. Button Component

Universal button based on shadcn `<Button>` with Tabler integration.

### Location
`/frontend/src/components/ui/button.tsx`

### Variants

| Variant | Background | Border | Text | Hover |
|---------|------------|--------|------|-------|
| **solid (default)** | Primary brand | Transparent | White | Brand hover |
| **outline** | Transparent | Border | Primary | Brand-50 bg |
| **secondary** | Sunken/muted | Border | Secondary | Border soft bg |
| **ghost** | Transparent | Transparent | Foreground | Bg accent |
| **destructive** | Danger | Transparent | White | Danger hover |

### Sizes

| Size | Height | Padding (h) | Font Size | Use Case |
|------|--------|------------|-----------|----------|
| **sm** | 32px | 8–10px | 12px | Secondary, compact actions |
| **md** | 36px | 12px | 13px | Standard buttons |
| **lg** | 40px | 16px | 14px | Primary CTA buttons |

### States

- **Default:** Baseline styling
- **Hover:** Lifted with `shadow-2`, border darkened
- **Active:** Scale 0.98, no lift
- **Disabled:** 50% opacity, no cursor

### Loading State

```tsx
<Button disabled={loading}>
    {loading && <Loader2 className="size-4 animate-spin" />}
    {loading ? "Loading..." : "Submit"}
</Button>
```

### Usage Example

```tsx
<Button variant="outline" size="sm">Cancel</Button>
<Button variant="solid" size="md">Save</Button>
<Button variant="destructive" size="sm">Delete</Button>
```

---

## 5. Table Component & TableWrapper

Standardized table styling with sticky headers, density options, and row states.

### Table Header (thead)

| Property | Value |
|----------|-------|
| **Padding** | 8px (compact), 12px (standard) |
| **Background** | `var(--tb-sunken)` |
| **Font Size** | 11px (`fs-xs`) |
| **Font Weight** | 700 (`fw-bold`) |
| **Text Color** | `var(--tb-text-secondary)` |
| **Text Transform** | Uppercase |
| **Sticky** | `position: sticky; top: 0; z-index: 1;` |

### Table Body (tbody)

| Property | Value |
|----------|-------|
| **Row Height** | Minimum 36px (--tb-table-row) |
| **Padding (td)** | 8px (compact), 12px (standard) |
| **Border Bottom** | 1px solid `var(--tb-border-soft)` |
| **Transition** | 150ms background color (hover) |

### Row States

| State | Background | Usage |
|-------|------------|-------|
| **Default** | `var(--tb-card-bg)` | Normal row |
| **Hover** | `color-mix(in srgb, var(--tb-brand) 4%, transparent)` | Interactive rows |
| **Selected** | `var(--tb-brand-50)` | Selected/highlighted |
| **Success (data)** | `#F0FDF4` | Success-indicating rows |
| **Danger (data)** | `#FFF1F2` | Error/danger rows |

### Responsive Table

On mobile (max-width: 768px), use vertical card layout:

- Hide `<thead>`
- Render each row as a bordered card
- Use `data-label` attributes for column names
- Left: label (50% width), Right: value (50% width)

### Sticky Header Pattern

```tsx
<div className="overflow-x-auto">
    <table className="w-full">
        <thead className="sticky top-0 z-10 bg-muted/80 backdrop-blur">
            {/* Headers */}
        </thead>
        <tbody>
            {/* Rows */}
        </tbody>
    </table>
</div>
```

---

## 6. EmptyState Component

Consistent empty state UI when no data is present.

### Location
`/frontend/src/components/EmptyState.tsx`

### Props

```tsx
interface EmptyStateProps {
    icon: React.ElementType;          // Lucide icon
    title: React.ReactNode;            // Main message
    description?: React.ReactNode;    // Secondary message
    action?: React.ReactNode;         // CTA button(s)
    className?: string;
}
```

### Sizing

| Property | Value |
|----------|-------|
| **Min Height** | 96px |
| **Padding** | 16px |
| **Icon Size** | 32px |
| **Icon Color** | `text-muted-foreground` |
| **Title Font** | `text-sm font-semibold` |
| **Description Font** | `text-xs text-muted-foreground` |

### Variants

- **In Card:** Use with card padding context
- **In Section:** With vertical spacing
- **Inline:** Minimal padding, compact

### Usage Example

```tsx
<EmptyState
    icon={Inbox}
    title="No transactions found"
    description="No purchase or sale transactions match the current filters"
    action={<Button size="sm" variant="outline">Create New</Button>}
/>
```

---

## 7. Badge Component

Compact status/tag display with semantic tones.

### Location
`/frontend/src/components/ui/badge.tsx`

### Sizing

| Property | Value |
|----------|-------|
| **Padding** | 2px 8px (compact), 4px 12px (standard) |
| **Border Radius** | 999px (pill) |
| **Font Size** | 11px (`fs-xs`) |
| **Font Weight** | 600 (`fw-semibold`) |
| **Line Height** | 1.6 |
| **White Space** | nowrap |

### Variants (Tones)

| Variant | Background | Text | Usage |
|---------|------------|------|-------|
| **default** | `var(--tb-brand-50)` | `var(--tb-brand-active)` | Primary, informational |
| **success** | `var(--tb-success-soft)` | `var(--tb-success-text)` | Success, positive |
| **warning** | `var(--tb-warning-soft)` | `var(--tb-warning-text)` | Warning, caution |
| **danger** | `var(--tb-danger-soft)` | `var(--tb-danger-text)` | Error, destructive |
| **info** | `var(--tb-info-soft)` | `var(--tb-info-text)` | Information |
| **secondary** | `var(--tb-sunken)` | `var(--tb-text-secondary)` | Neutral, muted |
| **outline** | Transparent | Primary | Outlined variant |

### Usage Pattern

```tsx
<Badge variant="success">Active</Badge>
<Badge variant="warning">Expiring</Badge>
<Badge variant="danger">{daysLeft} days</Badge>
```

---

## 8. Dialog/Modal Component

Standard modal for forms, confirmations, and details.

### Location
`/frontend/src/components/ui/dialog.tsx` (shadcn-based)

### Sizing

| Property | Value |
|----------|-------|
| **Max Width** | 500px (md), 700px (lg) |
| **Border Radius** | 8px (`r-lg`) |
| **Shadow** | `var(--tb-shadow-overlay)` |
| **Padding (DialogContent)** | 24px (desktop), 16px (mobile) |
| **Padding (DialogHeader)** | 0 (use parent padding) |

### Sub-Components

- **DialogTrigger:** Opens dialog
- **DialogContent:** Main container
- **DialogHeader:** Title + close button
- **DialogTitle:** Heading
- **DialogDescription:** Subtitle
- **DialogFooter:** Action buttons (right-aligned)

### Usage Example

```tsx
<Dialog>
    <DialogTrigger asChild>
        <Button>Open</Button>
    </DialogTrigger>
    <DialogContent>
        <DialogHeader>
            <DialogTitle>Confirm Action</DialogTitle>
            <DialogDescription>Are you sure?</DialogDescription>
        </DialogHeader>
        <DialogFooter>
            <Button variant="outline">Cancel</Button>
            <Button>Confirm</Button>
        </DialogFooter>
    </DialogContent>
</Dialog>
```

---

## 9. Input Component

Text input field for forms.

### Location
`/frontend/src/components/ui/input.tsx`

### Sizing

| Property | Value |
|----------|-------|
| **Height** | 36px (md) minimum |
| **Padding** | 6px 12px |
| **Border Radius** | 6px (`r-sm`) |
| **Font Size** | 13.5px (`fs-base`) |
| **Border** | 1px solid `var(--tb-border)` |
| **Background** | `var(--tb-card-bg)` |

### States

- **Default:** Neutral border, white bg
- **Focus:** Brand-colored border, focus ring
- **Error:** Danger-colored border
- **Disabled:** 50% opacity, no cursor

### Focus Ring

```css
&:focus {
    border-color: var(--tb-brand);
    box-shadow: var(--tb-ring);
    outline: none;
}
```

---

## 10. Select Component

Dropdown select field (shadcn-based, built on Radix).

### Location
`/frontend/src/components/ui/select.tsx`

### Sizing

| Property | Value |
|----------|-------|
| **Trigger Height** | 36px (md) |
| **Padding** | 8px 12px |
| **Border Radius** | 6px (`r-sm`) |
| **Shadow (Open)** | `var(--tb-shadow-3)` |
| **Z-Index (Open)** | 1000 (`--tb-z-dropdown`) |

### Content (Dropdown Menu)

| Property | Value |
|----------|-------|
| **Max Height** | 300px (scrollable) |
| **Border Radius** | 6px (`r-sm`) |
| **Shadow** | `var(--tb-shadow-3)` |
| **Item Padding** | 8px 12px |
| **Item Height** | Min 36px |

### Item States

- **Default:** Normal text
- **Hover:** Background `var(--tb-brand-50)`
- **Selected:** Background `var(--tb-brand)`, white text
- **Disabled:** 50% opacity

---

## 11. DataTable Component

Complex table wrapper with sorting, filtering, pagination.

### Location
`/frontend/src/components/DataTable.tsx`

### Features

- Sticky headers (if scrollable)
- Row hover states
- Density option (compact/standard)
- Row selection (optional)
- Responsive mobile layout

### Usage Pattern

```tsx
<DataTable
    columns={columns}
    data={data}
    loading={isLoading}
    onRowClick={(row) => navigate(`/detail/${row.id}`)}
    dense={true}
/>
```

### Density Modes

| Mode | Row Height | Padding | Use |
|------|-----------|---------|-----|
| **Standard** | 36px+ | 12px | Default |
| **Compact** | 32px | 8px | High-volume data |
| **Spacious** | 40px+ | 16px | Detail-focused |

---

## 12. Form Field Pattern

Standard form field wrapper (label + input + error/help text).

### Structure

```tsx
<div className="space-y-2">
    <label className="text-sm font-semibold text-muted-foreground">
        Field Label
        {required && <span className="text-danger ml-1">*</span>}
    </label>
    <input
        type="text"
        className="h-9 w-full rounded-md border border-border px-3 py-1 text-sm"
    />
    {error && <p className="text-xs text-danger">{error}</p>}
    {helpText && <p className="text-xs text-muted-foreground">{helpText}</p>}
</div>
```

### Spacing

- **Label to Input:** 8px (`space-y-2`)
- **Input to Error:** 4px (`mt-1`)
- **Error Font Size:** 11px (`text-xs`)

---

## Implementation Quality Checklist

- [ ] All spacing uses scale (sp-1 through sp-8)
- [ ] All colors use semantic tokens (`--tb-*` variables)
- [ ] All shadows use layered system
- [ ] All radius values conform to spec
- [ ] Dark mode works (no hardcoded hex values)
- [ ] Focus-visible rings present on all interactive elements
- [ ] Accessibility: contrast ratios AA minimum
- [ ] Responsive: tested on mobile/tablet/desktop
- [ ] Reduced motion: animations respect `prefers-reduced-motion`
- [ ] No Bootstrap class fallbacks in new code
- [ ] TypeScript types present and correct
- [ ] PropTypes or JSDoc documented

---

## References

- **UI Primitives:** `/frontend/src/components/ui/`
- **Design Tokens:** `/frontend/DESIGN_TOKENS.md`
- **Tabler Tokens:** `/frontend/src/theme/tabler.css`
- **Tailwind Config:** `/frontend/src/styles/tailwind.css`
- **Example Pages:** Dashboard, LicenseLedger (reference implementations)
