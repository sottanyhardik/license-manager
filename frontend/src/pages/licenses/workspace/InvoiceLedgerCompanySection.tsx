import { useId, useMemo, useState, type ReactNode } from "react";
import { ArrowDown, ArrowUp, ArrowUpDown, Building2, ChevronDown, ChevronRight, TriangleAlert } from "lucide-react";
import { cn } from "@/lib/utils";
import { formatCifAmount, formatInrAmount, formatLedgerDate, LEDGER_EMPTY } from "./invoiceLedgerFormat";
import type { LedgerColumn, LedgerColumnId } from "./invoiceLedgerColumns";
import {
  DEFAULT_LEDGER_SORT,
  PAGE_SIZES,
  pageWindow,
  sortLedgerRows,
  type LedgerSort,
  type PageSize,
} from "./invoiceLedgerModel";
import type { Decimal } from "@/pages/licence-balances/types";
import type { LedgerRow, LedgerRowType } from "./types";

const DEFAULT_PAGE_SIZE: PageSize = 10;

const NOTE_TYPES: ReadonlySet<LedgerRowType> = new Set(["CREDIT NOTE", "DEBIT NOTE"]);
/** Statuses that need no attention. Anything else is shown with a warning icon and its text. */
const SETTLED_STATUSES: ReadonlySet<string> = new Set(["OK", "MATCHED TO ORIGINAL"]);

interface InvoiceLedgerCompanySectionProps {
  company: string;
  balance: Decimal;
  currency: string;
  rows: LedgerRow[];
  columns: LedgerColumn[];
  filtersActive: boolean;
  selectedLineId: number | null;
  onOpenRow: (row: LedgerRow, trigger: HTMLButtonElement) => void;
}

/** One company's header bar, sortable and paged table. Each company keeps its own sort, page and expanded state. */
export default function InvoiceLedgerCompanySection({
  company,
  balance,
  currency,
  rows,
  columns,
  filtersActive,
  selectedLineId,
  onOpenRow,
}: InvoiceLedgerCompanySectionProps) {
  const headerId = useId();
  const regionId = useId();
  const [expanded, setExpanded] = useState(true);
  const [sort, setSort] = useState<LedgerSort>(DEFAULT_LEDGER_SORT);
  const [pageSize, setPageSize] = useState<PageSize>(DEFAULT_PAGE_SIZE);
  const [requestedPage, setRequestedPage] = useState(1);

  const sorted = useMemo(() => sortLedgerRows(rows, sort), [rows, sort]);
  const page = pageWindow(rows.length, requestedPage, pageSize);
  const pageRows = sorted.slice(page.start, page.end);

  const toggleSort = (key: LedgerColumnId) => {
    setSort((current) =>
      current.key === key
        ? { key, direction: current.direction === "asc" ? "desc" : "asc" }
        : { key, direction: "asc" },
    );
    setRequestedPage(1);
  };

  return (
    <section className="min-w-0 overflow-hidden rounded-xl border bg-card shadow-sm">
      <button
        id={headerId}
        type="button"
        aria-expanded={expanded}
        aria-controls={regionId}
        onClick={() => setExpanded((value) => !value)}
        className="flex w-full items-center justify-between gap-3 bg-blue-700 px-4 py-2.5 text-left text-sm font-semibold text-white outline-none hover:bg-blue-800 focus-visible:ring-[3px] focus-visible:ring-inset focus-visible:ring-white/70 dark:bg-blue-800 dark:hover:bg-blue-900"
      >
        <span className="flex min-w-0 items-center gap-2">
          <Building2 aria-hidden="true" className="size-4 shrink-0" />
          <span className="truncate">{company}</span>
          {expanded ? (
            <ChevronDown aria-hidden="true" className="size-4 shrink-0" />
          ) : (
            <ChevronRight aria-hidden="true" className="size-4 shrink-0" />
          )}
        </span>
        <span className="shrink-0 font-medium tabular-nums">{`Balance: ${formatCifAmount(balance)} ${currency}`}</span>
      </button>

      <div id={regionId} role="region" aria-labelledby={headerId}>
        {expanded && (
          <>
            <div className="max-h-[28rem] overflow-auto">
              <table className="w-full min-w-[56rem] border-collapse text-sm">
                <caption className="sr-only">{`Purchase and sale rows for ${company}`}</caption>
                <thead className="sticky top-0 z-10 bg-muted text-xs text-muted-foreground">
                  <tr>
                    {columns.map((column) => {
                      const active = sort.key === column.id;
                      return (
                        <th
                          key={column.id}
                          scope="col"
                          aria-sort={active ? (sort.direction === "asc" ? "ascending" : "descending") : "none"}
                          className={cn("px-3 py-2 font-medium", column.numeric ? "text-right" : "text-left")}
                        >
                          <button
                            type="button"
                            onClick={() => toggleSort(column.id)}
                            className={cn(
                              "inline-flex items-center gap-1 rounded-sm font-medium text-muted-foreground outline-none hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/40",
                              column.numeric && "flex-row-reverse",
                              active && "text-foreground",
                            )}
                          >
                            <span>{column.label}</span>
                            <SortIcon active={active} direction={sort.direction} />
                          </button>
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {pageRows.length === 0 && (
                    <tr>
                      <td colSpan={columns.length} className="px-3 py-6 text-center text-muted-foreground">
                        {filtersActive ? "No rows match the current filters." : "No rows for this company."}
                      </td>
                    </tr>
                  )}
                  {pageRows.map((row) => (
                    <LedgerRowLine
                      key={row.line_id}
                      row={row}
                      columns={columns}
                      selected={row.line_id === selectedLineId}
                      onOpen={onOpenRow}
                    />
                  ))}
                </tbody>
              </table>
            </div>

            <div className="flex flex-wrap items-center justify-between gap-3 border-t px-3 py-2 text-sm">
              <label className="inline-flex items-center gap-2 text-muted-foreground">
                <span>Rows per page</span>
                <select
                  aria-label={`Rows per page for ${company}`}
                  value={pageSize}
                  onChange={(event) => {
                    setPageSize(Number(event.target.value) as PageSize);
                    setRequestedPage(1);
                  }}
                  className="h-8 cursor-pointer rounded-md border border-input bg-card px-2 text-sm text-foreground outline-none focus-visible:ring-[3px] focus-visible:ring-ring/40"
                >
                  {PAGE_SIZES.map((size) => (
                    <option key={size} value={size}>
                      {size}
                    </option>
                  ))}
                </select>
              </label>
              <p className="text-muted-foreground tabular-nums">
                {`Showing ${page.from}–${page.to} of ${rows.length}`}
              </p>
              <div className="flex items-center gap-2">
                <PagerButton
                  label={`Previous page for ${company}`}
                  disabled={page.page <= 1}
                  onClick={() => setRequestedPage(page.page - 1)}
                >
                  Previous
                </PagerButton>
                <span className="text-muted-foreground tabular-nums">
                  {`Page ${page.page} of ${page.totalPages}`}
                </span>
                <PagerButton
                  label={`Next page for ${company}`}
                  disabled={page.page >= page.totalPages}
                  onClick={() => setRequestedPage(page.page + 1)}
                >
                  Next
                </PagerButton>
              </div>
            </div>
          </>
        )}
      </div>
    </section>
  );
}

function SortIcon({ active, direction }: { active: boolean; direction: LedgerSort["direction"] }) {
  if (!active) return <ArrowUpDown aria-hidden="true" className="size-3.5 opacity-50" />;
  return direction === "asc" ? (
    <ArrowUp aria-hidden="true" className="size-3.5" />
  ) : (
    <ArrowDown aria-hidden="true" className="size-3.5" />
  );
}

function PagerButton({
  label,
  disabled,
  onClick,
  children,
}: {
  label: string;
  disabled: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      disabled={disabled}
      onClick={onClick}
      className="h-8 rounded-md border bg-card px-3 text-sm font-medium outline-none hover:bg-muted focus-visible:ring-[3px] focus-visible:ring-ring/40 disabled:cursor-not-allowed disabled:opacity-50"
    >
      {children}
    </button>
  );
}

function LedgerRowLine({
  row,
  columns,
  selected,
  onOpen,
}: {
  row: LedgerRow;
  columns: LedgerColumn[];
  selected: boolean;
  onOpen: (row: LedgerRow, trigger: HTMLButtonElement) => void;
}) {
  const isSale = row.type === "SALE";
  const needsReview = !SETTLED_STATUSES.has(row.status);
  return (
    <tr
      data-line-id={row.line_id}
      data-needs-review={needsReview ? "true" : undefined}
      className={cn(
        "border-t align-top",
        isSale && "bg-destructive/5",
        selected && "bg-accent/60 ring-1 ring-inset ring-ring/60",
      )}
    >
      {columns.map((column) => (
        <LedgerCell key={column.id} columnId={column.id} row={row} onOpen={onOpen} />
      ))}
    </tr>
  );
}

function LedgerCell({
  columnId,
  row,
  onOpen,
}: {
  columnId: LedgerColumnId;
  row: LedgerRow;
  onOpen: (row: LedgerRow, trigger: HTMLButtonElement) => void;
}) {
  switch (columnId) {
    case "date":
      return <td className="px-3 py-2 whitespace-nowrap tabular-nums">{formatLedgerDate(row.date)}</td>;
    case "particulars":
      return <td className="min-w-[12rem] px-3 py-2">{row.particulars}</td>;
    case "invoice":
      return (
        <td className="min-w-[12rem] px-3 py-2">
          <button
            type="button"
            onClick={(event) => onOpen(row, event.currentTarget)}
            className="text-left font-medium break-all text-primary underline-offset-4 outline-none hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/40"
          >
            {row.invoice}
          </button>
          {row.classification === "INTERNAL" ? (
            <span className="mt-1 inline-block rounded-full border border-sky-300 bg-sky-50 px-2 py-0.5 text-xs font-semibold tracking-wide text-sky-900 dark:border-sky-700 dark:bg-sky-950/40 dark:text-sky-100">
              INTERNAL TRADE
            </span>
          ) : null}
          {row.counterpart ? (
            <p className="mt-1 text-xs text-muted-foreground">
              {row.transaction_class === "INTERNAL_TRANSFER_PURCHASE" ? "Internal transfer purchase" : "Internal transfer sale"}
              {" · "}counterpart {row.counterpart.invoice} ({row.counterpart.direction.toLowerCase()}, trade {row.counterpart.trade_id})
            </p>
          ) : null}
          {row.transaction_class === "UNMATCHED_INTERNAL_TRANSACTION" ? (
            <span className="mt-1 inline-block rounded-full border border-amber-300 bg-amber-50 px-2 py-0.5 text-xs font-semibold tracking-wide text-amber-900">
              UNMATCHED INTERNAL — REVIEW
            </span>
          ) : null}
          {!SETTLED_STATUSES.has(row.status) && (
            <p className="mt-1 flex items-start gap-1 text-xs font-medium text-foreground">
              <TriangleAlert aria-hidden="true" className="mt-px size-3.5 shrink-0 text-warning" />
              <span>{row.status}</span>
            </p>
          )}
        </td>
      );
    case "type":
      return (
        <td className="px-3 py-2">
          <TypePill type={row.type} />
          {NOTE_TYPES.has(row.type) && <p className="mt-1 text-xs text-muted-foreground">{row.effect}</p>}
        </td>
      );
    case "items":
      return <td className="min-w-[8rem] px-3 py-2">{row.items}</td>;
    case "sale":
      return <AmountTd value={row.sale_cif} format={formatCifAmount} tone="sale" />;
    case "purchase":
      return <AmountTd value={row.purchase_cif} format={formatCifAmount} tone="purchase" />;
    case "saleBill":
      return <AmountTd value={row.sale_bill_inr} format={formatInrAmount} tone="sale" />;
    case "purchaseBill":
      return <AmountTd value={row.purchase_bill_inr} format={formatInrAmount} tone="purchase" />;
    default:
      return null;
  }
}

/** Sale amounts read red and purchase amounts green. A negative (credit) value keeps its minus sign. */
function AmountTd({
  value,
  format,
  tone,
}: {
  value: Decimal;
  format: (value: Decimal) => string;
  tone: "sale" | "purchase";
}) {
  const text = format(value);
  const empty = text === LEDGER_EMPTY;
  return (
    <td
      className={cn(
        "px-3 py-2 text-right whitespace-nowrap tabular-nums",
        empty ? "text-muted-foreground" : tone === "sale" ? "text-destructive" : "text-success",
      )}
    >
      {text}
    </td>
  );
}

function TypePill({ type }: { type: LedgerRowType }) {
  const isNote = NOTE_TYPES.has(type);
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium whitespace-nowrap",
        isNote ? "border-dashed border-warning bg-warning/10 text-foreground" : "border-border text-foreground",
      )}
    >
      {type}
    </span>
  );
}
