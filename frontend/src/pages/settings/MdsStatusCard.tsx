import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, CheckCircle2, CloudOff, DatabaseZap, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { fetchMdsStatus, type MdsStatus } from "../../services/api/mdsApi";

/** A mirror is considered "stale" if it has never synced. */
function isModelStale(lastSyncedAt: string | null): boolean {
    return !lastSyncedAt;
}

/** Compact, dependency-free relative time (e.g. "3m ago", "2h ago", "just now"). */
function relativeTime(iso: string | null): string {
    if (!iso) return "never";
    const then = new Date(iso).getTime();
    if (Number.isNaN(then)) return "—";
    const diffMs = Date.now() - then;
    if (diffMs < 0) return "just now";
    const sec = Math.round(diffMs / 1000);
    if (sec < 45) return "just now";
    const min = Math.round(sec / 60);
    if (min < 60) return `${min}m ago`;
    const hr = Math.round(min / 60);
    if (hr < 24) return `${hr}h ago`;
    const day = Math.round(hr / 24);
    if (day < 30) return `${day}d ago`;
    const mon = Math.round(day / 30);
    if (mon < 12) return `${mon}mo ago`;
    return `${Math.round(mon / 12)}y ago`;
}

function absoluteTime(iso: string | null): string {
    if (!iso) return "Never synced";
    const d = new Date(iso);
    return Number.isNaN(d.getTime()) ? "" : d.toLocaleString();
}

interface HealthBadge {
    variant: "success" | "warning" | "secondary";
    label: string;
    Icon: typeof CheckCircle2;
}

function healthBadge(status: MdsStatus): HealthBadge {
    if (!status.enabled) return { variant: "secondary", label: "Off", Icon: CloudOff };
    if (status.healthy) return { variant: "success", label: "Healthy", Icon: CheckCircle2 };
    return { variant: "warning", label: "Stale", Icon: AlertTriangle };
}

export default function MdsStatusCard() {
    const [status, setStatus] = useState<MdsStatus | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(false);

    const load = async () => {
        setLoading(true);
        setError(false);
        try {
            const data = await fetchMdsStatus();
            setStatus(data);
        } catch {
            setError(true);
            setStatus(null);
            toast.error("Failed to load Master-Data Service status");
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        load();
    }, []);

    const badge = status ? healthBadge(status) : null;

    return (
        <Card className="mt-4">
            {/* ── Card header ───────────────────────────────────── */}
            <div className="flex items-center gap-2 border-b border-border px-5 py-3">
                <DatabaseZap className="size-4 text-muted-foreground" aria-hidden="true" />
                <span className="text-[13.5px] font-semibold text-foreground">Master Data Service</span>
                {badge && (
                    <Badge variant={badge.variant} className="ml-1">
                        <badge.Icon className="size-3" aria-hidden="true" />
                        {badge.label}
                    </Badge>
                )}
                <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={load}
                    disabled={loading}
                    aria-label="Refresh Master Data Service status"
                    title="Refresh"
                    className="ml-auto size-7"
                >
                    <RefreshCw
                        className={cn("size-4", loading && "animate-spin")}
                        aria-hidden="true"
                    />
                </Button>
            </div>

            {/* ── Card body ──────────────────────────────────────── */}
            <CardContent className="p-0">

                {/* Loading */}
                {loading && (
                    <p className="px-5 py-6 text-center text-[12.5px] text-muted-foreground">
                        Loading sync status…
                    </p>
                )}

                {/* Error */}
                {!loading && error && (
                    <div className="flex flex-col items-center gap-2.5 px-5 py-8 text-center text-[12.5px] text-muted-foreground">
                        <AlertTriangle className="size-5 text-warning" aria-hidden="true" />
                        <span>Could not load Master-Data Service status.</span>
                        <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={load}
                            className="gap-1.5"
                        >
                            <RefreshCw className="size-3.5" aria-hidden="true" />
                            Retry
                        </Button>
                    </div>
                )}

                {/* Disabled */}
                {!loading && !error && status && !status.enabled && (
                    <div className="flex flex-col items-center gap-2 px-5 py-8 text-center text-[12.5px] text-muted-foreground">
                        <CloudOff className="size-5" aria-hidden="true" />
                        Master Data Service not enabled
                    </div>
                )}

                {/* Enabled */}
                {!loading && !error && status && status.enabled && (
                    <div className="p-5">
                        {/* Base URL row */}
                        <div className="mb-3.5 flex flex-wrap items-center gap-1.5 text-[12px] text-muted-foreground">
                            <span className="font-medium">Base URL</span>
                            <code className="rounded-md border border-border/60 bg-muted px-1.5 py-px text-[11.5px] text-foreground break-all">
                                {status.base_url || "—"}
                            </code>
                        </div>

                        {/* Models table */}
                        <div className="overflow-x-auto">
                            <table className="table table-hover mb-0">
                                <thead>
                                    <tr>
                                        <th scope="col" className="pl-0">Model</th>
                                        <th scope="col" className="text-end">Rows</th>
                                        <th scope="col">Last Synced</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {status.models.map((m) => {
                                        const stale = isModelStale(m.last_synced_at);
                                        return (
                                            <tr key={m.model_label}>
                                                <td className="pl-0 text-[12.5px] font-medium">
                                                    {m.model_label}
                                                </td>
                                                <td className="text-end text-[12.5px] tabular-nums text-muted-foreground">
                                                    {m.count.toLocaleString()}
                                                </td>
                                                <td
                                                    className="whitespace-nowrap text-[12px]"
                                                    title={absoluteTime(m.last_synced_at)}
                                                >
                                                    {stale ? (
                                                        <Badge variant="warning">never synced</Badge>
                                                    ) : (
                                                        <span className="text-muted-foreground">
                                                            {relativeTime(m.last_synced_at)}
                                                        </span>
                                                    )}
                                                </td>
                                            </tr>
                                        );
                                    })}
                                    {status.models.length === 0 && (
                                        <tr>
                                            <td
                                                colSpan={3}
                                                className="py-8 text-center text-[12.5px] text-muted-foreground"
                                            >
                                                No mirrored models reported.
                                            </td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </div>
                )}
            </CardContent>
        </Card>
    );
}
