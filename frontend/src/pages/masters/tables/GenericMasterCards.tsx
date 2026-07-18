import { Inbox, Pencil, Trash2 } from "lucide-react";
import { cn } from "@/lib/utils";
import { saveFilterState } from "../../../utils/filterPersistence";

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
}

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
}: GenericMasterCardsProps) {
    if (loading) {
        return (
            <div className="py-5 text-center">
                <span className="inline-block size-5 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" />
                <div className="mt-2 text-muted-foreground">Loading {entityTitle}...</div>
            </div>
        );
    }

    if (data.length === 0) {
        return (
            <div className="py-5 text-center text-muted-foreground">
                <Inbox className="size-4" aria-hidden="true" />
                <div className="mt-2">No {entityTitle ? entityTitle.toLowerCase() : "records"} found</div>
            </div>
        );
    }

    const columns = metadata.list_display || [];
    const formatLabel = (column: string) => column.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
    const getValue = (item: Record<string, any>, column: string) => {
        const fieldKey = column.replace(/__/g, "_");
        const value = item[fieldKey] !== undefined ? item[fieldKey] : item[column];
        if (value === null || value === undefined || value === "") return null;
        if (typeof value === "boolean") return value ? "Yes" : "No";
        if (typeof value === "object") return JSON.stringify(value);
        return String(value);
    };

    return (
        <div>
            {data.map(item => (
                <div
                    key={item.id}
                    className="mb-1.5 flex items-center gap-3 rounded-[var(--tb-r-md)] border border-border border-l-[4px] border-l-indigo-600 bg-card px-3.5 py-2.5 shadow-sm"
                >
                    <div className="flex min-w-0 flex-1 items-start gap-2">
                        {columns.map((column: string, index: number) => {
                            const value = getValue(item, column);
                            return (
                                <div key={column} className="min-w-0 flex-1">
                                    <div className="mb-0.5 truncate text-[10px] font-semibold uppercase tracking-[0.5px] text-muted-foreground/70">
                                        {formatLabel(column)}
                                    </div>
                                    <div className={cn(
                                        "break-words text-sm",
                                        index === 0 ? "font-semibold text-primary" : "font-normal text-muted-foreground"
                                    )}>
                                        {value ?? <span className="text-border">—</span>}
                                    </div>
                                </div>
                            );
                        })}
                    </div>

                    <div className="flex shrink-0 items-center gap-1.5 self-center">
                        <button
                            type="button"
                            onClick={() => {
                                saveFilterState(entityName, {
                                    filters: filterParams,
                                    pagination: { currentPage, pageSize },
                                    search: "",
                                });
                                navigate(`/masters/${entityName}/${item.id}/edit`);
                            }}
                            title="Edit"
                            className="flex cursor-pointer items-center gap-1 rounded-md border border-primary/30 bg-primary/5 px-2.5 py-1 text-xs text-primary hover:bg-primary/10"
                        >
                            <Pencil className="size-4" aria-hidden="true" /> Edit
                        </button>
                        <button
                            type="button"
                            onClick={() => onDelete(item)}
                            title="Delete"
                            className="flex cursor-pointer items-center gap-1 rounded-md border border-destructive/30 bg-destructive/10 px-2.5 py-1 text-xs text-destructive hover:bg-destructive/20"
                        >
                            <Trash2 className="size-4" aria-hidden="true" />
                        </button>
                    </div>
                </div>
            ))}
        </div>
    );
}
