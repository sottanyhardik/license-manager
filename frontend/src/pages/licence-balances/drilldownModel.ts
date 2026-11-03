/**
 * Pure helpers for the item drill-down drawer: search, date filter, sort, pagination and CSV export.
 *
 * Money stays a decimal string. Sorting compares digits as text, so no float is ever involved and
 * no total is recomputed here. Totals always come from the API.
 */

export interface DrawerColumn<Row> {
  key: string;
  label: string;
  /** `decimal` sorts by exact digits, `date` by ISO date text, `text` by locale collation. */
  type: "text" | "date" | "decimal";
  align?: "left" | "right";
  /** Plain value used for sorting, search and CSV. Null sorts last. */
  value: (row: Row) => string | null;
}

export type SortState = { key: string; direction: "asc" | "desc" } | null;

export interface DateRange {
  from: string;
  to: string;
}

/**
 * Exact comparison of two decimal strings ("-1234.50", "0.005"). Null sorts after every value.
 * Works on the digits, never on a float, so 0.1 + 0.2 style artefacts cannot appear.
 */
export function compareDecimal(a: string | null, b: string | null): number {
  if (a === null || a.trim() === "") return b === null || b.trim() === "" ? 0 : 1;
  if (b === null || b.trim() === "") return -1;
  const left = parseDecimal(a);
  const right = parseDecimal(b);
  if (left.negative !== right.negative) return left.negative ? -1 : 1;
  const magnitude = compareMagnitude(left, right);
  return left.negative ? -magnitude : magnitude;
}

interface ParsedDecimal {
  negative: boolean;
  whole: string;
  fraction: string;
}

function parseDecimal(value: string): ParsedDecimal {
  const trimmed = value.trim();
  const unsigned = trimmed.replace(/^[-+]/, "");
  const [wholePart = "0", fractionPart = ""] = unsigned.split(".");
  const whole = wholePart.replace(/^0+(?=\d)/, "") || "0";
  const fraction = fractionPart.replace(/0+$/, "");
  // "-0.00" is zero, so it must not sort below "0.00".
  const isZero = whole === "0" && fraction === "";
  return { negative: trimmed.startsWith("-") && !isZero, whole, fraction };
}

function compareMagnitude(a: ParsedDecimal, b: ParsedDecimal): number {
  if (a.whole.length !== b.whole.length) return a.whole.length < b.whole.length ? -1 : 1;
  if (a.whole !== b.whole) return a.whole < b.whole ? -1 : 1;
  const width = Math.max(a.fraction.length, b.fraction.length);
  const left = a.fraction.padEnd(width, "0");
  const right = b.fraction.padEnd(width, "0");
  if (left === right) return 0;
  return left < right ? -1 : 1;
}

/** Every whitespace-separated term must appear somewhere in the row's search text (case-insensitive). */
export function matchesSearch(terms: (string | null | undefined)[], query: string): boolean {
  const needles = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (needles.length === 0) return true;
  const haystack = terms.filter((t): t is string => Boolean(t)).join(" ").toLowerCase();
  return needles.every((needle) => haystack.includes(needle));
}

/** ISO dates compare as text. A row without a date is kept only when no bound is set. */
export function withinDateRange(date: string | null, range: DateRange): boolean {
  if (!range.from && !range.to) return true;
  if (!date) return false;
  const day = date.slice(0, 10);
  if (range.from && day < range.from) return false;
  if (range.to && day > range.to) return false;
  return true;
}

export function sortRows<Row>(rows: Row[], columns: DrawerColumn<Row>[], sort: SortState): Row[] {
  if (!sort) return rows;
  const column = columns.find((c) => c.key === sort.key);
  if (!column) return rows;
  const direction = sort.direction === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const left = column.value(a);
    const right = column.value(b);
    if (left === null || right === null) {
      if (left === right) return 0;
      return left === null ? 1 : -1;
    }
    if (column.type === "decimal") return compareDecimal(left, right) * direction;
    if (column.type === "date") return left.localeCompare(right) * direction;
    return left.localeCompare(right, undefined, { numeric: true, sensitivity: "base" }) * direction;
  });
}

export interface Page<Row> {
  rows: Row[];
  page: number;
  pageCount: number;
}

/** Clamps the page to the available range, so a filter that shrinks the list never shows an empty page. */
export function paginate<Row>(rows: Row[], page: number, pageSize: number): Page<Row> {
  const pageCount = Math.max(1, Math.ceil(rows.length / pageSize));
  const safePage = Math.min(Math.max(1, page), pageCount);
  const start = (safePage - 1) * pageSize;
  return { rows: rows.slice(start, start + pageSize), page: safePage, pageCount };
}

/** Quotes a CSV cell and neutralises spreadsheet formulas. Numbers such as "-40.00" are not formulas. */
export function csvCell(value: string | null): string {
  if (value === null) return "";
  const guarded = /^[=+@]|^-(?!\d)/.test(value) ? `'${value}` : value;
  return /[",\r\n]/.test(guarded) ? `"${guarded.replace(/"/g, '""')}"` : guarded;
}

export function toCsv<Row>(columns: DrawerColumn<Row>[], rows: Row[]): string {
  const header = columns.map((c) => csvCell(c.label)).join(",");
  const body = rows.map((row) => columns.map((c) => csvCell(c.value(row))).join(","));
  return [header, ...body].join("\r\n");
}
