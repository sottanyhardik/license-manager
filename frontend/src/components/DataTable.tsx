import { useState, type ElementType } from "react";
import { toast } from "sonner";
import { formatDate } from "../utils/dateFormatter";
import { ArrowLeftRight, Check, Copy, Download, Eye, FileText, Inbox, LogIn, Pencil, Trash2, X } from "lucide-react";
import Icon from "@/components/Icon";
import { Skeleton } from "@/components/ui/skeleton";

// customActions pass `icon` as either a lucide PascalCase name or a legacy
// Bootstrap-icon kebab name. Resolve PascalCase here; fall back to <Icon> (bi map).
const ACTION_ICONS: Record<string, ElementType> = {
    FileText, ArrowLeftRight, Eye, Pencil, Copy, LogIn, Download, Trash2, Check,
};
function ActionIcon({ name }: { name: string }) {
    const L = ACTION_ICONS[name];
    return L ? <L className="size-4" aria-hidden="true" /> : <Icon name={name} className="size-4" />;
}

const NUMERIC_PATTERNS = [
    "amount", "price", "rate", "cost", "total", "subtotal",
    "quantity", "qty", "weight", "count", "number", "inr",
    "usd", "fc", "cif", "fob", "paid", "due", "balance",
    "pct", "percent", "exc_rate",
];

function isNumericColumn(col) {
    const lower = col.toLowerCase();
    return NUMERIC_PATTERNS.some(p => lower.includes(p));
}

function formatColumnName(col) {
    return col.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());
}

// Deterministic widths per column index — avoids Math.random() re-render flicker
const SKELETON_WIDTHS = ["w-4/5", "w-3/5", "w-2/3", "w-3/4", "w-1/2", "w-4/5", "w-2/5"];

function TableSkeleton({ colCount = 5, rowCount = 6 }) {
    return (
        <table className="table mb-0" aria-busy="true" aria-label="Loading…">
            <thead>
                <tr>
                    {Array.from({ length: colCount }).map((_, i) => (
                        <th scope="col" key={i}><Skeleton className={`h-2.5 ${SKELETON_WIDTHS[i % SKELETON_WIDTHS.length]}`} /></th>
                    ))}
                    <th scope="col"><Skeleton className="h-2.5 w-14" /></th>
                </tr>
            </thead>
            <tbody>
                {Array.from({ length: rowCount }).map((_, ri) => (
                    <tr key={ri}>
                        {Array.from({ length: colCount }).map((_, ci) => (
                            <td key={ci}>
                                <Skeleton className={`h-3 ${SKELETON_WIDTHS[(ri + ci) % SKELETON_WIDTHS.length]}`} />
                            </td>
                        ))}
                        <td>
                            <div className="flex gap-1">
                                <Skeleton className="size-7 rounded-md" />
                                <Skeleton className="size-7 rounded-md" />
                            </div>
                        </td>
                    </tr>
                ))}
            </tbody>
        </table>
    );
}

/**
 * DataTable — premium data table with skeleton loading, inline editing,
 * boolean toggles, and custom cell renderers.
 */
export default function DataTable({
    data = [],
    columns = [],
    onEdit,
    onDelete,
    customActions = [],
    loading = false,
    inlineEditable = [],
    onInlineUpdate,
    customCellRender = {},
    getRowStyle = null,
}) {
    const [editingCell, setEditingCell] = useState(null);
    const [editValue, setEditValue] = useState("");
    const [saving, setSaving] = useState(false);

    const formatValue = (value, columnName, isEditableField = false) => {
        if (value === null || value === undefined) {
            return <span className="text-muted-foreground">—</span>;
        }
        if (typeof value === "boolean") {
            if (isEditableField) {
                // Accessible toggle using native checkbox styled as a switch — no Bootstrap dependency
                return (
                    <label className="inline-flex cursor-pointer items-center" onClick={e => e.stopPropagation()}>
                        <input
                            type="checkbox"
                            role="switch"
                            checked={value}
                            onChange={() => {}}
                            aria-label="Toggle"
                            className="sr-only peer"
                        />
                        <span
                            aria-hidden="true"
                            className={[
                                "relative inline-block h-5 w-9 rounded-full border transition-colors duration-200",
                                value
                                    ? "border-primary/30 bg-primary"
                                    : "border-border bg-muted",
                            ].join(" ")}
                        >
                            <span
                                className={[
                                    "absolute top-0.5 size-4 rounded-full bg-white shadow-sm transition-transform duration-200",
                                    value ? "translate-x-4" : "translate-x-0.5",
                                ].join(" ")}
                            />
                        </span>
                    </label>
                );
            }
            return value ? (
                <span className="inline-flex items-center rounded-md border border-success/20 bg-success/10 px-2 py-0.5 text-xs font-medium text-success">
                    Yes
                </span>
            ) : (
                <span className="inline-flex items-center rounded-md border border-border bg-muted/60 px-2 py-0.5 text-xs font-medium text-muted-foreground">
                    No
                </span>
            );
        }
        if (columnName && (columnName.includes("date") || columnName.includes("_at") || columnName.includes("_on"))) {
            const formatted = formatDate(value);
            if (formatted) return formatted;
        }
        if (typeof value === "object") return JSON.stringify(value);
        return String(value);
    };

    const handleCellClick = (item, columnName) => {
        if (inlineEditable.includes(columnName)) {
            setEditingCell({ rowId: item.id, columnName });
            setEditValue(item[columnName] || "");
        }
    };

    const handleSave = async (item, columnName) => {
        if (!onInlineUpdate) return;
        setSaving(true);
        try {
            await onInlineUpdate(item.id, columnName, editValue);
            setEditingCell(null);
        } catch (error) {
            toast.error(error?.response?.data?.error || "Failed to save. Please try again.");
        } finally {
            setSaving(false);
        }
    };

    const handleCancel = () => { setEditingCell(null); setEditValue(""); };

    const handleKeyDown = (e, item, columnName) => {
        if (e.key === "Enter") handleSave(item, columnName);
        else if (e.key === "Escape") handleCancel();
    };

    const isEditing = (item, columnName) =>
        editingCell?.rowId === item.id && editingCell?.columnName === columnName;

    const handleBooleanToggle = async (item, columnName, currentValue) => {
        setSaving(true);
        try {
            await onInlineUpdate(item.id, columnName, !currentValue);
        } catch (error) {
            toast.error(error?.response?.data?.error || "Failed to update.");
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return (
            <div className="table-responsive-mobile">
                <TableSkeleton colCount={Math.max(columns.length, 3)} rowCount={7} />
            </div>
        );
    }

    if (data.length === 0) {
        return (
            <div className="flex flex-col items-center px-6 py-14 text-center">
                <span className="mb-3 flex size-12 items-center justify-center rounded-xl border border-border/60 bg-muted/50">
                    <Inbox className="size-5 text-muted-foreground/50" aria-hidden="true" />
                </span>
                <p className="text-sm font-semibold text-foreground">No records found</p>
                <p className="mt-1 text-xs text-muted-foreground">Try adjusting your search or filter criteria</p>
            </div>
        );
    }

    return (
        <div className="table-responsive-mobile">
            <table className="table table-hover">
                <thead>
                    <tr>
                        {columns.map(col => (
                            <th
                                scope="col"
                                key={col}
                                className={isNumericColumn(col) ? "text-right" : ""}
                            >
                                {formatColumnName(col)}
                            </th>
                        ))}
                        <th scope="col" className="w-[110px] text-center">Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {data.map((item, index) => (
                        <tr key={item.id || index} style={getRowStyle ? getRowStyle(item) : {}}>
                            {columns.map(col => {
                                const fieldKey = col.replace(/__/g, "_");
                                const value = item[fieldKey] ?? item[col];
                                const isEditableField = inlineEditable.includes(col);
                                const isCurrentlyEditing = isEditing(item, col);

                                return (
                                    <td
                                        key={col}
                                        data-label={formatColumnName(col)}
                                        onClick={() => {
                                            if (!isCurrentlyEditing && isEditableField && typeof value === "boolean") {
                                                handleBooleanToggle(item, col, value);
                                            } else if (!isCurrentlyEditing) {
                                                handleCellClick(item, col);
                                            }
                                        }}
                                        className={[
                                            isEditableField ? "cursor-pointer" : "",
                                            isNumericColumn(col) ? "text-right tabular-nums" : "",
                                        ].filter(Boolean).join(" ") || undefined}
                                        title={
                                            isEditableField && typeof value === "boolean"
                                                ? "Click to toggle"
                                                : isEditableField
                                                ? "Click to edit"
                                                : ""
                                        }
                                    >
                                        {isCurrentlyEditing ? (
                                            <div className="flex items-center gap-1">
                                                <input
                                                    type="text"
                                                    className="flex h-8 min-w-[80px] rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
                                                    value={editValue}
                                                    onChange={e => setEditValue(e.target.value)}
                                                    onKeyDown={e => handleKeyDown(e, item, col)}
                                                    onBlur={() => handleSave(item, col)}
                                                    autoFocus
                                                    disabled={saving}
                                                />
                                                <button
                                                    className="flex items-center justify-center rounded px-[7px] py-[2px] text-xs bg-success text-white cursor-pointer hover:bg-success/90"
                                                    onClick={() => handleSave(item, col)}
                                                    disabled={saving}
                                                    title="Save"
                                                >
                                                    <Check className="size-4" aria-hidden="true" />
                                                </button>
                                                <button
                                                    className="flex items-center justify-center rounded border border-border bg-card px-[7px] py-[2px] text-xs text-muted-foreground cursor-pointer hover:bg-muted"
                                                    onClick={handleCancel}
                                                    disabled={saving}
                                                    title="Cancel"
                                                >
                                                    <X className="size-4" aria-hidden="true" />
                                                </button>
                                            </div>
                                        ) : (
                                            <span className={isEditableField && typeof value !== "boolean" ? "group/cell relative inline-flex items-center gap-1.5 rounded pr-1" : ""}>
                                                {customCellRender[col]
                                                    ? customCellRender[col](item, value)
                                                    : formatValue(value, col, isEditableField)}
                                                {isEditableField && typeof value !== "boolean" && (
                                                    <Pencil
                                                        className="size-3 shrink-0 text-muted-foreground/40 opacity-0 transition-opacity duration-150 group-hover/cell:opacity-100"
                                                        aria-hidden="true"
                                                    />
                                                )}
                                            </span>
                                        )}
                                    </td>
                                );
                            })}
                            <td className="text-center" data-label="Actions">
                                <div className="inline-flex items-center gap-1">
                                    {customActions.map((action, idx) => {
                                        if (action.showIf && !action.showIf(item)) return null;
                                        return (
                                            <button
                                                key={idx}
                                                className={action.className || "inline-flex items-center gap-1 rounded border border-border px-2 py-1 text-xs text-muted-foreground hover:bg-muted"}
                                                onClick={() => action.onClick(item)}
                                                title={action.label}
                                                aria-label={action.label}
                                            >
                                                {action.icon && <ActionIcon name={action.icon} />}
                                            </button>
                                        );
                                    })}
                                    {onEdit && (
                                        <button
                                            className="inline-flex size-7 items-center justify-center rounded-md border border-primary/25 bg-primary/5 text-primary transition-colors hover:bg-primary/12 hover:border-primary/40 cursor-pointer"
                                            onClick={() => onEdit(item)}
                                            title="Edit"
                                            aria-label={`Edit ${item.id || "record"}`}
                                        >
                                            <Pencil className="size-3.5" aria-hidden="true" />
                                        </button>
                                    )}
                                    {onDelete && (
                                        <button
                                            className="inline-flex size-7 items-center justify-center rounded-md border border-destructive/25 bg-destructive/5 text-destructive transition-colors hover:bg-destructive/12 hover:border-destructive/40 cursor-pointer"
                                            onClick={() => onDelete(item)}
                                            title="Delete"
                                            aria-label={`Delete ${item.id || "record"}`}
                                        >
                                            <Trash2 className="size-3.5" aria-hidden="true" />
                                        </button>
                                    )}
                                </div>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
