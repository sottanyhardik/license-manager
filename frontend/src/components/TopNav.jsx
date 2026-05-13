import { useContext, useEffect, useRef, useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { AuthContext } from "../context/AuthContext";
import { reportEntities, masterEntities } from "../routes/config";

// Static nav groups with per-item role requirements.
const NAV_GROUPS = [
    {
        label: "Licenses",
        icon: "file-earmark-text",
        items: [
            { path: "/licenses",           label: "Licenses",           icon: "file-earmark-text", roles: ["LICENSE_MANAGER", "LICENSE_VIEWER"] },
            { path: "/incentive-licenses", label: "Incentive Licenses", icon: "award",              roles: ["INCENTIVE_LICENSE_MANAGER", "INCENTIVE_LICENSE_VIEWER"] },
            { path: "/license-ledger",     label: "License Ledger",     icon: "journal-text",       roles: ["LICENSE_MANAGER", "TRADE_MANAGER", "TRADE_VIEWER", "LEDGER_MANAGER"] },
            { path: "/ledger-upload",      label: "Ledger Upload",      icon: "cloud-upload",       roles: ["LICENSE_MANAGER", "LEDGER_MANAGER"] },
            { path: "/ledger-csv-upload",  label: "Ledger CSV Upload",  icon: "filetype-csv",       roles: ["LICENSE_MANAGER", "LEDGER_MANAGER"] },
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

// ── Styling helpers ────────────────────────────────────────────────────────
const triggerBase = {
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    height: 36,
    padding: "0 12px",
    borderRadius: 8,
    fontSize: "0.875rem",
    fontWeight: 500,
    color: "var(--text-secondary)",
    background: "transparent",
    border: "none",
    textDecoration: "none",
    cursor: "pointer",
    transition: "background-color 150ms ease, color 150ms ease",
    whiteSpace: "nowrap",
};
const triggerActive = {
    ...triggerBase,
    color: "var(--primary-color)",
    background: "var(--indigo-50)",
};
const menuPanel = {
    position: "absolute",
    top: "100%",
    minWidth: 220,
    background: "var(--surface-raised)",
    border: "1px solid var(--border-subtle)",
    borderRadius: 12,
    padding: 6,
    boxShadow: "var(--elevation-3)",
    zIndex: 1031,
    display: "flex",
    flexDirection: "column",
    gap: 2,
    listStyle: "none",
    margin: 0,
};
const itemBase = {
    display: "flex",
    alignItems: "center",
    gap: 10,
    padding: "8px 10px",
    borderRadius: 8,
    fontSize: "0.875rem",
    color: "var(--text-primary)",
    textDecoration: "none",
    cursor: "pointer",
    border: "none",
    background: "transparent",
    width: "100%",
    textAlign: "left",
};


// ── A single hover-or-click menu ──────────────────────────────────────────
function NavMenu({ icon, label, items, isActive, end = false }) {
    const [open, setOpen] = useState(false);
    const wrapperRef = useRef(null);
    const closeTimerRef = useRef(null);

    // Close when clicking outside or pressing Escape
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
                style={isActive ? triggerActive : triggerBase}
                onClick={() => setOpen(v => !v)}
                aria-expanded={open}
                aria-haspopup="menu"
            >
                <i className={`bi bi-${icon}`} aria-hidden="true" style={{ fontSize: "0.95rem" }}></i>
                {label}
                <i className="bi bi-chevron-down" aria-hidden="true" style={{ fontSize: "0.65rem", marginLeft: 2, opacity: 0.6 }}></i>
            </button>

            {open && (
                <ul
                    role="menu"
                    style={{
                        ...menuPanel,
                        ...(end ? { right: 0, left: "auto" } : { left: 0, right: "auto" }),
                    }}
                >
                    {/* Invisible bridge so cursor can move from trigger to menu */}
                    <li aria-hidden="true" style={{ position: "absolute", top: -8, left: 0, right: 0, height: 8 }}></li>
                    {items}
                </ul>
            )}
        </div>
    );
}


function MenuItem({ to, icon, label, active, onClick, danger = false }) {
    const [hover, setHover] = useState(false);
    const style = {
        ...itemBase,
        color: danger
            ? "var(--danger-color)"
            : active
                ? "var(--primary-deeper)"
                : "var(--text-primary)",
        background: hover
            ? (active ? "var(--indigo-50)" : "var(--surface-sunken)")
            : (active ? "var(--indigo-50)" : "transparent"),
    };
    const inner = (
        <>
            {icon && (
                <i
                    className={`bi bi-${icon}`}
                    style={{ color: danger ? "var(--danger-color)" : "var(--primary-color)", fontSize: "0.9rem", width: 16, textAlign: "center" }}
                ></i>
            )}
            <span style={{ flex: 1 }}>{label}</span>
        </>
    );
    if (onClick) {
        return (
            <li role="none">
                <button
                    type="button"
                    role="menuitem"
                    style={style}
                    onClick={onClick}
                    onMouseEnter={() => setHover(true)}
                    onMouseLeave={() => setHover(false)}
                >
                    {inner}
                </button>
            </li>
        );
    }
    return (
        <li role="none">
            <Link
                role="menuitem"
                to={to}
                style={style}
                onMouseEnter={() => setHover(true)}
                onMouseLeave={() => setHover(false)}
            >
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

    return (
        <nav
            className="top-nav"
            style={{
                background: "rgba(255, 255, 255, 0.82)",
                backdropFilter: "saturate(180%) blur(16px)",
                WebkitBackdropFilter: "saturate(180%) blur(16px)",
                borderBottom: "1px solid var(--border-subtle)",
                padding: "0 clamp(1rem, 4vw, 2rem)",
                height: 56,
                display: "flex",
                alignItems: "center",
                position: "sticky",
                top: 0,
                zIndex: 1030,
            }}
        >
            {/* Brand */}
            <Link
                to="/"
                style={{
                    display: "inline-flex",
                    alignItems: "center",
                    gap: 10,
                    textDecoration: "none",
                    marginRight: 24,
                    flexShrink: 0,
                    color: "var(--text-primary)",
                }}
            >
                <span
                    aria-hidden="true"
                    style={{
                        width: 30, height: 30, borderRadius: 8,
                        background: "var(--primary-gradient)",
                        display: "inline-flex", alignItems: "center", justifyContent: "center",
                        color: "#fff",
                        boxShadow: "var(--elevation-1)",
                    }}
                >
                    <i className="bi bi-shield-check" style={{ fontSize: "0.95rem" }}></i>
                </span>
                <span className="nav-brand-text" style={{ fontWeight: 600, fontSize: "0.95rem", letterSpacing: "-0.01em" }}>
                    License Manager
                </span>
            </Link>

            {/* Nav items */}
            <div className="nav-items-scroller" style={{ display: "flex", alignItems: "center", gap: 4, flex: 1, minWidth: 0 }}>
                {/* Dashboard */}
                {(() => {
                    const active = isPathActive("/dashboard");
                    return (
                        <Link to="/dashboard" style={active ? triggerActive : triggerBase}>
                            <i className="bi bi-speedometer2" aria-hidden="true" style={{ fontSize: "0.95rem" }}></i>
                            Dashboard
                        </Link>
                    );
                })()}

                {/* Grouped */}
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

                {/* Reports */}
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

                {/* Masters */}
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
                    label={(
                        <span className="user-name-label" style={{ paddingRight: 2 }}>
                            {user.username}
                        </span>
                    )}
                    isActive={false}
                    end
                    items={[
                        <li key="header" role="none" style={{ padding: "8px 10px 6px" }}>
                            <div style={{ fontSize: "0.7rem", color: "var(--text-tertiary)", fontWeight: 500, textTransform: "uppercase", letterSpacing: "0.06em" }}>Signed in as</div>
                            <div style={{ fontSize: "0.875rem", fontWeight: 600, color: "var(--text-primary)" }}>{user.username}</div>
                        </li>,
                        <li key="div1" role="separator" style={{ borderTop: "1px solid var(--border-subtle)", margin: "4px 0" }}></li>,
                        <MenuItem key="profile" to="/profile" icon="person" label="Profile" />,
                        ((isSuperAdmin && isSuperAdmin()) || (hasAnyRole && hasAnyRole(["USER_MANAGER"])))
                            ? <MenuItem key="activity" to="/admin/activity-log" icon="journal-text" label="Activity Log" />
                            : null,
                        (isSuperAdmin && isSuperAdmin())
                            ? <MenuItem key="settings" to="/settings" icon="shield-lock" label="Users & Roles" />
                            : null,
                        <li key="div2" role="separator" style={{ borderTop: "1px solid var(--border-subtle)", margin: "4px 0" }}></li>,
                        <MenuItem key="logout" icon="box-arrow-right" label="Sign out" danger onClick={logout} />,
                    ].filter(Boolean)}
                />
            )}
        </nav>
    );
}
