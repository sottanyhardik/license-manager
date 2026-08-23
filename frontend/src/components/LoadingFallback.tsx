/**
 * Premium loading fallbacks — skeleton-first, no spinners for page loads.
 * All inline styles converted to Tailwind utilities.
 */
import { ShieldCheck } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";

export function PageLoader() {
    return (
        <div className="flex min-h-[360px] flex-col items-center justify-center gap-3">
            <span
                className="size-6 animate-spin rounded-full border-2 border-primary border-t-transparent"
                role="status"
                aria-label="Loading"
            />
            <span className="text-[13px] text-muted-foreground">Loading…</span>
        </div>
    );
}

export function FullPageLoader() {
    return (
        <div className="fixed inset-0 z-[9999] flex flex-col items-center justify-center gap-3.5 bg-background">
            {/* Animated brand mark */}
            <div
                className="flex size-10 items-center justify-center rounded-xl text-white shadow-[0_4px_12px_rgba(37,99,235,0.35)]"
                style={{ background: "linear-gradient(135deg, var(--tb-brand) 0%, var(--tb-brand-hover) 100%)" }}
            >
                <ShieldCheck className="size-5 animate-pulse" aria-hidden="true" />
            </div>
            <span className="text-[13px] text-muted-foreground">Loading…</span>
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
                            <th key={i} scope="col">
                                <Skeleton className="h-2.5 w-3/5" />
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {Array.from({ length: rows }).map((_, ri) => (
                        <tr key={ri}>
                            {Array.from({ length: columns }).map((_, ci) => (
                                <td key={ci}>
                                    <Skeleton
                                        className="h-3"
                                        style={{ width: `${45 + ci * 10}%` }}
                                    />
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
                <Skeleton className="mb-5 h-5 w-[30%]" />
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    {Array.from({ length: fields }).map((_, i) => (
                        <div key={i} className="space-y-1.5">
                            <Skeleton className="h-2.5 w-[40%]" />
                            <Skeleton className="h-9 w-full" />
                        </div>
                    ))}
                </div>
                <Skeleton className="mt-5 h-9 w-24" />
            </div>
        </div>
    );
}

export function InlineLoader({ text = "Loading…" }) {
    return (
        <span className="inline-flex items-center gap-1.5 text-[13px] text-muted-foreground">
            <span
                className="size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent"
                role="status"
                aria-hidden="true"
            />
            {text}
        </span>
    );
}

export default PageLoader;
