export const routes = [
    {
        path: "/dashboard",
        label: "Dashboard",
        component: "Dashboard",
        protected: true,
        roles: [], // All authenticated users can access dashboard
        icon: "speedometer2",
    },
    {
        path: "/licenses",
        label: "Licenses",
        component: "LicensePage",
        protected: true,
        roles: ["LICENSE_MANAGER", "LICENSE_VIEWER"],
        icon: "file-earmark-text",
    },
    {
        path: "/allotments",
        label: "Allotments",
        component: "AllotmentPage",
        protected: true,
        roles: ["ALLOTMENT_MANAGER", "ALLOTMENT_VIEWER"],
        icon: "box-seam",
    },
    {
        path: "/bill-of-entries",
        label: "Bill of Entry",
        component: "MasterList",
        protected: true,
        roles: ["BOE_MANAGER", "BOE_VIEWER"],
        icon: "receipt",
    },
    {
        path: "/trades",
        label: "Trade In & Out",
        component: "MasterList",
        protected: true,
        roles: ["TRADE_MANAGER", "TRADE_VIEWER"],
        icon: "arrow-left-right",
    },
    {
        path: "/incentive-licenses",
        label: "Incentive Licenses",
        component: "MasterList",
        protected: true,
        roles: ["INCENTIVE_LICENSE_MANAGER", "INCENTIVE_LICENSE_VIEWER"],
        icon: "award",
    },
    {
        path: "/license-ledger",
        label: "License Ledger",
        component: "LicenseLedger",
        protected: true,
        roles: ["TRADE_VIEWER", "TRADE_MANAGER", "LICENSE_MANAGER"],
        icon: "journal-text",
    },
    {
        path: "/settings",
        label: "Settings",
        component: "Settings",
        protected: true,
        roles: ["USER_MANAGER"],
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
