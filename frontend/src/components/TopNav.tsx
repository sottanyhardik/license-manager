import React, { lazy, Suspense, useCallback, useContext, useEffect, useRef, useState } from "react";
import { Link as RouterLink, useLocation } from "react-router-dom";
import {
    AppBar,
    Toolbar,
    Box,
    Stack,
    Button,
    IconButton,
    Menu as MuiMenu,
    MenuItem,
    Drawer,
    List,
    ListItem,
    ListItemIcon,
    ListItemText,
    Divider,
    Typography,
    useMediaQuery,
    useTheme as useMuiTheme,
    Badge,
    Avatar,
} from "@mui/material";
import { AuthContext } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { reportEntities, masterEntities } from "../routes/config";
import { REPORT_ROLES } from "../routes/authorizationRoles";
import { ChevronDown, Gauge, Menu, Search, ShieldCheck, X, Sun, Moon } from "lucide-react";
import Icon from "@/components/Icon";

// cmdk and its dialog primitives are only useful after the user opens global
// search.  Keeping them out of the navigation chunk materially reduces the
// authenticated first-paint payload without changing the command workflow.
const CommandPalette = lazy(() => import("./CommandPalette"));

const NAV_GROUPS = [
    {
        label: "Licenses",
        icon: "file-earmark-text",
        items: [
            { path: "/licenses",           label: "Licenses",           icon: "file-earmark-text", roles: ["LICENSE_MANAGER", "LICENSE_VIEWER"] },
            { path: "/planning",           label: "Auto Plan",          icon: "diagram-3",          roles: ["LICENSE_MANAGER"] },
            { path: "/incentive-licenses", label: "Incentive Licenses", icon: "award",              roles: ["INCENTIVE_LICENSE_MANAGER", "INCENTIVE_LICENSE_VIEWER"] },
            { path: "/license-ledger",     label: "License Ledger",     icon: "journal-text",       roles: ["LICENSE_MANAGER", "TRADE_MANAGER", "TRADE_VIEWER", "LEDGER_MANAGER"] },
            { path: "/ledger-upload",      label: "Ledger Upload",      icon: "cloud-upload",       roles: ["LICENSE_MANAGER", "LEDGER_MANAGER"] },
        ],
    },
    {
        label: "Operations",
        icon: "arrow-left-right",
        items: [
            { path: "/allotments",      label: "Allotments",     icon: "box-seam",         roles: ["ALLOTMENT_MANAGER", "ALLOTMENT_VIEWER"] },
            { path: "/bill-of-entries", label: "Bill of Entry",  icon: "receipt",          roles: ["BOE_MANAGER", "BOE_VIEWER", "TL_GENERATE", "ACCOUNT_ACCESS"] },
            { path: "/trades",          label: "Trade In & Out", icon: "arrow-left-right", roles: ["TRADE_MANAGER", "TRADE_VIEWER"] },
            { path: "/reconciliation",  label: "Reconciliation", icon: "check2-square",    roles: ["BOE_MANAGER", "TRADE_MANAGER", "ACCOUNT_ACCESS"] },
        ],
    },
];


interface NavMenuItemProps {
    to?: string;
    icon?: string;
    label?: React.ReactNode;
    active?: boolean;
    onClick?: () => void;
    danger?: boolean;
}

function NavMenuItem({ to, icon, label, active, onClick, danger = false }: NavMenuItemProps) {
    const muiTheme = useMuiTheme();
    const componentProps = onClick
        ? { onClick, type: "button" as const }
        : { component: RouterLink as any, to };

    return (
        <MenuItem
            {...componentProps}
            selected={active}
            sx={{
                color: danger ? muiTheme.palette.error.main : muiTheme.palette.text.primary,
                "&.Mui-selected": {
                    backgroundColor: danger ? muiTheme.palette.error.light : muiTheme.palette.primary.light,
                    color: danger ? muiTheme.palette.error.main : muiTheme.palette.primary.main,
                },
            }}
        >
            {icon && (
                <ListItemIcon sx={{ minWidth: 32 }}>
                    <Icon name={icon} className="size-4" aria-hidden="true" />
                </ListItemIcon>
            )}
            <Typography variant="body2">{label}</Typography>
        </MenuItem>
    );
}

interface NavMenuProps {
    icon?: string;
    label?: React.ReactNode;
    items: React.ReactNode[];
    isActive?: boolean;
    end?: boolean;
}

function NavMenu({ icon, label, items, isActive }: NavMenuProps) {
    const muiTheme = useMuiTheme();
    const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);
    const open = Boolean(anchorEl);

    const handleClick = (event: React.MouseEvent<HTMLElement>) => {
        setAnchorEl(event.currentTarget);
    };
    const handleClose = () => {
        setAnchorEl(null);
    };

    return (
        <>
            <Button
                onClick={handleClick}
                endIcon={
                    <ChevronDown
                        size={14}
                        style={{
                            transform: open ? "rotate(180deg)" : "rotate(0deg)",
                            transition: "transform 200ms",
                        }}
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
                {icon && <Icon name={icon} className="size-4 mr-2" aria-hidden="true" />}
                {label}
            </Button>
            <MuiMenu
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
            >
                {items}
            </MuiMenu>
        </>
    );
}


export default function TopNav() {
    const { user, logout, isSuperAdmin, hasAnyRole } = useContext(AuthContext);
    const { theme, toggleTheme } = useTheme();
    const muiTheme = useMuiTheme();
    const location = useLocation();
    const isMobile = useMediaQuery(muiTheme.breakpoints.down("md"));
    const [cmdOpen, setCmdOpen] = useState(false);
    const [mobileOpen, setMobileOpen] = useState(false);
    const [userMenuAnchorEl, setUserMenuAnchorEl] = useState<null | HTMLElement>(null);
    const userMenuOpen = Boolean(userMenuAnchorEl);
    const mobileDrawerRef = useRef<HTMLDivElement | null>(null);
    const mobileTriggerRef = useRef<HTMLButtonElement | null>(null);

    const isPathActive = (path) =>
        location.pathname === path || location.pathname.startsWith(path + "/");
    const isGroupActive = (items) => items.some(i => isPathActive(i.path));
    const isDashActive = isPathActive("/dashboard");

    const openCmd = useCallback(() => setCmdOpen(true), []);
    const closeCmd = useCallback(() => setCmdOpen(false), []);
    const closeMobileNav = useCallback(() => {
        setMobileOpen(false);
        window.requestAnimationFrame(() => mobileTriggerRef.current?.focus());
    }, []);

    const handleUserMenuClick = (event: React.MouseEvent<HTMLElement>) => {
        setUserMenuAnchorEl(event.currentTarget);
    };
    const handleUserMenuClose = () => {
        setUserMenuAnchorEl(null);
    };

    const visibleGroups = NAV_GROUPS.map(group => ({
        ...group,
        items: group.items.filter(item => !item.roles || hasAnyRole(item.roles)),
    })).filter(group => group.items.length > 0);

    useEffect(() => {
        const handler = (e: KeyboardEvent) => {
            if ((e.metaKey || e.ctrlKey) && e.key === "k") {
                e.preventDefault();
                setCmdOpen(v => !v);
            }
        };
        document.addEventListener("keydown", handler);
        return () => document.removeEventListener("keydown", handler);
    }, []);

    useEffect(() => {
        if (!mobileOpen) return;
        document.body.classList.add("tb-mobile-nav-open");
        const onKeyDown = (event: KeyboardEvent) => {
            if (event.key === "Escape") { event.preventDefault(); closeMobileNav(); return; }
            if (event.key !== "Tab") return;
            const nodes = mobileDrawerRef.current?.querySelectorAll<HTMLElement>('a[href], button:not([disabled]), [tabindex]:not([tabindex="-1"])');
            if (!nodes?.length) return;
            const first = nodes[0];
            const last = nodes[nodes.length - 1];
            if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        };
        document.addEventListener("keydown", onKeyDown);
        const frame = window.requestAnimationFrame(() => mobileDrawerRef.current?.querySelector<HTMLElement>("button, a[href]")?.focus());
        return () => {
            document.body.classList.remove("tb-mobile-nav-open");
            window.cancelAnimationFrame(frame);
            document.removeEventListener("keydown", onKeyDown);
        };
    }, [closeMobileNav, mobileOpen]);

    useEffect(() => setMobileOpen(false), [location.pathname]);

    return (
        <>
            <AppBar
                position="static"
                className="tb-nav top-nav top-nav--premium"
                aria-label="Main navigation"
                elevation={1}
            >
                <Toolbar
                    disableGutters
                    sx={{
                        px: { xs: 1.5, sm: 3 },
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        gap: 2,
                    }}
                >
                    {/* Brand */}
                    <Button
                        component={RouterLink}
                        to="/"
                        sx={{
                            display: "flex",
                            alignItems: "center",
                            gap: 1,
                            color: muiTheme.palette.primary.main,
                            textTransform: "none",
                            fontSize: "1.1rem",
                            fontWeight: 600,
                            "&:hover": {
                                backgroundColor: "transparent",
                            },
                        }}
                        className="tb-nav-brand"
                    >
                        <ShieldCheck size={18} aria-hidden="true" />
                        <Box component="span" sx={{ display: { xs: "none", sm: "inline" } }}>
                            License Manager
                        </Box>
                    </Button>

                    {/* Desktop Nav Items */}
                    {!isMobile && (
                        <Stack direction="row" spacing={0} sx={{ flex: 1, ml: 3 }} aria-label="Primary sections">
                            <Button
                                component={RouterLink}
                                to="/dashboard"
                                startIcon={<Gauge size={16} aria-hidden="true" />}
                                sx={{
                                    color: isDashActive ? muiTheme.palette.primary.main : muiTheme.palette.text.primary,
                                    textTransform: "none",
                                    fontSize: "0.95rem",
                                    fontWeight: isDashActive ? 600 : 500,
                                }}
                            >
                                Dashboard
                            </Button>

                            {visibleGroups.map(group => (
                                <NavMenu
                                    key={group.label}
                                    icon={group.icon}
                                    label={group.label}
                                    isActive={isGroupActive(group.items)}
                                    items={group.items.map(item => (
                                        <NavMenuItem
                                            key={item.path}
                                            to={item.path}
                                            icon={item.icon}
                                            label={item.label}
                                            active={isPathActive(item.path)}
                                        />
                                    ))}
                                />
                            ))}

                            {hasAnyRole(REPORT_ROLES) && (
                                <NavMenu
                                    icon="bar-chart-line"
                                    label="Reports"
                                    isActive={isGroupActive(reportEntities)}
                                    items={reportEntities.map(r => (
                                        <NavMenuItem
                                            key={r.path}
                                            to={r.path}
                                            icon={r.icon}
                                            label={r.label}
                                            active={isPathActive(r.path)}
                                        />
                                    ))}
                                />
                            )}

                            <NavMenu
                                icon="database"
                                label="Masters"
                                isActive={isGroupActive(masterEntities)}
                                items={masterEntities.filter(m => !m.deprecated).map(m => (
                                    <NavMenuItem
                                        key={m.path}
                                        to={m.path}
                                        icon={m.icon}
                                        label={m.label}
                                        active={isPathActive(m.path)}
                                    />
                                ))}
                            />
                        </Stack>
                    )}

                    {/* Right-side controls */}
                    <Stack direction="row" spacing={0.5} sx={{ ml: "auto", display: "flex", alignItems: "center" }} aria-label="Session controls">
                        {/* Search button */}
                        <IconButton
                            onClick={openCmd}
                            aria-label="Search (⌘K)"
                            title="Search ⌘K"
                            size="small"
                            sx={{
                                display: { xs: "none", sm: "flex" },
                            }}
                        >
                            <Search size={18} aria-hidden="true" />
                        </IconButton>

                        {/* Dark mode toggle */}
                        <IconButton
                            onClick={toggleTheme}
                            aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
                            title={theme === "dark" ? "Light mode" : "Dark mode"}
                            size="small"
                        >
                            {theme === "dark" ? (
                                <Sun size={18} aria-hidden="true" />
                            ) : (
                                <Moon size={18} aria-hidden="true" />
                            )}
                        </IconButton>

                        {/* User menu */}
                        {user && (
                            <>
                                <IconButton
                                    onClick={handleUserMenuClick}
                                    size="small"
                                    sx={{
                                        ml: 1,
                                    }}
                                    aria-label={`User menu for ${user.username}`}
                                    aria-haspopup="menu"
                                    aria-expanded={userMenuOpen}
                                >
                                    <Avatar
                                        sx={{
                                            width: 32,
                                            height: 32,
                                            fontSize: "0.85rem",
                                            backgroundColor: muiTheme.palette.primary.main,
                                        }}
                                    >
                                        {user.username.charAt(0).toUpperCase()}
                                    </Avatar>
                                </IconButton>
                                <MuiMenu
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
                                >
                                    <Box sx={{ px: 2, py: 1 }}>
                                        <Typography variant="caption" color="textSecondary">
                                            Signed in as
                                        </Typography>
                                        <Typography variant="body2" sx={{ fontWeight: 600 }}>
                                            {user.username}
                                        </Typography>
                                    </Box>
                                    <Divider />
                                    <NavMenuItem
                                        to="/profile"
                                        icon="person"
                                        label="Profile"
                                        active={isPathActive("/profile")}
                                    />
                                    {((isSuperAdmin && isSuperAdmin()) || (hasAnyRole && hasAnyRole(["USER_MANAGER"]))) && (
                                        <NavMenuItem
                                            to="/admin/activity-log"
                                            icon="journal-text"
                                            label="Activity Log"
                                            active={isPathActive("/admin/activity-log")}
                                        />
                                    )}
                                    {(isSuperAdmin && isSuperAdmin()) && (
                                        <NavMenuItem
                                            to="/settings"
                                            icon="shield-lock"
                                            label="Users & Roles"
                                            active={isPathActive("/settings")}
                                        />
                                    )}
                                    <Divider />
                                    <MenuItem
                                        onClick={() => {
                                            logout();
                                            handleUserMenuClose();
                                        }}
                                        sx={{
                                            color: muiTheme.palette.error.main,
                                        }}
                                    >
                                        <ListItemIcon sx={{ minWidth: 32 }}>
                                            <Icon name="box-arrow-right" className="size-4" aria-hidden="true" />
                                        </ListItemIcon>
                                        <Typography variant="body2">Sign out</Typography>
                                    </MenuItem>
                                </MuiMenu>
                            </>
                        )}

                        {/* Mobile menu button */}
                        <IconButton
                            ref={mobileTriggerRef}
                            onClick={() => setMobileOpen(open => !open)}
                            aria-label={mobileOpen ? "Close navigation menu" : "Open navigation menu"}
                            aria-expanded={mobileOpen}
                            aria-controls="mobile-navigation-drawer"
                            data-testid="mobile-nav-toggle"
                            size="small"
                            sx={{
                                display: { xs: "flex", md: "none" },
                            }}
                        >
                            <Menu size={20} aria-hidden="true" />
                        </IconButton>
                    </Stack>
                </Toolbar>
            </AppBar>

            {/* Mobile Navigation Drawer */}
            <Drawer
                anchor="left"
                open={mobileOpen}
                onClose={closeMobileNav}
                id="mobile-navigation-drawer"
                data-testid="mobile-nav-drawer"
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
                    aria-label="Main navigation"
                    sx={{
                        display: "flex",
                        flexDirection: "column",
                        height: "100%",
                    }}
                >
                    {/* Header */}
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
                        <IconButton onClick={closeMobileNav} size="small">
                            <X size={20} aria-hidden="true" />
                        </IconButton>
                    </Box>

                    {/* Navigation */}
                    <Box sx={{ flex: 1, overflowY: "auto", py: 1 }}>
                        <List>
                            <ListItem component={RouterLink} to="/dashboard" onClick={closeMobileNav} selected={isDashActive} sx={{ cursor: "pointer" }}>
                                <ListItemIcon>
                                    <Gauge size={18} aria-hidden="true" />
                                </ListItemIcon>
                                <ListItemText primary="Dashboard" />
                            </ListItem>
                        </List>

                        {visibleGroups.map(group => (
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
                                    {group.items.map(item => (
                                        <ListItem
                                            key={item.path}
                                            component={RouterLink}
                                            to={item.path}
                                            onClick={closeMobileNav}
                                            selected={isPathActive(item.path)}
                                            sx={{
                                                pl: 4,
                                                cursor: "pointer",
                                            }}
                                        >
                                            <ListItemIcon sx={{ minWidth: 32 }}>
                                                <Icon name={item.icon} className="size-4" aria-hidden="true" />
                                            </ListItemIcon>
                                            <ListItemText primary={item.label} />
                                        </ListItem>
                                    ))}
                                </List>
                            </Box>
                        ))}

                        {hasAnyRole(REPORT_ROLES) && (
                            <Box>
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
                                    Reports
                                </Typography>
                                <List disablePadding>
                                    {reportEntities.map(report => (
                                        <ListItem
                                            key={report.path}
                                            component={RouterLink}
                                            to={report.path}
                                            onClick={closeMobileNav}
                                            selected={isPathActive(report.path)}
                                            sx={{
                                                pl: 4,
                                                cursor: "pointer",
                                            }}
                                        >
                                            <ListItemIcon sx={{ minWidth: 32 }}>
                                                <Icon name={report.icon} className="size-4" aria-hidden="true" />
                                            </ListItemIcon>
                                            <ListItemText primary={report.label} />
                                        </ListItem>
                                    ))}
                                </List>
                            </Box>
                        )}

                        <Box>
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
                                Masters
                            </Typography>
                            <List disablePadding>
                                {masterEntities.filter(master => !master.deprecated).map(master => (
                                    <ListItem
                                        key={master.path}
                                        component={RouterLink}
                                        to={master.path}
                                        onClick={closeMobileNav}
                                        selected={isPathActive(master.path)}
                                        sx={{
                                            pl: 4,
                                            cursor: "pointer",
                                        }}
                                    >
                                        <ListItemIcon sx={{ minWidth: 32 }}>
                                            <Icon name={master.icon} className="size-4" aria-hidden="true" />
                                        </ListItemIcon>
                                        <ListItemText primary={master.label} />
                                    </ListItem>
                                ))}
                            </List>
                        </Box>
                    </Box>

                    {/* Footer */}
                    <Box
                        sx={{
                            p: 1.5,
                            borderTop: `1px solid ${muiTheme.palette.divider}`,
                        }}
                    >
                        <Button
                            fullWidth
                            startIcon={<Search size={16} aria-hidden="true" />}
                            onClick={() => {
                                closeMobileNav();
                                openCmd();
                            }}
                            sx={{
                                mb: 1,
                                justifyContent: "flex-start",
                            }}
                        >
                            Search
                        </Button>
                        <Button
                            fullWidth
                            component={RouterLink}
                            to="/profile"
                            onClick={closeMobileNav}
                            startIcon={<Icon name="person" className="size-4" aria-hidden="true" />}
                            sx={{
                                mb: 1,
                                justifyContent: "flex-start",
                            }}
                        >
                            Profile
                        </Button>
                        <Button
                            fullWidth
                            startIcon={theme === "dark" ? <Sun size={16} aria-hidden="true" /> : <Moon size={16} aria-hidden="true" />}
                            onClick={toggleTheme}
                            sx={{
                                mb: 1,
                                justifyContent: "flex-start",
                            }}
                        >
                            {theme === "dark" ? "Light mode" : "Dark mode"}
                        </Button>
                        <Button
                            fullWidth
                            onClick={() => logout()}
                            color="error"
                            startIcon={<Icon name="box-arrow-right" className="size-4" aria-hidden="true" />}
                            sx={{
                                justifyContent: "flex-start",
                            }}
                        >
                            Sign out
                        </Button>
                    </Box>
                </Box>
            </Drawer>

            {cmdOpen && (
                <Suspense fallback={null}>
                    <CommandPalette open={cmdOpen} onClose={closeCmd} />
                </Suspense>
            )}
        </>
    );
}
