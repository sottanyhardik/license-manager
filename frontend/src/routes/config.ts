export interface RouteConfig {
    path: string;
    label: string;
    component: string;
    protected: boolean;
    icon: string;
    superuserOnly?: boolean;
}

export interface EntityRouteConfig {
    path: string;
    label: string;
    entity: string;
    icon: string;
    deprecated?: boolean;
    /** Groups the master on the Masters hub and in the Masters menu. */
    category: MasterCategory;
    /** One-line purpose shown on the Masters hub. */
    description?: string;
}

/** Master categories, in display order. */
export const MASTER_CATEGORIES = [
    "Parties & places",
    "Items & SION norms",
    "Licence & customs reference",
    "Rates & pricing",
] as const;
export type MasterCategory = typeof MASTER_CATEGORIES[number];

export interface ReportRouteConfig {
    path: string;
    label: string;
    icon: string;
}

export const routes: RouteConfig[] = [
    {
        path: "/dashboard",
        label: "Dashboard",
        component: "Dashboard",
        protected: false,
        icon: "speedometer2",
    },
    {
        path: "/licenses",
        label: "Licenses",
        component: "LicensePage",
        protected: false,
        icon: "file-earmark-text",
    },
    {
        path: "/allotments",
        label: "Allotments",
        component: "AllotmentPage",
        protected: false,
        icon: "box-seam",
    },
    {
        path: "/bill-of-entries",
        label: "Bill of Entry",
        component: "MasterList",
        protected: false,
        icon: "receipt",
    },
    {
        path: "/trades",
        label: "Trade In & Out",
        component: "MasterList",
        protected: false,
        icon: "arrow-left-right",
    },
    {
        path: "/incentive-licenses",
        label: "Incentive Licenses",
        component: "MasterList",
        protected: false,
        icon: "award",
    },
    {
        path: "/license-ledger",
        label: "License Ledger",
        component: "LicenseLedger",
        protected: false,
        icon: "journal-text",
    },
    {
        path: "/settings",
        label: "Users & Roles",
        component: "Settings",
        protected: false,
        icon: "shield-lock",
        superuserOnly: true,
    },
];

// Master data entities configuration
export const masterEntities: EntityRouteConfig[] = [
    { path: "/masters/companies",            label: "Companies",            entity: "companies",            icon: "building",          category: "Parties & places",            description: "Exporters, importers and trading parties" },
    { path: "/masters/ports",                label: "Ports",                entity: "ports",                icon: "geo-alt",           category: "Parties & places",            description: "Customs ports of registration and clearance" },
    { path: "/masters/hs-codes",             label: "HS Codes",             entity: "hs-codes",             icon: "upc-scan",          category: "Items & SION norms",          description: "Tariff codes and their product descriptions" },
    { path: "/masters/head-norms",           label: "Head Norms",           entity: "head-norms",           icon: "list-ul",           category: "Items & SION norms",          description: "SION head norms" },
    { path: "/masters/sion-classes",         label: "SION Classes",         entity: "sion-classes",         icon: "diagram-3",         category: "Items & SION norms",          description: "SION norm classes with export and import items" },
    { path: "/masters/groups",               label: "Groups",               entity: "groups",               icon: "folder",            category: "Items & SION norms",          description: "Item groups" },
    { path: "/masters/item-names",           label: "Item Names",           entity: "item-names",           icon: "tags",              category: "Items & SION norms",          description: "Import item names used in planning and reports" },
    { path: "/masters/scheme-codes",         label: "Scheme Codes",         entity: "scheme-codes",         icon: "badge-tm",          category: "Licence & customs reference", description: "DGFT scheme codes on licences" },
    { path: "/masters/notification-numbers", label: "Notification Numbers", entity: "notification-numbers", icon: "file-earmark-text", category: "Licence & customs reference", description: "Customs notifications (e.g. 025/2023)" },
    { path: "/masters/purchase-statuses",    label: "Purchase Statuses",    entity: "purchase-statuses",    icon: "check2-square",     category: "Licence & customs reference", description: "Licence purchase status codes and their order" },
    { path: "/masters/transfer-letters",     label: "Transfer Letters",     entity: "transfer-letters",     icon: "file-earmark-arrow-up", category: "Licence & customs reference", description: "Transfer letter templates" },
    { path: "/masters/exchange-rates",       label: "Exchange Rates",       entity: "exchange-rates",       icon: "currency-exchange", category: "Rates & pricing",             description: "Customs exchange rates by date" },
    { path: "/masters/unit-prices",          label: "Unit Prices",          entity: "unit-prices",          icon: "currency-rupee",    category: "Rates & pricing",             description: "Reference unit prices" },
];
// Report entities configuration
export const reportEntities: ReportRouteConfig[] = [
    {
        path: "/license-ledger/download-requests",
        label: "License Downloads",
        icon: "file-earmark-excel",
    },
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
    {
        path: "/reports/planned-report",
        label: "Planned Report",
        icon: "check2-square",
    },
    {
        path: "/reports/license-purchase-profit",
        label: "Purchase & Profit Report",
        icon: "graph-up-arrow",
    },
];
