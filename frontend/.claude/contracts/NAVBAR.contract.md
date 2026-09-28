# NAVBAR Contract (FROZEN)

**Status**: IMMUTABLE - This contract defines a fixed API. No page-specific variations allowed.

## Component: `Navbar.tsx`

**Location**: `/frontend/src/components/layout/Navbar.tsx`

### Props Interface

```typescript
interface NavbarProps {
  /** Current page path (e.g., "/license-overview" or "/dashboard") */
  currentPath: string;
  
  /** Callback to toggle dark/light theme */
  onThemeToggle: () => void;
  
  /** User menu items with labels and click handlers */
  userMenuItems: Array<{ label: string; onClick: () => void }>;
}
```

### Usage Example

```tsx
import { Navbar } from "@/components/layout/Navbar";
import { useLocation } from "react-router-dom";
import { useTheme } from "@/context/ThemeContext";

export default function MyLayout() {
  const location = useLocation();
  const { toggleTheme } = useTheme();
  
  const userMenuItems = [
    { label: "Profile", onClick: () => navigate("/profile") },
    { label: "Settings", onClick: () => navigate("/settings") },
    { label: "Logout", onClick: logout },
  ];
  
  return (
    <>
      <Navbar 
        currentPath={location.pathname}
        onThemeToggle={toggleTheme}
        userMenuItems={userMenuItems}
      />
      {/* Page content */}
    </>
  );
}
```

## Visual Specification

### Enterprise Navy/Slate Shell

- **Light Mode**: Slate background, blue text for active routes
- **Dark Mode**: Navy background, lighter blue for active routes
- **No gradients, no AI-style effects** — solid colors only
- **Theme colors from MUI theme.palette**:
  - Primary: Blue (active state)
  - Background: Slate/Navy (light/dark)
  - Text: Adaptive to mode

### Layout & Components

```
┌──────────────────────────────────────────────────────────────────────────┐
│ 🛡 License Manager │ Dashboard │ Operations ▾ │ Reports ▾ │ Masters ▾ │ 🔍 ◐ H │
└──────────────────────────────────────────────────────────────────────────┘
```

#### Left Section (Brand)
- **Logo Icon**: Shield ✓ (ShieldCheck from lucide-react)
- **App Name**: "License Manager" (hidden on mobile)
- **Link**: Navigates to home (`/`)

#### Center Section (Navigation) — Desktop Only
- **Dashboard**: Direct link, active when currentPath === "/dashboard"
- **Operations Menu**: Dropdown for Operations group
- **Reports Menu**: Dropdown for Reports group
- **Masters Menu**: Dropdown for Masters group

#### Right Section (Controls)
- **Search Icon**: Placeholder (TODO: wire to global search handler)
- **Theme Toggle**: Sun/Moon icon, calls onThemeToggle()
- **User Avatar**: Initials, opens menu with userMenuItems
- **Mobile Hamburger**: Menu icon, opens drawer (mobile only)

### Height (FIXED)

- **64px** — MUI AppBar default height
- **Consistent across all pages** — never override per-page
- **Affects layout**: Pages render below this fixed height

## Menu Structure

### Operations Group
```
Operations (dropdown)
├── Licenses        → /licenses
├── Allotments      → /allotments
└── Bills of Entry  → /bill-of-entries
```

### Reports Group
```
Reports (dropdown)
├── SION E1                  → /reports/parle/sion-e1
├── SION E5                  → /reports/parle/sion-e5
├── SION E126                → /reports/parle/sion-e126
├── SION E132                → /reports/parle/sion-e132
├── Expiring Licenses        → /reports/expiring-licenses
├── Active Licenses          → /reports/active-licenses
├── Download License         → /reports/download-license
├── Item Pivot               → /reports/item-pivot
├── Item Report              → /reports/item-report
├── Planned Report           → /reports/planned-report
└── License Purchase Profit  → /reports/license-purchase-profit
```

### Masters Group
```
Masters (dropdown)
├── Users & Roles       → /settings
├── User Management     → /admin/users
└── Activity Log        → /admin/activity-log
```

## Active Route Detection

**Rule**: A nav item is active (blue highlight) when:
- `currentPath === routePath` (exact match), OR
- `currentPath.startsWith(routePath + "/")` (path starts with item + "/")

**Examples**:
- currentPath="/dashboard" → Dashboard active
- currentPath="/licenses" → Operations active
- currentPath="/licenses/123/edit" → Operations active (matches /licenses)
- currentPath="/reports/item-pivot" → Reports active

## Responsive Breakpoints

### Desktop (1200px and up)
- Full navbar with text labels
- All navigation visible: Dashboard + 3 menu buttons
- Search icon visible
- Theme toggle visible
- User menu visible
- NO mobile hamburger

### Tablet (768px to 1199px)
- Same as desktop (MUI `md` breakpoint down = < 960px)
- Navigation items visible with icons and text
- Compact spacing

### Mobile (below 768px)
- Brand logo only (no text)
- NO navigation items in toolbar
- Search icon hidden (visible in drawer)
- Theme toggle visible (also in drawer)
- User menu button visible (also in drawer)
- **Mobile hamburger menu** opens drawer with all items

### Mobile Drawer
- Opens when hamburger is clicked
- Full-width or 300px on small screens
- Contains:
  - **Header**: Logo + "License Manager" text + close button
  - **Navigation**: All menu items (Dashboard + all groups)
  - **Footer**: Theme toggle + user menu items
- **Keyboard trap**: Tab cycles through drawer items, Escape closes
- **Auto-closes** on:
  - Route change (currentPath change)
  - Menu item click
  - Close button click
  - Escape key

## Keyboard Navigation

### Desktop
- **Tab**: Cycle through nav items, search, theme, user menu
- **Enter/Space**: Activate buttons or menu
- **Arrow keys**: Navigate within open menus
- **Escape**: Close open menus

### Mobile Drawer
- **Tab**: Cycle through drawer items
- **Shift+Tab**: Reverse cycle (with wrap-around)
- **Escape**: Close drawer
- **Enter/Space**: Activate links

## Accessibility (WCAG AA)

### ARIA Labels
- AppBar: `aria-label="Main navigation"`
- Dashboard button: `aria-current="page"` when active
- Menu buttons: `aria-haspopup="menu"` and `aria-expanded={open}`
- Menu items: `role="menuitem"`
- Menus: `role="menu"`
- User avatar button: `aria-label="User menu"`
- Theme toggle: `aria-label="Switch to dark/light mode"`
- Search: `aria-label="Search (⌘K)"`
- Mobile hamburger: `aria-expanded`, `aria-controls="mobile-navigation-drawer"`
- Mobile drawer: `role="dialog"`, `aria-modal="true"`

### Focus Management
- Visible focus indicator (MUI Button default)
- Focus restored to hamburger when drawer closes
- Tab trap in drawer (Shift+Tab wraps to bottom, Tab wraps to top)
- Active nav items highlighted in blue (sufficient contrast in light/dark modes)

### Color Contrast
- Text on background: AA standard (enforced by MUI theme)
- Active items: Primary blue (theme.palette.primary.main)
- No hardcoded colors — all from theme.palette

## Non-Negotiable Requirements (FROZEN)

- ✓ **MUI-based only** — AppBar, Toolbar, Box, Button, IconButton, Menu, MenuItem, Drawer, etc.
- ✓ **Shared application-shell component** — NOT page-specific
- ✓ **Fixed 64px height** across every page
- ✓ **No page overrides** to navbar height, styling, or menu structure
- ✓ **Operations/Reports/Masters use MUI menus** (not custom dropdowns)
- ✓ **Active route clearly identifiable** (blue highlight)
- ✓ **Search icon + theme control + user menu** in top-right
- ✓ **Keyboard navigation** (Tab, Enter, Escape for menus)
- ✓ **ARIA labels on all interactive elements**
- ✓ **Responsive**: Desktop (1200px+) → Tablet (768px–1199px) → Mobile (<768px)
- ✓ **No gradients or AI-style effects** — solid colors only
- ✓ **All existing routes/permissions preserved**

## Integration Notes

### Where It Lives in the App

The Navbar is imported **once** in `AdminLayout.tsx` (or at the root level):

```tsx
import { Navbar } from "@/components/layout/Navbar";

export default function AdminLayout({ children }) {
  const location = useLocation();
  const { toggleTheme } = useTheme();
  const { user, logout } = useContext(AuthContext);
  
  const userMenuItems = [
    { label: "Profile", onClick: () => navigate("/profile") },
    { label: "Logout", onClick: logout },
  ];
  
  return (
    <Box sx={{ display: "flex", flexDirection: "column", minHeight: "100vh" }}>
      <Navbar 
        currentPath={location.pathname}
        onThemeToggle={toggleTheme}
        userMenuItems={userMenuItems}
      />
      <Box sx={{ flex: 1 }}>
        {children}
      </Box>
    </Box>
  );
}
```

### What NOT to Do

- ❌ Do NOT override `AppBar` height in pages
- ❌ Do NOT pass different menu structures per-page
- ❌ Do NOT add page-specific nav items
- ❌ Do NOT style navbar from page components
- ❌ Do NOT use Radix or shadcn components (MUI only)
- ❌ Do NOT add gradients, shadows, or visual effects
- ❌ Do NOT change the props interface
- ❌ Do NOT nest another navbar below this one

## Testing Checklist

### Visual
- [ ] Logo and app name visible on desktop
- [ ] Logo only on mobile
- [ ] Active nav items highlighted in blue
- [ ] Dashboard link works
- [ ] Operations menu opens/closes
- [ ] Reports menu opens/closes
- [ ] Masters menu opens/closes
- [ ] Search icon visible (desktop/tablet)
- [ ] Theme toggle works (dark ↔ light)
- [ ] User avatar visible with initials
- [ ] User menu opens/closes
- [ ] Mobile hamburger visible on mobile
- [ ] Drawer opens when hamburger clicked

### Responsive
- [ ] Test at 375px (mobile)
- [ ] Test at 768px (tablet breakpoint)
- [ ] Test at 1200px (desktop)
- [ ] Test at 1536px (large desktop)
- [ ] Drawer collapses at breakpoint
- [ ] No layout shift when drawer opens

### Keyboard Navigation
- [ ] Tab cycles through all interactive elements
- [ ] Enter/Space activates buttons
- [ ] Arrow keys navigate menus
- [ ] Escape closes menus
- [ ] Escape closes drawer
- [ ] Tab traps in drawer (wraps around)
- [ ] Shift+Tab reverses in drawer
- [ ] Focus returns to hamburger when drawer closes

### Accessibility
- [ ] All buttons have aria-labels
- [ ] Menus have role="menu" and items have role="menuitem"
- [ ] Active nav items announced to screen readers
- [ ] Theme toggle label updates based on mode
- [ ] Mobile drawer is modal with aria-modal="true"
- [ ] Sufficient color contrast in light/dark modes
- [ ] Focus indicators visible

### Theme
- [ ] Navbar renders correctly in light mode
- [ ] Navbar renders correctly in dark mode
- [ ] Active items use primary.main color
- [ ] No hardcoded colors — all from theme
- [ ] Drawer background matches theme

## Version History

| Version | Date       | Status    | Notes                               |
|---------|------------|-----------|-------------------------------------|
| 1.0     | 2026-09-28 | FROZEN    | Initial contract, immutable         |

---

**IMPORTANT**: This contract is immutable after build. Do not iterate on it later.
