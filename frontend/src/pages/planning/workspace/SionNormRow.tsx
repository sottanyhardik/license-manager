import { memo, useCallback, type MouseEvent, type ReactNode } from "react";
import { Calendar, ChevronRight, GitBranch, Layers, ListChecks } from "lucide-react";

import type { SionNormSummary } from "@/api/planningRuleApi";
import { StatusBadge } from "@/components/shared";
import { cn } from "@/lib/utils";
import { displayDate } from "./normConfig";

/** Elements that handle their own clicks inside the header; clicks on them never toggle the row. */
const INTERACTIVE = "button, a, input, select, [role=menuitem]";

function Meta({ icon: Icon, label, children, className }: { icon: typeof Calendar; label: string; children: ReactNode; className?: string }) {
    return (
        <span className={cn("inline-flex min-w-0 items-center gap-1 whitespace-nowrap", className)}>
            <Icon className="size-3.5" aria-hidden="true" />
            <span className="sr-only">{label} </span>
            {children}
        </span>
    );
}

export interface SionNormRowProps {
    norm: SionNormSummary;
    expanded: boolean;
    onToggle: (id: number) => void;
    /** Inline detail strip shown under the header while expanded (actions, version). */
    detailBar?: ReactNode;
    /** Expanded workspace body; rendered only while expanded. */
    children?: ReactNode;
}

/**
 * One SION norm in the /planning list — same compact header row and inline
 * expanded workspace as the Licence register's `LicenceCard`.
 */
export const SionNormRow = memo(function SionNormRow({ norm, expanded, onToggle, detailBar, children }: SionNormRowProps) {
    const regionId = `sion-norm-content-${norm.id}`;
    const toggle = useCallback(() => onToggle(norm.id), [onToggle, norm.id]);
    const onHeaderClick = useCallback((e: MouseEvent<HTMLDivElement>) => {
        if ((e.target as HTMLElement).closest(INTERACTIVE)) return;
        toggle();
    }, [toggle]);

    const ruleCount = norm.active_rule_count || norm.registry_rule_count;
    const ruleSource = norm.active_rule_count ? "" : norm.registry_rule_count ? " (registry)" : "";
    const actionCount = norm.profile_action_count || norm.registry_action_count;
    const splitCount = norm.split_rule_count + norm.registry_split_count + (norm.profile_split_count ?? 0);
    const version = norm.max_rule_version ?? norm.profile_version;

    return (
        <article
            aria-label={`SION norm ${norm.norm_class}`}
            className={cn(
                "min-w-0 overflow-hidden rounded-lg border bg-card transition-colors",
                expanded ? "border-ring/40" : "border-border hover:border-foreground/20",
            )}
        >
            <div onClick={onHeaderClick} className={cn("flex cursor-pointer flex-wrap items-center gap-x-4 gap-y-1 px-3 py-2 md:px-4", expanded && "bg-muted/40")}>
                <div className="flex min-w-0 items-center gap-2">
                    <button
                        type="button"
                        onClick={toggle}
                        aria-expanded={expanded}
                        aria-controls={regionId}
                        aria-label={`${expanded ? "Collapse" : "Expand"} SION norm ${norm.norm_class}`}
                        className="inline-flex size-7 shrink-0 cursor-pointer items-center justify-center rounded-md text-muted-foreground outline-none hover:bg-muted hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
                    >
                        <ChevronRight className={cn("size-4 transition-transform duration-150 motion-reduce:transition-none", expanded && "rotate-90")} aria-hidden="true" />
                    </button>
                    <span className="min-w-[3.5rem] font-mono text-base font-semibold tracking-tight">{norm.norm_class}</span>
                </div>

                <div className="order-3 flex min-w-0 basis-full flex-wrap items-center gap-x-3 gap-y-0.5 pl-9 text-xs text-muted-foreground lg:order-none lg:basis-auto lg:flex-1 lg:pl-0">
                    {norm.description && <span className="max-w-[22rem] truncate text-foreground/80" title={norm.description}>{norm.description}</span>}
                    <Meta icon={ListChecks} label="Rules">{ruleCount} rule{ruleCount === 1 ? "" : "s"}{ruleSource}</Meta>
                    {actionCount > 0 && <Meta icon={Layers} label="Actions">{actionCount} action{actionCount === 1 ? "" : "s"}</Meta>}
                    {splitCount > 0 && <span className="rounded-sm border border-border px-1.5 py-px text-xs text-foreground/80"><GitBranch className="mr-1 inline size-3" aria-hidden="true" />Split{splitCount > 1 ? ` ×${splitCount}` : ""}</span>}
                    {norm.has_entitlement_profile && <span className="rounded-sm border border-border px-1.5 py-px text-xs text-foreground/80">Entitlement mapping</span>}
                    {norm.last_updated && <Meta icon={Calendar} label="Last updated">{displayDate(norm.last_updated)}</Meta>}
                </div>

                <div className="ml-auto flex shrink-0 items-center gap-3">
                    {version != null && <span className="text-xs tabular-nums text-muted-foreground">v{version}</span>}
                    <StatusBadge tone={norm.is_active ? "success" : "neutral"} label={norm.is_active ? "Active" : "Inactive"} />
                </div>
            </div>

            {expanded && (
                <div id={regionId} role="region" aria-label={`SION norm ${norm.norm_class} workspace`} className="border-t border-border">
                    {detailBar && <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-1.5 border-b border-border/60 px-3 py-1.5 md:px-4">{detailBar}</div>}
                    <div className="min-w-0 px-3 pb-3 pt-1.5 md:px-4">{children}</div>
                </div>
            )}
        </article>
    );
});
