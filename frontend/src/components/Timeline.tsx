import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export interface TimelineItem {
    id: string | number;
    /** Small colored dot class, e.g. "bg-primary" — pick per row_kind/category. */
    dotClassName?: string;
    title: ReactNode;
    subtitle?: ReactNode;
    meta?: ReactNode;
}

interface TimelineProps {
    items: TimelineItem[];
    emptyMessage?: string;
    className?: string;
}

/**
 * Small, reusable vertical timeline: a left rail line with a dot per item.
 * No existing component covers this shape in the app, so this is a new,
 * deliberately minimal primitive — a `<div>` with `border-left` plus
 * absolutely-positioned dots, per the brief (not over-engineered).
 */
export default function Timeline({ items, emptyMessage = "No timeline entries.", className }: TimelineProps) {
    if (items.length === 0) {
        return <p className="text-sm text-muted-foreground">{emptyMessage}</p>;
    }

    return (
        <ol className={cn("relative border-l border-border pl-5", className)}>
            {items.map((item) => (
                <li key={item.id} className="relative mb-5 last:mb-0">
                    <span
                        aria-hidden="true"
                        className={cn(
                            "absolute -left-[1.4rem] top-1 size-2.5 rounded-full ring-4 ring-background",
                            item.dotClassName ?? "bg-primary"
                        )}
                    />
                    <div className="text-sm font-medium text-foreground">{item.title}</div>
                    {item.subtitle && <div className="text-xs text-muted-foreground">{item.subtitle}</div>}
                    {item.meta && <div className="mt-0.5 text-xs text-muted-foreground/80">{item.meta}</div>}
                </li>
            ))}
        </ol>
    );
}
