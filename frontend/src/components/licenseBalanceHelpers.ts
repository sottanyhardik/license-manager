const UNSAFE_PATH_SEGMENT_CHARS = new Set(["/", "?", "#", "\\"]);

export function toSafeLicensePathSegment(licenseId: unknown) {
    const value = String(licenseId ?? "").trim();
    const unsafe = [...value].some((char) => {
        const code = char.charCodeAt(0);
        return UNSAFE_PATH_SEGMENT_CHARS.has(char) || code < 32 || code === 127;
    });
    if (!value || unsafe) throw new Error("A valid license id is required.");
    return encodeURIComponent(value);
}
export function buildLicenseEndpoint(licenseId: unknown, suffix = "") { return `licenses/${toSafeLicensePathSegment(licenseId)}/${suffix}`; }
export function formatFiniteDecimal(value: unknown, fractionDigits = 2) { const number = Number(value); return Number.isFinite(number) ? number.toFixed(fractionDigits) : Number(0).toFixed(fractionDigits); }
const normalizeArray = (value: unknown): any[] => Array.isArray(value) ? value : [];
export function normalizeItemOptions(data: any) { return normalizeArray(data?.results).filter((item) => item && item.id != null && item.name != null).map((item) => ({ value: item.id, label: String(item.name) })); }
export function normalizeUsageData(data: any) { return { boes: normalizeArray(data?.boes), allotments: normalizeArray(data?.allotments) }; }
export function normalizeLicenseBalanceData(data: any) { return !data || typeof data !== "object" ? null : { ...data, export_license: normalizeArray(data.export_license), import_license: normalizeArray(data.import_license) }; }
