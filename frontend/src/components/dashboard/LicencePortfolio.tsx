import { lazy, Suspense } from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import type {
    ExpiringLicence,
    ExpiryBandKey,
    LicencePortfolio as LicencePortfolioData,
    SectionError,
} from "@/pages/dashboardContract";
import { isSectionError } from "@/pages/dashboardContract";
import { bandTarget, licenceEditPath, licenceList, SECTION_ANCHORS, withinTarget } from "./dashboardLinks";
import { formatCount, formatDate, formatDaysToExpiry, formatMoney } from "./formatters";
import DashboardSection from "./DashboardSection";
import type { BarPlotDatum } from "./BarPlot";
import { sortRows, useTableSort } from "./tableSort";
import { SortableTh } from "./SortableTh";

const BarPlot = lazy(() => import("./BarPlot"));

const BAND_LABEL: Record<ExpiryBandKey, string> = {
    expired: "Expired",
    d0_7: "0–7 days",
    d8_15: "8–15 days",
    d16_30: "16–30 days",
    d31_60: "31–60 days",
    over_60: "Over 60 days",
    inactive: "Inactive",
    no_expiry: "No expiry date",
};

const BAND_COLOUR: Record<ExpiryBandKey, string> = {
    expired: "#991b1b",
    d0_7: "#dc2626",
    d8_15: "#f97316",
    d16_30: "#f59e0b",
    d31_60: "#64748b",
    over_60: "#94a3b8",
    inactive: "#e2e8f0",
    no_expiry: "#cbd5e1",
};

const WITHIN_DAYS = [7, 15, 30, 60] as const;

type ExpiringKey = "licence" | "expiry" | "days" | "balance";

type LicencePortfolioProps = {
    portfolio: LicencePortfolioData | SectionError | undefined;
    expiring: ExpiringLicence[] | SectionError | undefined;
    asOf: string;
    companyId: number | null;
    search: string;
};

function CountLink({ label, value, href, tooltip }: { label: string; value: number; href?: string; tooltip: string }) {
    const content = (
        <>
            <span className="block text-xs text-slate-500 dark:text-slate-400" title={tooltip}>
                {label}
            </span>
            <span className="block text-base font-semibold tabular-nums text-slate-900 dark:text-slate-50">
                {formatCount(value)}
            </span>
        </>
    );
    return href ? (
        <Link
            to={href}
            className="rounded-md px-2 py-1 outline-none hover:bg-slate-50 focus-visible:ring-2 focus-visible:ring-ring dark:hover:bg-slate-900"
        >
            {content}
        </Link>
    ) : (
        <div className="px-2 py-1">{content}</div>
    );
}

export default function LicencePortfolio({ portfolio, expiring, asOf, companyId, search }: LicencePortfolioProps) {
    const sort = useTableSort<ExpiringKey>({ key: "days", direction: "ascending" });

    if (!portfolio) return null;
    if (isSectionError(portfolio)) {
        return (
            <DashboardSection id="dashboard-licence-portfolio" title="Licence portfolio" error={portfolio.error} />
        );
    }

    const bands = portfolio.bands.map((band) => ({
        key: band.key,
        name: BAND_LABEL[band.key],
        count: band.count,
        href: bandTarget(band.key, asOf, companyId),
    }));

    const rows = Array.isArray(expiring) ? expiring : [];
    const needle = search.trim().toLowerCase();
    const filtered = needle
        ? rows.filter((row) => row.license_number.toLowerCase().includes(needle))
        : rows;
    const sortedRows = sortRows(filtered, sort.sort, {
        licence: (row) => row.license_number,
        expiry: (row) => row.license_expiry_date,
        days: (row) => row.days_to_expiry,
        balance: (row) => Number(row.balance_cif),
    });

    return (
        <div className="space-y-4">
            <div className="flex flex-wrap items-stretch gap-x-2 gap-y-1 rounded-lg border border-slate-200 bg-white p-2 dark:border-slate-800 dark:bg-slate-950">
                <CountLink
                    label="Missing DGFT (live balance < 200)"
                    value={portfolio.missing_dgft}
                    href={licenceList({ is_null: true, is_expired: "all" }, companyId)}
                    tooltip="Null DFIA: the licence list's live balance is below 200. The licence list is the source of truth for this figure."
                />
                <CountLink
                    label="Expiring ≤ 30 d (usable)"
                    value={portfolio.expiring_usable_30d}
                    href={SECTION_ANCHORS.expiring}
                    tooltip="Active licences expiring within 30 days whose live financial balance is at least 100. Listed below."
                />
                {portfolio.stale_expiry_flags > 0 && (
                    <CountLink
                        label="Stale expiry flags"
                        value={portfolio.stale_expiry_flags}
                        href={SECTION_ANCHORS.attention}
                        tooltip="Stored expiry flag disagrees with the expiry date. Listed in the attention centre."
                    />
                )}
            </div>

            <div className="flex flex-wrap items-center gap-2" aria-label="Licences expiring within">
                <span className="text-xs font-medium text-slate-500 dark:text-slate-400">Expiring within:</span>
                {WITHIN_DAYS.map((days) => (
                    <Link
                        key={days}
                        to={withinTarget(days, asOf, companyId)}
                        className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 px-3 py-1 text-xs font-medium text-slate-700 outline-none hover:bg-slate-50 focus-visible:ring-2 focus-visible:ring-ring dark:border-slate-700 dark:text-slate-200 dark:hover:bg-slate-900"
                    >
                        {days} days
                        <span className="tabular-nums text-slate-900 dark:text-slate-50">
                            {formatCount(portfolio.within[String(days) as "7" | "15" | "30" | "60"])}
                        </span>
                    </Link>
                ))}
            </div>

            <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <div className="rounded-lg border border-slate-200 p-3 dark:border-slate-800">
                    <div role="img" aria-label="Licence count by expiry band. The table lists the same counts.">
                        <Suspense fallback={<Skeleton className="h-56 w-full" />}>
                            <BarPlot
                                data={bands.map((band): BarPlotDatum => ({ name: band.name, value: band.count, colour: BAND_COLOUR[band.key] }))}
                                layout="horizontal"
                                height={224}
                            />
                        </Suspense>
                    </div>
                </div>
                <div className="overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-800">
                    <table className="w-full text-sm">
                        <caption className="sr-only">Licences by expiry band</caption>
                        <thead className="bg-slate-50 text-left text-xs font-semibold uppercase tracking-wide text-slate-600 dark:bg-slate-900/50 dark:text-slate-300">
                            <tr className="border-b border-slate-200 dark:border-slate-800">
                                <th scope="col" className="px-4 py-2">Expiry band</th>
                                <th scope="col" className="px-4 py-2 text-right">Licences</th>
                            </tr>
                        </thead>
                        <tbody>
                            {bands.map((band) => (
                                <tr key={band.key} className="border-t border-slate-200 dark:border-slate-800">
                                    <th scope="row" className="px-4 py-2 text-left text-xs font-normal text-slate-700 dark:text-slate-300">
                                        <span className="inline-block size-2.5 rounded-sm align-middle" style={{ background: BAND_COLOUR[band.key] }} aria-hidden="true" />
                                        <span className="ml-2">{band.name}</span>
                                    </th>
                                    <td className="px-4 py-2 text-right tabular-nums">
                                        {band.href ? (
                                            <Link to={band.href} className="font-medium text-blue-600 hover:underline dark:text-blue-400">
                                                {formatCount(band.count)}
                                            </Link>
                                        ) : (
                                            formatCount(band.count)
                                        )}
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            </div>

            <DashboardSection
                id="dashboard-expiring-licences"
                title="Expiring licences"
                description={
                    Array.isArray(expiring)
                        ? `Active, expiring within 30 days, live balance at least 100 (${sortedRows.length} shown)`
                        : undefined
                }
                error={isSectionError(expiring) ? expiring.error : undefined}
                empty={Array.isArray(expiring) && rows.length === 0}
                emptyTitle="No licences expiring within 30 days with usable balance"
                actions={
                    <Button asChild variant="secondary" size="sm">
                        <Link to={withinTarget(30, asOf, companyId)}>
                            Open licences
                        </Link>
                    </Button>
                }
            >
                {sortedRows.length === 0 && rows.length > 0 ? (
                    <p className="p-4 text-sm text-slate-500 dark:text-slate-400">No rows match the search.</p>
                ) : (
                    <div className="max-h-96 overflow-auto">
                        <table className="w-full text-sm">
                            <caption className="sr-only">Expiring licences, soonest first by default</caption>
                            <thead className="sticky top-0 z-10 bg-slate-50 dark:bg-slate-900">
                                <tr className="border-b border-slate-200 dark:border-slate-800">
                                    <SortableTh label="Licence" sortKey="licence" ariaSort={sort.ariaSort("licence")} onSort={sort.toggle} />
                                    <SortableTh label="Expiry" sortKey="expiry" ariaSort={sort.ariaSort("expiry")} onSort={sort.toggle} />
                                    <SortableTh label="Days" sortKey="days" align="right" ariaSort={sort.ariaSort("days")} onSort={sort.toggle} />
                                    <SortableTh label="Balance (FC)" sortKey="balance" align="right" ariaSort={sort.ariaSort("balance")} onSort={sort.toggle} />
                                    <th scope="col" className="px-4 py-2.5 text-left text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">SION norms</th>
                                </tr>
                            </thead>
                            <tbody>
                                {sortedRows.map((row) => (
                                    <tr key={row.id} className="border-t border-slate-200 hover:bg-slate-50 dark:border-slate-800 dark:hover:bg-slate-900/50">
                                        <td className="px-4 py-2.5 font-medium">
                                            <Link to={licenceEditPath(row.id)} className="rounded-sm text-blue-600 outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring dark:text-blue-400">
                                                {row.license_number}
                                            </Link>
                                        </td>
                                        <td className="whitespace-nowrap px-4 py-2.5 text-xs text-slate-500 dark:text-slate-400">{formatDate(row.license_expiry_date)}</td>
                                        <td className="px-4 py-2.5 text-right text-xs tabular-nums">
                                            <Badge variant={row.days_to_expiry <= 7 ? "destructive" : "secondary"}>{formatDaysToExpiry(row.days_to_expiry)}</Badge>
                                        </td>
                                        <td className="px-4 py-2.5 text-right text-xs tabular-nums">{formatMoney(row.balance_cif, "cif")}</td>
                                        <td className="px-4 py-2.5 text-xs text-slate-600 dark:text-slate-300">{row.sion_norms.join(", ") || "—"}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </DashboardSection>
        </div>
    );
}
