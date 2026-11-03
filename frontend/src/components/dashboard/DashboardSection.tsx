import type { ReactNode } from "react";
import { AlertTriangle, Inbox, RotateCcw, type LucideIcon } from "lucide-react";

import EmptyState from "@/components/EmptyState";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

type DashboardSectionProps = {
    id?: string;
    title: string;
    description?: ReactNode;
    actions?: ReactNode;
    /** Shows a skeleton in place of the body. */
    loading?: boolean;
    /** Message from a failed section (`{ error }`). Replaces the body. */
    error?: string | null;
    /** Refetches this section alone. Shown with the error message. */
    onRetry?: () => void;
    /** A retry request is in flight. Shows the skeleton, not the old error. */
    retrying?: boolean;
    /** Renders the empty state instead of the body. */
    empty?: boolean;
    emptyTitle?: string;
    emptyIcon?: LucideIcon;
    className?: string;
    bodyClassName?: string;
    children?: ReactNode;
};

export default function DashboardSection({
    id,
    title,
    description,
    actions,
    loading = false,
    error,
    onRetry,
    retrying = false,
    empty = false,
    emptyTitle = "Nothing to show",
    emptyIcon = Inbox,
    className,
    bodyClassName,
    children,
}: DashboardSectionProps) {
    const headingId = id ? `${id}-title` : undefined;
    return (
        <Card
            id={id}
            aria-labelledby={headingId}
            className={cn("scroll-mt-24 overflow-hidden border-slate-200 dark:border-slate-800", className)}
        >
            <CardHeader className="flex flex-row flex-wrap items-start justify-between gap-3 space-y-0 border-b border-slate-200 pb-3 dark:border-slate-800">
                <div className="min-w-0">
                    <h2 id={headingId} className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                        {title}
                    </h2>
                    {description && (
                        <div className="mt-0.5 text-xs text-slate-500 dark:text-slate-400">{description}</div>
                    )}
                </div>
                {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
            </CardHeader>
            <CardContent className={cn("p-0", bodyClassName)} aria-busy={loading || undefined}>
                {loading || retrying ? (
                    <div className="space-y-3 p-4" data-testid="section-skeleton">
                        <Skeleton className="h-4 w-1/3" />
                        <Skeleton className="h-16 w-full" />
                    </div>
                ) : error ? (
                    <div role="alert" className="m-4 flex flex-wrap items-start gap-3 rounded-md border border-red-200 bg-red-50 px-3 py-2.5 text-sm text-red-900 dark:border-red-900/40 dark:bg-red-950/30 dark:text-red-200">
                        <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
                        <span className="min-w-0 flex-1">{error}. The rest of the dashboard is unaffected.</span>
                        {onRetry && (
                            <Button variant="secondary" size="sm" onClick={onRetry} aria-label={`Retry ${title}`}>
                                <RotateCcw className="size-3.5" aria-hidden="true" />
                                Retry
                            </Button>
                        )}
                    </div>
                ) : empty ? (
                    <EmptyState icon={emptyIcon} title={emptyTitle} size="default" />
                ) : (
                    children
                )}
            </CardContent>
        </Card>
    );
}
