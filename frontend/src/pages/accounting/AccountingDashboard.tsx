import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import {
    AlertTriangle, ArrowDownLeft, ArrowUpRight, Banknote, Coins, FileClock, HandCoins, Landmark, Receipt, Scale,
    TrendingUp, Wallet,
} from "lucide-react";

import StatCard from "@/components/StatCard";
import {
    acctGet, acctKeys, type AccountingDashboardData, type AuditEvent, type Money, type Paged, type Voucher,
} from "@/api/accountingApi";

import { useAccounting } from "./AccountingContext";
import { formatMoney } from "./money";
import { Amount, DataGrid, Panel, QueryState, StatusBadge } from "./ui";

type Dashboard = AccountingDashboardData;

const AUDIT_LINK: Record<string, string> = { Voucher: "vouchers", Invoice: "invoices" };

function RecentVouchers() {
    const { entityId, fyRange } = useAccounting();
    const q = useQuery({
        queryKey: acctKeys.of(entityId, "vouchers", "recent", fyRange.start, fyRange.end),
        queryFn: () => acctGet<Paged<Voucher>>("vouchers/", { entity: entityId, ...fyRange, page_size: 8 }),
    });
    return (
        <Panel title="Recent vouchers" actions={<Link className="text-xs text-blue-700 hover:underline" to="/accounting/vouchers">All vouchers →</Link>}>
            <QueryState isLoading={q.isLoading} error={q.error} onRetry={() => void q.refetch()}>
                <DataGrid rows={q.data?.results ?? []} rowKey={(v) => v.id} caption="Recent vouchers" empty="No vouchers in this period yet." columns={[
                    { key: "d", header: "Date", cell: (v) => v.date },
                    { key: "n", header: "Number", cell: (v) => <Link className="font-medium text-blue-700 hover:underline" to={`/accounting/vouchers/${v.id}`}>{v.number ?? "Draft"}</Link> },
                    { key: "t", header: "Type", cell: (v) => v.voucher_type.replace(/_/g, " ") },
                    { key: "a", header: "Amount", numeric: true, cell: (v) => <Amount value={v.total} /> },
                    { key: "s", header: "Status", cell: (v) => <StatusBadge status={v.status} /> },
                ]} />
            </QueryState>
        </Panel>
    );
}

function RecentActivity() {
    const { entityId } = useAccounting();
    const q = useQuery({
        queryKey: acctKeys.of(entityId, "audit", "recent"),
        queryFn: () => acctGet<Paged<AuditEvent>>("audit/", { entity: entityId, page_size: 10 }),
    });
    const rows = q.data?.results ?? [];
    return (
        <Panel title="Recent accounting activity">
            <QueryState isLoading={q.isLoading} error={q.error} onRetry={() => void q.refetch()}>
                {rows.length === 0 ? <p className="text-sm text-slate-500">No activity recorded for this entity yet.</p> : (
                    <ol className="space-y-1.5 border-l-2 border-slate-200 pl-3 text-xs text-slate-600">
                        {rows.map((a) => {
                            const base = AUDIT_LINK[a.object_type];
                            const label = `${a.object_type} #${a.object_id ?? ""}`;
                            return (
                                <li key={a.id}>
                                    <span className="font-semibold text-slate-800">{a.action.replace(/_/g, " ").toLowerCase()}</span>
                                    {" · "}{base && a.object_id ? <Link className="text-blue-700 hover:underline" to={`/accounting/${base}/${a.object_id}`}>{label}</Link> : label}
                                    {" · "}{a.actor ?? "system"} · <time dateTime={a.at}>{a.at.slice(0, 16).replace("T", " ")}</time>
                                </li>
                            );
                        })}
                    </ol>)}
            </QueryState>
        </Panel>
    );
}

export default function AccountingDashboard() {
    const { entityId, scope, entities } = useAccounting();
    const navigate = useNavigate();
    const q = useQuery({
        queryKey: acctKeys.of(entityId, "dashboard", scope.start, scope.end),
        queryFn: () => acctGet<Dashboard>("reports/dashboard/", scope),
    });
    const d = q.data;
    const money = (v: Money | undefined) => `₹ ${formatMoney(v)}`;
    return (
        <QueryState isLoading={q.isLoading} error={q.error} onRetry={() => void q.refetch()}>
            {d && (
                <div className="space-y-6">
                    <section aria-label="Performance" className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
                        <StatCard compact label="Net sales" value={money(d.sales)} icon={TrendingUp} tone="primary"
                                  onClick={() => navigate("/accounting/reports/profit-loss")} />
                        <StatCard compact label="Purchases" value={money(d.purchases)} icon={Receipt}
                                  onClick={() => navigate("/accounting/reports/register?kind=purchase")} />
                        <StatCard compact label="Gross profit" value={money(d.gross_profit)} icon={Scale} tone="success"
                                  onClick={() => navigate("/accounting/reports/profit-loss")} />
                        <StatCard compact label="Net profit" value={money(d.net_profit)} icon={Coins}
                                  tone={d.net_profit.startsWith("-") ? "danger" : "success"}
                                  onClick={() => navigate("/accounting/reports/profit-loss")} />
                    </section>
                    <section aria-label="Position" className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
                        <StatCard compact label="Bank balance" value={money(d.bank_balance)} icon={Landmark}
                                  onClick={() => navigate("/accounting/banking")} />
                        <StatCard compact label="Cash balance" value={money(d.cash_balance)} icon={Wallet}
                                  onClick={() => navigate("/accounting/reports/cash-book")} />
                        <StatCard compact label="Receivables" value={money(d.receivables)} icon={ArrowDownLeft}
                                  secondaryValue={`Overdue ₹ ${formatMoney(d.overdue_receivables)}`}
                                  onClick={() => navigate("/accounting/reports/receivables-ageing")} />
                        <StatCard compact label="Payables" value={money(d.payables)} icon={ArrowUpRight}
                                  secondaryValue={`Overdue ₹ ${formatMoney(d.overdue_payables)}`}
                                  onClick={() => navigate("/accounting/reports/payables-ageing")} />
                    </section>
                    <section aria-label="Work queue" className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
                        <StatCard compact label="Unposted bills" value={d.unposted_invoices} icon={FileClock}
                                  tone={d.unposted_invoices ? "warning" : "primary"} onClick={() => navigate("/accounting/trades?status=PENDING")} />
                        <StatCard compact label="Unmatched bank lines" value={d.unmatched_bank_lines} icon={Banknote}
                                  tone={d.unmatched_bank_lines ? "warning" : "primary"} onClick={() => navigate("/accounting/banking")} />
                        <StatCard compact label="Open suspense" value={d.open_suspense} icon={AlertTriangle}
                                  tone={d.open_suspense ? "danger" : "primary"} onClick={() => navigate("/accounting/banking/suspense")} />
                        <StatCard compact label="Draft vouchers" value={d.draft_vouchers} icon={FileClock}
                                  onClick={() => navigate("/accounting/vouchers?status=DRAFT")} />
                    </section>
                    <section aria-label="Advances" className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                        <StatCard compact label="Advances paid (unallocated)" value={money(d.advances_paid)} icon={ArrowUpRight}
                                  onClick={() => navigate("/accounting/payments")} />
                        <StatCard compact label="Advances received (unallocated)" value={money(d.advances_received)} icon={ArrowDownLeft}
                                  onClick={() => navigate("/accounting/payments")} />
                    </section>
                    <section aria-label="Tax and loans" className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                        <StatCard compact label="GST net payable (FY)" value={money(d.gst_net_payable)} icon={Receipt}
                                  onClick={() => navigate("/accounting/reports/gst")} />
                        <StatCard compact label="TDS payable" value={money(d.tds_payable)} icon={HandCoins}
                                  onClick={() => navigate("/accounting/reports/tds")} />
                        <StatCard compact label="Loans outstanding (net)" value={money(d.loan_outstanding)} icon={Landmark}
                                  onClick={() => navigate("/accounting/loans")} />
                    </section>
                    <div className="grid gap-4 xl:grid-cols-[3fr_2fr]">
                        <RecentVouchers />
                        <RecentActivity />
                    </div>
                    {entities.length > 1 && (
                        <p className="text-sm text-slate-600">
                            {entities.length} entities keep separate books. <Link className="font-medium text-blue-700 hover:underline" to="/accounting/entities">Compare them side by side →</Link>
                        </p>)}
                </div>
            )}
        </QueryState>
    );
}
