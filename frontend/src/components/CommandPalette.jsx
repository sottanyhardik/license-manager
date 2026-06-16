import { useCallback, useContext, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AuthContext } from "../context/AuthContext";
import { masterEntities, reportEntities } from "../routes/config";

const BASE_COMMANDS = [
    { id: "dashboard",      label: "Dashboard",          icon: "speedometer2",          path: "/dashboard",        group: "Navigation" },
    { id: "licenses",       label: "Licenses",           icon: "file-earmark-text",     path: "/licenses",         group: "Navigation" },
    { id: "allotments",     label: "Allotments",         icon: "box-seam",              path: "/allotments",       group: "Navigation" },
    { id: "boe",            label: "Bill of Entries",    icon: "receipt",               path: "/bill-of-entries",  group: "Navigation" },
    { id: "trades",         label: "Trade In & Out",     icon: "arrow-left-right",      path: "/trades",           group: "Navigation" },
    { id: "ledger",         label: "License Ledger",     icon: "journal-text",          path: "/license-ledger",   group: "Navigation" },
    { id: "new-boe",        label: "New Bill of Entry",  icon: "plus-circle",           path: "/bill-of-entries/create", group: "Quick Create" },
    { id: "new-allotment",  label: "New Allotment",      icon: "plus-circle",           path: "/allotments/create",      group: "Quick Create" },
    { id: "new-license",    label: "New License",        icon: "plus-circle",           path: "/licenses/create",        group: "Quick Create" },
    { id: "profile",        label: "Profile",            icon: "person",                path: "/profile",          group: "Account" },
];

function buildCommands() {
    const cmds = [...BASE_COMMANDS];
    reportEntities.forEach(r => {
        cmds.push({ id: "report-" + r.path, label: r.label, icon: r.icon || "bar-chart", path: r.path, group: "Reports" });
    });
    masterEntities.forEach(m => {
        cmds.push({ id: "master-" + m.path, label: m.label, icon: m.icon || "database", path: m.path, group: "Masters" });
    });
    return cmds;
}

const ALL_COMMANDS = buildCommands();

export default function CommandPalette({ open, onClose }) {
    const navigate = useNavigate();
    const { isSuperAdmin, canManageUsers } = useContext(AuthContext);
    const [query, setQuery] = useState("");
    const [activeIdx, setActiveIdx] = useState(0);
    const inputRef = useRef(null);

    const commands = (() => {
        const base = [...ALL_COMMANDS];
        if (isSuperAdmin && isSuperAdmin()) {
            base.push({ id: "users",    label: "Users & Roles",  icon: "shield-lock", path: "/settings",             group: "Admin" });
            base.push({ id: "activity", label: "Activity Log",   icon: "journal-text", path: "/admin/activity-log",  group: "Admin" });
        } else if (canManageUsers && canManageUsers()) {
            base.push({ id: "users-list", label: "User Management", icon: "people", path: "/admin/users", group: "Admin" });
        }
        return base;
    })();

    const filtered = query.trim()
        ? commands.filter(c => c.label.toLowerCase().includes(query.toLowerCase()))
        : commands;

    const groups = [...new Set(filtered.map(c => c.group))];

    useEffect(() => {
        if (open) {
            setQuery("");
            setActiveIdx(0);
            setTimeout(() => inputRef.current?.focus(), 50);
        }
    }, [open]);

    useEffect(() => { setActiveIdx(0); }, [query]);

    const execute = useCallback((path) => {
        navigate(path);
        onClose();
    }, [navigate, onClose]);

    const handleKey = (e) => {
        if (e.key === "ArrowDown") {
            e.preventDefault();
            setActiveIdx(i => Math.min(i + 1, filtered.length - 1));
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setActiveIdx(i => Math.max(i - 1, 0));
        } else if (e.key === "Enter") {
            e.preventDefault();
            if (filtered[activeIdx]) execute(filtered[activeIdx].path);
        } else if (e.key === "Escape") {
            onClose();
        }
    };

    if (!open) return null;

    let globalIdx = 0;

    return (
        <div
            className="cmd-backdrop"
            role="dialog"
            aria-modal="true"
            aria-label="Command palette"
            onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
        >
            <div className="cmd-panel" onKeyDown={handleKey}>
                {/* Search row */}
                <div className="cmd-search-row">
                    <i className="bi bi-search cmd-search-icon" aria-hidden="true" />
                    <input
                        ref={inputRef}
                        className="cmd-input"
                        placeholder="Search pages, reports, masters…"
                        value={query}
                        onChange={e => setQuery(e.target.value)}
                        aria-autocomplete="list"
                        aria-expanded={filtered.length > 0}
                        role="combobox"
                    />
                    <kbd className="cmd-hint">Esc</kbd>
                </div>

                {/* Results */}
                <div
                    className="cmd-results"
                    role="listbox"
                    id="cmd-results"
                >
                    {filtered.length === 0 ? (
                        <div className="cmd-empty">No results for &ldquo;{query}&rdquo;</div>
                    ) : (
                        groups.map(group => {
                            const groupItems = filtered.filter(c => c.group === group);
                            return (
                                <div key={group}>
                                    <div className="cmd-group-label">{group}</div>
                                    {groupItems.map(cmd => {
                                        const idx = globalIdx++;
                                        const isActive = idx === activeIdx;
                                        return (
                                            <div
                                                key={cmd.id}
                                                className={`cmd-item${isActive ? " is-active" : ""}`}
                                                role="option"
                                                aria-selected={isActive}
                                                onClick={() => execute(cmd.path)}
                                                onMouseEnter={() => setActiveIdx(idx)}
                                            >
                                                <span className="cmd-item-icon">
                                                    <i className={`bi bi-${cmd.icon}`} aria-hidden="true" />
                                                </span>
                                                <span className="cmd-item-label">{cmd.label}</span>
                                            </div>
                                        );
                                    })}
                                </div>
                            );
                        })
                    )}
                </div>

                {/* Footer hints */}
                <div className="cmd-footer">
                    <div className="cmd-footer-hint">
                        <kbd className="cmd-key">↑↓</kbd> navigate
                    </div>
                    <div className="cmd-footer-hint">
                        <kbd className="cmd-key">↵</kbd> open
                    </div>
                    <div className="cmd-footer-hint">
                        <kbd className="cmd-key">Esc</kbd> close
                    </div>
                </div>
            </div>
        </div>
    );
}
