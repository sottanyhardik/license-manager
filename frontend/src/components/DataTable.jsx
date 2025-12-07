import {useState} from "react";
import {formatDate} from "../utils/dateFormatter";

/**
 * Reusable DataTable Component
 *
 * Props:
 * - data: array of data objects
 * - columns: array of column field names to display
 * - onEdit: callback function(item)
 * - onDelete: callback function(item)
 * - customActions: array of custom action objects {label, icon, onClick, className, showIf}
 * - loading: boolean
 * - basePath: base URL path for edit links (e.g., "/masters/companies")
 * - inlineEditable: array of field names that can be edited inline
 * - onInlineUpdate: callback function(itemId, fieldName, newValue) - called when inline edit is saved
 */
export default function DataTable({
    data = [],
    columns = [],
    onEdit,
    onDelete,
    customActions = [],
    loading = false,
    basePath = "",
    inlineEditable = [],
    onInlineUpdate
}) {
    const [editingCell, setEditingCell] = useState(null); // {rowId, columnName}
    const [editValue, setEditValue] = useState("");
    const [saving, setSaving] = useState(false);
    const formatValue = (value, columnName, isEditableField = false) => {
        if (value === null || value === undefined) {
            return <span className="text-muted">-</span>;
        }
        if (typeof value === "boolean") {
            // If it's an editable boolean field, render as a toggle switch
            if (isEditableField) {
                return (
                    <div className="form-check form-switch" style={{display: 'inline-block'}}>
                        <input
                            className="form-check-input"
                            type="checkbox"
                            role="switch"
                            checked={value}
                            onChange={() => {}} // Handled by parent onClick
                            style={{cursor: 'pointer'}}
                        />
                    </div>
                );
            }
            // Otherwise render as badge
            return value ? (
                <span className="badge bg-success">Yes</span>
            ) : (
                <span className="badge bg-secondary">No</span>
            );
        }
        // Format date fields as dd-MM-yyyy
        if (columnName && (columnName.includes("date") || columnName.includes("_at") || columnName.includes("_on"))) {
            const formattedDate = formatDate(value);
            if (formattedDate) {
                return formattedDate;
            }
        }
        if (typeof value === "object") {
            return JSON.stringify(value);
        }
        return String(value);
    };

    const formatColumnName = (column) => {
        return column
            .replace(/_/g, " ")
            .replace(/\b\w/g, (char) => char.toUpperCase());
    };

    const handleCellClick = (item, columnName) => {
        if (inlineEditable.includes(columnName)) {
            setEditingCell({rowId: item.id, columnName});
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
            console.error("Failed to update:", error);
        } finally {
            setSaving(false);
        }
    };

    const handleCancel = () => {
        setEditingCell(null);
        setEditValue("");
    };

    const handleKeyDown = (e, item, columnName) => {
        if (e.key === 'Enter') {
            handleSave(item, columnName);
        } else if (e.key === 'Escape') {
            handleCancel();
        }
    };

    const isEditing = (item, columnName) => {
        return editingCell?.rowId === item.id && editingCell?.columnName === columnName;
    };

    const handleBooleanToggle = async (item, columnName, currentValue) => {
        setSaving(true);
        try {
            const newValue = !currentValue;
            await onInlineUpdate(item.id, columnName, newValue);
        } catch (error) {
            console.error('Failed to toggle:', error);
        } finally {
            setSaving(false);
        }
    };

    if (loading) {
        return (
            <div className="text-center py-5">
                <div className="spinner-border text-primary" role="status">
                    <span className="visually-hidden">Loading...</span>
                </div>
                <p className="mt-2 text-muted">Loading data...</p>
            </div>
        );
    }

    if (data.length === 0) {
        return (
            <div className="alert alert-info">
                <i className="bi bi-info-circle me-2"></i>
                No records found.
            </div>
        );
    }

    return (
        <div className="table-responsive">
            <table className="table table-hover table-bordered">
                <thead className="table-light">
                    <tr>
                        {columns.map((column) => (
                            <th key={column}>{formatColumnName(column)}</th>
                        ))}
                        <th className="text-center" style={{width: "150px"}}>
                            Actions
                        </th>
                    </tr>
                </thead>
                <tbody>
                    {data.map((item, index) => (
                        <tr key={item.id || index}>
                            {columns.map((column) => {
                                // Convert head__name to head_name for annotated fields
                                const fieldKey = column.replace(/__/g, '_');
                                const value = item[fieldKey] || item[column];
                                const isEditableField = inlineEditable.includes(column);
                                const isCurrentlyEditing = isEditing(item, column);

                                return (
                                    <td
                                        key={column}
                                        onClick={() => {
                                            if (!isCurrentlyEditing && isEditableField && typeof value === 'boolean') {
                                                // For boolean fields with inline editing, toggle immediately
                                                handleBooleanToggle(item, column, value);
                                            } else if (!isCurrentlyEditing) {
                                                handleCellClick(item, column);
                                            }
                                        }}
                                        style={isEditableField ? {cursor: 'pointer'} : {}}
                                        title={isEditableField && typeof value === 'boolean' ? 'Click to toggle' : (isEditableField ? 'Click to edit' : '')}
                                    >
                                        {isCurrentlyEditing ? (
                                            <div className="d-flex align-items-center gap-1">
                                                <input
                                                    type="text"
                                                    className="form-control form-control-sm"
                                                    value={editValue}
                                                    onChange={(e) => setEditValue(e.target.value)}
                                                    onKeyDown={(e) => handleKeyDown(e, item, column)}
                                                    onBlur={() => handleSave(item, column)}
                                                    autoFocus
                                                    disabled={saving}
                                                />
                                                <button
                                                    className="btn btn-sm btn-success"
                                                    onClick={() => handleSave(item, column)}
                                                    disabled={saving}
                                                    title="Save"
                                                >
                                                    <i className="bi bi-check"></i>
                                                </button>
                                                <button
                                                    className="btn btn-sm btn-secondary"
                                                    onClick={handleCancel}
                                                    disabled={saving}
                                                    title="Cancel"
                                                >
                                                    <i className="bi bi-x"></i>
                                                </button>
                                            </div>
                                        ) : (
                                            <span>
                                                {formatValue(value, column, isEditableField)}
                                                {isEditableField && typeof value !== 'boolean' && (
                                                    <i className="bi bi-pencil ms-2 text-muted" style={{fontSize: '0.8rem'}}></i>
                                                )}
                                            </span>
                                        )}
                                    </td>
                                );
                            })}
                            <td className="text-center">
                                <div className="btn-group btn-group-sm">
                                    {customActions.map((action, idx) => {
                                        if (action.showIf && !action.showIf(item)) {
                                            return null;
                                        }
                                        return (
                                            <button
                                                key={idx}
                                                className={action.className || "btn btn-outline-info"}
                                                onClick={() => action.onClick(item)}
                                                title={action.label}
                                            >
                                                {action.icon && <i className={action.icon}></i>}
                                            </button>
                                        );
                                    })}
                                    {onEdit && (
                                        <button
                                            onClick={() => onEdit(item)}
                                            className="btn btn-outline-primary"
                                            title="Edit"
                                        >
                                            <i className="bi bi-pencil"></i>
                                        </button>
                                    )}
                                    {onDelete && (
                                        <button
                                            className="btn btn-outline-danger"
                                            onClick={() => onDelete(item)}
                                            title="Delete"
                                        >
                                            <i className="bi bi-trash"></i>
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
