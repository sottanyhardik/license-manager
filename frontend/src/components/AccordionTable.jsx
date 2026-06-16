import {useState, Fragment} from "react";
import {Link} from "react-router-dom";
import {toast} from "react-toastify";
import api from "../api/axios";
import {formatDate} from "../utils/dateFormatter";
import { Loader2, Check, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {formatIndianNumber} from "../utils/numberFormatter";

/**
 * Accordion Table Component
 *
 * Used for displaying records with nested arrays (like SION Norm Classes, Licenses)
 * that expand/collapse on click.
 */
export default function AccordionTable({data, columns, loading, onDelete, basePath, nestedFieldDefs = {}, nestedListDisplay = {}, customActions = [], lazyLoadNested = false, onToggleBoolean, inlineEditable = [], onInlineUpdate, onRowClick = null}) {
    const [expandedRows, setExpandedRows] = useState(new Set());
    const [nestedData, setNestedData] = useState({});
    const [loadingNested, setLoadingNested] = useState({});
    const [togglingFields, setTogglingFields] = useState({});
    const [editingCell, setEditingCell] = useState(null); // {rowId, columnName}
    const [editValue, setEditValue] = useState("");
    const [saving, setSaving] = useState(false);

    const toggleRow = async (id, item) => {
        // If custom onRowClick is provided, use it instead of default accordion behavior
        if (onRowClick) {
            onRowClick(item);
            return;
        }

        const isCurrentlyExpanded = expandedRows.has(id);
        const newExpanded = new Set(expandedRows);

        if (isCurrentlyExpanded) {
            newExpanded.delete(id);
        } else {
            newExpanded.add(id);

            // If lazyLoadNested is enabled and we haven't loaded data for this row yet
            if (lazyLoadNested && !nestedData[id] && !loadingNested[id]) {
                setLoadingNested({...loadingNested, [id]: true});
                try {
                    const response = await api.get(`${basePath}/${id}/nested_items/`);
                    setNestedData({...nestedData, [id]: response.data});
                } catch (err) {
                    toast.error('Failed to load details. Please try again.');
                } finally {
                    setLoadingNested({...loadingNested, [id]: false});
                }
            }
        }
        setExpandedRows(newExpanded);
    };

    const handleToggleBoolean = async (item, field, currentValue) => {
        if (!onToggleBoolean) return;

        const fieldKey = `${item.id}-${field}`;
        setTogglingFields({...togglingFields, [fieldKey]: true});

        try {
            await onToggleBoolean(item, field, !currentValue);
        } catch (err) {
            toast.error('Failed to update. Please try again.');
        } finally {
            setTogglingFields({...togglingFields, [fieldKey]: false});
        }
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

    // Check if column should be right-aligned (numeric/currency columns)
    const isNumericColumn = (columnName) => {
        const numericPatterns = [
            'amount', 'price', 'rate', 'cost', 'total', 'subtotal',
            'quantity', 'qty', 'weight', 'count', 'number', 'inr',
            'usd', 'fc', 'cif', 'fob', 'paid', 'due', 'balance',
            'pct', 'percent', 'exc_rate', 'kg'
        ];
        const lowerColumn = columnName.toLowerCase();
        return numericPatterns.some(pattern => lowerColumn.includes(pattern));
    };

    if (loading) {
        return (
            <div className="flex flex-col items-center gap-2 py-10 text-center">
                <Loader2 className="size-8 animate-spin text-primary" />
                <span className="text-sm text-muted-foreground">Loading…</span>
            </div>
        );
    }

    if (!data || data.length === 0) {
        return (
            <div className="alert alert-info">
                No records found.
            </div>
        );
    }

    const renderNestedTable = (items, fieldKey, fieldConfig) => {
        if (!items || items.length === 0) {
            return (
                <div className="alert alert-info mb-0">
                    <small>No {fieldKey.replace(/_/g, " ")} defined.</small>
                </div>
            );
        }

        // Handle both array and object with fields property
        let actualFieldConfig = fieldConfig;
        if (!Array.isArray(fieldConfig)) {
            // Check if it's an object with fields property (e.g., {label: "Trade Lines", fields: [...]})
            if (fieldConfig && typeof fieldConfig === 'object' && Array.isArray(fieldConfig.fields)) {
                actualFieldConfig = fieldConfig.fields;
            } else {
                return (
                    <div className="alert alert-warning mb-0">
                        <small>Invalid configuration for {fieldKey.replace(/_/g, " ")}.</small>
                    </div>
                );
            }
        }

        // Get fields to display - use nestedListDisplay if available, otherwise use field config
        const listDisplayFields = nestedListDisplay[fieldKey] || [];
        let visibleFields;

        if (listDisplayFields.length > 0) {
            // Use the configured list display fields
            visibleFields = listDisplayFields.map(fieldName => {
                // Try to find the field config
                const fieldDef = actualFieldConfig.find(f => f.name === fieldName);
                if (fieldDef) {
                    return fieldDef;
                }

                // If not found, try without _label suffix
                const baseFieldName = fieldName.replace('_label', '');
                const baseField = actualFieldConfig.find(f => f.name === baseFieldName);
                if (baseField) {
                    return {...baseField, name: fieldName, actualFieldName: fieldName};
                }

                // Create a basic field definition
                return {
                    name: fieldName,
                    label: fieldName.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase()),
                    type: "text"
                };
            });
        } else {
            // Fallback to showing all visible fields from config
            visibleFields = actualFieldConfig.filter(f =>
                f.name !== "id" &&
                !f.read_only &&
                f.name !== "license"
            );
        }

        // Determine icon based on field name
        const getIcon = () => {
            if (fieldKey.includes("export")) return "box-arrow-up";
            if (fieldKey.includes("import")) return "box-arrow-in-down";
            return "list-ul";
        };

        return (
            <div className="mb-3">
                <h6 className="text-primary mb-2">
                    <i className={`bi bi-${getIcon()} me-2`}></i>
                    {fieldKey.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}
                </h6>
                <div className="table-responsive">
                    <table className="table table-sm table-bordered mb-0">
                        <thead className="table-light">
                        <tr>
                            {visibleFields.map(field => {
                                // Hide headers based on billing mode for trade lines
                                if (fieldKey === 'lines' && items.length > 0 && items[0].mode) {
                                    const mode = items[0].mode; // All lines have same mode
                                    // For CIF_INR mode: hide qty_kg, fob_inr, rate_inr_per_kg headers
                                    if (mode === 'CIF_INR' && ['qty_kg', 'fob_inr', 'rate_inr_per_kg'].includes(field.name)) {
                                        return null;
                                    }
                                    // For FOB_INR mode: hide qty_kg, exc_rate, cif_inr, rate_inr_per_kg headers
                                    if (mode === 'FOB_INR' && ['qty_kg', 'exc_rate', 'cif_inr', 'rate_inr_per_kg'].includes(field.name)) {
                                        return null;
                                    }
                                    // For QTY mode: hide cif_fc, exc_rate, cif_inr, fob_inr, pct headers
                                    if (mode === 'QTY' && ['cif_fc', 'exc_rate', 'cif_inr', 'fob_inr', 'pct'].includes(field.name)) {
                                        return null;
                                    }
                                }

                                return (
                                    <th
                                        key={field.name}
                                        style={isNumericColumn(field.name) ? {textAlign: 'right'} : {}}
                                    >
                                        {field.label || field.name.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}
                                    </th>
                                );
                            })}
                        </tr>
                        </thead>
                        <tbody>
                        {items.map((item, idx) => (
                            <tr key={item.id || idx}>
                                {visibleFields.map(field => {
                                    // Skip fields based on billing mode for trade lines
                                    if (fieldKey === 'lines' && item.mode) {
                                        const mode = item.mode;
                                        // For CIF_INR mode: show only cif_fc, exc_rate, cif_inr (hide qty_kg, fob_inr)
                                        if (mode === 'CIF_INR' && ['qty_kg', 'fob_inr', 'rate_inr_per_kg'].includes(field.name)) {
                                            return null;
                                        }
                                        // For FOB_INR mode: show cif_fc and fob_inr (hide qty_kg, exc_rate, cif_inr, rate_inr_per_kg)
                                        if (mode === 'FOB_INR' && ['qty_kg', 'exc_rate', 'cif_inr', 'rate_inr_per_kg'].includes(field.name)) {
                                            return null;
                                        }
                                        // For QTY mode: show only qty_kg, rate_inr_per_kg (hide cif_fc, exc_rate, cif_inr, fob_inr)
                                        if (mode === 'QTY' && ['cif_fc', 'exc_rate', 'cif_inr', 'fob_inr', 'pct'].includes(field.name)) {
                                            return null;
                                        }
                                    }

                                    let value = item[field.name];

                                    // Determine if this is a decimal or integer field
                                    const isDecimalField = field.name.includes('quantity') ||
                                                          field.name.includes('cif') ||
                                                          field.name.includes('fob') ||
                                                          field.name.includes('value') ||
                                                          field.name.includes('balance') ||
                                                          field.name.includes('amount');

                                    const isIntegerField = field.name === 'serial_number' ||
                                                          field.type === 'integer';

                                    // Format based on field type
                                    if (value === null || value === undefined || value === "") {
                                        value = "-";
                                    } else if (typeof value === "boolean") {
                                        value = value ? "Yes" : "No";
                                    } else if (Array.isArray(value)) {
                                        value = value.length > 0 ? value.join(", ") : "-";
                                    } else if ((typeof value === "number" || !isNaN(parseFloat(value))) && (isDecimalField || isIntegerField)) {
                                        // Parse the value as a number
                                        const numValue = parseFloat(value);

                                        if (isIntegerField) {
                                            // Integer fields: no decimals, with Indian number format
                                            value = formatIndianNumber(Math.round(numValue), 0);
                                        } else if (isDecimalField) {
                                            // Decimal fields: 2 decimals, with Indian number format
                                            value = formatIndianNumber(numValue, 2);
                                        }
                                    } else if (field.name.includes("date") && value) {
                                        // Format date as dd-MM-yyyy
                                        const formattedDate = formatDate(value);
                                        if (formattedDate) {
                                            value = formattedDate;
                                        }
                                    }

                                    return (
                                        <td key={field.name} className={(isDecimalField || isIntegerField) ? "text-end" : ""}>
                                            {value}
                                        </td>
                                    );
                                })}
                            </tr>
                        ))}
                        </tbody>
                    </table>
                </div>
            </div>
        );
    };

    return (
        <div className="table-responsive">
            <table className="table table-hover">
                <thead className="table-light">
                <tr>
                    <th style={{width: "40px"}}></th>
                    {columns.map((col) => (
                        <th
                            key={col}
                            style={isNumericColumn(col) ? {textAlign: 'right'} : {}}
                        >
                            {col.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase())}
                        </th>
                    ))}
                    <th style={{width: "120px"}}>Actions</th>
                </tr>
                </thead>
                <tbody>
                {data.map((item) => {
                    const isExpanded = expandedRows.has(item.id);

                    return (
                        <Fragment key={item.id}>
                            {/* Main Row */}
                            <tr className={isExpanded ? "table-active" : ""}>
                                <td>
                                    <button
                                        className="cursor-pointer border-0 bg-transparent p-0 text-primary hover:opacity-70"
                                        onClick={() => toggleRow(item.id, item)}
                                        title={isExpanded ? "Collapse" : "Expand"}
                                    >
                                        <i className={`bi bi-chevron-${isExpanded ? "down" : "right"} fs-6`}></i>
                                    </button>
                                </td>
                                {columns.map((col) => {
                                    // Convert head__name to head_name for annotated fields
                                    const fieldKey = col.replace(/__/g, '_');
                                    let value = item[fieldKey] || item[col];

                                    // Format date fields as dd-MM-yyyy
                                    if (value && (col.includes("date") || col.includes("_at") || col.includes("_on"))) {
                                        const formattedDate = formatDate(value);
                                        if (formattedDate) {
                                            value = formattedDate;
                                        }
                                    }

                                    // Handle boolean fields with switch toggle
                                    const isBooleanField = typeof value === 'boolean' ||
                                                          col.startsWith('is_') ||
                                                          col.startsWith('has_');

                                    if (isBooleanField && onToggleBoolean) {
                                        const toggleKey = `${item.id}-${col}`;
                                        const isToggling = togglingFields[toggleKey];
                                        const boolValue = typeof value === 'boolean' ? value : false;

                                        return (
                                            <td key={col}>
                                                <div className="form-check form-switch">
                                                    <input
                                                        type="checkbox"
                                                        className="form-check-input"
                                                        role="switch"
                                                        id={`switch-${item.id}-${col}`}
                                                        checked={boolValue}
                                                        onChange={() => handleToggleBoolean(item, col, boolValue)}
                                                        disabled={isToggling}
                                                        style={{cursor: isToggling ? 'wait' : 'pointer'}}
                                                    />
                                                    {isToggling && <Loader2 className="ml-1.5 inline size-3.5 animate-spin text-primary" />}
                                                </div>
                                            </td>
                                        );
                                    }

                                    const isEditableField = inlineEditable.includes(col);
                                    const isCurrentlyEditing = isEditing(item, col);

                                    return (
                                        <td
                                            key={col}
                                            onClick={() => !isCurrentlyEditing && handleCellClick(item, col)}
                                            style={{
                                                ...(isEditableField ? {cursor: 'pointer'} : {}),
                                                ...(isNumericColumn(col) ? {textAlign: 'right'} : {})
                                            }}
                                            title={isEditableField ? 'Click to edit' : ''}
                                        >
                                            {isCurrentlyEditing ? (
                                                <div className="d-flex align-items-center gap-1">
                                                    <input
                                                        type="text"
                                                        className="flex h-8 rounded-md border border-input bg-card px-2 py-1 text-sm outline-none focus-visible:border-ring"
                                                        value={editValue}
                                                        onChange={(e) => setEditValue(e.target.value)}
                                                        onKeyDown={(e) => handleKeyDown(e, item, col)}
                                                        onBlur={() => handleSave(item, col)}
                                                        autoFocus
                                                        disabled={saving}
                                                        onClick={(e) => e.stopPropagation()}
                                                    />
                                                    <Button size="icon" className="size-7" onClick={(e) => { e.stopPropagation(); handleSave(item, col); }} disabled={saving} title="Save">
                                                        <Check className="size-3.5" />
                                                    </Button>
                                                    <Button size="icon" variant="outline" className="size-7" onClick={(e) => { e.stopPropagation(); handleCancel(); }} disabled={saving} title="Cancel">
                                                        <X className="size-3.5" />
                                                    </Button>
                                                </div>
                                            ) : col === "id" ? (
                                                <Link to={`${basePath}/${item.id}/edit`}>
                                                    {value || "-"}
                                                </Link>
                                            ) : col === "license_number" ? (
                                                // Check if license has documents
                                                item.license_documents && item.license_documents.length > 0 ? (
                                                    <a
                                                        href={`/api/licenses/${item.id}/merged-documents/`}
                                                        target="_blank"
                                                        rel="noopener noreferrer"
                                                        className="text-primary text-decoration-none"
                                                        title="View merged license documents"
                                                    >
                                                        {value || "-"}
                                                    </a>
                                                ) : (
                                                    <span className="text-muted">{value || "-"}</span>
                                                )
                                            ) : (
                                                <span>
                                                    {value || "-"}
                                                    {isEditableField && (
                                                        <i className="bi bi-pencil ms-2 text-muted" style={{fontSize: 12.5}}></i>
                                                    )}
                                                </span>
                                            )}
                                        </td>
                                    );
                                })}
                                <td>
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
                                        <Button size="sm" variant="outline" asChild title="Edit">
                                            <Link to={`${basePath}/${item.id}/edit`}>
                                                <i className="bi bi-pencil" aria-hidden="true" />
                                            </Link>
                                        </Button>
                                        <Button size="sm" variant="outline" className="text-destructive hover:bg-destructive/10" onClick={() => onDelete(item)} title="Delete">
                                            <i className="bi bi-trash" aria-hidden="true" />
                                        </Button>
                                    </div>
                                </td>
                            </tr>

                            {/* Nested Row (Expanded) */}
                            {isExpanded && (
                                <tr className="border-0">
                                    <td colSpan={columns.length + 2} className="border-0 bg-muted/30 p-4">
                                        {loadingNested[item.id] ? (
                                            <div className="flex items-center gap-2 py-3 text-sm text-muted-foreground">
                                                <Loader2 className="size-4 animate-spin text-primary" />
                                                Loading nested items…
                                            </div>
                                        ) : (
                                            Object.entries(nestedFieldDefs).map(([fieldKey, fieldConfig]) => {
                                                // Use lazy-loaded data if available, otherwise fall back to item data
                                                const nestedItems = lazyLoadNested && nestedData[item.id]
                                                    ? nestedData[item.id][fieldKey]
                                                    : item[fieldKey];
                                                return (
                                                    <div key={`${item.id}-${fieldKey}`}>
                                                        {renderNestedTable(nestedItems, fieldKey, fieldConfig)}
                                                    </div>
                                                );
                                            })
                                        )}
                                    </td>
                                </tr>
                            )}
                        </Fragment>
                    );
                })}
                </tbody>
            </table>
        </div>
    );
}
