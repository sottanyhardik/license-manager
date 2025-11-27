export const routes = [
    {
        path: "/dashboard",
        label: "Dashboard",
        component: "Dashboard",
        protected: true,
        roles: ["admin", "manager", "viewer"],
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
        path: "/settings",
        label: "Settings",
        component: "Settings",
        protected: true,
        roles: ["admin"],
        icon: "gear",
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
        path: "/masters/item-heads",
        label: "Item Heads",
        entity: "item-heads",
        icon: "folder",
    },
    {
        path: "/masters/item-names",
        label: "Item Names",
        entity: "item-names",
        icon: "tags",
    },
];

// Report entities configuration
export const reportEntities = [
    {
        path: "/reports/expiring-licenses",
        label: "Expiring Licenses",
        icon: "calendar-x",
    },
];
