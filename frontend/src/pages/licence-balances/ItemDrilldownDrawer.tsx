import { Fragment, useMemo, useState, type ReactNode } from "react";
import { ChevronDown, ChevronRight, Download, ExternalLink } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import LoadErrorPanel from "./LoadErrorPanel";
import { matchesSearch, paginate, sortRows, toCsv, withinDateRange, type DateRange, type DrawerColumn, type SortState } from "./drilldownModel";
import { CIF_DECIMALS, NOT_COMPUTED, QTY_DECIMALS, formatDecimal, formatIsoDate, formatQty, isNegativeDecimal } from "./format";
import { useItemDrilldown } from "./licenceBalanceQueries";
import type {
  AllotmentDrilldownTotals,
  BoeDrilldownTotals,
  Decimal,
  DrilldownAllotmentRow,
  DrilldownBoeRow,
  DrilldownGroup,
  DrilldownInvoiceRow,
  DrilldownReconciliationLine,
  InvoiceDrilldownTotals,
  ItemDrilldown,
} from "./types";

const PAGE_SIZES = [25, 50, 100] as const;
const NOT_RECORDED = "Not recorded";
const NOT_APPLICABLE = "—";
const UNIT_WITHHELD = "Unit unverified";
// The base dialog is a grid, which stretches the body rows over the full height. A flex column keeps the
// header at the top and gives the table all the remaining space.
const DRAWER_CLASS =
  "inset-y-0 right-0 left-auto top-0 flex h-dvh max-h-dvh w-full max-w-[min(100vw,80rem)] translate-x-0 translate-y-0 flex-col gap-0 overflow-hidden rounded-none p-0 sm:max-w-[min(100vw,80rem)]";

interface ItemDrilldownDrawerProps {
  licenceId: number;
  itemId: number;
  group: DrilldownGroup;
  /** The control that opened the drawer. Focus goes back to it on close. */
  returnFocusTo?: HTMLElement | null;
  onClose: () => void;
}

/** A column. Pairs share a `group` heading and always show Quantity first, then CIF. */
type Column<Row> = DrawerColumn<Row> & {
  render: (row: Row) => ReactNode;
  group?: string;
  /** Heading shown under the group heading. Defaults to `label`. */
  subLabel?: string;
};
type AnyRow = DrilldownBoeRow | DrilldownAllotmentRow | DrilldownInvoiceRow;

/** The item's unit as recorded, and whether quantities are withheld because it is not verified. */
interface UnitContext {
  unit: string | null;
  withheld: boolean;
}

const GROUP_TITLE: Record<DrilldownGroup, string> = {
  boes: "BOE Debit Details",
  allotments: "Customer Allotment Details",
  invoices: "Invoice Details",
};

/**
 * Right-side drawer with the rows behind one item's Debited, Allotted or Invoiced figure.
 * Every figure shows its quantity and its CIF together, quantity first. The licence workspace stays
 * underneath: closing returns focus to the figure that opened it.
 */
export default function ItemDrilldownDrawer({ licenceId, itemId, group, returnFocusTo, onClose }: ItemDrilldownDrawerProps) {
  const query = useItemDrilldown(licenceId, itemId, true);
  const itemLabel = query.data ? `SR ${query.data.item.sr}${query.data.item.description ? ` — ${query.data.item.description}` : ""}` : "";

  return (
    <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}>
      <DialogContent
        className={DRAWER_CLASS}
        aria-describedby="drilldown-description"
        onCloseAutoFocus={(event) => {
          if (!returnFocusTo) return;
          event.preventDefault();
          returnFocusTo.focus();
        }}
      >
        <DialogHeader className="border-b px-6 py-4">
          <DialogTitle>{`${GROUP_TITLE[group]} — ${itemLabel || "Item"}`}</DialogTitle>
          <DialogDescription id="drilldown-description">
            Every row contributes to this item's figure. Totals come from the balance report, not from the rows shown.
          </DialogDescription>
        </DialogHeader>
        <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
          {query.isPending ? (
            <p className="p-6 text-sm text-muted-foreground">Loading the source records…</p>
          ) : query.isError ? (
            <div className="p-6">
              <LoadErrorPanel title="The source records could not be loaded." error={query.error} onRetry={() => void query.refetch()} />
            </div>
          ) : (
            <DrilldownBody key={group} payload={query.data} group={group} />
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}

interface DrilldownBodyProps {
  payload: ItemDrilldown;
  group: DrilldownGroup;
}

function DrilldownBody({ payload, group }: DrilldownBodyProps) {
  const withheld = payload.item.unit_status === "UNIT_UNVERIFIED";
  const [query, setQuery] = useState("");
  const [dates, setDates] = useState<DateRange>({ from: "", to: "" });
  const [sort, setSort] = useState<SortState>(null);
  const [pageSize, setPageSize] = useState<(typeof PAGE_SIZES)[number]>(25);
  const [page, setPage] = useState(1);
  const [expanded, setExpanded] = useState<ReadonlySet<string>>(() => new Set());

  const unit = payload.item.unit ?? payload.item.unit_raw;
  const ctx = useMemo<UnitContext>(() => ({ unit, withheld }), [unit, withheld]);
  const config = useMemo(() => configFor(group, ctx), [group, ctx]);
  const rows: AnyRow[] = useMemo(() => {
    if (group === "boes") return payload.boes.rows;
    if (group === "allotments") return payload.allotments.rows;
    return payload.invoices.rows;
  }, [group, payload]);

  const filtered = useMemo(
    () => rows.filter((row) => matchesSearch(config.search(row), query) && withinDateRange(config.date(row), dates)),
    [rows, query, dates, config],
  );
  const sorted = useMemo(() => sortRows(filtered, config.columns, sort), [filtered, config.columns, sort]);
  const { rows: pageRows, page: safePage, pageCount } = paginate(sorted, page, pageSize);

  const toggleSort = (key: string) => {
    setPage(1);
    setSort((current) => {
      if (!current || current.key !== key) return { key, direction: "asc" };
      if (current.direction === "asc") return { key, direction: "desc" };
      return null;
    });
  };
  const toggleRow = (key: string) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  };
  const exportCsv = () => {
    const csv = `\uFEFF${toCsv(config.columns, sorted)}`;
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${payload.item.sr}-${group}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b px-6 py-3">
        {withheld ? (
          <span className="text-xs text-muted-foreground">Quantities are withheld: the unit is not verified.</span>
        ) : null}
        <div className="relative min-w-[14rem] flex-1">
          <Label htmlFor="drilldown-search" className="sr-only">Search rows</Label>
          <Input
            id="drilldown-search"
            type="search"
            placeholder="Search BOE, invoice, customer, status…"
            value={query}
            onChange={(event) => { setQuery(event.target.value); setPage(1); }}
          />
        </div>
        <div className="flex items-center gap-2">
          <Label htmlFor="drilldown-from" className="text-xs text-muted-foreground">From</Label>
          <Input id="drilldown-from" type="date" className="w-40" value={dates.from} onChange={(e) => { setDates({ ...dates, from: e.target.value }); setPage(1); }} />
          <Label htmlFor="drilldown-to" className="text-xs text-muted-foreground">To</Label>
          <Input id="drilldown-to" type="date" className="w-40" value={dates.to} onChange={(e) => { setDates({ ...dates, to: e.target.value }); setPage(1); }} />
        </div>
        <Button variant="outline" size="sm" onClick={exportCsv} disabled={sorted.length === 0}>
          <Download className="size-4" aria-hidden="true" />
          Export CSV
        </Button>
      </div>

      {group === "boes" ? (
        <BoeTotals payload={payload} ctx={ctx} />
      ) : group === "allotments" ? (
        <AllotmentTotals payload={payload} ctx={ctx} />
      ) : (
        <InvoiceTotals payload={payload} ctx={ctx} />
      )}

      <div className="min-h-0 flex-1 overflow-auto px-6 py-3">
        <p className="mb-2 text-xs text-muted-foreground" aria-live="polite">
          {`Showing ${sorted.length} of ${rows.length} rows`}
        </p>
        {rows.length === 0 ? (
          <EmptyMessage group={group} />
        ) : sorted.length === 0 ? (
          <p className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">No rows match the search or dates.</p>
        ) : (
          <table data-testid="drilldown-table" className="w-full min-w-[68rem] border-collapse text-sm">
            <caption className="sr-only">{`${GROUP_TITLE[group]} for SR ${payload.item.sr}, quantity and CIF in USD`}</caption>
            <TableHead columns={config.columns} sort={sort} onSort={toggleSort} />
            <tbody>
              {pageRows.map((row) => {
                const key = config.key(row);
                const isOpen = expanded.has(key);
                return (
                  <Fragment key={key}>
                    <tr className="border-t align-top hover:bg-muted/30">
                      <td className="px-2 py-2">
                        <button
                          type="button"
                          aria-expanded={isOpen}
                          aria-label={`${isOpen ? "Hide" : "Show"} details for ${config.rowLabel(row)}`}
                          onClick={() => toggleRow(key)}
                          className="inline-flex size-7 items-center justify-center rounded-md text-muted-foreground hover:bg-muted hover:text-foreground cursor-pointer"
                        >
                          {isOpen ? <ChevronDown className="size-4" aria-hidden="true" /> : <ChevronRight className="size-4" aria-hidden="true" />}
                        </button>
                      </td>
                      {config.columns.map((column) => (
                        <td key={column.key} className={cn("px-3 py-2", column.align === "right" && "text-right tabular-nums whitespace-nowrap")}>
                          {column.render(row)}
                        </td>
                      ))}
                    </tr>
                    {isOpen ? (
                      <tr className="border-t bg-muted/20">
                        <td colSpan={config.columns.length + 1} className="px-6 py-3">
                          {config.detail(row)}
                        </td>
                      </tr>
                    ) : null}
                  </Fragment>
                );
              })}
            </tbody>
          </table>
        )}
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 border-t px-6 py-3 text-sm">
        <div className="flex items-center gap-2">
          <Label htmlFor="drilldown-page-size" className="text-xs text-muted-foreground">Rows per page</Label>
          <select
            id="drilldown-page-size"
            className="h-8 rounded-md border bg-background px-2 text-sm"
            value={pageSize}
            onChange={(event) => { setPageSize(Number(event.target.value) as (typeof PAGE_SIZES)[number]); setPage(1); }}
          >
            {PAGE_SIZES.map((size) => (
              <option key={size} value={size}>{size}</option>
            ))}
          </select>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" disabled={safePage <= 1} onClick={() => setPage(safePage - 1)}>Previous</Button>
          <span className="text-xs text-muted-foreground" aria-live="polite">{`Page ${safePage} of ${pageCount}`}</span>
          <Button variant="outline" size="sm" disabled={safePage >= pageCount} onClick={() => setPage(safePage + 1)}>Next</Button>
        </div>
      </div>

      <ReconciliationFooter lines={payload.reconciliation.qty} subject="Quantity" />
      <ReconciliationFooter lines={payload.reconciliation.cif} subject="CIF" />
    </div>
  );
}

function EmptyMessage({ group }: { group: DrilldownGroup }) {
  const text = {
    boes: "No BOE debits are recorded for this item.",
    allotments: "No customer allotments are recorded for this item.",
    invoices: "No sales are recorded for this item.",
  }[group];
  return <p className="rounded-md border border-dashed p-6 text-center text-sm text-muted-foreground">{text}</p>;
}

// ---------------------------------------------------------------------------
// Table header: one row for ungrouped columns, two rows when paired columns are present
// ---------------------------------------------------------------------------

function segmentsOf(columns: Column<AnyRow>[]) {
  const segments: { group: string | undefined; columns: Column<AnyRow>[] }[] = [];
  for (const column of columns) {
    const last = segments[segments.length - 1];
    if (last && column.group !== undefined && last.group === column.group) last.columns.push(column);
    else segments.push({ group: column.group, columns: [column] });
  }
  return segments;
}

function TableHead({ columns, sort, onSort }: { columns: Column<AnyRow>[]; sort: SortState; onSort: (key: string) => void }) {
  const grouped = columns.some((column) => column.group !== undefined);
  const span = grouped ? 2 : 1;
  return (
    <thead className="bg-muted/50 text-xs text-muted-foreground">
      <tr>
        <th scope="col" rowSpan={span} className="w-10 px-2 py-2">
          <span className="sr-only">Details</span>
        </th>
        {segmentsOf(columns).map((segment) =>
          segment.group === undefined ? (
            segment.columns.map((column) => (
              <SortableHeader key={column.key} column={column} heading={column.label} rowSpan={span} sort={sort} onSort={onSort} />
            ))
          ) : (
            <th key={`group-${segment.columns[0].key}`} scope="colgroup" colSpan={segment.columns.length} className="px-3 py-2 text-center font-medium">
              {segment.group}
            </th>
          ),
        )}
      </tr>
      {grouped ? (
        <tr>
          {columns
            .filter((column) => column.group !== undefined)
            .map((column) => (
              <SortableHeader key={column.key} column={column} heading={column.subLabel ?? column.label} sort={sort} onSort={onSort} />
            ))}
        </tr>
      ) : null}
    </thead>
  );
}

function SortableHeader({
  column,
  heading,
  rowSpan,
  sort,
  onSort,
}: {
  column: Column<AnyRow>;
  heading: string;
  rowSpan?: number;
  sort: SortState;
  onSort: (key: string) => void;
}) {
  const direction = sort && sort.key === column.key ? sort.direction : null;
  return (
    <th
      scope="col"
      rowSpan={rowSpan}
      aria-sort={direction === "asc" ? "ascending" : direction === "desc" ? "descending" : "none"}
      className={cn("px-3 py-2 align-bottom font-medium", column.align === "right" ? "text-right" : "text-left")}
    >
      <button
        type="button"
        aria-label={`Sort by ${column.label}`}
        onClick={() => onSort(column.key)}
        className="inline-flex items-center gap-1 whitespace-nowrap hover:text-foreground cursor-pointer"
      >
        {heading}
        <span aria-hidden="true">{direction === "asc" ? "▲" : direction === "desc" ? "▼" : ""}</span>
      </button>
    </th>
  );
}

// ---------------------------------------------------------------------------
// Quantity and CIF values
// ---------------------------------------------------------------------------

/** A quantity with its unit. Withheld while the unit is not verified: words, never a figure. */
function QuantityValue({ value, unit, withheld }: { value: Decimal | undefined; unit: string | null; withheld: boolean }) {
  if (withheld) return <span className="text-xs italic text-muted-foreground">{UNIT_WITHHELD}</span>;
  return <span className={cn("tabular-nums", isNegativeDecimal(value) && "text-destructive")}>{formatQty(value, unit)}</span>;
}

function CifValue({ value }: { value: Decimal | undefined }) {
  return <span className={cn("tabular-nums", isNegativeDecimal(value) && "text-destructive")}>{formatDecimal(value, CIF_DECIMALS)}</span>;
}

interface PairedRow {
  label: string;
  qty: Decimal | undefined;
  cif: Decimal | undefined;
  emphasis?: boolean;
}

/** A small table of figures: Quantity column first, CIF second, on every row. */
function PairedValues({ caption, headingLabel, rows, ctx }: { caption: string; headingLabel: string; rows: PairedRow[]; ctx: UnitContext }) {
  return (
    <div className="max-w-full overflow-x-auto">
      <table aria-label={caption} className="w-full min-w-[26rem] max-w-2xl text-sm">
        <thead className="text-xs text-muted-foreground">
          <tr>
            <th scope="col" className="py-1 text-left font-normal">{headingLabel}</th>
            <th scope="col" className="py-1 text-right font-normal">{quantityHeading("Quantity", ctx)}</th>
            <th scope="col" className="py-1 text-right font-normal">CIF (USD)</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className="border-t">
              <th scope="row" className={cn("py-1 text-left font-normal", row.emphasis && "font-semibold")}>{row.label}</th>
              <td className={cn("py-1 text-right", row.emphasis && "font-semibold")}>
                <QuantityValue value={row.qty} unit={ctx.unit} withheld={ctx.withheld} />
              </td>
              <td className={cn("py-1 text-right", row.emphasis && "font-semibold")}>
                <CifValue value={row.cif} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** The unit as recorded goes beside the quantity heading. A withheld unit is labelled, never converted. */
function unitTag(ctx: UnitContext): string | null {
  if (ctx.withheld) return `${ctx.unit ?? "unit not recorded"}, unit not verified`;
  return ctx.unit;
}

function quantityHeading(base: string, ctx: UnitContext): string {
  const tag = unitTag(ctx);
  return tag ? `${base} (${tag})` : base;
}

// ---------------------------------------------------------------------------
// Totals and reconciliation
// ---------------------------------------------------------------------------

function BoeTotals({ payload, ctx }: { payload: ItemDrilldown; ctx: UnitContext }) {
  const t: BoeDrilldownTotals = payload.boes.totals;
  return (
    <section aria-label="Totals" className="border-b bg-muted/20 px-6 py-3 text-sm">
      <p className="mb-2 text-xs text-muted-foreground">
        BOE rows: <span className="font-medium text-foreground">{`${t.boe_rows} counted · ${t.previous_owner_rows} previous-owner`}</span>
      </p>
      <PairedValues
        caption="Totals for BOE debits"
        headingLabel="Figure"
        ctx={ctx}
        rows={[
          { label: "Covered by Sale", qty: t.covered_qty, cif: t.covered_cif },
          { label: "Uncovered BOE Debit (current owner)", qty: t.uncovered_qty, cif: t.uncovered_cif },
          { label: "Over-linked Excess", qty: t.over_linked_qty, cif: t.over_linked_cif },
          { label: "Debited (Item Figure)", qty: t.debited_qty, cif: t.debited_cif, emphasis: true },
          { label: "Previous-owner BOE Debit", qty: t.previous_owner_debit_qty, cif: t.previous_owner_debit_cif },
        ]}
      />
    </section>
  );
}

function AllotmentTotals({ payload, ctx }: { payload: ItemDrilldown; ctx: UnitContext }) {
  const t: AllotmentDrilldownTotals = payload.allotments.totals;
  return (
    <section aria-label="Totals" className="border-b bg-muted/20 px-6 py-3 text-sm">
      <p className="mb-2 text-xs text-muted-foreground">
        {`Allotments: ${t.allotment_rows} counted · ${t.cancelled_rows} cancelled`}
      </p>
      <PairedValues
        caption="Totals for customer allotments"
        headingLabel="Figure"
        ctx={ctx}
        rows={[
          { label: "Original", qty: t.original_qty, cif: t.original_cif },
          { label: "BOE-linked", qty: t.boe_linked_qty, cif: t.boe_linked_cif },
          { label: "Invoice-linked (not recorded)", qty: undefined, cif: undefined },
          { label: "Outstanding (Allotted Figure)", qty: t.outstanding_qty, cif: t.outstanding_cif, emphasis: true },
          { label: "Cancelled (excluded from the balance)", qty: undefined, cif: t.cancelled_cif_excluded },
        ]}
      />
    </section>
  );
}

function InvoiceTotals({ payload, ctx }: { payload: ItemDrilldown; ctx: UnitContext }) {
  const t: InvoiceDrilldownTotals = payload.invoices.totals;
  return (
    <section aria-label="Totals" className="border-b bg-muted/20 px-6 py-3 text-sm">
      <p className="mb-2 text-xs text-muted-foreground">{`Invoices: ${t.invoice_rows} rows`}</p>
      <PairedValues
        caption="Totals for invoices"
        headingLabel="Figure"
        ctx={ctx}
        rows={[
          // Internal sales are shown first, on their own. They are not part of the external figures below.
          { label: "Gross internal sales (INTERNAL TRADE, not external)", qty: t.internal_sold_qty ?? null, cif: t.internal_sold_cif ?? null },
          { label: "Gross external sales", qty: t.sold_qty, cif: t.sold_cif, emphasis: true },
          { label: "External sales covered by BOE", qty: t.covered_by_boe_qty, cif: t.covered_by_boe_cif },
          { label: "External uncovered sales", qty: t.uncovered_qty, cif: t.uncovered_cif },
          { label: "Over-linked", qty: t.over_linked_qty, cif: t.over_linked_cif },
          { label: "Amount contributing to external utilisation", qty: t.sold_qty, cif: t.current_balance_cif },
        ]}
      />
    </section>
  );
}

/** Compares the drawer's own totals with the item table for one measure. */
function ReconciliationFooter({ lines, subject }: { lines: DrilldownReconciliationLine[]; subject: "Quantity" | "CIF" }) {
  const mismatched = lines.some((line) => line.status === "MISMATCH");
  const computed = lines.filter((line) => line.drill !== undefined);
  const summary = mismatched
    ? `${subject} does not match the item table`
    : computed.length === 0
      ? `${subject} not reconciled: unit not verified`
      : `${subject} reconciles to the item table`;
  const decimals = subject === "Quantity" ? QTY_DECIMALS : CIF_DECIMALS;
  return (
    <details className="border-t px-6 py-3 text-sm" open={mismatched}>
      <summary className="cursor-pointer font-medium">{summary}</summary>
      {computed.length > 0 ? (
        <table className="mt-2 w-full max-w-3xl text-xs" data-testid="reconciliation-lines">
          <caption className="sr-only">{`${subject} reconciliation against the item table`}</caption>
          <thead className="text-muted-foreground">
            <tr>
              <th scope="col" className="py-1 text-left font-normal">Figure</th>
              <th scope="col" className="py-1 text-right font-normal">Drawer total</th>
              <th scope="col" className="py-1 text-right font-normal">Item table</th>
              <th scope="col" className="py-1 text-right font-normal">Difference</th>
              <th scope="col" className="py-1 text-left font-normal">Result</th>
            </tr>
          </thead>
          <tbody>
            {computed.map((line) => (
              <tr key={line.field} className="border-t">
                <td className="py-1 capitalize">{line.field}</td>
                <td className="py-1 text-right tabular-nums">{formatDecimal(line.drill, decimals)}</td>
                <td className="py-1 text-right tabular-nums">{formatDecimal(line.item_table, decimals)}</td>
                <td className="py-1 text-right tabular-nums">{formatDecimal(line.difference, decimals)}</td>
                <td className="py-1">{line.status === "RECONCILED" ? "Matches" : line.status === "MISMATCH" ? "MISMATCH" : NOT_COMPUTED}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
    </details>
  );
}

// ---------------------------------------------------------------------------
// Columns, search keys and detail panels per group
// ---------------------------------------------------------------------------

interface GroupConfig<Row> {
  columns: Column<Row>[];
  search: (row: Row) => (string | null | undefined)[];
  date: (row: Row) => string | null;
  key: (row: Row) => string;
  rowLabel: (row: Row) => string;
  detail: (row: Row) => ReactNode;
}

/**
 * The three group configs differ in row type only. The cast is safe: each config is only ever
 * applied to the rows of its own group, selected by the same `group` value.
 */
function configFor(group: DrilldownGroup, ctx: UnitContext): GroupConfig<AnyRow> {
  if (group === "boes") return boeConfig(ctx) as unknown as GroupConfig<AnyRow>;
  if (group === "allotments") return allotmentConfig(ctx) as unknown as GroupConfig<AnyRow>;
  return invoiceConfig(ctx) as unknown as GroupConfig<AnyRow>;
}

function text<Row>(key: string, label: string, value: (row: Row) => string | null): Column<Row> {
  return { key, label, type: "text", value, render: (row) => value(row) ?? NOT_COMPUTED };
}

function date<Row>(key: string, label: string, value: (row: Row) => string | null): Column<Row> {
  return { key, label, type: "date", value, render: (row) => formatIsoDate(value(row)) };
}

interface PairSpec<Row> {
  key: string;
  /** The group heading over both columns, e.g. "Covered by Sale". */
  group: string;
  /** Full labels, used for export headers and sort controls. */
  qtyLabel: string;
  cifLabel: string;
  qty: (row: Row) => Decimal;
  cif: (row: Row) => Decimal;
  /** When false for a row, both cells show a dash (the figure does not apply to that row). */
  applies?: (row: Row) => boolean;
  /** Both cells show "Not recorded" (a link the data model does not have). */
  notRecorded?: boolean;
}

/** Two adjacent columns for one figure: Quantity first, CIF second. */
function pair<Row>(spec: PairSpec<Row>, ctx: UnitContext): Column<Row>[] {
  const tag = unitTag(ctx);
  const qtyLabel = tag ? `${spec.qtyLabel} (${tag})` : spec.qtyLabel;
  const cell = (row: Row, content: () => ReactNode) => {
    if (spec.notRecorded) return <span className="text-muted-foreground">{NOT_RECORDED}</span>;
    if (spec.applies && !spec.applies(row)) return <span className="text-muted-foreground">{NOT_APPLICABLE}</span>;
    return content();
  };
  return [
    {
      key: `${spec.key}-qty`,
      label: qtyLabel,
      subLabel: tag ? `Quantity (${tag})` : "Quantity",
      group: spec.group,
      type: "decimal",
      align: "right",
      value: spec.qty,
      render: (row) => cell(row, () => <QuantityValue value={spec.qty(row)} unit={ctx.unit} withheld={ctx.withheld} />),
    },
    {
      key: `${spec.key}-cif`,
      label: spec.cifLabel,
      subLabel: "CIF (USD)",
      group: spec.group,
      type: "decimal",
      align: "right",
      value: spec.cif,
      render: (row) => cell(row, () => <CifValue value={spec.cif(row)} />),
    },
  ];
}

function boeConfig(ctx: UnitContext): GroupConfig<DrilldownBoeRow> {
  const isBoe = (row: DrilldownBoeRow) => row.kind === "BOE";
  const columns: Column<DrilldownBoeRow>[] = [
    text("boe", "BOE No.", (r) => (r.kind === "BOE" ? r.boe_number : `Excess on ${r.invoice_number}`)),
    date("date", "BOE Date", (r) => r.boe_date),
    text("port", "Port", (r) => r.port || null),
    text("importer", "Importer", (r) => r.importer || null),
    ...pair<DrilldownBoeRow>({ key: "boe", group: "BOE", qtyLabel: "BOE Quantity", cifLabel: "BOE CIF (USD)", qty: (r) => r.boe_qty, cif: (r) => r.boe_cif, applies: isBoe }, ctx),
    ...pair<DrilldownBoeRow>({ key: "covered", group: "Covered by Sale", qtyLabel: "Covered by Sale — Quantity", cifLabel: "Covered by Sale — CIF (USD)", qty: (r) => r.covered_qty, cif: (r) => r.covered_cif, applies: isBoe }, ctx),
    ...pair<DrilldownBoeRow>({ key: "debited", group: "Debited", qtyLabel: "Debited — Quantity", cifLabel: "Debited — CIF (USD)", qty: (r) => r.debited_qty, cif: (r) => r.debited_cif }, ctx),
    text("sale", "Sale / Invoice", (r) => r.sale_links.map((l) => l.invoice_number).join(", ") || r.invoice_number || null),
    text("allotment", "Allotment", (r) => r.allotment_ids.map((id) => `ALLOT-${id}`).join(", ") || null),
    text("status", "Status", (r) => r.status),
  ];
  return {
    columns,
    key: (r) => (r.kind === "BOE" ? `boe-${r.row_id}` : `excess-${r.source.id}`),
    rowLabel: (r) => (r.kind === "BOE" ? `BOE ${r.boe_number}` : `excess on ${r.invoice_number}`),
    search: (r) => [r.boe_number, r.port, r.importer, r.status, r.invoice_number, ...r.sale_links.map((l) => l.invoice_number), ...r.flags],
    date: (r) => r.boe_date,
    detail: (r) => <BoeDetail row={r} ctx={ctx} />,
  };
}

function allotmentConfig(ctx: UnitContext): GroupConfig<DrilldownAllotmentRow> {
  const columns: Column<DrilldownAllotmentRow>[] = [
    text("reference", "Reference", (r) => r.reference),
    date("date", "Allotment date", (r) => r.allotment_date),
    text("customer", "Customer", (r) => r.customer || null),
    ...pair<DrilldownAllotmentRow>({ key: "original", group: "Original", qtyLabel: "Original Quantity", cifLabel: "Original CIF (USD)", qty: (r) => r.original_qty, cif: (r) => r.original_cif }, ctx),
    ...pair<DrilldownAllotmentRow>({ key: "boe-linked", group: "BOE-linked", qtyLabel: "BOE-linked Quantity", cifLabel: "BOE-linked CIF (USD)", qty: (r) => r.boe_linked_qty, cif: (r) => r.boe_linked_cif }, ctx),
    ...pair<DrilldownAllotmentRow>({ key: "invoice-linked", group: "Invoice-linked", qtyLabel: "Invoice-linked Quantity", cifLabel: "Invoice-linked CIF (USD)", qty: (r) => r.invoice_linked_qty, cif: (r) => r.invoice_linked_cif, notRecorded: true }, ctx),
    ...pair<DrilldownAllotmentRow>({ key: "outstanding", group: "Outstanding", qtyLabel: "Outstanding Quantity", cifLabel: "Outstanding CIF (USD)", qty: (r) => r.outstanding_qty, cif: (r) => r.outstanding_cif }, ctx),
    text("status", "Status", (r) => r.status),
  ];
  return {
    columns,
    key: (r) => `allot-${r.allotment_item_id}`,
    rowLabel: (r) => r.reference,
    search: (r) => [r.reference, r.customer, r.status, r.source_status, ...r.linked_boes.map((b) => b.boe_number), ...r.flags],
    date: (r) => r.allotment_date,
    detail: (r) => <AllotmentDetail row={r} ctx={ctx} />,
  };
}

function invoiceConfig(ctx: UnitContext): GroupConfig<DrilldownInvoiceRow> {
  const columns: Column<DrilldownInvoiceRow>[] = [
    text("invoice", "Invoice", (r) => (r.classification === "INTERNAL" ? `${r.invoice_number} · INTERNAL TRADE` : r.invoice_number)),
    text("type", "Type", (r) => r.document_type),
    date("date", "Invoice date", (r) => r.invoice_date),
    text("customer", "Customer", (r) => r.customer || null),
    ...pair<DrilldownInvoiceRow>({ key: "sold", group: "Sold", qtyLabel: "Sold Quantity", cifLabel: "Sold CIF (USD)", qty: (r) => r.sold_qty, cif: (r) => r.sold_cif }, ctx),
    ...pair<DrilldownInvoiceRow>({ key: "covered", group: "Covered by BOE", qtyLabel: "Covered by BOE Quantity", cifLabel: "Covered by BOE CIF (USD)", qty: (r) => r.covered_by_boe_qty, cif: (r) => r.covered_by_boe_cif }, ctx),
    ...pair<DrilldownInvoiceRow>({ key: "uncovered", group: "Uncovered", qtyLabel: "Uncovered Quantity", cifLabel: "Uncovered CIF (USD)", qty: (r) => r.uncovered_qty, cif: (r) => r.uncovered_cif }, ctx),
    ...pair<DrilldownInvoiceRow>({ key: "over", group: "Over-linked", qtyLabel: "Over-linked Quantity", cifLabel: "Over-linked CIF (USD)", qty: (r) => r.over_linked_qty, cif: (r) => r.over_linked_cif }, ctx),
    ...pair<DrilldownInvoiceRow>({ key: "current", group: "In current balance", qtyLabel: "Current balance Quantity", cifLabel: "Current balance CIF (USD)", qty: (r) => r.sold_qty, cif: (r) => r.current_balance_cif }, ctx),
    text("status", "Status", (r) => r.status),
  ];
  return {
    columns,
    key: (r) => `inv-${r.trade_id}`,
    rowLabel: (r) => `invoice ${r.invoice_number}`,
    search: (r) => [r.invoice_number, r.document_type, r.customer, r.status, ...r.linked_boes.map((b) => b.boe_number), ...r.flags],
    date: (r) => r.invoice_date,
    detail: (r) => <InvoiceDetail row={r} ctx={ctx} />,
  };
}

// ---------------------------------------------------------------------------
// Detail panels: linked records, flags and a link to the source record
// ---------------------------------------------------------------------------

const SOURCE_PATHS: Record<string, (id: number) => string> = {
  bill_of_entry: (id) => `/bill-of-entries/${id}/edit`,
  trade: (id) => `/trades/${id}/edit`,
  allotment: (id) => `/allotments/${id}/edit`,
};

/** Opens the source record in a new tab, so the licence workspace stays where it is. */
function SourceLink({ href, label }: { href: string | null; label: string }) {
  if (!href) return null;
  return (
    <a href={href} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-sm text-primary underline-offset-4 hover:underline">
      {label}
      <ExternalLink className="size-3.5" aria-hidden="true" />
    </a>
  );
}

/**
 * Expanded BOE row. Every amount is shown as Quantity then CIF: the BOE, its coverage by sale,
 * its debit, each sale allocation and any over-linked excess. A previous-owner BOE is deducted
 * like any other BOE; its debit is labelled as previous-owner so audit can tell them apart.
 */
function BoeDetail({ row, ctx }: { row: DrilldownBoeRow; ctx: UnitContext }) {
  const href = row.source.id !== null && SOURCE_PATHS[row.source.type] ? SOURCE_PATHS[row.source.type](row.source.id) : null;
  const isExcess = row.kind === "OVER_LINKED_EXCESS";
  const figures: PairedRow[] = isExcess
    ? [
        {
          label: row.previous_owner ? "Over-linked excess — previous owner (counted as debit)" : "Over-linked excess (counted as debit)",
          qty: row.debited_qty,
          cif: row.debited_cif,
          emphasis: true,
        },
      ]
    : [
        { label: "BOE amount", qty: row.boe_qty, cif: row.boe_cif },
        { label: "Covered by sale", qty: row.covered_qty, cif: row.covered_cif },
        row.previous_owner
          ? { label: "Debited: previous-owner BOE (deducted)", qty: row.debited_qty, cif: row.debited_cif, emphasis: true }
          : { label: "Debited (counted in the item figure)", qty: row.debited_qty, cif: row.debited_cif, emphasis: true },
      ];
  return (
    <div className="space-y-3 text-sm">
      {isExcess ? (
        <p>{`Part of invoice ${row.invoice_number} whose linked BOEs exceed its sale amount. This excess is counted as debit on this item.`}</p>
      ) : null}
      {!isExcess && row.previous_owner ? (
        <p className="text-muted-foreground">
          Previous-owner BOE: deducted from Available CIF and quantity, like any other BOE. Ownership comes from the BOE hide/restore record.
        </p>
      ) : null}
      <PairedValues
        caption={isExcess ? "Over-linked excess figures" : `Figures for BOE ${row.boe_number}`}
        headingLabel="Figure"
        rows={figures}
        ctx={ctx}
      />
      {!isExcess && row.sale_links.length === 0 ? <p>No sale is linked to this BOE, so its debit is uncovered.</p> : null}
      {row.sale_links.length > 0 ? (
        <table className="w-full max-w-3xl text-xs" aria-label="Linked sales">
          <thead className="text-muted-foreground">
            <tr>
              <th scope="col" className="py-1 text-left font-normal">Sale / invoice</th>
              <th scope="col" className="py-1 text-right font-normal">{quantityHeading("Linked quantity", ctx)}</th>
              <th scope="col" className="py-1 text-right font-normal">Linked CIF (USD)</th>
              <th scope="col" className="py-1 text-left font-normal">Allocation basis</th>
            </tr>
          </thead>
          <tbody>
            {row.sale_links.map((link) => (
              <tr key={link.trade_id} className="border-t">
                <td className="py-1">{link.invoice_number}</td>
                <td className="py-1 text-right">
                  <QuantityValue value={link.qty} unit={ctx.unit} withheld={ctx.withheld} />
                </td>
                <td className="py-1 text-right">
                  <CifValue value={link.cif} />
                </td>
                <td className="py-1">{link.basis}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : null}
      <FlagList flags={row.flags} />
      <div className="flex flex-wrap gap-4">
        <SourceLink href={href} label={row.kind === "BOE" ? `Open BOE ${row.boe_number}` : `Open invoice ${row.invoice_number}`} />
      </div>
    </div>
  );
}

function AllotmentDetail({ row, ctx }: { row: DrilldownAllotmentRow; ctx: UnitContext }) {
  return (
    <div className="space-y-3 text-sm">
      <PairedValues
        caption={`Figures for ${row.reference}`}
        headingLabel="Figure"
        ctx={ctx}
        rows={[
          { label: "Original", qty: row.original_qty, cif: row.original_cif },
          { label: "BOE-linked", qty: row.boe_linked_qty, cif: row.boe_linked_cif },
          { label: "Outstanding", qty: row.outstanding_qty, cif: row.outstanding_cif, emphasis: true },
        ]}
      />
      {row.linked_boes.length === 0 ? (
        <p>No BOE is linked to this allotment.</p>
      ) : (
        <table className="w-full max-w-3xl text-xs" aria-label="BOEs linked to this allotment">
          <thead className="text-muted-foreground">
            <tr>
              <th scope="col" className="py-1 text-left font-normal">BOE no.</th>
              <th scope="col" className="py-1 text-left font-normal">Date</th>
              <th scope="col" className="py-1 text-right font-normal">{quantityHeading("Debit on this item", ctx)}</th>
              <th scope="col" className="py-1 text-right font-normal">Debit on this item CIF (USD)</th>
              <th scope="col" className="py-1 text-left font-normal">Position</th>
            </tr>
          </thead>
          <tbody>
            {row.linked_boes.map((boe) => (
              <tr key={boe.boe_id} className="border-t">
                <td className="py-1">{boe.boe_number}</td>
                <td className="py-1">{formatIsoDate(boe.boe_date)}</td>
                <td className="py-1 text-right">
                  <QuantityValue value={boe.debit_on_item_qty} unit={ctx.unit} withheld={ctx.withheld} />
                </td>
                <td className="py-1 text-right">
                  <CifValue value={boe.debit_on_item_cif} />
                </td>
                <td className="py-1">{boe.previous_owner ? "Previous owner (deducted)" : boe.on_this_item ? "Debits this item" : "Does not debit this item (review)"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="text-xs text-muted-foreground">No invoice link is recorded for allotments.</p>
      <FlagList flags={row.flags} />
      <SourceLink href={SOURCE_PATHS.allotment(row.allotment_id)} label={`Open allotment ${row.reference}`} />
    </div>
  );
}

/** Why an invoice is INTERNAL, and who authorised it. Shown only for INTERNAL invoices. */
function InternalTradeNote({ row }: { row: DrilldownInvoiceRow }) {
  if (row.classification !== "INTERNAL") return null;
  const authorised = row.classification_authorised_on ? formatIsoDate(row.classification_authorised_on.slice(0, 10)) : null;
  return (
    <div className="rounded-md border border-sky-300 bg-sky-50 p-3 text-xs text-sky-950 dark:border-sky-700 dark:bg-sky-950/40 dark:text-sky-100">
      <p className="font-semibold tracking-wide">INTERNAL TRADE</p>
      <p>Group-company sale. Kept for audit. Not external licence utilisation, and not deleted or reversed.</p>
      {row.classification_reason ? <p>{`Reason: ${row.classification_reason}`}</p> : null}
      {row.classification_authorised_by ? (
        <p>{`Authorised by ${row.classification_authorised_by}${authorised ? ` on ${authorised}` : ""}`}</p>
      ) : null}
    </div>
  );
}

function InvoiceDetail({ row, ctx }: { row: DrilldownInvoiceRow; ctx: UnitContext }) {
  return (
    <div className="space-y-3 text-sm">
      <InternalTradeNote row={row} />
      <PairedValues
        caption={`Figures for invoice ${row.invoice_number}`}
        headingLabel="Figure"
        ctx={ctx}
        rows={[
          { label: "Sold", qty: row.sold_qty, cif: row.sold_cif, emphasis: true },
          { label: "Covered by BOE", qty: row.covered_by_boe_qty, cif: row.covered_by_boe_cif },
          { label: "Uncovered", qty: row.uncovered_qty, cif: row.uncovered_cif },
          { label: "Over-linked", qty: row.over_linked_qty, cif: row.over_linked_cif },
        ]}
      />
      {row.linked_boes.length === 0 ? (
        <p>No BOE is linked to this invoice.</p>
      ) : (
        <table className="w-full max-w-3xl text-xs" aria-label="BOEs linked to this invoice">
          <thead className="text-muted-foreground">
            <tr>
              <th scope="col" className="py-1 text-left font-normal">BOE no.</th>
              <th scope="col" className="py-1 text-left font-normal">Date</th>
              <th scope="col" className="py-1 text-left font-normal">Importer</th>
              <th scope="col" className="py-1 text-right font-normal">{quantityHeading("Linked quantity", ctx)}</th>
              <th scope="col" className="py-1 text-right font-normal">Linked CIF (USD)</th>
              <th scope="col" className="py-1 text-left font-normal">Allocation basis</th>
            </tr>
          </thead>
          <tbody>
            {row.linked_boes.map((boe) => (
              <tr key={boe.row_id} className="border-t">
                <td className="py-1">{boe.boe_number}</td>
                <td className="py-1">{formatIsoDate(boe.boe_date)}</td>
                <td className="py-1">{boe.previous_owner ? `${boe.importer} · previous owner` : boe.importer}</td>
                <td className="py-1 text-right">
                  <QuantityValue value={boe.qty} unit={ctx.unit} withheld={ctx.withheld} />
                </td>
                <td className="py-1 text-right">
                  <CifValue value={boe.cif} />
                </td>
                <td className="py-1">{boe.basis}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      {row.boes_without_debit_on_item.length > 0 ? (
        <p className="text-amber-800 dark:text-amber-200">
          {`Linked to a BOE that does not debit this item (review): ${row.boes_without_debit_on_item.map((b) => b.boe_number).join(", ")}.`}
        </p>
      ) : null}
      <p className="text-xs text-muted-foreground">
        {row.classification === "INTERNAL"
          ? "Not in the external balance. Internal trades do not reduce the licence."
          : row.counts_in_current_balance ? "Counts in the current balance." : "Not in the current balance."}
      </p>
      <FlagList flags={row.flags} />
      <SourceLink href={SOURCE_PATHS.trade(row.trade_id)} label={`Open invoice ${row.invoice_number}`} />
    </div>
  );
}

function FlagList({ flags }: { flags: string[] }) {
  if (flags.length === 0) return null;
  return (
    <ul className="list-disc space-y-1 pl-5 text-xs text-muted-foreground">
      {flags.map((flag) => (
        <li key={flag}>{flag}</li>
      ))}
    </ul>
  );
}
