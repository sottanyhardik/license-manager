import * as React from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type Tone = "primary" | "success" | "danger" | "warning" | "info" | "neutral";

const TONE: Record<Tone, { icon: string; ring: string; glow: string }> = {
    primary: {
        icon: "bg-primary/10 text-primary",
        ring: "hover:ring-primary/20",
        glow: "before:from-primary/5",
    },
    success: {
        icon: "bg-success/10 text-success",
        ring: "hover:ring-success/20",
        glow: "before:from-success/5",
    },
    danger: {
        icon: "bg-destructive/10 text-destructive",
        ring: "hover:ring-destructive/20",
        glow: "before:from-destructive/5",
    },
    warning: {
        icon: "bg-warning/10 text-warning",
        ring: "hover:ring-warning/20",
        glow: "before:from-warning/5",
    },
    info: {
        icon: "bg-info/10 text-info",
        ring: "hover:ring-info/20",
        glow: "before:from-info/5",
    },
    neutral: {
        icon: "bg-muted text-muted-foreground",
        ring: "hover:ring-border",
        glow: "before:from-muted/40",
    },
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
                // Base card — clean, no left border
                "relative flex w-full items-center gap-3.5 overflow-hidden rounded-xl border border-border/70 bg-card px-4 py-3.5 text-left",
                // Subtle gradient wash at top via pseudo-element
                "before:pointer-events-none before:absolute before:inset-x-0 before:top-0 before:h-16 before:bg-gradient-to-b before:to-transparent",
                t.glow,
                // Shadow + ring system
                "shadow-[0_1px_3px_rgba(0,0,0,0.05),0_1px_2px_rgba(0,0,0,0.03)]",
                "transition-all duration-200",
                interactive && [
                    "cursor-pointer",
                    "hover:shadow-[0_4px_12px_rgba(0,0,0,0.08),0_2px_4px_rgba(0,0,0,0.04)]",
                    "hover:-translate-y-px",
                    "hover:ring-2 hover:ring-offset-0",
                    t.ring,
                    "active:scale-[0.99] active:translate-y-0",
                ]
            )}
        >
            {/* Icon */}
            <span
                className={cn(
                    "relative z-10 flex size-10 shrink-0 items-center justify-center rounded-lg",
                    t.icon
                )}
            >
                <Icon className="size-[18px]" strokeWidth={1.75} />
            </span>

            {/* Text */}
            <div className="relative z-10 min-w-0 flex-1">
                <div className="text-[10.5px] font-semibold uppercase tracking-widest text-muted-foreground">
                    {label}
                </div>
                <div className="mt-0.5 text-[1.6rem] font-bold leading-none tracking-tight text-foreground tabular-nums">
                    {loading
                        ? <span className="inline-block h-7 w-14 animate-pulse rounded-md bg-muted" />
                        : (value ?? "—")}
                </div>
            </div>
        </Comp>
    );
}
