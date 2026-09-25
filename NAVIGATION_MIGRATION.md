# Navigation System Implementation Plan
**Migration from Current TopNav-Only to Hybrid Sidebar + TopBar**
Date: 2026-09-25

---

## Table of Contents
1. [Overview](#overview)
2. [Phased Rollout](#phased-rollout)
3. [File Structure](#file-structure)
4. [Implementation Details](#implementation-details)
5. [Testing Strategy](#testing-strategy)
6. [Rollback Plan](#rollback-plan)

---

## Overview

### Current State
- **Horizontal navigation only** via TopNav.tsx
- **Mobile drawer** for full navigation
- **Sidebar.tsx exists but unused** (not imported in AdminLayout)
- **Quick-actions footer** with 4 buttons

### Target State
- **Desktop (>1024px):** Persistent 240px sidebar + minimal top bar
- **Tablet (480-1024px):** Collapsible sidebar (60px icon-only, expands on hover)
- **Mobile (<480px):** Bottom navigation pill + hamburger drawer + hidden sidebar
- **Consistent color system** using CSS tokens
- **No inline styles** in navigation components
- **Full accessibility** (WCAG AA)

### Why This Approach
1. **Persistent sidebar** provides instant navigation without menu fatigue
2. **Mobile bottom nav** is more thumb-friendly than drawer-only
3. **Responsive collapse** optimizes space on tablets
4. **Token-driven styling** ensures consistency and dark-mode support
5. **Maintains role-based filtering** from current system

---

## Phased Rollout

### Phase A: Foundation & Refactoring (Week 1)
**Goal:** Create new components and refactor existing code without visual changes

#### A1: Create Navigation Token System
**File:** `frontend/src/theme/navigationTokens.js` (NEW)

```javascript
export const NAV_TOKENS = {
  // Sidebar
  sidebar: {
    width: '240px',
    widthCollapsed: '60px',
    background: 'var(--tb-sunken)',
    borderRight: '1px solid var(--tb-border)',
    transitionDuration: '200ms',
  },
  
  // Navigation items
  navItem: {
    paddingDefault: '10px 12px',
    paddingSm: '8px 10px',
    paddingLg: '12px 14px',
    borderRadius: '6px',
    heightDefault: '44px',
    heightSm: '36px',
    heightLg: '52px',
    transitionDuration: '150ms',
  },
  
  // Spacing
  sectionSpacing: '12px',
  itemGap: '4px',
  
  // Colors
  colors: {
    default: { bg: 'transparent', text: 'var(--tb-text-secondary)' },
    hover: { bg: 'var(--tb-sunken)', text: 'var(--tb-text)' },
    active: { bg: 'var(--tb-brand-50)', text: 'var(--tb-brand-active)' },
    danger: { text: 'var(--tb-danger-text)' },
  },
};
```

**Dependencies:** 
- Requires no changes to existing files
- Can be merged independently

#### A2: Create Reusable Navigation Components
**Files:**
- `frontend/src/components/NavItem.tsx` (NEW)
- `frontend/src/components/NavSection.tsx` (NEW)
- `frontend/src/components/Breadcrumb.tsx` (NEW)

**Implementation:**
- Use `navigationTokens.js` for all styling
- Support both `Link` (React Router) and `button` variants
- Accessible: aria-labels, focus visible, semantic HTML

**Dependencies:**
- lucide-react (already imported)
- @/lib/utils for `cn()` utility
- navigationTokens.js

**Testing:**
- Unit tests for each component
- Snapshot tests for rendered states
- Accessibility audit (color contrast, focus)

#### A3: Refactor Sidebar.tsx
**File:** `frontend/src/layout/Sidebar.tsx` (MODIFY)

**Changes:**
1. Replace inline styles with className + navigationTokens.js
2. Remove hardcoded color references
3. Add responsive collapse behavior (hide on <480px)
4. Ensure role-based filtering matches TopNav.tsx
5. Export NavSection structure as prop interface

**Before:**
```tsx
const navLinkStyle = (active, sub = false) => ({
  borderRadius: sub ? '6px' : '8px',
  backgroundColor: active ? 'var(--primary-color)' : 'transparent',
});
```

**After:**
```tsx
<NavItem
  to={path}
  icon={icon}
  label={label}
  active={isActive}
  className={cn(
    NAV_TOKENS.navItem.borderRadius,
    activeState && NAV_TOKENS.colors.active.bg,
  )}
/>
```

**Testing:**
- Visual regression test (compare with current)
- Keyboard navigation through all links
- Verify active state indicators
- Test role-based visibility

#### A4: Create Breadcrumb Component
**File:** `frontend/src/components/Breadcrumb.tsx` (NEW)

**Features:**
- Auto-truncate long paths
- Semantic nav element
- Link all but current item
- Responsive: hidden on mobile

**Testing:**
- Truncation logic with 5+ items
- Focus indicators
- Keyboard navigation
- Mobile hide/show

### Phase B: Integration & Responsive Design (Week 2)
**Goal:** Integrate components into AdminLayout and add responsive behaviors

#### B1: Integrate Sidebar into AdminLayout
**File:** `frontend/src/layout/AdminLayout.tsx` (MODIFY)

**Changes:**
1. Import Sidebar component
2. Add flex layout: sidebar (240px) + content (flex-1)
3. Hide sidebar on mobile (<480px)
4. Add toggle button for tablet view
5. Adjust main content area width

**Structure:**
```tsx
<div className="app-shell app-shell--admin flex min-h-screen bg-background">
  {!isInIframe && <TopNav />}
  
  <div className="flex flex-1 overflow-hidden">
    {!isInIframe && isSidebarVisible && <Sidebar {...props} />}
    
    <main id="main-content" className="flex-1 overflow-y-auto">
      {/* content */}
    </main>
  </div>
  
  {/* footer remains same */}
</div>
```

**Breakpoints:**
```css
/* Tablet: show toggle, collapse sidebar */
@media (max-width: 1024px) {
  .sidebar { width: 60px; }
  .sidebar:hover { width: 240px; }
}

/* Mobile: hide sidebar entirely */
@media (max-width: 480px) {
  .sidebar { display: none; }
}
```

**Testing:**
- Sidebar visibility at each breakpoint
- Layout alignment (no content shift)
- Scroll behavior (independent scrolling)
- Touch interaction on tablet

#### B2: Update TopNav Styling
**File:** `frontend/src/components/TopNav.tsx` (MODIFY)

**Changes:**
1. Use CSS tokens instead of inline styles
2. Ensure consistency with new color system
3. Simplify hover/focus states
4. Keep mobile drawer (reuse existing pattern)

**Minimal changes:**
- No behavior changes
- Visual polish only

**Testing:**
- Dropdown menu positioning
- Mobile drawer animation
- User menu focus trap
- Theme toggle functionality

#### B3: Create Bottom Navigation Component (Mobile)
**File:** `frontend/src/components/BottomNav.tsx` (NEW)

**Features:**
- 5 main destination buttons
- Badge support for notifications
- Overflow menu for additional items
- Icon-only layout
- Visible only on <480px

**Structure:**
```tsx
<div className="bottom-nav fixed bottom-0 left-0 right-0">
  <nav role="navigation" aria-label="Mobile navigation">
    <BottomNavItem icon="home" label="Home" active />
    <BottomNavItem icon="file-earmark-text" label="Licenses" />
    <BottomNavItem icon="arrow-left-right" label="Ops" expandsMenu />
    <BottomNavItem icon="chart-line" label="Reports" expandsMenu />
    <BottomNavItem icon="more-horizontal" label="More" onClick={toggleMenu} />
  </nav>
</div>
```

**Testing:**
- Layout on actual phones
- Touch hit targets (44x44px)
- Badge display accuracy
- Menu expansion/collapse
- Animation smoothness

#### B4: Integration Tests
**Files:**
- `frontend/e2e/navigation.responsive.spec.ts` (NEW)
- `frontend/components/navigation.test.tsx` (NEW)

**Test Cases:**
1. Desktop view: sidebar visible, bottom nav hidden
2. Tablet view: sidebar collapses, expands on hover
3. Mobile view: sidebar hidden, bottom nav visible
4. All breakpoints: top bar always visible
5. Role-based filtering: same results across layouts
6. Active state: consistent across sidebar + breadcrumb

### Phase C: Accessibility & Polish (Week 3)
**Goal:** Ensure WCAG AA compliance and refine UX

#### C1: Accessibility Audit
**Checklist:**
- [ ] Color contrast: 4.5:1 for text, 3:1 for large text
- [ ] Focus indicators: 2px outline visible on all elements
- [ ] Keyboard navigation: Tab order logical, no traps
- [ ] Screen reader: aria-labels, semantic HTML
- [ ] Mobile: touch targets ≥44x44px, 8px gap
- [ ] Motion: respects prefers-reduced-motion

**Tools:**
- axe DevTools browser extension
- Lighthouse accessibility audit
- Manual keyboard navigation test
- VoiceOver / TalkBack testing

**Issues Found → Fix List:**
- Log in `.claude/logs/accessibility-audit.md`

#### C2: Dark Mode Verification
**Testing:**
1. Set `data-theme="dark"` on root
2. Visual inspection of all navigation elements
3. Color contrast check in dark mode
4. Verify no hardcoded colors leak through

**Common Issues:**
- Sidebar background too dark (fix: use token)
- Text contrast fail in hover state (fix: adjust colors)
- Border not visible in dark mode (fix: use semantic token)

#### C3: Mobile Testing on Real Devices
**Devices:**
- iPhone SE (small screen)
- iPhone 14/15 (standard)
- iPad (tablet)
- Android device (if possible)

**Checks:**
- Safe area padding (notch, home indicator)
- Bottom nav doesn't overlap content
- Sidebar drawer doesn't have scroll issues
- All touch interactions work

#### C4: Performance Optimization
**Areas:**
1. Lazy-load Sidebar on desktop view
2. Memoize NavItem components (prevent re-renders)
3. Debounce sidebar collapse/expand on tablet
4. Virtualize long lists (if Masters list grows)

**Metrics:**
- Sidebar component bundle size
- Time to interactive
- Navigation interaction latency

#### C5: Visual Polish
**Tasks:**
1. Fine-tune spacing (use 4px grid)
2. Consistent border radius (6px for buttons, 8px for cards)
3. Icon alignment (vertically centered)
4. Transition timing (150ms for interactions, 200ms for major layout shifts)
5. Dark mode: adjust colors for readability

---

## File Structure

### New Files
```
frontend/src/
├── components/
│   ├── NavItem.tsx                     (NEW)
│   ├── NavSection.tsx                  (NEW)
│   ├── Breadcrumb.tsx                  (NEW)
│   ├── BottomNav.tsx                   (NEW)
│   └── BottomNav/
│       ├── BottomNavItem.tsx
│       └── BottomNavMenu.tsx
├── layout/
│   ├── Sidebar.tsx                     (MODIFY - refactor)
│   └── AdminLayout.tsx                 (MODIFY - integrate)
├── theme/
│   ├── navigationTokens.js             (NEW)
│   └── tabler.css                      (unchanged)
├── styles/
│   └── navigation.css                  (NEW - optional, if needed for complex selectors)
├── test/
│   └── navigation.test.tsx             (NEW)
└── e2e/
    └── navigation.responsive.spec.ts   (NEW)
```

### Modified Files
```
frontend/src/
├── components/
│   ├── TopNav.tsx                      (MODIFY - optional styling cleanup)
│   └── AdminLayout.tsx                 (MODIFY - integrate sidebar + bottom nav)
├── routes/
│   └── config.js                       (unchanged, used by sidebar for nav structure)
└── layout/
    └── Sidebar.tsx                     (MODIFY - refactor styles)
```

### Files to Delete
```
None. Keep Sidebar.tsx existing code for reference during refactor.
Existing Sidebar.css (if exists) will be replaced by inline tokens.
```

---

## Implementation Details

### NavItem Component

**Location:** `frontend/src/components/NavItem.tsx`

```typescript
import React from 'react';
import { Link } from 'react-router-dom';
import { cn } from '@/lib/utils';
import Icon from '@/components/Icon';
import { NAV_TOKENS } from '@/theme/navigationTokens';

interface NavItemProps {
  to?: string;
  onClick?: () => void;
  icon?: string;
  label: React.ReactNode;
  active?: boolean;
  disabled?: boolean;
  badge?: number | string;
  variant?: 'primary' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  ariaLabel?: string;
}

export default function NavItem({
  to,
  onClick,
  icon,
  label,
  active = false,
  disabled = false,
  badge,
  variant = 'primary',
  size = 'md',
  className,
  ariaLabel,
}: NavItemProps) {
  const baseClasses = cn(
    'nav-item',
    'flex items-center gap-2.5',
    'px-3 py-2.5',
    'rounded-md',
    'transition-all duration-150',
    'text-sm font-medium',
    'outline-none',
    'focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-[var(--tb-brand)]',
    {
      'text-[var(--tb-text-secondary)] hover:text-[var(--tb-text)] hover:bg-[var(--tb-sunken)]':
        !active && !disabled,
      'text-[var(--tb-brand-active)] bg-[var(--tb-brand-50)] font-semibold border-l-3 border-[var(--tb-brand)] pl-[calc(0.75rem-3px)]':
        active,
      'text-[var(--tb-text-muted)] opacity-60 cursor-not-allowed': disabled,
      'text-[var(--tb-danger-text)]': variant === 'danger',
    },
    className,
  );

  const Inner = () => (
    <>
      {icon && <Icon name={icon} size={size === 'sm' ? 14 : size === 'lg' ? 18 : 16} />}
      <span>{label}</span>
      {badge && (
        <span className="ml-auto inline-flex items-center justify-center w-4 h-4 text-xs font-bold text-white bg-[var(--tb-danger)] rounded-full">
          {badge}
        </span>
      )}
    </>
  );

  if (to && !disabled) {
    return (
      <Link to={to} className={baseClasses} aria-label={ariaLabel} aria-current={active ? 'page' : undefined}>
        <Inner />
      </Link>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={baseClasses}
      aria-label={ariaLabel}
    >
      <Inner />
    </button>
  );
}
```

### NavSection Component

**Location:** `frontend/src/components/NavSection.tsx`

```typescript
import React, { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import NavItem from './NavItem';
import Icon from '@/components/Icon';

interface NavSectionProps {
  label?: string;
  items: Array<{
    to?: string;
    icon?: string;
    label: string;
    active?: boolean;
  }>;
  collapsible?: boolean;
  defaultOpen?: boolean;
}

export default function NavSection({
  label,
  items,
  collapsible = false,
  defaultOpen = true,
}: NavSectionProps) {
  const [open, setOpen] = useState(defaultOpen);

  if (collapsible) {
    return (
      <div className="nav-section mt-3">
        <button
          onClick={() => setOpen(!open)}
          className="w-full flex items-center justify-between px-3 py-2 rounded-md hover:bg-[var(--tb-sunken)]"
          aria-expanded={open}
        >
          <span className="flex items-center gap-2 text-xs font-semibold uppercase text-[var(--tb-text-tertiary)]">
            {label}
          </span>
          <ChevronDown size={14} className={open ? 'rotate-180' : ''} />
        </button>
        {open && (
          <ul role="group" className="mt-1">
            {items.map((item) => (
              <li key={item.to}>
                <NavItem {...item} />
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  }

  return (
    <div className="nav-section mt-3">
      {label && (
        <div className="px-3 py-2 text-xs font-semibold uppercase text-[var(--tb-text-tertiary)] tracking-wider">
          {label}
        </div>
      )}
      <ul role="group">
        {items.map((item) => (
          <li key={item.to} className="mb-0.5">
            <NavItem {...item} />
          </li>
        ))}
      </ul>
    </div>
  );
}
```

### Sidebar Integration into AdminLayout

**Key Changes:**
1. Wrap TopNav + Sidebar + Content in a flex container
2. Control sidebar visibility with media queries
3. Adjust main content width to `flex-1`

```tsx
<div className="app-shell flex flex-col min-h-screen">
  {!isInIframe && <TopNav />}
  
  <div className="flex flex-1 overflow-hidden">
    {!isInIframe && (
      <aside className="hidden lg:block w-60 overflow-y-auto bg-[var(--tb-sunken)] border-r border-[var(--tb-border)]">
        <Sidebar sections={navigationSections} brand={brand} footer={footer} />
      </aside>
    )}
    
    <main id="main-content" className="flex-1 overflow-y-auto">
      <div className="app-shell__content p-6 mx-auto w-full max-w-7xl">
        {children}
      </div>
    </main>
  </div>
  
  {!isInIframe && <footer>{/* quick actions */}</footer>}
</div>
```

### Responsive Classes

```css
/* Sidebar visibility */
.sidebar {
  @apply hidden;
}

@media (min-width: 1024px) {
  .sidebar {
    @apply block;
  }
}

/* Tablet collapse */
@media (max-width: 1024px) {
  .sidebar {
    @apply w-15 hover:w-60 transition-all duration-200;
  }
  
  .sidebar:hover .nav-item-label {
    @apply inline-block;
  }
}

/* Mobile hide */
@media (max-width: 480px) {
  .sidebar {
    @apply hidden;
  }
  
  .bottom-nav {
    @apply block;
  }
}
```

---

## Testing Strategy

### Unit Tests (Jest + React Testing Library)

**NavItem Component:**
```typescript
describe('NavItem', () => {
  it('renders as a link when `to` prop provided', () => {
    render(<NavItem to="/licenses" label="Licenses" />);
    expect(screen.getByRole('link')).toBeInTheDocument();
  });

  it('shows active state styling when active=true', () => {
    render(<NavItem active label="Active Item" />);
    expect(screen.getByText('Active Item')).toHaveClass('bg-[var(--tb-brand-50)]');
  });

  it('is disabled when disabled=true', () => {
    render(<NavItem disabled label="Disabled" />);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('displays badge when provided', () => {
    render(<NavItem label="Item" badge={3} />);
    expect(screen.getByText('3')).toBeInTheDocument();
  });
});
```

**NavSection Component:**
```typescript
describe('NavSection', () => {
  const items = [
    { to: '/a', label: 'Item A' },
    { to: '/b', label: 'Item B' },
  ];

  it('renders all items when not collapsible', () => {
    render(<NavSection items={items} />);
    expect(screen.getByText('Item A')).toBeInTheDocument();
    expect(screen.getByText('Item B')).toBeInTheDocument();
  });

  it('toggles item visibility when collapsible', async () => {
    const user = userEvent.setup();
    render(<NavSection items={items} collapsible defaultOpen={false} />);
    
    expect(screen.queryByText('Item A')).not.toBeInTheDocument();
    
    await user.click(screen.getByRole('button'));
    expect(screen.getByText('Item A')).toBeInTheDocument();
  });
});
```

### Integration Tests (Cypress)

**Responsive Navigation:**
```typescript
describe('Navigation Responsive Behavior', () => {
  it('shows sidebar on desktop (>1024px)', () => {
    cy.viewport(1280, 720);
    cy.get('[data-testid="sidebar"]').should('be.visible');
    cy.get('[data-testid="bottom-nav"]').should('not.be.visible');
  });

  it('hides sidebar and shows bottom nav on mobile (<480px)', () => {
    cy.viewport(375, 667);
    cy.get('[data-testid="sidebar"]').should('not.be.visible');
    cy.get('[data-testid="bottom-nav"]').should('be.visible');
  });

  it('maintains active state when navigating', () => {
    cy.get('[href="/licenses"]').click();
    cy.get('[href="/licenses"]').parent().should('have.class', 'is-active');
  });
});
```

### Accessibility Tests (axe)

```typescript
describe('Navigation Accessibility', () => {
  it('passes axe accessibility audit', () => {
    cy.mount(<AdminLayout><div>Content</div></AdminLayout>);
    cy.injectAxe();
    cy.checkA11y();
  });

  it('has visible focus indicators on all interactive elements', () => {
    cy.get('[data-testid="nav-item"]').first().focus();
    cy.get('[data-testid="nav-item"]').first()
      .should('have.css', 'outline');
  });

  it('maintains focus order in sidebar', () => {
    cy.get('[data-testid="sidebar"]').should('exist');
    cy.get('[data-testid="nav-item"]').each(($el) => {
      cy.wrap($el).should('be.focusable');
    });
  });
});
```

### Visual Regression Tests (Percy or Chromatic)

```typescript
describe('Navigation Visual Regression', () => {
  it('looks correct in light mode', () => {
    cy.mount(<ThemeProvider theme="light"><Navigation /></ThemeProvider>);
    cy.percySnapshot('Navigation - Light Mode');
  });

  it('looks correct in dark mode', () => {
    cy.mount(<ThemeProvider theme="dark"><Navigation /></ThemeProvider>);
    cy.percySnapshot('Navigation - Dark Mode');
  });

  it('sidebar renders correctly on tablet', () => {
    cy.viewport(768, 1024);
    cy.percySnapshot('Navigation - Tablet');
  });
});
```

---

## Rollback Plan

### Rollback Trigger
If any of these occur:
1. Critical accessibility failure (WAI-ARIA violations)
2. Navigation completely non-functional on any device
3. Significant performance regression (bundle size +50KB)
4. Color contrast failure (fail WCAG AA)

### Rollback Steps

**Option A: Revert Entire Branch**
```bash
git revert HEAD --no-edit
git push origin main
```

**Option B: Feature Flag**
```typescript
// In AdminLayout.tsx
if (FEATURE_FLAGS.NEW_NAVIGATION_SYSTEM) {
  return <AdminLayoutV2 {...props} />;
}
return <AdminLayout {...props} />;
```

Enable flag only after Phase C completion.

**Option C: Gradual Rollout**
1. Week 1: Deploy Phase A (background only, no visual changes)
2. Week 2: Deploy Phase B (with feature flag, 10% users)
3. Week 3: Full rollout if no issues

---

## Success Metrics

- [x] Audit complete
- [ ] All navigation components created without errors
- [ ] Sidebar integrated into AdminLayout
- [ ] Responsive behavior working at all breakpoints
- [ ] WCAG AA compliance verified
- [ ] Color contrast 4.5:1 on all elements
- [ ] Keyboard navigation fully functional
- [ ] Mobile bottom nav working on real devices
- [ ] Unit tests passing (>95% coverage)
- [ ] Integration tests passing
- [ ] No bundle size increase >10KB
- [ ] Performance metrics baseline met
- [ ] Zero accessibility violations (axe audit)
- [ ] Visual regression tests passing
- [ ] Mobile device testing complete
- [ ] Dark mode verified
- [ ] Rollout complete without critical issues

---

## Resources & References

- **Design System:** `/frontend/src/theme/tokens.js`, `/frontend/src/theme/tabler.css`
- **Component Library:** `/frontend/src/components/ui/`
- **Existing Navigation:** `/frontend/src/components/TopNav.tsx`, `/frontend/src/layout/Sidebar.tsx`
- **Tests:** `/frontend/e2e/`, `/frontend/src/test/`
- **Icons:** lucide-react (https://lucide.dev)

---

## Sign-Off

- **Product Designer:** Navigation & Shell specialist
- **Frontend Engineer:** Implementation lead
- **QA Lead:** Accessibility & testing certification
- **Tech Lead:** Architecture review & performance sign-off

