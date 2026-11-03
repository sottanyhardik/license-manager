/**
 * Display formatting for backend decimal strings.
 *
 * Strings in, strings out. Integer digits are grouped with
 * Intl.NumberFormat('en-IN') applied to a BigInt (exact, no float conversion).
 * Fraction digits are copied verbatim and padded to the requested precision,
 * never rounded. Nothing here adds, subtracts or compares money as numbers.
 */
import type { Decimal } from "./types";

export const CIF_DECIMALS = 2;
export const QTY_DECIMALS = 3;
/** Shown for a null, missing or empty amount. */
export const NOT_COMPUTED = "—";

const DECIMAL_PATTERN = /^(-?)(\d+)(?:\.(\d+))?$/;
const ISO_DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;
const INTEGER_FORMAT = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const DATE_FORMAT = new Intl.DateTimeFormat("en-IN", { day: "2-digit", month: "short", year: "numeric" });

/**
 * Formats a decimal string for display. Unrecognised input is returned
 * unchanged rather than guessed at.
 */
export function formatDecimal(value: Decimal | undefined, decimals: number): string {
  if (value === null || value === undefined || value.trim() === "") return NOT_COMPUTED;
  const match = DECIMAL_PATTERN.exec(value.trim());
  if (!match) return value;
  const [, sign, integerDigits, fraction = ""] = match;
  const grouped = INTEGER_FORMAT.format(BigInt(integerDigits));
  const digits = fraction.length >= decimals ? fraction : fraction.padEnd(decimals, "0");
  return `${sign}${grouped}${digits ? `.${digits}` : ""}`;
}

/** CIF amount, 2 decimals (the caller adds the USD context, e.g. in the column header). */
export function formatCif(value: Decimal | undefined): string {
  return formatDecimal(value, CIF_DECIMALS);
}

/** Quantity amount, 3 decimals, with the unit from the payload when present. */
export function formatQty(value: Decimal | undefined, unit?: string | null): string {
  const number = formatDecimal(value, QTY_DECIMALS);
  if (number === NOT_COMPUTED || !unit) return number;
  return `${number} ${unit}`;
}

/** True only for a strictly negative amount (a leading minus on a non-zero value). */
export function isNegativeDecimal(value: Decimal | undefined): boolean {
  return value !== null && value !== undefined && /^\s*-/.test(value) && /[1-9]/.test(value);
}

/** True for a zero amount in any spelling ("0", "0.00", "-0.000"). Empty or non-decimal text is not zero. */
export function isZeroDecimal(value: Decimal | undefined): boolean {
  if (value === null || value === undefined || value.trim() === "") return false;
  return /^\s*-?0*(\.0*)?\s*$/.test(value) && /\d/.test(value);
}

/**
 * Compares two decimal strings by their canonical digits, so "100.5" and
 * "100.50" match and "-0.00" equals "0". Strings are never converted to numbers.
 */
export function sameDecimal(a: Decimal | undefined, b: Decimal | undefined): boolean {
  const left = canonicalDecimal(a);
  return left !== null && left === canonicalDecimal(b);
}

function canonicalDecimal(value: Decimal | undefined): string | null {
  if (value === null || value === undefined) return null;
  const match = DECIMAL_PATTERN.exec(value.trim());
  if (!match) return null;
  const [, sign, integerDigits, fraction = ""] = match;
  const integer = integerDigits.replace(/^0+(?=\d)/, "");
  const trimmedFraction = fraction.replace(/0+$/, "");
  const isZero = integer === "0" && trimmedFraction === "";
  return `${sign && !isZero ? "-" : ""}${integer}${trimmedFraction ? `.${trimmedFraction}` : ""}`;
}

/** Formats an integer count (e.g. the number of licences). */
export function formatCount(count: number): string {
  return INTEGER_FORMAT.format(count);
}

/** Formats an ISO `YYYY-MM-DD` date as `31 Dec 2026`, without a timezone shift. */
export function formatIsoDate(value: string | null | undefined): string {
  if (!value) return NOT_COMPUTED;
  const match = ISO_DATE_PATTERN.exec(value);
  if (!match) return value;
  const [, year, month, day] = match;
  return DATE_FORMAT.format(new Date(Number(year), Number(month) - 1, Number(day)));
}
