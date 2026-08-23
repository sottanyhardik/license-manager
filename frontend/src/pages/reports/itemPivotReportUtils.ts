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
