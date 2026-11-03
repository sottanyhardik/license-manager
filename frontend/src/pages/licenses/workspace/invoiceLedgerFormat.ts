/**
 * Display formatting and exact ordering for the purchase and sale ledger.
 *
 * Strings in, strings out. Integer digits are grouped with Intl.NumberFormat
 * applied to a BigInt, so large values are never rounded through a float.
 * Fraction digits are copied verbatim (padded to the minimum, never rounded).
 * Nothing here adds, subtracts or converts money.
 */
import type { Decimal } from "@/pages/licence-balances/types";
import type { LedgerRow } from "./types";

/** Shown for a null or empty amount or date. An en dash, never a zero. */
export const LEDGER_EMPTY = "–";

const DECIMAL_PATTERN = /^(-?)(\d+)(?:\.(\d+))?$/;
const ISO_DATE_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;

/** CIF uses thousands separators, as the backend stores it. */
const CIF_INTEGER = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });
/** INR uses Indian grouping (1,02,344.00). */
const INR_INTEGER = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });

interface ParsedDecimal {
  sign: string;
  integer: string;
  fraction: string;
}

function parseDecimal(value: string): ParsedDecimal | null {
  const match = DECIMAL_PATTERN.exec(value.trim());
  if (!match) return null;
  const [, sign, integer, fraction = ""] = match;
  return { sign, integer, fraction };
}

function isBlank(value: Decimal | undefined): value is null | undefined | "" {
  return value === null || value === undefined || value.trim() === "";
}

function groupDecimal(value: string, format: Intl.NumberFormat, minFraction: number): string {
  const parts = parseDecimal(value);
  if (!parts) return value;
  const grouped = format.format(BigInt(parts.integer));
  const fraction = parts.fraction.length >= minFraction ? parts.fraction : parts.fraction.padEnd(minFraction, "0");
  return `${parts.sign}${grouped}${fraction ? `.${fraction}` : ""}`;
}

/** A CIF amount with thousands separators and at least two decimals. Negative values keep their sign. */
export function formatCifAmount(value: Decimal | undefined): string {
  if (isBlank(value)) return LEDGER_EMPTY;
  return groupDecimal(value, CIF_INTEGER, 2);
}

/** An INR amount in Indian grouping with two decimals, e.g. 1,02,344.00. */
export function formatInrAmount(value: Decimal | undefined): string {
  if (isBlank(value)) return LEDGER_EMPTY;
  return groupDecimal(value, INR_INTEGER, 2);
}

/** An exchange rate exactly as stored. Shown only when present. */
export function formatExchangeRate(value: Decimal | undefined): string {
  return isBlank(value) ? LEDGER_EMPTY : value;
}

/** ISO `YYYY-MM-DD` as `DD-MM-YYYY`, matching the licence register. Anything else is shown as received. */
export function formatLedgerDate(value: string | null | undefined): string {
  if (!value) return LEDGER_EMPTY;
  const match = ISO_DATE_PATTERN.exec(value);
  if (!match) return value;
  const [, year, month, day] = match;
  return `${day}-${month}-${year}`;
}

/** The one currency shared by every row, or null when the rows use several (or none). */
export function uniqueCurrency(rows: readonly LedgerRow[]): string | null {
  const currencies = new Set(rows.map((row) => row.source.currency).filter((code) => code.trim() !== ""));
  return currencies.size === 1 ? [...currencies][0] : null;
}

interface MagnitudeParts {
  negative: boolean;
  /** Integer digits without leading zeros ("0" for zero). */
  integer: string;
  /** Fraction digits without trailing zeros. */
  fraction: string;
}

function canonical(value: Decimal): MagnitudeParts | null {
  if (isBlank(value)) return null;
  const parts = parseDecimal(value);
  if (!parts) return null;
  const integer = parts.integer.replace(/^0+(?=\d)/, "");
  const fraction = parts.fraction.replace(/0+$/, "");
  const isZero = integer === "0" && fraction === "";
  return { negative: parts.sign === "-" && !isZero, integer, fraction };
}

/**
 * Orders two decimal strings exactly. Null or non-decimal values sort after
 * every number. Strings are compared digit by digit and never converted to
 * floats, so "100.5" and "100.50" are equal and "-0.00" equals "0".
 */
export function compareDecimal(a: Decimal, b: Decimal): number {
  const left = canonical(a);
  const right = canonical(b);
  if (!left && !right) return 0;
  if (!left) return 1;
  if (!right) return -1;
  if (left.negative !== right.negative) return left.negative ? -1 : 1;
  const magnitude = compareMagnitude(left, right);
  return left.negative ? -magnitude : magnitude;
}

function compareMagnitude(left: MagnitudeParts, right: MagnitudeParts): number {
  if (left.integer.length !== right.integer.length) return left.integer.length < right.integer.length ? -1 : 1;
  if (left.integer !== right.integer) return left.integer < right.integer ? -1 : 1;
  const width = Math.max(left.fraction.length, right.fraction.length);
  const leftFraction = left.fraction.padEnd(width, "0");
  const rightFraction = right.fraction.padEnd(width, "0");
  if (leftFraction === rightFraction) return 0;
  return leftFraction < rightFraction ? -1 : 1;
}
