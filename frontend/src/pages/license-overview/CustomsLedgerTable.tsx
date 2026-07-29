import { ArrowRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { CustomsLedgerRow, CustomsLedgerSummary } from "@/pages/license-balance/types";
import { customsLedgerRowClass, customsStatusVariant, fmtDate, fmtNum } from "@/pages/license-balance/licenseBalanceHelpers";
import SummaryCard from "./SummaryCard";

interface CustomsLedgerTableProps {
    rows: CustomsLedgerRow[];
    summary: CustomsLedgerSummary;
}

const HEADERS = [
    "Sr", "Date", "Type", "Doc Number", "BOE Number", "BOE Date", "Company", "Item",
    "Qty", "CIF USD", "Credit", "Debit", "Running Balance", "Status", "Remarks",
];

/** One step of the Available Balance flow — a compact value chip, optionally
 * preceded by an inline operator ("−" for a deduction, "=" for a resulting
 * total). Laid out horizontally (wrapping on narrow screens) rather than as
 * a tall vertical stack, so the whole flow fits in one shallow strip. */
function FlowStep({
    label,
    value,
    operator,
    emphasize,
}: {
    label: string;
    value: string;
    operator?: "−" | "=";
    emphasize?: boolean;
}) {
    return (
        <div className="flex items-center gap-2">
            {operator && (
                <div className="flex items-center gap-1 text-xs font-semibold text-muted-foreground">
                    <ArrowRight className="size-3.5 shrink-0" />
                    <span>{operator}</span>
                </div>
            )}
            <div
                className={cn(
                    "flex items-baseline gap-1.5 whitespace-nowrap rounded-md border px-2.5 py-1",
                    emphasize ? "border-primary/40 bg-primary/5" : "border-border/70 bg-card"
                )}
            >
                <span className="text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</span>
                <span className={cn("text-sm font-bold tabular-nums", emphasize ? "text-primary" : "text-foreground")}>
                    {value}
                </span>
            </div>
        </div>
    );
}

/**
 * Overview tab's "Customs Ledger — Running Balance": the SEPARATE
 * running-CUSTOMS-utilisation statement from `data.customs_ledger` (every
 * BOE debits at its FULL raw CIF, unconditionally — see the backend
 * builder's docstring). This is intentionally distinct from
 * `CustomsLedgerSection.tsx`'s per-item "Customs Ledger — Item Detail" table
 * (HSN/available-qty breakdown) — the two answer different questions and
 * are never conflated.
 *
 * Mirrors the PDF's "Customs Summary" card + "Customs Ledger" table
 * (`_build_customs_ledger_elements`) so PDF/Excel/UI share one information
 * architecture.
 *
 * Relocated (unchanged) from `pages/license-balance/` — still backed by
 * `useLicenseBalanceLedger`.
 */
export default function CustomsLedgerTable({ rows, summary }: CustomsLedgerTableProps) {
    return (
        <div className="space-y-3">
            {/* Available Balance flow: Original CIF -> (-) Total BOE CIF ->
                Remaining After BOE -> (-) Pending/Unlinked Allotted CIF ->
                Available Balance. Horizontal + wrapping, so it's one shallow
                strip instead of a tall column. Every value is read straight
                off `summary` (computed server-side) — nothing is re-derived
                here. The card grid below only repeats the figures NOT
                already visible in this flow (Balance Engine/Difference/
                Status), to avoid showing the same number twice. */}
            <div className="rounded-lg border border-border/70 bg-muted/10 px-3 py-2.5">
                <div className="flex flex-wrap items-center gap-2">
                    <FlowStep label="Original Licence CIF" value={fmtNum(summary.opening_balance)} />
                    <FlowStep label="Total BOE CIF" value={fmtNum(summary.total_boe_cif)} operator="−" />
                    <FlowStep label="Remaining After BOE" value={fmtNum(summary.remaining_after_boe)} operator="=" />
                    <FlowStep label="Pending / Unlinked Allotted CIF" value={fmtNum(summary.total_pending_allotment_cif)} operator="−" />
                    <FlowStep label="Available Balance" value={fmtNum(summary.computed_balance)} operator="=" emphasize />
                </div>
            </div>

            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                <SummaryCard label="Available Balance" value={fmtNum(summary.computed_balance)} variant="primary" size="lg" />
                <SummaryCard label="Balance Engine" value={fmtNum(summary.engine_balance)} size="lg" />
                <SummaryCard
                    label="Difference"
                    value={fmtNum(summary.difference)}
                    variant={summary.mismatched ? "danger" : "success"}
                />
                <div className="rounded-lg border border-border/70 bg-card px-3 py-2.5">
                    <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">Status</div>
                    <div className="mt-1">
                        <Badge variant={summary.mismatched ? "destructive" : "success"}>
                            {summary.mismatched ? "Reconciliation Failed" : "Reconciled"}
                        </Badge>
                    </div>
                </div>
            </div>

            <div className="overflow-x-auto rounded-lg border border-border">
                <table className="w-full text-sm">
                    <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
                        <tr>
                            {HEADERS.map((h) => (
                                <th key={h} scope="col" className="whitespace-nowrap px-3 py-2 text-left font-semibold">
                                    {h}
                                </th>
                            ))}
                        </tr>
                    </thead>
                    <tbody>
                        {rows.length === 0 && (
                            <tr>
                                <td colSpan={HEADERS.length} className="px-3 py-6 text-center text-muted-foreground">
                                    No customs ledger rows.
                                </td>
                            </tr>
                        )}
                        {rows.map((row) => (
                            <tr
                                key={row.sr}
                                className={cn("border-t border-border/60", customsLedgerRowClass(row.row_kind, row.mismatched))}
                            >
                                <td className="px-3 py-2">{row.sr}</td>
                                <td className="whitespace-nowrap px-3 py-2">{fmtDate(row.date)}</td>
                                <td className="whitespace-nowrap px-3 py-2 font-medium">{row.type}</td>
                                <td className="px-3 py-2">{row.document_number ?? "—"}</td>
                                <td className="px-3 py-2">{row.boe_number ?? "—"}</td>
                                <td className="whitespace-nowrap px-3 py-2">{fmtDate(row.boe_date)}</td>
                                <td className="px-3 py-2">{row.company ?? "—"}</td>
                                <td className="px-3 py-2">{row.item_name ?? "—"}</td>
                                <td className="px-3 py-2 text-right">{fmtNum(row.qty)}</td>
                                <td className="px-3 py-2 text-right">{fmtNum(row.cif_usd)}</td>
                                <td className="px-3 py-2 text-right">{fmtNum(row.credit)}</td>
                                <td className="px-3 py-2 text-right">{fmtNum(row.debit)}</td>
                                <td className="px-3 py-2 text-right font-medium">{fmtNum(row.running_balance)}</td>
                                <td className="px-3 py-2">
                                    <Badge variant={customsStatusVariant(row.status)}>{row.status}</Badge>
                                </td>
                                <td className="px-3 py-2">{row.remarks ?? "—"}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}
