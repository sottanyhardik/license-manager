import { useEffect, useState } from "react";
import { toast } from "sonner";
import { AlertTriangle, CheckCircle2, CloudOff, DatabaseZap, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
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
        <div className="card" style={{ marginTop: 16 }}>
            <div
                className="card-header"
                style={{ display: "flex", alignItems: "center", gap: 8 }}
            >
                <DatabaseZap className="size-4" aria-hidden="true" />
                <span style={{ fontSize: 13.5, fontWeight: 600 }}>Master Data Service</span>
                {badge && (
                    <Badge variant={badge.variant} className="ml-1">
                        <badge.Icon aria-hidden="true" />
                        {badge.label}
                    </Badge>
                )}
                <button
                    type="button"
                    onClick={load}
                    disabled={loading}
                    aria-label="Refresh Master Data Service status"
                    title="Refresh"
                    style={{
                        marginLeft: "auto",
                        background: "transparent",
                        border: "none",
                        cursor: loading ? "default" : "pointer",
                        color: "var(--tb-text-tertiary)",
                        padding: 4,
                        borderRadius: "var(--tb-r-sm)",
                        opacity: loading ? 0.5 : 1,
                        display: "inline-flex",
                    }}
                >
                    <RefreshCw
                        className={`size-4${loading ? " animate-spin" : ""}`}
                        aria-hidden="true"
                    />
                </button>
            </div>

            <div className="card-body">
                {/* Loading */}
                {loading && (
                    <div
                        style={{
                            padding: "24px 8px",
                            textAlign: "center",
                            color: "var(--tb-text-tertiary)",
                            fontSize: 12.5,
                        }}
                    >
                        Loading sync status…
                    </div>
                )}

                {/* Error */}
                {!loading && error && (
                    <div
                        style={{
                            padding: "24px 8px",
                            textAlign: "center",
                            color: "var(--tb-text-secondary)",
                            fontSize: 12.5,
                            display: "flex",
                            flexDirection: "column",
                            alignItems: "center",
                            gap: 10,
                        }}
                    >
                        <AlertTriangle className="size-5" aria-hidden="true" style={{ color: "var(--tb-warning-text)" }} />
                        Could not load Master-Data Service status.
                        <button
                            type="button"
                            onClick={load}
                            className="inline-flex items-center gap-1.5 rounded px-2.5 py-1 font-medium"
                            style={{
                                fontSize: 12,
                                background: "var(--tb-brand-50)",
                                color: "var(--tb-brand-active)",
                                border: "1px solid var(--tb-brand-100)",
                            }}
                        >
                            <RefreshCw className="size-3.5" aria-hidden="true" />
                            Retry
                        </button>
                    </div>
                )}

                {/* Disabled */}
                {!loading && !error && status && !status.enabled && (
                    <div
                        style={{
                            padding: "24px 8px",
                            textAlign: "center",
                            color: "var(--tb-text-tertiary)",
                            fontSize: 12.5,
                            display: "flex",
                            flexDirection: "column",
                            alignItems: "center",
                            gap: 8,
                        }}
                    >
                        <CloudOff className="size-5" aria-hidden="true" />
                        Master Data Service not enabled
                    </div>
                )}

                {/* Enabled */}
                {!loading && !error && status && status.enabled && (
                    <>
                        <div
                            style={{
                                display: "flex",
                                alignItems: "center",
                                gap: 6,
                                flexWrap: "wrap",
                                fontSize: 12,
                                color: "var(--tb-text-secondary)",
                                marginBottom: 14,
                            }}
                        >
                            <span style={{ fontWeight: 500, color: "var(--tb-text-tertiary)" }}>Base URL</span>
                            <code
                                style={{
                                    fontSize: 11.5,
                                    background: "var(--tb-sunken)",
                                    border: "1px solid var(--tb-border-soft)",
                                    borderRadius: "var(--tb-r-sm)",
                                    padding: "1px 6px",
                                    color: "var(--tb-text-primary)",
                                    wordBreak: "break-all",
                                }}
                            >
                                {status.base_url || "—"}
                            </code>
                        </div>

                        <div className="table-responsive">
                            <table className="table table-hover mb-0">
                                <thead>
                                    <tr>
                                        <th style={{ paddingLeft: 16 }}>Model</th>
                                        <th className="text-end">Rows</th>
                                        <th>Last Synced</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {status.models.map((m) => {
                                        const stale = isModelStale(m.last_synced_at);
                                        return (
                                            <tr key={m.model_label}>
                                                <td style={{ paddingLeft: 16, fontSize: 12.5, fontWeight: 500 }}>
                                                    {m.model_label}
                                                </td>
                                                <td
                                                    className="text-end"
                                                    style={{ fontSize: 12.5, color: "var(--tb-text-secondary)", fontVariantNumeric: "tabular-nums" }}
                                                >
                                                    {m.count.toLocaleString()}
                                                </td>
                                                <td
                                                    style={{ fontSize: 12, whiteSpace: "nowrap" }}
                                                    title={absoluteTime(m.last_synced_at)}
                                                >
                                                    {stale ? (
                                                        <Badge variant="warning">never synced</Badge>
                                                    ) : (
                                                        <span style={{ color: "var(--tb-text-secondary)" }}>
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
                                                style={{ textAlign: "center", padding: "32px 24px", color: "var(--tb-text-tertiary)", fontSize: 12.5 }}
                                            >
                                                No mirrored models reported.
                                            </td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                    </>
                )}
            </div>
        </div>
    );
}
