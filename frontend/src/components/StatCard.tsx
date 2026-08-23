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
    /** Small, muted line under the primary value — e.g. an abbreviated
     * Lakh/Crore form for currency cards. Renders nothing when omitted. */
    secondaryValue?: React.ReactNode;
    /** Native `title=""` attribute on the value element — full-precision
     * value on hover. Not set when omitted. */
    title?: string;
    /** Opt-in to the denser layout (tighter padding/icon/gap) and
     * length-aware value sizing, for pages whose values can be long
     * currency strings. Defaults to `false` so every EXISTING caller
     * (Dashboard, ReconciliationIssues, ReconciliationPanel) keeps
     * rendering at its original size/spacing/fixed font — this prop must
     * be explicitly passed `true` to change anything for them. */
    compact?: boolean;
}

// Length-aware sizing for string values only (a plain `.length` check at
// render time, never a DOM measurement) — keeps long, unbreakable currency
// strings (e.g. "1,26,90,443.00") from clipping against the card's own
// `overflow-hidden`. Only ever consulted when `compact` is true — the
// default (non-compact) callers always get the original fixed size
// regardless of their value's type/length (this also sidesteps a real bug
// the compact mode would otherwise inherit: `cif_difference` on the
// Reconciliation pages arrives as a STRING at runtime — DRF's default
// `COERCE_DECIMAL_TO_STRING` — so a length check on non-compact callers
// would have silently shrunk that one card on real data, not just in the
// currently-zero test fixtures).
// Thresholds are deliberately conservative: undershooting is invisible,
// overshooting reintroduces the clipping bug.
function valueTextSize(value: React.ReactNode): string {
    if (typeof value !== "string") return "text-2xl";
    const len = value.length;
    if (len <= 6) return "text-2xl";
    if (len <= 10) return "text-xl";
    if (len <= 14) return "text-lg";
    return "text-base";
}

export default function StatCard({
    label, value, icon: Icon, tone = "primary", onClick, loading, secondaryValue, title, compact = false,
}: StatCardProps) {
    const t = TONE[tone];
    const interactive = !!onClick;
    const Comp = interactive ? "button" : "div";
    return (
        <Comp
            onClick={onClick}
            className={cn(
                // Base card — clean, no left border
                "app-stat-card relative flex w-full items-center overflow-hidden rounded-xl border border-border/70 bg-card text-left",
                compact ? "gap-3 px-3.5 py-3" : "gap-3.5 px-4 py-3.5",
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
                    "relative z-10 flex shrink-0 items-center justify-center rounded-lg",
                    compact ? "size-9" : "size-10",
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
                <div
                    title={title}
                    className={cn(
                        "mt-0.5 font-bold leading-none tracking-tight text-foreground tabular-nums",
                        // Only guaranteed single-line in compact mode — the
                        // default (non-compact) callers never had
                        // `whitespace-nowrap` before this task and keep not
                        // having it, for genuine byte-for-byte parity.
                        compact && "whitespace-nowrap",
                        // Skip the length-based lookup while loading — the
                        // skeleton placeholder below has its own fixed
                        // h-7/w-14 sizing, independent of the value's
                        // eventual length.
                        compact && !loading ? valueTextSize(value) : compact ? "text-2xl" : "text-[1.6rem]",
                    )}
                >
                    {loading
                        ? <span className="inline-block h-7 w-14 animate-pulse rounded-md bg-muted" />
                        : (value ?? "—")}
                </div>
                {!loading && secondaryValue != null && (
                    <div className="mt-0.5 whitespace-nowrap text-xs font-medium text-muted-foreground">
                        {secondaryValue}
                    </div>
                )}
            </div>
        </Comp>
    );
}
