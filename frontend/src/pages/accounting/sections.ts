/**
 * Information architecture of the accounting workspace: one source for the group tabs, the
 * per-group sub-navigation and the breadcrumbs. Every path here is a real route in
 * AccountingWorkspace (no placeholder screens). The main sidebar mirrors it in navConfig.ts.
 */
export interface SectionItem { to: string; label: string }
export interface SectionGroup { id: string; label: string; items: SectionItem[] }

const A = "/accounting";

export const ACCOUNTING_GROUPS: SectionGroup[] = [
    { id: "dashboard", label: "Dashboard", items: [{ to: `${A}/dashboard`, label: "Accounting Dashboard" }] },
    {
        id: "masters", label: "Masters", items: [
            { to: `${A}/masters/accounts`, label: "Chart of Accounts" },
            { to: `${A}/masters/groups`, label: "Account Groups" },
            { to: `${A}/masters/parties`, label: "Parties" },
        ],
    },
    {
        id: "transactions", label: "Transactions", items: [
            { to: `${A}/vouchers`, label: "All Vouchers" },
            { to: `${A}/vouchers/journal`, label: "Journal" },
            { to: `${A}/vouchers/payment`, label: "Payment" },
            { to: `${A}/vouchers/receipt`, label: "Receipt" },
            { to: `${A}/vouchers/contra`, label: "Contra" },
            { to: `${A}/vouchers/sales`, label: "Sales" },
            { to: `${A}/vouchers/purchase`, label: "Purchase" },
            { to: `${A}/payments`, label: "Record Payment / Receipt" },
            { to: `${A}/trades`, label: "Trade → Invoice" },
        ],
    },
    {
        id: "ledgers", label: "Ledgers", items: [
            { to: `${A}/reports/general-ledger`, label: "General Ledger" },
            { to: `${A}/party-ledger`, label: "Party Ledger" },
            { to: `${A}/ledgers/customers`, label: "Customer Ledger" },
            { to: `${A}/ledgers/suppliers`, label: "Supplier Ledger" },
        ],
    },
    {
        id: "banking", label: "Banking", items: [
            { to: `${A}/banking`, label: "Bank Accounts" },
            { to: `${A}/banking/transactions`, label: "Bank Transactions" },
            { to: `${A}/banking/unmatched`, label: "Unmatched Transactions" },
            { to: `${A}/banking/reconciliation`, label: "Bank Reconciliation" },
            { to: `${A}/banking/suspense`, label: "Suspense" },
            { to: `${A}/banking/workbench`, label: "Reconciliation Workbench" },
        ],
    },
    {
        id: "expenses", label: "Expenses & Income", items: [
            { to: `${A}/invoices`, label: "Bills & Expenses" },
            { to: `${A}/reports/register/expense`, label: "Expense Register" },
            { to: `${A}/reports/register/sales`, label: "Income (Sales) Register" },
            { to: `${A}/reports/register/purchase`, label: "Purchase Register" },
            { to: `${A}/reports/register/commission`, label: "Commission Register" },
            { to: `${A}/reports/register/notes`, label: "Debit / Credit Notes" },
            { to: `${A}/loans`, label: "Loans & Interest" },
        ],
    },
    {
        id: "reports", label: "Reports", items: [
            { to: `${A}/reports/trial-balance`, label: "Trial Balance" },
            { to: `${A}/reports/profit-loss`, label: "Profit & Loss" },
            { to: `${A}/reports/balance-sheet`, label: "Balance Sheet" },
            { to: `${A}/reports/cash-flow`, label: "Cash Flow" },
            { to: `${A}/reports/party-outstanding`, label: "Party Outstanding" },
            { to: `${A}/reports/receivables-ageing`, label: "Receivables Ageing" },
            { to: `${A}/reports/payables-ageing`, label: "Payables Ageing" },
            { to: `${A}/reports/cash-book`, label: "Cash Book" },
            { to: `${A}/reports/bank-book`, label: "Bank Book" },
            { to: `${A}/reports/voucher-register`, label: "Voucher Register" },
            { to: `${A}/reports/register`, label: "Registers" },
            { to: `${A}/reports/gst`, label: "GST" },
            { to: `${A}/reports/tds`, label: "TDS" },
            { to: `${A}/reports/trade-profitability`, label: "Trade Profitability" },
        ],
    },
    {
        id: "entities", label: "Entity-wise", items: [
            { to: `${A}/entities`, label: "Entity Summary" },
            { to: `${A}/reports/consolidated`, label: "Consolidated" },
        ],
    },
    {
        id: "admin", label: "Setup", items: [
            { to: `${A}/setup`, label: "Books Setup" },
            { to: `${A}/migration`, label: "Migration Center" },
        ],
    },
];

const matches = (pathname: string, to: string) => pathname === to || pathname.startsWith(`${to}/`);

/** Longest-prefix match over every item (the same rule as the main sidebar's active item). */
export function activeSection(pathname: string): { group: SectionGroup; item: SectionItem } | null {
    let best: { group: SectionGroup; item: SectionItem } | null = null;
    for (const group of ACCOUNTING_GROUPS) {
        for (const item of group.items) {
            if (matches(pathname, item.to) && item.to.length > (best?.item.to.length ?? 0)) best = { group, item };
        }
    }
    return best;
}
