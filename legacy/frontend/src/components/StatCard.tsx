import * as React from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type Tone = "primary" | "success" | "danger" | "warning" | "info" | "neutral";

const TONE: Record<Tone, { icon: string; accent: string }> = {
    primary: { icon: "bg-primary/10 text-primary",       accent: "border-l-primary/60" },
    success: { icon: "bg-success/10 text-success",       accent: "border-l-success/60" },
    danger:  { icon: "bg-destructive/10 text-destructive", accent: "border-l-destructive/60" },
    warning: { icon: "bg-warning/10 text-warning",       accent: "border-l-warning/60" },
    info:    { icon: "bg-info/10 text-info",             accent: "border-l-info/60" },
    neutral: { icon: "bg-muted text-muted-foreground",   accent: "border-l-border" },
};

interface StatCardProps {
    label: string;
    value: React.ReactNode;
    icon: LucideIcon;
    tone?: Tone;
    onClick?: () => void;
    loading?: boolean;
}

export default function StatCard({ label, value, icon: Icon, tone = "primary", onClick, loading }: StatCardProps) {
    const t = TONE[tone];
    const interactive = !!onClick;
    const Comp = interactive ? "button" : "div";
    return (
        <Comp
            onClick={onClick}
            className={cn(
                "flex w-full items-center gap-3 rounded-xl border border-border border-l-[3px] bg-card px-4 py-3 text-left shadow-sm transition-all duration-200",
                t.accent,
                interactive && "cursor-pointer hover:shadow-md hover:-translate-y-px active:scale-[0.99]"
            )}
        >
            <span className={cn("flex size-9 shrink-0 items-center justify-center rounded-lg", t.icon)}>
                <Icon className="size-4" />
            </span>
            <div className="min-w-0 flex-1">
                <div className="mb-0.5 text-[10.5px] font-bold uppercase tracking-wider text-muted-foreground">
                    {label}
                </div>
                <div className="text-2xl font-bold leading-tight tracking-tight text-foreground tabular-nums">
                    {loading ? <span className="inline-block h-6 w-12 animate-pulse rounded bg-muted" /> : (value ?? "—")}
                </div>
            </div>
        </Comp>
    );
}
