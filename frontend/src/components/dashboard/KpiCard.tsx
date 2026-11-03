import { Info } from "lucide-react";
import { Link } from "react-router-dom";

import { Skeleton } from "@/components/ui/skeleton";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "@/components/ui/tooltip";
import { cn } from "@/lib/utils";

type KpiCardProps = {
    label: string;
    value: string;
    /** Currency or unit shown after the label, e.g. "USD (FC)". */
    unit?: string;
    /** One line of context under the value. Never a trend or a percentage change. */
    context?: string;
    /** How the figure is calculated. Shown on hover and focus of the info button. */
    tooltip: string;
    /** Click-through target. Omit when the figure has no list to open. */
    href?: string;
    loading?: boolean;
    variant?: "primary" | "compact";
};

/**
 * Single KPI component for the dashboard. Primary cards show a large value with
 * context and a calculation tooltip. Compact items are used in secondary strips.
 */
export default function KpiCard({
    label,
    value,
    unit,
    context,
    tooltip,
    href,
    loading = false,
    variant = "primary",
}: KpiCardProps) {
    const primary = variant === "primary";
    const body = (
        <>
            <span className="text-xs font-medium text-slate-500 dark:text-slate-400">
                {label}
                {unit && <span className="ml-1 font-normal text-slate-500 dark:text-slate-400">({unit})</span>}
            </span>
            {loading ? (
                <Skeleton className={cn("mt-2", primary ? "h-7 w-2/3" : "h-5 w-1/2")} />
            ) : (
                <span
                    className={cn(
                        "mt-1 block font-semibold tabular-nums text-slate-900 dark:text-slate-50",
                        primary ? "text-2xl" : "text-base",
                    )}
                >
                    {value}
                </span>
            )}
            {context && !loading && (
                <span className="mt-1 block text-xs text-slate-500 dark:text-slate-400">{context}</span>
            )}
        </>
    );

    const linkClass =
        "block min-w-0 flex-1 rounded-md outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 dark:focus-visible:ring-offset-slate-950";

    return (
        <TooltipProvider delayDuration={150}>
            <div
                className={cn(
                    "flex items-start gap-2 rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-950",
                    !primary && "p-3",
                )}
            >
                {href ? (
                    <Link to={href} className={linkClass} aria-label={`${label}: ${value}. Open list`}>
                        {body}
                    </Link>
                ) : (
                    <div className="min-w-0 flex-1">{body}</div>
                )}
                <Tooltip>
                    <TooltipTrigger asChild>
                        <button
                            type="button"
                            className="shrink-0 rounded-full p-1 text-slate-500 hover:text-slate-700 focus-visible:ring-2 focus-visible:ring-ring focus-visible:outline-none dark:text-slate-500 dark:hover:text-slate-200"
                            aria-label={`How ${label} is calculated`}
                        >
                            <Info className="size-3.5" aria-hidden="true" />
                        </button>
                    </TooltipTrigger>
                    <TooltipContent side="top" className="max-w-xs text-xs leading-relaxed">
                        {tooltip}
                    </TooltipContent>
                </Tooltip>
            </div>
        </TooltipProvider>
    );
}
