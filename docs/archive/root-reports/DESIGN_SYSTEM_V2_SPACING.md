# Enterprise Spacing System V2
## License Manager Design System

**Last Updated:** 2026-09-25  
**Version:** 2.0  
**Status:** Reference Specification

---

## Executive Summary

This document defines a **4-point/8-point rhythm spacing scale** that ensures:
- **Consistent visual density** across the application
- **Appropriate whitespace** for enterprise UIs (not oversized)
- **Fast, predictable layouts** using a 12-value scale
- **Dark mode parity** (spacing unchanged)
- **Responsive behavior** (stacked on mobile, same units)

---

## 1. Core Spacing Scale (4pt/8pt Rhythm)

### Primary Scale Values (pixels)

| Token | Size | Usage |
|-------|------|-------|
| **sp-1** | 4px | Micro-gaps, icon spacing, tight packing |
| **sp-2** | 8px | Default gap, component padding (small), form field spacing |
| **sp-3** | 12px | Component padding (medium), list item spacing |
| **sp-4** | 16px | Section padding, card padding (default) |
| **sp-5** | 20px | Large spacing, button padding |
| **sp-6** | 24px | Section spacing, page padding, card padding (large) |
| **sp-8** | 32px | Major section spacing, container spacing |
| **sp-10** | 40px | Large container spacing, page edge padding |
| **sp-12** | 48px | Very large sections, vertical rhythm breaker |
| **sp-16** | 64px | Page section gaps, major visual breaks |

### CSS Variables (theme/tabler.css)
```css
:root {
    --tb-sp-1: 4px;
    --tb-sp-2: 8px;
    --tb-sp-3: 12px;
    --tb-sp-4: 16px;
    --tb-sp-5: 20px;
    --tb-sp-6: 24px;
    --tb-sp-8: 32px;
    --tb-sp-10: 40px;
    --tb-sp-12: 48px;
    --tb-sp-16: 64px;
}
```

### JavaScript Token Map (tokens.js)
```javascript
export const tokens = {
    spacing: {
        1: 4,    // sp-1
        2: 8,    // sp-2
        3: 12,   // sp-3
        4: 16,   // sp-4
        5: 20,   // sp-5
        6: 24,   // sp-6
        8: 32,   // sp-8
        10: 40,  // sp-10
        12: 48,  // sp-12
        16: 64   // sp-16
    }
};
```

---

## 2. Component Spacing Rules

### Button (Primary Control)

| Property | Value | Rationale |
|----------|-------|-----------|
| **Height** | 36–40px | Touch-friendly on mobile, compact on desktop |
| **Padding (vertical)** | 8px | Control height - 2 * border ÷ 2 |
| **Padding (horizontal)** | 16px | Matches sp-4 |
| **Icon margin** | 8px | Breathing room between icon and text |
| **Gap (multiple buttons)** | 8px or 12px | Group cohesion |

```css
.btn {
    height: 36px;
    padding: 8px 16px;
    gap: 8px;
}
.btn-group {
    gap: 8px; /* Default spacing between buttons */
}
.btn-group.lg {
    gap: 12px; /* Looser spacing in headers */
}
```

### Form Field

| Element | Spacing | Rationale |
|---------|---------|-----------|
| **Label to input** | 6px | 1.5 × 4pt, visual connection |
| **Input height** | 36px | Matches --tb-control-md |
| **Padding (vertical)** | 8px | Centered with icon |
| **Padding (horizontal)** | 12px | Icon breathing room |
| **Field to field** | 12–16px | Group separation |
| **Group to next group** | 24px | Clear visual break |

```css
.form-group-material {
    margin-bottom: 12px; /* Default field spacing */
}
.form-group-material.lg {
    margin-bottom: 16px; /* Grouped sections */
}
label {
    margin-bottom: 6px; /* Tight label-to-control connection */
}
.form-group-set {
    margin-bottom: 24px; /* Between field groups */
}
```

### Card (Container)

| Property | Value | Usage |
|----------|-------|-------|
| **Padding** | 16px–20px | Default card body padding |
| **Padding (compact)** | 12px | Dense lists, narrow cards |
| **Padding (spacious)** | 24px–32px | Large modal dialogs |
| **Header padding** | 16px (top/sides) | Matches card body |
| **Border** | 1px solid border | Subtle definition |
| **Border radius** | 8px | --tb-r-md |
| **Shadow** | var(--tb-shadow-0) or shadow-1 | Raised from bg |
| **Gap (internal items)** | 8px–12px | List item spacing within card |

```css
.card {
    border-radius: 8px;
    border: 1px solid var(--tb-border);
    box-shadow: var(--tb-shadow-0);
}
.card-body {
    padding: 16px;
}
.card-body.compact {
    padding: 12px;
}
.card-body.spacious {
    padding: 24px;
}
.card-header {
    padding: 16px;
    border-bottom: 1px solid var(--tb-border-soft);
}
```

### List Item

| Context | Spacing | Height |
|---------|---------|--------|
| **Dense list (table-like)** | 8px gap, 36px row | Tables, data grids |
| **Standard list** | 12px gap, 40px item | Most lists, menu items |
| **Relaxed list** | 16px gap, 44px item | Touch-friendly mobile |

```css
.list-dense li {
    min-height: 36px;
    padding: 8px 12px;
}
.list-standard li {
    min-height: 40px;
    padding: 10px 12px;
}
.list-relaxed li {
    min-height: 44px;
    padding: 12px 16px;
}
```

---

## 3. Page & Section Spacing

### Page Layout

| Zone | Padding | Margin Bottom |
|------|---------|-----------------|
| **Page header** | 24px top, 24px sides | 24px |
| **Section title + intro** | 0 padding | 16px below title, 8px below intro |
| **Section content** | inherit page padding | 24px between sections |
| **Page edge (desktop)** | 24px–32px | — |
| **Page edge (mobile)** | 16px | — |

### Example Structure
```jsx
<section className="space-y-6">
    {/* Page header: 24px bottom margin */}
    <PageHeader title="Licenses" />
    
    {/* Section 1: 24px margin-bottom */}
    <section className="space-y-4">
        <div className="space-y-1">
            <h2>Active Licenses</h2>
            <p className="text-sm text-muted-foreground">Status overview</p>
        </div>
        <div>Data here</div>
    </section>
    
    {/* Section 2: 24px margin above (via outer space-y-6) */}
    <section>...</section>
</section>
```

### CSS
```css
.dashboard-page,
.list-page,
.detail-page {
    padding: 24px 24px; /* Desktop */
}
@media (max-width: 768px) {
    .page {
        padding: 16px;
    }
}

.page-section {
    margin-bottom: 24px;
}
.section-title {
    margin-bottom: 8px;
}
.section-intro {
    margin-bottom: 16px;
}
```

---

## 4. Table Spacing

### Row Height Contract
```css
:root {
    --tb-table-row: 36px; /* Compact, enterprise standard */
}
```

| Style | Height | Padding v | Padding h | Use Case |
|-------|--------|-----------|-----------|----------|
| **Compact** | 32px | 6px | 12px | Dense master data tables |
| **Standard** | 36px | 8px | 12px | Most tables (default) |
| **Relaxed** | 40px | 10px | 12px | Touch-friendly, mobile |
| **Spacious** | 44px–48px | 12px | 16px | Modal tables with detail |

### Table Structure
```css
table {
    width: 100%;
    border-collapse: collapse;
}

thead th {
    height: 36px;
    padding: 8px 12px;
    border-bottom: 2px solid var(--tb-border-strong);
    font-size: 12px;
    font-weight: 500;
}

tbody td {
    padding: 8px 12px;
    height: 36px;
    border-bottom: 1px solid var(--tb-border-soft);
}

tbody tr:hover {
    background-color: var(--row-hover-bg);
}

/* Actions column spacing */
td.actions {
    padding: 4px 8px; /* Tighter for button group */
}
.table-actions {
    display: flex;
    gap: 4px;
}
```

### Column Spacing
| Column Type | Padding | Align | Width |
|-------------|---------|-------|-------|
| **Text (description)** | 12px h | left | auto |
| **Number (amount, qty)** | 12px h | right | auto |
| **Date** | 12px h | center | 120px |
| **Status** | 12px h | center | auto |
| **Action buttons** | 8px h | center | auto |

---

## 5. Dialog / Modal Spacing

### Modal Container
| Property | Value |
|----------|-------|
| **Body padding** | 24px (top/sides), 24px (bottom) |
| **Header padding** | 24px |
| **Footer padding** | 16px |
| **Gap (header to content)** | 8px (implicit from padding) |
| **Gap (content to footer)** | 16px–24px |

```css
[role="dialog"],
.modal-content {
    padding: 24px;
    max-width: 500px;
}

[role="dialog"] .modal-header {
    margin-bottom: 16px;
    padding-bottom: 16px;
    border-bottom: 1px solid var(--tb-border-soft);
}

[role="dialog"] .modal-footer {
    margin-top: 24px;
    padding-top: 16px;
    border-top: 1px solid var(--tb-border-soft);
    display: flex;
    gap: 8px;
    justify-content: flex-end;
}
```

### Confirm Dialog
```css
.confirm-dialog {
    padding: 24px;
}
.confirm-dialog .dialog-body {
    margin-bottom: 24px;
}
.confirm-dialog .dialog-actions {
    display: flex;
    gap: 12px;
    justify-content: flex-end;
}
```

---

## 6. Filter Card Spacing

### Filter Container (Sidebar / Header)
| Property | Value |
|----------|-------|
| **Padding** | 16px |
| **Field group spacing** | 12px |
| **Label margin** | 6px below |
| **Control height** | 36px |
| **Button height** | 36px |
| **Divider spacing** | 12px top/bottom |

```css
.filter-card {
    padding: 16px;
    border-radius: 8px;
    border: 1px solid var(--tb-border);
    background-color: var(--tb-card-bg);
}

.filter-field {
    margin-bottom: 12px;
}

.filter-field:last-child {
    margin-bottom: 0;
}

.filter-actions {
    display: flex;
    gap: 8px;
    margin-top: 16px;
}
```

### Responsive Filter (Mobile)
- On mobile: full-width drawer or stacked card
- Padding: 16px (same as desktop for consistency)
- Button heights: 44px (touch target)

---

## 7. Grid & Layout Spacing

### Grid Gap (Responsive)

| Breakpoint | Gap (gap-x/gap-y) | Usage |
|------------|-------------------|-------|
| **Mobile (<640px)** | 12px | Stat cards, tight packing |
| **Tablet (640–1024px)** | 16px | Stat grid, card grids |
| **Desktop (>1024px)** | 20px–24px | 3+ column layouts |

```jsx
{/* Stat cards */}
<div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 lg:grid-cols-5 xl:gap-4">
    <StatCard ... />
</div>

{/* Card grid */}
<div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3 lg:gap-6">
    <Card ... />
</div>
```

### Flex Gap
| Context | Gap | Rationale |
|---------|-----|-----------|
| **Button group** | 8px | Cohesion, not too spread |
| **Breadcrumb** | 4px | Tight, icon + text + separator |
| **Inline badges** | 8px | Item separation |
| **Header actions** | 12px–16px | Right-aligned action buttons |

```css
.button-group { gap: 8px; }
.breadcrumb { gap: 4px; }
.inline-badges { gap: 8px; }
.page-actions { gap: 12px; }
```

---

## 8. Responsive Spacing Adjustments

### Mobile (< 640px)
- **Page padding:** 16px (down from 24px)
- **Section gap:** 16px (down from 24px)
- **Card padding:** 12px (down from 16px)
- **Form field gap:** 12px (same)
- **Button height:** 44px (up from 36–40px for touch)

### Tablet (640–1024px)
- **Page padding:** 20px–24px
- **Section gap:** 20px
- **Card padding:** 16px
- **Form field gap:** 12px

### Desktop (> 1024px)
- **Page padding:** 24px–32px
- **Section gap:** 24px–32px
- **Card padding:** 16px–20px
- **Form field gap:** 12px–16px

### CSS Media Queries
```css
@media (max-width: 640px) {
    .page { padding: 16px; }
    .section { margin-bottom: 16px; }
    .card { padding: 12px; }
    button { min-height: 44px; }
}

@media (min-width: 640px) and (max-width: 1024px) {
    .page { padding: 20px; }
    .section { margin-bottom: 20px; }
}

@media (min-width: 1024px) {
    .page { padding: 24px; }
    .section { margin-bottom: 24px; }
}
```

---

## 9. Removed: Excessive Whitespace

### Anti-patterns to eliminate:
- ~~Padding > 32px on cards (unless modal)~~
- ~~Margin > 48px between sections (breaks visual rhythm)~~
- ~~Input height > 44px (wastes space)~~
- ~~Table row height > 48px (except special cases)~~
- ~~Form field gaps > 24px (disconnect)~~
- ~~Icon padding > 12px (loose spacing)~~

### Before (Oversized)
```jsx
{/* BAD: Way too much padding */}
<Card className="p-12"> {/* = 48px! */}
    <h2 className="mb-8">Title</h2>
    <p className="mb-12">Content</p>
</Card>
```

### After (Appropriate)
```jsx
{/* GOOD: Consistent 4pt scale */}
<Card className="p-4 space-y-3">
    <h2 className="font-semibold">Title</h2>
    <p className="text-sm">Content</p>
</Card>
```

---

## 10. Semantic Spacing Classes (Tailwind)

### Spacing Scale Mapping
```css
/* Maps --tb-sp-* to Tailwind p/m/gap utilities */
p-1 = 4px    /* padding: 4px */
p-2 = 8px
p-3 = 12px
p-4 = 16px
p-5 = 20px
p-6 = 24px
p-8 = 32px
p-10 = 40px
p-12 = 48px
p-16 = 64px

/* Same for margin, gap, space-y, etc. */
m-4 = margin: 16px
gap-3 = gap: 12px
space-y-4 = > * + * { margin-top: 16px }
```

### Common Tailwind Utilities
```jsx
{/* Padding */}
<div className="p-4">Padded card</div>
<div className="px-6 py-4">Horiz/vert padding</div>

{/* Margin */}
<div className="mb-6">Below section</div>
<div className="mt-4">Above element</div>

{/* Gap / Space */}
<div className="flex gap-3">
    <button>Action 1</button>
    <button>Action 2</button>
</div>
<div className="space-y-4">
    <div>Item 1</div>
    <div>Item 2</div>
</div>
```

---

## 11. Z-Index Spacing (Strata)

### Layer Stack (not pixel spacing, but important)
```css
:root {
    --tb-z-sticky: 20;       /* Sticky headers */
    --tb-z-dropdown: 1000;   /* Dropdowns, popovers */
    --tb-z-modal: 1050;      /* Modals, dialogs */
    --tb-z-tooltip: 1070;    /* Tooltips (highest) */
}
```

**Note:** Z-index spacing is not "spacing" per se, but follows the same hierarchy principle.

---

## 12. Accessibility Implications

### Touch Target Spacing
- **Minimum button height:** 44px (WCAG 2.5.5)
- **Minimum button width:** 44px (square icons)
- **Gap between targets:** 8px minimum (to avoid accidental clicks)
- **Responsive:** Enforced at mobile breakpoint

```css
@media (max-width: 768px) {
    button, a.btn, input[type="button"] {
        min-height: 44px;
        min-width: 44px;
    }
    /* Ensure gap between clickables */
    button + button {
        margin-left: 8px;
    }
}
```

### Spacing for Clarity
- **Section breaks (24px+):** Help screen reader users understand content structure
- **List item spacing (8–12px):** Reduces cognitive load
- **Form field spacing (12px+):** Clear grouping and separation

---

## 13. Dark Mode & Spacing

**No changes.** Spacing values are identical in dark mode:
- Padding: unchanged
- Margin: unchanged
- Gap: unchanged
- Only **colors** change (shadows, borders adjust)

---

## 14. Implementation Checklist

- [x] Audit: 4pt/8pt scale defined in tabler.css
- [x] Audit: Control heights set (32–44px range)
- [ ] Consolidate: Remove arbitrary margins/padding from components
- [ ] Standardize: Enforce scale via Tailwind config
- [ ] Add: Semantic spacing classes (e.g., `.section-gap-24`)
- [ ] Test: Responsive spacing at 320px, 768px, 1024px
- [ ] Test: Touch targets on mobile (44px min)
- [ ] Document: Update component guidelines
- [ ] Migrate: Convert hardcoded `margin: 20px` → `m-5`
- [ ] Audit: Remove > 48px spacing (unless justified)

---

## 15. Examples

### Example 1: Page with Sections
```jsx
<section className="space-y-6">
    <PageHeader title="Licenses" />
    <section className="space-y-4">
        <h2 className="text-lg font-semibold">Active Licenses</h2>
        <p className="text-sm text-muted-foreground">Status overview</p>
        <div className="grid grid-cols-2 gap-4 md:grid-cols-5">
            {/* 4px cards */}
        </div>
    </section>
    <section className="space-y-4">
        <h2>Recent Activity</h2>
        {/* More content */}
    </section>
</section>
```

### Example 2: Form with Groups
```jsx
<form className="space-y-6">
    <div className="space-y-4">
        <h3>Personal Info</h3>
        <div className="space-y-3">
            <FormField label="Name" />
            <FormField label="Email" />
        </div>
    </div>
    <div className="space-y-4">
        <h3>Preferences</h3>
        <div className="space-y-3">
            <FormField label="Theme" />
        </div>
    </div>
    <div className="flex gap-3 justify-end">
        <Button>Cancel</Button>
        <Button>Save</Button>
    </div>
</form>
```

### Example 3: Table with Actions
```jsx
<table>
    <thead>
        <tr>
            <th className="px-3 py-2">License #</th>
            <th className="px-3 py-2">Status</th>
            <th className="px-3 py-2">Actions</th>
        </tr>
    </thead>
    <tbody>
        <tr className="h-9">
            <td className="px-3">LIC-001</td>
            <td className="px-3"><Badge>Active</Badge></td>
            <td className="px-2">
                <div className="flex gap-1">
                    <Button size="sm" variant="ghost">Edit</Button>
                    <Button size="sm" variant="ghost">Delete</Button>
                </div>
            </td>
        </tr>
    </tbody>
</table>
```

---

## References

- **4-point grid:** [Material Design Spacing](https://material.io/design/layout/spacing-methods.html)
- **Modular scale:** [Tailwind spacing scale](https://tailwindcss.com/docs/customizing-spacing)
- **Touch targets:** [WCAG 2.5.5 Target Size](https://www.w3.org/WAI/WCAG21/Understanding/target-size.html)
- **Responsive design:** [Mobile-first CSS](https://www.mobileresponsive.org/)

