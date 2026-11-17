import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface StickyFormBarProps {
    position: "top" | "bottom";
    /** When false, children render untouched (lets callers gate per entity). */
    enabled?: boolean;
    /** Accessible name for the landmark region. */
    label: string;
    className?: string;
    children: ReactNode;
}

/**
 * Presentational sticky bar for workspace forms (header or action footer).
 * Mirrors the Licence form's sticky pattern. Footer is a labelled region.
 */
export function StickyFormBar({ position, enabled = true, label, className, children }: StickyFormBarProps) {
    if (!enabled) return <>{children}</>;
    return (
        <div
            role="region"
            aria-label={label}
            data-testid={`sticky-form-${position}`}
            className={cn(
                "sticky z-20 bg-background/95 backdrop-blur supports-[backdrop-filter]:bg-background/90",
                position === "top"
                    ? "top-0 -mx-1 border-b border-border/70 px-1 py-3"
                    : "bottom-0 -mx-4 border-x border-t border-border/70 bg-card/95 px-4 py-3 shadow-[0_-6px_16px_rgba(26,58,82,0.06)] sm:-mx-6 sm:px-6",
                className,
            )}
        >
            {children}
        </div>
    );
}

export default StickyFormBar;
