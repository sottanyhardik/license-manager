import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { CustomsLedgerRow, CustomsLedgerSummary } from "./types";
import { customsLedgerRowClass, customsStatusVariant, fmtDate, fmtNum } from "./licenseBalanceHelpers";

interface CustomsLedgerTableProps {
    rows: CustomsLedgerRow[];
    summary: CustomsLedgerSummary;
}

const HEADERS = [
    "Sr", "Date", "Type", "Doc Number", "BOE Number", "BOE Date", "Company", "Item",
    "Qty", "CIF USD", "Credit", "Debit", "Running Balance", "Status", "Remarks",
];

/**
 * "Customs Ledger — Running Balance": the SEPARATE running-CUSTOMS-
 * utilisation statement from `data.customs_ledger` (every BOE debits at its
 * FULL raw CIF, unconditionally — see the backend builder's docstring). This
 * is intentionally distinct from `CustomsLedgerSection.tsx`'s per-item
 * "Customs Ledger — Item Detail" table (HSN/available-qty breakdown) — the
 * two answer different questions and are never conflated.
 *
 * Mirrors the PDF's "Customs Summary" card + "Customs Ledger" table
 * (`_build_customs_ledger_elements`) so PDF/Excel/UI share one information
 * architecture.
 */
export default function CustomsLedgerTable({ rows, summary }: CustomsLedgerTableProps) {
    const summaryRows: [string, string][] = [
        ["Original Licence CIF", fmtNum(summary.opening_balance)],
        ["Total BOE CIF", fmtNum(summary.total_boe_cif)],
        ["Pending Allotment CIF", fmtNum(summary.total_pending_allotment_cif)],
        ["Available Balance", fmtNum(summary.computed_balance)],
        ["Balance Engine", fmtNum(summary.engine_balance)],
        ["Difference", fmtNum(summary.difference)],
    ];

    return (
        <div className="space-y-4">
            <div className="rounded-lg border border-border">
                <table className="w-full text-sm">
                    <tbody>
                        {summaryRows.map(([label, value]) => (
                            <tr key={label} className="border-t border-border/60 first:border-t-0">
                                <td className="px-3 py-2 text-muted-foreground">{label}</td>
                                <td className="px-3 py-2 text-right font-medium tabular-nums">{value}</td>
                            </tr>
                        ))}
                        <tr className="border-t border-border/60">
                            <td className="px-3 py-2 text-muted-foreground">Status</td>
                            <td className="px-3 py-2 text-right">
                                <Badge variant={summary.mismatched ? "destructive" : "success"}>
                                    {summary.mismatched ? "RECONCILIATION FAILED" : "MATCHED"}
                                </Badge>
                            </td>
                        </tr>
                    </tbody>
                </table>
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
