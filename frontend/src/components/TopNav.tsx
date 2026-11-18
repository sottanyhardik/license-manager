import { lazy, Suspense, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { AuthContext } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { USER_ADMIN_ROLES } from "../routes/authorizationRoles";
import { Gauge, Menu, Search, ShieldCheck, X } from "lucide-react";
import Icon from "@/components/Icon";
import { NavMenu, NavMenuHeader, NavMenuItem, NavMenuSection, NavMenuSeparator } from "./navigation/NavMenu";
import { DASHBOARD_PATH, groupItems, resolveActiveNavPath, visibleNavGroups } from "./navigation/navConfig";
import { siblingTrigger, useNavMenus } from "./navigation/useNavMenus";

// cmdk and its dialog primitives are only useful after the user opens global
// search.  Keeping them out of the navigation chunk materially reduces the
// authenticated first-paint payload without changing the command workflow.
const CommandPalette = lazy(() => import("./CommandPalette"));


export default function TopNav() {
    const { user, logout, isSuperAdmin, hasAnyRole } = useContext(AuthContext);
    const { theme, toggleTheme } = useTheme();
    const location = useLocation();
    const [cmdOpen, setCmdOpen] = useState(false);
    const [mobileOpen, setMobileOpen] = useState(false);
    const mobileDrawerRef = useRef<HTMLDivElement | null>(null);
    const mobileTriggerRef = useRef<HTMLButtonElement | null>(null);

    const menus = useNavMenus();
    const { close: closeMenus } = menus;

    // Account-menu destinations are not in the primary config; plain prefix match.
    const isPathActive = (path: string) =>
        location.pathname === path || location.pathname.startsWith(path + "/");

    const openCmd = useCallback(() => setCmdOpen(true), []);
    const closeCmd = useCallback(() => setCmdOpen(false), []);
    const closeMobileNav = useCallback(() => {
        setMobileOpen(false);
        window.requestAnimationFrame(() => mobileTriggerRef.current?.focus());
    }, []);
    const visibleGroups = useMemo(() => visibleNavGroups(hasAnyRole), [hasAnyRole]);
    const activePath = resolveActiveNavPath(location.pathname, visibleGroups);
    const isDashActive = activePath === DASHBOARD_PATH;
    const isGroupActive = (group: (typeof visibleGroups)[number]) =>
        groupItems(group).some(item => item.path === activePath);
    const canSeeActivityLog = Boolean((isSuperAdmin && isSuperAdmin()) || (hasAnyRole && hasAnyRole(USER_ADMIN_ROLES)));
    const canManageRoles = Boolean(isSuperAdmin && isSuperAdmin());

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

    // Only the mobile drawer closes on route change.  Desktop menus close on
    // item select / outside press / Escape instead: lazy routes commit inside a
    // transition, so a pathname effect fires late and would shut a menu the
    // user hovered open while the next page was still loading.
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

                {/* Primary sections — one shared open-state, so menus never overlap */}
                <div className="tb-nav-scroller nav-items-scroller" data-nav-bar="">
                    <Link
                        to={DASHBOARD_PATH}
                        className={`tb-nav-trigger${isDashActive ? " is-active" : ""}`}
                        aria-current={isDashActive ? "page" : undefined}
                        data-nav-trigger=""
                        onPointerEnter={(event) => { if (event.pointerType === "mouse") closeMenus(); }}
                        onKeyDown={(event) => {
                            if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
                            event.preventDefault();
                            siblingTrigger(event.currentTarget, event.key === "ArrowRight" ? 1 : -1)?.focus();
                        }}
                    >
                        <Gauge className="size-4" aria-hidden="true" />
                        <span className="tb-nav-trigger-label">Dashboard</span>
                    </Link>

                    {visibleGroups.map(group => {
                        const items = groupItems(group);
                        const columns = group.columns ?? 1;
                        const rows = group.sections.length > 1 ? 1 : Math.ceil(items.length / columns);
                        const renderSection = (section: (typeof group.sections)[number], index: number) => (
                            <NavMenuSection key={section.label ?? index} label={group.sections.length > 1 ? section.label : undefined}>
                                {section.items.map(item => (
                                    <NavMenuItem key={item.path} to={item.path} icon={item.icon} label={item.label} active={item.path === activePath} />
                                ))}
                            </NavMenuSection>
                        );
                        // Opt-in stacking: `sectionRows` sections per column, each column its own wrapper so
                        // short and long sections do not share row heights across columns.
                        const stacked = group.sectionRows && group.sections.length > 1
                            ? Array.from({ length: Math.ceil(group.sections.length / group.sectionRows) }, (_, c) =>
                                group.sections.slice(c * group.sectionRows!, (c + 1) * group.sectionRows!))
                            : null;
                        return (
                            <NavMenu
                                key={group.id}
                                id={group.id}
                                icon={group.icon}
                                label={group.label}
                                controller={menus}
                                isActive={isGroupActive(group)}
                                columns={stacked ? stacked.length : Math.min(columns, group.sections.length > 1 ? group.sections.length : items.length)}
                                rows={rows}
                            >
                                {stacked
                                    ? stacked.map((column, c) => (
                                        <div key={c} role="presentation" className="tb-nav-menu-column">
                                            {column.map((section, i) => renderSection(section, c * group.sectionRows! + i))}
                                        </div>
                                    ))
                                    : group.sections.map(renderSection)}
                            </NavMenu>
                        );
                    })}
                </div>

                {/* Right-side controls */}
                <div className="tb-nav__utilities flex items-center gap-1 ml-2 shrink-0" aria-label="Session controls">
                    {/* Command palette search trigger — pill style on wider viewports */}
                    <button
                        type="button"
                        className="tb-nav-theme-toggle w-auto gap-2 px-3 text-xs text-muted-foreground/70 transition-colors hover:bg-muted/50 rounded-lg"
                        onClick={openCmd}
                        aria-label="Search (⌘K)"
                        title="Search ⌘K"
                    >
                        <Search className="size-4" aria-hidden="true" />
                        <span className="hidden xl:inline text-xs">Search</span>
                        <kbd className="hidden rounded bg-muted/40 px-1.5 py-0.5 font-mono text-[10px] tracking-normal border border-border xl:inline-block">
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
                        <div className="tb-nav-account" data-nav-bar="">
                            <NavMenu
                                id="account"
                                icon="person-circle"
                                label={user.username}
                                ariaLabel={`Account menu for ${user.username}`}
                                controller={menus}
                                align="end"
                            >
                                <NavMenuHeader>
                                    <div className="pretitle">Signed in as</div>
                                    <div className="username">{user.username}</div>
                                </NavMenuHeader>
                                <NavMenuSeparator />
                                <NavMenuItem to="/profile" icon="person" label="Profile" active={isPathActive("/profile")} />
                                {canSeeActivityLog && (
                                    <NavMenuItem to="/admin/activity-log" icon="journal-text" label="Activity Log" active={isPathActive("/admin/activity-log")} />
                                )}
                                {canManageRoles && (
                                    <NavMenuItem to="/settings" icon="shield-lock" label="Users & Roles" active={isPathActive("/settings")} />
                                )}
                                <NavMenuSeparator />
                                <NavMenuItem icon="box-arrow-right" label="Sign out" danger onSelect={logout} />
                            </NavMenu>
                        </div>
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
                            <Link to={DASHBOARD_PATH} className={`tb-mobile-nav-link${isDashActive ? " is-active" : ""}`} aria-current={isDashActive ? "page" : undefined} onClick={closeMobileNav}><Gauge className="size-4" aria-hidden="true" /> Dashboard</Link>
                            {visibleGroups.map(group => (
                                <section className="tb-mobile-nav-group" key={group.id} aria-label={group.label}>
                                    <div className="tb-mobile-nav-group-label"><Icon name={group.icon} className="size-3.5" aria-hidden="true" />{group.label}</div>
                                    {groupItems(group).map(item => (
                                        <Link
                                            key={item.path}
                                            to={item.path}
                                            className={`tb-mobile-nav-link${item.path === activePath ? " is-active" : ""}`}
                                            aria-current={item.path === activePath ? "page" : undefined}
                                            onClick={closeMobileNav}
                                        >
                                            <Icon name={item.icon} className="size-4" aria-hidden="true" />{item.label}
                                        </Link>
                                    ))}
                                </section>
                            ))}
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
