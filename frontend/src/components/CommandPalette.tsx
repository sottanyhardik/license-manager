/**
 * CommandPalette — powered by cmdk (v1).
 *
 * Before: 170-line custom implementation with manual keyboard navigation,
 *         manual search filtering, manual focus management, manual ARIA.
 * After: cmdk handles all of that. We keep:
 *   - role-based command list building (domain logic)
 *   - existing CSS class names for visual styling
 *   - onClose / open API contract (unchanged)
 */

import { useCallback, useContext } from "react";
import { useNavigate } from "react-router-dom";
import { Command } from "cmdk";
import { AuthContext } from "../context/AuthContext";
import { masterEntities, reportEntities } from "../routes/config";
import { REPORT_ROLES } from "../routes/authorizationRoles";
import { Search } from "lucide-react";
import Icon from "@/components/Icon";
import { ACCOUNTING_ROLES, ALLOTMENT_ROLES, BOE_LIST_ROLES, LEDGER_READ_ROLES, LICENSE_ROLES, ROLES, TRADE_ROLES } from "../routes/authorizationRoles";

// ── Command registry ──────────────────────────────────────────────────────────

interface CommandDef {
    id: string;
    label: string;
    icon: string;
    path: string;
    group: string;
    roles?: string[];
}

const BASE_COMMANDS: CommandDef[] = [
    { id: "dashboard",      label: "Dashboard",          icon: "speedometer2",          path: "/dashboard",              group: "Navigation" },
    { id: "licenses",       label: "Licenses",           icon: "file-earmark-text",     path: "/licenses",               group: "Navigation", roles: LICENSE_ROLES },
    { id: "allotments",     label: "Allotments",         icon: "box-seam",              path: "/allotments",             group: "Navigation", roles: ALLOTMENT_ROLES },
    { id: "boe",            label: "Bill of Entries",    icon: "receipt",               path: "/bill-of-entries",        group: "Navigation", roles: BOE_LIST_ROLES },
    { id: "trades",         label: "Trade In & Out",     icon: "arrow-left-right",      path: "/trades",                 group: "Navigation", roles: TRADE_ROLES },
    { id: "ledger",         label: "License Ledger",     icon: "journal-text",          path: "/license-ledger",         group: "Navigation", roles: LEDGER_READ_ROLES },
    { id: "accounting",     label: "Accounting Dashboard", icon: "speedometer2",        path: "/accounting/dashboard",                group: "Accounting", roles: ACCOUNTING_ROLES },
    { id: "acct-accounts",  label: "Chart of Accounts",  icon: "list-ul",               path: "/accounting/masters/accounts",         group: "Accounting", roles: ACCOUNTING_ROLES },
    { id: "acct-vouchers",  label: "Vouchers",           icon: "journal-text",          path: "/accounting/vouchers",                 group: "Accounting", roles: ACCOUNTING_ROLES },
    { id: "acct-gl",        label: "General Ledger",     icon: "journal-text",          path: "/accounting/reports/general-ledger",   group: "Accounting", roles: ACCOUNTING_ROLES },
    { id: "acct-party",     label: "Party Ledger",       icon: "person",                path: "/accounting/party-ledger",             group: "Accounting", roles: ACCOUNTING_ROLES },
    { id: "acct-banking",   label: "Banking",            icon: "database",              path: "/accounting/banking",                  group: "Accounting", roles: ACCOUNTING_ROLES },
    { id: "acct-brs",       label: "Bank Reconciliation", icon: "check2-square",        path: "/accounting/banking/reconciliation",   group: "Accounting", roles: ACCOUNTING_ROLES },
    { id: "acct-tb",        label: "Trial Balance",      icon: "list-ul",               path: "/accounting/reports/trial-balance",    group: "Accounting", roles: ACCOUNTING_ROLES },
    { id: "acct-pl",        label: "Profit & Loss",      icon: "graph-up-arrow",        path: "/accounting/reports/profit-loss",      group: "Accounting", roles: ACCOUNTING_ROLES },
    { id: "acct-bs",        label: "Balance Sheet",      icon: "table",                 path: "/accounting/reports/balance-sheet",    group: "Accounting", roles: ACCOUNTING_ROLES },
    { id: "new-boe",        label: "New Bill of Entry",  icon: "plus-circle",           path: "/bill-of-entries/create", group: "Quick Create", roles: [ROLES.BOE_MANAGER] },
    { id: "new-allotment",  label: "New Allotment",      icon: "plus-circle",           path: "/allotments/create",      group: "Quick Create", roles: [ROLES.ALLOTMENT_MANAGER] },
    { id: "new-license",    label: "New License",        icon: "plus-circle",           path: "/licenses/create",        group: "Quick Create", roles: [ROLES.LICENSE_MANAGER] },
    { id: "profile",        label: "Profile",            icon: "person",                path: "/profile",                group: "Account" },
];

function buildAllCommands(): CommandDef[] {
    const cmds: CommandDef[] = [...BASE_COMMANDS];
    reportEntities.forEach(r => {
        cmds.push({ id: "report-" + r.path, label: r.label, icon: r.icon || "bar-chart", path: r.path, group: "Reports", roles: [...(r.roles ?? REPORT_ROLES)] });
    });
    masterEntities.forEach(m => {
        cmds.push({ id: "master-" + m.path, label: m.label, icon: m.icon || "database", path: m.path, group: "Masters" });
    });
    return cmds;
}

const ALL_COMMANDS = buildAllCommands();

// ── Component ─────────────────────────────────────────────────────────────────

interface CommandPaletteProps {
    open: boolean;
    onClose: () => void;
}

export default function CommandPalette({ open, onClose }: CommandPaletteProps) {
    const navigate = useNavigate();
    const { isSuperAdmin, canManageUsers, hasAnyRole } = useContext(AuthContext);

    // Build role-filtered command list (domain logic — stays in React)
    const commands = (() => {
        const base = ALL_COMMANDS.filter(cmd => {
            if (isSuperAdmin && isSuperAdmin()) return true;
            return !cmd.roles || hasAnyRole(cmd.roles);
        });
        if (isSuperAdmin && isSuperAdmin()) {
            base.push({ id: "users",    label: "Users & Roles",   icon: "shield-lock",  path: "/settings",           group: "Admin" });
            base.push({ id: "activity", label: "Activity Log",    icon: "journal-text", path: "/admin/activity-log", group: "Admin" });
        } else if (canManageUsers && canManageUsers()) {
            base.push({ id: "users-list", label: "User Management", icon: "people", path: "/admin/users", group: "Admin" });
        }
        return base;
    })();

    // Derive unique groups preserving insertion order
    const groups = [...new Set(commands.map(c => c.group))];

    const execute = useCallback((path: string) => {
        navigate(path);
        onClose();
    }, [navigate, onClose]);

    if (!open) return null;

    return (
        // Backdrop — click outside to close
        <div
            className="cmd-backdrop"
            role="dialog"
            aria-modal="true"
            aria-label="Command palette"
            onClick={(e) => { if (e.target === e.currentTarget) onClose(); }}
        >
            {/*
             * cmdk's Command handles:
             *   ↑ / ↓   keyboard navigation
             *   Enter    item selection
             *   search   fuzzy filtering against item `value` props
             *   ARIA     combobox roles, aria-selected, etc.
             * We only add Escape → onClose (cmdk doesn't know about our modal).
             */}
            <Command
                className="cmd-panel"
                label="Command palette"
                loop
                onKeyDown={(e) => { if (e.key === "Escape") onClose(); }}
            >
                {/* Search row */}
                <div className="cmd-search-row">
                    <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                    <Command.Input
                        className="cmd-input"
                        placeholder="Search pages, reports, masters…"
                        autoFocus
                    />
                    <kbd className="cmd-hint">Esc</kbd>
                </div>

                {/* Results list — cmdk handles filtering and scroll-into-view */}
                <Command.List className="cmd-results">
                    <Command.Empty className="cmd-empty">
                        No results found.
                    </Command.Empty>

                    {groups.map(group => {
                        const groupCmds = commands.filter(c => c.group === group);
                        return (
                            <Command.Group
                                key={group}
                                heading={<span className="cmd-group-label">{group}</span>}
                            >
                                {groupCmds.map(cmd => (
                                    <Command.Item
                                        key={cmd.id}
                                        value={cmd.label}  // cmdk filters against this
                                        className="cmd-item"
                                        onSelect={() => execute(cmd.path)}
                                    >
                                        <span className="cmd-item-icon">
                                            <Icon name={cmd.icon} className="size-4" />
                                        </span>
                                        <span className="cmd-item-label">{cmd.label}</span>
                                    </Command.Item>
                                ))}
                            </Command.Group>
                        );
                    })}
                </Command.List>

                {/* Footer keyboard hints */}
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
            </Command>
        </div>
    );
}
