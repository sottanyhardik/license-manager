/**
 * Shared query-string builder for the Item Report and Planned Report pages.
 *
 * Both reports accept the exact same filter parameters (item names,
 * companies, balance thresholds, license status, etc.) and only differ in
 * which endpoint path they're built against — see `ItemReport.tsx`'s
 * `buildItemReportPath` and `PlannedReport.tsx`'s `buildPlannedReportPath`,
 * both thin wrappers around `reportQueryString`.
 */

/** Raw filter values as tracked by `useItemReportFilters`. */
export type ReportFilterValues = {
    selectedItemNames?: unknown[];
    selectedCompanies?: unknown[];
    excludeCompanies?: unknown[];
    minBalance?: unknown;
    minAvailQty?: unknown;
    licenseStatus?: unknown;
    isRestricted?: unknown;
    purchaseStatus?: unknown[];
    productDescSearch?: unknown;
    hsnCodeSearch?: unknown;
    selectedNorms?: unknown[];
    selectedNotifications?: unknown[];
    expiryDateFrom?: unknown;
    expiryDateTo?: unknown;
};

export type ReportQueryOptions = ReportFilterValues & {
    format: "json" | "excel";
};

export function normalizeReportNumber(value: unknown, fallback = 0): number {
    const parsed = Number.parseInt(String(value ?? ""), 10);
    return Number.isFinite(parsed) ? parsed : fallback;
}

export function normalizeFilterValues(values?: unknown[]): string[] {
    if (!Array.isArray(values)) {
        return [];
    }

    return values
        .map((value) => String(value ?? "").trim())
        .filter(Boolean);
}

/**
 * Builds the query string (no leading `?`, no endpoint path) shared by
 * `reports/item-report/` and `reports/planned-report/`.
 */
export function reportQueryString({
    format,
    selectedItemNames = [],
    selectedCompanies = [],
    excludeCompanies = [],
    minBalance = 200,
    minAvailQty = 0,
    licenseStatus = "active",
    isRestricted = "all",
    purchaseStatus = [],
    productDescSearch,
    hsnCodeSearch,
    selectedNorms = [],
    selectedNotifications = [],
    expiryDateFrom,
    expiryDateTo,
}: ReportQueryOptions): string {
    // Use _format (underscore prefix) so DRF's ?format= content-negotiation
    // interceptor does not reject 'excel' as an unknown format.
    const params = new URLSearchParams(format === 'excel' ? {_format: format} : {format});
    const itemNames = normalizeFilterValues(selectedItemNames);
    const companyIds = normalizeFilterValues(selectedCompanies);
    const excludedCompanyIds = normalizeFilterValues(excludeCompanies);
    const purchaseStatuses = normalizeFilterValues(purchaseStatus);
    const norms = normalizeFilterValues(selectedNorms);
    const notifications = normalizeFilterValues(selectedNotifications);
    const productDescription = String(productDescSearch ?? "").trim();
    const hsnCode = String(hsnCodeSearch ?? "").trim();
    const restricted = String(isRestricted ?? "all").trim();
    const expiryFrom = String(expiryDateFrom ?? "").trim();
    const expiryTo = String(expiryDateTo ?? "").trim();

    if (itemNames.length > 0) params.set("item_names", itemNames.join(","));
    if (companyIds.length > 0) params.set("company_ids", companyIds.join(","));
    if (excludedCompanyIds.length > 0) params.set("exclude_company_ids", excludedCompanyIds.join(","));
    params.set("min_balance", String(normalizeReportNumber(minBalance, 200)));
    params.set("min_avail_qty", String(normalizeReportNumber(minAvailQty, 0)));
    params.set("license_status", String(licenseStatus || "active"));
    if (restricted && restricted !== "all") params.set("is_restricted", restricted);
    if (purchaseStatuses.length > 0) params.set("purchase_status", purchaseStatuses.join(","));
    if (productDescription) params.set("product_description", productDescription);
    if (hsnCode) params.set("hsn_code", hsnCode);
    if (norms.length > 0) params.set("norms", norms.join(","));
    if (notifications.length > 0) params.set("notification_numbers", notifications.join(","));
    if (expiryFrom) params.set("expiry_date_from", expiryFrom);
    if (expiryTo) params.set("expiry_date_to", expiryTo);

    return params.toString();
}
