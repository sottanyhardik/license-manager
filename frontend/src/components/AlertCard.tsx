import React from "react";
import type { LucideIcon } from "lucide-react";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type AlertTone = "danger" | "warning" | "info";

interface AlertCardProps {
    icon: LucideIcon;
    title: string;
    description?: string;
    count: number;
    tone?: AlertTone;
    onViewAll?: () => void;
    loading?: boolean;
}

const TONE_STYLES: Record<AlertTone, { bg: string; border: string; icon: string; text: string }> = {
    danger: {
        bg: "bg-destructive/5",
        border: "border-destructive/30",
        icon: "bg-destructive/10 text-destructive",
        text: "text-destructive",
    },
    warning: {
        bg: "bg-warning/5",
        border: "border-warning/30",
        icon: "bg-warning/10 text-warning",
        text: "text-warning",
    },
    info: {
        bg: "bg-info/5",
        border: "border-info/30",
        icon: "bg-info/10 text-info",
        text: "text-info",
    },
};

/**
 * AlertCard — dashboard urgent action card
 *
 * Displays high-priority operational alerts (expiring licenses, missing DGFT, pending invoices).
 * Shows count, description, and "View all" action button.
 */
export default function AlertCard({
    icon: Icon,
    title,
    description,
    count,
    tone = "danger",
    onViewAll,
    loading = false,
}: AlertCardProps) {
    const styles = TONE_STYLES[tone];

    return (
        <div
            className={cn(
                "flex flex-col gap-3 rounded-lg border px-4 py-4 transition-all duration-200",
                styles.bg,
                styles.border,
                onViewAll && "cursor-pointer hover:shadow-md hover:border-opacity-100",
            )}
        >
            {/* Icon + Title row */}
            <div className="flex items-center gap-2.5">
                <span
                    className={cn(
                        "flex size-7 shrink-0 items-center justify-center rounded-md",
                        styles.icon,
                    )}
                >
                    <Icon className="size-4" strokeWidth={2} />
                </span>
                <h3 className="text-sm font-semibold text-foreground">{title}</h3>
            </div>

            {/* Count + Description */}
            <div className="space-y-1">
                {loading ? (
                    <div className="inline-block h-7 w-12 animate-pulse rounded bg-muted" />
                ) : (
                    <div className={cn("text-2xl font-bold", styles.text)}>
                        {count}
                    </div>
                )}
                {description && (
                    <p className="text-xs text-muted-foreground">{description}</p>
                )}
            </div>

            {/* Action button */}
            {onViewAll && (
                <Button
                    variant="outline"
                    size="sm"
                    onClick={onViewAll}
                    className="w-full justify-between"
                    disabled={loading}
                >
                    <span>View all</span>
                    <ArrowRight className="size-3.5" />
                </Button>
            )}
        </div>
    );
}
