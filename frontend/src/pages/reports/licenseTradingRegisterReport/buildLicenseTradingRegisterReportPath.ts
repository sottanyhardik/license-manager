/**
 * Pure URL-builder for the License Trading Register & Profit Report —
 * mirrors `buildLicensePurchaseProfitReportPath` (LicensePurchaseProfitReport.tsx)
 * / `buildPlannedReportPath` (PlannedReport.tsx): a `URLSearchParams` built
 * from the current filters, omitting anything blank or at its default so
 * the query string stays minimal and stable across re-renders.
 */

export type LicenseTradingRegisterReportPathOptions = {
    format: "json" | "excel" | "pdf";
    fromDate?: unknown;
    toDate?: unknown;
    norm?: unknown;
    licenseType?: unknown;
    licenseNumber?: unknown;
    /** Company/item ids selected via `AsyncSelectField` — single value, may
     * be an `{value, label}` option object, a raw id, or null/undefined. */
    exporter?: unknown;
    item?: unknown;
    customer?: unknown;
    supplier?: unknown;
};

function normalizeOptionId(value: unknown): string {
    if (value === null || value === undefined || value === "") return "";
    if (typeof value === "object" && "value" in (value as Record<string, unknown>)) {
        return String((value as Record<string, unknown>).value ?? "").trim();
    }
    return String(value).trim();
}

export function buildLicenseTradingRegisterReportPath({
    format,
    fromDate,
    toDate,
    norm = "All",
    licenseType = "All",
    licenseNumber,
    exporter,
    item,
    customer,
    supplier,
}: LicenseTradingRegisterReportPathOptions): string {
    const params = new URLSearchParams({ format });

    const from = String(fromDate ?? "").trim();
    const to = String(toDate ?? "").trim();
    const normValue = String(norm ?? "").trim();
    const licenseTypeValue = String(licenseType ?? "").trim();
    const license = String(licenseNumber ?? "").trim();
    const exporterId = normalizeOptionId(exporter);
    const itemId = normalizeOptionId(item);
    const customerId = normalizeOptionId(customer);
    const supplierId = normalizeOptionId(supplier);

    if (from) params.set("from_date", from);
    if (to) params.set("to_date", to);
    if (normValue && normValue !== "All") params.set("norm", normValue);
    if (licenseTypeValue && licenseTypeValue !== "All") params.set("license_type", licenseTypeValue);
    if (license) params.set("license_number", license);
    if (exporterId) params.set("exporter_id", exporterId);
    if (itemId) params.set("item_id", itemId);
    if (customerId) params.set("customer_id", customerId);
    if (supplierId) params.set("supplier_id", supplierId);

    return `reports/license-trading-register-profit/?${params.toString()}`;
}
