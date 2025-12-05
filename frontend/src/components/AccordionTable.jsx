import {useState, Fragment} from "react";
import {Link} from "react-router-dom";
import api from "../api/axios";
import {formatDate} from "../utils/dateFormatter";
import {formatIndianNumber} from "../utils/numberFormatter";

/**
 * Accordion Table Component
 *
 * Used for displaying records with nested arrays (like SION Norm Classes, Licenses)
 * that expand/collapse on click.
 */
export default function AccordionTable({data, columns, loading, onDelete, basePath, nestedFieldDefs = {}, nestedListDisplay = {}, customActions = [], lazyLoadNested = false, onToggleBoolean}) {
    const [expandedRows, setExpandedRows] = useState(new Set());
    const [nestedData, setNestedData] = useState({});
    const [loadingNested, setLoadingNested] = useState({});
    const [togglingFields, setTogglingFields] = useState({});

    const toggleRow = async (id) => {
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
                    // Silently handle error
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
            // Silently handle error
        } finally {
            setTogglingFields({...togglingFields, [fieldKey]: false});
        }
    };

    if (loading) {
        return (
            <div className="text-center py-5">
                <div className="spinner-border text-primary" role="status">
                    <span className="visually-hidden">Loading...</span>
                </div>
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
                                    // For FOB_INR mode: hide qty_kg, cif_fc, exc_rate, cif_inr, rate_inr_per_kg headers
                                    if (mode === 'FOB_INR' && ['qty_kg', 'cif_fc', 'exc_rate', 'cif_inr', 'rate_inr_per_kg'].includes(field.name)) {
                                        return null;
                                    }
                                    // For QTY mode: hide cif_fc, exc_rate, cif_inr, fob_inr, pct headers
                                    if (mode === 'QTY' && ['cif_fc', 'exc_rate', 'cif_inr', 'fob_inr', 'pct'].includes(field.name)) {
                                        return null;
                                    }
                                }

                                return (
                                    <th key={field.name}>
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
                                        // For FOB_INR mode: show only fob_inr (hide qty_kg, cif_fc, exc_rate, cif_inr, rate_inr_per_kg)
                                        if (mode === 'FOB_INR' && ['qty_kg', 'cif_fc', 'exc_rate', 'cif_inr', 'rate_inr_per_kg'].includes(field.name)) {
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
                        <th key={col}>
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
                                        className="btn btn-sm btn-link p-0 text-primary"
                                        onClick={() => toggleRow(item.id)}
                                        title={isExpanded ? "Collapse" : "Expand"}
                                    >
                                        <i className={`bi bi-chevron-${isExpanded ? "down" : "right"} fs-6`}></i>
                                    </button>
                                </td>
                                {columns.map((col) => {
                                    // Convert head__name to head_name for annotated fields
                                    const fieldKey = col.replace(/__/g, '_');
                                    let value = item[fieldKey] || item[col];

                                    // Format date fields as dd-mm-yyyy
                                    if (value && (col.includes("date") || col.includes("_at") || col.includes("_on"))) {
                                        try {
                                            const date = new Date(value);
                                            if (!isNaN(date.getTime())) {
                                                const day = String(date.getDate()).padStart(2, '0');
                                                const month = String(date.getMonth() + 1).padStart(2, '0');
                                                const year = date.getFullYear();
                                                value = `${day}-${month}-${year}`;
                                            }
                                        } catch (e) {
                                            // Keep original value if date parsing fails
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
                                                    {isToggling && (
                                                        <span className="spinner-border spinner-border-sm ms-2" role="status"></span>
                                                    )}
                                                </div>
                                            </td>
                                        );
                                    }

                                    return (
                                        <td key={col}>
                                            {col === "id" ? (
                                                <Link to={`${basePath}/${item.id}/edit`}>
                                                    {value || "-"}
                                                </Link>
                                            ) : col === "license_number" ? (
                                                <a
                                                    href={`http://localhost:8000/api/licenses/${item.id}/merged-documents/`}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                    className="text-primary text-decoration-none"
                                                    title="View merged license documents"
                                                >
                                                    {value || "-"}
                                                </a>
                                            ) : (
                                                value || "-"
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
                                        <Link
                                            to={`${basePath}/${item.id}/edit`}
                                            className="btn btn-outline-primary"
                                            title="Edit"
                                        >
                                            <i className="bi bi-pencil"></i>
                                        </Link>
                                        <button
                                            onClick={() => onDelete(item)}
                                            className="btn btn-outline-danger"
                                            title="Delete"
                                        >
                                            <i className="bi bi-trash"></i>
                                        </button>
                                    </div>
                                </td>
                            </tr>

                            {/* Nested Row (Expanded) */}
                            {isExpanded && (
                                <tr className="border-0">
                                    <td colSpan={columns.length + 2} className="bg-light border-0 p-4">
                                        {loadingNested[item.id] ? (
                                            <div className="text-center py-3">
                                                <div className="spinner-border spinner-border-sm text-primary" role="status">
                                                    <span className="visually-hidden">Loading...</span>
                                                </div>
                                                <span className="ms-2">Loading nested items...</span>
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
