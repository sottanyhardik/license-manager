import { useState } from "react";

/** `norm` query-param options the backend accepts (see backend service's
 * `CONVERSION_NORMS` + `Others` catch-all / `All` no-op). */
export const LICENSE_PURCHASE_PROFIT_NORM_OPTIONS = ["All", "E1", "E5", "E126", "E132", "Others"] as const;

export type LicensePurchaseProfitNorm = (typeof LICENSE_PURCHASE_PROFIT_NORM_OPTIONS)[number];

/**
 * Owns every filter on the License Purchase & Profit Report: From/To date
 * (required by the backend to load anything), Norm, License Number and
 * Exporter — plus "clear filters" and an active-filters flag. Mirrors the
 * shape of `useItemReportFilters` (state + handlers + `hasActiveFilters`)
 * but scoped to this report's much smaller filter set.
 */
export function useLicensePurchaseProfitReportFilters() {
    const [fromDate, setFromDate] = useState("");
    const [toDate, setToDate] = useState("");
    const [norm, setNorm] = useState<string>("All");
    const [licenseNumber, setLicenseNumber] = useState("");
    const [exporter, setExporter] = useState<unknown>(null);

    const handleExporterChange = (value: unknown) => {
        setExporter(value ?? null);
    };

    const handleClearFilters = () => {
        setFromDate("");
        setToDate("");
        setNorm("All");
        setLicenseNumber("");
        setExporter(null);
    };

    const hasActiveFilters = Boolean(fromDate) || Boolean(toDate) || norm !== "All" || Boolean(licenseNumber) || Boolean(exporter);

    return {
        fromDate,
        setFromDate,
        toDate,
        setToDate,
        norm,
        setNorm,
        licenseNumber,
        setLicenseNumber,
        exporter,
        handleExporterChange,

        hasActiveFilters,
        handleClearFilters,
    };
}
