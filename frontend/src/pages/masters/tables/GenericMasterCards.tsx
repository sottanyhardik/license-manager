/**
 * GenericMasterCards: the list for every simple master (`/masters/:entity`).
 * Same row anatomy as the licence register (`features/licenses/LicenceCard`):
 * bordered compact rows, a primary identifier that opens the record, muted
 * meta fields, a status badge and one shared ActionMenu. Columns come from the
 * backend `list_display` metadata, so a new master needs no UI code.
 */
import { Link } from "react-router-dom";
import { Eye, Pencil, Trash2 } from "lucide-react";
import { ActionMenu, EmptyState, LoadingState, StatusBadge, type ActionMenuItem } from "@/components/shared";
import { saveFilterState } from "../../../utils/filterPersistence";
import { getMasterRecordKey } from "../masterListConfig";
import { formatMasterLabel, formatMasterValue, readMasterField } from "../masterDetailFields";

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
}

/** `is_active` is shown as a status badge, not as a meta field. */
const STATUS_FIELD = "is_active";

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
}: GenericMasterCardsProps) {
    if (loading) return <LoadingState variant="skeleton-rows" rows={6} label={`Loading ${entityTitle ?? "records"}`} />;

    if (data.length === 0) {
        return (
            <EmptyState
                size="page"
                title={`No ${entityTitle ? entityTitle.toLowerCase() : "records"} found`}
                description="Try adjusting your search or filters."
            />
        );
    }

    const columns: string[] = metadata.list_display || [];
    const [primary, ...meta] = columns;
    const fieldMeta: Record<string, { label?: string }> = metadata.field_meta || {};
    const rememberList = () => saveFilterState(entityName, {
        filters: filterParams,
        pagination: { currentPage, pageSize },
        search: "",
    });

    return (
        <ul className="flex min-w-0 flex-col gap-1.5" aria-label={entityTitle ?? entityName}>
            {data.map(item => {
                const key = getMasterRecordKey(entityName, item);
                const detailPath = `/masters/${entityName}/${key}`;
                const title = formatMasterValue(primary ? readMasterField(item, primary) : undefined) ?? `#${item.id}`;
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
                            className="flex min-w-0 flex-wrap items-center gap-x-4 gap-y-1 rounded-lg border border-border bg-card px-3 py-2 transition-colors hover:border-foreground/20 md:px-4"
                        >
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
    );
}
