import { useCallback, useContext, useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
    RefreshCw, LogIn, LogOut, Eye, PlusCircle, Pencil, Trash2,
    Download, Upload, FileDown, Search, ScrollText, FileX,
} from "lucide-react";

import api from "../../api/axios";
import { AuthContext } from "../../context/AuthContext";
import { getErrorMessage } from "../../utils/errorUtils";
import PageHeader from "@/components/PageHeader";
import EmptyState from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

// ─── Types ────────────────────────────────────────────────────────────────────

interface ActivityLogEntry {
    id: number | string;
    timestamp: string | null;
    username?: string | null;
    action: string;
    module?: string | null;
    resource_id?: number | string | null;
    description?: string | null;
    endpoint?: string | null;
    status_code?: number | null;
    ip_address?: string | null;
}

type FilterState = {
    username: string;
    action: string;
    module: string;
    date_from: string;
    date_to: string;
    search: string;
    limit: string;
};

// ─── Action metadata ──────────────────────────────────────────────────────────
// Tailwind classes only — no CSS var references

const ACTION_META: Record<string, { chipClass: string; Icon: typeof ScrollText }> = {
    LOGIN:    { chipClass: "bg-success/10 text-success",          Icon: LogIn },
    LOGOUT:   { chipClass: "bg-destructive/10 text-destructive",  Icon: LogOut },
    VIEW:     { chipClass: "bg-info/10 text-info",                Icon: Eye },
    CREATE:   { chipClass: "bg-success/10 text-success",          Icon: PlusCircle },
    UPDATE:   { chipClass: "bg-warning/10 text-warning",          Icon: Pencil },
    DELETE:   { chipClass: "bg-destructive/10 text-destructive",  Icon: Trash2 },
    DOWNLOAD: { chipClass: "bg-muted text-muted-foreground",      Icon: Download },
    UPLOAD:   { chipClass: "bg-muted text-muted-foreground",      Icon: Upload },
    EXPORT:   { chipClass: "bg-success/10 text-success",          Icon: FileDown },
    SEARCH:   { chipClass: "bg-muted text-muted-foreground",      Icon: Search },
};

const ACTIONS = Object.keys(ACTION_META);
const ALL = "__all__";

// ─── Utilities ────────────────────────────────────────────────────────────────

function fmtDate(ts: string | null | undefined): string {
    if (!ts) return "—";
    return new Date(ts).toLocaleString("en-IN", {
        day: "2-digit", month: "short", year: "numeric",
        hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
    });
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function ActivityLog() {
    const { user } = useContext(AuthContext);
    const [logs, setLogs] = useState<ActivityLogEntry[]>([]);
    const [loading, setLoading] = useState(false);
    const [filters, setFilters] = useState<FilterState>({
        username: "", action: "", module: "", date_from: "", date_to: "", search: "", limit: "200",
    });
    const abortRef = useRef<AbortController | null>(null);

    const fetchLogs = useCallback(async () => {
        if (abortRef.current) abortRef.current.abort();
        abortRef.current = new AbortController();
        setLoading(true);
        try {
            const params = Object.fromEntries(
                Object.entries(filters).filter(([, v]) => v !== ""),
            );
            const { data } = await api.get("masters/activity-logs/", {
                params,
                signal: abortRef.current.signal,
            });
            setLogs(Array.isArray(data) ? data : data.results ?? []);
        } catch (err: unknown) {
            const e = err as { name?: string };
            if (e.name !== "CanceledError" && e.name !== "AbortError") {
                toast.error(getErrorMessage(err));
            }
        } finally {
            setLoading(false);
        }
    }, [filters]);

    useEffect(() => { fetchLogs(); }, [fetchLogs]);

    const handleFilter = (key: keyof FilterState, value: string) =>
        setFilters(prev => ({ ...prev, [key]: value }));

    const clearFilters = () =>
        setFilters(f => ({ ...f, action: "", username: "", module: "", search: "", date_from: "", date_to: "" }));

    return (
        <>
            <PageHeader
                pretitle="Admin"
                title="Activity Log"
                description={user?.is_superuser ? "All user actions across the system" : "Your recent activity"}
                actions={
                    <Button variant="outline" onClick={fetchLogs} disabled={loading}>
                        <RefreshCw className={cn("size-4", loading && "animate-spin")} aria-hidden="true" />
                        Refresh
                    </Button>
                }
            />

            {/* ── Filters ──────────────────────────────────────────── */}
            <Card className="mb-3">
                <CardContent className="grid grid-cols-2 gap-3 py-3 md:grid-cols-3 lg:grid-cols-6">
                    {user?.is_superuser && (
                        <div>
                            <Label className="mb-1 text-xs" htmlFor="f-user">Username</Label>
                            <Input
                                id="f-user"
                                className="h-8"
                                placeholder="Search user…"
                                value={filters.username}
                                onChange={e => handleFilter("username", e.target.value)}
                            />
                        </div>
                    )}
                    <div>
                        <Label className="mb-1 text-xs" htmlFor="f-action">Action</Label>
                        <Select value={filters.action || ALL} onValueChange={v => handleFilter("action", v === ALL ? "" : v)}>
                            <SelectTrigger id="f-action" size="sm">
                                <SelectValue placeholder="All Actions" />
                            </SelectTrigger>
                            <SelectContent>
                                <SelectItem value={ALL}>All Actions</SelectItem>
                                {ACTIONS.map(a => <SelectItem key={a} value={a}>{a}</SelectItem>)}
                            </SelectContent>
                        </Select>
                    </div>
                    <div>
                        <Label className="mb-1 text-xs" htmlFor="f-module">Module</Label>
                        <Input
                            id="f-module"
                            className="h-8"
                            placeholder="e.g. licenses"
                            value={filters.module}
                            onChange={e => handleFilter("module", e.target.value)}
                        />
                    </div>
                    <div>
                        <Label className="mb-1 text-xs" htmlFor="f-from">From</Label>
                        <Input
                            id="f-from"
                            type="date"
                            className="h-8"
                            value={filters.date_from}
                            onChange={e => handleFilter("date_from", e.target.value)}
                        />
                    </div>
                    <div>
                        <Label className="mb-1 text-xs" htmlFor="f-to">To</Label>
                        <Input
                            id="f-to"
                            type="date"
                            className="h-8"
                            value={filters.date_to}
                            onChange={e => handleFilter("date_to", e.target.value)}
                        />
                    </div>
                    <div>
                        <Label className="mb-1 text-xs" htmlFor="f-search">Search</Label>
                        <Input
                            id="f-search"
                            className="h-8"
                            placeholder="IP, description…"
                            value={filters.search}
                            onChange={e => handleFilter("search", e.target.value)}
                        />
                    </div>
                </CardContent>
            </Card>

            {/* ── Action summary chips ──────────────────────────────── */}
            {!loading && logs.length > 0 && (
                <div className="mb-3 flex flex-wrap items-center gap-2">
                    {ACTIONS.filter(a => logs.some(l => l.action === a)).map(a => {
                        const m = ACTION_META[a];
                        const count = logs.filter(l => l.action === a).length;
                        const Icon = m.Icon;
                        const isActive = filters.action === a;
                        return (
                            <button
                                key={a}
                                type="button"
                                onClick={() => handleFilter("action", isActive ? "" : a)}
                                aria-pressed={isActive}
                                className={cn(
                                    "inline-flex cursor-pointer items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-opacity hover:opacity-80",
                                    m.chipClass,
                                    isActive && "ring-2 ring-current ring-offset-1",
                                )}
                            >
                                <Icon className="size-3.5" aria-hidden="true" />
                                {a} <strong>{count}</strong>
                            </button>
                        );
                    })}
                    <button
                        type="button"
                        className="ml-auto cursor-pointer text-xs text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:underline"
                        onClick={clearFilters}
                    >
                        Clear filters
                    </button>
                </div>
            )}

            {/* ── Log table ─────────────────────────────────────────── */}
            <Card>
                <CardContent className="p-0">
                    {loading ? (
                        <div className="flex flex-col items-center gap-2 p-12 text-center">
                            <RefreshCw className="size-6 animate-spin text-primary" aria-hidden="true" />
                            <span className="text-sm text-muted-foreground">Loading activity log…</span>
                        </div>
                    ) : logs.length === 0 ? (
                        <EmptyState
                            icon={FileX}
                            title="No activity records found"
                            description="Try adjusting the date range or filters"
                        />
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-border bg-muted/50 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                                        <th scope="col" className="px-3 py-2.5 w-[170px]">Time</th>
                                        {user?.is_superuser && <th scope="col" className="px-3 py-2.5">User</th>}
                                        <th scope="col" className="px-3 py-2.5 w-[120px]">Action</th>
                                        <th scope="col" className="px-3 py-2.5">Module</th>
                                        <th scope="col" className="px-3 py-2.5">Description</th>
                                        <th scope="col" className="px-3 py-2.5 w-[70px]">Status</th>
                                        <th scope="col" className="px-3 py-2.5 w-[130px]">IP</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {logs.map(log => {
                                        const m = ACTION_META[log.action] ?? { chipClass: "bg-muted text-muted-foreground", Icon: ScrollText };
                                        const Icon = m.Icon;
                                        const isError = log.status_code != null && log.status_code >= 400;
                                        return (
                                            <tr
                                                key={log.id}
                                                className={cn(
                                                    "border-b border-border/60",
                                                    isError && "bg-destructive/5",
                                                )}
                                            >
                                                <td className="whitespace-nowrap px-3 py-2 text-xs text-muted-foreground">
                                                    {fmtDate(log.timestamp)}
                                                </td>

                                                {user?.is_superuser && (
                                                    <td className="px-3 py-2">
                                                        <div className="flex items-center gap-2">
                                                            <div
                                                                className="flex size-6 shrink-0 items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary/70 text-[10px] font-bold text-white"
                                                                aria-hidden="true"
                                                            >
                                                                {(log.username || "?")[0].toUpperCase()}
                                                            </div>
                                                            <span className="text-[13px] font-medium">
                                                                {log.username || "—"}
                                                            </span>
                                                        </div>
                                                    </td>
                                                )}

                                                <td className="px-3 py-2">
                                                    <span className={cn(
                                                        "inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-medium",
                                                        m.chipClass,
                                                    )}>
                                                        <Icon className="size-3" aria-hidden="true" />
                                                        {log.action}
                                                    </span>
                                                </td>

                                                <td className="px-3 py-2 text-xs text-muted-foreground">
                                                    {log.module || "—"}
                                                    {log.resource_id && (
                                                        <span className="ml-1 text-muted-foreground/70">
                                                            #{log.resource_id}
                                                        </span>
                                                    )}
                                                </td>

                                                <td className="max-w-[300px] px-3 py-2 text-xs">
                                                    <span
                                                        className="block truncate"
                                                        title={log.description ?? log.endpoint ?? undefined}
                                                    >
                                                        {log.description || log.endpoint || "—"}
                                                    </span>
                                                </td>

                                                <td className="px-3 py-2">
                                                    {log.status_code != null ? (
                                                        <span className={cn(
                                                            "rounded px-1.5 py-0.5 text-[10.5px] font-medium",
                                                            isError
                                                                ? "bg-destructive/15 text-destructive"
                                                                : "bg-success/15 text-success",
                                                        )}>
                                                            {log.status_code}
                                                        </span>
                                                    ) : "—"}
                                                </td>

                                                <td className="px-3 py-2 text-xs text-muted-foreground">
                                                    {log.ip_address || "—"}
                                                </td>
                                            </tr>
                                        );
                                    })}
                                </tbody>
                            </table>
                        </div>
                    )}
                </CardContent>

                {!loading && logs.length > 0 && (
                    <div className="flex justify-between border-t border-border/60 px-4 py-2 text-xs text-muted-foreground">
                        <span>Showing {logs.length} records</span>
                        <span>Most recent first</span>
                    </div>
                )}
            </Card>
        </>
    );
}
