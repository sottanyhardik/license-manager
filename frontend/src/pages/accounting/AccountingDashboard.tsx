import { useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
    AlertTriangle, ArrowDownLeft, ArrowUpRight, Banknote, Coins, FileClock, HandCoins, Landmark, Receipt, Scale,
    TrendingUp, Wallet,
} from "lucide-react";

import StatCard from "@/components/StatCard";
import { acctGet, acctKeys, type Money } from "@/api/accountingApi";

import { useAccounting } from "./AccountingContext";
import { formatMoney } from "./money";
import { QueryState } from "./ui";

interface Dashboard {
    sales: Money; purchases: Money; gross_profit: Money; net_profit: Money; bank_balance: Money; cash_balance: Money;
    receivables: Money; payables: Money; overdue_receivables: Money; overdue_payables: Money; draft_vouchers: number;
    unposted_invoices: number; unmatched_bank_lines: number; open_suspense: number; gst_net_payable: Money;
    tds_payable: Money; loan_outstanding: Money;
}

export default function AccountingDashboard() {
    const { entityId, scope } = useAccounting();
    const navigate = useNavigate();
    const q = useQuery({
        queryKey: acctKeys.of(entityId, "dashboard", scope.fy),
        queryFn: () => acctGet<Dashboard>("reports/dashboard/", scope),
    });
    const d = q.data;
    const money = (v: Money | undefined) => `₹ ${formatMoney(v)}`;
    return (
        <QueryState isLoading={q.isLoading} error={q.error}>
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
                    <section aria-label="Tax and loans" className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                        <StatCard compact label="GST net payable (FY)" value={money(d.gst_net_payable)} icon={Receipt}
                                  onClick={() => navigate("/accounting/reports/gst")} />
                        <StatCard compact label="TDS payable" value={money(d.tds_payable)} icon={HandCoins}
                                  onClick={() => navigate("/accounting/reports/tds")} />
                        <StatCard compact label="Loans outstanding (net)" value={money(d.loan_outstanding)} icon={Landmark}
                                  onClick={() => navigate("/accounting/loans")} />
                    </section>
                </div>
            )}
        </QueryState>
    );
}
