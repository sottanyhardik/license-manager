import * as React from "react";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

type Tone = "primary" | "success" | "danger" | "warning" | "info" | "neutral";

const TONE: Record<Tone, string> = {
    primary: "bg-primary/10 text-primary",
    success: "bg-success/10 text-success",
    danger: "bg-destructive/10 text-destructive",
    warning: "bg-warning/10 text-warning",
    info: "bg-info/10 text-info",
    neutral: "bg-muted text-muted-foreground",
};

interface StatCardProps {
    label: string;
    value: React.ReactNode;
    icon: LucideIcon;
    tone?: Tone;
    onClick?: () => void;
}

export default function StatCard({ label, value, icon: Icon, tone = "primary", onClick }: StatCardProps) {
    const interactive = !!onClick;
    const Comp = interactive ? "button" : "div";
    return (
        <Comp
            onClick={onClick}
            className={cn(
                "flex w-full items-start gap-3.5 rounded-xl border border-border bg-card p-4 text-left shadow-sm transition-all",
                interactive && "cursor-pointer hover:border-border/80 hover:shadow-md active:scale-[0.99]"
            )}
        >
            <span className={cn("flex size-10 shrink-0 items-center justify-center rounded-lg", TONE[tone])}>
                <Icon className="size-5" />
            </span>
            <div className="min-w-0 flex-1">
                <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{label}</div>
                <div className="mt-0.5 text-2xl font-semibold leading-tight tracking-tight text-foreground tabular-nums">
                    {value ?? "—"}
                </div>
            </div>
        </Comp>
    );
}
