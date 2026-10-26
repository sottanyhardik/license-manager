export type ItemPivotPathOptions = {
    format: string; normClass?: unknown; selectedCompanies?: unknown[]; excludeCompanies?: unknown[];
    minBalance?: unknown; licenseStatus?: unknown; expiryDateFrom?: unknown; expiryDateTo?: unknown; purchaseStatus?: unknown[];
};
export function toFiniteNumber(value: unknown, fallback = 0): number {
    const parsed = Number.parseFloat(String(value ?? ""));
    return Number.isFinite(parsed) ? parsed : fallback;
}
const normalizeFilterValues = (values?: unknown[]) => Array.isArray(values) ? values.map((value) => String(value ?? "").trim()).filter(Boolean) : [];
export function buildItemPivotReportPath({ format, normClass, selectedCompanies = [], excludeCompanies = [], minBalance = 200, licenseStatus = "active", expiryDateFrom, expiryDateTo, purchaseStatus = [] }: ItemPivotPathOptions): string {
    const params = new URLSearchParams({ format, days: "30" });
    const normClassValue = String(normClass ?? "").trim();
    const expiryFrom = String(expiryDateFrom ?? "").trim(); const expiryTo = String(expiryDateTo ?? "").trim();
    if (normClassValue) params.set("sion_norm", normClassValue);
    const included = normalizeFilterValues(selectedCompanies); const excluded = normalizeFilterValues(excludeCompanies); const statuses = normalizeFilterValues(purchaseStatus);
    if (included.length) params.set("company_ids", included.join(",")); if (excluded.length) params.set("exclude_company_ids", excluded.join(","));
    params.set("min_balance", String(toFiniteNumber(minBalance, 200))); params.set("license_status", String(licenseStatus || "active"));
    if (expiryFrom) params.set("expiry_date_from", expiryFrom); if (expiryTo) params.set("expiry_date_to", expiryTo); if (statuses.length) params.set("purchase_status", statuses.join(","));
    return `reports/item-pivot/?${params.toString()}`;
}

// Heading of the all-notification total section. Every norm uses this same text.
export const TOTAL_SUMMARY_TITLE = "TOTAL SUMMARY — ALL NOTIFICATIONS";

export const ITEM_FIELD_KEYS = ['hsn_code','description','total_qty','allotted_qty','allotted_cif','debited_qty','boe_used_cif','billed_qty','billed_cif','balance_qty','restriction_percent','restriction_value','plan_qty','planned_cif'];
export const ITEM_FIELD_LABELS = ['HSN CODE','DESCRIPTION','TOTAL QTY','ALLOTTED QTY','ALLOTTED CIF','DEBITED QTY','DEBITED CIF','BILLED QTY','BILLED CIF','BALANCE QTY','RESTRICTION %','RESTRICTION VAL','PLAN QTY','PLANNED CIF'];

// RUTILE blocks carry a UNIT PRICE column right after BALANCE QTY: total balance CIF / total balance QTY.
export function itemFieldKeys(item: any): string[] {
    if (item?.product_category !== 'RUTILE') return ITEM_FIELD_KEYS;
    return [...ITEM_FIELD_KEYS.slice(0, 10), 'unit_price', ...ITEM_FIELD_KEYS.slice(10)];
}

export function itemFieldLabels(item: any): string[] {
    if (item?.product_category !== 'RUTILE') return ITEM_FIELD_LABELS;
    return [...ITEM_FIELD_LABELS.slice(0, 10), 'UNIT PRICE', ...ITEM_FIELD_LABELS.slice(10)];
}

// A field column is hidden for an item block when every licence cell and the item total for it are null or 0.
// HSN CODE and DESCRIPTION are identity columns and always show.
export const ALWAYS_SHOWN_ITEM_FIELDS = ['hsn_code', 'description'];

export function hasPivotValue(value: unknown): boolean {
    return value != null && value !== '' && Number(value) !== 0;
}

export function visibleItemFields(item: any, group: any): { key: string; label: string }[] {
    const keys = itemFieldKeys(item);
    const labels = itemFieldLabels(item);
    const total = group.totals?.items?.[item.key];
    return keys
        .map((key, index) => ({ key, label: labels[index] }))
        .filter(({ key }) => ALWAYS_SHOWN_ITEM_FIELDS.includes(key)
            || hasPivotValue(total?.[key])
            || group.licenses.some((license: any) => hasPivotValue(license.items?.[item.key]?.[key])));
}

// Item Summary name: the product category (RUTILE, ALUMINIUM OXIDE, ...), because item names can be raw import descriptions.
export function itemSummaryName(row: { product_category?: string | null; item_name?: string | null }): string {
    const category = row.product_category;
    return category && category !== 'UNCLASSIFIED' ? category : (row.item_name || '');
}

// One Item Summary row per matrix item, read from the same totals the matrix shows above it.
// The SION suffix is dropped from the fallback name because the SION has its own column.
export function itemSummaryRowsFromMatrix(group: any): any[] {
    return (group.item_groups || []).map((item: any) => {
        const total = group.totals?.items?.[item.key] || {};
        const cells = (group.licenses || []).map((license: any) => license.items?.[item.key]).filter(Boolean);
        const sionSuffix = ` - ${item.sion}`;
        const rawName = item.name?.endsWith(sionSuffix) ? item.name.slice(0, -sionSuffix.length) : item.name;
        return {
            item_name: itemSummaryName({ product_category: item.product_category, item_name: rawName }),
            sion: item.sion,
            hsn_codes: [...new Set(cells.map((cell: any) => cell.hsn_code).filter(Boolean))],
            license_count: cells.length,
            total_qty: total.total_qty, allotted_qty: total.allotted_qty, allotted_cif: total.allotted_cif,
            boe_used_qty: total.debited_qty, boe_used_cif: total.boe_used_cif, balance_qty: total.balance_qty,
            unit_price: total.unit_price, planned_qty: total.plan_qty, planned_cif: total.planned_cif,
        };
    });
}

// SUBTOTAL for the Item Summary rows. Unit price is the balance-weighted average of the rows that have one.
export function itemSummarySubtotal(rows: any[]): Record<string, number | null> {
    const sum = (key: string) => rows.reduce((total, row) => total + (Number(row[key]) || 0), 0);
    const priced = rows.filter((row) => row.unit_price != null && Number(row.balance_qty) > 0);
    const weight = priced.reduce((total, row) => total + Number(row.balance_qty), 0);
    return {
        total_qty: sum('total_qty'), allotted_qty: sum('allotted_qty'), allotted_cif: sum('allotted_cif'),
        boe_used_qty: sum('boe_used_qty'), boe_used_cif: sum('boe_used_cif'), balance_qty: sum('balance_qty'),
        planned_qty: sum('planned_qty'), planned_cif: sum('planned_cif'),
        unit_price: weight > 0 ? priced.reduce((total, row) => total + Number(row.unit_price) * Number(row.balance_qty), 0) / weight : null,
    };
}
