import { useState } from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import type { BoeActivity as BoeActivityData, BoeRow, SectionError } from "@/pages/dashboardContract";
import { isSectionError } from "@/pages/dashboardContract";
import { boeEditPath, LIST_PATHS } from "./dashboardLinks";
import { formatCount, formatDate, formatDateTime } from "./formatters";
import DashboardSection from "./DashboardSection";

/** Full row at `xl`, so the eight BOE columns fit without clipping. Below `xl` the table scrolls inside the card. */
export const BOE_CARD_CLASS = "xl:col-span-2";
import { sortRows, useTableSort } from "./tableSort";
import { SortableTh } from "./SortableTh";

type SortKey = "number" | "date" | "importer" | "invoice" | "allotments" | "items" | "modified";

type TabKey = "recent" | "pending" | "modified";

type BoeActivityProps = {
    section: BoeActivityData | SectionError | undefined;
    search: string;
    onRetry?: () => void;
    retrying?: boolean;
};

const SORT_ACCESSORS = {
    number: (row: BoeRow) => row.bill_of_entry_number,
    date: (row: BoeRow) => row.bill_of_entry_date,
    importer: (row: BoeRow) => row.company_name,
    invoice: (row: BoeRow) => row.invoice_no,
    allotments: (row: BoeRow) => row.allotment_links,
    items: (row: BoeRow) => row.licence_items,
    modified: (row: BoeRow) => row.modified_on,
};

function BoeTable({ rows, sort }: { rows: BoeRow[]; sort: ReturnType<typeof useTableSort<SortKey>> }) {
    const sorted = sortRows(rows, sort.sort, SORT_ACCESSORS);
    return (
        <div
            role="region"
            aria-label="Bills of entry, scroll horizontally for all columns"
            tabIndex={0}
            className="max-h-96 overflow-auto focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
        >
            <table className="w-full min-w-[1000px] text-sm">
                <caption className="sr-only">Bills of entry</caption>
                <thead className="sticky top-0 z-10 bg-slate-50 dark:bg-slate-900">
                    <tr className="border-b border-slate-200 dark:border-slate-800">
                        <SortableTh label="BOE #" sortKey="number" ariaSort={sort.ariaSort("number")} onSort={sort.toggle} />
                        <SortableTh label="Date" sortKey="date" ariaSort={sort.ariaSort("date")} onSort={sort.toggle} />
                        <SortableTh label="Importer" sortKey="importer" ariaSort={sort.ariaSort("importer")} onSort={sort.toggle} />
                        <SortableTh label="Invoice" sortKey="invoice" ariaSort={sort.ariaSort("invoice")} onSort={sort.toggle} />
                        <SortableTh label="Allotments" sortKey="allotments" align="right" ariaSort={sort.ariaSort("allotments")} onSort={sort.toggle} />
                        <SortableTh label="Licence items" sortKey="items" align="right" ariaSort={sort.ariaSort("items")} onSort={sort.toggle} />
                        <th scope="col" className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">Mapping</th>
                        <SortableTh label="Modified" sortKey="modified" ariaSort={sort.ariaSort("modified")} onSort={sort.toggle} />
                    </tr>
                </thead>
                <tbody>
                    {sorted.map((row) => (
                        <tr key={row.id} className="border-t border-slate-200 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-900/50">
                            <td className="px-4 py-2.5">
                                <Link to={boeEditPath(row.id)} className="rounded-sm font-medium text-blue-600 outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring dark:text-blue-400">
                                    {row.bill_of_entry_number || "—"}
                                </Link>
                            </td>
                            <td className="whitespace-nowrap px-4 py-2.5 text-xs text-slate-500 dark:text-slate-400">{formatDate(row.bill_of_entry_date)}</td>
                            <td className="max-w-[180px] truncate px-4 py-2.5 text-xs text-slate-900 dark:text-slate-100" title={row.company_name ?? undefined}>
                                {row.company_name || "—"}
                            </td>
                            <td className="px-4 py-2.5 text-xs text-slate-600 dark:text-slate-300">{row.invoice_no || "—"}</td>
                            <td className="px-4 py-2.5 text-right text-xs tabular-nums">{formatCount(row.allotment_links)}</td>
                            <td className="px-4 py-2.5 text-right text-xs tabular-nums">{formatCount(row.licence_items)}</td>
                            <td className="px-4 py-2.5">
                                <Badge variant={row.mapping_status === "mapped" ? "secondary" : "destructive"}>
                                    {row.mapping_status === "mapped" ? "Mapped" : "Pending licence"}
                                </Badge>
                            </td>
                            <td className="whitespace-nowrap px-4 py-2.5 text-xs text-slate-500 dark:text-slate-400">{formatDateTime(row.modified_on)}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

export default function BoeActivity({ section, search, onRetry, retrying = false }: BoeActivityProps) {
    const [tab, setTab] = useState<TabKey>("recent");
    const sort = useTableSort<SortKey>(null);
    if (!section) return null;

    if (retrying) {
        return <DashboardSection id="dashboard-boe" title="BOE activity" className={BOE_CARD_CLASS} loading />;
    }

    if (isSectionError(section)) {
        return (
            <DashboardSection id="dashboard-boe" title="BOE activity" className={BOE_CARD_CLASS} error={section.error} onRetry={onRetry} retrying={retrying} />
        );
    }

    const needle = search.trim().toLowerCase();
    const matches = (row: BoeRow) =>
        !needle ||
        row.bill_of_entry_number.toLowerCase().includes(needle) ||
        (row.company_name ?? "").toLowerCase().includes(needle) ||
        (row.invoice_no ?? "").toLowerCase().includes(needle);

    const recent = section.recent.filter(matches);
    const pending = section.pending_mapping.filter(matches);
    const modified = section.recently_modified.filter(matches);

    const counts: { label: string; value: number; href?: string; tooltip: string }[] = [
        { label: "Total BOEs", value: section.total, href: "/bill-of-entries", tooltip: "Bills of entry in scope, filtered by bill date and company." },
        { label: "Linked to allotment", value: section.linked_to_allotment, tooltip: "BOEs with at least one allotment link." },
        { label: "Direct", value: section.direct, tooltip: "BOEs with no allotment link." },
        { label: "Pending licence mapping", value: section.pending_licence_mapping, tooltip: "BOEs with no licence item rows, so they cannot be debited against a licence." },
        { label: "Without invoice no.", value: section.without_invoice_no, tooltip: "BOEs where the invoice number is blank." },
    ];

    return (
        <DashboardSection
            id="dashboard-boe"
            title="BOE activity"
            className={BOE_CARD_CLASS}
            description={`${formatCount(section.total)} bills of entry in scope`}
            actions={
                <Link to={LIST_PATHS.boes} className="rounded-md text-xs font-medium text-blue-600 hover:underline focus-visible:ring-2 focus-visible:ring-ring dark:text-blue-400">
                    View all
                </Link>
            }
        >
            <div className="grid grid-cols-2 gap-x-4 gap-y-2 border-b border-slate-200 px-4 py-3 text-xs dark:border-slate-800 sm:grid-cols-5">
                {counts.map((count) => (
                    <div key={count.label} title={count.tooltip}>
                        <span className="block text-slate-500 dark:text-slate-400">{count.label}</span>
                        <span className="font-semibold tabular-nums text-slate-900 dark:text-slate-100">{formatCount(count.value)}</span>
                    </div>
                ))}
            </div>

            <Tabs value={tab} onValueChange={(value) => setTab(value as TabKey)} className="gap-0">
                <div className="border-b border-slate-200 px-4 py-2 dark:border-slate-800">
                    <TabsList>
                        <TabsTrigger value="recent">Recent</TabsTrigger>
                        <TabsTrigger value="pending">Pending licence mapping</TabsTrigger>
                        <TabsTrigger value="modified">Recently modified</TabsTrigger>
                    </TabsList>
                </div>
                <TabsContent value="recent" className="mt-0">
                    {recent.length === 0 ? (
                        <p className="p-4 text-sm text-slate-500 dark:text-slate-400">{needle ? "No BOEs match the search." : "No recent BOE records."}</p>
                    ) : (
                        <BoeTable rows={recent} sort={sort} />
                    )}
                </TabsContent>
                <TabsContent value="pending" className="mt-0">
                    <p className="px-4 pt-3 text-xs text-slate-500 dark:text-slate-400">
                        Showing up to {section.pending_mapping.length} of {formatCount(section.pending_licence_mapping)} BOEs with no licence rows.
                    </p>
                    {pending.length === 0 ? (
                        <p className="p-4 text-sm text-slate-500 dark:text-slate-400">{needle ? "No pending BOEs match the search." : "No BOEs are pending licence mapping."}</p>
                    ) : (
                        <BoeTable rows={pending} sort={sort} />
                    )}
                </TabsContent>
                <TabsContent value="modified" className="mt-0">
                    {modified.length === 0 ? (
                        <p className="p-4 text-sm text-slate-500 dark:text-slate-400">{needle ? "No BOEs match the search." : "No recently modified BOEs."}</p>
                    ) : (
                        <BoeTable rows={modified} sort={sort} />
                    )}
                </TabsContent>
            </Tabs>
        </DashboardSection>
    );
}
