import { cn } from "@/lib/utils";

export interface SummaryCardProps {
    label: string;
    value: string;
    sub?: string;
    variant?: "default" | "primary" | "success" | "danger" | "muted";
    size?: "sm" | "lg";
}

const VARIANT_CLASSES: Record<Required<SummaryCardProps>["variant"], string> = {
    default: "text-foreground",
    primary: "text-primary",
    success: "text-emerald-700 dark:text-emerald-400",
    danger: "text-destructive",
    muted: "text-muted-foreground",
};

/**
 * Small reusable metric card for the Overview tab's 9-card grid — adapted
 * from `SummaryMetric` in `pages/masters/tables/LedgerTab.tsx` (~186-201),
 * wrapped in a bordered card shell (that file renders it bare, inline in a
 * grid that already has its own card wrapper) so it can be dropped straight
 * into a `grid` here.
 */
export default function SummaryCard({ label, value, sub, variant = "default", size = "sm" }: SummaryCardProps) {
    return (
        <div className="rounded-lg border border-border/70 bg-card px-3 py-2.5">
            <div className="text-[10.5px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</div>
            <div
                className={cn(
                    "mt-0.5 tabular-nums font-bold",
                    VARIANT_CLASSES[variant],
                    size === "lg" ? "text-2xl" : "text-sm"
                )}
            >
                {value}
            </div>
            {sub && <div className="text-[10.5px] text-muted-foreground">{sub}</div>}
        </div>
    );
}
