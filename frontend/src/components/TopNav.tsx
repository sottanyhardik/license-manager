import React, { useCallback, useContext, useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { AuthContext } from "../context/AuthContext";
import { useTheme } from "../context/ThemeContext";
import { reportEntities, masterEntities } from "../routes/config";
import { REPORT_ROLES } from "../routes/authorizationRoles";
import CommandPalette from "./CommandPalette";
import { ChevronDown, Gauge, Search, ShieldCheck } from "lucide-react";
import Icon from "@/components/Icon";

const NAV_GROUPS = [
    {
        label: "Licenses",
        icon: "file-earmark-text",
        items: [
            { path: "/licenses",           label: "Licenses",           icon: "file-earmark-text", roles: ["LICENSE_MANAGER", "LICENSE_VIEWER"] },
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
                <ChevronDown className="size-4" aria-hidden="true" />
            </button>

            {open && (
                <ul role="menu" className={`tb-nav-menu${end ? " is-end" : ""}`}>
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

    const isPathActive = (path) =>
        location.pathname === path || location.pathname.startsWith(path + "/");
    const isGroupActive = (items) => items.some(i => isPathActive(i.path));
    const isDashActive = isPathActive("/dashboard");

    const openCmd = useCallback(() => setCmdOpen(true), []);
    const closeCmd = useCallback(() => setCmdOpen(false), []);

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

    return (
        <>
            <nav className="tb-nav top-nav" aria-label="Main navigation">
                {/* Brand */}
                <Link to="/" className="tb-nav-brand">
                    <span className="tb-nav-brand-mark" aria-hidden="true">
                        <ShieldCheck className="size-4" aria-hidden="true" />
                    </span>
                    <span className="tb-nav-brand-text">License Manager</span>
                </Link>

                {/* Nav items */}
                <div className="tb-nav-scroller nav-items-scroller">
                    <Link to="/dashboard" className={`tb-nav-trigger${isDashActive ? " is-active" : ""}`}>
                        <Gauge className="size-4" aria-hidden="true" />
                        Dashboard
                    </Link>

                    {NAV_GROUPS.map(group => {
                        const visible = group.items.filter(item => !item.roles || hasAnyRole(item.roles));
                        if (visible.length === 0) return null;
                        return (
                            <NavMenu
                                key={group.label}
                                icon={group.icon}
                                label={group.label}
                                isActive={isGroupActive(visible)}
                                items={visible.map(item => (
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
                <div style={{ display: "flex", alignItems: "center", gap: 4, marginLeft: 8, flexShrink: 0 }}>
                    {/* Command palette search trigger */}
                    <button
                        type="button"
                        className="tb-nav-theme-toggle"
                        onClick={openCmd}
                        aria-label="Search (⌘K)"
                        title="Search  ⌘K"
                        style={{ width: "auto", paddingInline: 10, gap: 6, fontSize: 12, color: "var(--tb-text-tertiary)" }}
                    >
                        <Search className="size-4" aria-hidden="true" />
                        <span style={{ display: "none" }} className="d-sm-inline">
                            Search
                        </span>
                        <kbd
                            style={{
                                fontSize: 10,
                                background: "var(--tb-sunken)",
                                border: "1px solid var(--tb-border)",
                                borderRadius: 4,
                                padding: "1px 5px",
                                fontFamily: "var(--tb-font-mono)",
                                display: "none",
                            }}
                            className="d-lg-inline"
                        >
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
                </div>
            </nav>

            <CommandPalette open={cmdOpen} onClose={closeCmd} />
        </>
    );
}
