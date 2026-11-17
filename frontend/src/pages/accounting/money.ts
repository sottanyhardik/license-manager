/**
 * Money helpers for the accounting workspace. The API sends amounts as Decimal strings;
 * they are formatted with string arithmetic only (never parsed to float), so ₹ values of any
 * size keep every paise.
 */

export type Money = string;

const ZERO_RE = /^-?0+(\.0+)?$/;

/** "1234567.5" -> "12,34,567.50" (Indian grouping, 2dp). Empty/invalid -> "—". */
export function formatMoney(value: Money | null | undefined, { blankZero = false } = {}): string {
    if (value === null || value === undefined || value === "") return "—";
    const text = String(value).trim();
    if (!/^-?\d+(\.\d+)?$/.test(text)) return "—";
    if (blankZero && ZERO_RE.test(text)) return "";
    const negative = text.startsWith("-");
    const [intRaw, fracRaw = ""] = text.replace("-", "").split(".");
    const frac = (fracRaw + "00").slice(0, 2);
    const intPart = intRaw.replace(/^0+(?=\d)/, "");
    const last3 = intPart.slice(-3);
    const rest = intPart.slice(0, -3);
    const grouped = rest ? `${rest.replace(/\B(?=(\d{2})+(?!\d))/g, ",")},${last3}` : last3;
    const isZero = ZERO_RE.test(text);
    return `${negative && !isZero ? "-" : ""}${grouped}.${frac}`;
}

export function isNegative(value: Money | null | undefined): boolean {
    return typeof value === "string" && value.trim().startsWith("-") && !ZERO_RE.test(value.trim());
}

export function isZero(value: Money | null | undefined): boolean {
    return value === null || value === undefined || value === "" || ZERO_RE.test(String(value).trim());
}

/** Debit-positive balance -> "1,000.00 Dr" / "1,000.00 Cr". */
export function drCr(value: Money | null | undefined): string {
    if (isZero(value)) return "0.00";
    const v = String(value);
    return isNegative(v) ? `${formatMoney(v.slice(1))} Cr` : `${formatMoney(v)} Dr`;
}

/** Exact decimal-string sum (paise integers via BigInt) for client-side footers of server values. */
export function sumMoney(values: Array<Money | null | undefined>): Money {
    let paise = 0n;
    for (const raw of values) {
        if (raw === null || raw === undefined || raw === "") continue;
        const text = String(raw).trim();
        if (!/^-?\d+(\.\d+)?$/.test(text)) continue;
        const negative = text.startsWith("-");
        const [i, f = ""] = text.replace("-", "").split(".");
        const p = BigInt(i) * 100n + BigInt((f + "00").slice(0, 2));
        paise += negative ? -p : p;
    }
    const negative = paise < 0n;
    const abs = negative ? -paise : paise;
    const whole = abs / 100n;
    const cents = (abs % 100n).toString().padStart(2, "0");
    return `${negative ? "-" : ""}${whole}.${cents}`;
}

/** Validates user input as a money string (no float conversion). */
export function isMoneyInput(value: string): boolean {
    return /^\d+(\.\d{1,2})?$/.test(value.trim());
}
