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
