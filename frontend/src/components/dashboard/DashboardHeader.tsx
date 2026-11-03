import { useEffect, useId, useState } from "react";
import { Link } from "react-router-dom";
import { Bell, RefreshCw, Search } from "lucide-react";

import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { AttentionRow } from "./attention";
import { formatClockTime, formatDate } from "./formatters";
import { RANGE_PRESETS, type RangePreset } from "./scope";

export type CompanyOption = { id: number; name: string };

type DashboardHeaderProps = {
    asOf: string | null;
    lastRefreshed: Date | null;
    refreshing: boolean;
    onRefresh: () => void;
    companies: CompanyOption[];
    companiesUnavailable: boolean;
    companyId: number | null;
    onCompanyChange: (companyId: number | null) => void;
    preset: RangePreset;
    onPresetChange: (preset: RangePreset) => void;
    search: string;
    onSearchChange: (value: string) => void;
    notifications: AttentionRow[] | null;
    asOfTimezone: string | null;
};

const SELECT_CLASS =
    "h-9 rounded-md border border-slate-300 bg-white px-2.5 text-sm text-slate-900 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none dark:border-slate-700 dark:bg-slate-950 dark:text-slate-100";

/** Bell button that lists the verified attention items. Same data as the attention centre. */
function NotificationButton({ items }: { items: AttentionRow[] | null }) {
    const [open, setOpen] = useState(false);
    const panelId = useId();
    const count = items?.length ?? 0;

    useEffect(() => {
        if (!open) return;
        const onKey = (event: KeyboardEvent) => {
            if (event.key === "Escape") setOpen(false);
        };
        document.addEventListener("keydown", onKey);
        return () => document.removeEventListener("keydown", onKey);
    }, [open]);

    return (
        <div className="relative">
            <Button
                type="button"
                variant="secondary"
                size="sm"
                aria-expanded={open}
                aria-controls={panelId}
                aria-label={`Notifications: ${count} open ${count === 1 ? "item" : "items"}`}
                onClick={() => setOpen((value) => !value)}
            >
                <Bell className="size-4" aria-hidden="true" />
                <span className="tabular-nums">{count}</span>
            </Button>
            {open && (
                <div
                    id={panelId}
                    className="absolute right-0 z-30 mt-2 w-80 max-w-[calc(100vw-2rem)] rounded-lg border border-slate-200 bg-white p-2 shadow-md dark:border-slate-800 dark:bg-slate-950"
                >
                    <p className="px-2 py-1 text-xs font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">Attention</p>
                    {count === 0 ? (
                        <p className="px-2 py-2 text-sm text-slate-600 dark:text-slate-300">No open exceptions in this scope.</p>
                    ) : (
                        <ul className="max-h-80 space-y-1 overflow-auto">
                            {items?.map((item) => (
                                <li key={item.key}>
                                    {item.href && !item.href.startsWith("#") ? (
                                        <Link
                                            to={item.href}
                                            onClick={() => setOpen(false)}
                                            className="flex items-center justify-between gap-3 rounded-md px-2 py-2 text-sm hover:bg-slate-50 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none dark:hover:bg-slate-900"
                                        >
                                            <span className="text-slate-900 dark:text-slate-100">{item.title}</span>
                                            <span className="font-semibold tabular-nums">{item.count}</span>
                                        </Link>
                                    ) : (
                                        <a
                                            href={item.href ?? "#dashboard-attention"}
                                            onClick={() => setOpen(false)}
                                            className="flex items-center justify-between gap-3 rounded-md px-2 py-2 text-sm hover:bg-slate-50 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none dark:hover:bg-slate-900"
                                        >
                                            <span className="text-slate-900 dark:text-slate-100">{item.title}</span>
                                            <span className="font-semibold tabular-nums">{item.count}</span>
                                        </a>
                                    )}
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            )}
        </div>
    );
}

export default function DashboardHeader({
    asOf,
    lastRefreshed,
    refreshing,
    onRefresh,
    companies,
    companiesUnavailable,
    companyId,
    onCompanyChange,
    preset,
    onPresetChange,
    search,
    onSearchChange,
    notifications,
    asOfTimezone,
}: DashboardHeaderProps) {
    const companySelectId = useId();
    const rangeSelectId = useId();
    const searchId = useId();

    const description = (
        <span className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span>As of {asOf ? formatDate(asOf) : "—"}{asOfTimezone ? ` (${asOfTimezone})` : ""}</span>
            <span aria-hidden="true" className="text-border">•</span>
            <span aria-live="polite">{refreshing ? "Refreshing…" : `Last refreshed ${formatClockTime(lastRefreshed)}`}</span>
        </span>
    );

    return (
        <div className="space-y-4">
            <PageHeader
                pretitle="Home"
                title="Dashboard"
                description={description}
                actions={
                    <div className="flex flex-wrap items-center justify-end gap-2">
                        <NotificationButton items={notifications} />
                        <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            onClick={onRefresh}
                            disabled={refreshing}
                            aria-label="Refresh dashboard data"
                        >
                            <RefreshCw className={cn("size-4", refreshing && "animate-spin")} aria-hidden="true" />
                            {refreshing ? "Refreshing" : "Refresh"}
                        </Button>
                    </div>
                }
            />

            <div className="flex flex-wrap items-end gap-3">
                <div className="flex min-w-[180px] flex-col gap-1">
                    <label htmlFor={companySelectId} className="text-xs font-medium text-slate-500 dark:text-slate-400">
                        Company
                    </label>
                    <select
                        id={companySelectId}
                        className={SELECT_CLASS}
                        value={companyId ?? ""}
                        onChange={(event) => onCompanyChange(event.target.value ? Number(event.target.value) : null)}
                        aria-describedby={companiesUnavailable ? `${companySelectId}-note` : undefined}
                    >
                        <option value="">All companies</option>
                        {companies.map((company) => (
                            <option key={company.id} value={company.id}>
                                {company.name}
                            </option>
                        ))}
                    </select>
                    {companiesUnavailable && (
                        <span id={`${companySelectId}-note`} className="text-xs text-amber-700 dark:text-amber-400">
                            Company list unavailable
                        </span>
                    )}
                </div>

                <div className="flex flex-col gap-1">
                    <label htmlFor={rangeSelectId} className="text-xs font-medium text-slate-500 dark:text-slate-400">
                        Activity date range
                    </label>
                    <select
                        id={rangeSelectId}
                        className={SELECT_CLASS}
                        value={preset}
                        onChange={(event) => onPresetChange(event.target.value as RangePreset)}
                    >
                        {RANGE_PRESETS.map((range) => (
                            <option key={range.value} value={range.value}>
                                {range.label}
                            </option>
                        ))}
                    </select>
                </div>

                <div className="flex min-w-[220px] flex-1 flex-col gap-1 sm:max-w-sm">
                    <label htmlFor={searchId} className="text-xs font-medium text-slate-500 dark:text-slate-400">
                        Search visible rows
                    </label>
                    <div className="relative">
                        <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-slate-400" aria-hidden="true" />
                        <Input
                            id={searchId}
                            type="search"
                            value={search}
                            onChange={(event) => onSearchChange(event.target.value)}
                            placeholder="Licence, BOE, item, invoice or party"
                            className="h-9 pl-8"
                        />
                    </div>
                </div>
            </div>
        </div>
    );
}
