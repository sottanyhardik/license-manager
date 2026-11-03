import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import type { AllotmentActivity as AllotmentActivityData, AllotmentActivityRow, AllotmentStatus, SectionError } from "@/pages/dashboardContract";
import { isSectionError } from "@/pages/dashboardContract";
import { allotmentPath, licenceOverviewPath } from "./dashboardLinks";
import { formatCount, formatDate, formatMoney, formatQuantity } from "./formatters";
import DashboardSection from "./DashboardSection";
import { sortRows, useTableSort } from "./tableSort";
import { SortableTh } from "./SortableTh";

/** Labels describe what the engine reports. "Fully utilised" means every item's CIF is matched by a BOE allocation. */
const STATUS_LABEL: Record<AllotmentStatus, string> = {
    open: "Open",
    partly_consumed: "Partly utilised",
    consumed: "Fully utilised",
    boe_linked: "BOE linked, no allocation",
};

const STATUS_VARIANT: Record<AllotmentStatus, "secondary" | "default" | "destructive" | "outline"> = {
    open: "secondary",
    partly_consumed: "default",
    consumed: "outline",
    boe_linked: "outline",
};

type SortKey = "created" | "reference" | "company" | "licence" | "item" | "original" | "allotted" | "consumed" | "reserved" | "status";

type AllotmentActivityProps = {
    section: AllotmentActivityData | SectionError | undefined;
    search: string;
    allotmentsHref: string;
    onRetry?: () => void;
    retrying?: boolean;
};

/** Full row at `xl`, so every column fits without clipping. Below `xl` the table scrolls inside the card. */
export const ALLOTMENT_CARD_CLASS = "xl:col-span-2";

const SORT_ACCESSORS = {
    created: (row: AllotmentActivityRow) => row.created_on,
    reference: (row: AllotmentActivityRow) => row.id,
    company: (row: AllotmentActivityRow) => row.company_name,
    licence: (row: AllotmentActivityRow) => row.licences[0]?.license_number ?? "",
    item: (row: AllotmentActivityRow) => row.item_name,
    original: (row: AllotmentActivityRow) => Number(row.original_quantity),
    allotted: (row: AllotmentActivityRow) => Number(row.allotted_cif),
    consumed: (row: AllotmentActivityRow) => Number(row.consumed_cif),
    reserved: (row: AllotmentActivityRow) => Number(row.reserved_cif),
    status: (row: AllotmentActivityRow) => STATUS_LABEL[row.status],
};

function matchesSearch(row: AllotmentActivityRow, needle: string): boolean {
    return (
        row.item_name.toLowerCase().includes(needle) ||
        (row.company_name ?? "").toLowerCase().includes(needle) ||
        row.reference.toLowerCase().includes(needle) ||
        row.licences.some((licence) => licence.license_number.toLowerCase().includes(needle))
    );
}

function LicenceCell({ row }: { row: AllotmentActivityRow }) {
    const [first] = row.licences;
    if (!first) return <span className="text-slate-500 dark:text-slate-400">—</span>;
    return (
        <span className="flex flex-wrap items-center gap-x-1.5">
            <Link
                to={licenceOverviewPath(first.id)}
                className="rounded-sm font-medium text-blue-600 outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring dark:text-blue-400"
            >
                {first.license_number}
            </Link>
            {row.licence_count > 1 && (
                <span className="text-xs text-slate-500 dark:text-slate-400" title={row.licences.map((licence) => licence.license_number).join(", ")}>
                    +{row.licence_count - 1} more
                </span>
            )}
        </span>
    );
}

export default function AllotmentActivity({ section, search, allotmentsHref, onRetry, retrying = false }: AllotmentActivityProps) {
    const sort = useTableSort<SortKey>(null);
    if (!section) return null;

    if (retrying) {
        return <DashboardSection id="dashboard-allotments" title="Allotment activity" className={ALLOTMENT_CARD_CLASS} loading />;
    }

    if (isSectionError(section)) {
        return (
            <DashboardSection
                id="dashboard-allotments"
                title="Allotment activity"
                className={ALLOTMENT_CARD_CLASS}
                error={section.error}
                onRetry={onRetry}
                retrying={retrying}
            />
        );
    }

    const needle = search.trim().toLowerCase();
    const rows = section.recent.filter((row) => !needle || matchesSearch(row, needle));
    const sorted = sortRows(rows, sort.sort, SORT_ACCESSORS);

    return (
        <DashboardSection
            id="dashboard-allotments"
            title="Allotment activity"
            className={ALLOTMENT_CARD_CLASS}
            description={`${formatCount(section.total)} allotments in scope · latest ${section.recent.length}`}
            actions={
                <Link to={allotmentsHref} className="rounded-md text-xs font-medium text-blue-600 hover:underline focus-visible:ring-2 focus-visible:ring-ring dark:text-blue-400">
                    View all
                </Link>
            }
            empty={section.recent.length === 0}
            emptyTitle="No recent allotments"
        >
            <div className="grid grid-cols-2 gap-x-4 gap-y-2 border-b border-slate-200 px-4 py-3 text-xs dark:border-slate-800 sm:grid-cols-4">
                {(Object.keys(STATUS_LABEL) as AllotmentStatus[]).map((status) => (
                    <div key={status}>
                        <span className="block text-slate-500 dark:text-slate-400">{STATUS_LABEL[status]}</span>
                        <span className="font-semibold tabular-nums text-slate-900 dark:text-slate-100">{formatCount(section.counts[status])}</span>
                    </div>
                ))}
            </div>
            {section.recent.length > 0 && sorted.length === 0 && (
                <p className="p-4 text-sm text-slate-500 dark:text-slate-400">No allotments match the search.</p>
            )}
            {sorted.length > 0 && (
                <div
                    role="region"
                    aria-label="Recent allotments, scroll horizontally for all columns"
                    tabIndex={0}
                    className="max-h-[32rem] overflow-auto rounded-sm focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none"
                >
                    <table className="w-full min-w-[1100px] text-sm">
                        <caption className="sr-only">Recent allotments with CIF utilisation, reservation and status</caption>
                        <thead className="sticky top-0 z-10 bg-slate-50 dark:bg-slate-900">
                            <tr className="border-b border-slate-200 dark:border-slate-800">
                                <SortableTh label="Reference" sortKey="reference" ariaSort={sort.ariaSort("reference")} onSort={sort.toggle} />
                                <SortableTh label="Date" sortKey="created" ariaSort={sort.ariaSort("created")} onSort={sort.toggle} />
                                <SortableTh label="Customer" sortKey="company" ariaSort={sort.ariaSort("company")} onSort={sort.toggle} />
                                <SortableTh label="Licence" sortKey="licence" ariaSort={sort.ariaSort("licence")} onSort={sort.toggle} />
                                <SortableTh label="Item" sortKey="item" ariaSort={sort.ariaSort("item")} onSort={sort.toggle} />
                                <SortableTh label="Original qty" sortKey="original" align="right" ariaSort={sort.ariaSort("original")} onSort={sort.toggle} />
                                <SortableTh label="Allocated CIF (FC)" sortKey="allotted" align="right" ariaSort={sort.ariaSort("allotted")} onSort={sort.toggle} />
                                <SortableTh label="Utilised CIF (FC)" sortKey="consumed" align="right" ariaSort={sort.ariaSort("consumed")} onSort={sort.toggle} />
                                <SortableTh label="Remaining reservation" sortKey="reserved" align="right" ariaSort={sort.ariaSort("reserved")} onSort={sort.toggle} />
                                <SortableTh label="Status" sortKey="status" ariaSort={sort.ariaSort("status")} onSort={sort.toggle} />
                            </tr>
                        </thead>
                        <tbody>
                            {sorted.map((row) => (
                                <tr key={row.id} className="border-t border-slate-200 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-900/50">
                                    <td className="whitespace-nowrap px-4 py-2.5">
                                        <Link
                                            to={allotmentPath(row.id)}
                                            className="rounded-sm font-medium text-blue-600 outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring dark:text-blue-400"
                                        >
                                            {row.reference}
                                        </Link>
                                    </td>
                                    <td className="whitespace-nowrap px-4 py-2.5 text-xs text-slate-500 dark:text-slate-400">{formatDate(row.created_on)}</td>
                                    <td className="max-w-[180px] truncate px-4 py-2.5 text-xs text-slate-900 dark:text-slate-100" title={row.company_name ?? undefined}>
                                        {row.company_name ?? "—"}
                                    </td>
                                    <td className="whitespace-nowrap px-4 py-2.5 text-xs">
                                        <LicenceCell row={row} />
                                    </td>
                                    <td className="max-w-[200px] truncate px-4 py-2.5 text-sm text-slate-900 dark:text-slate-100" title={row.item_name}>
                                        {row.item_name}
                                    </td>
                                    <td className="px-4 py-2.5 text-right text-xs tabular-nums">
                                        <span className="block whitespace-nowrap">{formatQuantity(row.original_quantity)}</span>
                                        {Number(row.unplaced_quantity) > 0 && (
                                            <span
                                                className="block whitespace-nowrap text-[11px] text-slate-500 dark:text-slate-400"
                                                title="Requested but not yet placed on any licence item."
                                            >
                                                unplaced {formatQuantity(row.unplaced_quantity)}
                                            </span>
                                        )}
                                    </td>
                                    <td className="whitespace-nowrap px-4 py-2.5 text-right text-xs tabular-nums">{formatMoney(row.allotted_cif, "cif")}</td>
                                    <td className="whitespace-nowrap px-4 py-2.5 text-right text-xs tabular-nums">{formatMoney(row.consumed_cif, "cif")}</td>
                                    <td className="px-4 py-2.5 text-right text-xs tabular-nums">
                                        <span className="block whitespace-nowrap">{formatMoney(row.reserved_cif, "cif")}</span>
                                        <span className="block whitespace-nowrap text-[11px] text-slate-500 dark:text-slate-400">
                                            qty {formatQuantity(row.remaining_quantity)}
                                        </span>
                                        {Number(row.not_reserved_cif) > 0 && (
                                            <span
                                                className="block whitespace-nowrap text-[11px] text-amber-800 dark:text-amber-300"
                                                title="CIF the engine neither reserves nor counts as utilised. It is non-zero only for BOE-linked allotments (ISS-008)."
                                            >
                                                Not reserved {formatMoney(row.not_reserved_cif, "cif")}
                                            </span>
                                        )}
                                    </td>
                                    <td className="whitespace-nowrap px-4 py-2.5">
                                        <Badge variant={STATUS_VARIANT[row.status]}>{STATUS_LABEL[row.status]}</Badge>
                                        <span className="mt-1 block text-[11px] text-slate-500 dark:text-slate-400">
                                            {row.boe_count === 0 ? "No BOE" : `${formatCount(row.boe_count)} BOE${row.boe_count === 1 ? "" : "s"}`}
                                        </span>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                        <tfoot className="border-t-2 border-slate-300 bg-slate-50 text-xs dark:border-slate-700 dark:bg-slate-900/60">
                            <tr>
                                <th scope="row" colSpan={6} className="px-4 py-2.5 text-left font-semibold text-slate-700 dark:text-slate-200">
                                    Total, all allotments in scope
                                </th>
                                <td className="px-4 py-2.5 text-right font-semibold tabular-nums">{formatMoney(section.totals.allotted_cif, "cif")}</td>
                                <td className="px-4 py-2.5 text-right font-semibold tabular-nums">{formatMoney(section.totals.consumed_cif, "cif")}</td>
                                <td className="px-4 py-2.5 text-right font-semibold tabular-nums">
                                    <span className="block">{formatMoney(section.totals.reserved_cif, "cif")}</span>
                                    {Number(section.totals.not_reserved_cif) > 0 && (
                                        <span className="block text-[11px] font-normal text-amber-800 dark:text-amber-300">
                                            Not reserved {formatMoney(section.totals.not_reserved_cif, "cif")}
                                        </span>
                                    )}
                                </td>
                                <td />
                            </tr>
                        </tfoot>
                    </table>
                </div>
            )}
            {sorted.length > 0 && (
                <p className="border-t border-slate-200 px-4 py-2 text-[11px] text-slate-500 dark:border-slate-800 dark:text-slate-400">
                    Allocated CIF = Utilised + Remaining reservation + Not reserved. Not reserved is non-zero only for BOE-linked allotments (ISS-008, DEC-010).
                    Figures come from the licence balance engine.
                </p>
            )}
        </DashboardSection>
    );
}
