/**
 * Premium loading fallbacks — skeleton-first, no spinners for page loads.
 */
import { ShieldCheck } from "lucide-react";

export function PageLoader() {
    return (
        <div
            style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                minHeight: 360,
                flexDirection: "column",
                gap: 12,
            }}
        >
            <span
                className="inline-block size-7 animate-spin rounded-full border-2 border-primary border-t-transparent"
                role="status"
                aria-label="Loading"
            />
            <span style={{ fontSize: 13, color: "var(--tb-text-tertiary)" }}>Loading…</span>
        </div>
    );
}

export function FullPageLoader() {
    return (
        <div
            style={{
                position: "fixed",
                inset: 0,
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                background: "var(--tb-body-bg)",
                zIndex: 9999,
                flexDirection: "column",
                gap: 14,
            }}
        >
            <div
                style={{
                    width: 40,
                    height: 40,
                    borderRadius: 10,
                    background: "linear-gradient(135deg, var(--tb-brand) 0%, var(--tb-brand-hover) 100%)",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    color: "#fff",
                    fontSize: 20,
                    boxShadow: "0 4px 12px rgba(37,99,235,0.35)",
                }}
            >
                <ShieldCheck className="size-4" aria-hidden="true" />
            </div>
            <span style={{ fontSize: 13, color: "var(--tb-text-tertiary)" }}>Loading…</span>
        </div>
    );
}

export function TableSkeletonLoader({ rows = 6, columns = 5 }) {
    return (
        <div className="table-responsive">
            <table className="table mb-0" aria-busy="true">
                <thead>
                    <tr>
                        {Array.from({ length: columns }).map((_, i) => (
                            <th key={i}>
                                <div className="skeleton" style={{ height: 10, width: "60%", borderRadius: 4 }} />
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {Array.from({ length: rows }).map((_, ri) => (
                        <tr key={ri}>
                            {Array.from({ length: columns }).map((_, ci) => (
                                <td key={ci}>
                                    <div className="skeleton" style={{ height: 13, width: `${45 + ci * 10}%`, borderRadius: 4 }} />
                                </td>
                            ))}
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}

export function FormSkeletonLoader({ fields = 6 }) {
    return (
        <div className="card">
            <div className="card-body">
                <div className="skeleton" style={{ height: 22, width: "30%", borderRadius: 6, marginBottom: 20 }} />
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    {Array.from({ length: fields }).map((_, i) => (
                        <div key={i}>
                            <div className="skeleton" style={{ height: 10, width: "40%", borderRadius: 4, marginBottom: 6 }} />
                            <div className="skeleton" style={{ height: 36, width: "100%", borderRadius: 6 }} />
                        </div>
                    ))}
                </div>
                <div className="skeleton" style={{ height: 36, width: 100, borderRadius: 6, marginTop: 20 }} />
            </div>
        </div>
    );
}

export function InlineLoader({ text = "Loading…" }) {
    return (
        <span style={{ display: "inline-flex", alignItems: "center", gap: 7, color: "var(--tb-text-secondary)", fontSize: 13 }}>
            <span
                className="inline-block size-4 animate-spin rounded-full border-2 border-current border-t-transparent"
                role="status"
                aria-hidden="true"
                style={{ width: 13, height: 13 }}
            />
            {text}
        </span>
    );
}

export default PageLoader;
