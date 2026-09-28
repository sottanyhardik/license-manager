# Phase 3: MUI Layout Components - Developer Reference

Quick guide for using the new Material UI layout components in License Manager.

## Overview

Phase 3 converts the main layout shell from Tailwind/shadcn to Material UI components. All authenticated pages are wrapped with the new `AdminLayout` component that now uses MUI primitives.

## File Structure

```
frontend/src/
├── layout/
│   └── AdminLayout.tsx          ← Main layout shell (CONVERTED TO MUI)
├── components/
│   ├── TopNav.tsx               ← Navigation bar (CONVERTED TO MUI)
│   └── PageHeader.tsx            ← Page header component (CONVERTED TO MUI)
├── context/
│   ├── ThemeContext.tsx          ← Theme provider (unchanged)
│   └── AuthContext.tsx           ← Auth provider (unchanged)
└── theme/
    ├── index.ts                  ← Theme configuration
    ├── components.ts             ← MUI component overrides
    ├── palette.ts                ← Color palette (light/dark)
    ├── typography.ts             ← Typography settings
    └── shadows.ts                ← Shadow definitions
```

## Component Reference

### AdminLayout

The main layout wrapper for all authenticated pages. Wraps page content with:
- Top navigation bar (AppBar)
- Responsive main content area (flex column)
- Quick-actions footer (sticky)
- Task FAB (floating action button)
- Form announcements live region (ARIA)

**Usage**:
```typescript
import AdminLayout from "@/layout/AdminLayout";

export default function MyPage() {
  return (
    <AdminLayout>
      <PageHeader title="My Page" />
      {/* Page content here */}
    </AdminLayout>
  );
}
```

**Props**: 
- `children: React.ReactNode` — Page content (required)

**Layout Structure**:
```
┌─────────────────────────────────────┐
│  AppBar (TopNav)                    │  ← Fixed height ~56px
├─────────────────────────────────────┤
│                                     │
│  Main Content Area (flex: 1)        │  ← Scrollable
│  - Responsive Container             │
│  - Full height on small screens     │
│                                     │
├─────────────────────────────────────┤
│  Quick Actions Footer (sticky)      │  ← Height 44px
└─────────────────────────────────────┘
```

**Key Features**:
- Responsive padding (xs: 2, sm: 3 in MUI spacing units)
- Dark mode support (inherited from MUI theme)
- ARIA announcements live region
- Iframe detection (hides nav/footer when embedded)

---

### TopNav

Navigation bar component with:
- Brand logo and app name (left)
- Navigation items (center, desktop only)
- Search, theme toggle, user menu (right)
- Mobile hamburger menu (mobile only)

**Structure**:
```
┌─────────────────────────────────────────────────────────┐
│ Logo │ Dashboard │ Licenses │ Reports │ Masters │ 🔍 🌙 👤 ☰ │
└─────────────────────────────────────────────────────────┘
        (hidden on mobile < md breakpoint)
```

**Navigation Groups** (from config):
- **Licenses**: Licenses, Auto Plan, Incentive Licenses, Ledger
- **Operations**: Allotments, Bill of Entry, Trades, Reconciliation
- **Reports**: Reports (if REPORT_ROLES)
- **Masters**: Masters data (HR, Rates, etc.)

**User Menu Items** (dropdown):
- Profile
- Activity Log (USER_MANAGER only)
- Users & Roles (superadmin only)
- Sign out

**Mobile Drawer** (swipe from left):
- Same navigation structure
- Grouped by section
- Quick actions in footer (Search, Profile, Theme, Sign out)

**Key Components**:
- `AppBar` — Top navigation container
- `Toolbar` — Navigation content wrapper
- `Menu` — User dropdown (MUI component)
- `Drawer` — Mobile navigation (MUI component)
- `List` — Mobile nav item list (MUI component)

---

### PageHeader

Page summary component with title, description, and action buttons.

**Usage**:
```typescript
<PageHeader
  pretitle="Dashboard"
  title="Welcome Back"
  description="Here's what's happening with your licenses"
  actions={
    <>
      <Button variant="contained">Create License</Button>
      <Button variant="outlined">Export</Button>
    </>
  }
/>
```

**Props**:
```typescript
interface PageHeaderProps {
  pretitle?: React.ReactNode;      // Small label above title
  title?: React.ReactNode;          // Main page title
  description?: React.ReactNode;    // Descriptive text
  actions?: React.ReactNode;        // Action buttons (right side)
  children?: React.ReactNode;       // Additional content
  className?: string;               // CSS class (for overrides)
}
```

**Styling**:
- Background: `palette.background.paper` (white/dark gray)
- Border: `1px solid ${palette.divider}`
- Shadow: `theme.shadows[1]`
- Padding: Responsive (xs: 2.5, sm: 3)
- Border radius: 4px

**Responsive**:
- Mobile: Full-width, actions wrap
- Tablet/Desktop: Horizontal layout

**Typography**:
- Pretitle: `variant="caption"` (uppercase, secondary color)
- Title: `variant="h4"` (bold, primary color)
- Description: `variant="body2"` (secondary color)

---

## MUI Imports

Common imports for working with the new layout:

```typescript
// Layout components
import { Box, Stack, Container } from '@mui/material';

// Navigation components
import { AppBar, Toolbar, Button, IconButton } from '@mui/material';
import { Menu, MenuItem, List, ListItem, ListItemIcon, ListItemText } from '@mui/material';
import { Drawer, Avatar } from '@mui/material';

// Typography
import { Typography } from '@mui/material';

// Utilities
import { useTheme, useMediaQuery } from '@mui/material';

// Icons (use lucide-react, not MUI icons)
import { Menu, Search, Sun, Moon, ChevronDown } from 'lucide-react';
```

## Theme Integration

All components inherit from the MUI theme configured in `src/theme/index.ts`.

### Accessing Theme in Components

```typescript
import { useTheme } from '@mui/material/styles';

function MyComponent() {
  const theme = useTheme();
  
  return (
    <Box sx={{
      backgroundColor: theme.palette.background.paper,
      borderColor: theme.palette.divider,
    }}>
      Content
    </Box>
  );
}
```

### Dark Mode

Theme automatically switches between light and dark modes based on `ThemeContext`:

```typescript
import { useTheme as useCustomTheme } from '@/context/ThemeContext';

function MyComponent() {
  const { theme, toggleTheme } = useCustomTheme();
  
  return (
    <button onClick={toggleTheme}>
      Current: {theme} (click to toggle)
    </button>
  );
}
```

## Responsive Layout

MUI breakpoints (matching Tailwind):
- `xs`: 0px (mobile)
- `sm`: 600px (mobile landscape)
- `md`: 900px (tablet)
- `lg`: 1200px (desktop)
- `xl`: 1536px (large desktop)

### Example: Responsive Styling

```typescript
<Box sx={{
  display: { xs: 'block', md: 'none' },  // Show on mobile only
  backgroundColor: { xs: 'blue', md: 'red' },  // Different colors
  padding: { xs: 1, sm: 2, md: 3 },  // Progressive padding
}}>
  Responsive content
</Box>
```

### useMediaQuery Hook

```typescript
import { useMediaQuery, useTheme } from '@mui/material';

function MyComponent() {
  const theme = useTheme();
  const isMobile = useMediaQuery(theme.breakpoints.down('md'));
  
  return isMobile ? <MobileView /> : <DesktopView />;
}
```

## Spacing System

MUI uses an 8px base unit for spacing:

```typescript
// MUI spacing scale
0,    // 0px
0.5,  // 4px
1,    // 8px
1.5,  // 12px
2,    // 16px
2.5,  // 20px
3,    // 24px
4,    // 32px
...
```

### Common Spacing Props

```typescript
<Box sx={{
  p: 2,           // padding: 16px
  px: 2,          // paddingLeft/Right: 16px
  py: 1,          // paddingTop/Bottom: 8px
  m: 1,           // margin: 8px
  gap: 1.5,       // gap between children: 12px
  mt: 3,          // marginTop: 24px
  mb: 2,          // marginBottom: 16px
}}>
</Box>
```

## Common Patterns

### Full-Width Container with Padding

```typescript
<Container maxWidth={false} sx={{ px: 2, py: 3 }}>
  <PageHeader title="My Page" />
  {/* Content */}
</Container>
```

### Horizontal Button Group

```typescript
<Stack direction="row" spacing={1}>
  <Button variant="contained">Save</Button>
  <Button variant="outlined">Cancel</Button>
</Stack>
```

### Sticky Footer

```typescript
<Box sx={{
  position: 'sticky',
  bottom: 0,
  zIndex: 40,
  borderTop: `1px solid ${theme.palette.divider}`,
  backgroundColor: theme.palette.background.paper,
  padding: 2,
}}>
  Footer content
</Box>
```

### Mobile Responsive Grid

```typescript
<Stack
  direction={{ xs: 'column', md: 'row' }}
  spacing={{ xs: 1, md: 2 }}
>
  <Box flex={1}>Column 1</Box>
  <Box flex={1}>Column 2</Box>
</Stack>
```

## Accessibility Guidelines

### ARIA Attributes

All navigation components include proper ARIA:
- AppBar includes `nav` semantics
- Drawer includes `aria-modal="true"` and `role="dialog"`
- Buttons include `aria-label` and `aria-haspopup` as needed
- Live regions for announcements (form errors, etc.)

### Keyboard Navigation

Supported out of the box:
- `Tab` — Move focus forward
- `Shift+Tab` — Move focus backward
- `Arrow Up/Down` — Navigate menu items
- `Enter` — Activate menu item
- `Escape` — Close menu/drawer

### Focus Management

- Focus visible on all interactive elements (default browser outline)
- Focus trapped in mobile drawer (can't Tab outside)
- Focus returned to trigger button when drawer closes

### Color Contrast

All colors meet WCAG AA standards in both light and dark modes:
- Text: Minimum 4.5:1 contrast
- UI components: Minimum 3:1 contrast
- Dark mode: Automatically inverted for proper contrast

## Troubleshooting

### Component Not Styled Correctly

**Problem**: Button colors don't match design system  
**Solution**: Check MUI Button overrides in `src/theme/components.ts`

### Mobile Drawer Not Closing

**Problem**: Mobile drawer stays open after clicking item  
**Solution**: Ensure `onClick={closeMobileNav}` is set on ListItem

### Dark Mode Not Working

**Problem**: Colors don't change in dark mode  
**Solution**: Use `theme.palette.[type].main` instead of hardcoded colors

### Responsive Layout Breaking

**Problem**: Layout doesn't adapt at breakpoint  
**Solution**: Use `sx={{ display: { xs: 'none', md: 'block' } }}` instead of Tailwind classes

### TypeScript Errors with MUI Components

**Problem**: Type errors with `Button`, `MenuItem`, etc.  
**Solution**: Ensure MUI is v9.4.0+ and types are installed: `npm install @types/react @types/react-dom`

## Performance Tips

1. **Lazy-load mobile drawer**: Use `Suspense` for CommandPalette
2. **Memoize callbacks**: Use `useCallback` for event handlers
3. **Avoid inline sx objects**: Define styles outside render
4. **Use Stack for layouts**: More efficient than custom flexbox

## Further Reading

- [MUI Documentation](https://mui.com/)
- [MUI Theme Customization](https://mui.com/material-ui/customization/theming/)
- [MUI Components](https://mui.com/material-ui/react-app-bar/)
- [Responsive Design](https://mui.com/material-ui/react-container/)

---

**Last Updated**: 2026-09-28  
**Phase**: 3 (App Shell & Navigation)  
**Status**: In Progress
