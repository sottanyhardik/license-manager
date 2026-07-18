import * as React from "react";
import { cn } from "@/lib/utils";

interface PageHeaderProps {
    pretitle?: React.ReactNode;
    title?: React.ReactNode;
    description?: React.ReactNode;
    actions?: React.ReactNode;
    children?: React.ReactNode;
    className?: string;
}

/**
 * Tailwind/shadcn page header. API-compatible with the legacy PageHeader
 * (pretitle / title / description / actions) for drop-in migration.
 *
 * Design: Clean, enterprise-grade header with clear visual hierarchy:
 * - pretitle: all-caps category label (gray, 11px)
 * - title: prominent h1 (24px bold)
 * - description: muted context (13px)
 * - actions: right-aligned CTA group
 */
export default function PageHeader({
    pretitle,
    title,
    description,
    actions,
    children,
    className,
}: PageHeaderProps) {
    return (
        <div
            className={cn(
                "mb-5 flex flex-wrap items-center justify-between gap-x-4 gap-y-3",
                "border-b border-border/60 pb-4",
                className
            )}
        >
            {/* Left: Breadcrumb + title + description */}
            <div className="min-w-0 flex-1">
                {pretitle && (
                    <div className="mb-1 flex items-center gap-1.5 text-[10.5px] font-semibold uppercase tracking-widest text-muted-foreground/70">
                        {pretitle}
                    </div>
                )}
                {title && (
                    <h1 className="text-[1.375rem] font-bold leading-tight tracking-tight text-foreground">
                        {title}
                    </h1>
                )}
                {description && (
                    <p className="mt-1 text-[12.5px] leading-snug text-muted-foreground">
                        {description}
                    </p>
                )}
                {children}
            </div>

            {/* Right: Actions */}
            {actions && (
                <div className="flex shrink-0 flex-wrap items-center gap-2">
                    {actions}
                </div>
            )}
        </div>
    );
}
