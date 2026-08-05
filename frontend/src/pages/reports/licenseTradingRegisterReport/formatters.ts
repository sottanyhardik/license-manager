import { formatIndianNumber } from "@/utils/numberFormatter";

/** Numbers arrive as Decimal-safe strings from the API — never assume a
 * plain JS number, always parse defensively before formatting/arithmetic
 * (same convention as the sibling Purchase & Profit Report). */
export function toNum(value: unknown): number {
    const num = Number(value);
    return Number.isFinite(num) ? num : 0;
}

export function money(value: unknown): string {
    return formatIndianNumber(toNum(value), 2);
}

export function qty(value: unknown, decimals = 3): string {
    return formatIndianNumber(toNum(value), decimals);
}

export function pct(value: unknown): string {
    return `${formatIndianNumber(toNum(value), 2)}%`;
}

/**
 * Running-profit formatting for the Transaction Register: negative values
 * render parenthesized (no minus sign), e.g. `(₹13,13,305)`; non-negative
 * values render as a plain rupee amount, e.g. `₹57,35,943`.
 * `formatIndianNumber` itself has no parens-for-negative mode, so this
 * wraps it rather than changing the shared helper (which 5+ other reports
 * depend on for plain signed formatting).
 */
export function formatSignedRupees(value: unknown, decimals = 0): string {
    const num = toNum(value);
    const abs = formatIndianNumber(Math.abs(num), decimals);
    return num < 0 ? `(₹${abs})` : `₹${abs}`;
}
