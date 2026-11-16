# Card System V2

**Last Updated:** 2026-09-25  
**Owner:** Product Designer  
**Scope:** All data cards, entity cards, and stat cards across the License Manager SPA

## Overview

The card system defines reusable container components for organizing information into digestible, scannable units. This spec ensures consistency, proper hierarchy, and dense data presentation suitable for enterprise applications.

## Design Principles

- **Enterprise density:** Compact, scannable layouts that respect user attention
- **Token-driven:** All values map to design tokens (`--tb-*` in `theme/tabler.css`)
- **No oversizing:** Avoid pill-shaped cards or excessive whitespace
- **Subtle elevation:** Use shadows to distinguish depth, never as decoration
- **Semantic color:** Status/tone via `TONE_MAP` from `theme/tokens.js`, never ad-hoc colors

---

## Card Variants

### 1. Default (Data Card)

Standard card for displaying information without special treatment.

**Usage:** General data display, lists, details sections

**Styling:**
- Background: `--tb-card-bg` (white/dark-themed)
- Border: 1px `--tb-border`
- Radius: `--tb-r-md` (8px)
- Shadow: `--tb-shadow-0` (subtle edge line)
- Padding: 16-20px
- Spacing between cards: 16px

**Component:** `<Card>` from `frontend/src/components/ui/card.tsx`

```tsx
<Card>
  <CardHeader>
    <CardTitle>Title</CardTitle>
    <CardDescription>Subtitle</CardDescription>
  </CardHeader>
  <CardContent>Content here</CardContent>
</Card>
```

### 2. Raised (Elevated)

Card with subtle elevation for interactive or primary content.

**Usage:** Stat cards, action-driven cards, secondary CTAs

**Styling:**
- Background: `--tb-card-bg`
- Border: 1px `--tb-border` (soft)
- Radius: `--tb-r-md` (8px)
- Shadow: `--tb-shadow-1` (default), `--tb-shadow-2` (on hover)
- Padding: 16-20px
- Transition: `box-shadow var(--tb-tx-base)` on hover
- Hover state: Shadow escalates to shadow-2, optional subtle lift

**Component:** `StatCard` or custom wrapper

```tsx
<button className="... shadow-sm hover:shadow-md transition-shadow ...">
  Card content
</button>
```

### 3. Flat (Border Only)

Minimal card with border-only treatment, no shadow.

**Usage:** Form sections, secondary content, grouped data

**Styling:**
- Background: `--tb-card-bg`
- Border: 1px `--tb-border`
- Radius: `--tb-r-md` (8px)
- Shadow: none
- Padding: 16-20px

```tsx
<div className="bg-card border border-border rounded-lg p-5 ...">
  Content
</div>
```

### 4. Accent (Highlighted)

Card with left-side tone indicator for status or semantic meaning.

**Usage:** List items with status, entity cards with priority indicators

**Styling:**
- Background: `--tb-card-bg`
- Border: 1px `--tb-border`
- Border-left: 3px + semantic color (success, danger, warning, info, primary)
- Radius: `--tb-r-md` (8px)
- Shadow: `--tb-shadow-0`
- Padding: 16-20px
- Tone colors: from `ACCENT_MAP` in `theme/tokens.js`

**Component:** `EntityCard`

```tsx
<div className="border border-border border-l-4 border-l-success ...">
  {/* 3px accent color on left edge */}
</div>
```

---

## Sizing & Spacing

### Card Dimensions

| Property | Value | Notes |
|----------|-------|-------|
| Padding (standard) | 16-20px | Horizontal 20px, vertical 16px |
| Padding (compact) | 12-16px | For dense lists or mobile |
| Border radius | 8px (`--tb-r-md`) | Enterprise, not pill-shaped |
| Min width | 100% (flex container) | Responsive, never fixed width |
| Max width | Constrained by parent | Usually `max-w-screen-xl` on container |

### Internal Spacing

**CardHeader:**
- Padding: 20px (top/sides), 16px (bottom) — or use gap for spacing
- Gap between elements: 8px (between title and chips)
- Border-bottom: 1px `--tb-border-soft` (when followed by content)

**CardContent:**
- Padding: 20px (top/sides), 20px (bottom)
- Border-top: 1px `--tb-border-soft` (when preceded by header)

**CardFooter:**
- Padding: 20px (top/sides), 20px (bottom)
- Border-top: 1px `--tb-border-soft` (when preceded by content)
- Flexbox: `flex items-center` to align buttons/actions

### Spacing Between Cards

| Context | Gap | Token | Notes |
|---------|-----|-------|-------|
| Vertical stack | 16px | `--tb-sp-4` | Default list spacing |
| Compact list | 8px | `--tb-sp-2` | Dense presentations (tables) |
| Relaxed view | 24px | `--tb-sp-6` | Spacious dashboard layouts |

---

## Component Library Reference

### `<Card>` (shadcn base)

**File:** `frontend/src/components/ui/card.tsx`

**Current issue:** `rounded-xl` (16px) is too large. **Should be `--tb-r-md` (8px).**

**Components:**
- `Card` — main container
- `CardHeader` — header section with light background
- `CardTitle` — title text
- `CardDescription` — subtitle/description
- `CardContent` — main content area
- `CardFooter` — footer with actions

**Recommended fix:**
```tsx
// Change line 10 from:
"rounded-xl border shadow-sm",
// To:
"rounded-lg border shadow-sm", // or use --tb-r-md variable
```

### `EntityCard` (custom component)

**File:** `frontend/src/components/primitives/EntityCard.tsx`

**CSS:** `frontend/src/theme/tabler.css` (lines 924–1015)

**Current state:** Good structure, but needs padding adjustments

**Props:**
- `accent`: tone (primary, success, warning, danger, info, neutral)
- `title`: reference number or main label
- `headerChips`: array of small labels/badges
- `statusBadges`: array of status indicators
- `summary`: array of key-value stats
- `actions`: array of action buttons
- `detail`: expandable detail section
- `onView`: controlled open state

**Styling adjustments needed:**
- Header padding: increase from 5px to 12px vertical
- Body padding: increase from 6px to 12px vertical
- Card spacing: increase from 4px to 16px between cards

### `StatCard` (custom component)

**File:** `frontend/src/components/StatCard.tsx`

**Current state:** Excellent, already follows V2 principles

**Props:**
- `label`: uppercase label (auto-formatted)
- `value`: primary metric
- `icon`: lucide-react component
- `tone`: semantic color
- `compact`: boolean for dense layouts
- `secondaryValue`: muted helper text
- `title`: hover tooltip

**Styling:** Already uses proper spacing, shadows, and transitions

---

## Card States

### Default

- Shadow: `--tb-shadow-0` (subtle edge)
- Border: `--tb-border`
- Background: `--tb-card-bg`

### Hover (Interactive Cards)

- Shadow: `--tb-shadow-1` or `--tb-shadow-2`
- Border: `--tb-border` or `--tb-border-strong`
- Transform: optional `translate-y-[-2px]` for subtle lift
- Transition: `var(--tb-tx-base)` (160ms)

### Focus (Keyboard Navigation)

- Outline: `--tb-ring` (3px focus ring around card)
- Box-shadow: add focus ring to existing shadow

### Disabled/Loading

- Opacity: 0.6
- Cursor: `not-allowed`
- Pointer-events: `none`
- Background: can use skeleton loaders

### Selected (List Items)

- Background: `var(--tb-sunken)` or `--tb-brand-50` (tinted)
- Border: highlight with brand color
- Shadow: optional subtle lift

---

## Border & Shadow System

### Border Hierarchy

| Tier | Token | Usage |
|------|-------|-------|
| Soft | `--tb-border-soft` | Interior dividers, subtle separations |
| Default | `--tb-border` | Card borders, main outlines |
| Strong | `--tb-border-strong` | Focus/active states, emphasis |

### Shadow Depth

| Level | Token | Usage |
|-------|-------|-------|
| 0 | `--tb-shadow-0` | Subtle edge line (cards at rest) |
| 1 | `--tb-shadow-1` | Raised cards, hover state |
| 2 | `--tb-shadow-2` | Elevated cards, active state |
| 3 | `--tb-shadow-3` | Modals, popovers, important overlays |

---

## Typography Within Cards

### Header

- Font size: `--tb-fs-md` (14.5px) or `--tb-fs-base` (13.5px)
- Font weight: `--tb-fw-semibold` (600)
- Color: `--tb-text` (primary foreground)
- Letter spacing: -0.01em (tight)

### Description

- Font size: `--tb-fs-sm` (12px)
- Font weight: `--tb-fw-normal` (400)
- Color: `--tb-text-secondary`

### Body

- Font size: `--tb-fs-base` (13.5px)
- Font weight: `--tb-fw-normal` (400)
- Color: `--tb-text`

### Labels (within EntityCard)

- Font size: `--tb-fs-xs` (11px)
- Font weight: `--tb-fw-semibold` (600)
- Color: `--tb-text-tertiary`
- Transform: `uppercase`
- Letter spacing: 0.06em

---

## Responsive Behavior

### Desktop (≥1024px)

- Standard padding: 20px
- Card gap: 16px
- Full details visible

### Tablet (720px–1023px)

- Padding: 16px
- Card gap: 12px
- Might stack actions vertically

### Mobile (<720px)

- Padding: 12px
- Card gap: 8px
- Actions wrap or stack
- Full-width cards with margin constraints
- Compact state enabled where available

---

## Accessibility

### Hit Targets

- Card click areas: minimum 44px height (WCAG touch target)
- Action buttons within cards: minimum 32px
- Spacing between clickable elements: minimum 8px

### Focus

- Focus rings: `--tb-ring` or `--tb-ring-danger` on destructive actions
- Keyboard navigation: cards should be focusable if interactive
- Tab order: logical flow through card actions

### Color

- Never rely on color alone for meaning
- Use icon + color for status badges
- Sufficient contrast: AA minimum (4.5:1 for small text, 3:1 for large)

### Motion

- Transitions: respect `prefers-reduced-motion`
- Duration: use `--tb-tx-fast` (100ms) or `--tb-tx-base` (160ms)
- Easing: `--tb-ease` (cubic-bezier(0.22, 1, 0.36, 1))

---

## Dark Mode

All card styling automatically adapts via CSS variables:
- `--tb-card-bg` → dark background in dark mode
- `--tb-border` → light border in dark mode
- `--tb-text` → light text in dark mode
- `--tb-sunken` → darker surface for headers

No additional work needed; test with `[data-theme="dark"]` attribute on root element.

---

## Validation Checklist

Before shipping card designs:

- [ ] Border radius is `--tb-r-md` (8px), not 12px or 16px
- [ ] Padding is 16–20px, not excessive or too tight
- [ ] Shadow is `--tb-shadow-0` or `--tb-shadow-1`, never custom
- [ ] Colors map to tokens (no hardcoded hex)
- [ ] Status colors use `TONE_MAP` from `theme/tokens.js`
- [ ] Hover state includes shadow transition
- [ ] Focus state includes keyboard ring
- [ ] Responsive behavior tested on mobile
- [ ] Spacing between cards is consistent (16px default)
- [ ] Typography matches spec (font size, weight, color)
- [ ] Accessibility: focus rings, contrast, hit targets
- [ ] Dark mode tested with `[data-theme="dark"]`

---

## Common Patterns

### Single Stat Card

```tsx
<StatCard
  label="Total Orders"
  value="1,245"
  icon={ShoppingCart}
  tone="primary"
/>
```

### Entity Card (with expandable detail)

```tsx
<EntityCard
  accent="success"
  title="License #ABC123"
  headerChips={[{ label: "Active", icon: "Check" }]}
  statusBadges={[{ tone: "success", label: "Approved" }]}
  summary={[
    { label: "Quantity", value: "500 MT", tone: "primary" },
    { label: "Balance", value: "250 MT" },
  ]}
  actions={[
    { icon: "Eye", onClick: () => {}, label: "View" },
    { icon: "Pencil", onClick: () => {}, label: "Edit" },
  ]}
  detail={() => <div>Detailed information here</div>}
/>
```

### Form Section Card

```tsx
<Card>
  <CardHeader>
    <CardTitle>Personal Information</CardTitle>
  </CardHeader>
  <CardContent className="space-y-4">
    <FormField label="Name" placeholder="..." />
    <FormField label="Email" placeholder="..." />
  </CardContent>
  <CardFooter className="gap-2">
    <Button>Save</Button>
    <Button variant="outline">Cancel</Button>
  </CardFooter>
</Card>
```

---

## Migration Path

### From V1 to V2

1. **Card component:**
   - Change `rounded-xl` to `rounded-lg`
   - Verify padding is 16–20px
   - Ensure shadow is from token

2. **EntityCard:**
   - Increase header padding from 5px to 12px vertical
   - Increase body padding from 6px to 12px vertical
   - Increase card gap from 4px to 16px

3. **StatCard:**
   - Already compliant; no changes needed

4. **Custom cards:**
   - Audit for hardcoded values
   - Replace with tokens
   - Ensure consistency with variants

---

## Files to Update

- `frontend/src/components/ui/card.tsx` — Fix `rounded-xl` → `rounded-lg`
- `frontend/src/theme/tabler.css` — Already defines entity card styles; verify paddings
- Tests — ensure card spacing/sizing tests pass
