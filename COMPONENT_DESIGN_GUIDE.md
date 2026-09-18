# Component Design Guide

**License Manager UI Modernization**  
**Date**: 2026-09-18

---

## Design Principles

1. **Premium Enterprise**: Think Linear, Stripe, Vercel, Notion
2. **Strong Hierarchy**: Intentional use of typography, spacing, color
3. **Data Density**: Compact but readable; financial values scannable
4. **Subtle Motion**: Only where it improves UX
5. **Dark Mode Parity**: Perfect light/dark support
6. **Accessibility First**: WCAG AA minimum
7. **Consistency**: Predictable patterns across the app

---

## TYPOGRAPHY HIERARCHY

### Page Titles (h1)
- Size: 26px (--tb-fs-2xl)
- Weight: 600 (semibold)
- Line height: 1.2
- Letter spacing: -0.015em
- Color: --tb-text (foreground)
- Margin: 0 (handle in PageHeader)
- **Usage**: Top of page, unique per route

```tsx
<h1 className="text-2xl font-semibold tracking-tight">Dashboard</h1>
```

### Section Titles (h2)
- Size: 20px (--tb-fs-xl)
- Weight: 600 (semibold)
- Line height: 1.25
- Color: --tb-text (foreground)
- **Usage**: Major sections within a page

```tsx
<h2 className="text-xl font-semibold">License Health</h2>
```

### Card Titles (h3)
- Size: 16px (--tb-fs-lg)
- Weight: 600 (semibold)
- Line height: 1.35
- **Usage**: Card headers, subsection titles

```tsx
<h3 className="text-lg font-semibold">Recent Allotments</h3>
```

### Body Text
- Size: 13.5px (--tb-fs-base)
- Weight: 400 (normal)
- Line height: 1.5
- Color: --tb-text (foreground)
- **Usage**: Primary readable content

```tsx
<p className="text-base">This is body text.</p>
```

### Secondary Text
- Size: 12px (--tb-fs-sm)
- Weight: 400 (normal)
- Color: --tb-text-secondary
- **Usage**: Descriptions, metadata, lesser importance

```tsx
<p className="text-sm text-muted-foreground">Last updated 2 hours ago</p>
```

### Small/Tertiary Text
- Size: 11px (--tb-fs-xs)
- Weight: 500 (medium)
- Color: --tb-text-tertiary or --tb-text-secondary
- **Usage**: Labels, hints, metadata
- **Letter spacing**: 0.05em or 0.06em for uppercase

```tsx
<label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
  License Number
</label>
```

---

## SPACING SCALE (4px Grid)

### Consistent Gaps Between Elements

| Token | Pixels | Usage |
|-------|--------|-------|
| sp-1 | 4px | Minimal gaps (within components) |
| sp-2 | 8px | Small gaps (icon+text in buttons, items in lists) |
| sp-3 | 12px | Moderate gaps (form field gaps) |
| sp-4 | 16px | Default gaps (between sections, card padding) |
| sp-5 | 20px | Large gaps (between major sections) |
| sp-6 | 24px | XL gaps (section separation) |
| sp-8 | 32px | Page-level gaps |

### Component-Specific Rules

**Button**:
- Padding: 0.4375rem (7px) vertical × 0.875rem (14px) horizontal
- Icon + text gap: 8px
- Icon only: center in button

**Card**:
- Padding: 16px (sp-4)
- Header padding: 12px 16px (with border below)
- Body padding: 16px
- Footer padding: 10px 16px (with border above)

**Table**:
- Row height: 36px (--tb-table-row)
- Cell padding: 10px 14px
- Header padding: 9px 14px
- Gap between columns: 14px horizontal

**Form Field**:
- Label to input: 4px (sp-1)
- Input to help text: 4px (sp-1)
- Field to field: 12px (sp-3)
- Form group internal gap: 8px (sp-2)

**Page Spacing**:
- Page padding (horizontal): clamp(14px, 2vw, 28px)
- Page padding (vertical): 20px (sp-5) top, 32px (sp-8) bottom
- Section to section: 20px (sp-5) or 24px (sp-6)

---

## COLOR USAGE

### Primary Brand Color
- Color: #2563EB (--tb-brand)
- Usage: Main actions, primary buttons, active states, links
- Rule: **Use sparingly** — one primary action per page section
- **Don't**: Don't color everything blue

### Status Colors (Semantic)
- **Success**: #16A34A (--tb-success) — completed, positive
- **Danger**: #DC2626 (--tb-danger) — error, critical
- **Warning**: #D97706 (--tb-warning) — attention, caution
- **Info**: #0891B2 (--tb-info) — information, neutral positive

### Text Color Hierarchy
- **Primary**: --tb-text (#111827) — main readable text
- **Secondary**: --tb-text-secondary (#5E6673) — descriptions, labels
- **Tertiary**: --tb-text-tertiary (#9CA3AF) — hints, metadata, disabled
- **Muted**: --tb-text-muted (#C4C9D4) — very subtle text

### Neutral Surfaces
- **Body background**: --tb-body-bg (#F5F6FA light, #0D1117 dark)
- **Card background**: --tb-card-bg (#FFFFFF light, #161B22 dark)
- **Sunken background**: --tb-sunken (#F8F9FB light, #0D1117 dark)
- **Border**: --tb-border (#E4E7EC light, #21262D dark)

### Tone Mapping (from tokens.js)
Use TONE_MAP for status-colored badges/chips:
```js
TONE_MAP = {
  primary:  { bg: var(--tb-brand-50),      fg: var(--tb-brand-active),   ... },
  success:  { bg: var(--tb-success-soft),  fg: var(--tb-success-text),   ... },
  warning:  { bg: var(--tb-warning-soft),  fg: var(--tb-warning-text),   ... },
  danger:   { bg: var(--tb-danger-soft),   fg: var(--tb-danger-text),    ... },
  info:     { bg: var(--tb-info-soft),     fg: var(--tb-info-text),      ... },
  neutral:  { bg: var(--tb-sunken),        fg: var(--tb-text-secondary), ... }
}
```

---

## ELEVATION & SHADOWS

### Shadow System

| Level | CSS Variable | Usage |
|-------|---|---|
| 0 | --tb-shadow-0 | Minimal (1px border) |
| 1 | --tb-shadow-1 | Subtle (default cards) |
| 2 | --tb-shadow-2 | Card hover, elevated sections |
| 3 | --tb-shadow-3 | Dropdowns, modals, popovers |
| overlay | --tb-shadow-overlay | Full-page modals |

### Elevation Rules
- **Default card**: shadow-0 (just border)
- **Interactive card** (hoverable): shadow-2 on hover
- **Dropdown**: shadow-3
- **Modal**: shadow-overlay
- **Sticky header**: shadow-1 (subtle, doesn't interfere)

---

## BORDER & RADIUS

### Border Radius Scale
- sm: 6px — buttons, small components
- md: 8px — cards, modals, default radius
- lg: 10px — larger modals, special components
- xl: 14px — full-page modals (modals should feel special)
- pill: 999px — pill buttons, badges when needed

### Border Colors
- **Default**: --tb-border (#E4E7EC light, #21262D dark)
- **Soft**: --tb-border-soft (#EEF0F4 light, #1E2530 dark)
- **Strong**: --tb-border-strong (#CDD2DA light, #30363D dark)
- Rule: Use soft for light dividers, strong for emphasis

---

## COMPONENT SPECIFICATIONS

### Button

**Base Styling**:
```tsx
<button className="btn btn-primary">Action</button>
```

**Variants**:
- `btn-primary` — Solid blue, for primary actions
- `btn-outline-primary` — Outline blue, for secondary actions
- `btn-light` — Subtle, for tertiary actions
- `btn-danger` — Red, for destructive actions
- `btn-outline-secondary` — Minimal, for quaternary actions

**Sizes**:
- `btn` (default) — 36px height, normal text
- `btn-sm` — 32px height, smaller text (12px)
- `btn-lg` — 40px height, larger text

**States**:
- **Hover**: Darker shade, enhanced shadow
- **Active**: Scale down slightly (0.98)
- **Disabled**: opacity 0.5, cursor not-allowed
- **Focus**: Outline ring (--tb-ring)
- **Loading**: Show spinner, disable interactions

### Card

**Structure**:
```tsx
<div className="card">
  <div className="card-header">Title</div>
  <div className="card-body">Content</div>
  <div className="card-footer">Actions</div>
</div>
```

**Styling**:
- Border: 1px solid --tb-border
- Radius: 8px (md)
- Shadow: --tb-shadow-0 (default), --tb-shadow-2 (hover)
- Padding: 16px (body)

**Variants**:
- `.card` — Standard card
- `.card.card-hoverable` — Clickable card with hover effect
- `.surface-panel` — Alternative name for .card

### Input

**Styling**:
- Padding: 0.4375rem 0.75rem
- Border: 1px solid --tb-border
- Radius: 6px (sm)
- Font: 13.5px (base)

**States**:
- **Focus**: border-primary, ring focus
- **Disabled**: sunken background, tertiary text, opacity 0.75
- **Invalid**: border-danger, ring-danger

### Badge

**Structure**:
```tsx
<span className="badge bg-primary">Primary</span>
<span className="badge bg-success">Success</span>
<span className="badge bg-danger">Danger</span>
```

**Styling**:
- Padding: 3px 8px
- Font size: 11px
- Font weight: 500 (medium)
- Border: 1px solid (tone-specific)
- Radius: 6px (sm)

### Table

**Styling**:
- Font size: 13px
- Border collapse: separate
- Border spacing: 0
- Row height: 36px

**Header**:
- Background: --tb-sunken
- Color: --tb-text-secondary
- Font size: 11px
- Font weight: 600 (semibold)
- Text transform: uppercase
- Letter spacing: 0.05em
- Padding: 9px 14px
- Border bottom: 1px solid --tb-border

**Body**:
- Padding: 10px 14px
- Border bottom: 1px solid --tb-border-soft
- **Hover**: background: var(--row-hover-bg) (light blue soft)

**Numeric Columns**:
- Text align: right
- Font family: Consider tabular numerals (font-variant-numeric: tabular-nums)

### Modal

**Structure**:
```tsx
<div className="modal-dialog">
  <div className="modal-content">
    <div className="modal-header">Title</div>
    <div className="modal-body">Content</div>
    <div className="modal-footer">Actions</div>
  </div>
</div>
```

**Styling**:
- Border radius: 14px (xl)
- Shadow: --tb-shadow-overlay
- Modal backdrop: opacity 0.5
- Header border: 1px solid --tb-border (bottom)
- Footer background: --tb-sunken
- Footer border: 1px solid --tb-border (top)

---

## COMPOUND COMPONENTS (Custom)

### PageHeader
**Purpose**: Consistent page structure  
**Location**: `components/PageHeader.tsx`

**Structure**:
```tsx
<PageHeader
  pretitle="Home"
  title="Dashboard"
  description="Current status and recent activity"
  actions={<Button>Action</Button>}
/>
```

**Styling**:
- Border: 1px solid --tb-border/70
- Background: --tb-card-bg
- Border radius: 12px (rounded-xl)
- Padding: 16px 20px (sm: 20px 24px)
- Shadow: --tb-shadow-sm

**Pretitle**: 11px, uppercase, tracking-wide, --tb-text-tertiary

**Title**: 26px, font-bold, tracking-tight

**Description**: 13px, --tb-text-secondary

### StatCard
**Purpose**: KPI display  
**Location**: `components/StatCard.tsx`

**Structure**:
```tsx
<StatCard
  label="Active Licenses"
  value={42}
  icon={FileText}
  tone="primary"
  onClick={handleClick}
/>
```

**Styling**:
- Border: 1px solid --tb-border
- Background: --tb-card-bg
- Border radius: 8px (md)
- Padding: 16px 18px
- Min height: 90px
- Shadow: --tb-shadow-0, hover: --tb-shadow-2

**Icon**:
- Size: 40px × 40px
- Border radius: 8px (md)
- Background: tone-specific soft color
- Color: tone-specific text color

**Label**: 11px, uppercase, tracking-wide, --tb-text-tertiary

**Value**: 22px, font-semibold, tracking-tight

**Hover State**: Elevated shadow, cursor pointer

### DataTable
**Purpose**: Complex data display  
**Location**: `components/DataTable.tsx`

**Features**:
- Skeleton loading
- Inline editing
- Custom cell rendering
- Row styling
- Action buttons

**Enhancements Needed**:
- Better numeric alignment (right-align, tabular numerals)
- Improved header styling (uppercase, tracking)
- Better row hover (more obvious)
- Sticky headers
- Column visibility controls

### FilterBar
**Purpose**: Unified filter experience  
**Location**: `components/FilterBar.tsx` (CREATE)

**Structure**:
```tsx
<FilterBar>
  <FilterField label="Status">
    <Select options={...} />
  </FilterField>
  <FilterField label="Date Range">
    <DateRangePicker />
  </FilterField>
  <Button onClick={handleClear}>Clear Filters</Button>
</FilterBar>
```

**Styling**:
- Border: 1px solid --tb-border
- Background: --tb-card-bg
- Border radius: 8px (md)
- Padding: 10px 14px
- Shadow: --tb-shadow-0
- Gap: 8px
- Flex wrap: wrap

### EmptyState
**Purpose**: No-data feedback  
**Location**: `components/EmptyState.tsx`

**Structure**:
```tsx
<EmptyState
  icon={Inbox}
  title="No licenses"
  description="Create your first license to get started."
  action={<Button>Create License</Button>}
/>
```

**Styling**:
- Padding: 48px 24px
- Text align: center
- Color: --tb-text-tertiary

**Icon**: 40px, --tb-text-muted, opacity 0.6

**Title**: 14px (md), font-semibold, --tb-text-secondary

**Description**: 12px (sm), --tb-text-tertiary, max-width 300px

---

## COMPONENT VARIANT DECISIONS

### When to Use Each Button Style

| Situation | Button Style | Example |
|-----------|---|---|
| Page primary action | `btn-primary` | "Create License" |
| Page secondary action | `btn-outline-primary` | "Export", "View All" |
| Tertiary action | `btn-light` | "Cancel", "More options" |
| Destructive action | `btn-danger` | "Delete", "Remove" |
| Quaternary action | `btn-outline-secondary` | Minimal actions in dense layouts |

### When to Create a Card

- Grouping related content
- Containing a section with distinct background
- Wrapping a form
- Displaying a repeating item

### When NOT to Create a Card

- Simple inline content
- Overuse causes "box fatigue"
- Consider white space instead
- Dark surfaces (--tb-sunken) can replace some cards

---

## ANIMATION & MOTION

### Transition Timing

| Variable | Duration | Use |
|---|---|---|
| --tb-tx-fast | 100ms | Small state changes (hover) |
| --tb-tx-base | 160ms | Standard transitions |
| --tb-tx-slow | 280ms | Page transitions |

### Page Transition
```tsx
<div className="page-enter">Content</div>
```
- Duration: 200ms
- Animation: Fade in + slight translate Y (6px)
- Easing: cubic-bezier(0.22, 1, 0.36, 1)

### Rules
- Don't animate more than necessary
- Fast transitions are better than slow
- Disable animations for users with prefers-reduced-motion

---

## DARK MODE

### Color Variables Used
All colors use CSS variables from tabler.css:
- `--tb-brand`, `--tb-brand-hover`, `--tb-brand-active`
- `--tb-text`, `--tb-text-secondary`, `--tb-text-tertiary`
- `--tb-border`, `--tb-card-bg`, `--tb-body-bg`
- Status colors (success, danger, warning, info)

### Dark Mode Declaration
```css
[data-theme="dark"] {
  /* Dark-specific overrides */
}
```

### Testing
- Always test both light and dark modes
- Ensure sufficient contrast in both modes
- Check status colors readability

---

## ACCESSIBILITY CHECKLIST

- [ ] Semantic HTML (button, link, heading tags)
- [ ] Focus states visible (ring or outline)
- [ ] Color not the only indicator
- [ ] Keyboard navigation works
- [ ] ARIA labels where needed
- [ ] Image alt text
- [ ] Form labels properly associated
- [ ] Focus order logical
- [ ] Skip nav links (if needed)
- [ ] Screen reader testing
- [ ] Contrast ratio ≥ 4.5:1 for text

---

## IMPLEMENTATION CHECKLIST

### For Each Component Update
- [ ] Update styling to follow this guide
- [ ] Test in light and dark modes
- [ ] Test on mobile/tablet
- [ ] Verify keyboard navigation
- [ ] Check focus states
- [ ] Update component stories/docs if applicable
- [ ] Run tests
- [ ] Get design approval

---

**This guide drives all component styling decisions for the modernization.**
