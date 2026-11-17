/**
 * Entity-wise accounting: each entity's own statutory books, side by side, from the same
 * `reports/dashboard/` endpoint per entity. Figures are never added across entities here;
 * group totals (with intercompany elimination) are the separate Consolidated report.
 */
import { Link, useNavigate } from "react-router-dom";
import { useQueries } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { acctGet, acctKeys, type AccountingDashboardData } from "@/api/accountingApi";

import { useAccounting } from "./AccountingContext";
import { Amount, Panel, QueryState } from "./ui";

export default function EntitySummary() {
    const { entities, entityId, setEntityId, fyRange } = useAccounting();
    const navigate = useNavigate();
    const results = useQueries({
        queries: entities.map((e) => ({
            queryKey: acctKeys.of(e.id, "dashboard", fyRange.start, fyRange.end),
            queryFn: () => acctGet<AccountingDashboardData>("reports/dashboard/", { entity: e.id, ...fyRange }),
        })),
    });
    const open = (id: number, to: string) => { setEntityId(id); navigate(to); };
    const metric = (label: string, pick: (d: AccountingDashboardData) => string) => ({ label, pick });
    const metrics = [
        metric("Net sales", (d) => d.sales), metric("Gross profit", (d) => d.gross_profit), metric("Net profit", (d) => d.net_profit),
        metric("Bank balance", (d) => d.bank_balance), metric("Cash balance", (d) => d.cash_balance),
        metric("Receivables", (d) => d.receivables), metric("Payables", (d) => d.payables),
    ];
    return (
        <Panel title={`Entity-wise books · ${fyRange.start} to ${fyRange.end}`} actions={
            <Link to="/accounting/reports/consolidated"><Button size="sm" variant="outline">Consolidated report →</Button></Link>}>
            <div className="overflow-x-auto rounded-lg border border-slate-200 bg-white">
                <table className="w-full text-sm">
                    <caption className="sr-only">Entity-wise summary</caption>
                    <thead className="bg-slate-50 text-[11px] uppercase tracking-wider text-slate-500">
                        <tr>
                            <th scope="col" className="px-3 py-2 text-left font-semibold">Entity</th>
                            {metrics.map((m) => <th key={m.label} scope="col" className="px-3 py-2 text-right font-semibold">{m.label}</th>)}
                            <th scope="col" className="px-3 py-2 text-right font-semibold">Unmatched bank lines</th>
                            <th scope="col" className="px-3 py-2"><span className="sr-only">Open</span></th>
                        </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                        {entities.map((e, i) => {
                            const r = results[i];
                            return (
                                <tr key={e.id} className={e.id === entityId ? "bg-blue-50/50" : "hover:bg-blue-50/40"}>
                                    <th scope="row" className="px-3 py-1.5 text-left font-medium">{e.name}
                                        {e.gstin && <span className="block text-[11px] font-normal text-slate-500">{e.gstin}</span>}</th>
                                    {r?.isLoading || r?.error ? (
                                        <td colSpan={metrics.length + 1} className="px-3 py-1.5">
                                            <QueryState isLoading={!!r?.isLoading} error={r?.error} onRetry={() => void r?.refetch()}>{null}</QueryState>
                                        </td>
                                    ) : r?.data && (<>
                                        {metrics.map((m) => <td key={m.label} className="px-3 py-1.5 text-right tabular-nums"><Amount value={m.pick(r.data!)} /></td>)}
                                        <td className="px-3 py-1.5 text-right tabular-nums">{r.data.unmatched_bank_lines}</td>
                                    </>)}
                                    <td className="px-3 py-1.5 text-right">
                                        <Button size="sm" variant="ghost" onClick={() => open(e.id, "/accounting/dashboard")}>Open books</Button>
                                    </td>
                                </tr>
                            );
                        })}
                        {entities.length === 0 && <tr><td colSpan={metrics.length + 3} className="px-3 py-6 text-center text-slate-500">No entity books are active.</td></tr>}
                    </tbody>
                </table>
            </div>
            <p className="mt-2 text-xs text-slate-500">Each row is one entity's separate books for the selected period. Rows are not added together; see the Consolidated report for group figures after intercompany elimination.</p>
        </Panel>
    );
}
