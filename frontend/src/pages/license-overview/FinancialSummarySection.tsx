import { Badge } from "@/components/ui/badge";
import type { FinancialLedgerSummary } from "@/pages/license-balance/types";
import { fmtNum } from "@/pages/license-balance/licenseBalanceHelpers";

interface FinancialSummarySectionProps {
    summary: FinancialLedgerSummary;
}

/**
 * Overview tab's Financial Summary section: a small key-value table from
 * `financial_ledger.summary`. Relocated (unchanged) from
 * `pages/license-balance/` — still backed by `useLicenseBalanceLedger`.
 */
export default function FinancialSummarySection({ summary }: FinancialSummarySectionProps) {
    const rows: [string, string][] = [
        ["Original Licence CIF", fmtNum(summary.opening_balance)],
        ["Total BOE Debits", fmtNum(summary.total_boe_debit)],
        ["Outstanding Active Allotments", fmtNum(summary.total_allotment_debit)],
        ...(summary.total_trade_debit > 0 ? ([["Total Trade Debits", fmtNum(summary.total_trade_debit)]] as [string, string][]) : []),
        ["Current Available Balance", fmtNum(summary.computed_balance)],
        ["Licence Balance Engine", fmtNum(summary.engine_balance)],
        ["Difference", fmtNum(summary.difference)],
        ["Tolerance", fmtNum(summary.tolerance)],
    ];

    return (
        <div className="rounded-lg border border-border">
            <table className="w-full text-sm">
                <tbody>
                    {rows.map(([label, value]) => (
                        <tr key={label} className="border-t border-border/60 first:border-t-0">
                            <td className="px-3 py-2 text-muted-foreground">{label}</td>
                            <td className="px-3 py-2 text-right font-medium tabular-nums">{value}</td>
                        </tr>
                    ))}
                    <tr className="border-t border-border/60">
                        <td className="px-3 py-2 text-muted-foreground">Status</td>
                        <td className="px-3 py-2 text-right">
                            <Badge variant={summary.mismatched ? "destructive" : "success"}>
                                {summary.mismatched ? "FAILED" : "MATCHED"}
                            </Badge>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    );
}
