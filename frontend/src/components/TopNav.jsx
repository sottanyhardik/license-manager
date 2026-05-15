import { useContext, useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { AuthContext } from "../context/AuthContext";
import { reportEntities, masterEntities } from "../routes/config";

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
            { path: "/allotments",      label: "Allotments",     icon: "box-seam",        roles: ["ALLOTMENT_MANAGER", "ALLOTMENT_VIEWER"] },
            { path: "/bill-of-entries", label: "Bill of Entry",  icon: "receipt",         roles: ["BOE_MANAGER", "BOE_VIEWER", "TL_GENERATE", "ACCOUNT_ACCESS"] },
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
        const onDown = (e) => {
            if (!wrapperRef.current?.contains(e.target)) setOpen(false);
        };
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
        closeTimerRef.current = setTimeout(() => setOpen(false), 140);
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
                <i className={`bi bi-${icon}`} aria-hidden="true" />
                {label}
                <i className="bi bi-chevron-down" aria-hidden="true" />
            </button>

            {open && (
                <ul role="menu" className={`tb-nav-menu${end ? " is-end" : ""}`}>
                    {/* Invisible bridge so cursor can move from trigger to menu */}
                    <li aria-hidden="true" style={{ position: "absolute", top: -8, left: 0, right: 0, height: 8 }} />
                    {items}
                </ul>
            )}
        </div>
    );
}


function MenuItem({ to, icon, label, active, onClick, danger = false }) {
    const classes = [
        "tb-nav-menu-item",
        active ? "is-active" : "",
        danger ? "is-danger" : "",
    ].filter(Boolean).join(" ");
    const inner = (
        <>
            {icon && <i className={`bi bi-${icon}`} aria-hidden="true" />}
            <span style={{ flex: 1 }}>{label}</span>
        </>
    );
    if (onClick) {
        return (
            <li role="none">
                <button type="button" role="menuitem" className={classes} onClick={onClick}>
                    {inner}
                </button>
            </li>
        );
    }
    return (
        <li role="none">
            <Link role="menuitem" to={to} className={classes}>
                {inner}
            </Link>
        </li>
    );
}


export default function TopNav() {
    const { user, logout, isSuperAdmin, hasAnyRole } = useContext(AuthContext);
    const location = useLocation();

    const isPathActive = (path) =>
        location.pathname === path || location.pathname.startsWith(path + "/");
    const isGroupActive = (items) => items.some(i => isPathActive(i.path));
    const isDashActive = isPathActive("/dashboard");

    return (
        <nav className="tb-nav top-nav">
            {/* Brand */}
            <Link to="/" className="tb-nav-brand">
                <span className="tb-nav-brand-mark" aria-hidden="true">
                    <i className="bi bi-shield-check" style={{ fontSize: "0.95rem" }} />
                </span>
                <span className="tb-nav-brand-text">License Manager</span>
            </Link>

            {/* Nav items */}
            <div className="tb-nav-scroller nav-items-scroller">
                <Link to="/dashboard" className={`tb-nav-trigger${isDashActive ? " is-active" : ""}`}>
                    <i className="bi bi-speedometer2" aria-hidden="true" />
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

                {hasAnyRole(["REPORT_VIEWER", "LICENSE_MANAGER", "TRADE_MANAGER", "ALLOTMENT_MANAGER", "BOE_MANAGER", "INCENTIVE_LICENSE_MANAGER"]) && (
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

            {/* User menu */}
            {user && (
                <NavMenu
                    icon="person-circle"
                    label={<span className="user-name-label">{user.username}</span>}
                    isActive={false}
                    end
                    items={[
                        <li key="header" role="none" className="tb-nav-menu-header">
                            <div className="pretitle">Signed in as</div>
                            <div className="username">{user.username}</div>
                        </li>,
                        <li key="div1" role="separator" className="tb-nav-menu-divider" />,
                        <MenuItem key="profile" to="/profile" icon="person" label="Profile" />,
                        ((isSuperAdmin && isSuperAdmin()) || (hasAnyRole && hasAnyRole(["USER_MANAGER"])))
                            ? <MenuItem key="activity" to="/admin/activity-log" icon="journal-text" label="Activity Log" />
                            : null,
                        (isSuperAdmin && isSuperAdmin())
                            ? <MenuItem key="settings" to="/settings" icon="shield-lock" label="Users & Roles" />
                            : null,
                        <li key="div2" role="separator" className="tb-nav-menu-divider" />,
                        <MenuItem key="logout" icon="box-arrow-right" label="Sign out" danger onClick={logout} />,
                    ].filter(Boolean)}
                />
            )}
        </nav>
    );
}
