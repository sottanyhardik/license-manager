import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";
import BalanceAmount from "@/pages/licence-balances/BalanceAmount";
import { CIF_DECIMALS, NOT_COMPUTED, QTY_DECIMALS, formatCif, formatDecimal, formatQty, isNegativeDecimal } from "@/pages/licence-balances/format";
import { describeFlag, statusDisplay } from "@/pages/licence-balances/labels";
import { StatusPill } from "@/pages/licence-balances/StatusPill";
import type { ItemRow, LicenceDetail } from "@/pages/licence-balances/types";
import { cn } from "@/lib/utils";
import AsyncGate, { EmptyPanel } from "./AsyncGate";
import { useLicenceTransactions, useSourceReconciliation } from "./licenceWorkspaceQueries";
import { TextCell, TransactionTable, type ColumnHeader } from "./TransactionTable";
import type { AllocationIssue, BoeRow, SourceReconciliation, SourceReconciliationItem, SourceReconciliationLine } from "./types";
import { displayDate } from "./workspaceFormat";

interface ReconciliationTabProps {
  detail: LicenceDetail;
  licenceId: number;
  /** Opens the item on Items & Balance, with its sources and movement ledger available there. */
  onOpenItem: (itemId: number) => void;
}

const RECONCILED = "RECONCILED";

function isReconciled(item: ItemRow): boolean {
  return item.status.trim().toUpperCase() === RECONCILED;
}

function isUnmapped(item: ItemRow): boolean {
  return item.status.trim().toUpperCase() === "UNMAPPED ITEM" || item.flags.includes("UNMAPPED_AMOUNT");
}

/** Units the backend could not verify. Covers both the item's unit status and the licence-level list. */
function unitIssueIds(detail: LicenceDetail): Set<number> {
  const ids = new Set(detail.unverified_qty_items.map((entry) => entry.item_id));
  for (const item of detail.items) {
    if (item.unit_status === "UNIT_UNVERIFIED") ids.add(item.item_id);
  }
  return ids;
}

/** Item counts per status label. Counting is not money arithmetic, so it runs here. */
function countByStatus(items: ItemRow[]): { label: string; count: number }[] {
  const counts = new Map<string, number>();
  for (const item of items) {
    const label = statusDisplay(item.status).label;
    counts.set(label, (counts.get(label) ?? 0) + 1);
  }
  return Array.from(counts, ([label, count]) => ({ label, count }));
}

/** A quantity cell with its unit. Withheld while the unit is not verified: words, never a figure. */
function QuantityCell({ value, unit, withheld }: { value: string | null | undefined; unit: string | null; withheld: boolean }) {
  if (withheld) {
    return <td className="whitespace-nowrap px-3 py-2 text-right text-xs italic text-muted-foreground">Unit unverified</td>;
  }
  const text = formatQty(value ?? undefined, unit);
  return (
    <td
      className={cn(
        "whitespace-nowrap px-3 py-2 text-right tabular-nums",
        isNegativeDecimal(value) && "font-medium text-destructive",
        text === NOT_COMPUTED && "text-muted-foreground",
      )}
    >
      {text}
    </td>
  );
}

/** A CIF cell, USD. Formatted, never converted. */
function CifCell({ value }: { value: string | null | undefined }) {
  const text = formatDecimal(value ?? undefined, CIF_DECIMALS);
  return (
    <td
      className={cn(
        "whitespace-nowrap px-3 py-2 text-right tabular-nums",
        isNegativeDecimal(value) && "font-medium text-destructive",
        text === NOT_COMPUTED && "text-muted-foreground",
      )}
    >
      {text}
    </td>
  );
}

/**
 * Reconciliation for one licence: the balance lines, source-level differences, allocation issues,
 * the bills of entry behind the balance, and the item-level review lists. Every amount is shown
 * quantity first, then CIF. Nothing here recalculates a balance.
 */
export default function ReconciliationTab({ detail, licenceId, onOpenItem }: ReconciliationTabProps) {
  const unitIds = unitIssueIds(detail);
  const notReconciled = detail.items.filter((item) => !isReconciled(item));
  const unmapped = detail.items.filter(isUnmapped);
  const unitIssues = detail.items.filter((item) => unitIds.has(item.item_id));
  const negative = detail.items.filter((item) => isNegativeDecimal(item.cif.available) || isNegativeDecimal(item.qty.available));
  const statusCounts = countByStatus(detail.items);

  return (
    <div className="flex flex-col gap-6">
      <LicenceBalanceLines detail={detail} />

      <SourceReconciliationSection licenceId={licenceId} detail={detail} onOpenItem={onOpenItem} />

      <AllocationIssuesSection licenceId={licenceId} detail={detail} onOpenItem={onOpenItem} />

      <BoeSourceSection licenceId={licenceId} detail={detail} />

      <section aria-labelledby="status-counts-heading" className="space-y-2">
        <h3 id="status-counts-heading" className="text-sm font-semibold">
          Items by status
        </h3>
        {statusCounts.length === 0 ? (
          <p className="text-sm text-muted-foreground">No items are recorded for this licence.</p>
        ) : (
          <ul className="flex flex-wrap gap-2 text-sm">
            {statusCounts.map((entry) => (
              <li key={entry.label} className="rounded-md border bg-card px-3 py-1.5">
                {`${entry.label}: ${entry.count}`}
              </li>
            ))}
          </ul>
        )}
      </section>

      <IssueSection
        headingId="issues-not-reconciled"
        title="Items not reconciled"
        emptyText="Every item is reconciled."
        items={notReconciled}
        detailHeader="Review flags"
        renderDetail={(item) => <FlagList codes={item.flags} />}
        onOpenItem={onOpenItem}
      />

      <IssueSection
        headingId="issues-unmapped"
        title="Unmapped amounts"
        emptyText="No amounts are unmapped."
        items={unmapped}
        detailHeader="Detail"
        renderDetail={() => (
          <span className="text-sm text-muted-foreground">Some transactions for this item could not be attributed to it.</span>
        )}
        onOpenItem={onOpenItem}
      />

      <IssueSection
        headingId="issues-units"
        title="Unit issues"
        emptyText="Every quantity unit is verified."
        items={unitIssues}
        detailHeader="Detail"
        renderDetail={(item) => (
          <span className="text-sm">
            {`Unit recorded as ${item.unit_raw ?? "not recorded"}. Quantities are withheld until it is verified.`}
          </span>
        )}
        onOpenItem={onOpenItem}
      />

      <IssueSection
        headingId="issues-negative"
        title="Negative balances"
        emptyText="No item has a negative balance."
        items={negative}
        detailHeader="Available"
        renderDetail={(item) => (
          <dl className="grid gap-1 text-sm sm:grid-cols-2">
            <div className="flex justify-between gap-3 sm:justify-start">
              <dt className="text-muted-foreground">Qty</dt>
              <dd>
                <BalanceAmount block={item.qty} field="available" kind="qty" unitFallback={item.unit ?? item.unit_raw} />
              </dd>
            </div>
            <div className="flex justify-between gap-3 sm:justify-start">
              <dt className="text-muted-foreground">CIF (USD)</dt>
              <dd>
                <BalanceAmount block={item.cif} field="available" kind="cif" />
              </dd>
            </div>
          </dl>
        )}
        onOpenItem={onOpenItem}
      />

      <LegacyComparison detail={detail} />
    </div>
  );
}

/**
 * The debits and reservations behind the available figure. The available figure itself
 * is in the header cards, so it is not repeated as a row here.
 */
function LicenceBalanceLines({ detail }: { detail: LicenceDetail }) {
  const lines: { label: string; field: "original" | "debited" | "allotted" | "invoiced" }[] = [
    { label: "Original", field: "original" },
    { label: "Used through BOEs (debited)", field: "debited" },
    { label: "Reserved for customers (allotted)", field: "allotted" },
    { label: "Invoiced", field: "invoiced" },
  ];
  return (
    <section aria-labelledby="balance-lines-heading" className="space-y-2">
      <h3 id="balance-lines-heading" className="text-sm font-semibold">
        Licence balance
      </h3>
      <div className="max-w-full overflow-x-auto rounded-lg border bg-card">
        <table className="w-full min-w-[28rem] border-collapse text-sm">
          <caption className="sr-only">Licence balance lines. Quantity is shown first, then CIF in USD.</caption>
          <thead className="bg-muted/50 text-xs text-muted-foreground">
            <tr>
              <th scope="col" className="px-3 py-2 text-left font-medium">
                Line
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                Quantity
              </th>
              <th scope="col" className="px-3 py-2 text-right font-medium">
                CIF (USD)
              </th>
            </tr>
          </thead>
          <tbody>
            {lines.map((line) => (
              <tr key={line.field} className="border-t">
                <th scope="row" className="px-3 py-2 text-left font-normal">
                  {line.label}
                </th>
                <td className="px-3 py-2 text-right">
                  <BalanceAmount block={detail.qty} field={line.field} kind="qty" />
                </td>
                <td className="px-3 py-2 text-right">
                  <BalanceAmount block={detail.cif} field={line.field} kind="cif" />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Source-level differences: each item's drawer totals against its item figures
// ---------------------------------------------------------------------------

interface DifferenceRow {
  sr: string;
  item: string;
  figure: string;
  qty: SourceReconciliationLine | undefined;
  cif: SourceReconciliationLine | undefined;
  qtyWithheld: boolean;
}

/** Lines where the source records do not agree with the item figure, one row per figure. */
function differenceRows(item: SourceReconciliationItem, withheld: boolean): DifferenceRow[] {
  const fields = new Set([...item.reconciliation.cif.map((l) => l.field), ...item.reconciliation.qty.map((l) => l.field)]);
  return Array.from(fields)
    .map((field) => ({
      sr: item.sr,
      item: item.description,
      figure: field,
      qty: item.reconciliation.qty.find((l) => l.field === field),
      cif: item.reconciliation.cif.find((l) => l.field === field),
      qtyWithheld: withheld,
    }))
    .filter((row) => row.cif?.status !== "RECONCILED" || (!row.qtyWithheld && row.qty?.status !== "RECONCILED"));
}

function SourceReconciliationSection({ licenceId, detail, onOpenItem }: { licenceId: number; detail: LicenceDetail; onOpenItem: (itemId: number) => void }) {
  const query = useSourceReconciliation(licenceId);
  return (
    <section aria-labelledby="source-reconciliation-heading" className="space-y-2">
      <h3 id="source-reconciliation-heading" className="text-sm font-semibold">
        Source-level reconciliation
      </h3>
      <AsyncGate
        data={query.data}
        isError={query.isError}
        error={query.error}
        onRetry={() => void query.refetch()}
        loadingLabel="Loading source reconciliation"
        errorTitle="The source reconciliation could not be loaded."
      >
        {(source: SourceReconciliation) => <SourceDifferences source={source} detail={detail} onOpenItem={onOpenItem} />}
      </AsyncGate>
    </section>
  );
}

function SourceDifferences({ source, detail, onOpenItem }: { source: SourceReconciliation; detail: LicenceDetail; onOpenItem: (itemId: number) => void }) {
  const withheldItems = new Set(detail.items.filter((item) => item.unit_status === "UNIT_UNVERIFIED").map((item) => item.item_id));
  const rows = source.items.flatMap((item) => differenceRows(item, withheldItems.has(item.item_id)).map((row) => ({ ...row, itemId: item.item_id })));
  const reconciled = source.items.length - source.items_not_reconciled;

  return (
    <div className="space-y-2">
      <p className="text-sm">
        {`${reconciled} of ${source.items.length} items reconcile to their source records.`}
      </p>
      {rows.length === 0 ? (
        <p className="text-sm text-muted-foreground">Every item's source records agree with its item figures.</p>
      ) : (
        <div className="max-w-full overflow-x-auto rounded-lg border bg-card">
          <table className="w-full min-w-[60rem] border-collapse text-sm">
            <caption className="sr-only">Figures where the source records and the item figures differ. Quantity is shown first, then CIF.</caption>
            <thead className="bg-muted/50 text-xs text-muted-foreground">
              <tr>
                <th scope="col" className="px-3 py-2 text-left font-medium">SR</th>
                <th scope="col" className="px-3 py-2 text-left font-medium">Figure</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">Quantity (source)</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">Quantity (item table)</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">CIF (USD, source)</th>
                <th scope="col" className="px-3 py-2 text-right font-medium">CIF (USD, item table)</th>
                <th scope="col" className="px-3 py-2 text-left font-medium">Result</th>
                <th scope="col" className="px-3 py-2 text-left font-medium"><span className="sr-only">Action</span></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((row) => (
                <tr key={`${row.sr}-${row.figure}`} className="border-t align-top">
                  <td className="whitespace-nowrap px-3 py-2 font-medium">{row.sr}</td>
                  <td className="px-3 py-2 capitalize">{row.figure}</td>
                  {row.qtyWithheld ? (
                    <td colSpan={2} className="px-3 py-2 text-right text-xs italic text-muted-foreground">Unit unverified</td>
                  ) : (
                    <>
                      <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">{formatDecimal(row.qty?.drill, QTY_DECIMALS)}</td>
                      <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">{formatDecimal(row.qty?.item_table, QTY_DECIMALS)}</td>
                    </>
                  )}
                  <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">{formatDecimal(row.cif?.drill, CIF_DECIMALS)}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">{formatDecimal(row.cif?.item_table, CIF_DECIMALS)}</td>
                  <td className="px-3 py-2">
                    <StatusPill status={row.cif?.status ?? row.qty?.status ?? NOT_COMPUTED} />
                  </td>
                  <td className="whitespace-nowrap px-3 py-2">
                    <Button variant="outline" size="sm" onClick={() => onOpenItem(row.itemId)} aria-label={`Show SR ${row.sr} in Items & Balance`}>
                      Show in Items &amp; Balance
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Allocation issues: BOEs, invoices and allotments that need review
// ---------------------------------------------------------------------------

const KIND_LABEL: Record<AllocationIssue["kind"], string> = {
  BOE: "Bill of entry",
  INVOICE: "Invoice",
  ALLOTMENT: "Allotment",
};

function AllocationIssuesSection({ licenceId, detail, onOpenItem }: { licenceId: number; detail: LicenceDetail; onOpenItem: (itemId: number) => void }) {
  const query = useSourceReconciliation(licenceId);
  return (
    <section aria-labelledby="allocation-issues-heading" className="space-y-2">
      <h3 id="allocation-issues-heading" className="text-sm font-semibold">
        Allocation issues
      </h3>
      <AsyncGate
        data={query.data}
        isError={query.isError}
        error={query.error}
        onRetry={() => void query.refetch()}
        loadingLabel="Loading allocation issues"
        errorTitle="The allocation issues could not be loaded."
      >
        {(source: SourceReconciliation) => {
          const issues = source.items.flatMap((item) => item.issues.map((issue) => ({ item, issue })));
          if (issues.length === 0) return <EmptyPanel>No allocation record needs review.</EmptyPanel>;
          const withheldItems = new Set(detail.items.filter((item) => item.unit_status === "UNIT_UNVERIFIED").map((item) => item.item_id));
          return (
            <div className="max-w-full overflow-x-auto rounded-lg border bg-card">
              <table className="w-full min-w-[64rem] border-collapse text-sm">
                <caption className="sr-only">Allocation records that need review. Quantity is shown first, then CIF.</caption>
                <thead className="bg-muted/50 text-xs text-muted-foreground">
                  <tr>
                    <th scope="col" className="px-3 py-2 text-left font-medium">SR</th>
                    <th scope="col" className="px-3 py-2 text-left font-medium">Record</th>
                    <th scope="col" className="px-3 py-2 text-left font-medium">Reference</th>
                    <th scope="col" className="px-3 py-2 text-left font-medium">Status</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">Quantity</th>
                    <th scope="col" className="px-3 py-2 text-right font-medium">CIF (USD)</th>
                    <th scope="col" className="px-3 py-2 text-left font-medium">Why it needs review</th>
                    <th scope="col" className="px-3 py-2 text-left font-medium"><span className="sr-only">Action</span></th>
                  </tr>
                </thead>
                <tbody>
                  {issues.map(({ item, issue }) => {
                    const withheld = withheldItems.has(item.item_id);
                    const unit = detail.items.find((candidate) => candidate.item_id === item.item_id)?.unit ?? null;
                    return (
                      <tr key={`${item.item_id}-${issue.kind}-${issue.reference}-${issue.status}`} className="border-t align-top">
                        <td className="whitespace-nowrap px-3 py-2 font-medium">{item.sr}</td>
                        <td className="whitespace-nowrap px-3 py-2">{KIND_LABEL[issue.kind]}</td>
                        <td className="whitespace-nowrap px-3 py-2">{issue.reference}</td>
                        <td className="px-3 py-2">{issue.status}</td>
                        <QuantityCell value={issue.amount.qty} unit={unit} withheld={withheld} />
                        <CifCell value={issue.amount.cif} />
                        <td className="px-3 py-2">
                          <FlagText codes={issue.flags} />
                        </td>
                        <td className="whitespace-nowrap px-3 py-2">
                          <Button variant="outline" size="sm" onClick={() => onOpenItem(item.item_id)} aria-label={`Show SR ${item.sr} in Items & Balance`}>
                            Show in Items &amp; Balance
                          </Button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          );
        }}
      </AsyncGate>
    </section>
  );
}

function FlagText({ codes }: { codes: string[] }) {
  if (codes.length === 0) return <span className="text-muted-foreground">No flags recorded.</span>;
  return (
    <ul className="space-y-0.5 text-xs">
      {codes.map((code) => (
        <li key={code}>{describeFlag(code).text}</li>
      ))}
    </ul>
  );
}

// ---------------------------------------------------------------------------
// Bills of entry behind the balance: the licence-wide source list
// ---------------------------------------------------------------------------

const BOE_COLUMNS: ColumnHeader[] = [
  { label: "BOE No." },
  { label: "BOE Date" },
  { label: "SR" },
  { label: "Customer" },
  { label: "BOE Quantity", numeric: true },
  { label: "BOE CIF (USD)", numeric: true },
  { label: "Covered by Sale — Quantity", numeric: true },
  { label: "Covered by Sale — CIF (USD)", numeric: true },
  { label: "Uncovered — Quantity", numeric: true },
  { label: "Uncovered — CIF (USD)", numeric: true },
  { label: "Sale / Invoice" },
  { label: "Status" },
];

function BoeSourceSection({ licenceId, detail }: { licenceId: number; detail: LicenceDetail }) {
  const query = useLicenceTransactions(licenceId);
  const unitOf = (itemId: number) => detail.items.find((item) => item.item_id === itemId);
  return (
    <section aria-labelledby="boe-source-heading" className="space-y-2">
      <h3 id="boe-source-heading" className="text-sm font-semibold">
        Bills of entry behind the balance
      </h3>
      <AsyncGate
        data={query.data?.boes}
        isError={query.isError}
        error={query.error}
        onRetry={() => void query.refetch()}
        loadingLabel="Loading bills of entry"
        errorTitle="The bills of entry could not be loaded."
      >
        {(boes: BoeRow[]) =>
          boes.length === 0 ? (
            <EmptyPanel>No bills of entry are linked to this licence.</EmptyPanel>
          ) : (
            <TransactionTable caption="Bills of entry behind this licence's balance. Quantity is shown first, then CIF in USD." columns={BOE_COLUMNS}>
              {boes.map((row, index) => {
                const item = unitOf(row.item_id);
                const unit = item?.unit ?? item?.unit_raw ?? null;
                const withheld = item?.unit_status === "UNIT_UNVERIFIED";
                return (
                  <tr key={`${row.boe_number}-${row.sr}-${index}`} className="border-t" data-previous-owner={row.previous_owner ? "true" : undefined}>
                    <TextCell className="whitespace-nowrap font-medium">
                      {row.boe_number}
                      {row.previous_owner ? (
                        <span className="ml-2 rounded-md border px-1.5 py-0.5 text-xs font-normal">Previous owner</span>
                      ) : null}
                    </TextCell>
                    <TextCell className="whitespace-nowrap">{displayDate(row.boe_date)}</TextCell>
                    <TextCell className="whitespace-nowrap">{row.sr}</TextCell>
                    <TextCell>{row.customer ?? "—"}</TextCell>
                    <QuantityCell value={row.qty} unit={unit} withheld={withheld} />
                    <CifCell value={row.cif_fc} />
                    <QuantityCell value={row.covered_qty} unit={unit} withheld={withheld} />
                    <CifCell value={row.covered_cif} />
                    <QuantityCell value={row.uncovered_qty} unit={unit} withheld={withheld} />
                    <CifCell value={row.uncovered_cif} />
                    <TextCell>{row.linked_sale_invoices.length > 0 ? row.linked_sale_invoices.join(", ") : "—"}</TextCell>
                    <TextCell>
                      <StatusPill status={row.status} />
                    </TextCell>
                  </tr>
                );
              })}
            </TransactionTable>
          )
        }
      </AsyncGate>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Item review lists and the legacy comparison (unchanged in meaning)
// ---------------------------------------------------------------------------

function FlagList({ codes }: { codes: string[] }) {
  if (codes.length === 0) return <span className="text-sm text-muted-foreground">No flags recorded.</span>;
  return (
    <ul className="space-y-1 text-sm">
      {codes.map((code) => {
        const flag = describeFlag(code);
        return (
          <li key={code}>
            {flag.text}
            {flag.known ? <span className="ml-2 font-mono text-xs text-muted-foreground">{flag.code}</span> : null}
          </li>
        );
      })}
    </ul>
  );
}

interface IssueSectionProps {
  headingId: string;
  title: string;
  emptyText: string;
  items: ItemRow[];
  detailHeader: string;
  renderDetail: (item: ItemRow) => ReactNode;
  onOpenItem: (itemId: number) => void;
}

/** One category of items needing attention. Empty categories say so in words. */
function IssueSection({ headingId, title, emptyText, items, detailHeader, renderDetail, onOpenItem }: IssueSectionProps) {
  return (
    <section aria-labelledby={headingId} className="space-y-2">
      <h3 id={headingId} className="text-sm font-semibold">
        {`${title} (${items.length})`}
      </h3>
      {items.length === 0 ? (
        <p className="text-sm text-muted-foreground">{emptyText}</p>
      ) : (
        <div className="max-w-full overflow-x-auto rounded-lg border bg-card">
          <table className="w-full min-w-[40rem] border-collapse text-sm">
            <caption className="sr-only">{title}</caption>
            <thead className="bg-muted/50 text-xs text-muted-foreground">
              <tr>
                <th scope="col" className="px-3 py-2 text-left font-medium">SR</th>
                <th scope="col" className="px-3 py-2 text-left font-medium">Item</th>
                <th scope="col" className="px-3 py-2 text-left font-medium">Status</th>
                <th scope="col" className="px-3 py-2 text-left font-medium">{detailHeader}</th>
                <th scope="col" className="px-3 py-2 text-left font-medium"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {items.map((item) => (
                <tr key={item.item_id} className="border-t align-top">
                  <td className="whitespace-nowrap px-3 py-2 font-medium">{item.sr}</td>
                  <td className="px-3 py-2">{item.description}</td>
                  <td className="px-3 py-2">
                    <StatusPill status={item.status} />
                  </td>
                  <td className="px-3 py-2">{renderDetail(item)}</td>
                  <td className="whitespace-nowrap px-3 py-2">
                    <Button variant="outline" size="sm" onClick={() => onOpenItem(item.item_id)} aria-label={`Show SR ${item.sr} in Items & Balance`}>
                      Show in Items &amp; Balance
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function LegacyComparison({ detail }: { detail: LicenceDetail }) {
  const explanation =
    detail.legacy_status === "MISMATCH"
      ? "The legacy balance engine and the reconciled item calculation disagree. The reconciled figure is the one used in this workspace. Review required."
      : detail.legacy_status === "RECONCILED"
        ? "The legacy balance engine agrees with the reconciled figure."
        : "No legacy comparison is recorded for this licence.";

  return (
    <section aria-labelledby="legacy-comparison-heading" className="space-y-2">
      <h3 id="legacy-comparison-heading" className="text-sm font-semibold">
        Legacy comparison
      </h3>
      <dl className="divide-y rounded-lg border bg-card text-sm">
        <div className="flex flex-wrap justify-between gap-2 px-4 py-2">
          <dt className="text-muted-foreground">Legacy balance engine (CIF, USD)</dt>
          <dd className="tabular-nums">{detail.legacy_balance_cif === null ? "Not computed" : formatCif(detail.legacy_balance_cif)}</dd>
        </div>
      </dl>
      <p
        role={detail.legacy_status === "MISMATCH" ? "note" : undefined}
        className={cn("text-sm", detail.legacy_status === "MISMATCH" ? "font-medium text-amber-900 dark:text-amber-100" : "text-muted-foreground")}
      >
        {explanation}
      </p>
    </section>
  );
}
