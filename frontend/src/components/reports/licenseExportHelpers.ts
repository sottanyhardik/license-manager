export const MIN_DAYS = 1;
export const MAX_DAYS = 365;
export function normalizeExportDays(value: unknown, fallback = 30): number {
    const fallbackDays = Number.isFinite(fallback) ? Math.min(MAX_DAYS, Math.max(MIN_DAYS, Math.trunc(fallback))) : 30;
    const parsed = Number.parseInt(String(value), 10);
    return Number.isFinite(parsed) ? Math.min(MAX_DAYS, Math.max(MIN_DAYS, parsed)) : fallbackDays;
}
