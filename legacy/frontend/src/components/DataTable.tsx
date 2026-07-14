import { useState, type ElementType } from "react";
import { toast } from "sonner";
import { formatDate } from "../utils/dateFormatter";
import { ArrowLeftRight, Check, Copy, Download, Eye, FileText, Inbox, LogIn, Pencil, Trash2, X } from "lucide-react";
import Icon from "@/components/Icon";

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

function TableSkeleton({ colCount = 5, rowCount = 6 }) {
    return (
        <table className="table mb-0" aria-busy="true" aria-label="Loading…">
            <thead>
                <tr>
                    {Array.from({ length: colCount }).map((_, i) => (
                        <th key={i}>
                            <div className="skeleton" style={{ height: 11, width: `${50 + Math.random() * 40}%`, borderRadius: 4 }} />
                        </th>
                    ))}
                    <th><div className="skeleton" style={{ height: 11, width: 60, borderRadius: 4 }} /></th>
                </tr>
            </thead>
            <tbody>
                {Array.from({ length: rowCount }).map((_, ri) => (
                    <tr key={ri}>
                        {Array.from({ length: colCount }).map((_, ci) => (
                            <td key={ci}>
                                <div className="skeleton" style={{ height: 13, width: `${40 + Math.random() * 50}%`, borderRadius: 4 }} />
                            </td>
                        ))}
                        <td>
                            <div style={{ display: "flex", gap: 4 }}>
                                <div className="skeleton" style={{ height: 28, width: 28, borderRadius: 6 }} />
                                <div className="skeleton" style={{ height: 28, width: 28, borderRadius: 6 }} />
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
            return <span style={{ color: "var(--tb-text-muted)" }}>—</span>;
        }
        if (typeof value === "boolean") {
            if (isEditableField) {
                return (
                    <div className="form-check form-switch" style={{ display: "inline-block", margin: 0 }}>
                        <input
                            className="form-check-input"
                            type="checkbox"
                            role="switch"
                            checked={value}
                            onChange={() => {}}
                            style={{ cursor: "pointer" }}
                        />
                    </div>
                );
            }
            return value ? (
                <span className="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium" style={{ background: "var(--tb-success-soft)", color: "var(--tb-success-text)" }}>Yes</span>
            ) : (
                <span className="inline-flex items-center rounded px-2 py-0.5 text-xs font-medium" style={{ background: "var(--tb-sunken)", color: "var(--tb-text-secondary)" }}>No</span>
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
            <div
                style={{
                    textAlign: "center",
                    padding: "52px 24px",
                    color: "var(--tb-text-tertiary)",
                }}
            >
                <Inbox className="size-4" aria-hidden="true" />
                <div style={{ fontSize: 14, fontWeight: 500, color: "var(--tb-text-secondary)", marginBottom: 4 }}>
                    No records found
                </div>
                <div style={{ fontSize: 12.5, color: "var(--tb-text-tertiary)" }}>
                    Try adjusting your search or filters
                </div>
            </div>
        );
    }

    return (
        <div className="table-responsive-mobile">
            <table className="table">
                <thead>
                    <tr>
                        {columns.map(col => (
                            <th
                                key={col}
                                style={isNumericColumn(col) ? { textAlign: "right" } : {}}
                            >
                                {formatColumnName(col)}
                            </th>
                        ))}
                        <th className="text-center" style={{ width: 110 }}>Actions</th>
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
                                        style={{
                                            ...(isEditableField ? { cursor: "pointer" } : {}),
                                            ...(isNumericColumn(col) ? { textAlign: "right", fontVariantNumeric: "tabular-nums" } : {}),
                                        }}
                                        title={
                                            isEditableField && typeof value === "boolean"
                                                ? "Click to toggle"
                                                : isEditableField
                                                ? "Click to edit"
                                                : ""
                                        }
                                    >
                                        {isCurrentlyEditing ? (
                                            <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                                                <input
                                                    type="text"
                                                    className="flex h-8 rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
                                                    value={editValue}
                                                    onChange={e => setEditValue(e.target.value)}
                                                    onKeyDown={e => handleKeyDown(e, item, col)}
                                                    onBlur={() => handleSave(item, col)}
                                                    autoFocus
                                                    disabled={saving}
                                                    style={{ minWidth: 80 }}
                                                />
                                                <button
                                                    className="flex items-center justify-center rounded px-2 py-1 text-xs bg-success text-white cursor-pointer hover:bg-success/90"
                                                    onClick={() => handleSave(item, col)}
                                                    disabled={saving}
                                                    title="Save"
                                                    style={{ padding: "2px 7px" }}
                                                >
                                                    <Check className="size-4" aria-hidden="true" />
                                                </button>
                                                <button
                                                    className="flex items-center justify-center rounded border border-border bg-card px-2 py-1 text-xs text-muted-foreground cursor-pointer hover:bg-muted"
                                                    onClick={handleCancel}
                                                    disabled={saving}
                                                    title="Cancel"
                                                    style={{ padding: "2px 7px" }}
                                                >
                                                    <X className="size-4" aria-hidden="true" />
                                                </button>
                                            </div>
                                        ) : (
                                            <span>
                                                {customCellRender[col]
                                                    ? customCellRender[col](item, value)
                                                    : formatValue(value, col, isEditableField)}
                                                {isEditableField && typeof value !== "boolean" && (
                                                    <Pencil className="size-4" aria-hidden="true" />
                                                )}
                                            </span>
                                        )}
                                    </td>
                                );
                            })}
                            <td className="text-center" data-label="Actions">
                                <div style={{ display: "inline-flex", gap: 4 }}>
                                    {customActions.map((action, idx) => {
                                        if (action.showIf && !action.showIf(item)) return null;
                                        return (
                                            <button
                                                key={idx}
                                                className={action.className || "btn btn-sm btn-outline-secondary"}
                                                onClick={() => action.onClick(item)}
                                                title={action.label}
                                                aria-label={action.label}
                                                style={{ padding: "3px 8px" }}
                                            >
                                                {action.icon && <ActionIcon name={action.icon} />}
                                            </button>
                                        );
                                    })}
                                    {onEdit && (
                                        <button
                                            className="flex items-center justify-center rounded border border-primary/30 bg-primary/5 px-2 py-1 text-xs text-primary cursor-pointer hover:bg-primary/10"
                                            onClick={() => onEdit(item)}
                                            title="Edit"
                                            aria-label={`Edit ${item.id || "record"}`}
                                            style={{ padding: "3px 8px" }}
                                        >
                                            <Pencil className="size-4" aria-hidden="true" />
                                        </button>
                                    )}
                                    {onDelete && (
                                        <button
                                            className="flex items-center justify-center rounded border border-destructive/30 bg-destructive/5 px-2 py-1 text-xs text-destructive cursor-pointer hover:bg-destructive/10"
                                            onClick={() => onDelete(item)}
                                            title="Delete"
                                            aria-label={`Delete ${item.id || "record"}`}
                                            style={{ padding: "3px 8px" }}
                                        >
                                            <Trash2 className="size-4" aria-hidden="true" />
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
