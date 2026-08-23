/**
 * Dashboard date formatting deliberately keeps parsing separate from display.
 * API timestamps are ISO instants; a caller may supply the business timezone
 * instead of relying on the browser's local timezone.
 */
export type DashboardDateFormatOptions = {
    /** IANA timezone used by the business UI. Defaults to UTC for deterministic output. */
    timeZone?: string;
    includeTime?: boolean;
};

const dateFormatterCache = new Map<string, Intl.DateTimeFormat>();

function getFormatter(timeZone: string, includeTime: boolean) {
    const key = `${timeZone}:${includeTime ? "datetime" : "date"}`;
    const existing = dateFormatterCache.get(key);
    if (existing) return existing;

    const formatter = new Intl.DateTimeFormat("en-GB", {
        timeZone,
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        ...(includeTime ? { hour: "2-digit", minute: "2-digit", hourCycle: "h23" as const } : {}),
    });
    dateFormatterCache.set(key, formatter);
    return formatter;
}

/**
 * Formats API ISO timestamps safely for Dashboard tables.
 * Null and malformed values are unavailable, never coerced to zero or sliced.
 */
export function formatDashboardDate(
    value: string | Date | null | undefined,
    { timeZone = "UTC", includeTime = false }: DashboardDateFormatOptions = {},
): string {
    if (value == null || value === "") return "—";
    const date = value instanceof Date ? value : new Date(value);
    if (Number.isNaN(date.getTime())) return "—";

    try {
        return getFormatter(timeZone, includeTime).format(date).replace(/\//g, "-").replace(",", "");
    } catch {
        // Invalid IANA timezone should not turn an otherwise valid value into a raw API string.
        return "—";
    }
}
