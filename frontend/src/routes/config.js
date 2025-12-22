export const routes = [
    {
        path: "/dashboard",
        label: "Dashboard",
        component: "Dashboard",
        protected: true,
        roles: ["admin", "manager", "accounts"],
        icon: "speedometer2",
    },
    {
        path: "/licenses",
        label: "Licenses",
        component: "LicensePage",
        protected: true,
        roles: ["admin", "manager"],
        icon: "file-earmark-text",
    },
    {
        path: "/allotments",
        label: "Allotments",
        component: "AllotmentPage",
        protected: true,
        roles: ["admin", "manager"],
        icon: "box-seam",
    },
    {
        path: "/bill-of-entries",
        label: "Bill of Entry",
        component: "MasterList",
        protected: true,
        roles: ["admin", "manager"],
        icon: "receipt",
    },
    {
        path: "/trades",
        label: "Trade In & Out",
        component: "MasterList",
        protected: true,
        roles: ["admin", "manager"],
        icon: "arrow-left-right",
    },
    {
        path: "/incentive-licenses",
        label: "Incentive Licenses",
        component: "MasterList",
        protected: true,
        roles: ["admin", "manager"],
        icon: "award",
    },
    {
        path: "/settings",
        label: "Settings",
        component: "Settings",
        protected: true,
        roles: ["admin"],
        icon: "gear",
    },
];

// Ledger entities configuration
export const ledgerEntities = [
    {
        path: "/ledger/chart-of-accounts",
        label: "Chart of Accounts",
        icon: "list-columns",
    },
    {
        path: "/ledger/bank-accounts",
        label: "Bank Accounts",
        icon: "bank",
    },
    {
        path: "/ledger/journal-entries",
        label: "Journal Entries",
        icon: "journal-text",
    },
    {
        path: "/ledger/party-ledger",
        label: "Party Ledger",
        icon: "people",
    },
    {
        path: "/ledger/account-ledger",
        label: "Account Ledger",
        icon: "list-ul",
    },
    {
        path: "/ledger/reports/balance-sheet",
        label: "Balance Sheet",
        icon: "bar-chart",
    },
    {
        path: "/ledger/reports/profit-loss",
        label: "Profit & Loss",
        icon: "graph-up",
    },
    {
        path: "/ledger/reports/trial-balance",
        label: "Trial Balance",
        icon: "calculator",
    },
    {
        path: "/ledger/reports/outstanding",
        label: "Outstanding Invoices",
        icon: "cash-stack",
    },
];

// Commission entities configuration
export const commissionEntities = [
    {
        path: "/commissions",
        label: "Commission List",
        icon: "percent",
    },
    {
        path: "/commissions/agents",
        label: "Agents",
        icon: "person-badge",
    },
    {
        path: "/commissions/calculate",
        label: "Calculate Commission",
        icon: "calculator",
    },
];

// Master data entities configuration
export const masterEntities = [
    {
        path: "/masters/companies",
        label: "Companies",
        entity: "companies",
        icon: "building",
    },
    {
        path: "/masters/ports",
        label: "Ports",
        entity: "ports",
        icon: "geo-alt",
    },
    {
        path: "/masters/hs-codes",
        label: "HS Codes",
        entity: "hs-codes",
        icon: "upc-scan",
    },
    {
        path: "/masters/head-norms",
        label: "Head Norms",
        entity: "head-norms",
        icon: "list-ul",
    },
    {
        path: "/masters/sion-classes",
        label: "SION Classes",
        entity: "sion-classes",
        icon: "diagram-3",
    },
    {
        path: "/masters/groups",
        label: "Groups",
        entity: "groups",
        icon: "folder",
    },
    {
        path: "/masters/item-names",
        label: "Item Names",
        entity: "item-names",
        icon: "tags",
    },
    {
        path: "/masters/exchange-rates",
        label: "Exchange Rates",
        entity: "exchange-rates",
        icon: "currency-exchange",
    },
    {
        path: "/masters/item-heads",
        label: "Item Heads (Deprecated)",
        entity: "item-heads",
        icon: "folder",
        deprecated: true,
    },
];

// Report entities configuration
export const reportEntities = [
    {
        path: "/reports/item-pivot",
        label: "Item Pivot Report",
        icon: "table",
    },
    {
        path: "/reports/item-report",
        label: "Item Report",
        icon: "list-ul",
    },
];
