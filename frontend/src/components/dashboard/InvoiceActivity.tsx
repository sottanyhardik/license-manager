import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import type { InvoiceActivity as InvoiceActivityData, InvoiceStatus, SectionError } from "@/pages/dashboardContract";
import { isSectionError } from "@/pages/dashboardContract";
import { LIST_PATHS, tradeEditPath } from "./dashboardLinks";
import { formatCount, formatDate, formatMoney } from "./formatters";
import DashboardSection from "./DashboardSection";
import { sortRows, useTableSort } from "./tableSort";
import { SortableTh } from "./SortableTh";

const STATUS_LABEL: Record<InvoiceStatus, string> = {
    paid: "Paid",
    partially_paid: "Partially paid",
    unpaid: "Unpaid",
};

const NOT_TRACKED_LABEL: Record<string, string> = {
    draft: "Draft",
    pending: "Pending",
    confirmed: "Confirmed",
    posted: "Posted",
};

type SortKey = "invoice" | "date" | "direction" | "party" | "total" | "outstanding" | "status";

type InvoiceActivityProps = {
    section: InvoiceActivityData | SectionError | undefined;
    search: string;
    onRetry?: () => void;
    retrying?: boolean;
};

export default function InvoiceActivity({ section, search, onRetry, retrying = false }: InvoiceActivityProps) {
    const sort = useTableSort<SortKey>(null);
    if (!section) return null;

    if (retrying) {
        return <DashboardSection id="dashboard-invoices" title="Invoice activity" loading />;
    }

    if (isSectionError(section)) {
        return (
            <DashboardSection id="dashboard-invoices" title="Invoice activity" error={section.error} onRetry={onRetry} retrying={retrying} />
        );
    }

    const needle = search.trim().toLowerCase();
    const rows = section.recent.filter(
        (row) =>
            !needle ||
            row.invoice_number.toLowerCase().includes(needle) ||
            (row.party_name ?? "").toLowerCase().includes(needle),
    );
    const sorted = sortRows(rows, sort.sort, {
        invoice: (row) => row.invoice_number,
        date: (row) => row.invoice_date,
        direction: (row) => row.direction,
        party: (row) => row.party_name,
        total: (row) => Number(row.total_amount_inr),
        outstanding: (row) => Number(row.outstanding_inr),
        status: (row) => STATUS_LABEL[row.status],
    });

    const statusCounts: { label: string; value: number; tooltip: string }[] = [
        { label: "Total invoices", value: section.total, tooltip: "Trades with an invoice number, in scope." },
        { label: "Paid", value: section.paid, tooltip: "Settled amount is at least the invoice total." },
        { label: "Partially paid", value: section.partially_paid, tooltip: "Some amount settled, some still outstanding." },
        { label: "Unpaid", value: section.unpaid, tooltip: "Nothing settled yet." },
        { label: "Open", value: section.open, tooltip: "Partially paid plus unpaid invoices." },
    ];

    return (
        <DashboardSection
            id="dashboard-invoices"
            title="Invoice activity"
            description="Amounts in ₹ (INR), from trade invoices and their settlements"
            actions={
                <Link to={LIST_PATHS.trades} className="rounded-md text-xs font-medium text-blue-600 hover:underline focus-visible:ring-2 focus-visible:ring-ring dark:text-blue-400">
                    View all
                </Link>
            }
            empty={section.recent.length === 0}
            emptyTitle="No recent invoices"
        >
            <div className="grid grid-cols-2 gap-x-4 gap-y-3 border-b border-slate-200 px-4 py-3 text-xs dark:border-slate-800 sm:grid-cols-4">
                {statusCounts.map((count) => (
                    <div key={count.label} title={count.tooltip}>
                        <span className="block text-slate-500 dark:text-slate-400">{count.label}</span>
                        <span className="font-semibold tabular-nums text-slate-900 dark:text-slate-100">{formatCount(count.value)}</span>
                    </div>
                ))}
                <div>
                    <span className="block text-slate-500 dark:text-slate-400">Outstanding</span>
                    <span className="font-semibold tabular-nums text-slate-900 dark:text-slate-100">{formatMoney(section.outstanding_inr, "invoice")}</span>
                </div>
                <div>
                    <span className="block text-slate-500 dark:text-slate-400">Sales outstanding</span>
                    <span className="font-semibold tabular-nums text-slate-900 dark:text-slate-100">
                        {formatMoney(section.by_direction.sale.outstanding_inr, "invoice")}
                    </span>
                </div>
                <div>
                    <span className="block text-slate-500 dark:text-slate-400">Purchases outstanding</span>
                    <span className="font-semibold tabular-nums text-slate-900 dark:text-slate-100">
                        {formatMoney(section.by_direction.purchase.outstanding_inr, "invoice")}
                    </span>
                </div>
                <div>
                    <span className="block text-slate-500 dark:text-slate-400">Total invoiced</span>
                    <span className="font-semibold tabular-nums text-slate-900 dark:text-slate-100">{formatMoney(section.total_amount_inr, "invoice")}</span>
                </div>
                <div>
                    <span className="block text-slate-500 dark:text-slate-400">Settled</span>
                    <span className="font-semibold tabular-nums text-slate-900 dark:text-slate-100">{formatMoney(section.paid_inr, "invoice")}</span>
                </div>
            </div>

            {section.not_tracked.length > 0 && (
                <p className="border-b border-slate-200 px-4 py-2 text-xs text-slate-500 dark:border-slate-800 dark:text-slate-400">
                    Not tracked in this system: {section.not_tracked.map((state) => NOT_TRACKED_LABEL[state] ?? state).join(", ")}. Invoices show
                    paid, partially paid or unpaid only.
                </p>
            )}

            {section.recent.length > 0 && sorted.length === 0 && (
                <p className="p-4 text-sm text-slate-500 dark:text-slate-400">No invoices match the search.</p>
            )}
            {sorted.length > 0 && (
                <div className="max-h-96 overflow-auto">
                    <table className="w-full text-sm">
                        <caption className="sr-only">Recent invoices with outstanding amounts</caption>
                        <thead className="sticky top-0 z-10 bg-slate-50 dark:bg-slate-900">
                            <tr className="border-b border-slate-200 dark:border-slate-800">
                                <SortableTh label="Invoice" sortKey="invoice" ariaSort={sort.ariaSort("invoice")} onSort={sort.toggle} />
                                <SortableTh label="Date" sortKey="date" ariaSort={sort.ariaSort("date")} onSort={sort.toggle} />
                                <SortableTh label="Direction" sortKey="direction" ariaSort={sort.ariaSort("direction")} onSort={sort.toggle} />
                                <SortableTh label="Party" sortKey="party" ariaSort={sort.ariaSort("party")} onSort={sort.toggle} />
                                <SortableTh label="Total (₹)" sortKey="total" align="right" ariaSort={sort.ariaSort("total")} onSort={sort.toggle} />
                                <SortableTh label="Outstanding (₹)" sortKey="outstanding" align="right" ariaSort={sort.ariaSort("outstanding")} onSort={sort.toggle} />
                                <SortableTh label="Status" sortKey="status" ariaSort={sort.ariaSort("status")} onSort={sort.toggle} />
                            </tr>
                        </thead>
                        <tbody>
                            {sorted.map((row) => (
                                <tr key={row.id} className="border-t border-slate-200 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-900/50">
                                    <td className="px-4 py-2.5">
                                        <Link to={tradeEditPath(row.id)} className="rounded-sm font-medium text-blue-600 outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring dark:text-blue-400">
                                            {row.invoice_number}
                                        </Link>
                                    </td>
                                    <td className="whitespace-nowrap px-4 py-2.5 text-xs text-slate-500 dark:text-slate-400">{formatDate(row.invoice_date)}</td>
                                    <td className="px-4 py-2.5 text-xs capitalize text-slate-600 dark:text-slate-300">{row.direction}</td>
                                    <td className="max-w-[180px] truncate px-4 py-2.5 text-xs text-slate-900 dark:text-slate-100" title={row.party_name ?? undefined}>
                                        {row.party_name || "—"}
                                    </td>
                                    <td className="px-4 py-2.5 text-right text-xs tabular-nums">{formatMoney(row.total_amount_inr, "invoice")}</td>
                                    <td className="px-4 py-2.5 text-right text-xs tabular-nums">{formatMoney(row.outstanding_inr, "invoice")}</td>
                                    <td className="px-4 py-2.5">
                                        <Badge variant={row.status === "paid" ? "secondary" : row.status === "unpaid" ? "destructive" : "default"}>
                                            {STATUS_LABEL[row.status]}
                                        </Badge>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </DashboardSection>
    );
}
