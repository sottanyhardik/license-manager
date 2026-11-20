import { describe, expect, it } from "vitest";
import { NAV_GROUPS, groupItems, resolveActiveNavPath, visibleNavGroups } from "./navConfig";
import { ROLES } from "../../routes/authorizationRoles";
import type { Role } from "../../routes/authorizationRoles";

const allRoles = Object.values(ROLES) as Role[];
const everyone = () => true;
const withRoles = (roles: Role[]) => (required: Role[]) => required.some(r => roles.includes(r));
const labelsByGroup = (groups = NAV_GROUPS) =>
    Object.fromEntries(groups.map(g => [g.label, groupItems(g).map(i => i.label)]));

// The menu hierarchy and paths the navigation must keep (regression baseline).
const EXPECTED = {
    Licenses: [
        ["Licenses", "/licenses"], ["Auto Plan", "/planning"], ["Incentive Licenses", "/incentive-licenses"],
        ["License Ledger", "/license-ledger"], ["Ledger Upload", "/ledger-upload"],
    ],
    Operations: [
        ["Allotments", "/allotments"], ["Bill of Entry", "/bill-of-entries"], ["Trade In & Out", "/trades"],
        ["Reconciliation", "/reconciliation"], ["Reconciliation Issues", "/reconciliation-issues"],
    ],
    Mapping: [["Item Name Mapping", "/mapping"]],
    Accounting: [
        ["Accounting Dashboard", "/accounting/dashboard"], ["Chart of Accounts", "/accounting/masters/accounts"],
        ["Account Groups", "/accounting/masters/groups"], ["Parties", "/accounting/masters/parties"],
        ["Entity-wise Books", "/accounting/entities"],
        ["All Vouchers", "/accounting/vouchers"], ["Journal Vouchers", "/accounting/vouchers/journal"],
        ["Payment Vouchers", "/accounting/vouchers/payment"], ["Receipt Vouchers", "/accounting/vouchers/receipt"],
        ["Contra Vouchers", "/accounting/vouchers/contra"], ["Sales Vouchers", "/accounting/vouchers/sales"],
        ["Purchase Vouchers", "/accounting/vouchers/purchase"], ["Payments & Receipts", "/accounting/payments"],
        ["Trade → Invoice", "/accounting/trades"],
        ["General Ledger", "/accounting/reports/general-ledger"], ["Party Ledger", "/accounting/party-ledger"],
        ["Customer Ledger", "/accounting/ledgers/customers"], ["Supplier Ledger", "/accounting/ledgers/suppliers"],
        ["Bills & Expenses", "/accounting/invoices"], ["Expense Register", "/accounting/reports/register/expense"],
        ["Income Register", "/accounting/reports/register/sales"], ["Loans & Interest", "/accounting/loans"],
        ["Bank Accounts", "/accounting/banking"], ["Bank Transactions", "/accounting/banking/transactions"],
        ["Unmatched Transactions", "/accounting/banking/unmatched"], ["Invoice Proposals", "/accounting/banking/proposals"], ["Bank Reconciliation", "/accounting/banking/reconciliation"],
        ["Suspense", "/accounting/banking/suspense"],
        ["Trial Balance", "/accounting/reports/trial-balance"], ["Profit & Loss", "/accounting/reports/profit-loss"],
        ["Balance Sheet", "/accounting/reports/balance-sheet"], ["Cash Flow", "/accounting/reports/cash-flow"],
        ["Party Outstanding", "/accounting/reports/party-outstanding"], ["Voucher Register", "/accounting/reports/voucher-register"],
        ["GST & TDS", "/accounting/reports/gst"], ["Consolidated", "/accounting/reports/consolidated"],
        ["Migration Center", "/accounting/migration"], ["Books Setup", "/accounting/setup"],
    ],
    Reports: [
        ["License Downloads", "/license-ledger/download-requests"], ["Item Pivot Report", "/reports/item-pivot"],
        ["Item Report", "/reports/item-report"], ["Planned Report", "/reports/planned-report"],
        ["Purchase & Profit Report", "/reports/license-purchase-profit"],
        ["Expiring Licenses", "/reports/expiring-licenses"], ["Active Licenses", "/reports/active-licenses"],
        ["Download License", "/reports/download-license"],
        ["SION E1 Report", "/reports/parle/sion-e1"], ["SION E5 Report", "/reports/parle/sion-e5"],
        ["SION E126 Report", "/reports/parle/sion-e126"], ["SION E132 Report", "/reports/parle/sion-e132"],
    ],
    Masters: [
        ["Masters overview", "/masters"],
        ["Companies", "/masters/companies"], ["Ports", "/masters/ports"], ["HS Codes", "/masters/hs-codes"],
        ["Head Norms", "/masters/head-norms"], ["SION Classes", "/masters/sion-classes"], ["Groups", "/masters/groups"],
        ["Item Names", "/masters/item-names"], ["Scheme Codes", "/masters/scheme-codes"],
        ["Notification Numbers", "/masters/notification-numbers"], ["Purchase Statuses", "/masters/purchase-statuses"],
        ["Transfer Letters", "/masters/transfer-letters"], ["Exchange Rates", "/masters/exchange-rates"],
        ["Unit Prices", "/masters/unit-prices"],
    ],
};

describe("Reports menu gates mirror their routes", () => {
    it("shows License Downloads only to roles its route (LEDGER_READ_ROLES) admits", () => {
        const reportLabels = (roles: Role[]) => labelsByGroup(visibleNavGroups(withRoles(roles))).Reports ?? [];
        // REPORT_VIEWER can open the Reports menu but the download-requests route would 403.
        expect(reportLabels([ROLES.REPORT_VIEWER])).not.toContain("License Downloads");
        expect(reportLabels([ROLES.REPORT_VIEWER])).toContain("Expiring Licenses");
        expect(reportLabels([ROLES.LICENSE_MANAGER])).toContain("License Downloads");
        expect(reportLabels([ROLES.TRADE_MANAGER])).toContain("License Downloads");
    });
});

describe("navConfig hierarchy", () => {
    it("keeps every category, item, order and route", () => {
        expect(NAV_GROUPS.map(g => g.label)).toEqual(Object.keys(EXPECTED));
        for (const group of NAV_GROUPS) {
            expect(groupItems(group).map(i => [i.label, i.path])).toEqual(EXPECTED[group.label as keyof typeof EXPECTED]);
        }
    });

    it("defines each route exactly once", () => {
        const paths = NAV_GROUPS.flatMap(groupItems).map(i => i.path);
        expect(new Set(paths).size).toBe(paths.length);
    });
});

describe("visibleNavGroups (role-based visibility)", () => {
    it("shows everything to a user with every role", () => {
        expect(labelsByGroup(visibleNavGroups(withRoles(allRoles)))).toEqual(labelsByGroup());
        expect(visibleNavGroups(everyone)).toHaveLength(6); // + Accounting + Mapping
    });

    it("gates Reports on REPORT_ROLES and keeps Masters ungated (unchanged behaviour)", () => {
        const groups = labelsByGroup(visibleNavGroups(withRoles([ROLES.LICENSE_VIEWER])));
        expect(Object.keys(groups)).toEqual(["Licenses", "Masters"]);
        expect(groups.Licenses).toEqual(["Licenses"]);
    });

    it("drops a group whose every item is hidden", () => {
        const groups = labelsByGroup(visibleNavGroups(withRoles([ROLES.TRADE_VIEWER])));
        expect(groups.Licenses).toEqual(["License Ledger"]);
        expect(groups.Operations).toEqual(["Trade In & Out", "Reconciliation Issues"]);
    });

    it("shows the Mapping workspace on the Reports gate", () => {
        expect(labelsByGroup(visibleNavGroups(withRoles([ROLES.LICENSE_MANAGER]))).Mapping).toEqual(["Item Name Mapping"]);
        expect(labelsByGroup(visibleNavGroups(withRoles([ROLES.LICENSE_VIEWER]))).Mapping).toBeUndefined();
    });

    it("hides Auto Plan from everyone but LICENSE_MANAGER", () => {
        expect(labelsByGroup(visibleNavGroups(withRoles([ROLES.LICENSE_VIEWER]))).Licenses).not.toContain("Auto Plan");
        expect(labelsByGroup(visibleNavGroups(withRoles([ROLES.LICENSE_MANAGER]))).Licenses).toContain("Auto Plan");
    });
});

describe("resolveActiveNavPath", () => {
    const groups = visibleNavGroups(everyone);
    it.each([
        ["/dashboard", "/dashboard"],
        ["/licenses", "/licenses"],
        ["/licenses/42/edit", "/licenses"],
        ["/license-ledger", "/license-ledger"],
        ["/license-ledger/download-requests", "/license-ledger/download-requests"],
        ["/reports/parle/sion-e126", "/reports/parle/sion-e126"],
        ["/masters/ports/3", "/masters/ports"],
        ["/masters", "/masters"],
        ["/mapping", "/mapping"],
        ["/masters/notification-numbers/025%2F2023/edit", "/masters/notification-numbers"],
        ["/profile", null],
        ["/licenses-archive", null],
    ])("%s → %s", (pathname, expected) => {
        expect(resolveActiveNavPath(pathname, groups)).toBe(expected);
    });
});
