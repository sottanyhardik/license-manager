/**
 * GenericMasterCards: the list for every simple master (`/masters/:entity`).
 * Same row anatomy as the licence register (`features/licenses/LicenceCard`):
 * bordered compact rows, a primary identifier that opens the record, muted
 * meta fields, a status badge and one shared ActionMenu. Columns come from the
 * backend `list_display` metadata, so a new master needs no UI code.
 *
 * Bulk actions: offered when the backend lists them in `metadata.bulk_actions`
 * and the user can write. Selection is per page (like DataTable) and clears
 * whenever the page's rows change.
 */
import { useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { CircleCheck, CircleOff, Eye, Pencil, Trash2, X } from "lucide-react";
import { ActionMenu, BulkSelectionSummary, EmptyState, LoadingState, StatusBadge, TONE_MAP, type ActionMenuItem } from "@/components/shared";
import { cn } from "@/lib/utils";
import { useOptionalConfirm, type ConfirmOptions } from "@/components/shared/ConfirmDialog";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import { saveFilterState } from "../../../utils/filterPersistence";
import { getMasterRecordKey, getMasterRecordLookup } from "../masterListConfig";
import { formatMasterLabel, formatMasterValue, readMasterField } from "../masterDetailFields";

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
    navigate: (path: string) => void;
    onDelete: (item: any) => void;
    /** Edit/Delete are shown only to users the API lets write (defaults to true). */
    canWrite?: boolean;
    /** Runs one generic bulk request (`POST masters/<entity>/bulk/`). */
    onBulk?: (action: MasterBulkAction, keys: string[]) => Promise<MasterBulkResult>;
}

/** `is_active` is shown as a status badge, not as a meta field. */
const STATUS_FIELD = "is_active";

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
    filterParams,
    currentPage,
    pageSize,
    navigate,
    onDelete,
    canWrite = true,
    onBulk,
}: GenericMasterCardsProps) {
    // The app mounts ConfirmProvider (App.tsx); the browser dialog is only a fallback for bare test harnesses.
    const sharedConfirm = useOptionalConfirm();
    const confirm = (opts: ConfirmOptions) => sharedConfirm ? sharedConfirm(opts) : Promise.resolve(window.confirm(opts.title));
    const [selected, setSelected] = useState<Set<string>>(() => new Set());
    const [pending, setPending] = useState<MasterBulkAction | null>(null);
    // Titles are captured when the request is made: deleted rows leave the refreshed list.
    const [outcome, setOutcome] = useState<{ result: MasterBulkResult; titles: Record<string, string> } | null>(null);

    const bulkActions: MasterBulkAction[] = canWrite && onBulk ? (metadata.bulk_actions || []) : [];
    const pageKeys = useMemo(() => data.map(item => getMasterRecordLookup(entityName, item)), [data, entityName]);
    // A new page, filter or refetch replaces the rows: never act on rows the user can no longer see.
    useEffect(() => { setSelected(new Set()); }, [pageKeys]);

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

    const columns: string[] = metadata.list_display || [];
    const [primary, ...meta] = columns;
    const fieldMeta: Record<string, { label?: string }> = metadata.field_meta || {};
    const titleOf = (item: Record<string, unknown>) =>
        formatMasterValue(primary ? readMasterField(item, primary) : undefined) ?? `#${item.id}`;
    const rememberList = () => saveFilterState(entityName, {
        filters: filterParams,
        pagination: { currentPage, pageSize },
        search: "",
    });
    const allSelected = selected.size > 0 && selected.size === pageKeys.length;
    const toggle = (key: string, on: boolean) => setSelected(prev => {
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

    return (
        <div className="flex min-w-0 flex-col gap-1.5">
            {resultsPanel}
            {bulkActions.length > 0 && (
                <div className="flex min-h-9 flex-wrap items-center gap-2 px-1" data-slot="bulk-actions">
                    <Checkbox
                        aria-label="Select all on page"
                        checked={allSelected ? true : selected.size > 0 ? "indeterminate" : false}
                        onCheckedChange={(v) => setSelected(v ? new Set(pageKeys) : new Set())}
                    />
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
            )}
            <ul className="flex min-w-0 flex-col gap-1.5" aria-label={entityTitle ?? entityName}>
                {data.map((item, index) => {
                    const lookup = pageKeys[index];
                    const key = getMasterRecordKey(entityName, item);
                    const detailPath = `/masters/${entityName}/${key}`;
                    const title = titleOf(item);
                    const actions: ActionMenuItem[] = [
                        { id: "open", label: "Open", icon: Eye, onSelect: () => { rememberList(); navigate(detailPath); } },
                        ...(canWrite ? [
                            { id: "edit", label: "Edit", icon: Pencil, onSelect: () => { rememberList(); navigate(`${detailPath}/edit`); } },
                            { id: "delete", label: "Delete", icon: Trash2, tone: "danger" as const, separatorBefore: true, onSelect: () => onDelete(item) },
                        ] : []),
                    ];
                    return (
                        <li key={item.id ?? key} className="min-w-0">
                            <article
                                aria-label={`${entityTitle ?? "Record"} ${title}`}
                                data-state={selected.has(lookup) ? "selected" : undefined}
                                className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-border bg-card px-3 py-2 transition-colors hover:border-foreground/20 data-[state=selected]:border-ring/40 data-[state=selected]:bg-muted/40 md:px-4"
                            >
                                {bulkActions.length > 0 && (
                                    <Checkbox
                                        aria-label={`Select ${title}`}
                                        checked={selected.has(lookup)}
                                        onCheckedChange={(v) => toggle(lookup, !!v)}
                                    />
                                )}
                                <Link
                                    to={detailPath}
                                    onClick={rememberList}
                                    className="min-w-0 truncate rounded-sm font-mono text-base font-semibold tracking-tight text-primary underline-offset-2 outline-none hover:underline focus-visible:ring-[3px] focus-visible:ring-ring/50"
                                >
                                    {title}
                                </Link>
                                <dl className="order-3 flex min-w-0 basis-full flex-wrap items-baseline gap-x-4 gap-y-0.5 text-xs text-muted-foreground lg:order-none lg:basis-auto lg:flex-1">
                                    {meta.filter(column => column !== STATUS_FIELD).map(column => (
                                        <div key={column} className="flex min-w-0 items-baseline gap-1">
                                            <dt className="shrink-0 text-muted-foreground/70">{formatMasterLabel(column, fieldMeta)}</dt>
                                            <dd className="min-w-0 truncate text-foreground/80" title={formatMasterValue(readMasterField(item, column)) ?? undefined}>
                                                {formatMasterValue(readMasterField(item, column)) ?? "—"}
                                            </dd>
                                        </div>
                                    ))}
                                </dl>
                                <div className="ml-auto flex shrink-0 items-center gap-2">
                                    {STATUS_FIELD in item && (
                                        <StatusBadge tone={item[STATUS_FIELD] ? "success" : "neutral"} label={item[STATUS_FIELD] ? "Active" : "Inactive"} />
                                    )}
                                    <ActionMenu items={actions} label={`Actions for ${title}`} />
                                </div>
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
        <div role="status" className={cn("flex items-start justify-between gap-3 rounded-lg border px-3 py-2 text-sm", TONE_MAP[failures.length === 0 ? "success" : "warning"].outline)} data-testid="bulk-results">
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
