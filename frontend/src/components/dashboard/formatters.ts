import { formatDashboardDate } from "@/utils/dashboardDate";

/** Shown wherever a value is missing or not computed. Never shown as 0. */
export const UNAVAILABLE = "—";

export type MoneyUnit = "cif" | "invoice";

const MONEY_LOCALE: Record<MoneyUnit, { locale: string; symbol: string }> = {
    cif: { locale: "en-US", symbol: "$" },
    invoice: { locale: "en-IN", symbol: "₹" },
};

/**
 * Formats a decimal string from the API. `cif` is foreign currency (USD for most
 * rows); `invoice` is INR. Values are displayed as received, never converted.
 */
export function formatMoney(value: string | number | null | undefined, unit: MoneyUnit = "cif"): string {
    if (value == null || value === "") return UNAVAILABLE;
    const number = typeof value === "number" ? value : Number(value);
    if (!Number.isFinite(number)) return UNAVAILABLE;
    const { locale, symbol } = MONEY_LOCALE[unit];
    const formatted = new Intl.NumberFormat(locale, {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2,
    }).format(Math.abs(number));
    return `${number < 0 ? "−" : ""}${symbol}${formatted}`;
}

export function formatCount(value: number | null | undefined): string {
    if (value == null || !Number.isFinite(value)) return UNAVAILABLE;
    return value.toLocaleString("en-US");
}

export function formatQuantity(value: string | number | null | undefined): string {
    if (value == null || value === "") return UNAVAILABLE;
    const number = Number(value);
    if (!Number.isFinite(number)) return UNAVAILABLE;
    return number.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

/** `committed_pct` arrives already computed (2 dp). Null means the base is zero. */
export function formatPercent(value: number | null | undefined): string {
    if (value == null || !Number.isFinite(value)) return UNAVAILABLE;
    return `${value.toFixed(2)}%`;
}

/** Date-only values as `dd-mm-yyyy` (UTC, matching the API's date fields). */
export function formatDate(value: string | null | undefined): string {
    return formatDashboardDate(value);
}

/** Timestamps as `dd-mm-yyyy HH:MM` in UTC. */
export function formatDateTime(value: string | null | undefined): string {
    return formatDashboardDate(value, { includeTime: true });
}

/** Local clock time for the client-side "last refreshed" stamp. */
export function formatClockTime(value: Date | null): string {
    if (!value) return UNAVAILABLE;
    return new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(value);
}

/** Days to expiry as the compact label used in tables. */
export function formatDaysToExpiry(days: number | null | undefined): string {
    if (days == null || !Number.isFinite(days)) return UNAVAILABLE;
    if (days < 0) return "Expired";
    if (days === 0) return "Today";
    return `${days} d`;
}
