/** Response shapes of `GET reports/item-report/products/` and its `drilldown/` — Decimals are strings. */

export const PRODUCT_METRICS = [
    "total_qty", "total_cif", "allotted_qty", "allotted_cif", "debited_qty", "debited_cif",
    "invoice_qty", "invoice_cif", "balance_qty", "balance_cif", "planned_qty", "planned_cif",
] as const;

export type ProductMetric = (typeof PRODUCT_METRICS)[number];

export type ProductMetrics = Record<ProductMetric, string | null>;

export type ProductRow = ProductMetrics & {
    key: string;
    canonical_item_id: number | null;
    item_name: string;
    sion: string;
    product_category: string;
    hsn_codes: string[];
    license_count: number;
    units: string[];
    mixed_units: boolean;
    is_planned: boolean;
};

export type ProductReconciliation = {
    reconciled: boolean;
    metrics: Record<string, { item_report: string | null; item_pivot: string | null; difference: string | null }>;
};

export type ProductReport = {
    report_date: string;
    scope: { norms: string[]; licence_count: number; filters: Record<string, unknown> };
    products: ProductRow[];
    totals: ProductMetrics;
    planning_counts: { all: number; planned: number; unplanned: number };
    reconciliation: ProductReconciliation;
};

export type DrilldownLicence = {
    license_id: number;
    license_number: string;
    import_items: {
        import_item_id: number; serial_number: number | null; description: string; hs_code: string;
        norm: string; unit: string; total_qty: string | null; total_cif: string | null;
    }[];
    boes: { boe_id: number; bill_of_entry_number: string; date: string | null; row_id: number; qty: string | null; cif: string | null; share?: string | null }[];
    allotments: { allotment_id: number; reference: string; row_id: number; qty: string | null; cif: string | null; outstanding: string | null }[];
    invoices: { invoice_id: number; invoice_number: string; date: string | null; line_id: number; qty: string | null; cif: string | null; share?: string | null }[];
    debited_qty: string | null;
    debited_cif: string | null;
    allotted_qty: string | null;
    allotted_cif: string | null;
    invoice_qty: string | null;
    invoice_cif: string | null;
    balance_qty: string | null;
    balance_cif: string | null;
};

export type ProductDrilldown = { product: ProductRow; licences: DrilldownLicence[] };
