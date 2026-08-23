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
    /** License numbers to exclude entirely — applied AFTER
     * `licenseNumber`/`norm`/`exporter` inclusion; always wins over an
     * overlapping inclusion. Accepts a chip-input `string[]` or a
     * comma-separated string. */
    excludeLicenseNumber?: unknown;
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

function normalizeExcludeLicenseNumbers(value: unknown): string {
    if (Array.isArray(value)) {
        return value.map((v) => String(v ?? "").trim()).filter(Boolean).join(",");
    }
    return String(value ?? "").trim();
}

export function buildLicensePurchaseProfitReportPath({
    format,
    fromDate,
    toDate,
    norm = "All",
    licenseNumber,
    excludeLicenseNumber,
    exporter,
}: LicensePurchaseProfitReportPathOptions): string {
    const params = new URLSearchParams({ format });

    const from = String(fromDate ?? "").trim();
    const to = String(toDate ?? "").trim();
    const normValue = String(norm ?? "").trim();
    const license = String(licenseNumber ?? "").trim();
    const excludeLicense = normalizeExcludeLicenseNumbers(excludeLicenseNumber);
    const exporterId = normalizeExporterId(exporter);

    if (from) params.set("from_date", from);
    if (to) params.set("to_date", to);
    if (normValue && normValue !== "All") params.set("norm", normValue);
    if (license) params.set("license_number", license);
    if (excludeLicense) params.set("exclude_license_number", excludeLicense);
    if (exporterId) params.set("exporter_id", exporterId);

    return `reports/license-purchase-profit/?${params.toString()}`;
}

/** Query-string keys this report's filters read/write — shared by
 * `hasLicensePurchaseProfitReportParams` and `parseLicensePurchaseProfitReportParams`
 * so the two stay in lockstep. */
const FILTER_PARAM_KEYS = [
    "from_date",
    "to_date",
    "norm",
    "license_number",
    "exclude_license_number",
    "exporter_id",
] as const;

/** Filter values as read back out of a `URLSearchParams` — the inverse of
 * `buildLicensePurchaseProfitReportPath`'s inputs (minus `format`, which
 * isn't a persisted filter). */
export type LicensePurchaseProfitReportParams = {
    fromDate: string;
    toDate: string;
    norm: string;
    licenseNumber: string;
    excludeLicenseNumber: string[];
    exporter: number | null;
};

/** True when the URL carries ANY of this report's filter params — used to
 * decide between hydrating from the URL vs. falling back to sessionStorage
 * on mount (e.g. arriving via a nav link rather than Back/refresh). */
export function hasLicensePurchaseProfitReportParams(searchParams: URLSearchParams): boolean {
    return FILTER_PARAM_KEYS.some((key) => searchParams.has(key));
}

/**
 * Parses this report's filters back out of a `URLSearchParams` — the
 * inverse of `buildLicensePurchaseProfitReportPath`. Missing params fall
 * back to the same defaults `useLicensePurchaseProfitReportFilters` uses
 * (`norm: "All"`, everything else empty/null).
 */
export function parseLicensePurchaseProfitReportParams(searchParams: URLSearchParams): LicensePurchaseProfitReportParams {
    const fromDate = searchParams.get("from_date") ?? "";
    const toDate = searchParams.get("to_date") ?? "";
    const norm = searchParams.get("norm") ?? "All";
    const licenseNumber = searchParams.get("license_number") ?? "";
    const excludeLicenseNumberRaw = searchParams.get("exclude_license_number") ?? "";
    const excludeLicenseNumber = excludeLicenseNumberRaw
        ? excludeLicenseNumberRaw.split(",").map((v) => v.trim()).filter(Boolean)
        : [];
    const exporterIdRaw = searchParams.get("exporter_id");
    const exporterId = exporterIdRaw !== null && exporterIdRaw !== "" ? Number(exporterIdRaw) : NaN;
    const exporter = Number.isFinite(exporterId) ? exporterId : null;

    return { fromDate, toDate, norm, licenseNumber, excludeLicenseNumber, exporter };
}
