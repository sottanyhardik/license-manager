# Shell Visual Examples & Reference
**Before/After Comparisons and Design References**
Date: 2026-09-25

---

## Table of Contents
1. [Before State (Current)](#before-state-current)
2. [After State (Target)](#after-state-target)
3. [Responsive Breakpoints](#responsive-breakpoints)
4. [Component States](#component-states)
5. [Color References](#color-references)
6. [Typography Scale](#typography-scale)
7. [Spacing Grid](#spacing-grid)

---

## Before State (Current)

### Current Desktop Layout
```
┌─────────────────────────────────────────────────────────────────────────┐
│  [Shield] License Manager    [Dashboard] [Licenses ▼] [Operations ▼]   │ 56px
│                              [Reports ▼] [Masters ▼]  [Search] [User ▼]│
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ Page Title                                                        │  │
│  │ Description                                      [Action Button]  │  │
│  └────────────���─────────────────────────────────────────────────────┘  │
│                                                                          │
│  Page Content                                                            │
│                                                                          │
│  (scrolls)                                                               │
│                                                                          │
│                                                                          │
├─────────────────────────────────────────────────────────────────────────┤
│ [+ New License] [New Allotment] [New BOE] [Reports]  License Manager   │ 44px
└─────────────────────────────────────────────────────────────────────────┘
```

**Issues:**
1. All navigation is horizontal (no persistent sidebar)
2. Dropdowns required to see secondary items
3. Footer quick-actions cramped and disconnected
4. No breadcrumb navigation
5. Sidebar exists but unused

### Current Mobile Layout
```
┌──────────────────────────┐
│ [≡] [Search] [☀] [👤]   │ 56px
├──────────────────────────┤
│                          │
│ Page Content             │
│ (scrolls)                │
│                          │
├──────────────────────────┤
│ [+ New License] [New Allotment] [New BOE] [Reports] │ 44px
└──────────────────────────┘

Mobile Drawer (when ≡ tapped):
┌──────────────────────────┐
│ [≡] License Manager [×]  │ dark header
├──────────────────────────┤
│ • Dashboard              │
│ • LICENSING              │
│  - Licenses              │
│  - License Ledger        │ Full-screen overlay
│ • OPERATIONS             │
│  - Allotments            │
│  - Bill of Entry         │
├──────────────────────────┤
│ [Search] [Profile] [☀]  │ footer utilities
│ [Sign Out]               │
└──────────────────────────┘
```

**Issues:**
1. Drawer is full-screen overlay (heavy)
2. Quick-actions footer still present (redundant)
3. No persistent bottom nav
4. Mobile drawer doesn't close on scroll

---

## After State (Target)

### After Desktop Layout (>1024px)
```
┌──────┬───────────────────────────────────────────────────────────────┐
│      │ [Shield] License Manager    [Search] [☀] | [User ▼] [?]     │ 56px
├──────┼───────────────────────────────────────────────────────────────┤
│      │                                                               │
│ DASH │ ┌───────────────────────────────────────────────────────────┐│
│ LICE │ │ Dashboard > Licenses > Detail                          [•]││
│      │ ├───────────────────────────────────────────────────────────┤│
│ LIC  │ │ License Detail                                          ││
│ LEDE │ │ Manage license information and history   [Edit] [Delete] ││
│      │ ├───────────────────────────────────────────────────────────┤│
│ OPER │ │                                                        ││
│ ALLO │ │ License Information                                   ││
│ BOE  │ │                                                        ││
│ TRAD │ │ (page content scrolls)                                ││
│ RECON│ │                                                        ││
│      │ │                                                        ││
│ REPT │ │                                                        ││
│ ITEM │ │                                                        ││
│      │ │                                                        ││
│ MAST │ │                                                        ││
│      │ │                                                        ││
├──────┼───────────────────────────────────────────────────────────────┤
│      │ [+ New License] [New Allot.] [New BOE] [Reports]             │ 44px
└──────┴───────────────────────────────────────────────────────────────┘
```

**Key Improvements:**
1. Persistent 240px sidebar on left
2. All navigation items visible without dropdowns
3. Clear section grouping (LICENSING, OPERATIONS, REPORTS, MASTERS)
4. Breadcrumb shows hierarchy
5. Page header integrated with actions
6. Quick-actions moved to context area (not footer)

### After Tablet Layout (480px - 1024px)
```
┌────┬──────────────────────────────────────────────────────┐
│    │ [Shield] License Manager  [Search] [☀] | [User ▼]  │ 56px
├──┐ │  (on hover or click, expands to 240px)              │
│DA│ ├──────────────────────────────────────────────────────┤
│  │ │                                                      │
│LI│ │ Dashboard > Licenses > Detail                        │
│  │ │ ┌───────────────────────────────────────────────┐   │
│EX│ │ │ License Detail                                │   │
│  │ │ │                                               │   │
│OP│ │ │ (page content)                                │   │
│  │ │ │                                               │   │
│RE│ │ │                                               │   │
│  │ │ │                                               │   │
│MA│ │ └───────────────────────────────────────────────┘   │
│  │ ├──────────────────────────────────────────────────────┤
└────┴──────────────────────────────────────────────────────┘

When sidebar expanded (on hover):
┌──────┬────────────────────────────────────────────────────┐
│      │ [Shield] License Manager  [Search] [☀] | [User ▼] │
│ DASH │├────────────────────────────────────────────────────┤
│      ││                                                   │
│ LICE ││ Page content                                      │
│ LEDE ││                                                   │
└──────┴────────────────────────────────────────────────────┘
```

**Behavior:**
1. Sidebar 60px (icon-only) by default
2. Expands to 240px on hover
3. Active icon highlighted with brand color
4. Icons clearly visible
5. Labels appear on expand

### After Mobile Layout (<480px)
```
┌────────────────────────────────┐
│ [≡] License Manager [Search]   │ 56px
├────────────────────────────────┤
│                                │
│ Dashboard > Licenses > Detail  │
│ ┌──────────────────────────────┐
│ │ License Detail              │
│ │                              │
│ │ (page content scrolls)        │
│ │                              │
│ │                              │
│ │                              │
│ └──────────────────────────────┘
├────────────────────────────────┤
│ [⌂] [📄] [↔] [📊] [⋯]         │ 52px + safe-area
└────────────────────────────────┘

Mobile Hamburger Drawer (≡ tapped):
┌──────────────────────────┐
│ [License Manager] [×]    │ dark header
├──────────────────────────┤
│ • Dashboard              │
│ • LICENSING              │
│  - Licenses              │
│  - License Ledger        │ Drawer (not full-screen)
│  - Incentive Licenses    │ Width: 88vw (max 360px)
│ • OPERATIONS             │
│  - Allotments            │
│ • REPORTS                │
│  - Item Pivot            │
├──────────────────────────┤
│ [Search] [Profile]       │ footer
│ [☀ Light] [Sign Out]     │ (2-column grid)
└──────────────────────────┘
```

**Key Differences:**
1. Bottom navigation pill (5 items) replaces footer quick-actions
2. Hamburger drawer is side panel (not full overlay)
3. Drawer 88vw width (max 360px) fits most phones
4. Bottom nav has badge support (notifications)
5. Menu items grouped logically

---

## Responsive Breakpoints

### Breakpoint 1: Desktop (>1024px)
```
Screen: 1280px wide (typical desktop)

┌─────────────────┬──────────────────────────────────┐
│ Sidebar 240px   │ Content area (flex-1)            │
│ (visible)       │                                  │
│ 100% height     │                                  │
└─────────────────┴──────────────────────────────────┘

TopBar: 56px fixed
Content: Full viewport minus sidebar and top bar
Footer: 44px sticky (quick-actions)
Bottom Nav: Hidden
```

**CSS:**
```css
/* Sidebar visible */
.sidebar { display: block; width: 240px; }
.main-content { margin-left: 240px; }

/* Full TopBar */
.top-bar { width: 100%; }
.search-button span { display: inline; }
.username-display { max-width: 120px; }
```

### Breakpoint 2: Tablet (480px - 1024px)
```
Screen: 768px wide (iPad)

┌──┬──────────────────────────────────┐
│  │ Content area                     │
│  │ (sidebar collapses to 60px)      │
│  │                                  │
└──┴──────────────────────────────────┘

TopBar: 56px fixed (same)
Sidebar: 60px (icon-only) → 240px (on hover)
Content: Adjusts width based on sidebar state
Transition: 200ms smooth
```

**CSS:**
```css
/* Sidebar collapses */
.sidebar { width: 60px; overflow: hidden; }
.sidebar:hover { width: 240px; z-index: 1030; }

/* Icon-only mode */
.sidebar.collapsed .nav-item-label { display: none; }
.sidebar.collapsed .nav-item-icon { margin: auto; }

/* Transition */
.sidebar { transition: width 200ms cubic-bezier(0.4, 0, 0.2, 1); }
```

### Breakpoint 3: Mobile (<480px)
```
Screen: 375px wide (iPhone)

┌──────────────────────────┐
│ TopBar (simplified)      │ 56px
├──────────────────────────┤
│                          │
│ Content                  │
│ (no sidebar)             │
│                          │
├──────────────────────────┤
│ Bottom Navigation Pill   │ 52px
└──────────────────────────┘
```

**CSS:**
```css
/* Sidebar hidden */
.sidebar { display: none; }
.main-content { margin-left: 0; }

/* TopBar simplified */
.brand-text { display: none; }
.search-button { width: 40px; padding: 0; }
.username-display { display: none; }

/* Bottom nav visible */
.bottom-nav { display: flex; }

/* Safe area for notch/home-indicator */
.bottom-nav { padding-bottom: env(safe-area-inset-bottom); }
```

---

## Component States

### NavItem States

#### 1. Default State
```
Text: var(--tb-text-secondary) #5E6673
Background: transparent
Padding: 10px 12px
Height: 44px
Border Radius: 6px
Font: 14px 500 weight
```

**Example:**
```
│ 📄 Licenses
│ (secondary gray, no background)
```

#### 2. Hover State
```
Text: var(--tb-text) #111827
Background: var(--tb-sunken) #F8F9FB
Cursor: pointer
Transition: 150ms
```

**Example:**
```
│ 📄 Licenses  ← lighter gray bg
│ (darker text)
```

#### 3. Active State
```
Text: var(--tb-brand-active) #1E40AF
Background: var(--tb-brand-50) #EFF6FF
Border Left: 3px solid var(--tb-brand) #2563EB
Padding Left: 9px (adjusted for border)
Font Weight: 600
```

**Example:**
```
│▮ 📄 Licenses  ← blue background + border + bold
│ (brand blue text)
```

#### 4. Focus State (Keyboard)
```
Outline: 2px solid var(--tb-brand) #2563EB
Outline Offset: -2px (inside)
No background change
```

**Example:**
```
│ ░░ 📄 Licenses ░░  ← 2px outline around item
│ (keyboard focus indicator)
```

#### 5. Disabled State
```
Text: var(--tb-text-muted) #C4C9D4
Opacity: 0.6
Cursor: not-allowed
No hover effect
```

**Example:**
```
│ 📄 Licenses  (grayed out, no interaction)
```

#### 6. Danger Variant (e.g., Logout)
```
Text: var(--tb-danger-text) #7F1D1D
Default background: transparent
Hover background: var(--tb-danger-soft) #FEE2E2
Hover text: var(--tb-danger) #DC2626
```

**Example:**
```
│ 🚪 Sign Out  (red text)
│          ↓ on hover:
│ 🚪 Sign Out  (red background, darker red text)
```

---

## Color References

### Navigation Color Palette

| Element | Light Mode | Dark Mode | Usage |
|---------|-----------|-----------|-------|
| **Sidebar BG** | var(--tb-sunken) #F8F9FB | var(--tb-body-bg) adjusted | Section background |
| **Sidebar Border** | var(--tb-border) #E4E7EC | var(--tb-border) adjusted | Right edge divider |
| **Nav Default Text** | var(--tb-text-secondary) #5E6673 | var(--tb-text-secondary) | Regular nav item |
| **Nav Hover BG** | var(--tb-sunken) #F8F9FB | var(--tb-card-bg) +10% | Hover background |
| **Nav Hover Text** | var(--tb-text) #111827 | var(--tb-text) | Hover text |
| **Nav Active BG** | var(--tb-brand-50) #EFF6FF | var(--tb-brand-50) | Active item background |
| **Nav Active Text** | var(--tb-brand-active) #1E40AF | var(--tb-brand-active) | Active item text |
| **Nav Active Border** | var(--tb-brand) #2563EB | var(--tb-brand) | Left accent bar |
| **Section Header Text** | var(--tb-text-tertiary) #9CA3AF | var(--tb-text-tertiary) | Section labels |
| **Focus Outline** | var(--tb-brand) #2563EB | var(--tb-brand) | Keyboard focus |
| **Danger Text** | var(--tb-danger-text) #7F1D1D | var(--tb-danger-text) | Logout/destructive |
| **Danger BG** | var(--tb-danger-soft) #FEE2E2 | var(--tb-danger-soft) | Danger hover |

### Light Mode Reference
```
Light Background:      #F5F6FA (--tb-body-bg)
Light Card:            #FFFFFF (--tb-card-bg)
Light Sunken:          #F8F9FB (--tb-sunken)
Light Border:          #E4E7EC (--tb-border)

Brand Primary:         #2563EB (--tb-brand)
Brand Light:           #EFF6FF (--tb-brand-50)
Brand Active:          #1E40AF (--tb-brand-active)

Text Dark:             #111827 (--tb-text)
Text Medium:           #5E6673 (--tb-text-secondary)
Text Light:            #9CA3AF (--tb-text-tertiary)
Text Muted:            #C4C9D4 (--tb-text-muted)
```

### Dark Mode Reference
```
Dark Background:       Darker shade of --tb-body-bg
Dark Card:             Darker shade of --tb-card-bg
Dark Sunken:           Darker shade of --tb-sunken
Dark Border:           Darker shade of --tb-border

Brand Primary:         #2563EB (--tb-brand) - unchanged
Brand Light:           #EFF6FF (--tb-brand-50) - adjusted for contrast
Brand Active:          #1E40AF (--tb-brand-active) - unchanged

Text Light:            Lighter shade of --tb-text
Text Medium:           Lighter shade of --tb-text-secondary
Text Dark:             Lighter shade of --tb-text-tertiary
Text Muted:            Lighter shade of --tb-text-muted
```

---

## Typography Scale

### Sidebar Typography

| Element | Font Size | Weight | Line Height | Letter Spacing | Color |
|---------|-----------|--------|-------------|----------------|-------|
| **Nav Item** | 14px | 500 | 1.4 | 0 | --tb-text-secondary |
| **Nav Item (Active)** | 14px | 600 | 1.4 | 0 | --tb-brand-active |
| **Section Header** | 10px | 600 | 1.2 | 0.08em (uppercase) | --tb-text-tertiary |
| **Collapsed Icon** | 16x16px | N/A | N/A | N/A | --tb-text |
| **Active Icon** | 16x16px | N/A | N/A | N/A | --tb-brand-active |

### TopBar Typography

| Element | Font Size | Weight | Line Height | Color |
|---------|-----------|--------|-------------|-------|
| **Brand Text** | 16px | 600 | 1.2 | --tb-text |
| **Nav Item (Desktop)** | 14px | 500 | 1.4 | --tb-text-secondary |
| **Keyboard Hint** | 12px | 400 | 1.2 | --tb-text-muted |
| **User Menu Header** | 14px | 600 | 1.4 | --tb-text |

### Breadcrumb Typography

| Element | Font Size | Weight | Color |
|---------|-----------|--------|-------|
| **Ancestor Link** | 12px | 500 | --tb-text-secondary |
| **Current Page** | 12px | 600 | --tb-brand |
| **Separator** | 12px | 400 | --tb-border |

### Mobile Nav Typography

| Element | Font Size | Weight | Color |
|---------|-----------|--------|-------|
| **Section Label** | 10px | 600 | --tb-text-tertiary |
| **Nav Link** | 14px | 500 | --tb-text-secondary |
| **Nav Link (Active)** | 14px | 600 | --tb-brand-active |
| **Footer Button** | 12px | 500 | --tb-text-secondary |

---

## Spacing Grid

### Base Unit: 4px

```
1x = 4px
2x = 8px
3x = 12px
4x = 16px
5x = 20px
6x = 24px
8x = 32px
10x = 40px
12x = 48px
```

### Component Spacing

#### NavItem
```
Height: 44px (11x base)
Padding: 10px 12px (2.5x 3x)
Icon Size: 16px (4x)
Gap (icon to label): 10px (2.5x)
Icon Margin Right: 10px
```

#### NavSection
```
Section Margin Top: 12px (3x)
First Section Margin: 0
Section Header Padding: 8px 12px (top), 12px 12px (bottom)
Item Gap: 4px (1x)
```

#### Sidebar
```
Width: 240px
Width (Collapsed): 60px
Brand Area Height: 56px
Brand Padding: 12px 16px
Padding: 12px
Scroll Area Padding: 12px
Footer Padding: 12px 12px 16px
```

#### TopBar
```
Height: 56px (14x)
Padding: 0 20px (5x)
Gap Between Items: 8px (2x)
Separator Gap: 0 8px (2x)
Avatar Size: 32px (8x)
Icon Size: 16px (4x)
```

#### Mobile Bottom Nav
```
Height: 52px (13x) + safe-area
Item Width: 1/5 (5 items)
Icon Size: 24px (6x)
Icon to Label Gap: 2px
Label Font: 10px
```

### Responsive Padding

#### Desktop
```
Page Content: 24px (6x) padding
Main Container: 20px (5x) max-width constraint
Card Padding: 16px (4x) to 20px (5x)
```

#### Mobile
```
Page Content: 16px (4x) padding
Page Content (iframe): 12px (3x) padding
Card Padding: 12px (3x) to 16px (4x)
Bottom Safe Area: env(safe-area-inset-bottom)
```

---

## Motion & Animation

### Transition Timings

| Action | Duration | Easing | Example |
|--------|----------|--------|---------|
| Hover state | 150ms | ease-out | NavItem hover |
| Color change | 150ms | ease-out | Icon color on hover |
| Expand/collapse | 200ms | ease-out | Sidebar collapse |
| Dropdown open | 100ms | ease-out | Menu appear |
| Page transition | 300ms | ease-out | Route change animation |

### Sidebar Collapse Animation
```css
.sidebar {
  transition: width 200ms cubic-bezier(0.4, 0, 0.2, 1);
  
  &:hover {
    width: 240px;
  }
}
```

### Mobile Drawer Animation
```css
/* Slide in from left */
@keyframes slideInLeft {
  from {
    opacity: 0.7;
    transform: translateX(-20px);
  }
  to {
    opacity: 1;
    transform: translateX(0);
  }
}

.mobile-nav-drawer {
  animation: slideInLeft 190ms cubic-bezier(0.4, 0, 0.2, 1) both;
}
```

### Backdrop Fade
```css
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

.mobile-nav-backdrop {
  animation: fadeIn 160ms cubic-bezier(0.4, 0, 0.2, 1) both;
}
```

### Respects prefers-reduced-motion
```css
@media (prefers-reduced-motion: reduce) {
  * {
    animation-duration: 0ms !important;
    transition-duration: 0ms !important;
  }
}
```

---

## Accessibility Indicators

### Focus Visible
```css
.nav-item:focus-visible {
  outline: 2px solid var(--tb-brand);
  outline-offset: -2px;
  border-radius: 6px;
}
```

### Focus Trap (Mobile Drawer)
```typescript
// Tab cycles within drawer
// First element ← → Last element
// Shift+Tab cycles backward

if (event.shiftKey && activeElement === firstElement) {
  event.preventDefault();
  lastElement.focus();
}
```

### Active Item Indicator
```
Visual: Left border (3px) + background + text color
Screen Reader: aria-current="page"
```

### Color Contrast Verification
```
Text on Light Background:    ≥4.5:1
Text on Dark Background:     ≥4.5:1
Large Text (18px+):          ≥3:1
Focus Outline:               2px solid, -2px offset
```

---

## Implementation Checklist

- [ ] Sidebar styled with tokens (no inline styles)
- [ ] NavItem component with all states
- [ ] NavSection component with grouping
- [ ] TopBar simplified styling
- [ ] Breadcrumb component
- [ ] Bottom navigation pill
- [ ] Mobile drawer
- [ ] Responsive behavior at all breakpoints
- [ ] Focus indicators visible
- [ ] Color contrast verified
- [ ] Dark mode tested
- [ ] Motion respects prefers-reduced-motion
- [ ] Touch targets ≥44px
- [ ] Keyboard navigation complete
- [ ] Screen reader labels
- [ ] Visual regression tests
- [ ] Performance metrics baseline

