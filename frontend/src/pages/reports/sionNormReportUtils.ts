type SionReportFilters = { is_expired: string; is_null: string; sion_norm: string };
const BOOLEAN_FILTER_VALUES = new Set(["False", "True"]);
export const normalizeBooleanFilter = (value: unknown, fallback = "False") => {
    const normalized = String(value ?? "").trim();
    return BOOLEAN_FILTER_VALUES.has(normalized) ? normalized : fallback;
};
export function formatReportNumber(value: unknown, decimals = 2): string {
    if (value === null || value === undefined || value === "") return "—";
    const parsed = Number(value); if (!Number.isFinite(parsed)) return "—";
    const fractionDigits = Number.isInteger(decimals) && decimals >= 0 && decimals <= 6 ? decimals : 2;
    return parsed.toLocaleString("en-IN", { minimumFractionDigits: fractionDigits, maximumFractionDigits: fractionDigits });
}
export const buildSionReportPath = (filters: SionReportFilters) => `licenses/active-dfia-report/?${new URLSearchParams({ is_expired: normalizeBooleanFilter(filters.is_expired), is_null: normalizeBooleanFilter(filters.is_null), sion_norm: String(filters.sion_norm ?? "").trim() }).toString()}`;
export const getSionReportGroups = (data: unknown): any[] => data && typeof data === "object" && "groups" in data && Array.isArray(data.groups) ? data.groups : [];
