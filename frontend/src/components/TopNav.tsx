import React, { lazy, Suspense, useCallback, useContext, useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { AuthContext } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { reportEntities, masterEntities } from "../routes/config";
import { REPORT_ROLES } from "../routes/authorizationRoles";
import { ChevronDown, Gauge, Menu, Search, ShieldCheck, X } from "lucide-react";
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


function NavMenu({ icon, label, items, isActive, end = false }) {
    const [open, setOpen] = useState(false);
    const wrapperRef = useRef(null);
    const closeTimerRef = useRef(null);

    useEffect(() => {
        if (!open) return;
        const onDown = (e) => { if (!wrapperRef.current?.contains(e.target)) setOpen(false); };
        const onKey = (e) => { if (e.key === "Escape") setOpen(false); };
        document.addEventListener("mousedown", onDown);
        document.addEventListener("keydown", onKey);
        return () => {
            document.removeEventListener("mousedown", onDown);
            document.removeEventListener("keydown", onKey);
        };
    }, [open]);

    const scheduleClose = () => {
        clearTimeout(closeTimerRef.current);
        closeTimerRef.current = setTimeout(() => setOpen(false), 150);
    };
    const cancelClose = () => clearTimeout(closeTimerRef.current);

    return (
        <div
            ref={wrapperRef}
            style={{ position: "relative" }}
            onMouseEnter={() => { cancelClose(); setOpen(true); }}
            onMouseLeave={scheduleClose}
        >
            <button
                type="button"
                className={`tb-nav-trigger${isActive ? " is-active" : ""}`}
                onClick={() => setOpen(v => !v)}
                aria-expanded={open}
                aria-haspopup="menu"
            >
                <Icon name={icon} className="size-4" />
                {label}
                <ChevronDown
                    className="size-3.5 transition-transform duration-200"
                    style={{ transform: open ? "rotate(180deg)" : "rotate(0deg)", opacity: 0.6 }}
                    aria-hidden="true"
                />
            </button>

            {open && (
                <ul role="menu" className={`tb-nav-menu${end ? " is-end" : ""}`}>
                    {/* Invisible bridge prevents gap between trigger and menu closing on mouse movement */}
                    <li aria-hidden="true" style={{ position: "absolute", top: -8, left: 0, right: 0, height: 8 }} />
                    {items}
                </ul>
            )}
        </div>
    );
}


function MenuItem({ to, icon, label, active, onClick, danger = false }: { to?: string; icon?: string; label?: React.ReactNode; active?: boolean; onClick?: ((...args: unknown[]) => unknown); danger?: boolean }) {
    const classes = [
        "tb-nav-menu-item",
        active ? "is-active" : "",
        danger ? "is-danger" : "",
    ].filter(Boolean).join(" ");
    const inner = (
        <>
            {icon && <Icon name={icon} className="size-4" />}
            <span style={{ flex: 1 }}>{label}</span>
        </>
    );
    if (onClick) {
        return (
            <li role="none">
                <button type="button" role="menuitem" className={classes} onClick={onClick}>{inner}</button>
            </li>
        );
    }
    return (
        <li role="none">
            <Link role="menuitem" to={to} className={classes}>{inner}</Link>
        </li>
    );
}


export default function TopNav() {
    const { user, logout, isSuperAdmin, hasAnyRole } = useContext(AuthContext);
    const { theme, toggleTheme } = useTheme();
    const location = useLocation();
    const [cmdOpen, setCmdOpen] = useState(false);
    const [mobileOpen, setMobileOpen] = useState(false);
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
    const visibleGroups = NAV_GROUPS.map(group => ({
        ...group,
        items: group.items.filter(item => !item.roles || hasAnyRole(item.roles)),
    })).filter(group => group.items.length > 0);

    useEffect(() => {
        const handler = (e) => {
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
            <nav className="tb-nav top-nav top-nav--premium" aria-label="Main navigation">
                {/* Brand */}
                <Link to="/" className="tb-nav-brand">
                    <span className="tb-nav-brand-mark" aria-hidden="true">
                        <ShieldCheck className="size-4" aria-hidden="true" />
                    </span>
                    <span className="tb-nav-brand-text">License Manager</span>
                </Link>

                {/* Nav items */}
                <div className="tb-nav-scroller nav-items-scroller" aria-label="Primary sections">
                    <Link to="/dashboard" className={`tb-nav-trigger${isDashActive ? " is-active" : ""}`}>
                        <Gauge className="size-4" aria-hidden="true" />
                        Dashboard
                    </Link>

                    {visibleGroups.map(group => {
                        return (
                            <NavMenu
                                key={group.label}
                                icon={group.icon}
                                label={group.label}
                                isActive={isGroupActive(group.items)}
                                items={group.items.map(item => (
                                    <MenuItem
                                        key={item.path}
                                        to={item.path}
                                        icon={item.icon}
                                        label={item.label}
                                        active={isPathActive(item.path)}
                                    />
                                ))}
                            />
                        );
                    })}

                    {hasAnyRole(REPORT_ROLES) && (
                        <NavMenu
                            icon="bar-chart-line"
                            label="Reports"
                            isActive={isGroupActive(reportEntities)}
                            items={reportEntities.map(r => (
                                <MenuItem
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
                            <MenuItem
                                key={m.path}
                                to={m.path}
                                icon={m.icon}
                                label={m.label}
                                active={isPathActive(m.path)}
                            />
                        ))}
                    />
                </div>

                {/* Right-side controls */}
                <div className="tb-nav__utilities flex items-center gap-1 ml-2 shrink-0" aria-label="Session controls">
                    {/* Command palette search trigger — pill style on wider viewports */}
                    <button
                        type="button"
                        className="tb-nav-theme-toggle w-auto gap-1.5 px-2.5 text-xs text-muted-foreground/70"
                        onClick={openCmd}
                        aria-label="Search (⌘K)"
                        title="Search ⌘K"
                    >
                        <Search className="size-3.5" aria-hidden="true" />
                        <span className="hidden sm:inline text-[12px]">Search</span>
                        <kbd className="hidden rounded bg-muted/40 px-[5px] py-[1px] font-mono text-[10px] tracking-normal border border-border lg:inline-block">
                            ⌘K
                        </kbd>
                    </button>

                    {/* Dark mode toggle */}
                    <button
                        type="button"
                        className="tb-nav-theme-toggle"
                        onClick={toggleTheme}
                        aria-label={theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
                        title={theme === "dark" ? "Light mode" : "Dark mode"}
                    >
                        <Icon name={theme === "dark" ? "sun" : "moon"} className="size-4" />
                    </button>

                    <div className="tb-nav-sep" />

                    {/* User menu */}
                    {user && (
                        <NavMenu
                            icon="person-circle"
                            label={<span style={{ maxWidth: 120, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", display: "block" }}>{user.username}</span>}
                            isActive={false}
                            end
                            items={[
                                <li key="header" role="none" className="tb-nav-menu-header">
                                    <div className="pretitle">Signed in as</div>
                                    <div className="username">{user.username}</div>
                                </li>,
                                <li key="div1" role="separator" className="tb-nav-menu-divider" />,
                                <MenuItem key="profile" to="/profile" icon="person" label="Profile" active={isPathActive("/profile")} />,
                                ((isSuperAdmin && isSuperAdmin()) || (hasAnyRole && hasAnyRole(["USER_MANAGER"])))
                                    ? <MenuItem key="activity" to="/admin/activity-log" icon="journal-text" label="Activity Log" active={isPathActive("/admin/activity-log")} />
                                    : null,
                                (isSuperAdmin && isSuperAdmin())
                                    ? <MenuItem key="settings" to="/settings" icon="shield-lock" label="Users & Roles" active={isPathActive("/settings")} />
                                    : null,
                                <li key="div2" role="separator" className="tb-nav-menu-divider" />,
                                <MenuItem key="logout" icon="box-arrow-right" label="Sign out" danger onClick={logout} />,
                            ].filter(Boolean)}
                        />
                    )}
                    <button
                        ref={mobileTriggerRef}
                        type="button"
                        className="tb-nav-mobile-toggle"
                        aria-label={mobileOpen ? "Close navigation menu" : "Open navigation menu"}
                        aria-expanded={mobileOpen}
                        aria-controls="mobile-navigation-drawer"
                        onClick={() => setMobileOpen(open => !open)}
                        data-testid="mobile-nav-toggle"
                    >
                        <Menu className="size-5" aria-hidden="true" />
                    </button>
                </div>
            </nav>

            {mobileOpen && (
                <div className="tb-mobile-nav-layer" role="presentation">
                    <button type="button" className="tb-mobile-nav-backdrop" aria-label="Close navigation menu" onClick={closeMobileNav} />
                    <aside
                        id="mobile-navigation-drawer"
                        ref={mobileDrawerRef}
                        className="tb-mobile-nav-drawer"
                        role="dialog"
                        aria-modal="true"
                        aria-label="Main navigation"
                        data-testid="mobile-nav-drawer"
                    >
                        <div className="tb-mobile-nav-header">
                            <span className="tb-nav-brand-mark" aria-hidden="true"><ShieldCheck className="size-4" /></span>
                            <span className="tb-mobile-nav-title">License Manager</span>
                            <button type="button" className="tb-mobile-nav-close" onClick={closeMobileNav} aria-label="Close navigation menu"><X className="size-5" aria-hidden="true" /></button>
                        </div>
                        <div className="tb-mobile-nav-body">
                            <Link to="/dashboard" className={`tb-mobile-nav-link${isDashActive ? " is-active" : ""}`} onClick={closeMobileNav}><Gauge className="size-4" aria-hidden="true" /> Dashboard</Link>
                            {visibleGroups.map(group => (
                                <section className="tb-mobile-nav-group" key={group.label} aria-label={group.label}>
                                    <div className="tb-mobile-nav-group-label"><Icon name={group.icon} className="size-3.5" aria-hidden="true" />{group.label}</div>
                                    {group.items.map(item => (
                                        <Link key={item.path} to={item.path} className={`tb-mobile-nav-link${isPathActive(item.path) ? " is-active" : ""}`} onClick={closeMobileNav}><Icon name={item.icon} className="size-4" aria-hidden="true" />{item.label}</Link>
                                    ))}
                                </section>
                            ))}
                            {hasAnyRole(REPORT_ROLES) && (
                                <section className="tb-mobile-nav-group" aria-label="Reports">
                                    <div className="tb-mobile-nav-group-label"><Icon name="bar-chart-line" className="size-3.5" aria-hidden="true" />Reports</div>
                                    {reportEntities.map(report => <Link key={report.path} to={report.path} className={`tb-mobile-nav-link${isPathActive(report.path) ? " is-active" : ""}`} onClick={closeMobileNav}><Icon name={report.icon} className="size-4" aria-hidden="true" />{report.label}</Link>)}
                                </section>
                            )}
                            <section className="tb-mobile-nav-group" aria-label="Masters">
                                <div className="tb-mobile-nav-group-label"><Icon name="database" className="size-3.5" aria-hidden="true" />Masters</div>
                                {masterEntities.filter(master => !master.deprecated).map(master => <Link key={master.path} to={master.path} className={`tb-mobile-nav-link${isPathActive(master.path) ? " is-active" : ""}`} onClick={closeMobileNav}><Icon name={master.icon} className="size-4" aria-hidden="true" />{master.label}</Link>)}
                            </section>
                        </div>
                        <div className="tb-mobile-nav-footer">
                            <button type="button" className="tb-mobile-nav-utility" onClick={() => { closeMobileNav(); openCmd(); }}><Search className="size-4" aria-hidden="true" /> Search</button>
                            <Link to="/profile" className="tb-mobile-nav-utility" onClick={closeMobileNav}><Icon name="person" className="size-4" aria-hidden="true" /> Profile</Link>
                            <button type="button" className="tb-mobile-nav-utility" onClick={toggleTheme}><Icon name={theme === "dark" ? "sun" : "moon"} className="size-4" aria-hidden="true" />{theme === "dark" ? "Light mode" : "Dark mode"}</button>
                            <button type="button" className="tb-mobile-nav-utility is-danger" onClick={() => logout()}><Icon name="box-arrow-right" className="size-4" aria-hidden="true" /> Sign out</button>
                        </div>
                    </aside>
                </div>
            )}

            {cmdOpen && (
                <Suspense fallback={null}>
                    <CommandPalette open={cmdOpen} onClose={closeCmd} />
                </Suspense>
            )}
        </>
    );
}
