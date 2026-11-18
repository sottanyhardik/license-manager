/**
 * WorkspaceToolbar: the Licence register's one-row page toolbar, shared by every ERP workspace.
 *
 *   [Breadcrumb  Title  N records] [search] [Filters ▾ (n)] [status] [actions…]
 *   └─ collapsible "Filters" panel, closed by default ─────────────────────────┘
 *
 * The Licence register renders it through `AdvancedFilter` (collapsible mode); pages that own their own
 * filter state (Licence Ledger, Planning, Ledger Upload) render it directly with their existing controls.
 * Presentation only — no data, filtering or permission logic lives here.
 */
import { Fragment, useId, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import { ChevronDown, Filter, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";

export interface WorkspaceCrumb {
    label: string;
    to?: string;
}

export interface WorkspaceTitleProps {
    title: string;
    /** Parent crumbs; the title is appended as the current page. */
    breadcrumbs?: WorkspaceCrumb[];
    /** Record count; omitted when the workspace has no list. */
    count?: number;
    /** Noun for the count ("record", "licence"); pluralised with "s". */
    countNoun?: string;
}

/** Breadcrumb + H1 + record count, laid out like the Licence register. */
export function WorkspaceTitle({ title, breadcrumbs = [{ label: "Home", to: "/" }], count, countNoun = "record" }: WorkspaceTitleProps) {
    const navigate = useNavigate();
    return (
        <div className="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-0.5">
            <nav aria-label="Breadcrumb" className="text-xs text-muted-foreground">
                {/* Same markup as the Licence register toolbar (plain anchor + client-side navigation). */}
                {breadcrumbs.map(crumb => (
                    <Fragment key={`${crumb.label}-${crumb.to ?? ""}`}>
                        {crumb.to
                            ? <a href={crumb.to} onClick={(e) => { e.preventDefault(); navigate(crumb.to!); }} className="text-inherit no-underline hover:underline">{crumb.label}</a>
                            : <span>{crumb.label}</span>}
                        <span className="mx-1.5 opacity-50">/</span>
                    </Fragment>
                ))}
                <span>{title}</span>
            </nav>
            <h1 className="text-lg font-semibold leading-tight tracking-tight text-foreground">{title}</h1>
            {count !== undefined && (
                <span className="text-xs tabular-nums text-muted-foreground">
                    {count.toLocaleString("en-IN")} {countNoun}{count === 1 ? "" : "s"}
                </span>
            )}
        </div>
    );
}

export interface WorkspaceToolbarProps {
    /** Left side: usually `<WorkspaceTitle …/>`. */
    start?: ReactNode;
    /** Search control (the caller owns its state). */
    search?: ReactNode;
    /** Filter fields; shows the Filters toggle and a collapsible panel (closed by default). */
    filters?: ReactNode;
    /** Applied filter count shown on the toggle. */
    activeFilterCount?: number;
    /** Footer of the filter panel (e.g. Reset). */
    filterActions?: ReactNode;
    /** Controlled open state (optional). */
    filtersOpen?: boolean;
    onFiltersOpenChange?: (open: boolean) => void;
    /** Shows an "Updating" status while a refetch runs. */
    isUpdating?: boolean;
    /** Right side: exports, create, overflow menu. */
    actions?: ReactNode;
    /** Grid used for the filter fields. */
    filterLayout?: "grid" | "wide";
    className?: string;
}

export function WorkspaceToolbar({
    start,
    search,
    filters,
    activeFilterCount = 0,
    filterActions,
    filtersOpen,
    onFiltersOpenChange,
    isUpdating = false,
    actions,
    filterLayout = "grid",
    className,
}: WorkspaceToolbarProps) {
    const panelId = useId();
    const [localOpen, setLocalOpen] = useState(false);
    const open = filtersOpen ?? localOpen;
    const setOpen = (next: boolean) => {
        if (filtersOpen === undefined) setLocalOpen(next);
        onFiltersOpenChange?.(next);
    };
    const hasFilters = filters !== undefined && filters !== null && filters !== false;
    return (
        <div className={className ?? "mb-3 rounded-lg border border-border/70 bg-card shadow-sm"}>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2">
                {start && <div className="min-w-0 flex-1">{start}</div>}
                {search && <div className="w-full sm:w-64 lg:w-72">{search}</div>}
                {hasFilters && (
                    <Button type="button" variant="outline" size="sm" aria-expanded={open} aria-controls={panelId} onClick={() => setOpen(!open)}>
                        <Filter className="size-3.5" aria-hidden="true" />
                        Filters
                        {activeFilterCount > 0 && <span className="rounded-full bg-primary/15 px-1.5 text-xs text-primary">{activeFilterCount}</span>}
                        <ChevronDown className={`size-3.5 transition-transform motion-reduce:transition-none ${open ? "rotate-180" : ""}`} aria-hidden="true" />
                    </Button>
                )}
                {isUpdating && (
                    <span role="status" className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                        <Loader2 className="size-3 animate-spin motion-reduce:animate-none" />Updating
                    </span>
                )}
                {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
            </div>
            {hasFilters && (
                <section id={panelId} aria-label="Filters" hidden={!open} className="border-t border-border/60 p-3">
                    <div className={filterLayout === "grid" ? "grid grid-cols-1 gap-x-4 gap-y-3 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4" : "grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4"}>
                        {filters}
                    </div>
                    {filterActions && <div className="mt-3 flex justify-end">{filterActions}</div>}
                </section>
            )}
        </div>
    );
}
