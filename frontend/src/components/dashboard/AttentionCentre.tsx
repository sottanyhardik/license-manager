import { Link } from "react-router-dom";
import { ArrowRight, CheckCircle2 } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import type {
    AttentionItem,
    AttentionSeverity,
    LicenceExceptions,
    NotMonitoredItem,
    SectionError,
} from "@/pages/dashboardContract";
import { isSectionError } from "@/pages/dashboardContract";
import { buildAttentionRows } from "./attention";
import { licenceEditPath } from "./dashboardLinks";
import { formatCount } from "./formatters";

const ACTION_LINK_CLASS =
    "inline-flex items-center gap-1 rounded-md text-xs font-medium text-blue-600 hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none dark:text-blue-400";

const SEVERITY_BADGE: Record<AttentionSeverity, { label: string; variant: "destructive" | "default" | "secondary" }> = {
    high: { label: "High", variant: "destructive" },
    medium: { label: "Medium", variant: "default" },
    low: { label: "Low", variant: "secondary" },
};

/** Attention keys whose affected licences are listed inline (capped at 25 by the server). */
const EXCEPTION_LIST_KEYS: Partial<Record<string, keyof LicenceExceptions>> = {
    over_utilised: "over_utilised",
    expired_with_balance: "expired_with_balance",
    stale_expiry_flags: "stale_expiry_flags",
};

const LIST_CAP = 25;

type AttentionCentreProps = {
    items: AttentionItem[];
    notMonitored: NotMonitoredItem[];
    exceptions: LicenceExceptions | SectionError | undefined;
    companyId: number | null;
};

function LicenceList({
    row,
    exceptions,
    listKey,
}: {
    row: { count: number };
    exceptions: LicenceExceptions | SectionError | undefined;
    listKey: keyof LicenceExceptions;
}) {
    if (!exceptions) return null;
    if (isSectionError(exceptions)) {
        return <p className="mt-1 text-xs text-red-700 dark:text-red-400">Licence list unavailable: {exceptions.error}</p>;
    }
    const licences = exceptions[listKey];
    return (
        <details className="group w-full basis-full">
            <summary className="inline-flex cursor-pointer list-none items-center gap-1 rounded-md text-xs font-medium text-blue-600 hover:underline focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none dark:text-blue-400">
                Show licences ({formatCount(licences.length)} shown)
                <ArrowRight className="size-3 transition-transform group-open:rotate-90" aria-hidden="true" />
            </summary>
            {licences.length === 0 ? (
                <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">No licences listed.</p>
            ) : (
                <ul className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs sm:grid-cols-3">
                    {licences.map((licence) => (
                        <li key={licence.id}>
                            <Link to={licenceEditPath(licence.id)} className="rounded-sm text-blue-600 outline-none hover:underline focus-visible:ring-2 focus-visible:ring-ring dark:text-blue-400">
                                {licence.license_number}
                            </Link>
                        </li>
                    ))}
                </ul>
            )}
            {row.count > licences.length && (
                <p className="mt-2 text-xs text-slate-500 dark:text-slate-400">
                    Showing {formatCount(licences.length)} of {formatCount(row.count)}. The list is capped at {LIST_CAP}.
                </p>
            )}
        </details>
    );
}

export default function AttentionCentre({ items, notMonitored, exceptions, companyId }: AttentionCentreProps) {
    const rows = buildAttentionRows(items, companyId);

    return (
        <section id="dashboard-attention" aria-labelledby="dashboard-attention-title" className="scroll-mt-24 space-y-3">
            <div className="flex items-baseline justify-between gap-3">
                <h2 id="dashboard-attention-title" className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                    Attention required
                </h2>
                <p className="text-xs text-slate-500 dark:text-slate-400">Only verified counts are listed</p>
            </div>

            {rows.length === 0 ? (
                <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-3 text-sm text-slate-600 dark:border-slate-800 dark:bg-slate-950 dark:text-slate-300">
                    <CheckCircle2 className="size-4 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
                    No open exceptions in this scope.
                </div>
            ) : (
                <ul className="divide-y divide-slate-200 overflow-hidden rounded-lg border border-slate-200 bg-white dark:divide-slate-800 dark:border-slate-800 dark:bg-slate-950">
                    {rows.map((row) => {
                        const badge = SEVERITY_BADGE[row.severity];
                        return (
                            <li key={row.key} className="flex flex-wrap items-center gap-3 px-4 py-3">
                                <span className="w-12 shrink-0 text-right text-lg font-semibold tabular-nums text-slate-900 dark:text-slate-50">
                                    {formatCount(row.count)}
                                </span>
                                <div className="min-w-0 flex-1">
                                    <div className="flex flex-wrap items-center gap-2">
                                        <span className="text-sm font-medium text-slate-900 dark:text-slate-100">{row.title}</span>
                                        <Badge variant={badge.variant}>{badge.label}</Badge>
                                    </div>
                                    {row.description && (
                                        <p className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{row.description}</p>
                                    )}
                                </div>
                                {EXCEPTION_LIST_KEYS[row.key] ? (
                                    <LicenceList
                                        row={row}
                                        exceptions={exceptions}
                                        listKey={EXCEPTION_LIST_KEYS[row.key] as keyof LicenceExceptions}
                                    />
                                ) : (
                                    row.href &&
                                    (row.href.startsWith("#") ? (
                                        <a href={row.href} className={ACTION_LINK_CLASS}>
                                            {row.action}
                                            <ArrowRight className="size-3" aria-hidden="true" />
                                        </a>
                                    ) : (
                                        <Link to={row.href} className={ACTION_LINK_CLASS}>
                                            {row.action}
                                            <ArrowRight className="size-3" aria-hidden="true" />
                                        </Link>
                                    )))}
                            </li>
                        );
                    })}
                </ul>
            )}

            {notMonitored.length > 0 && (
                <div className="rounded-lg border border-dashed border-slate-300 px-4 py-3 dark:border-slate-700">
                    <p className="text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Not monitored on this dashboard</p>
                    <ul className="mt-2 space-y-1 text-xs text-slate-500 dark:text-slate-400">
                        {notMonitored.map((item) => (
                            <li key={item.key}>
                                <span className="font-medium text-slate-600 dark:text-slate-300">{item.key.replace(/_/g, " ")}:</span>{" "}
                                {item.reason}
                            </li>
                        ))}
                    </ul>
                </div>
            )}
        </section>
    );
}
