/**
 * Single source of truth for the primary navigation (desktop menu bar and the
 * mobile drawer both render from this).  Route paths are not redefined here:
 * Reports and Masters reuse `reportEntities` / `masterEntities` from
 * routes/config.ts (also consumed by the command palette), and every role gate
 * mirrors the guard on the matching route in AppRoutes.
 */
import { masterEntities, reportEntities } from "../../routes/config";
import {
    ACCOUNTING_ROLES, ALLOTMENT_ROLES, BOE_LIST_ROLES, INCENTIVE_LICENSE_ROLES, LEDGER_READ_ROLES, LEDGER_UPLOAD_ROLES,
    LICENSE_ROLES, RECONCILIATION_ISSUES_ROLES, RECONCILIATION_ROLES, REPORT_ROLES, ROLES, TRADE_ROLES,
} from "../../routes/authorizationRoles";
import type { Role } from "../../routes/authorizationRoles";

export interface NavItem {
    path: string;
    label: string;
    /** Legacy icon name rendered through <Icon name="…"> (lucide-backed). */
    icon: string;
    /** Item is shown only when the user has any of these roles (omitted = everyone). */
    roles?: readonly Role[];
}

export interface NavSection {
    /** Optional heading; omitted for single-section groups. */
    label?: string;
    items: NavItem[];
}

export interface NavGroup {
    id: string;
    label: string;
    icon: string;
    /** Whole group is shown only when the user has any of these roles. */
    roles?: readonly Role[];
    /** Dropdown column count on desktop (sections flow into columns). */
    columns?: 1 | 2 | 3;
    sections: NavSection[];
}

export const DASHBOARD_PATH = "/dashboard";

// Report routes that exist in AppRoutes (all guarded by REPORT_ROLES, the same
// gate as the whole Reports menu) but are not in routes/config.ts, so the
// command palette is unaffected.
const LICENCE_STATUS_REPORTS: NavItem[] = [
    { path: "/reports/expiring-licenses", label: "Expiring Licenses", icon: "exclamation-triangle" },
    { path: "/reports/active-licenses",   label: "Active Licenses",   icon: "check-circle" },
    { path: "/reports/download-license",  label: "Download License",  icon: "download" },
];
const SION_REPORTS: NavItem[] = [
    { path: "/reports/parle/sion-e1",   label: "SION E1 Report",   icon: "file-earmark-text" },
    { path: "/reports/parle/sion-e5",   label: "SION E5 Report",   icon: "file-earmark-text" },
    { path: "/reports/parle/sion-e126", label: "SION E126 Report", icon: "file-earmark-text" },
    { path: "/reports/parle/sion-e132", label: "SION E132 Report", icon: "file-earmark-text" },
];

export const NAV_GROUPS: readonly NavGroup[] = [
    {
        id: "licenses",
        label: "Licenses",
        icon: "file-earmark-text",
        sections: [{
            items: [
                { path: "/licenses",           label: "Licenses",           icon: "file-earmark-text", roles: LICENSE_ROLES },
                { path: "/planning",           label: "Auto Plan",          icon: "diagram-3",         roles: [ROLES.LICENSE_MANAGER] },
                { path: "/incentive-licenses", label: "Incentive Licenses", icon: "award",             roles: INCENTIVE_LICENSE_ROLES },
                { path: "/license-ledger",     label: "License Ledger",     icon: "journal-text",      roles: LEDGER_READ_ROLES },
                { path: "/ledger-upload",      label: "Ledger Upload",      icon: "cloud-upload",      roles: LEDGER_UPLOAD_ROLES },
            ],
        }],
    },
    {
        id: "operations",
        label: "Operations",
        icon: "arrow-left-right",
        sections: [{
            items: [
                { path: "/allotments",            label: "Allotments",            icon: "box-seam",             roles: ALLOTMENT_ROLES },
                { path: "/bill-of-entries",       label: "Bill of Entry",         icon: "receipt",              roles: BOE_LIST_ROLES },
                { path: "/trades",                label: "Trade In & Out",        icon: "arrow-left-right",     roles: TRADE_ROLES },
                { path: "/reconciliation",        label: "Reconciliation",        icon: "check2-square",        roles: RECONCILIATION_ROLES },
                { path: "/reconciliation-issues", label: "Reconciliation Issues", icon: "exclamation-triangle", roles: RECONCILIATION_ISSUES_ROLES },
            ],
        }],
    },
    {
        id: "accounting",
        label: "Accounting",
        icon: "journal-text",
        roles: ACCOUNTING_ROLES,
        columns: 3,
        sections: [
            {
                label: "Overview & masters",
                items: [
                    { path: "/accounting/dashboard",        label: "Accounting Dashboard", icon: "speedometer2" },
                    { path: "/accounting/masters/accounts", label: "Chart of Accounts",    icon: "list-ul" },
                    { path: "/accounting/masters/groups",   label: "Account Groups",       icon: "folder" },
                    { path: "/accounting/masters/parties",  label: "Parties",              icon: "people" },
                    { path: "/accounting/entities",         label: "Entity-wise Books",    icon: "building" },
                ],
            },
            {
                label: "Transactions",
                items: [
                    { path: "/accounting/vouchers",          label: "All Vouchers",           icon: "journal-text" },
                    { path: "/accounting/vouchers/journal",  label: "Journal Vouchers",       icon: "pencil-square" },
                    { path: "/accounting/vouchers/payment",  label: "Payment Vouchers",       icon: "box-arrow-right" },
                    { path: "/accounting/vouchers/receipt",  label: "Receipt Vouchers",       icon: "box-arrow-in-down" },
                    { path: "/accounting/vouchers/contra",   label: "Contra Vouchers",        icon: "arrow-repeat" },
                    { path: "/accounting/vouchers/sales",    label: "Sales Vouchers",         icon: "graph-up-arrow" },
                    { path: "/accounting/vouchers/purchase", label: "Purchase Vouchers",      icon: "receipt" },
                    { path: "/accounting/payments",          label: "Payments & Receipts",    icon: "receipt-cutoff" },
                    { path: "/accounting/trades",            label: "Trade → Invoice",        icon: "arrow-left-right" },
                ],
            },
            {
                label: "Ledgers, expenses & income",
                items: [
                    { path: "/accounting/reports/general-ledger",   label: "General Ledger",    icon: "journal-text" },
                    { path: "/accounting/party-ledger",             label: "Party Ledger",      icon: "person" },
                    { path: "/accounting/ledgers/customers",        label: "Customer Ledger",   icon: "person-circle" },
                    { path: "/accounting/ledgers/suppliers",        label: "Supplier Ledger",   icon: "person-plus" },
                    { path: "/accounting/invoices",                 label: "Bills & Expenses",  icon: "receipt" },
                    { path: "/accounting/reports/register/expense", label: "Expense Register",  icon: "file-earmark-text" },
                    { path: "/accounting/reports/register/sales",   label: "Income Register",   icon: "currency-rupee" },
                    { path: "/accounting/loans",                    label: "Loans & Interest",  icon: "table" },
                ],
            },
            {
                label: "Banking",
                items: [
                    { path: "/accounting/banking",                label: "Bank Accounts",          icon: "database" },
                    { path: "/accounting/banking/transactions",   label: "Bank Transactions",      icon: "list-ul" },
                    { path: "/accounting/banking/unmatched",      label: "Unmatched Transactions", icon: "exclamation-circle" },
                    { path: "/accounting/banking/reconciliation", label: "Bank Reconciliation",    icon: "check2-square" },
                    { path: "/accounting/banking/suspense",       label: "Suspense",               icon: "exclamation-triangle" },
                ],
            },
            {
                label: "Reports & setup",
                items: [
                    { path: "/accounting/reports/trial-balance",     label: "Trial Balance",     icon: "list-ul" },
                    { path: "/accounting/reports/profit-loss",       label: "Profit & Loss",     icon: "graph-up-arrow" },
                    { path: "/accounting/reports/balance-sheet",     label: "Balance Sheet",     icon: "table" },
                    { path: "/accounting/reports/cash-flow",         label: "Cash Flow",         icon: "currency-exchange" },
                    { path: "/accounting/reports/party-outstanding", label: "Party Outstanding", icon: "people" },
                    { path: "/accounting/reports/voucher-register",  label: "Voucher Register",  icon: "journal-text" },
                    { path: "/accounting/reports/gst",               label: "GST & TDS",         icon: "receipt" },
                    { path: "/accounting/reports/consolidated",      label: "Consolidated",      icon: "intersect" },
                    { path: "/accounting/migration",                 label: "Migration Center",  icon: "file-earmark-arrow-up" },
                    { path: "/accounting/setup",                     label: "Books Setup",       icon: "shield-lock" },
                ],
            },
        ],
    },
    {
        id: "reports",
        label: "Reports",
        icon: "bar-chart-line",
        roles: REPORT_ROLES,
        columns: 3,
        sections: [
            { label: "Reports",        items: reportEntities.map(({ path, label, icon }) => ({ path, label, icon })) },
            { label: "Licence status", items: LICENCE_STATUS_REPORTS },
            { label: "SION norms",     items: SION_REPORTS },
        ],
    },
    {
        id: "masters",
        label: "Masters",
        icon: "database",
        columns: 2,
        sections: [{
            items: masterEntities.filter(m => !m.deprecated).map(({ path, label, icon }) => ({ path, label, icon })),
        }],
    },
];

type HasAnyRole = (roles: Role[]) => boolean;

const allowed = (roles: readonly Role[] | undefined, hasAnyRole: HasAnyRole) =>
    !roles || hasAnyRole([...roles]);

/** Groups/sections/items the user may see; empty sections and groups are dropped. */
export function visibleNavGroups(hasAnyRole: HasAnyRole, groups: readonly NavGroup[] = NAV_GROUPS): NavGroup[] {
    return groups
        .filter(group => allowed(group.roles, hasAnyRole))
        .map(group => ({
            ...group,
            sections: group.sections
                .map(section => ({ ...section, items: section.items.filter(item => allowed(item.roles, hasAnyRole)) }))
                .filter(section => section.items.length > 0),
        }))
        .filter(group => group.sections.length > 0);
}

export const groupItems = (group: NavGroup): NavItem[] => group.sections.flatMap(s => s.items);

const matches = (pathname: string, path: string) => pathname === path || pathname.startsWith(path + "/");

/**
 * The single nav path to highlight for `pathname`: the longest matching path,
 * so e.g. /license-ledger/download-requests highlights "License Downloads"
 * rather than also lighting up "License Ledger".
 */
export function resolveActiveNavPath(pathname: string, groups: readonly NavGroup[]): string | null {
    let best: string | null = matches(pathname, DASHBOARD_PATH) ? DASHBOARD_PATH : null;
    for (const group of groups) {
        for (const item of groupItems(group)) {
            if (matches(pathname, item.path) && item.path.length > (best?.length ?? 0)) best = item.path;
        }
    }
    return best;
}
