/**
 * Filtering, sorting and paging for the purchase and sale ledger. These run on
 * rows the backend already totalled. They decide which rows are shown and never
 * change a total.
 */
import { compareDecimal } from "./invoiceLedgerFormat";
import type { LedgerColumnId } from "./invoiceLedgerColumns";
import type { LedgerRow, LedgerRowType } from "./types";

export const LEDGER_ROW_TYPES: readonly LedgerRowType[] = ["PURCHASE", "SALE", "CREDIT NOTE", "DEBIT NOTE"];

/** "all" shows every row. "none" shows invoices with no credit or debit note against them. */
export type NoteFilter = "all" | "credit" | "debit" | "none";

export interface LedgerFilters {
  dateFrom: string;
  dateTo: string;
  /** Empty string means every company. */
  company: string;
  types: ReadonlySet<LedgerRowType>;
  particulars: string;
  item: string;
  invoice: string;
  note: NoteFilter;
  /** Empty string means every currency. */
  currency: string;
}

export const DEFAULT_LEDGER_FILTERS: LedgerFilters = {
  dateFrom: "",
  dateTo: "",
  company: "",
  types: new Set(LEDGER_ROW_TYPES),
  particulars: "",
  item: "",
  invoice: "",
  note: "all",
  currency: "",
};

export function isLedgerFilterActive(filters: LedgerFilters): boolean {
  return (
    filters.dateFrom !== "" ||
    filters.dateTo !== "" ||
    filters.company !== "" ||
    filters.types.size !== LEDGER_ROW_TYPES.length ||
    filters.particulars.trim() !== "" ||
    filters.item.trim() !== "" ||
    filters.invoice.trim() !== "" ||
    filters.note !== "all" ||
    filters.currency !== ""
  );
}

/** Number of credit and debit notes that point at each original trade. Counted over the whole ledger. */
export function countNotesByTrade(rows: readonly LedgerRow[]): Map<number, number> {
  const counts = new Map<number, number>();
  for (const row of rows) {
    if (row.type !== "CREDIT NOTE" && row.type !== "DEBIT NOTE") continue;
    const original = row.matched_original?.trade_id;
    if (original === undefined) continue;
    counts.set(original, (counts.get(original) ?? 0) + 1);
  }
  return counts;
}

function containsText(haystack: string, needle: string): boolean {
  return haystack.toLowerCase().includes(needle.trim().toLowerCase());
}

export function rowMatchesFilters(row: LedgerRow, filters: LedgerFilters, notesByTrade: ReadonlyMap<number, number>): boolean {
  if (!filters.types.has(row.type)) return false;
  if (filters.dateFrom && (row.date === null || row.date < filters.dateFrom)) return false;
  if (filters.dateTo && (row.date === null || row.date > filters.dateTo)) return false;
  if (filters.particulars.trim() && !containsText(row.particulars, filters.particulars)) return false;
  if (filters.item.trim() && !containsText(row.items, filters.item)) return false;
  if (filters.invoice.trim() && !containsText(row.invoice, filters.invoice)) return false;
  if (filters.currency && row.source.currency !== filters.currency) return false;
  switch (filters.note) {
    case "credit":
      return row.type === "CREDIT NOTE";
    case "debit":
      return row.type === "DEBIT NOTE";
    case "none":
      return (row.type === "PURCHASE" || row.type === "SALE") && !notesByTrade.get(row.trade_id);
    default:
      return true;
  }
}

export type SortDirection = "asc" | "desc";

export interface LedgerSort {
  key: LedgerColumnId;
  direction: SortDirection;
}

export const DEFAULT_LEDGER_SORT: LedgerSort = { key: "date", direction: "asc" };

const TEXT_COLLATOR = new Intl.Collator("en-IN", { sensitivity: "base", numeric: true });

type DecimalField = "sale_cif" | "purchase_cif" | "sale_bill_inr" | "purchase_bill_inr";

const DECIMAL_SORT_FIELD: Partial<Record<LedgerColumnId, DecimalField>> = {
  sale: "sale_cif",
  purchase: "purchase_cif",
  saleBill: "sale_bill_inr",
  purchaseBill: "purchase_bill_inr",
};

function sortValue(key: LedgerColumnId, row: LedgerRow): string | null {
  switch (key) {
    case "date":
      return row.date;
    case "particulars":
      return row.particulars;
    case "invoice":
      return row.invoice;
    case "type":
      return row.type;
    case "items":
      return row.items;
    default: {
      const field = DECIMAL_SORT_FIELD[key];
      return field ? row[field] : null;
    }
  }
}

function compareValues(key: LedgerColumnId, a: string, b: string): number {
  if (DECIMAL_SORT_FIELD[key] !== undefined) return compareDecimal(a, b);
  if (key === "date") return a < b ? -1 : a > b ? 1 : 0;
  return TEXT_COLLATOR.compare(a, b);
}

/**
 * Sorts a copy of the rows. Empty values always sort last, whichever way the
 * column is sorted, so a blank bill never jumps to the top. Ties fall back to line order.
 */
export function sortLedgerRows(rows: readonly LedgerRow[], sort: LedgerSort): LedgerRow[] {
  const sign = sort.direction === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const left = sortValue(sort.key, a);
    const right = sortValue(sort.key, b);
    if (left === null || right === null) {
      if (left === right) return a.line_id - b.line_id;
      return left === null ? 1 : -1;
    }
    const result = compareValues(sort.key, left, right) * sign;
    return result !== 0 ? result : a.line_id - b.line_id;
  });
}

export const PAGE_SIZES = [10, 25, 50] as const;
export type PageSize = (typeof PAGE_SIZES)[number];

export interface PageWindow {
  page: number;
  totalPages: number;
  start: number;
  end: number;
  /** One-based first and last row shown, or 0 and 0 when there are none. */
  from: number;
  to: number;
}

/** Clamps the page to the rows that exist, so a filter that shrinks the list never leaves the table empty. */
export function pageWindow(total: number, requestedPage: number, pageSize: number): PageWindow {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const page = Math.min(Math.max(1, requestedPage), totalPages);
  const start = (page - 1) * pageSize;
  const end = Math.min(total, start + pageSize);
  return {
    page,
    totalPages,
    start,
    end: start + pageSize,
    from: total === 0 ? 0 : start + 1,
    to: end,
  };
}
