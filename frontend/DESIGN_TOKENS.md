# License Manager Design System - Design Tokens

## Overview

This document defines the unified design token system for the License Manager application. All spacing, sizing, color, typography, and component dimensions must conform to these specifications.

**Last Updated:** 2026-09-25  
**Design System Version:** v2.0 (Tabler + shadcn/ui unified)  
**CSS Token Prefix:** `--tb-*` (root-level CSS variables in `theme/tabler.css`)

---

## 1. Spacing Scale (4-Point Grid)

The spacing system uses a base unit of 4px. All spacing must conform to this scale to maintain visual rhythm and consistency.

| Token | Value | CSS Variable | Usage |
|-------|-------|--------------|-------|
| `sp-1` | 4px | `--tb-sp-1` | Minimal gaps, tight layouts |
| `sp-2` | 8px | `--tb-sp-2` | Small gaps, icon spacing |
| `sp-3` | 12px | `--tb-sp-3` | Section padding, small margins |
| `sp-4` | 16px | `--tb-sp-4` | Standard padding, margins |
| `sp-5` | 20px | `--tb-sp-5` | Card padding, section margins |
| `sp-6` | 24px | `--tb-sp-6` | Large card padding |
| `sp-8` | 32px | `--tb-sp-8` | Major section spacing |
| `sp-10` | 40px | (not yet) | Extra-large section spacing |
| `sp-12` | 48px | (not yet) | Page-level spacing |

### Spacing Usage Rules

- **Page/Section Gaps:** Use `sp-4` (16px) between major sections
- **Card Padding:** Use `sp-4` to `sp-6` (16px–24px) for card content
- **Table Row Height:** 36px minimum (`--tb-table-row: 36px`)
- **Control Height:** 32px (sm), 36px (md), 40px (lg) — see Control Sizing below

---

## 2. Radius Tokens

Border radius values ensure consistent, modern corners throughout the UI.

| Token | Value | CSS Variable | Usage |
|-------|-------|--------------|-------|
| `r-sm` | 6px | `--tb-r-sm` | Small buttons, select inputs, small badges |
| `r-md` | 8px | `--tb-r-md` | Standard buttons, input fields, cards |
| `r-lg` | 10px | `--tb-r-lg` | Large containers, modals |
| `r-xl` | 14px | `--tb-r-xl` | Page headers, large cards, panels |
| `r-pill` | 999px | `--tb-r-pill` | Badges, chips, pills |

### Radius Usage Rules

- **Page Headers:** `r-xl` (14px)
- **Cards:** `r-lg` to `r-xl` (10px–14px)
- **Buttons & Inputs:** `r-sm` to `r-md` (6px–8px)
- **Badges & Chips:** `r-pill` (999px)

---

## 3. Shadow System (Layered Depth)

Shadows create visual hierarchy and elevation. Use the layered system for consistent depth.

| Token | CSS Variable | Usage | CSS Value |
|-------|--------------|-------|-----------|
| **Minimal Border** | `--tb-shadow-0` | Form controls, subtle outlines | `0 0 0 1px rgba(15, 23, 42, 0.04)` |
| **Elevation 1** | `--tb-shadow-1` | Card base elevation, small dropdowns | `0 1px 3px rgba(15, 23, 42, 0.07), 0 1px 2px rgba(15, 23, 42, 0.04)` |
| **Elevation 2** | `--tb-shadow-2` | Hovered cards, floating buttons | `0 4px 8px rgba(15, 23, 42, 0.08), 0 2px 4px rgba(15, 23, 42, 0.04)` |
| **Elevation 3** | `--tb-shadow-3` | Dropdowns, popovers, tooltips | `0 12px 24px rgba(15, 23, 42, 0.1), 0 4px 8px rgba(15, 23, 42, 0.06)` |
| **Overlay** | `--tb-shadow-overlay` | Modals, full-screen overlays | `0 20px 48px rgba(15, 23, 42, 0.16), 0 8px 16px rgba(15, 23, 42, 0.08)` |

### Shadow Usage Rules

- **Cards at rest:** `shadow-1`
- **Cards on hover:** `shadow-2`
- **Dropdown/Popover:** `shadow-3`
- **Modal/Overlay:** `shadow-overlay`

---

## 4. Typography Scale

Font sizes and weights for all text elements. Base font is **Inter** (system fallback provided).

### Font Sizes

| Token | Size (px) | Size (rem) | CSS Variable | Usage |
|-------|-----------|-----------|--------------|-------|
| `fs-xs` | 11px | 0.688rem | `--tb-fs-xs` | Badge text, table labels, captions |
| `fs-sm` | 12px | 0.75rem | `--tb-fs-sm` | Small body text, form labels |
| `fs-base` | 13.5px | 0.844rem | `--tb-fs-base` | Form inputs, default body, table cells |
| `fs-md` | 14.5px | 0.906rem | `--tb-fs-md` | Increased body, emphasized labels |
| `fs-lg` | 16px | 1rem | `--tb-fs-lg` | Page section headings |
| `fs-xl` | 20px | 1.25rem | `--tb-fs-xl` | Larger headings, modals |
| `fs-2xl` | 26px | 1.625rem | `--tb-fs-2xl` | Page titles |

### Font Weights

| Token | Weight | CSS Variable | Usage |
|-------|--------|--------------|-------|
| `fw-normal` | 400 | `--tb-fw-normal` | Body text, default |
| `fw-medium` | 500 | `--tb-fw-medium` | Emphasis, secondary headings |
| `fw-semibold` | 600 | `--tb-fw-semibold` | Badges, buttons, labels |
| `fw-bold` | 700 | `--tb-fw-bold` | Primary headings, card titles |

### Typography Hierarchy

| Element | Font Size | Font Weight | Variant | Usage |
|---------|-----------|-------------|---------|-------|
| **Page Title (h1)** | `fs-2xl` (26px) | `fw-bold` | `font-bold text-2xl` | Main page heading |
| **Section Title (h2)** | `fs-lg` (16px) | `fw-bold` | `font-bold text-lg` | Section headings, card titles |
| **Subsection (h3)** | `fs-md` (14.5px) | `fw-semibold` | `font-semibold text-md` | Subsection headings |
| **Body (p, td)** | `fs-base` (13.5px) | `fw-normal` | `text-base` | Paragraphs, table cells, default text |
| **Small Text** | `fs-sm` (12px) | `fw-normal` | `text-sm` | Helper text, secondary info |
| **Tiny/Label** | `fs-xs` (11px) | `fw-semibold` | `text-xs font-semibold` | Labels, badges, captions |

---

## 5. Color Palette

### Semantic Colors (Status Tones)

Colors are used for semantic meaning: success (green), warning (orange), danger (red), info (blue), and neutral states.

| Tone | Color | Usage | CSS Variables |
|------|-------|-------|----------------|
| **Primary/Brand** | `#2563EB` | Buttons, links, focus | `--tb-brand`, `--tb-brand-hover`, `--tb-brand-active` |
| **Success** | `#16A34A` | Success states, positive actions | `--tb-success`, `--tb-success-soft`, `--tb-success-text` |
| **Warning** | `#D97706` | Warnings, alerts, caution | `--tb-warning`, `--tb-warning-soft`, `--tb-warning-text` |
| **Danger** | `#DC2626` | Errors, destructive actions | `--tb-danger`, `--tb-danger-soft`, `--tb-danger-text` |
| **Info** | `#0891B2` | Informational messages | `--tb-info`, `--tb-info-soft`, `--tb-info-text` |

### Neutral Palette

| Element | Light Mode | Dark Mode | CSS Variable | Usage |
|---------|-----------|-----------|------|-------|
| **Background (Page)** | `#F5F6FA` | (dark equivalent) | `--tb-body-bg` | Page background |
| **Card Surface** | `#FFFFFF` | (dark equivalent) | `--tb-card-bg` | Card, modal, dropdown |
| **Sunken/Muted** | `#F8F9FB` | (dark equivalent) | `--tb-sunken` | Secondary surface, disabled state |
| **Text Primary** | `#111827` | (light equivalent) | `--tb-text` | Main body text |
| **Text Secondary** | `#5E6673` | (light equivalent) | `--tb-text-secondary` | Secondary info, labels |
| **Text Tertiary** | `#9CA3AF` | (light equivalent) | `--tb-text-tertiary` | Placeholders, hints |
| **Border Default** | `#E4E7EC` | (dark equivalent) | `--tb-border` | Form, table, card borders |
| **Border Soft** | `#EEF0F4` | (dark equivalent) | `--tb-border-soft` | Subtle dividers |
| **Border Strong** | `#CDD2DA` | (dark equivalent) | `--tb-border-strong` | Emphasis borders |

### Dark Mode

Dark mode is activated via `[data-theme="dark"]` on the `<html>` element. All CSS variables automatically invert.

---

## 6. Control Sizing

Standard control heights ensure accessibility and visual consistency.

| Size | Height | Padding (vertical) | Padding (horizontal) | Usage |
|------|--------|-------------------|---------------------|-------|
| **sm** | 32px | 4px | 8px–10px | Compact controls, small inputs |
| **md** | 36px | 6px | 12px | Standard buttons, select inputs |
| **lg** | 40px | 8px | 16px | Large buttons, prominent CTAs |

### Control Specifications

- **All controls** have min-height (not fixed height) for text-heavy labels
- **Input fields & selects:** Use `md` (36px) by default
- **Small buttons:** Use `sm` (32px) for secondary, compact actions
- **Primary buttons:** Use `md` (36px) standard, `lg` (40px) for primary CTAs

---

## 7. Z-Index Strata

Z-index values prevent stacking context confusion.

| Layer | Value | CSS Variable | Usage |
|-------|-------|--------------|-------|
| **Sticky** | 20 | `--tb-z-sticky` | Sticky table headers, sticky sidebars |
| **Dropdown** | 1000 | `--tb-z-dropdown` | Dropdowns, popovers, floating menus |
| **Modal** | 1050 | `--tb-z-modal` | Modal overlays, dialogs |
| **Tooltip** | 1070 | `--tb-z-tooltip` | Tooltips (if needed) |

---

## 8. Motion Tokens

Animation timings and easing for consistent, subtle motion.

| Token | Value | CSS Variable | Usage |
|-------|-------|--------------|-------|
| **Ease (standard)** | `cubic-bezier(0.22, 1, 0.36, 1)` | `--tb-ease` | Default easing |
| **Ease In** | `cubic-bezier(0.55, 0, 1, 0.45)` | `--tb-ease-in` | Entrance animations |
| **Fast** | 100ms | `--tb-tx-fast` | Quick state changes (hover, focus) |
| **Base** | 160ms | `--tb-tx-base` | Standard transitions |
| **Slow** | 280ms | `--tb-tx-slow` | Longer transitions (modals opening) |

### Motion Usage Rules

- **Hover states:** `--tb-tx-fast` (100ms)
- **State transitions:** `--tb-tx-base` (160ms)
- **Modal/open animations:** `--tb-tx-slow` (280ms)
- **Prefers-reduced-motion:** Reduce to 0.01ms on systems with motion disabled

---

## 9. Breakpoints

Responsive design breakpoints for mobile-first styling.

| Breakpoint | Width | CSS Variable | Usage |
|------------|-------|--------------|-------|
| `sm` | 480px | `--tb-bp-sm` | Small phone to tablet |
| `md` | 720px | `--tb-bp-md` | Tablet |
| `lg` | 1024px | `--tb-bp-lg` | Desktop |
| `xl` | 1280px | `--tb-bp-xl` | Wide desktop |
| `2xl` | 1640px | `--tb-bp-2xl` | Ultra-wide |

### Responsive Patterns

- **Mobile first:** Style for mobile, add Tailwind prefixes (`md:`, `lg:`) for larger screens
- **Page content max-width:** 1600px (`--tb-content-max`)
- **Sticky positioning:** Reset to static on mobile (`position: static` at `max-width: 768px`)

---

## 10. Focus & Accessibility

### Focus Ring

| Token | CSS Variable | Value |
|-------|--------------|-------|
| **Primary Ring** | `--tb-ring` | `0 0 0 3px rgba(37, 99, 235, 0.2)` |
| **Danger Ring** | `--tb-ring-danger` | `0 0 0 3px rgba(220, 38, 38, 0.2)` |
| **Success Ring** | `--tb-ring-success` | `0 0 0 3px rgba(22, 163, 74, 0.2)` |

### Focus-Visible Pattern

```css
:focus-visible {
    outline: 2px solid var(--tb-brand);
    outline-offset: 2px;
}
```

---

## Implementation Guidelines

### CSS Variables vs. Tailwind

1. **CSS Variables** are defined in `theme/tabler.css` and can be used directly in custom CSS:
   ```css
   padding: var(--tb-sp-4);
   border-radius: var(--tb-r-md);
   ```

2. **Tailwind Utilities** are preferred in React/JSX:
   ```tsx
   className="px-4 py-3 rounded-md"  // Uses sp-4 and r-md
   ```

3. **Both systems are aligned:** Tailwind utilities map to the same values.

### Dark Mode

Dark mode is **automatic** — all colors invert when `[data-theme="dark"]` is present on `<html>`:

```html
<html data-theme="dark">
```

No component-level dark mode classes needed.

### Color Mapping (shadcn ↔ Tabler)

shadcn semantic variables are bridged to Tabler tokens:

| shadcn | Tabler |
|--------|--------|
| `--primary` | `--tb-brand` |
| `--success` | `--tb-success` |
| `--destructive` | `--tb-danger` |
| `--warning` | `--tb-warning` |
| `--info` | `--tb-info` |
| `--background` | `--tb-body-bg` |
| `--card` | `--tb-card-bg` |
| `--muted` | `--tb-sunken` |
| `--border` | `--tb-border` |

---

## Validation & Quality Gates

1. **No hardcoded hex values** in components — use token variables
2. **No inline pixel values** — use spacing scale (`sp-*`) or Tailwind utilities
3. **All colors** use semantic tones from TONE_MAP/CHIP_TONE_MAP in `theme/tokens.js`
4. **All shadows** use layered shadow tokens
5. **Typography** follows the hierarchy defined above
6. **Motion** respects `prefers-reduced-motion`

---

## References

- **CSS Variables:** `/frontend/src/theme/tabler.css`
- **Design Tokens (JS):** `/frontend/src/theme/tokens.js`
- **Tailwind Config Bridge:** `/frontend/src/styles/tailwind.css`
- **Component Examples:** `/frontend/src/components/ui/*`
