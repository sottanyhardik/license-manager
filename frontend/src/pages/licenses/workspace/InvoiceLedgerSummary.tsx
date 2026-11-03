import type { ReactNode } from "react";
import { ArrowLeftRight, ReceiptText, ScrollText, TriangleAlert, Wallet } from "lucide-react";
import { cn } from "@/lib/utils";
import { isZeroDecimal } from "@/pages/licence-balances/format";
import { formatCifAmount, formatInrAmount } from "./invoiceLedgerFormat";
import type { InvoiceLedgerSummary as LedgerSummary } from "./types";

type Tone = "purchase" | "sale" | "balance" | "neutral";

const TONE_CLASS: Record<Tone, string> = {
  purchase: "bg-success/10 text-success",
  sale: "bg-destructive/10 text-destructive",
  balance: "bg-info/10 text-info",
  neutral: "bg-muted text-muted-foreground",
};

interface SummaryCardProps {
  label: string;
  tone: Tone;
  icon: ReactNode;
  value: ReactNode;
  lines: string[];
}

function SummaryCard({ label, tone, icon, value, lines }: SummaryCardProps) {
  return (
    <div className="flex min-w-0 items-start gap-3 rounded-xl border bg-card p-4 shadow-sm">
      <span aria-hidden="true" className={cn("flex size-9 shrink-0 items-center justify-center rounded-lg", TONE_CLASS[tone])}>
        {icon}
      </span>
      <div className="min-w-0 space-y-1">
        <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{label}</p>
        <div className="text-xl font-semibold text-foreground tabular-nums">{value}</div>
        {lines.map((line) => (
          <p key={line} className="text-xs break-words text-muted-foreground tabular-nums">
            {line}
          </p>
        ))}
      </div>
    </div>
  );
}

/**
 * Four licence totals and the reconciliation notes under them. The totals come
 * from the backend. CIF (in the licence currency) and INR bill values are shown
 * side by side and never combined.
 */
export default function InvoiceLedgerSummaryCards({ summary }: { summary: LedgerSummary }) {
  const currency = summary.currency;
  const difference = summary.canonical_vs_net_sale_difference;
  const showDifference = difference !== undefined && difference !== null && difference.trim() !== "" && !isZeroDecimal(difference);
  const unmatchedCount = summary.unmatched_notes;

  return (
    <section aria-label="Licence totals" className="flex flex-col gap-3">
      <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-4">
        <SummaryCard
          label="Total purchase"
          tone="purchase"
          icon={<Wallet className="size-4" />}
          value={
            <>
              <span>{formatCifAmount(summary.net_purchase_cif)}</span>{" "}
              <span className="text-sm font-medium text-muted-foreground">{currency}</span>
            </>
          }
          lines={[
            `Bill ₹ ${formatInrAmount(summary.net_purchase_bill_inr)}`,
            `Gross ${formatCifAmount(summary.gross_purchase_cif)} · adjustments ${formatCifAmount(summary.purchase_adjustments_cif)}`,
          ]}
        />
        <SummaryCard
          label="Total sale"
          tone="sale"
          icon={<ReceiptText className="size-4" />}
          value={
            <>
              <span>{formatCifAmount(summary.net_sale_cif)}</span>{" "}
              <span className="text-sm font-medium text-muted-foreground">{currency}</span>
            </>
          }
          lines={[
            `Bill ₹ ${formatInrAmount(summary.net_sale_bill_inr)}`,
            `Gross ${formatCifAmount(summary.gross_sale_cif)} · credit/debit notes ${formatCifAmount(summary.sale_adjustments_cif)}`,
            ...(summary.internal_row_count
              ? [`Internal trades, not external: ${formatCifAmount(summary.gross_internal_sale_cif ?? "0.00")}`]
              : []),
          ]}
        />
        <SummaryCard
          label="Current balance"
          tone="balance"
          icon={<ScrollText className="size-4" />}
          value={
            <>
              <span>{formatCifAmount(summary.current_balance_cif)}</span>{" "}
              <span className="text-sm font-medium text-muted-foreground">{currency}</span>
            </>
          }
          lines={["Net purchase − net sale (external trades only)"]}
        />
        <SummaryCard
          label="Net bill difference"
          tone="neutral"
          icon={<ArrowLeftRight className="size-4" />}
          value={
            <>
              <span className="text-sm font-medium text-muted-foreground">₹</span>{" "}
              <span>{formatInrAmount(summary.net_bill_difference_inr)}</span>
            </>
          }
          lines={["Net purchase bill − net sale bill"]}
        />
      </div>

      {showDifference && (
        <div
          data-testid="reconciliation-difference"
          className="flex gap-2 rounded-lg border border-warning/50 bg-warning/10 p-3 text-sm text-foreground"
        >
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-warning" />
          <p>
            The balance engine counts {formatCifAmount(summary.canonical_sale_cif)} as sale; the net sale here is{" "}
            {formatCifAmount(summary.net_sale_cif)}. The difference of {formatCifAmount(difference)} is credit notes the
            engine does not yet net.
          </p>
        </div>
      )}

      {unmatchedCount > 0 && (
        <div
          data-testid="reconciliation-unmatched"
          className="flex gap-2 rounded-lg border border-destructive/50 bg-destructive/5 p-3 text-sm text-foreground"
        >
          <TriangleAlert aria-hidden="true" className="mt-0.5 size-4 shrink-0 text-destructive" />
          <p>
            {unmatchedCount} credit or debit {unmatchedCount === 1 ? "note has" : "notes have"} no matching original invoice
            and {unmatchedCount === 1 ? "is" : "are"} not netted. Unmatched CIF: {formatCifAmount(summary.unmatched_note_cif)}.
          </p>
        </div>
      )}
    </section>
  );
}
