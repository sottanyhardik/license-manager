import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export type StatAccent = "blue" | "indigo" | "purple" | "orange" | "red" | "cyan" | "green";

interface AccentStyle {
    icon: string;
    iconChip: string;
    tint: string;
    ring: string;
    ringHighlighted: string;
}

/**
 * Closed-union color map, spelled out as full static Tailwind class strings
 * (never string-concatenated) so the classes survive Tailwind's build-time
 * purge — `bg-${accent}-500/5` would not.
 */
const ACCENT_STYLES: Record<StatAccent, AccentStyle> = {
    blue: {
        icon: "text-blue-500 dark:text-blue-400",
        iconChip: "bg-blue-500/10",
        tint: "bg-blue-500/5",
        ring: "ring-blue-500/20",
        ringHighlighted: "ring-blue-500/40",
    },
    indigo: {
        icon: "text-indigo-500 dark:text-indigo-400",
        iconChip: "bg-indigo-500/10",
        tint: "bg-indigo-500/5",
        ring: "ring-indigo-500/20",
        ringHighlighted: "ring-indigo-500/40",
    },
    purple: {
        icon: "text-purple-500 dark:text-purple-400",
        iconChip: "bg-purple-500/10",
        tint: "bg-purple-500/5",
        ring: "ring-purple-500/20",
        ringHighlighted: "ring-purple-500/40",
    },
    orange: {
        icon: "text-orange-500 dark:text-orange-400",
        iconChip: "bg-orange-500/10",
        tint: "bg-orange-500/5",
        ring: "ring-orange-500/20",
        ringHighlighted: "ring-orange-500/40",
    },
    red: {
        icon: "text-red-500 dark:text-red-400",
        iconChip: "bg-red-500/10",
        tint: "bg-red-500/5",
        ring: "ring-red-500/20",
        ringHighlighted: "ring-red-500/40",
    },
    cyan: {
        icon: "text-cyan-500 dark:text-cyan-400",
        iconChip: "bg-cyan-500/10",
        tint: "bg-cyan-500/5",
        ring: "ring-cyan-500/20",
        ringHighlighted: "ring-cyan-500/40",
    },
    green: {
        icon: "text-green-500 dark:text-green-400",
        iconChip: "bg-green-500/10",
        tint: "bg-green-500/5",
        ring: "ring-green-500/20",
        ringHighlighted: "ring-green-500/40",
    },
};

export interface StatCardProps {
    icon: LucideIcon;
    title: string;
    value: string;
    /** Short unit/helper caption shown under the value, e.g. "Bills of entry linked". */
    helper?: string;
    accent: StatAccent;
    /** Balance CIF gets this: slightly larger value text + a stronger accent ring. */
    highlighted?: boolean;
}

/**
 * Reusable metric tile for the Overview tab's stat grid — accent icon +
 * title on top, a large bold value in the middle, a muted helper caption at
 * the bottom. Deliberately no gradients/neon: a soft color-tinted background
 * plus a subtle ring is the entire "glow" treatment.
 */
export default function StatCard({ icon: Icon, title, value, helper, accent, highlighted = false }: StatCardProps) {
    const styles = ACCENT_STYLES[accent];
    return (
        <div
            className={cn(
                "flex flex-col gap-3 rounded-xl border border-border/60 p-4 ring-1 transition-shadow",
                styles.tint,
                highlighted ? cn(styles.ringHighlighted, "shadow-sm") : styles.ring
            )}
        >
            <div className="flex items-center gap-2">
                <span className={cn("flex size-8 shrink-0 items-center justify-center rounded-lg", styles.iconChip, styles.icon)}>
                    <Icon className="size-4" aria-hidden="true" />
                </span>
                <span className="truncate text-sm font-medium text-muted-foreground">{title}</span>
            </div>
            <div
                className={cn(
                    "tabular-nums font-bold text-foreground",
                    highlighted ? "text-[2.75rem] leading-none" : "text-4xl leading-none"
                )}
            >
                {value}
            </div>
            {helper && <div className="text-xs text-muted-foreground">{helper}</div>}
        </div>
    );
}
