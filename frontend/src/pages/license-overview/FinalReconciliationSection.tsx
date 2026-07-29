import { CheckCircle2, AlertTriangle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { ReconciliationSummary } from "@/pages/license-balance/types";
import { fmtNum } from "@/pages/license-balance/licenseBalanceHelpers";

interface FinalReconciliationSectionProps {
    reconciliation: ReconciliationSummary;
}

/**
 * Overview tab's Final Reconciliation section, from the `reconciliation`
 * object. Relocated (unchanged) from `pages/license-balance/` — still
 * backed by `useLicenseBalanceLedger`.
 */
export default function FinalReconciliationSection({ reconciliation }: FinalReconciliationSectionProps) {
    const rows: [string, string][] = [
        ["Financial Ledger Balance", fmtNum(reconciliation.financial_ledger_balance)],
        ["Customs Ledger Balance", fmtNum(reconciliation.customs_ledger_balance)],
        ["Balance Engine", fmtNum(reconciliation.balance_engine)],
        ["Difference", fmtNum(reconciliation.difference)],
        ["Tolerance", fmtNum(reconciliation.tolerance)],
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
                            <Badge variant={reconciliation.matched ? "success" : "destructive"} className="gap-1">
                                {reconciliation.matched ? (
                                    <>
                                        <CheckCircle2 className="size-3" /> MATCHED
                                    </>
                                ) : (
                                    <>
                                        <AlertTriangle className="size-3" /> DIFFERENCE FOUND
                                    </>
                                )}
                            </Badge>
                        </td>
                    </tr>
                </tbody>
            </table>
        </div>
    );
}
