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
 * Design: a single, calm page-summary surface that keeps navigation, context,
 * and next actions together without competing with the working content below.
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
                "app-page-header mb-6 flex flex-wrap items-center justify-between gap-x-5 gap-y-4",
                "rounded-lg border border-border/60 bg-card px-5 py-4 shadow-sm sm:px-6 sm:py-5",
                className
            )}
        >
            {/* Left: Breadcrumb + title + description */}
            <div className="min-w-0 flex-1">
                {pretitle && (
                    <div className="mb-1.5 flex items-center gap-1.5 text-[10px] font-bold uppercase tracking-wider text-muted-foreground">
                        {pretitle}
                    </div>
                )}
                {title && (
                    <h1 className="text-2xl font-bold leading-tight tracking-tight text-foreground sm:text-[1.625rem] lg:text-3xl">
                        {title}
                    </h1>
                )}
                {description && (
                    <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
                        {description}
                    </p>
                )}
                {children}
            </div>

            {/* Right: Actions */}
            {actions && (
                <div className="flex shrink-0 flex-wrap items-center gap-2 sm:gap-3">
                    {actions}
                </div>
            )}
        </div>
    );
}
