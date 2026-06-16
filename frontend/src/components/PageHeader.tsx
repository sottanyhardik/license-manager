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
                "mb-5 flex flex-wrap items-end justify-between gap-3 border-b border-border/70 pb-4",
                className
            )}
        >
            <div className="min-w-0">
                {pretitle && (
                    <div className="mb-0.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
                        {pretitle}
                    </div>
                )}
                {title && (
                    <h1 className="text-2xl font-bold leading-tight tracking-tight text-foreground">
                        {title}
                    </h1>
                )}
                {description && (
                    <p className="mt-1 text-sm text-muted-foreground">{description}</p>
                )}
                {children}
            </div>
            {actions && (
                <div className="flex flex-wrap items-center gap-2">{actions}</div>
            )}
        </div>
    );
}
