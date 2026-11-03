import type { ReactNode } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import BalanceAmount from "./BalanceAmount";
import { formatCif, formatQty } from "./format";
import { StatusPill } from "./StatusPill";
import type { BalanceBlock, Decimal, LicenceSummary } from "./types";

interface BalanceSummaryPanelsProps {
  summary: LicenceSummary;
  /**
   * Whether each panel ends with its "Remaining" figure. A page that already shows the
   * available figure in a card turns this off, so the figure appears once.
   */
  showAvailable?: boolean;
}

/** The two licence-level panels: quantity, then original CIF value. Side by side on wide screens. */
export default function BalanceSummaryPanels({ summary, showAvailable = true }: BalanceSummaryPanelsProps) {
  return (
    <section aria-label="Balance summary" className="grid gap-4 lg:grid-cols-2">
      <QuantityPanel summary={summary} showAvailable={showAvailable} />
      <CifPanel summary={summary} showAvailable={showAvailable} />
    </section>
  );
}

const FIGURE_FIELDS = ["original", "debited", "allotted", "invoiced", "available"] as const;

/** A block that carries amounts. An OVER-ALLOCATED or unverified block carries none. */
function hasFigures(block: BalanceBlock): boolean {
  return FIGURE_FIELDS.some((field) => {
    const value: Decimal | undefined = block[field];
    return value !== null && value !== undefined;
  });
}

function SummaryRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2">
      <dt className="text-sm text-muted-foreground">{label}</dt>
      <dd className="text-sm">{children}</dd>
    </div>
  );
}

function RemainingFigure({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-lg bg-muted/50 p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">Remaining</p>
      <p className="mt-1 text-2xl font-semibold">{children}</p>
    </div>
  );
}

function CifPanel({ summary, showAvailable }: BalanceSummaryPanelsProps) {
  const cif = summary.cif;
  return (
    <Card>
      <CardHeader>
        <CardTitle>Original licence value</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {summary.cif_control === "LICENCE" ? (
          <p className="text-sm text-muted-foreground">
            Licence-level CIF control (Individual Item CIF is off). The licence&apos;s total CIF decides over-utilisation.
            Item CIF is shown as attribution only.
          </p>
        ) : null}
        {hasFigures(cif) ? (
          <>
            <dl className="divide-y">
              <SummaryRow label="Original">
                <BalanceAmount block={cif} field="original" kind="cif" />
              </SummaryRow>
              <SummaryRow label="Used through BOEs (debited)">
                <BalanceAmount block={cif} field="debited" kind="cif" />
              </SummaryRow>
              <SummaryRow label="Of which previous-owner BOEs (deducted)">
                <span className="tabular-nums">{formatCif(summary.previous_owner_debit_cif)}</span>
              </SummaryRow>
              <SummaryRow label="Reserved for customers (allotted)">
                <BalanceAmount block={cif} field="allotted" kind="cif" />
              </SummaryRow>
              <SummaryRow label="Invoiced">
                <BalanceAmount block={cif} field="invoiced" kind="cif" />
              </SummaryRow>
            </dl>
            {showAvailable ? (
              <RemainingFigure>
                <BalanceAmount block={cif} field="available" kind="cif" emphasis />
              </RemainingFigure>
            ) : null}
          </>
        ) : (
          <div className="space-y-2 text-sm">
            <p className="text-muted-foreground">CIF figures are not computed for this licence.</p>
            <StatusPill status={cif.status} />
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function QuantityPanel({ summary, showAvailable }: BalanceSummaryPanelsProps) {
  const qty = summary.qty;
  const unitLabel = qty.unit ? ` (${qty.unit})` : "";
  const unverified = qty.status === "UNIT_UNVERIFIED";

  return (
    <Card>
      <CardHeader>
        <CardTitle>{`Quantity${unitLabel}`}</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {unverified ? (
          <div role="note" className="space-y-2 rounded-md border border-sky-300 bg-sky-50 p-3 text-sm text-sky-900 dark:border-sky-700 dark:bg-sky-950/40 dark:text-sky-100">
            <p className="font-medium">Unit unverified</p>
            <p>{qty.note ?? "Quantity figures are withheld until the unit is verified."}</p>
            {summary.unverified_qty_items.length > 0 ? (
              <ul className="list-inside list-disc text-xs">
                {summary.unverified_qty_items.map((item) => (
                  <li key={item.item_id}>{`SR ${item.sr}: unit recorded as ${item.unit_raw ?? "not recorded"}`}</li>
                ))}
              </ul>
            ) : null}
          </div>
        ) : (
          <dl className="divide-y">
            <SummaryRow label="Original">
              <BalanceAmount block={qty} field="original" kind="qty" />
            </SummaryRow>
            <SummaryRow label="Used through BOEs (debited)">
              <BalanceAmount block={qty} field="debited" kind="qty" />
            </SummaryRow>
            <SummaryRow label="Of which previous-owner BOEs (deducted)">
              <span className="tabular-nums">{formatQty(summary.previous_owner_debit_qty, qty.unit)}</span>
            </SummaryRow>
            <SummaryRow label="Reserved for customers (allotted)">
              <BalanceAmount block={qty} field="allotted" kind="qty" />
            </SummaryRow>
            <SummaryRow label="Invoiced">
              <BalanceAmount block={qty} field="invoiced" kind="qty" />
            </SummaryRow>
          </dl>
        )}
        {showAvailable ? (
          <RemainingFigure>
            <BalanceAmount block={qty} field="available" kind="qty" emphasis />
          </RemainingFigure>
        ) : null}
      </CardContent>
    </Card>
  );
}
