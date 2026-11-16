# Shell Redesign Specification
**License Manager Global Navigation & Application Shell**
Date: 2026-09-25 | Version: 1.0

---

## Executive Summary

This document defines the redesigned global application shell for the License Manager, including sidebar navigation, top navigation bar, breadcrumbs, and mobile navigation. The redesign modernizes the interface while maintaining enterprise-grade professionalism and accessibility (WCAG AA).

The rebrand moves from a horizontal-dropdown-only navigation model to a **hybrid dual-navigation** system:
- **Desktop:** Persistent left sidebar + condensed top bar
- **Mobile:** Bottom navigation + collapsible menu
- **Consistent:** Single source of truth for navigation structure and role-based filtering

---

## PHASE 1: AUDIT FINDINGS

### Current State Analysis

#### 1. Top Navigation Bar (TopNav.tsx)
**What Works:**
- Linear, professional horizontal navigation design
- Premium styling with proper spacing and typography
- Robust keyboard navigation (Cmd+K, Escape, Tab trap)
- Role-based visibility filtering
- Mobile drawer with logical section grouping
- Active state indicators clear and prominent
- Command palette integration

**Issues:**
- No persistent sidebar means navigation is always menu-driven
- Heavy reliance on dropdowns can cause fatigue on larger datasets
- Mobile drawer is full-screen overlay (not ideal for quick access)
- Username truncation at 120px arbitrary and brittle
- Quick-actions footer is cramped and disconnected

#### 2. Sidebar (Sidebar.tsx)
**What Exists:**
- 260px fixed sidebar with dark theme
- 3-level hierarchy: top-level nav + collapsible sections (Masters, Reports)
- Inline styles with hardcoded color references
- Manual hover state management

**Problem:**
- **Not used in the main shell** — it exists but AdminLayout doesn't import it
- Inconsistent with TopNav styling system
- Inline styles break design system consistency
- No integration with role-based filtering

#### 3. Page Header (PageHeader.tsx)
**What Works:**
- Clean card-based layout with pretitle/title/description/actions
- Responsive spacing
- Proper semantic HTML with h1

**Issues:**
- No breadcrumb navigation implemented
- Limited context for deep navigation paths
- Could better integrate with shell navigation state

#### 4. Mobile Navigation
**Current:**
- Full-screen drawer triggered by hamburger in top bar
- Good section grouping and touch sizing
- Footer with utility actions (Search, Profile, Theme, Logout)

**Issues:**
- Overlay-based (not dismissible by scrolling)
- No bottom-nav option (heavy reliance on hamburger)
- Footer utilities (4 items) could be better organized

#### 5. Quick Actions Footer
**Current:**
- Sticky 44px footer with primary action + secondary buttons
- 4 quick-create routes (New License, Allotment, BOE, Reports)

**Issues:**
- Limited visual hierarchy
- Small font (11.5px) and narrow hit targets
- Disconnected from main navigation
- No indication of keyboard shortcuts

#### 6. Theme & Tokens
**System:**
- Tabler CSS with semantic colors
- Full light/dark mode support
- CSS custom properties for extensibility

**Issues:**
- Sidebar uses `var(--tb-card-bg)` as background (too dark for text contrast in some modes)
- No centralized navigation token definitions
- Color palette not optimized for navigation hover/active states

---

## PHASE 2: GLOBAL SHELL REDESIGN

### 2.1 Navigation Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  TOP BAR: Brand | Search | Theme | User | Help              │  [0-56px]
├──────────┬──────────────────────────────────────────────────┤
│ SIDEBAR  │  MAIN CONTENT                                    │
│ (240px)  │  ┌──────────────────────────────────────────┐  │
│          │  │ PAGE HEADER: Breadcrumb | Title | Actions │  │
│          │  ├──────────────────────────────────────────┤  │
│ • Home   │  │                                          │  │
│ • Module │  │  PAGE CONTENT                            │  │
│ • Module │  │  (scrollable)                            │  │
│ • ...    │  │                                          │  │
│          │  └──────────────────────────────────────────┘  │
├──────────┼──────────────────────────────────────────────────┤
│ QUICK-CREATE ACTIONS (inline with content, not footer)      │  [Optional]
└─────────────────────────────────────────────────────────────┘
```

**Device Breakpoints:**
- **Mobile (<480px):** Top bar only + bottom nav (persistent pill with 4-5 key actions)
- **Tablet (480-1024px):** Top bar + collapsible sidebar + bottom action bar
- **Desktop (>1024px):** Top bar + persistent sidebar (240px) + content

---

### 2.2 Sidebar Navigation (Desktop)

#### Visual Design
- **Width:** 240px (fixed, no collapse animation)
- **Background:** Neutral layer (var(--tb-sunken) in light mode, adjusted dark mode)
- **Border Right:** 1px solid var(--tb-border) for definition
- **Typography:** 
  - Section headers: 10px, 600 weight, uppercase, var(--tb-text-tertiary)
  - Nav items: 14px, 500 weight, var(--tb-text-secondary)
  - Active items: 14px, 600 weight, var(--tb-text)

#### Structure
```
Navigation
│
├─ Dashboard (direct link)
├─ LICENSING SECTION
│  ├─ Licenses
│  ├─ License Ledger
│  ├─ Incentive Licenses
│  └─ Auto Planning
├─ OPERATIONS SECTION
│  ├─ Allotments
│  ├─ Bill of Entry
│  ├─ Trade In & Out
│  └─ Reconciliation
├─ DATA & REPORTS SECTION
│  ├─ Item Pivot Report
│  ├─ Item Report
│  ├─ Planned Report
│  └─ Purchase & Profit Report
├─ MASTERS SECTION (collapsible)
│  ├─ Item Names
│  ├─ Groups
│  ├─ Exchange Rates
│  └─ ... (other masters)
└─ ADMIN SECTION (role-gated)
   ├─ Users & Roles
   ├─ Activity Log
   └─ Settings
```

#### Navigation Item States

**Default State:**
- Background: transparent
- Text Color: var(--tb-text-secondary)
- Icon: var(--tb-text-tertiary)
- Padding: 10px 12px (44px min-height for touch)
- Border Radius: 6px
- Transition: 150ms ease

**Hover State:**
- Background: var(--tb-sunken) (lighter on dark mode)
- Text Color: var(--tb-text)
- Icon: var(--tb-brand)
- Cursor: pointer

**Active State:**
- Background: var(--tb-brand-50)
- Text Color: var(--tb-brand-active)
- Border Left: 3px solid var(--tb-brand) (accent)
- Icon: var(--tb-brand-active)
- Font Weight: 600

**Focus State:**
- Outline: 2px solid var(--tb-brand)
- Outline Offset: -2px (inside)
- No change to background

**Disabled State:**
- Text Color: var(--tb-text-muted)
- Cursor: not-allowed
- Opacity: 0.6

#### Section Headers
- Padding: 8px 12px (top), 12px 12px (bottom)
- Font: 10px 600 uppercase
- Color: var(--tb-text-tertiary)
- Letter Spacing: 0.08em

#### Responsive Behavior
- **480px-768px:** Sidebar collapses to icon-only (60px), expands on click
- **<480px:** Sidebar hidden, replaced with bottom nav

---

### 2.3 Top Navigation Bar

#### Layout & Spacing
- **Height:** 56px (fixed, sticky)
- **Background:** var(--tb-card-bg) with backdrop blur
- **Border Bottom:** 1px solid var(--tb-border)
- **Box Shadow:** 0 2px 8px rgba(0,0,0,0.08)
- **Z-Index:** 1020 (sticky layer)
- **Padding:** 0 20px

#### Regions

**Left Region (Brand)**
- Logo/Icon: 24x24px
- Brand text: "License Manager" (hidden on <480px)
- Total width: 160px
- Font: 16px 600
- Text Color: var(--tb-text)

**Center Region (Reserved)**
- Currently empty; available for global messaging or search hints
- Could be used for breadcrumb overflow on ultra-large screens

**Right Region (Utilities)**
Ordered: Search | Theme | Separator | User Menu | Mobile Toggle

**Search:**
- Icon: 16px (Lucide Search)
- Desktop: Pill-style button with "⌘K" keyboard hint
- Mobile: Icon-only button
- Background: transparent, hover: var(--tb-sunken)

**Theme Toggle:**
- Icon: 16px (Sun/Moon)
- Button: Icon-only, 40x40px
- Background: transparent, hover: var(--tb-sunken)

**Separator:**
- Border: 1px solid var(--tb-border-soft)
- Height: 24px
- Margin: 0 8px

**User Menu:**
- Trigger: Avatar or initials + name (desktop), icon-only (mobile)
- Dropdown: Right-aligned, 240px max-width
- Items: Profile, Activity Log (admin), Settings (superadmin), Logout

**Mobile Toggle:**
- Icon: 20x20px (Hamburger/Menu)
- Hidden on desktop
- Button: 44x44px, icon-only

#### Keyboard Navigation
- **Cmd+K / Ctrl+K:** Open command palette
- **Escape:** Close open menus
- **Tab:** Cycle through nav items and menus
- **Tab (in mobile drawer):** Trap focus within drawer

---

### 2.4 Mobile Navigation (Mobile <480px)

#### Top Bar
- Simplified: Logo + Search + Theme + Hamburger (40px each button)
- No dropdown menus
- Search opens command palette

#### Bottom Navigation Pill (Persistent)
- **Fixed Position:** Bottom safe-area (accounts for notch/home indicator)
- **Height:** 52px + safe-area-inset-bottom
- **Background:** var(--tb-card-bg) with backdrop blur
- **Border Top:** 1px solid var(--tb-border)
- **Items:** 5 main destinations + overflow menu
  1. Home (Dashboard icon)
  2. Licenses (Document icon)
  3. Operations (Arrow icon) → Expands sub-menu
  4. Reports (Chart icon) → Expands sub-menu
  5. Menu (More icon) → Expands overflow

#### Hamburger Drawer (On Demand)
- **Trigger:** Menu icon in top bar or bottom nav
- **Width:** 88vw (max 360px)
- **Position:** Left sidebar, full height minus top bar
- **Background:** var(--tb-card-bg)
- **Shadow:** 18px 0 42px rgba(2,10,24,0.28)
- **Content:** Full navigation tree organized by section
- **Dismiss:** 
  - Tap backdrop
  - Tap navigation item (navigate + close)
  - Escape key
  - X button in drawer header

#### Bottom Menu Expansion (Dropups)
When "Operations" or "Reports" tapped:
- Expands upward above the pill
- Shows 4-5 items
- Tap to navigate or tap back to collapse
- Or scroll content behind and auto-collapse

---

### 2.5 Breadcrumb Navigation

#### Location
- **Desktop:** Inside PageHeader component, above page title
- **Mobile:** Hidden (space constraints), accessible via page header pretitle

#### Structure
```
Dashboard > Licenses > Detail > Edit
```

**Rendering Rules:**
- **Truncation:** Show last 3 breadcrumbs + ellipsis for earlier ones
- **Current Page:** Not a link, styled with brand color
- **Ancestors:** Links to parent pages

#### Styling
- **Container:** Flex row, gap: 4px, height: 20px
- **Item Font:** 12px, 500 weight, var(--tb-text-secondary)
- **Item Padding:** 0 4px
- **Separator:** "/" text in var(--tb-border)
- **Current Item:** 600 weight, var(--tb-brand), no link
- **Link Hover:** var(--tb-brand), text-decoration: underline
- **Link Focus:** 2px outline, -2px offset

#### Accessibility
- **aria-label:** "Breadcrumb navigation"
- **nav** semantic element
- **aria-current="page"** on active item
- Keyboard navigable (Tab stops on each link)

---

### 2.6 Quick Actions

#### Current State (Footer)
- Positioned in 44px sticky footer below main content
- Primary action (New License) with brand color
- Secondary actions with border styling

**Redesign:**
- Move to **PageHeader actions region** (if applicable per page)
- Or use **floating action button (FAB)** for prominent actions
- Keep footer for context-dependent actions only

#### FAB Pattern (Alternative)
- **Position:** Bottom-right corner, 64px safe area from edges
- **Mobile:** Adjust for bottom nav (52px safe area)
- **Primary Action:** "New License" (primary color)
- **Expand on Hover/Click:** Shows 3-4 secondary actions
- **Dismiss:** Tap outside or Escape

---

### 2.7 Color System (Navigation-Specific)

#### Surface Colors
| Element | Light Mode | Dark Mode |
|---------|-----------|-----------|
| Sidebar Background | var(--tb-sunken) #F8F9FB | var(--tb-body-bg) adjusted |
| Top Bar Background | var(--tb-card-bg) #FFF | var(--tb-card-bg) adjusted |
| Hover Background | var(--tb-border-soft) #EEF0F4 | var(--tb-card-bg) +10% |
| Active Background | var(--tb-brand-50) #EFF6FF | var(--tb-brand-50) |

#### Text Colors
| Element | Light Mode | Dark Mode |
|---------|-----------|-----------|
| Primary Text | var(--tb-text) #111827 | var(--tb-text) adjusted |
| Secondary Text | var(--tb-text-secondary) #5E6673 | var(--tb-text-secondary) |
| Tertiary Text | var(--tb-text-tertiary) #9CA3AF | var(--tb-text-tertiary) |
| Active Text | var(--tb-brand-active) #1E40AF | var(--tb-brand-active) |

#### Border Colors
| Element | Color |
|---------|-------|
| Dividers | var(--tb-border) #E4E7EC |
| Soft Dividers | var(--tb-border-soft) #EEF0F4 |
| Strong Dividers | var(--tb-border-strong) #CDD2DA |

---

### 2.8 Typography

#### Sidebar
- **Section Headers:** 10px, 600 weight, uppercase, letter-spacing: 0.08em
- **Nav Items:** 14px, 500 weight, line-height: 1.4
- **Active Nav Items:** 14px, 600 weight

#### Top Bar
- **Brand Text:** 16px, 600 weight, letter-spacing: -0.015em
- **Nav Items:** 14px, 500 weight
- **Utilities Text:** 12px, 400 weight (keyboard hints)

#### Breadcrumbs
- **Font:** 12px, 500 weight
- **Current Item:** 600 weight

---

### 2.9 Icon System

**All icons from lucide-react:**
- Sidebar nav items: 16x16px
- Section headers: 14x14px
- Top bar buttons: 16x16px or 20x20px
- Mobile nav: 20x20px
- Breadcrumb: 12x12px (optional)

**Color Rules:**
- **Default:** var(--tb-text-tertiary)
- **Hover:** var(--tb-brand)
- **Active:** var(--tb-brand-active)

---

## PHASE 3: KEY SPECIFICATIONS

### 3.1 Spacing Scale

| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Component padding, gaps |
| sm | 8px | Section spacing |
| md | 12px | Nav item padding |
| lg | 16px | Container padding |
| xl | 20px | Between major sections |
| 2xl | 24px | Page margins |

### 3.2 Border Radius
- **Buttons / Nav Items:** 6px (md)
- **Cards / Panels:** 8px (lg)
- **Modals:** 8px (lg)

### 3.3 Transitions
- **Fast:** 150ms cubic-bezier(0.4, 0, 0.2, 1)
- **Normal:** 200ms cubic-bezier(0.4, 0, 0.2, 1)
- **Slow:** 300ms cubic-bezier(0.4, 0, 0.2, 1)

### 3.4 Z-Index Strata
- **Base:** 0-99
- **Sticky/Sidebar:** 1020
- **Fixed/Modals:** 1030
- **Tooltips:** 1070
- **Mobile Drawer:** 1100

### 3.5 Breakpoints
- **Mobile:** < 480px
- **Tablet:** 480px - 1024px
- **Desktop:** > 1024px

---

## PHASE 4: INTERACTION PATTERNS

### 4.1 Active State Indicators

**Sidebar:**
- Left border (3px) + background highlight + text color change
- Active parent section shows children, no expansion needed if already visible
- Only one item active at a time

**Top Bar:**
- Underline or background highlight (design choice)
- Subtle effect, doesn't dominate

**Breadcrumb:**
- Current item: No link, bold text, brand color
- Ancestors: Clickable links

### 4.2 Hover States

**All Navigation Items:**
- 150ms transition
- Background lightens slightly
- Icon/text color shifts toward brand or neutral (depending on context)
- Cursor becomes pointer

**Disabled Items:**
- 0.6 opacity, no hover effect, cursor: not-allowed

### 4.3 Focus States

**Keyboard Navigation:**
- 2px solid outline in var(--tb-brand)
- -2px outline offset (inside element)
- Visible at all times, even on touch devices (for keyboard users)

### 4.4 Mobile Touch

**Hit Targets:**
- Minimum 44x44px for buttons and nav items
- Sufficient spacing (8px gap) to prevent accidental taps
- No hover effects on touch devices (use :hover and @media (hover) OR use Tailwind's touch-friendly approach)

### 4.5 Keyboard Navigation

**Tab Order:**
1. Logo/brand link
2. Search button
3. Theme toggle
4. User menu trigger
5. Mobile toggle (hidden on desktop)
6. Sidebar nav items (if visible)

**Keyboard Shortcuts:**
- **Cmd+K / Ctrl+K:** Open command palette
- **Escape:** Close open menus, drawers
- **Enter/Space:** Activate buttons or follow links

### 4.6 Loading States

**Navigation:**
- If nav items are dynamically loaded, show skeleton loaders
- Disabled state while loading

**Mobile Drawer:**
- Smooth slide-in animation (190ms)
- Backdrop fade-in (160ms)

### 4.7 Notification Badges

**User Menu:**
- Small red badge (8x8px) in top-right corner of avatar if notifications exist
- Animate in with brief scale pulse

**Sidebar Items:**
- Optional red badge on icon (e.g., "Unresolved Issues: 3")
- Justified to top-right of icon container

---

## PHASE 5: ACCESSIBILITY (WCAG AA)

### 5.1 Color Contrast
- **Text on Background:** 4.5:1 ratio for normal text, 3:1 for large text
- **Icon on Background:** Same as text
- **Verify:** Run contrast checker on all color combinations in both light and dark modes

### 5.2 Keyboard Navigation
- All interactive elements (links, buttons, dropdowns) are focusable
- Focus order is logical and top-to-bottom
- No keyboard traps (focus can always escape)
- Focus indicator clearly visible (2px outline)

### 5.3 Screen Reader Support
- Semantic HTML (nav, button, a, ul, li)
- aria-label and aria-expanded on toggles
- aria-current="page" on active nav link
- aria-controls for drawers/menus
- Breadcrumb has aria-label="Breadcrumb navigation"

### 5.4 Motion
- Respect prefers-reduced-motion: animation duration becomes 0ms, transitions remain for visual update

```css
@media (prefers-reduced-motion: reduce) {
  * { animation-duration: 0ms !important; transition-duration: 0ms !important; }
}
```

### 5.5 Responsive & Mobile
- Minimum touch target: 44x44px
- Sufficient spacing: 8px minimum gap between touch targets
- Bottom navigation doesn't overlap scrollable content
- Sidebar doesn't block content on narrow screens

---

## IMPLEMENTATION PRIORITIES

### Phase A (Week 1): Foundation
1. Refactor Sidebar to use design tokens (remove inline styles)
2. Integrate Sidebar into AdminLayout (responsive visibility)
3. Update TopNav styles to match new color system
4. Create breadcrumb navigation component

### Phase B (Week 2): Enhancement
1. Implement mobile bottom navigation pill
2. Add focus styles across all nav elements
3. Optimize mobile drawer animations
4. Add notification badge system

### Phase C (Week 3): Polish
1. Test keyboard navigation
2. Verify accessibility (WCAG AA)
3. Refine hover/active states in both light and dark modes
4. Performance optimization (lazy-load nav sections)

---

## Success Criteria

- [x] Audit completed and documented
- [ ] All navigation components use centralized design tokens
- [ ] Desktop: Sidebar + Top Bar layout
- [ ] Mobile: Bottom nav + Hamburger drawer
- [ ] Breadcrumb navigation working on all pages
- [ ] WCAG AA color contrast verified
- [ ] Keyboard navigation fully functional
- [ ] Focus indicators visible on all interactive elements
- [ ] Mobile drawer accessible and performant
- [ ] Light/Dark mode working correctly
- [ ] All role-based filtering preserved

---

## Files to Create/Modify

- `frontend/src/layout/Sidebar.tsx` — Refactor to use tokens
- `frontend/src/layout/AdminLayout.tsx` — Integrate sidebar
- `frontend/src/components/TopNav.tsx` — Update styling
- `frontend/src/components/Breadcrumb.tsx` — NEW
- `frontend/src/components/BottomNav.tsx` — NEW (mobile)
- `frontend/src/theme/navigationTokens.js` — NEW (centralized nav tokens)
- `frontend/src/styles/navigation.css` — NEW (semantic CSS)

---

## Design System Alignment

- **Design System:** shadcn/ui + Tabler tokens
- **Icons:** lucide-react only (no bootstrap-icons)
- **Colors:** CSS custom properties (--tb-*)
- **Typography:** Inter font, standardized scale
- **Spacing:** 4px-based scale (4, 8, 12, 16, 20, 24, 32)
- **Transitions:** Standardized timing (150ms, 200ms, 300ms)

