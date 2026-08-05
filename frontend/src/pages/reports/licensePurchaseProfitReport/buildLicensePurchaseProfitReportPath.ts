/**
 * Pure URL-builder for the License Purchase & Profit Report — mirrors
 * `buildItemPivotReportPath` (ItemPivotReport.tsx) / `buildPlannedReportPath`
 * (PlannedReport.tsx): a `URLSearchParams` built from the current filters,
 * omitting anything blank or at its default so the query string stays
 * minimal and stable across re-renders.
 */

export type LicensePurchaseProfitReportPathOptions = {
    format: "json" | "excel" | "pdf";
    fromDate?: unknown;
    toDate?: unknown;
    norm?: unknown;
    licenseNumber?: unknown;
    /** Company id selected via `AsyncSelectField` — single value, may be an
     * `{value, label}` option object, a raw id, or null/undefined. */
    exporter?: unknown;
};

function normalizeExporterId(value: unknown): string {
    if (value === null || value === undefined || value === "") return "";
    if (typeof value === "object" && "value" in (value as Record<string, unknown>)) {
        return String((value as Record<string, unknown>).value ?? "").trim();
    }
    return String(value).trim();
}

export function buildLicensePurchaseProfitReportPath({
    format,
    fromDate,
    toDate,
    norm = "All",
    licenseNumber,
    exporter,
}: LicensePurchaseProfitReportPathOptions): string {
    const params = new URLSearchParams({ format });

    const from = String(fromDate ?? "").trim();
    const to = String(toDate ?? "").trim();
    const normValue = String(norm ?? "").trim();
    const license = String(licenseNumber ?? "").trim();
    const exporterId = normalizeExporterId(exporter);

    if (from) params.set("from_date", from);
    if (to) params.set("to_date", to);
    if (normValue && normValue !== "All") params.set("norm", normValue);
    if (license) params.set("license_number", license);
    if (exporterId) params.set("exporter_id", exporterId);

    return `reports/license-purchase-profit/?${params.toString()}`;
}
