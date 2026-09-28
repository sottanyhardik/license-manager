import { useState, useRef, useEffect, useCallback } from "react";
import {
  AppBar,
  Toolbar,
  Box,
  Button,
  IconButton,
  Menu,
  MenuItem,
  Stack,
  Drawer,
  List,
  ListItem,
  ListItemIcon,
  ListItemText,
  Divider,
  Typography,
  useMediaQuery,
  useTheme as useMuiTheme,
  Avatar,
  Tooltip,
} from "@mui/material";
import { ChevronDown, Menu as MenuIcon, Search, Sun, Moon, ShieldCheck, X } from "lucide-react";

/**
 * Frozen Navbar contract component.
 * This component is immutable and shared across all pages.
 * Do not override navbar height, styling, or menu structure per-page.
 */
export interface NavbarProps {
  /** Current page path (e.g., "/license-overview" or "/dashboard") */
  currentPath: string;
  /** Callback to toggle dark/light theme */
  onThemeToggle: () => void;
  /** User menu items with labels and click handlers */
  userMenuItems: Array<{ label: string; onClick: () => void }>;
}

/**
 * Menu group definition for the navbar.
 */
interface MenuGroup {
  label: string;
  items: Array<{
    label: string;
    path: string;
  }>;
}

/**
 * Route pattern matching for active state detection.
 */
const MENU_GROUPS: MenuGroup[] = [
  {
    label: "Operations",
    items: [
      { label: "Licenses", path: "/licenses" },
      { label: "Allotments", path: "/allotments" },
      { label: "Bills of Entry", path: "/bill-of-entries" },
    ],
  },
  {
    label: "Reports",
    items: [
      { label: "SION E1", path: "/reports/parle/sion-e1" },
      { label: "SION E5", path: "/reports/parle/sion-e5" },
      { label: "SION E126", path: "/reports/parle/sion-e126" },
      { label: "SION E132", path: "/reports/parle/sion-e132" },
      { label: "Expiring Licenses", path: "/reports/expiring-licenses" },
      { label: "Active Licenses", path: "/reports/active-licenses" },
      { label: "Download License", path: "/reports/download-license" },
      { label: "Item Pivot", path: "/reports/item-pivot" },
      { label: "Item Report", path: "/reports/item-report" },
      { label: "Planned Report", path: "/reports/planned-report" },
      { label: "License Purchase Profit", path: "/reports/license-purchase-profit" },
    ],
  },
  {
    label: "Masters",
    items: [
      { label: "Users & Roles", path: "/settings" },
      { label: "User Management", path: "/admin/users" },
      { label: "Activity Log", path: "/admin/activity-log" },
    ],
  },
];

/**
 * Check if the current path matches or starts with a given route.
 */
function isPathActive(currentPath: string, routePath: string): boolean {
  return currentPath === routePath || currentPath.startsWith(routePath + "/");
}

/**
 * Menu button component for the navbar.
 */
function NavMenuButton({
  label,
  items,
  isActive,
  onItemClick,
}: {
  label: string;
  items: Array<{ label: string; path: string }>;
  isActive: boolean;
  onItemClick: (path: string) => void;
}) {
  const muiTheme = useMuiTheme();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
  const open = Boolean(anchorEl);

  const handleClick = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleClose = () => {
    setAnchorEl(null);
  };

  const handleItemClick = (path: string) => {
    onItemClick(path);
    handleClose();
  };

  return (
    <>
      <Button
        onClick={handleClick}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label={`${label} menu`}
        endIcon={
          <ChevronDown
            size={14}
            style={{
              transform: open ? "rotate(180deg)" : "rotate(0deg)",
              transition: "transform 200ms",
            }}
            aria-hidden="true"
          />
        }
        sx={{
          color: isActive ? muiTheme.palette.primary.main : muiTheme.palette.text.primary,
          textTransform: "none",
          fontSize: "0.95rem",
          fontWeight: 500,
          "&:hover": {
            backgroundColor: muiTheme.palette.action.hover,
          },
        }}
      >
        {label}
      </Button>
      <Menu
        anchorEl={anchorEl}
        open={open}
        onClose={handleClose}
        anchorOrigin={{
          vertical: "bottom",
          horizontal: "left",
        }}
        transformOrigin={{
          vertical: "top",
          horizontal: "left",
        }}
        role="menu"
      >
        {items.map((item) => (
          <MenuItem
            key={item.path}
            onClick={() => handleItemClick(item.path)}
            role="menuitem"
          >
            {item.label}
          </MenuItem>
        ))}
      </Menu>
    </>
  );
}

/**
 * Main Navbar component - immutable contract.
 * Fixed height: 64px (MUI AppBar default).
 * Responsive breakpoints:
 * - Desktop (1200px+): Full navbar with text labels
 * - Tablet (768px-1199px): Compact spacing
 * - Mobile (<768px): Hamburger menu with drawer
 */
export function Navbar({
  currentPath,
  onThemeToggle,
  userMenuItems,
}: NavbarProps) {
  const muiTheme = useMuiTheme();
  const isMobile = useMediaQuery(muiTheme.breakpoints.down("md")); // < 960px (MUI md breakpoint)
  const isDarkMode = muiTheme.palette.mode === "dark";

  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);
  const [userMenuAnchorEl, setUserMenuAnchorEl] = useState<null | HTMLElement>(null);
  const userMenuOpen = Boolean(userMenuAnchorEl);
  const mobileDrawerRef = useRef<HTMLDivElement | null>(null);
  const mobileTriggerRef = useRef<HTMLButtonElement | null>(null);

  /**
   * Check if a menu group has any active items.
   */
  const isGroupActive = useCallback(
    (items: Array<{ label: string; path: string }>) =>
      items.some((item) => isPathActive(currentPath, item.path)),
    [currentPath]
  );

  /**
   * Close mobile drawer and return focus to trigger button.
   */
  const closeMobileDrawer = useCallback(() => {
    setMobileDrawerOpen(false);
    window.requestAnimationFrame(() => mobileTriggerRef.current?.focus());
  }, []);

  /**
   * Handle user menu click.
   */
  const handleUserMenuClick = (event: React.MouseEvent<HTMLElement>) => {
    setUserMenuAnchorEl(event.currentTarget);
  };

  const handleUserMenuClose = () => {
    setUserMenuAnchorEl(null);
  };

  /**
   * Handle menu item navigation (mobile drawer).
   */
  const handleNavItemClick = (path: string) => {
    // In a real app, use router.push(path) or window.location.href = path
    window.location.href = path;
    closeMobileDrawer();
  };

  /**
   * Mobile drawer keyboard trap management.
   */
  useEffect(() => {
    if (!mobileDrawerOpen) return;

    document.body.classList.add("navbar-mobile-open");

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        closeMobileDrawer();
        return;
      }

      if (event.key !== "Tab") return;

      const focusableElements = mobileDrawerRef.current?.querySelectorAll<HTMLElement>(
        'a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])'
      );

      if (!focusableElements?.length) return;

      const first = focusableElements[0];
      const last = focusableElements[focusableElements.length - 1];

      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    const frame = window.requestAnimationFrame(() =>
      mobileDrawerRef.current?.querySelector<HTMLElement>("button, a[href]")?.focus()
    );

    return () => {
      document.body.classList.remove("navbar-mobile-open");
      window.cancelAnimationFrame(frame);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [mobileDrawerOpen, closeMobileDrawer]);

  /**
   * Close drawer on route change.
   */
  useEffect(() => {
    setMobileDrawerOpen(false);
  }, [currentPath]);

  const isDashboardActive = isPathActive(currentPath, "/dashboard");

  return (
    <>
      {/* Main Navbar */}
      <AppBar
        position="static"
        className="navbar navbar--frozen"
        aria-label="Main navigation"
        elevation={1}
        sx={{
          height: 64, // Fixed height per contract
        }}
      >
        <Toolbar
          disableGutters
          sx={{
            height: 64,
            px: { xs: 1.5, sm: 2, md: 3 },
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 2,
          }}
        >
          {/* Brand Logo + Name */}
          <Button
            href="/"
            sx={{
              display: "flex",
              alignItems: "center",
              gap: 1,
              color: muiTheme.palette.primary.main,
              textTransform: "none",
              fontSize: "1.1rem",
              fontWeight: 600,
              minWidth: "auto",
              "&:hover": {
                backgroundColor: "transparent",
              },
            }}
            aria-label="License Manager Home"
            className="navbar__brand"
          >
            <ShieldCheck size={20} aria-hidden="true" />
            <Box component="span" sx={{ display: { xs: "none", sm: "inline" } }}>
              License Manager
            </Box>
          </Button>

          {/* Desktop Navigation */}
          {!isMobile && (
            <Stack
              direction="row"
              spacing={0.5}
              sx={{ flex: 1, ml: 3 }}
              aria-label="Primary navigation"
            >
              {/* Dashboard */}
              <Button
                href="/dashboard"
                sx={{
                  color: isDashboardActive
                    ? muiTheme.palette.primary.main
                    : muiTheme.palette.text.primary,
                  textTransform: "none",
                  fontSize: "0.95rem",
                  fontWeight: isDashboardActive ? 600 : 500,
                  "&:hover": {
                    backgroundColor: muiTheme.palette.action.hover,
                  },
                }}
                aria-current={isDashboardActive ? "page" : undefined}
              >
                Dashboard
              </Button>

              {/* Menu Groups */}
              {MENU_GROUPS.map((group) => (
                <NavMenuButton
                  key={group.label}
                  label={group.label}
                  items={group.items}
                  isActive={isGroupActive(group.items)}
                  onItemClick={handleNavItemClick}
                />
              ))}
            </Stack>
          )}

          {/* Right-side Controls */}
          <Stack
            direction="row"
            spacing={0.5}
            sx={{ ml: isMobile ? "auto" : 0, display: "flex", alignItems: "center" }}
            aria-label="Session controls"
          >
            {/* Search Button */}
            <Tooltip title="Search (⌘K)">
              <IconButton
                aria-label="Search"
                size="small"
                sx={{
                  display: { xs: "none", sm: "flex" },
                }}
                // TODO: Wire up global search handler
              >
                <Search size={18} aria-hidden="true" />
              </IconButton>
            </Tooltip>

            {/* Theme Toggle */}
            <Tooltip title={isDarkMode ? "Light mode" : "Dark mode"}>
              <IconButton
                onClick={onThemeToggle}
                aria-label={isDarkMode ? "Switch to light mode" : "Switch to dark mode"}
                size="small"
              >
                {isDarkMode ? (
                  <Sun size={18} aria-hidden="true" />
                ) : (
                  <Moon size={18} aria-hidden="true" />
                )}
              </IconButton>
            </Tooltip>

            {/* User Menu */}
            <Tooltip title="User menu">
              <IconButton
                onClick={handleUserMenuClick}
                size="small"
                aria-label="User menu"
                aria-haspopup="menu"
                aria-expanded={userMenuOpen}
                sx={{ ml: 1 }}
              >
                <Avatar
                  sx={{
                    width: 32,
                    height: 32,
                    fontSize: "0.85rem",
                    backgroundColor: muiTheme.palette.primary.main,
                  }}
                >
                  H
                </Avatar>
              </IconButton>
            </Tooltip>
            <Menu
              anchorEl={userMenuAnchorEl}
              open={userMenuOpen}
              onClose={handleUserMenuClose}
              anchorOrigin={{
                vertical: "bottom",
                horizontal: "right",
              }}
              transformOrigin={{
                vertical: "top",
                horizontal: "right",
              }}
              role="menu"
            >
              {userMenuItems.map((item, index) => (
                <MenuItem
                  key={index}
                  onClick={() => {
                    item.onClick();
                    handleUserMenuClose();
                  }}
                  role="menuitem"
                >
                  {item.label}
                </MenuItem>
              ))}
            </Menu>

            {/* Mobile Menu Toggle */}
            <IconButton
              ref={mobileTriggerRef}
              onClick={() => setMobileDrawerOpen((prev) => !prev)}
              aria-label={mobileDrawerOpen ? "Close navigation menu" : "Open navigation menu"}
              aria-expanded={mobileDrawerOpen}
              aria-controls="mobile-navigation-drawer"
              size="small"
              sx={{
                display: { xs: "flex", md: "none" },
              }}
            >
              <MenuIcon size={20} aria-hidden="true" />
            </IconButton>
          </Stack>
        </Toolbar>
      </AppBar>

      {/* Mobile Navigation Drawer */}
      <Drawer
        anchor="left"
        open={mobileDrawerOpen}
        onClose={closeMobileDrawer}
        id="mobile-navigation-drawer"
        aria-label="Mobile navigation"
        sx={{
          "& .MuiDrawer-paper": {
            width: { xs: "100%", sm: 300 },
          },
        }}
      >
        <Box
          ref={mobileDrawerRef}
          role="dialog"
          aria-modal="true"
          aria-label="Navigation menu"
          sx={{
            display: "flex",
            flexDirection: "column",
            height: "100%",
          }}
        >
          {/* Drawer Header */}
          <Box
            sx={{
              p: 2,
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              borderBottom: `1px solid ${muiTheme.palette.divider}`,
            }}
          >
            <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
              <ShieldCheck size={18} aria-hidden="true" />
              <Typography variant="subtitle1" sx={{ fontWeight: 600 }}>
                License Manager
              </Typography>
            </Box>
            <IconButton onClick={closeMobileDrawer} size="small" aria-label="Close menu">
              <X size={20} aria-hidden="true" />
            </IconButton>
          </Box>

          {/* Drawer Navigation */}
          <Box sx={{ flex: 1, overflowY: "auto", py: 1 }}>
            <List>
              <ListItem
                component="a"
                href="/dashboard"
                onClick={closeMobileDrawer}
                sx={{
                  cursor: "pointer",
                  backgroundColor: isDashboardActive ? 'action.selected' : 'transparent',
                  '&:hover': {
                    backgroundColor: 'action.hover',
                  }
                }}
              >
                <ListItemText primary="Dashboard" />
              </ListItem>
            </List>

            {/* Menu Groups */}
            {MENU_GROUPS.map((group) => (
              <Box key={group.label}>
                <Typography
                  variant="caption"
                  sx={{
                    px: 2,
                    py: 1,
                    display: "block",
                    fontWeight: 600,
                    textTransform: "uppercase",
                    color: muiTheme.palette.text.secondary,
                  }}
                >
                  {group.label}
                </Typography>
                <List disablePadding>
                  {group.items.map((item) => (
                    <ListItem
                      key={item.path}
                      component="a"
                      href={item.path}
                      onClick={closeMobileDrawer}
                      sx={{
                        pl: 4,
                        cursor: "pointer",
                        backgroundColor: isPathActive(currentPath, item.path) ? 'action.selected' : 'transparent',
                        '&:hover': {
                          backgroundColor: 'action.hover',
                        }
                      }}
                    >
                      <ListItemText primary={item.label} />
                    </ListItem>
                  ))}
                </List>
              </Box>
            ))}
          </Box>

          {/* Drawer Footer */}
          <Box
            sx={{
              p: 1.5,
              borderTop: `1px solid ${muiTheme.palette.divider}`,
            }}
          >
            <Button
              fullWidth
              onClick={onThemeToggle}
              startIcon={isDarkMode ? <Sun size={16} /> : <Moon size={16} />}
              sx={{
                mb: 1,
                justifyContent: "flex-start",
                textTransform: "none",
              }}
            >
              {isDarkMode ? "Light mode" : "Dark mode"}
            </Button>
            {userMenuItems.map((item, index) => (
              <Button
                key={index}
                fullWidth
                onClick={() => {
                  item.onClick();
                  closeMobileDrawer();
                }}
                sx={{
                  mb: 1,
                  justifyContent: "flex-start",
                  textTransform: "none",
                }}
              >
                {item.label}
              </Button>
            ))}
          </Box>
        </Box>
      </Drawer>
    </>
  );
}
