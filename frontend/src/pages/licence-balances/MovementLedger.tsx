import { useEffect, useRef } from "react";
import { CircleCheck, TriangleAlert, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import LoadErrorPanel from "./LoadErrorPanel";
import { CIF_DECIMALS, NOT_COMPUTED, QTY_DECIMALS, formatDecimal, formatIsoDate, isNegativeDecimal, sameDecimal } from "./format";
import { movementLabel } from "./labels";
import { useItemLedger } from "./licenceBalanceQueries";
import type { Decimal, ItemLedger, Movement } from "./types";

interface MovementLedgerProps {
  licenceId: number;
  itemId: number;
  onClose: () => void;
}

/**
 * Inline movement ledger for one item. The item endpoint is fetched once when
 * this mounts, so opening it fetches and closing it does not discard the cache.
 */
export default function MovementLedger({ licenceId, itemId, onClose }: MovementLedgerProps) {
  const query = useItemLedger(licenceId, itemId);
  const headingRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  const ledger = query.data;

  return (
    <section
      id="movement-ledger"
      data-testid="movement-ledger"
      aria-labelledby="movement-ledger-heading"
      className="space-y-4 rounded-lg border bg-card p-4"
    >
      <div className="flex items-start justify-between gap-3">
        <h2 id="movement-ledger-heading" ref={headingRef} tabIndex={-1} className="text-base font-semibold outline-none">
          {ledger ? `Movement ledger: SR ${ledger.sr}, ${ledger.description}` : "Movement ledger"}
        </h2>
        <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close movement ledger">
          <X aria-hidden="true" />
        </Button>
      </div>

      {ledger ? (
        <LedgerBody ledger={ledger} />
      ) : query.isError ? (
        <LoadErrorPanel title="The movement ledger could not be loaded." error={query.error} onRetry={() => void query.refetch()} compact />
      ) : (
        <Skeleton role="status" aria-label="Loading movement ledger" className="h-32 w-full" />
      )}
    </section>
  );
}

function LedgerBody({ ledger }: { ledger: ItemLedger }) {
  const unitUnverified = ledger.unit_status === "UNIT_UNVERIFIED";
  const qtyUnit = ledger.qty.unit ?? ledger.unit ?? ledger.unit_raw ?? null;

  return (
    <div className="space-y-6">
      {unitUnverified ? (
        <div role="note" className="rounded-md border border-sky-300 bg-sky-50 p-3 text-sm text-sky-900 dark:border-sky-700 dark:bg-sky-950/40 dark:text-sky-100">
          Quantity unit not verified — figures are shown as recorded.
        </div>
      ) : null}

      <div className="space-y-2">
        <h3 className="text-sm font-semibold">{`Quantity ledger${qtyUnit ? ` (${qtyUnit})` : ""}`}</h3>
        <LedgerTable
          rows={ledger.qty_movements}
          decimals={QTY_DECIMALS}
          amountUnit={qtyUnit ?? "qty"}
          caption="Quantity movement ledger"
          testId="qty-ledger"
        />
        {unitUnverified ? (
          <p className="text-sm text-muted-foreground">Quantity check not run: the unit is not verified.</p>
        ) : (
          <LedgerCheck
            rows={ledger.qty_movements}
            available={ledger.qty.available}
            decimals={QTY_DECIMALS}
            testId="qty-ledger-check"
            label="Quantity"
          />
        )}
      </div>

      <div className="space-y-2">
        <h3 className="text-sm font-semibold">CIF ledger (USD)</h3>
        <LedgerTable
          rows={ledger.cif_movements}
          decimals={CIF_DECIMALS}
          amountUnit="USD"
          caption="CIF movement ledger"
          testId="cif-ledger"
        />
        <LedgerCheck
          rows={ledger.cif_movements}
          available={ledger.cif.available}
          decimals={CIF_DECIMALS}
          testId="cif-ledger-check"
          label="CIF"
        />
      </div>
    </div>
  );
}

/** The last balance-changing row's running balance. Memo rows never change the balance, so they are skipped. */
function finalBalance(rows: Movement[]): Decimal | null {
  for (let index = rows.length - 1; index >= 0; index -= 1) {
    const row = rows[index];
    if (!row.memo && row.running_balance !== null) return row.running_balance;
  }
  return null;
}

interface LedgerCheckProps {
  rows: Movement[];
  available: Decimal | undefined;
  decimals: number;
  testId: string;
  label: string;
}

/** Confirms the ledger's final running balance equals the item's Available figure. Compared as strings. */
function LedgerCheck({ rows, available, decimals, testId, label }: LedgerCheckProps) {
  if (available === null || available === undefined) {
    return (
      <p data-testid={testId} className="text-sm text-muted-foreground">
        {`${label} available is not computed for this item, so the ledger cannot be checked.`}
      </p>
    );
  }

  const ending = finalBalance(rows);
  if (ending === null) {
    return (
      <p data-testid={testId} className="text-sm text-muted-foreground">
        {`No balance-changing movements are recorded. ${label} available is ${formatDecimal(available, decimals)}.`}
      </p>
    );
  }

  const endingText = formatDecimal(ending, decimals);
  if (sameDecimal(ending, available)) {
    return (
      <p data-testid={testId} role="status" className="flex items-center gap-2 text-sm text-emerald-800 dark:text-emerald-200">
        <CircleCheck className="size-4 shrink-0" aria-hidden="true" />
        {`Ledger ends at ${endingText} — matches available`}
      </p>
    );
  }

  return (
    <p data-testid={testId} role="status" className="flex items-center gap-2 text-sm text-amber-900 dark:text-amber-200">
      <TriangleAlert className="size-4 shrink-0" aria-hidden="true" />
      {`Ledger ends at ${endingText}, but available is ${formatDecimal(available, decimals)}. Review required.`}
    </p>
  );
}

interface LedgerTableProps {
  rows: Movement[];
  decimals: number;
  amountUnit: string;
  caption: string;
  testId: string;
}

function LedgerTable({ rows, decimals, amountUnit, caption, testId }: LedgerTableProps) {
  if (rows.length === 0) {
    return <p className="text-sm text-muted-foreground">No movements recorded.</p>;
  }

  return (
    <div className="overflow-x-auto rounded-md border">
      <table data-testid={testId} className="w-full min-w-[60rem] text-sm">
        <caption className="sr-only">{caption}</caption>
        <thead className="bg-muted/50 text-xs text-muted-foreground">
          <tr>
            <th scope="col" className="px-3 py-2 text-left font-medium">Date</th>
            <th scope="col" className="px-3 py-2 text-left font-medium">Movement</th>
            <th scope="col" className="px-3 py-2 text-left font-medium">Reference</th>
            <th scope="col" className="px-3 py-2 text-left font-medium">Customer</th>
            <th scope="col" className="px-3 py-2 text-right font-medium">{`Debit (${amountUnit})`}</th>
            <th scope="col" className="px-3 py-2 text-right font-medium">{`Credit (${amountUnit})`}</th>
            <th scope="col" className="px-3 py-2 text-right font-medium">{`Running balance (${amountUnit})`}</th>
            <th scope="col" className="px-3 py-2 text-left font-medium">Link status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr
              key={`${row.kind}-${row.source.id}-${index}`}
              data-memo={row.memo ? "true" : undefined}
              className={cn("border-t align-top", row.memo && "italic text-muted-foreground")}
            >
              <td className="px-3 py-2 whitespace-nowrap">{formatIsoDate(row.date)}</td>
              <td className="px-3 py-2">
                <span>{movementLabel(row.kind)}</span>
                {row.memo ? <span className="ml-2 text-xs">(memo — not deducted)</span> : null}
                {row.previous_owner ? <span className="ml-2 rounded-md border px-1.5 py-0.5 text-xs">Previous owner</span> : null}
              </td>
              <td className="px-3 py-2 whitespace-nowrap">{row.reference || NOT_COMPUTED}</td>
              <td className="px-3 py-2">{row.customer || NOT_COMPUTED}</td>
              <td className="px-3 py-2 text-right tabular-nums whitespace-nowrap">{formatDecimal(row.debit, decimals)}</td>
              <td className="px-3 py-2 text-right tabular-nums whitespace-nowrap">{formatDecimal(row.credit, decimals)}</td>
              <td
                className={cn(
                  "px-3 py-2 text-right font-semibold tabular-nums whitespace-nowrap",
                  isNegativeDecimal(row.running_balance) && "text-destructive",
                )}
              >
                {formatDecimal(row.running_balance, decimals)}
              </td>
              <td className="px-3 py-2 whitespace-nowrap">{row.link_status || NOT_COMPUTED}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
