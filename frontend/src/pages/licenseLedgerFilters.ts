import { getFinancialYearRange } from "../utils/dateRangePresets";

export type SelectValue = string | number | { value: string | number; label?: string } | null;
export type LicenseLedgerFilters = {
    company: SelectValue; licenseType: string; minBalance: string; search: string;
    ordering: string; activeOnly: boolean; norm: SelectValue; purchaseStatus: SelectValue;
    purchaseBill: string; purchaseDateFrom: string; purchaseDateTo: string;
    licenseNumbers: string; excludeLicenseNumbers: string;
};

export function defaultLicenseLedgerFilters(date = new Date()): LicenseLedgerFilters {
    const { fyStart, fyEnd } = getFinancialYearRange(date);
    return { company: null, licenseType: "ALL", minBalance: "", search: "",
        ordering: "-license_date", activeOnly: false, norm: null, purchaseStatus: null,
        purchaseBill: "ALL", purchaseDateFrom: fyStart, purchaseDateTo: fyEnd, licenseNumbers: "", excludeLicenseNumbers: "" };
}

const selected = (value: SelectValue): string => {
    const identifier = typeof value === "object" && value !== null ? value.value : value;
    if (identifier === null || identifier === undefined) return "";
    const normalized = String(identifier).trim();
    return normalized && normalized !== "undefined" && normalized !== "null" ? normalized : "";
};

export function buildLicenseLedgerParams(filters: LicenseLedgerFilters): URLSearchParams {
    const params = new URLSearchParams();
    params.set("license_type", filters.licenseType);
    params.set("ordering", filters.ordering);
    if (filters.activeOnly) params.set("active_only", "true");
    const values = {
        buying_company_id: selected(filters.company), min_balance: filters.minBalance.trim(), search: filters.search.trim(),
        norm: selected(filters.norm), purchase_status: selected(filters.purchaseStatus),
        purchase_bill: filters.purchaseBill === "ALL" ? "" : filters.purchaseBill,
        purchase_date_from: filters.purchaseDateFrom, purchase_date_to: filters.purchaseDateTo,
        license_numbers: filters.licenseNumbers.trim(),
        exclude_license_numbers: filters.excludeLicenseNumbers.trim(),
    };
    Object.entries(values).forEach(([key, value]) => { if (value) params.set(key, value); });
    return params;
}
