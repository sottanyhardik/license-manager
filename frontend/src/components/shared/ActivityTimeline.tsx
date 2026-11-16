import type { ReactNode } from "react";
import { formatDateTime } from "@/utils/dateFormatter";
import { cn } from "@/lib/utils";
import { EmptyState } from "./EmptyState";
import { InlineError } from "./InlineError";
import { LoadingState } from "./LoadingState";
import { TONE_MAP, type Tone } from "./tone";

export interface ActivityItem {
    id: string | number;
    /** ISO timestamp. */
    at: string;
    actor?: string;
    action: string;
    detail?: ReactNode;
    tone?: Tone;
}

export interface ActivityTimelineProps {
    items: ActivityItem[];
    state: { status: "loading" | "error" | "success"; error?: unknown };
    emptyLabel?: string;
    onRetry?: () => void;
}

/** Presentational, ordered activity list (caller fetches, slices and orders). */
export function ActivityTimeline({ items, state, emptyLabel = "No activity yet", onRetry }: ActivityTimelineProps) {
    if (state.status === "loading") return <LoadingState variant="skeleton-rows" label="Loading activity" />;
    if (state.status === "error") return <InlineError error={state.error} onRetry={onRetry} title="Could not load activity" />;
    if (items.length === 0) return <EmptyState size="inline" title={emptyLabel} />;

    return (
        <ol className="relative space-y-4 border-l border-border pl-5">
            {items.map((item) => {
                const tone = item.tone ?? "neutral";
                return (
                    <li key={item.id} className="relative">
                        <span aria-hidden="true" className={cn("absolute -left-[1.6rem] top-1.5 size-2 rounded-full", TONE_MAP[tone].dot)} />
                        <div className="text-sm font-medium text-foreground">
                            {item.action}
                            {item.tone && item.tone !== "neutral" && <span className="sr-only"> ({item.tone})</span>}
                        </div>
                        <div className="text-xs text-muted-foreground">
                            {item.actor && <span>{item.actor} · </span>}
                            <time dateTime={item.at}>{formatDateTime(item.at)}</time>
                        </div>
                        {item.detail && <div className="mt-1 text-sm text-muted-foreground">{item.detail}</div>}
                    </li>
                );
            })}
        </ol>
    );
}
