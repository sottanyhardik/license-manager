import { Fragment, useState } from "react";
import { ChevronDown, ChevronRight, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import BalanceAmount, { type AmountField } from "./BalanceAmount";
import ItemDrilldownDrawer from "./ItemDrilldownDrawer";
import { formatDecimal, NOT_COMPUTED, CIF_DECIMALS } from "./format";
import { StatusReasonsButton } from "./StatusPill";
import { useItemDrilldown } from "./licenceBalanceQueries";
import type { BalanceBlock, DrilldownGroup, DrilldownMeasure, ItemRow } from "./types";

interface ItemBalanceTableProps {
  licenceId: number;
  items: ItemRow[];
  onOpenLedger: (itemId: number) => void;
}

/** Each figure group is a quantity column, then a CIF column: quantity always comes first. */
const GROUPS: { field: AmountField; label: string }[] = [
  { field: "original", label: "Original" },
  { field: "debited", label: "Used through BOEs" },
  { field: "allotted", label: "Reserved for Customers" },
  { field: "invoiced", label: "Invoiced" },
  { field: "available", label: "Available" },
];

/** The three figures that open a source drawer. Original and Available are not drill-down figures. */
const DRILLABLE: Partial<Record<AmountField, { group: DrilldownGroup; name: string }>> = {
  debited: { group: "boes", name: "BOE debit details" },
  allotted: { group: "allotments", name: "customer allotment details" },
  invoiced: { group: "invoices", name: "invoice details" },
};

/** SR, Item, HS Code, Unit, five quantity and CIF pairs, CIF Control, Status. The expand control sits in the SR cell. */
const COLUMN_COUNT = 4 + GROUPS.length * 2 + 2;
const CELL = "px-3 py-1.5 align-top";
const GROUP_CELL = "px-3 py-1.5 text-right align-top";

interface OpenDrill {
  itemId: number;
  group: DrilldownGroup;
  /** The control that opened the drawer. Focus returns to it when the drawer closes. */
  opener: HTMLElement | null;
}

function detailsId(itemId: number) {
  return `item-${itemId}-details`;
}

function hasFigure(block: BalanceBlock | undefined, field: AmountField, kind: DrilldownMeasure, unitUnverified: boolean) {
  if (kind === "qty" && (unitUnverified || block?.status === "UNIT_UNVERIFIED")) return false;
  const value = block?.[field];
  return value !== null && value !== undefined && value.trim() !== "";
}

/**
 * The Available CIF a row displays. Under licence-level control it is the licence's own balance, which the
 * backend sends to every row. It is one figure and is never summed. Under item-level control it is the item's own.
 */
function displayedAvailableCif(item: ItemRow): BalanceBlock {
  if (item.cif_control !== "LICENCE" || item.available_cif_display === undefined) return item.cif;
  return { status: item.cif.status, available: item.available_cif_display, is_over_utilised: false };
}

function CifControlCell({ item }: { item: ItemRow }) {
  if (item.cif_control === "LICENCE") {
    return (
      <span
        className="whitespace-nowrap text-xs"
        title="The licence's available CIF is shown on every row. Item CIF is attribution, not a limit."
      >
        Licence-level CIF control
      </span>
    );
  }
  if (item.cif_control === "ITEM") return <span className="whitespace-nowrap text-xs">Individual item CIF</span>;
  return <span className="text-muted-foreground">{NOT_COMPUTED}</span>;
}

function UnitCell({ item }: { item: ItemRow }) {
  const label = item.unit_raw ?? item.unit ?? NOT_COMPUTED;
  const warn = item.unit_status === "UNIT_UNVERIFIED" || /^mts$/i.test((item.unit_raw ?? "").trim());
  return (
    <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
      {label}
      {warn ? (
        <span className="inline-flex items-center gap-1 text-amber-800 dark:text-amber-200">
          <TriangleAlert className="size-3.5" aria-hidden="true" />
          <span className="text-xs">Unit not verified</span>
        </span>
      ) : null}
    </span>
  );
}

/**
 * Item-level balances for one licence. Debited, Allotted and Invoiced figures open the source
 * drawer. Each row can also expand to three source sections and the movement ledger.
 */
export default function ItemBalanceTable({ licenceId, items, onOpenLedger }: ItemBalanceTableProps) {
  const [expanded, setExpanded] = useState<ReadonlySet<number>>(() => new Set());
  const [drill, setDrill] = useState<OpenDrill | null>(null);

  const toggle = (itemId: number) => {
    setExpanded((current) => {
      const next = new Set(current);
      if (next.has(itemId)) next.delete(itemId);
      else next.add(itemId);
      return next;
    });
  };

  if (items.length === 0) {
    return (
      <div className="rounded-lg border border-dashed bg-card p-6 text-center text-sm text-muted-foreground">
        No items are recorded for this licence.
      </div>
    );
  }

  return (
    <>
      <div className="overflow-x-auto rounded-lg border bg-card">
        <table data-testid="item-table" className="w-full min-w-[80rem] border-collapse text-sm">
          <caption className="sr-only">Item balances for this licence. CIF is in USD.</caption>
          <thead className="bg-muted/50 text-xs text-muted-foreground">
            <tr>
              <th scope="col" rowSpan={2} className="px-3 py-2 text-left font-medium">SR</th>
              <th scope="col" rowSpan={2} className="px-3 py-2 text-left font-medium">Item</th>
              <th scope="col" rowSpan={2} className="px-3 py-2 text-left font-medium">HS Code</th>
              <th scope="col" rowSpan={2} className="px-3 py-2 text-left font-medium">Unit</th>
              {GROUPS.map((group) => (
                <th key={group.field} scope="colgroup" colSpan={2} className="px-3 py-2 text-center font-medium">
                  {group.label}
                </th>
              ))}
              <th scope="col" rowSpan={2} className="px-3 py-2 text-left font-medium">CIF Control</th>
              <th scope="col" rowSpan={2} className="px-3 py-2 text-left font-medium">Status</th>
            </tr>
            <tr>
              {GROUPS.map((group) => (
                <Fragment key={group.field}>
                  <th scope="col" className="px-3 py-1 text-right font-normal">Quantity</th>
                  <th scope="col" className="px-3 py-1 text-right font-normal">CIF (USD)</th>
                </Fragment>
              ))}
            </tr>
          </thead>
          <tbody>
            {items.map((item) => {
              const isOpen = expanded.has(item.item_id);
              const unitUnverified = item.unit_status === "UNIT_UNVERIFIED";
              return (
                <Fragment key={item.item_id}>
                  <tr className="border-t transition-colors hover:bg-muted/30">
                    <td className={cn(CELL, "whitespace-nowrap font-medium")}>
                      <span className="inline-flex items-center gap-1.5">
                        <button
                          type="button"
                          aria-expanded={isOpen}
                          aria-controls={detailsId(item.item_id)}
                          aria-label={`${isOpen ? "Hide" : "Show"} sources for SR ${item.sr}`}
                          onClick={() => toggle(item.item_id)}
                          className="inline-flex size-7 items-center justify-center rounded-md text-muted-foreground outline-none hover:bg-muted hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/40 cursor-pointer"
                        >
                          {isOpen ? <ChevronDown className="size-4" aria-hidden="true" /> : <ChevronRight className="size-4" aria-hidden="true" />}
                        </button>
                        {item.sr}
                      </span>
                    </td>
                    <td className={CELL}>
                      {/* Truncated to one line. The full text stays in the DOM, so the tooltip and screen readers have it. */}
                      <span className="block max-w-[18rem] truncate" title={item.description}>
                        {item.description}
                      </span>
                    </td>
                    <td className={cn(CELL, "whitespace-nowrap")}>
                      {item.hs_code ? (
                        item.hs_code
                      ) : (
                        <span className="text-amber-800 dark:text-amber-200">Unmapped</span>
                      )}
                    </td>
                    <td className={CELL}>
                      <UnitCell item={item} />
                    </td>
                    {GROUPS.map((group) => {
                      const drillable = DRILLABLE[group.field];
                      const emphasis = group.field === "available";
                      return (
                        <Fragment key={group.field}>
                          <td className={cn(GROUP_CELL, emphasis && "bg-muted/20")}>
                            <FigureCell
                              item={item}
                              field={group.field}
                              kind="qty"
                              drillable={drillable && hasFigure(item.qty, group.field, "qty", unitUnverified) ? drillable : undefined}
                              onOpen={(drillGroup, opener) => setDrill({ itemId: item.item_id, group: drillGroup, opener })}
                            />
                          </td>
                          <td className={cn(GROUP_CELL, emphasis && "bg-muted/20")}>
                            <FigureCell
                              item={item}
                              field={group.field}
                              kind="cif"
                              block={group.field === "available" ? displayedAvailableCif(item) : undefined}
                              drillable={drillable && hasFigure(item.cif, group.field, "cif", unitUnverified) ? drillable : undefined}
                              onOpen={(drillGroup, opener) => setDrill({ itemId: item.item_id, group: drillGroup, opener })}
                            />
                          </td>
                        </Fragment>
                      );
                    })}
                    <td className={CELL}>
                      <CifControlCell item={item} />
                    </td>
                    <td className={CELL}>
                      <StatusReasonsButton status={item.status} flags={item.flags} subject={`SR ${item.sr}`} />
                    </td>
                  </tr>
                  {isOpen ? (
                    <tr id={detailsId(item.item_id)} className="border-t bg-muted/20">
                      <td colSpan={COLUMN_COUNT} className="p-4">
                        <ItemSources
                          licenceId={licenceId}
                          item={item}
                          onOpenLedger={() => onOpenLedger(item.item_id)}
                          onViewAll={(group, opener) => setDrill({ itemId: item.item_id, group, opener })}
                        />
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
      {drill ? (
        <ItemDrilldownDrawer
          licenceId={licenceId}
          itemId={drill.itemId}
          group={drill.group}
          returnFocusTo={drill.opener}
          onClose={() => setDrill(null)}
        />
      ) : null}
    </>
  );
}

interface FigureCellProps {
  item: ItemRow;
  field: AmountField;
  kind: DrilldownMeasure;
  /** The figure to show. Defaults to the item's own block for this measure. */
  block?: BalanceBlock;
  drillable: { group: DrilldownGroup; name: string } | undefined;
  onOpen: (group: DrilldownGroup, opener: HTMLElement) => void;
}

/** A figure. A debited, allotted or invoiced figure with a value is a button that opens its drawer. */
function FigureCell({ item, field, kind, block: blockOverride, drillable, onOpen }: FigureCellProps) {
  const block = blockOverride ?? (kind === "cif" ? item.cif : item.qty);
  const unitUnverified = item.unit_status === "UNIT_UNVERIFIED";
  const amount = (
    <BalanceAmount
      block={block}
      field={field}
      kind={kind}
      emphasis={field === "available"}
      unitUnverified={unitUnverified}
      unitFallback={item.unit ?? item.unit_raw}
    />
  );
  if (!drillable) return amount;
  const figure = kind === "cif" ? "CIF (USD)" : "quantity";
  return (
    <button
      type="button"
      onClick={(event) => onOpen(drillable.group, event.currentTarget)}
      aria-label={`Open ${drillable.name} for SR ${item.sr}, ${figure}`}
      className="inline-flex max-w-full cursor-pointer justify-end rounded-sm underline decoration-dotted underline-offset-4 outline-none hover:text-primary focus-visible:ring-[3px] focus-visible:ring-ring/40"
    >
      {amount}
    </button>
  );
}

interface ItemSourcesProps {
  licenceId: number;
  item: ItemRow;
  onOpenLedger: () => void;
  onViewAll: (group: DrilldownGroup, opener: HTMLElement) => void;
}

/** The three source sections for an item: BOE debits, customer allotments and invoices, each with View all. */
function ItemSources({ licenceId, item, onOpenLedger, onViewAll }: ItemSourcesProps) {
  const drill = useItemDrilldown(licenceId, item.item_id, true);
  const data = drill.data;

  return (
    <div className="space-y-4" aria-busy={drill.isPending}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h3 className="text-sm font-semibold">Sources for SR {item.sr}</h3>
        <Button variant="outline" size="sm" onClick={onOpenLedger}>
          Open movement ledger
        </Button>
      </div>
      {drill.isError ? (
        <p role="alert" className="text-sm text-destructive">The sources for this item could not be loaded. Collapse and expand the row to retry.</p>
      ) : null}
      <div className="grid gap-3 md:grid-cols-3">
        <SourceSection
          title="BOE debits"
          viewName="BOE debits"
          group="boes"
          sr={item.sr}
          summary={data ? `${data.boes.totals.boe_rows} BOEs · debited ${formatDecimal(data.boes.totals.debited_cif, CIF_DECIMALS)} USD · covered ${formatDecimal(data.boes.totals.covered_cif, CIF_DECIMALS)} USD` : null}
          loading={drill.isPending}
          onViewAll={onViewAll}
        />
        <SourceSection
          title="Customer allotments"
          viewName="customer allotments"
          group="allotments"
          sr={item.sr}
          summary={data ? `${data.allotments.totals.allotment_rows} allotments · outstanding ${formatDecimal(data.allotments.totals.outstanding_cif, CIF_DECIMALS)} USD` : null}
          loading={drill.isPending}
          onViewAll={onViewAll}
        />
        <SourceSection
          title="Invoices"
          viewName="invoices"
          group="invoices"
          sr={item.sr}
          summary={data ? `${data.invoices.totals.invoice_rows} invoices · sold ${formatDecimal(data.invoices.totals.sold_cif, CIF_DECIMALS)} USD · uncovered ${formatDecimal(data.invoices.totals.uncovered_cif, CIF_DECIMALS)} USD` : null}
          loading={drill.isPending}
          onViewAll={onViewAll}
        />
      </div>
    </div>
  );
}

interface SourceSectionProps {
  title: string;
  /** Lower-case name used in the View all label, e.g. "customer allotments". */
  viewName: string;
  group: DrilldownGroup;
  sr: string;
  summary: string | null;
  loading: boolean;
  onViewAll: (group: DrilldownGroup, opener: HTMLElement) => void;
}

function SourceSection({ title, viewName, group, sr, summary, loading, onViewAll }: SourceSectionProps) {
  const headingId = `source-${group}-${sr}`;
  return (
    <section aria-labelledby={headingId} className="flex flex-col gap-2 rounded-md border bg-card p-3">
      <div className="flex items-center justify-between gap-2">
        <h4 id={headingId} className="text-sm font-medium">{title}</h4>
        <Button variant="outline" size="sm" aria-label={`View all ${viewName} for SR ${sr}`} onClick={(event) => onViewAll(group, event.currentTarget)}>
          View all
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">{loading ? "Loading…" : summary ?? NOT_COMPUTED}</p>
    </section>
  );
}
