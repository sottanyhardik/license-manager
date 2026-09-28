# Navigation Component Specifications
**Detailed Component API & Design**
Date: 2026-09-25

---

## Table of Contents
1. [NavItem](#navitem)
2. [NavSection](#navsection)
3. [Sidebar](#sidebar)
4. [TopBar](#topbar)
5. [Breadcrumb](#breadcrumb)
6. [UserMenu](#usermenu)
7. [MobileNav](#mobilenav)
8. [BottomNav](#bottomnav)

---

## NavItem

### Purpose
Renders a single navigation link or button within a section.

### Props
```typescript
interface NavItemProps {
  // Navigation
  to?: string;              // React Router path
  onClick?: () => void;     // Handler for non-link items
  
  // Content
  icon?: string;            // lucide-react icon name
  label: React.ReactNode;   // Text label or custom content
  
  // State
  active?: boolean;         // True if current page matches
  disabled?: boolean;       // Disable interaction
  badge?: number | string;  // Optional badge (e.g., notification count)
  
  // Styling
  variant?: 'primary' | 'danger';  // 'danger' for logout
  size?: 'sm' | 'md' | 'lg';       // Padding & height
  className?: string;               // Additional classes
  
  // Accessibility
  ariaLabel?: string;
  ariaExpanded?: boolean;
}
```

### Sizing
| Size | Height | Padding | Font Size |
|------|--------|---------|-----------|
| sm | 36px | 8px 10px | 12px |
| md | 44px | 10px 12px | 14px |
| lg | 52px | 12px 14px | 16px |

### States

#### Default
```css
/* NavItem */
background: transparent;
color: var(--tb-text-secondary);
border-radius: 6px;
padding: 10px 12px;
transition: background-color 150ms, color 150ms;
```

#### Hover
```css
background: var(--tb-sunken);
color: var(--tb-text);
```

#### Active
```css
background: var(--tb-brand-50);
color: var(--tb-brand-active);
border-left: 3px solid var(--tb-brand);
padding-left: 9px; /* Adjusted for border */
font-weight: 600;
```

#### Focus
```css
outline: 2px solid var(--tb-brand);
outline-offset: -2px;
```

#### Disabled
```css
color: var(--tb-text-muted);
opacity: 0.6;
cursor: not-allowed;
pointer-events: none;
```

#### Danger (e.g., Logout)
```css
color: var(--tb-danger-text);
```
On hover:
```css
background: var(--tb-danger-soft);
color: var(--tb-danger);
```

### Badge

Position: Top-right corner of icon or label
```css
width: 16px;
height: 16px;
border-radius: 50%;
background: var(--tb-danger);
color: #fff;
font-size: 10px;
font-weight: 600;
display: flex;
align-items: center;
justify-content: center;
```

### Icon Sizing
- **sm:** 14x14px
- **md:** 16x16px
- **lg:** 18x18px

### Usage Examples

#### Basic Link
```tsx
<NavItem
  to="/licenses"
  icon="file-earmark-text"
  label="Licenses"
  active={pathname === '/licenses'}
/>
```

#### With Badge
```tsx
<NavItem
  to="/dashboard"
  icon="gauge"
  label="Dashboard"
  active={pathname === '/dashboard'}
  badge={3}
/>
```

#### Logout Button (Danger)
```tsx
<NavItem
  onClick={handleLogout}
  icon="box-arrow-right"
  label="Sign Out"
  variant="danger"
/>
```

---

## NavSection

### Purpose
Groups related navigation items under a labeled section.

### Props
```typescript
interface NavSectionProps {
  // Content
  label?: string;           // Section title ("LICENSES", "OPERATIONS", etc.)
  items: NavItemProps[];    // Child navigation items
  
  // State
  collapsible?: boolean;    // Allow expand/collapse
  defaultOpen?: boolean;    // Initial state if collapsible
  
  // Styling
  className?: string;
}
```

### Structure
```
┌─ SECTION HEADER (optional)
│  └─ 10px, 600 weight, uppercase, letter-spacing: 0.08em
│     padding: 8px 12px (top), 12px 12px (bottom)
│     color: var(--tb-text-tertiary)
├─ NAV ITEM
├─ NAV ITEM
├─ NAV ITEM
└─ (repeat)
```

### Spacing
- **Between items:** 4px gap
- **Between sections:** 12px margin-top
- **First section:** 0px margin-top

### Collapsible Behavior

When `collapsible={true}`:
```tsx
<div className="nav-section">
  <button className="nav-section-header">
    <Icon name={icon} size="14" className="mr-2" />
    <span>{label}</span>
    <ChevronDown 
      size="16" 
      className="ml-auto transition-transform"
      style={{ transform: open ? 'rotate(180deg)' : 'rotate(0deg)' }}
    />
  </button>
  {open && (
    <ul role="group">
      {items.map(item => <NavItem {...item} />)}
    </ul>
  )}
</div>
```

### Usage Examples

#### Fixed Section
```tsx
<NavSection
  label="Licensing"
  items={[
    { to: "/licenses", icon: "file-earmark-text", label: "Licenses", active },
    { to: "/license-ledger", icon: "journal-text", label: "License Ledger", active },
  ]}
/>
```

#### Collapsible Section
```tsx
<NavSection
  label="Masters"
  collapsible
  defaultOpen={false}
  items={[
    { to: "/masters/item-names", icon: "tags", label: "Item Names", active },
    { to: "/masters/groups", icon: "folder", label: "Groups", active },
  ]}
/>
```

---

## Sidebar

### Purpose
Persistent left-side navigation container for desktop views.

### Props
```typescript
interface SidebarProps {
  // Content
  sections: NavSectionProps[];  // Navigation sections
  brand?: React.ReactNode;      // Logo/branding area
  footer?: React.ReactNode;     // Bottom area (e.g., user card, help)
  
  // State
  visible?: boolean;            // Show/hide on tablet
  collapsed?: boolean;          // Icon-only mode
  
  // Styling
  className?: string;
  
  // Callbacks
  onNavigate?: (path: string) => void;
}
```

### Dimensions

**Desktop (>1024px):**
- Width: 240px (fixed)
- No collapse

**Tablet (480px - 1024px):**
- Width: 240px when expanded
- Collapses to 60px (icon-only) when not hovered
- Expands on hover or menu button click
- Smooth transition: 200ms

**Mobile (<480px):**
- Hidden (replaced by bottom nav + drawer)

### Layout
```
┌─────────────────────┐  56px
│  [Logo] Sidebar     │  (matches top bar height)
├─────────────────────┤
│  ┌─ Dashboard       │
│  ├─ SECTION 1       │
│  │ ├─ Item A        │
│  │ ├─ Item B        │
│  │ └─ Item C        │
│  ├─ SECTION 2       │
│  │ ├─ Item D        │
│  │ └─ Item E        │
│  └─ ...             │  (scrollable)
│                     │
├─────────────────────┤
│ [User Card]         │  (sticky footer)
└─────────────────────┘
```

### Styling

#### Container
```css
background: var(--tb-sunken);
border-right: 1px solid var(--tb-border);
overflow-y: auto;
overflow-x: hidden;
-webkit-overflow-scrolling: touch;
```

#### Scroll Behavior
- Smooth scrolling
- No scrollbar on mobile (use `-webkit-scrollbar-width: none`)
- Desktop: Thin scrollbar with hover effect

### Brand Area
```css
height: 56px;
padding: 12px 16px;
border-bottom: 1px solid var(--tb-border);
display: flex;
align-items: center;
gap: 10px;
font-weight: 600;
font-size: 16px;
```

### Footer Area (Optional)
```css
position: sticky;
bottom: 0;
padding: 12px 12px 16px;
border-top: 1px solid var(--tb-border);
background: var(--tb-card-bg);
```

### Tablet Collapse Animation
```css
transition: width 200ms cubic-bezier(0.4, 0, 0.2, 1);
width: 240px;

&.is-collapsed {
  width: 60px;
  
  /* Icon-only mode */
  .nav-item-label,
  .nav-section-label {
    display: none;
  }
  
  .nav-item-icon {
    margin-right: 0;
    display: flex;
    align-items: center;
    justify-content: center;
  }
}
```

### Usage Examples

#### Full Implementation
```tsx
<Sidebar
  sections={[
    {
      label: "Licensing",
      items: [
        { to: "/dashboard", icon: "gauge", label: "Dashboard", active: true },
        { to: "/licenses", icon: "file-earmark-text", label: "Licenses" },
      ]
    },
    {
      label: "Operations",
      items: [
        { to: "/allotments", icon: "box-seam", label: "Allotments" },
      ]
    }
  ]}
  brand={<ShieldCheck size={20} />}
  footer={<UserCard user={currentUser} />}
/>
```

---

## TopBar

### Purpose
Sticky header with branding, search, theme toggle, and user menu.

### Props
```typescript
interface TopBarProps {
  // Content
  brand?: string;                  // Logo text
  onSearch?: (query: string) => void;
  
  // State
  theme?: 'light' | 'dark';
  user?: User;
  
  // Styling
  className?: string;
}
```

### Dimensions
```
┌─ 56px fixed height
├─ Sticky positioning (z-index: 1020)
├─ Full viewport width
└─ Box shadow below
```

### Regions

#### Left (Brand)
```
[Icon] "License Manager"
 24px   16px 600 weight
```
Responsive: Text hidden on <480px

#### Center (Reserved)
Currently empty, available for future global messaging.

#### Right (Utilities)
```
[Search] [Theme] | [UserMenu] [Hamburger]
  20px     20px    [Variable]   20px
```
- Spacing between items: 8px
- Separator: 1px solid var(--tb-border-soft), 24px height, margin: 0 8px

### Search Button
```css
width: 40px;
height: 40px;
display: flex;
align-items: center;
justify-content: center;
border: 0;
background: transparent;
border-radius: 6px;
cursor: pointer;
transition: background-color 150ms;

/* Desktop variant: pill style */
@media (min-width: 768px) {
  width: auto;
  padding: 0 12px;
  gap: 8px;
  font-size: 12px;
}

&:hover {
  background: var(--tb-sunken);
}

&:focus-visible {
  outline: 2px solid var(--tb-brand);
  outline-offset: -2px;
}
```

### Theme Toggle
```css
Same as search button dimensions
Swaps sun/moon icon based on mode
```

### User Menu
```
Trigger: [Avatar] "username"  (desktop)
         [Avatar]             (mobile)

Desktop: 120px max-width for username
Mobile: Icon-only
```

Dropdown Menu:
```
┌─────────────────────┐
│ Signed in as        │ (gray text, small)
│ username@domain     │ (bold, larger)
├─────────────────────┤
│ Profile             │
│ Activity Log        │ (conditional)
│ Settings            │ (superadmin only)
├─────────────────────┤
│ Sign Out (danger)   │
└─────────────────────┘
```

### Mobile Toggle (Hamburger)
```
Visible only on <1024px
Width: 44px
Height: 44px
Shows/hides sidebar drawer
```

### Styling
```css
/* Container */
background: var(--tb-card-bg);
border-bottom: 1px solid var(--tb-border);
box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
padding: 0 20px;
display: flex;
align-items: center;
justify-content: space-between;
gap: 16px;

/* Utilities region */
display: flex;
align-items: center;
gap: 8px;
margin-left: auto;
```

### Keyboard Navigation
- **Tab:** Cycle through utilities left-to-right
- **Shift+Tab:** Reverse
- **Enter/Space:** Activate button
- **Escape:** Close open menus
- **Cmd+K / Ctrl+K:** Open search (global listener)

---

## Breadcrumb

### Purpose
Semantic breadcrumb trail for page context.

### Props
```typescript
interface BreadcrumbProps {
  // Content
  items: Array<{
    label: string;
    path?: string;  // Omit for current page
  }>;
  
  // Styling
  className?: string;
  truncateAt?: number;  // Show last N items + "..." (default: 3)
}
```

### Structure
```
Home > Module > Submodule > Current Page
 ↑     ↑         ↑          ↑
link   link      link       text (no link)
```

### Rendering Rules
- Show first item (home) always
- Show last 2-3 items
- Ellipsis (...) if truncated: `Home > ... > Parent > Current`
- Truncate at 3 items by default
- Non-link item (current page) is not clickable

### Styling
```css
/* Container */
display: flex;
align-items: center;
gap: 4px;
height: 20px;
margin-bottom: 12px;
flex-wrap: wrap;

/* Individual item */
font-size: 12px;
font-weight: 500;
color: var(--tb-text-secondary);
padding: 0 4px;

/* Link */
text-decoration: none;
cursor: pointer;
color: var(--tb-text-secondary);
transition: color 150ms;

&:hover {
  color: var(--tb-brand);
  text-decoration: underline;
}

&:focus-visible {
  outline: 2px solid var(--tb-brand);
  outline-offset: 2px;
}

/* Current page (no link) */
font-weight: 600;
color: var(--tb-brand);
text-decoration: none;
cursor: default;

/* Separator */
color: var(--tb-border);
margin: 0 2px;
user-select: none;
```

### Accessibility
```html
<nav aria-label="Breadcrumb navigation">
  <ol>
    <li><a href="/dashboard">Dashboard</a></li>
    <li aria-label="current page"><span>Licenses</span></li>
  </ol>
</nav>
```

### Mobile Behavior
On <480px:
- Hidden in breadcrumb
- Show only current page title
- Or integrate into PageHeader pretitle

### Usage Examples

#### Basic Breadcrumb
```tsx
<Breadcrumb
  items={[
    { label: "Dashboard", path: "/dashboard" },
    { label: "Licenses", path: "/licenses" },
    { label: "Detail" }, // Current page, no path
  ]}
/>
```

#### Auto-Truncated
```tsx
<Breadcrumb
  items={[
    { label: "Home", path: "/" },
    { label: "Module A", path: "/a" },
    { label: "Module B", path: "/a/b" },
    { label: "Sub-Module", path: "/a/b/c" },
    { label: "Current Page" }, // Will show: Home > ... > Sub-Module > Current Page
  ]}
  truncateAt={3}
/>
```

---

## UserMenu

### Purpose
User profile and session management dropdown.

### Props
```typescript
interface UserMenuProps {
  // Data
  user: {
    username: string;
    email?: string;
    avatar?: string;
    initials?: string;
  };
  
  // Actions
  onProfile?: () => void;
  onSettings?: () => void;
  onActivityLog?: () => void;
  onLogout?: () => void;
  
  // State
  isAdmin?: boolean;
  isSuperAdmin?: boolean;
  
  // Styling
  compact?: boolean;  // Icon-only on mobile
}
```

### Trigger

**Desktop (>480px):**
```
[Avatar] username
```
Width: Avatar (32px) + username (120px max) = ~160px

**Mobile (<480px):**
```
[Avatar]  (icon-only, 40x40px)
```

### Dropdown Menu

**Position:** Right-aligned, 16px from right edge

**Width:** 240px max

**Items:**
1. Header (non-interactive)
   ```
   Signed in as (gray text, 11px)
   username@domain (bold, 14px)
   ```

2. Divider

3. Links (conditional visibility)
   ```
   [person icon] Profile
   [journal icon] Activity Log       (admin only)
   [shield-lock] Users & Roles        (superadmin only)
   ```

4. Divider

5. Logout (danger)
   ```
   [box-arrow-right icon] Sign Out (red text)
   ```

### Styling

#### Trigger
```css
display: flex;
align-items: center;
gap: 8px;
padding: 8px 12px;
border-radius: 6px;
background: transparent;
cursor: pointer;
transition: background-color 150ms;

&:hover {
  background: var(--tb-sunken);
}

&:focus-visible {
  outline: 2px solid var(--tb-brand);
  outline-offset: -2px;
}

/* Avatar */
width: 32px;
height: 32px;
border-radius: 50%;
background: var(--tb-brand-50);
color: var(--tb-brand-active);
font-weight: 600;
font-size: 12px;
display: flex;
align-items: center;
justify-content: center;
overflow: hidden;

img { width: 100%; height: 100%; object-fit: cover; }

/* Username (hidden on <480px) */
max-width: 120px;
overflow: hidden;
text-overflow: ellipsis;
white-space: nowrap;
font-size: 14px;
color: var(--tb-text);

@media (max-width: 480px) {
  display: none;
}
```

#### Menu
```css
position: absolute;
top: 100%;
right: 0;
margin-top: 8px;
width: 240px;
background: var(--tb-card-bg);
border: 1px solid var(--tb-border);
border-radius: 8px;
box-shadow: 0 10px 40px rgba(0, 0, 0, 0.12);
z-index: 1000;
overflow: hidden;
animation: slideDown 150ms ease-out;

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}
```

#### Menu Items
```css
/* Header */
padding: 12px 16px;
border-bottom: 1px solid var(--tb-border);

.pretitle {
  font-size: 11px;
  font-weight: 600;
  color: var(--tb-text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 4px;
}

.username {
  font-size: 14px;
  font-weight: 600;
  color: var(--tb-text);
}

/* Links */
display: flex;
align-items: center;
gap: 10px;
padding: 10px 16px;
border: 0;
background: transparent;
color: var(--tb-text-secondary);
font-size: 14px;
cursor: pointer;
transition: background-color 150ms, color 150ms;
text-decoration: none;
text-align: left;
width: 100%;

&:hover {
  background: var(--tb-sunken);
  color: var(--tb-text);
}

&:focus-visible {
  outline: 2px solid var(--tb-brand);
  outline-offset: -2px;
}

/* Danger variant (logout) */
&.is-danger {
  color: var(--tb-danger-text);
}

&.is-danger:hover {
  background: var(--tb-danger-soft);
  color: var(--tb-danger);
}

/* Divider */
height: 1px;
background: var(--tb-border);
margin: 4px 0;
```

### Keyboard Navigation
- **Escape:** Close menu
- **Tab:** Move to next item, wraps around
- **Shift+Tab:** Previous item
- **Enter/Space:** Activate item

---

## MobileNav

### Purpose
Full-screen navigation drawer for mobile devices (<480px).

### Props
```typescript
interface MobileNavProps {
  // Content
  sections: NavSectionProps[];
  onNavigate?: (path: string) => void;
  
  // State
  open: boolean;
  onClose: () => void;
}
```

### Structure
```
┌─────────────────────────────────────┐
│ [Logo] License Manager [Close]      │  Header (56px)
├─────────────────────────────────────┤
│                                     │
│  • Dashboard                        │
│  • LICENSING                        │
│    - Licenses                       │  Body (scrollable)
│    - License Ledger                 │
│  • OPERATIONS                       │
│    - Allotments                     │
│    - Bill of Entry                  │
│                                     │
├─────────────────────────────────────┤
│ [Search] [Profile] [Theme] [Logout] │  Footer (4 utility buttons)
└─────────────────────────────────────┘
```

### Dimensions

**Position:** Left sidebar, full height
```css
position: absolute;
top: 0;
bottom: 0;
left: 0;
width: min(88vw, 360px);
```

**Breakpoint:** Hidden on >480px

### Animations

**Entrance (Open):**
```css
animation: slideInLeft 190ms var(--tb-ease) both;

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
```

**Backdrop (Entrance):**
```css
animation: fadeIn 160ms var(--tb-ease) both;

@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}
```

**Exit (Close):**
- Reverse animations
- Duration: 150ms

### Sections

#### Header
```css
display: flex;
align-items: center;
gap: 10px;
padding: env(safe-area-inset-top) 12px 0;
min-height: calc(60px + env(safe-area-inset-top));
background: linear-gradient(125deg, var(--tb-shell-navy), var(--tb-shell-navy-2));
color: #fff;

/* Brand mark & text */
font-weight: 600;
letter-spacing: -0.015em;

/* Close button */
width: 44px;
height: 44px;
margin-left: auto;
border: 0;
background: transparent;
border-radius: 6px;
cursor: pointer;
transition: background-color 150ms;

&:hover { background: rgba(255, 255, 255, 0.1); }
&:focus-visible { outline: 2px solid #fff; outline-offset: -2px; }
```

#### Body
```css
flex: 1;
overflow-y: auto;
-webkit-overflow-scrolling: touch;
padding: 12px;
```

**Nav Group:**
```css
margin-top: 16px;

&:first-of-type { margin-top: 8px; }

/* Group label */
display: flex;
align-items: center;
gap: 8px;
padding: 0 10px 8px;
color: var(--tb-text-tertiary);
font-size: 10px;
font-weight: 600;
text-transform: uppercase;
letter-spacing: 0.08em;
```

**Nav Link:**
```css
display: flex;
align-items: center;
gap: 12px;
padding: 10px 12px;
min-height: 44px;
border: 0;
border-radius: 6px;
background: transparent;
color: var(--tb-text-secondary);
font-size: 14px;
font-weight: 500;
cursor: pointer;
transition: background-color 150ms, color 150ms;
text-decoration: none;
text-align: left;
width: 100%;

&:hover,
&:focus-visible {
  background: var(--tb-sunken);
  color: var(--tb-text);
}

&.is-active {
  color: var(--tb-brand-active);
  background: var(--tb-brand-50);
  box-shadow: inset 3px 0 0 var(--tb-brand);
  font-weight: 600;
}
```

#### Footer
```css
display: grid;
grid-template-columns: 1fr 1fr;
gap: 6px;
padding: 12px max(12px, env(safe-area-inset-right)) 
         calc(12px + env(safe-area-inset-bottom)) 
         max(12px, env(safe-area-inset-left));
border-top: 1px solid var(--tb-border);
background: var(--tb-body-bg);

button {
  min-width: 0;
  padding: 10px 8px;
  border: 0;
  border-radius: 6px;
  background: transparent;
  color: var(--tb-text-secondary);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  transition: background-color 150ms, color 150ms;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

button:hover {
  background: var(--tb-sunken);
  color: var(--tb-text);
}

button.is-danger {
  color: var(--tb-danger-text);
}

button.is-danger:hover {
  background: var(--tb-danger-soft);
  color: var(--tb-danger);
}
```

### Backdrop
```css
position: fixed;
inset: 0;
background: rgba(5, 12, 26, 0.52);
z-index: 1099;
animation: fadeIn 160ms var(--tb-ease) both;
cursor: default;
```

### Accessibility

```html
<div class="tb-mobile-nav-layer" role="presentation">
  <button class="tb-mobile-nav-backdrop" aria-label="Close navigation menu" />
  <aside
    id="mobile-navigation-drawer"
    role="dialog"
    aria-modal="true"
    aria-label="Main navigation"
  >
    <!-- content -->
  </aside>
</div>
```

**Focus Management:**
- Initial focus: First focusable element in drawer
- Tab trap: Cycle within drawer, don't escape to backdrop
- Escape key: Close drawer
- Backdrop click: Close drawer

---

## BottomNav

### Purpose
Persistent bottom navigation pill for mobile (mobile <480px).

### Props
```typescript
interface BottomNavProps {
  // Routes
  items: Array<{
    id: string;
    icon: string;
    label?: string;
    badge?: number;
    to?: string;
    onClick?: () => void;
  }>;
  
  // State
  active?: string;  // Active item ID
  
  // Styling
  expanded?: boolean;  // Show labels (default: icon-only)
}
```

### Structure
```
┌───────────────────────────────────────────┐
│  [Home] [Licenses] [Ops] [Reports] [Menu] │  Pill container
└───────────────────────────────────────────┘
↑ 52px + safe-area-inset-bottom
```

### Dimensions
```css
position: fixed;
bottom: 0;
left: 0;
right: 0;
height: 52px;
padding-bottom: env(safe-area-inset-bottom);
z-index: 1050;
```

### Items

**Standard Item (Icon + Optional Label):**
```css
flex: 1;
display: flex;
flex-direction: column;
align-items: center;
justify-content: center;
gap: 2px;
border: 0;
background: transparent;
color: var(--tb-text-secondary);
font-size: 10px;
font-weight: 500;
cursor: pointer;
transition: color 150ms;
position: relative;
min-height: 52px;

&:hover {
  color: var(--tb-text);
}

&.is-active {
  color: var(--tb-brand-active);
  
  /* Underline indicator */
  &::after {
    content: '';
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: var(--tb-brand-active);
  }
}
```

**Icon Size:** 24x24px

**Badge Position:** Top-right of icon
```css
position: absolute;
top: 8px;
right: 8px;
width: 16px;
height: 16px;
background: var(--tb-danger);
color: #fff;
border-radius: 50%;
font-size: 9px;
font-weight: 700;
display: flex;
align-items: center;
justify-content: center;
```

### Collapsed vs. Expanded

**Collapsed (Icon-only):**
- Default on mobile
- Icon: 24x24px
- No label
- Compact spacing

**Expanded (Icon + Label):**
- Shows on scroll up or user interaction
- Icon: 20x20px
- Label below icon (8px gap)
- Slightly taller or pushed down with label

### Overflow Menu ("More")

If more than 5 items:
- Last item shows "..." or ⋮ (more icon)
- Click to show submenu above the pill
- Submenu appears as popover/list

```css
.bottom-nav-menu {
  position: fixed;
  bottom: 52px;
  right: 16px;
  width: auto;
  background: var(--tb-card-bg);
  border: 1px solid var(--tb-border);
  border-radius: 8px;
  box-shadow: 0 -4px 16px rgba(0, 0, 0, 0.12);
  z-index: 1040;
  animation: slideUp 150ms ease-out;
}

@keyframes slideUp {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.bottom-nav-menu-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 0;
  background: transparent;
  cursor: pointer;
  font-size: 14px;
  color: var(--tb-text-secondary);
  text-decoration: none;
  text-align: left;
  white-space: nowrap;
  transition: background-color 150ms, color 150ms;

  &:hover {
    background: var(--tb-sunken);
    color: var(--tb-text);
  }

  &:focus-visible {
    outline: 2px solid var(--tb-brand);
    outline-offset: -2px;
  }
}
```

### Keyboard Navigation
- **Tab:** Cycle through bottom nav items
- **Shift+Tab:** Reverse
- **Enter/Space:** Activate
- **Escape:** Close submenu

---

## Responsive Behavior Summary

| Component | <480px | 480-1024px | >1024px |
|-----------|--------|------------|---------|
| TopBar | Minimal (icon-only search) | Full | Full |
| Sidebar | Hidden | Collapsed (hover) | Expanded |
| BottomNav | Visible (pill) | Visible (pill) | Hidden |
| MobileNav | Hamburger drawer | Hamburger drawer | Hidden |
| Breadcrumb | Hidden/pretitle | Visible | Visible |

