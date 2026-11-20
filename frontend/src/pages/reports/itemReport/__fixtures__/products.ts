import type { ProductDrilldown, ProductMetrics, ProductReport, ProductRow } from "../productTypes";

/** Shared contract fixtures for `reports/item-report/products/` — align with the backend serializer here only. */

const metrics = (over: Partial<ProductMetrics> = {}): ProductMetrics => ({
    total_qty: "1000.000", total_cif: "5000.00", allotted_qty: "200.000", allotted_cif: "1000.00",
    debited_qty: "300.000", debited_cif: "1500.00", invoice_qty: "100.000", invoice_cif: "500.00",
    balance_qty: "500.000", balance_cif: "2500.00", planned_qty: "50.000", planned_cif: "250.00",
    ...over,
});

const product = (over: Partial<ProductRow>): ProductRow => ({
    key: "k", canonical_item_id: 1, item_name: "ITEM", sion: "E126", product_category: "FOOD",
    hsn_codes: ["15132110"], license_count: 2, units: ["KG"], mixed_units: false, is_planned: true,
    ...metrics(), ...over,
});

export const PKO = product({ key: "pko|E126", canonical_item_id: 11, item_name: "PKO", hsn_codes: ["15132110", "15132190"] });
export const PALM_KERNEL_OIL = product({
    key: "pko-long|E126", canonical_item_id: 12, item_name: "PALM KERNEL OIL", is_planned: false,
    total_qty: "40.000", balance_qty: "0.000", balance_cif: null, planned_qty: "0.000", planned_cif: "0.00",
    mixed_units: true, units: ["KG", "MT"],
});
export const NOT_ATTRIBUTED = product({
    key: "none|E126", canonical_item_id: null, item_name: "NOT ATTRIBUTED", is_planned: false, balance_cif: "0.00",
});

export const TOTALS: ProductMetrics = metrics({
    total_qty: "9999.000", total_cif: "88888.00", balance_cif: "7777.00",
});

export const PRODUCTS_RECONCILED: ProductReport = {
    report_date: "2026-11-20",
    scope: { norms: ["E126"], licence_count: 3, filters: {} },
    products: [PKO, PALM_KERNEL_OIL, NOT_ATTRIBUTED],
    totals: TOTALS,
    planning_counts: { all: 3, planned: 1, unplanned: 2 },
    reconciliation: { reconciled: true, metrics: {} },
};

export const PRODUCTS_MISMATCH: ProductReport = {
    ...PRODUCTS_RECONCILED,
    reconciliation: {
        reconciled: false,
        metrics: {
            balance_cif: { item_report: "2500.00", item_pivot: "2400.00", difference: "100.00" },
            total_qty: { item_report: "1000.000", item_pivot: "1000.000", difference: "0.000" },
        },
    },
};

export const DRILLDOWN_PKO: ProductDrilldown = {
    product: PKO,
    licences: [{
        license_id: 501, license_number: "0311012345",
        import_items: [{
            import_item_id: 7001, serial_number: 3, description: "PALM KERNEL OIL REFINED", hs_code: "15132110",
            norm: "E126", unit: "KG", total_qty: "600.000", total_cif: "3000.00",
        }],
        boes: [{ boe_id: 91, bill_of_entry_number: "BOE-7788", date: "2026-02-01", row_id: 1, qty: "120.000", cif: "600.00", share: "0.4" }],
        allotments: [{ allotment_id: 31, reference: "ALT-0042", row_id: 2, qty: "80.000", cif: "400.00", outstanding: "0.000" }],
        invoices: [{ invoice_id: 61, invoice_number: "INV-2026-9", date: "2026-03-05", line_id: 4, qty: "40.000", cif: "200.00" }],
        debited_qty: "120.000", debited_cif: "600.00", allotted_qty: "80.000", allotted_cif: "400.00",
        invoice_qty: "40.000", invoice_cif: "200.00", balance_qty: "400.000", balance_cif: "2000.00",
    }],
};
