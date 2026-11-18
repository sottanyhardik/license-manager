/**
 * GenericMasterCards: the list for every simple master (`/masters/:entity`).
 * Same row anatomy as the licence register (`features/licenses/LicenceCard`):
 * one compact bordered row per record — expand chevron, a monospace identifier
 * that opens the record, the master's own columns, a status badge and one
 * shared ActionMenu — expanding in place to secondary details. Columns come
 * from `masterColumns.ts` (one config per master), so a new master needs
 * configuration, not UI code.
 *
 * Bulk actions: offered when the backend lists them in `metadata.bulk_actions`
 * and the user can write. Selection is per page (like DataTable) and clears
 * whenever the page's rows change.
 */
import { useEffect, useMemo, useState, type MouseEvent } from "react";
import { Link } from "react-router-dom";
import { ChevronRight, CircleCheck, CircleOff, Eye, Pencil, Trash2, X } from "lucide-react";
import { ActionMenu, BulkSelectionSummary, EmptyState, LoadingState, StatusBadge, TONE_MAP, type ActionMenuItem } from "@/components/shared";
import { cn } from "@/lib/utils";
import { useOptionalConfirm, type ConfirmOptions } from "@/components/shared/ConfirmDialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { getMasterRecordKey, getMasterRecordLookup } from "../masterListConfig";
import { formatMasterValue, readMasterField } from "../masterDetailFields";
import { masterColumnLabel, resolveMasterColumns } from "../masterColumns";
import MasterRecordPanel from "../MasterRecordPanel";

export type MasterBulkAction = "activate" | "deactivate" | "delete";

export interface MasterBulkResult {
    action: MasterBulkAction;
    requested: number;
    succeeded: number;
    failed: number;
    results: { key: string; ok: boolean; error?: string }[];
}

interface GenericMasterCardsProps {
    loading: boolean;
    data: any[];
    metadata: Record<string, any>;
    entityName: string;
    entityTitle?: string;
    filterParams: Record<string, any>;
    currentPage: number;
    pageSize: number;
    /** Kept for callers; records open and edit inline, so the rows never navigate away. */
    navigate?: (path: string) => void;
    onDelete: (item: any) => void;
    /** Edit/Delete are shown only to users the API lets write (defaults to true). */
    canWrite?: boolean;
    /** Runs one generic bulk request (`POST masters/<entity>/bulk/`). */
    onBulk?: (action: MasterBulkAction, keys: string[]) => Promise<MasterBulkResult>;
    /**
     * Controlled expansion (raw record lookup, e.g. from `/masters/:entity/:id`). With `onExpandedChange`
     * the owner (MasterList) keeps it in the URL; without it the rows keep it locally.
     */
    expandedLookup?: string | null;
    onExpandedChange?: (lookup: string | null) => void;
    /** First tab for the record named in the entry URL (old `?tab=` / `/edit` links) — that record only. */
    initialRecordTab?: { lookup: string; tab: string };
}

/** `is_active` is shown as a status badge, not as a column. */
const STATUS_FIELD = "is_active";
/** Controls inside a row that keep their own click behaviour (row click toggles otherwise). */
const ROW_CONTROLS = "a,button,input,[role=checkbox],[role=menu],[role=menuitem]";

const BULK_LABEL: Record<MasterBulkAction, { label: string; icon: typeof Trash2; done: string }> = {
    activate: { label: "Activate", icon: CircleCheck, done: "activated" },
    deactivate: { label: "Deactivate", icon: CircleOff, done: "deactivated" },
    delete: { label: "Delete", icon: Trash2, done: "deleted" },
};

export default function GenericMasterCards({
    loading,
    data,
    metadata,
    entityName,
    entityTitle,
    onDelete,
    canWrite = true,
    onBulk,
    expandedLookup,
    onExpandedChange,
    initialRecordTab,
}: GenericMasterCardsProps) {
    // The app mounts ConfirmProvider (App.tsx); the browser dialog is only a fallback for bare test harnesses.
    const sharedConfirm = useOptionalConfirm();
    const confirm = (opts: ConfirmOptions) => sharedConfirm ? sharedConfirm(opts) : Promise.resolve(window.confirm(opts.title));
    const [selected, setSelected] = useState<Set<string>>(() => new Set());
    const [localExpanded, setLocalExpanded] = useState<string | null>(null);
    const controlled = onExpandedChange !== undefined;
    const expandedKey = controlled ? (expandedLookup ?? null) : localExpanded;
    const setExpanded = (lookup: string | null) => (controlled ? onExpandedChange(lookup) : setLocalExpanded(lookup));
    // Row menu "Edit": open the record (if needed) and switch its panel to the Edit tab.
    const [tabRequest, setTabRequest] = useState<{ lookup: string; tab: string; n: number } | null>(null);
    const openOnTab = (lookup: string, tab: string) => {
        setTabRequest(prev => ({ lookup, tab, n: (prev?.n ?? 0) + 1 }));
        if (expandedKey !== lookup) setExpanded(lookup);
    };
    const panelTabProps = (lookup: string) => ({
        initialTab: tabRequest?.lookup === lookup ? tabRequest.tab : initialRecordTab?.lookup === lookup ? initialRecordTab.tab : undefined,
        tabRequest: tabRequest?.lookup === lookup ? tabRequest : undefined,
        canWrite,
    });
    const [pending, setPending] = useState<MasterBulkAction | null>(null);
    // Titles are captured when the request is made: deleted rows leave the refreshed list.
    const [outcome, setOutcome] = useState<{ result: MasterBulkResult; titles: Record<string, string> } | null>(null);

    const bulkActions: MasterBulkAction[] = canWrite && onBulk ? (metadata.bulk_actions || []) : [];
    const pageKeys = useMemo(() => data.map(item => getMasterRecordLookup(entityName, item)), [data, entityName]);
    // A new page, filter or refetch replaces the rows: never act on rows the user can no longer see. The URL-owned
    // open record stays open (it is shown pinned above the list when it is not on this page).
    useEffect(() => { setSelected(new Set()); if (!controlled) setLocalExpanded(null); }, [pageKeys, controlled]);
    // A direct link / back navigation to a record brings its row into view only when the row's header is off
    // screen; opening a visible row (a click) never moves the page, so the list scroll position is kept.
    useEffect(() => {
        if (!expandedKey) return;
        const row = document.querySelector<HTMLElement>(`[data-master-lookup="${CSS.escape(expandedKey)}"]`);
        if (!row) return;
        const { top } = row.getBoundingClientRect();
        if (top < 0 || top > window.innerHeight - 48) row.scrollIntoView({ block: "start" });
    }, [expandedKey, pageKeys]);

    if (loading) return <LoadingState variant="skeleton-rows" rows={6} label={`Loading ${entityTitle ?? "records"}`} />;

    const resultsPanel = outcome && <BulkResults outcome={outcome.result} titles={outcome.titles} onDismiss={() => setOutcome(null)} />;

    if (data.length === 0) {
        return (
            <>
                {resultsPanel}
                <EmptyState
                    size="page"
                    title={`No ${entityTitle ? entityTitle.toLowerCase() : "records"} found`}
                    description="Try adjusting your search or filters."
                />
            </>
        );
    }

    const { columns } = resolveMasterColumns(entityName, metadata);
    const [primary, ...cells] = columns;
    const fieldMeta: Record<string, { label?: string }> = metadata.field_meta || {};
    const template = columns.map(c => c.width ?? "minmax(8rem,1fr)").join(" ");
    const hasStatus = data.some(item => STATUS_FIELD in item);
    const showSelect = bulkActions.length > 0;
    const titleOf = (item: Record<string, unknown>) =>
        formatMasterValue(primary ? readMasterField(item, primary.field) : undefined) ?? `#${item.id}`;
    const allSelected = selected.size > 0 && selected.size === pageKeys.length;
    const toggleSelected = (key: string, on: boolean) => setSelected(prev => {
        const next = new Set(prev);
        if (on) next.add(key); else next.delete(key);
        return next;
    });

    const runBulk = async (action: MasterBulkAction) => {
        if (!onBulk || selected.size === 0) return;
        const keys = pageKeys.filter(key => selected.has(key));
        const titles = Object.fromEntries(data.map((item, index) => [pageKeys[index], titleOf(item)]));
        const noun = `${keys.length} ${keys.length === 1 ? "record" : "records"}`;
        const ok = await confirm({
            title: `${BULK_LABEL[action].label} ${noun}?`,
            description: action === "delete"
                ? "Each record is deleted separately. Records still used elsewhere are refused and listed; the rest are deleted. This cannot be undone."
                : `Each of the ${noun} is updated separately; any that fail are listed.`,
            confirmLabel: BULK_LABEL[action].label,
            tone: action === "delete" ? "danger" : "default",
        });
        if (!ok) return;
        setPending(action);
        try {
            setOutcome({ result: await onBulk(action, keys), titles });
            setSelected(new Set());
        } finally {
            setPending(null);
        }
    };

    // The column header and every row use the same slots, so the grid columns line up.
    const trailClass = cn("flex shrink-0 items-center justify-end gap-2", hasStatus ? "w-[7.5rem]" : "w-8");

    return (
        <div className="flex min-w-0 flex-col gap-1.5">
            {resultsPanel}
            {/* One header row: select-all + column labels (desktop) aligned with the row grid; while rows are
                selected the bulk actions take the labels' place (no extra toolbar row). Rows carry sr-only labels. */}
            <div
                data-testid="master-column-header"
                data-slot={showSelect ? "bulk-actions" : undefined}
                className={cn(
                    "min-h-8 items-center gap-x-4 px-3 text-[11px] font-medium uppercase tracking-wide text-muted-foreground md:px-4",
                    showSelect ? "flex" : "hidden lg:flex",
                )}
            >
                {showSelect && (
                    <Checkbox
                        aria-label="Select all on page"
                        checked={allSelected ? true : selected.size > 0 ? "indeterminate" : false}
                        onCheckedChange={(v) => setSelected(v ? new Set(pageKeys) : new Set())}
                    />
                )}
                <span className="size-7 shrink-0" aria-hidden="true" />
                {selected.size > 0 ? (
                    <div className="flex min-w-0 flex-1 flex-wrap items-center gap-2 normal-case tracking-normal">
                        <BulkSelectionSummary count={selected.size}>
                            {bulkActions.map(action => {
                                const { label, icon: Icon } = BULK_LABEL[action];
                                return (
                                    <Button
                                        key={action}
                                        type="button"
                                        size="sm"
                                        variant={action === "delete" ? "destructive" : "outline"}
                                        disabled={pending !== null}
                                        onClick={() => { void runBulk(action); }}
                                    >
                                        <Icon className="size-3.5" aria-hidden="true" />
                                        {pending === action ? `${label}…` : label}
                                    </Button>
                                );
                            })}
                            <Button type="button" size="sm" variant="ghost" onClick={() => setSelected(new Set())} disabled={pending !== null}>
                                Clear
                            </Button>
                        </BulkSelectionSummary>
                    </div>
                ) : (
                    <>
                        <div aria-hidden="true" className="hidden min-w-0 flex-1 gap-x-4 lg:grid" style={{ gridTemplateColumns: template }}>
                            {columns.map(column => (
                                <span key={column.field} className={cn("truncate", column.align === "end" && "text-right")}>
                                    {masterColumnLabel(column, fieldMeta)}
                                </span>
                            ))}
                        </div>
                        <span aria-hidden="true" className={cn(trailClass, "hidden lg:flex")}>{hasStatus ? "Status" : ""}</span>
                    </>
                )}
            </div>

            {expandedKey && !pageKeys.includes(expandedKey) && (
                // Opened by URL but not on this page (bookmark, other page/filter): shown pinned, same panel.
                <article aria-label={`${entityTitle ?? "Record"} ${expandedKey}`} className="min-w-0 overflow-hidden rounded-lg border border-ring/40 bg-card" data-master-lookup={expandedKey}>
                    <div className="flex items-center gap-x-4 bg-muted/40 px-3 py-2 md:px-4">
                        <span className="min-w-0 flex-1 truncate text-base font-semibold tracking-tight">{expandedKey}</span>
                        <span className="text-xs text-muted-foreground">Not on this page</span>
                        <Button type="button" size="icon" variant="ghost" aria-label={`Close ${expandedKey}`} onClick={() => setExpanded(null)}>
                            <X className="size-4" aria-hidden="true" />
                        </Button>
                    </div>
                    <div role="region" aria-label={`${expandedKey} details`} className="min-w-0 border-t border-border px-3 pb-2 pt-1.5 md:px-4">
                        <MasterRecordPanel entity={entityName} lookup={expandedKey} label={`${entityTitle ?? entityName} ${expandedKey}`} {...panelTabProps(expandedKey)} />
                    </div>
                </article>
            )}

            <ul className="flex min-w-0 flex-col gap-1.5" aria-label={entityTitle ?? entityName}>
                {data.map((item, index) => {
                    const lookup = pageKeys[index];
                    const key = getMasterRecordKey(entityName, item);
                    const detailPath = `/masters/${entityName}/${key}`;
                    const title = titleOf(item);
                    // Every record expands: the inline panel loads the full record (licence register pattern).
                    const canExpand = true;
                    const expanded = expandedKey === lookup;
                    const isSelected = selected.has(lookup);
                    const regionId = `master-row-${entityName}-${lookup.replace(/[^A-Za-z0-9_-]/g, "_")}`;
                    const toggleExpanded = () => setExpanded(expanded ? null : lookup);
                    // Plain clicks open the record inline; modified clicks keep the link's new-tab behaviour.
                    const openInline = (event: MouseEvent<HTMLAnchorElement>) => {
                        if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
                        event.preventDefault();
                        setExpanded(lookup);
                    };
                    const actions: ActionMenuItem[] = [
                        { id: "open", label: "Open record", icon: Eye, onSelect: () => setExpanded(lookup) },
                        ...(canWrite ? [
                            { id: "edit", label: "Edit", icon: Pencil, onSelect: () => openOnTab(lookup, "edit") },
                            { id: "delete", label: "Delete", icon: Trash2, tone: "danger" as const, separatorBefore: true, onSelect: () => onDelete(item) },
                        ] : []),
                    ];
                    return (
                        <li key={item.id ?? key} className="min-w-0">
                            <article
                                aria-label={`${entityTitle ?? "Record"} ${title}`}
                                data-master-lookup={lookup}
                                data-state={isSelected ? "selected" : undefined}
                                className={cn(
                                    "min-w-0 overflow-hidden rounded-lg border bg-card transition-colors",
                                    expanded || isSelected ? "border-ring/40" : "border-border hover:border-foreground/20",
                                )}
                            >
                                {/* Header row. Mouse: anywhere toggles (licence register); keyboard: the chevron (aria-expanded). */}
                                <div
                                    onClick={(event) => {
                                        if (!canExpand || (event.target as HTMLElement).closest(ROW_CONTROLS)) return;
                                        toggleExpanded();
                                    }}
                                    className={cn(
                                        "flex min-w-0 items-center gap-x-4 px-3 py-2 md:px-4",
                                        canExpand && "cursor-pointer",
                                        (expanded || isSelected) && "bg-muted/40",
                                    )}
                                >
                                    {showSelect && (
                                        <Checkbox aria-label={`Select ${title}`} checked={isSelected} onCheckedChange={(v) => toggleSelected(lookup, !!v)} />
                                    )}
                                    {canExpand ? (
                                        <button
                                            type="button"
                                            onClick={toggleExpanded}
                                            aria-expanded={expanded}
                                            aria-controls={regionId}
                                            aria-label={`${expanded ? "Collapse" : "Expand"} ${title}`}
                                            className="inline-flex size-7 shrink-0 cursor-pointer items-center justify-center rounded-md text-muted-foreground outline-none hover:bg-muted hover:text-foreground focus-visible:ring-[3px] focus-visible:ring-ring/50"
                                        >
                                            <ChevronRight
                                                className={cn("size-4 transition-transform duration-150 motion-reduce:transition-none", expanded && "rotate-90")}
                                                aria-hidden="true"
                                            />
                                        </button>
                                    ) : <span className="size-7 shrink-0" aria-hidden="true" />}

                                    <dl className="flex min-w-0 flex-1 flex-wrap items-baseline gap-x-4 gap-y-0.5 lg:grid" style={{ gridTemplateColumns: template }}>
                                        <div className="min-w-0 basis-full lg:basis-auto">
                                            <dt className="sr-only">{primary ? masterColumnLabel(primary, fieldMeta) : "Record"}</dt>
                                            <dd className="min-w-0 truncate">
                                                <Link
                                                    to={detailPath}
                                                    onClick={openInline}
                                                    aria-expanded={expanded}
                                                    className={cn(
                                                        "rounded-sm text-base font-semibold tracking-tight text-primary underline-offset-2 outline-none hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50",
                                                        primary?.mono && "font-mono",
                                                    )}
                                                >
                                                    {title}
                                                </Link>
                                            </dd>
                                        </div>
                                        {cells.map(column => {
                                            const value = formatMasterValue(readMasterField(item, column.field));
                                            return (
                                                <div key={column.field} className={cn("flex min-w-0 items-baseline gap-1 text-xs lg:block", column.align === "end" && "lg:text-right")}>
                                                    <dt className="shrink-0 text-muted-foreground/70 lg:sr-only">{masterColumnLabel(column, fieldMeta)}</dt>
                                                    <dd
                                                        className={cn("min-w-0 truncate text-foreground/80", column.mono && "font-mono", column.align === "end" && "tabular-nums")}
                                                        title={value ?? undefined}
                                                    >
                                                        {value ?? "—"}
                                                    </dd>
                                                </div>
                                            );
                                        })}
                                    </dl>

                                    <div className={trailClass}>
                                        {STATUS_FIELD in item && (
                                            <StatusBadge tone={item[STATUS_FIELD] ? "success" : "neutral"} label={item[STATUS_FIELD] ? "Active" : "Inactive"} />
                                        )}
                                        <ActionMenu items={actions} label={`Actions for ${title}`} />
                                    </div>
                                </div>

                                {expanded && (
                                    <div id={regionId} role="region" aria-label={`${title} details`} className="min-w-0 border-t border-border px-3 pb-2 pt-1.5 md:px-4">
                                        <MasterRecordPanel entity={entityName} lookup={lookup} label={`${entityTitle ?? entityName} ${title}`} {...panelTabProps(lookup)} />
                                    </div>
                                )}
                            </article>
                        </li>
                    );
                })}
            </ul>
        </div>
    );
}

/** Per-record outcome of the last bulk request; failures keep the server's reason. */
function BulkResults({ outcome, titles, onDismiss }: { outcome: MasterBulkResult; titles: Record<string, string>; onDismiss: () => void }) {
    const failures = outcome.results.filter(r => !r.ok);
    return (
        <div
            role="status"
            className={cn("flex items-start justify-between gap-3 rounded-lg border px-3 py-2 text-sm", TONE_MAP[failures.length === 0 ? "success" : "warning"].outline)}
            data-testid="bulk-results"
        >
            <div className="min-w-0">
                <p className="font-medium text-foreground">
                    {outcome.succeeded} of {outcome.requested} {BULK_LABEL[outcome.action].done}
                    {failures.length > 0 && <span className="text-muted-foreground"> · {failures.length} not changed</span>}
                </p>
                {failures.length > 0 && (
                    <ul className="mt-1 space-y-0.5 text-xs text-muted-foreground">
                        {failures.map(f => (
                            <li key={f.key}><span className="font-mono text-foreground">{titles[f.key] ?? f.key}</span> — {f.error ?? "Refused."}</li>
                        ))}
                    </ul>
                )}
            </div>
            <Button type="button" size="icon" variant="ghost" aria-label="Dismiss bulk results" onClick={onDismiss}>
                <X className="size-4" aria-hidden="true" />
            </Button>
        </div>
    );
}
