import { useState } from "react";

/** `norm` query-param options the backend accepts (see `LICENSE_PURCHASE_PROFIT_NORM_OPTIONS`
 * on the sibling report — same `CONVERSION_NORMS` + `Others` catch-all / `All` no-op). */
export const LICENSE_TRADING_REGISTER_NORM_OPTIONS = ["All", "E1", "E5", "E126", "E132", "Others"] as const;

export type LicenseTradingRegisterNorm = (typeof LICENSE_TRADING_REGISTER_NORM_OPTIONS)[number];

/** `license_type` query-param options — DFIA is currently the only meaningful
 * value the backend filters on; `All` is a no-op. */
export const LICENSE_TRADING_REGISTER_LICENSE_TYPE_OPTIONS = ["All", "DFIA"] as const;

export type LicenseTradingRegisterLicenseType = (typeof LICENSE_TRADING_REGISTER_LICENSE_TYPE_OPTIONS)[number];

/**
 * Owns every filter on the License Trading Register & Profit Report:
 * From/To date (required by the backend to load anything), Norm, License
 * Type, License Number, Exporter, Item, Customer and Supplier — plus
 * "clear filters" and an active-filters flag. Mirrors the shape of
 * `useLicensePurchaseProfitReportFilters` but with the larger filter set
 * this report's contract requires.
 */
export function useLicenseTradingRegisterReportFilters() {
    const [fromDate, setFromDate] = useState("");
    const [toDate, setToDate] = useState("");
    const [norm, setNorm] = useState<string>("All");
    const [licenseType, setLicenseType] = useState<string>("All");
    const [licenseNumber, setLicenseNumber] = useState("");
    const [exporter, setExporter] = useState<unknown>(null);
    const [item, setItem] = useState<unknown>(null);
    const [customer, setCustomer] = useState<unknown>(null);
    const [supplier, setSupplier] = useState<unknown>(null);

    const handleExporterChange = (value: unknown) => {
        setExporter(value ?? null);
    };
    const handleItemChange = (value: unknown) => {
        setItem(value ?? null);
    };
    const handleCustomerChange = (value: unknown) => {
        setCustomer(value ?? null);
    };
    const handleSupplierChange = (value: unknown) => {
        setSupplier(value ?? null);
    };

    const handleClearFilters = () => {
        setFromDate("");
        setToDate("");
        setNorm("All");
        setLicenseType("All");
        setLicenseNumber("");
        setExporter(null);
        setItem(null);
        setCustomer(null);
        setSupplier(null);
    };

    const hasActiveFilters =
        Boolean(fromDate) ||
        Boolean(toDate) ||
        norm !== "All" ||
        licenseType !== "All" ||
        Boolean(licenseNumber) ||
        Boolean(exporter) ||
        Boolean(item) ||
        Boolean(customer) ||
        Boolean(supplier);

    return {
        fromDate,
        setFromDate,
        toDate,
        setToDate,
        norm,
        setNorm,
        licenseType,
        setLicenseType,
        licenseNumber,
        setLicenseNumber,
        exporter,
        handleExporterChange,
        item,
        handleItemChange,
        customer,
        handleCustomerChange,
        supplier,
        handleSupplierChange,

        hasActiveFilters,
        handleClearFilters,
    };
}
