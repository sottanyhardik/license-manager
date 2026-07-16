import { Inbox, Pencil, Trash2 } from "lucide-react";

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
            <div className="text-center py-5">
                <span className="inline-block size-5 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" />
                <div className="mt-2 text-muted-foreground">Loading {entityTitle}...</div>
            </div>
        );
    }

    if (data.length === 0) {
        return (
            <div className="text-center py-5 text-muted-foreground">
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
                    style={{
                        display: "flex",
                        alignItems: "center",
                        background: "var(--tb-card-bg)",
                        border: "1px solid var(--tb-border)",
                        borderLeft: "4px solid #4f46e5",
                        borderRadius: "var(--tb-r-md)",
                        marginBottom: "6px",
                        padding: "10px 14px",
                        gap: "12px",
                        boxShadow: "0 1px 3px rgba(0,0,0,0.04)",
                    }}
                >
                    <div style={{ flex: 1, display: "flex", gap: "8px", alignItems: "flex-start", minWidth: 0 }}>
                        {columns.map((column: string, index: number) => {
                            const value = getValue(item, column);
                            return (
                                <div key={column} style={{ flex: "1 1 0", minWidth: 0 }}>
                                    <div style={{ fontSize: 10, color: "var(--tb-text-tertiary)", fontWeight: "600", textTransform: "uppercase", letterSpacing: "0.5px", marginBottom: "2px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                                        {formatLabel(column)}
                                    </div>
                                    <div
                                        style={{
                                            fontSize: 14,
                                            color: index === 0 ? "var(--tb-brand-active)" : "var(--tb-gray-700)",
                                            fontWeight: index === 0 ? "600" : "400",
                                            wordBreak: "break-word",
                                        }}
                                    >
                                        {value ?? <span style={{ color: "var(--tb-border-strong)" }}>—</span>}
                                    </div>
                                </div>
                            );
                        })}
                    </div>

                    <div style={{ display: "flex", gap: "6px", flexShrink: 0, alignSelf: "center" }}>
                        <button
                            onClick={() => {
                                saveFilterState(entityName, {
                                    filters: filterParams,
                                    pagination: { currentPage, pageSize },
                                    search: "",
                                });
                                navigate(`/masters/${entityName}/${item.id}/edit`);
                            }}
                            title="Edit"
                            style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: 12, color: "var(--tb-brand-hover)", background: "var(--tb-brand-50)", border: "1px solid #93c5fd", borderRadius: "5px", padding: "4px 10px", cursor: "pointer" }}
                        >
                            <Pencil className="size-4" aria-hidden="true" /> Edit
                        </button>
                        <button
                            onClick={() => onDelete(item)}
                            title="Delete"
                            style={{ display: "flex", alignItems: "center", gap: "4px", fontSize: 12, color: "var(--tb-danger-text)", background: "var(--tb-danger-soft)", border: "1px solid #fca5a5", borderRadius: "5px", padding: "4px 9px", cursor: "pointer" }}
                        >
                            <Trash2 className="size-4" aria-hidden="true" />
                        </button>
                    </div>
                </div>
            ))}
        </div>
    );
}
