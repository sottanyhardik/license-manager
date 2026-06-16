import { useCallback, useContext, useEffect, useRef, useState } from "react";
import { toast } from "react-toastify";
import {
    RefreshCw, LogIn, LogOut, Eye, PlusCircle, Pencil, Trash2,
    Download, Upload, FileDown, Search, ScrollText, FileX,
} from "lucide-react";

import api from "../../api/axios";
import { AuthContext } from "../../context/AuthContext";
import { getErrorMessage } from "../../utils/errorUtils";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import {
    Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";

// bg/color use design tokens so the chips flip in dark mode.
const ACTION_META = {
    LOGIN:    { bg: "var(--tb-success-soft)", color: "var(--tb-success-text)", Icon: LogIn },
    LOGOUT:   { bg: "var(--tb-danger-soft)",  color: "var(--tb-danger-text)",  Icon: LogOut },
    VIEW:     { bg: "var(--tb-info-soft)",     color: "var(--tb-info-text)",    Icon: Eye },
    CREATE:   { bg: "var(--tb-success-soft)",  color: "var(--tb-success-text)", Icon: PlusCircle },
    UPDATE:   { bg: "var(--tb-warning-soft)",  color: "var(--tb-warning-text)", Icon: Pencil },
    DELETE:   { bg: "var(--tb-danger-soft)",   color: "var(--tb-danger-text)",  Icon: Trash2 },
    DOWNLOAD: { bg: "var(--tb-sunken)",        color: "var(--accent-color)",    Icon: Download },
    UPLOAD:   { bg: "var(--tb-sunken)",        color: "var(--accent-color)",    Icon: Upload },
    EXPORT:   { bg: "var(--tb-success-soft)",  color: "var(--tb-success-text)", Icon: FileDown },
    SEARCH:   { bg: "var(--tb-sunken)",        color: "var(--tb-text-secondary)", Icon: Search },
};

const ACTIONS = ["LOGIN", "LOGOUT", "VIEW", "CREATE", "UPDATE", "DELETE", "DOWNLOAD", "UPLOAD", "EXPORT", "SEARCH"];
const ALL = "__all__";

const fmtDate = (ts) => {
    if (!ts) return "—";
    return new Date(ts).toLocaleString("en-IN", {
        day: "2-digit", month: "short", year: "numeric",
        hour: "2-digit", minute: "2-digit", second: "2-digit", hour12: false,
    });
};

export default function ActivityLog() {
    const { user } = useContext(AuthContext);
    const [logs, setLogs] = useState([]);
    const [loading, setLoading] = useState(false);
    const [filters, setFilters] = useState({
        username: "", action: "", module: "", date_from: "", date_to: "", search: "", limit: "200",
    });
    const abortRef = useRef(null);

    const fetchLogs = useCallback(async () => {
        if (abortRef.current) abortRef.current.abort();
        abortRef.current = new AbortController();
        setLoading(true);
        try {
            const params = Object.fromEntries(Object.entries(filters).filter(([, v]) => v !== ""));
            const { data } = await api.get("masters/activity-logs/", { params, signal: abortRef.current.signal });
            setLogs(Array.isArray(data) ? data : data.results ?? []);
        } catch (err) {
            if (err.name !== "CanceledError" && err.name !== "AbortError") toast.error(getErrorMessage(err));
        } finally {
            setLoading(false);
        }
    }, [filters]);

    useEffect(() => { fetchLogs(); }, [fetchLogs]);

    const handleFilter = (key, value) => setFilters(prev => ({ ...prev, [key]: value }));

    return (
        <>
            <PageHeader
                pretitle="Admin"
                title="Activity Log"
                description={user?.is_superuser ? "All user actions across the system" : "Your recent activity"}
                actions={
                    <Button variant="outline" onClick={fetchLogs} disabled={loading}>
                        <RefreshCw className={`size-4 ${loading ? "animate-spin" : ""}`} />
                        Refresh
                    </Button>
                }
            />

            {/* Filters */}
            <Card className="mb-3">
                <CardContent className="grid grid-cols-2 gap-3 py-3 md:grid-cols-3 lg:grid-cols-6">
                    {user?.is_superuser && (
                        <div>
                            <Label className="mb-1 text-xs" htmlFor="f-user">Username</Label>
                            <Input id="f-user" className="h-8" placeholder="Search user…" value={filters.username} onChange={(e) => handleFilter("username", e.target.value)} />
                        </div>
                    )}
                    <div>
                        <Label className="mb-1 text-xs">Action</Label>
                        <Select value={filters.action || ALL} onValueChange={(v) => handleFilter("action", v === ALL ? "" : v)}>
                            <SelectTrigger size="sm"><SelectValue placeholder="All Actions" /></SelectTrigger>
                            <SelectContent>
                                <SelectItem value={ALL}>All Actions</SelectItem>
                                {ACTIONS.map((a) => <SelectItem key={a} value={a}>{a}</SelectItem>)}
                            </SelectContent>
                        </Select>
                    </div>
                    <div>
                        <Label className="mb-1 text-xs" htmlFor="f-module">Module</Label>
                        <Input id="f-module" className="h-8" placeholder="e.g. licenses" value={filters.module} onChange={(e) => handleFilter("module", e.target.value)} />
                    </div>
                    <div>
                        <Label className="mb-1 text-xs" htmlFor="f-from">From</Label>
                        <Input id="f-from" type="date" className="h-8" value={filters.date_from} onChange={(e) => handleFilter("date_from", e.target.value)} />
                    </div>
                    <div>
                        <Label className="mb-1 text-xs" htmlFor="f-to">To</Label>
                        <Input id="f-to" type="date" className="h-8" value={filters.date_to} onChange={(e) => handleFilter("date_to", e.target.value)} />
                    </div>
                    <div>
                        <Label className="mb-1 text-xs" htmlFor="f-search">Search</Label>
                        <Input id="f-search" className="h-8" placeholder="IP, description…" value={filters.search} onChange={(e) => handleFilter("search", e.target.value)} />
                    </div>
                </CardContent>
            </Card>

            {/* Stats chips */}
            {!loading && logs.length > 0 && (
                <div className="mb-3 flex flex-wrap items-center gap-2">
                    {ACTIONS.filter((a) => logs.some((l) => l.action === a)).map((a) => {
                        const m = ACTION_META[a] ?? {};
                        const count = logs.filter((l) => l.action === a).length;
                        const Icon = m.Icon;
                        return (
                            <button
                                key={a}
                                onClick={() => handleFilter("action", filters.action === a ? "" : a)}
                                className="inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-medium transition-opacity hover:opacity-80 cursor-pointer"
                                style={{ background: m.bg, color: m.color }}
                            >
                                {Icon && <Icon className="size-3.5" />}
                                {a} <strong>{count}</strong>
                            </button>
                        );
                    })}
                    <button
                        className="ml-auto text-xs text-muted-foreground hover:text-foreground cursor-pointer"
                        onClick={() => setFilters((f) => ({ ...f, action: "", username: "", module: "", search: "", date_from: "", date_to: "" }))}
                    >
                        Clear filters
                    </button>
                </div>
            )}

            {/* Table */}
            <Card>
                <CardContent className="p-0">
                    {loading ? (
                        <div className="flex flex-col items-center gap-2 p-12 text-center">
                            <RefreshCw className="size-6 animate-spin text-primary" />
                            <span className="text-sm text-muted-foreground">Loading activity log…</span>
                        </div>
                    ) : logs.length === 0 ? (
                        <div className="flex flex-col items-center gap-2 p-12 text-center text-muted-foreground">
                            <FileX className="size-8 opacity-50" />
                            <span>No activity records found</span>
                        </div>
                    ) : (
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead>
                                    <tr className="border-b border-border bg-muted/50 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                                        <th className="px-3 py-2.5" style={{ width: 170 }}>Time</th>
                                        {user?.is_superuser && <th className="px-3 py-2.5">User</th>}
                                        <th className="px-3 py-2.5" style={{ width: 120 }}>Action</th>
                                        <th className="px-3 py-2.5">Module</th>
                                        <th className="px-3 py-2.5">Description</th>
                                        <th className="px-3 py-2.5" style={{ width: 70 }}>Status</th>
                                        <th className="px-3 py-2.5" style={{ width: 130 }}>IP</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {logs.map((log) => {
                                        const m = ACTION_META[log.action] ?? { bg: "var(--tb-sunken)", color: "var(--tb-text-secondary)", Icon: ScrollText };
                                        const Icon = m.Icon;
                                        const isError = log.status_code && log.status_code >= 400;
                                        return (
                                            <tr key={log.id} className="border-b border-border/60" style={isError ? { background: "var(--tb-danger-soft)" } : {}}>
                                                <td className="whitespace-nowrap px-3 py-2 text-xs text-muted-foreground">{fmtDate(log.timestamp)}</td>
                                                {user?.is_superuser && (
                                                    <td className="px-3 py-2">
                                                        <div className="flex items-center gap-2">
                                                            <div className="flex size-6 shrink-0 items-center justify-center rounded-full text-[10px] font-bold text-white"
                                                                 style={{ background: "linear-gradient(135deg, var(--tb-brand), var(--tb-brand-hover))" }}>
                                                                {(log.username || "?")[0].toUpperCase()}
                                                            </div>
                                                            <span className="text-[13px] font-medium">{log.username || "—"}</span>
                                                        </div>
                                                    </td>
                                                )}
                                                <td className="px-3 py-2">
                                                    <span className="inline-flex items-center gap-1 rounded px-2 py-0.5 text-[11px] font-medium" style={{ background: m.bg, color: m.color }}>
                                                        {Icon && <Icon className="size-3" />}{log.action}
                                                    </span>
                                                </td>
                                                <td className="px-3 py-2 text-xs text-muted-foreground">
                                                    {log.module || "—"}
                                                    {log.resource_id && <span className="ml-1 text-muted-foreground/70">#{log.resource_id}</span>}
                                                </td>
                                                <td className="max-w-[300px] px-3 py-2 text-xs">
                                                    <span className="block truncate" title={log.description}>{log.description || log.endpoint || "—"}</span>
                                                </td>
                                                <td className="px-3 py-2">
                                                    {log.status_code ? (
                                                        <span className={`rounded px-1.5 py-0.5 text-[10.5px] font-medium ${isError ? "bg-destructive/15 text-destructive" : "bg-success/15 text-success"}`}>
                                                            {log.status_code}
                                                        </span>
                                                    ) : "—"}
                                                </td>
                                                <td className="px-3 py-2 text-xs text-muted-foreground">{log.ip_address || "—"}</td>
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
