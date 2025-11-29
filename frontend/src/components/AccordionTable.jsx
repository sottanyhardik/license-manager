import {useState, Fragment} from "react";
import {Link} from "react-router-dom";
import api from "../api/axios";

/**
 * Accordion Table Component
 *
 * Used for displaying records with nested arrays (like SION Norm Classes, Licenses)
 * that expand/collapse on click.
 */
export default function AccordionTable({data, columns, loading, onDelete, basePath, nestedFieldDefs = {}, nestedListDisplay = {}, customActions = [], lazyLoadNested = false}) {
    const [expandedRows, setExpandedRows] = useState(new Set());
    const [nestedData, setNestedData] = useState({});
    const [loadingNested, setLoadingNested] = useState({});

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
                    console.error('Failed to load nested items:', err);
                } finally {
                    setLoadingNested({...loadingNested, [id]: false});
                }
            }
        }
        setExpandedRows(newExpanded);
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

        // Get fields to display - use nestedListDisplay if available, otherwise use field config
        const listDisplayFields = nestedListDisplay[fieldKey] || [];
        let visibleFields;

        console.log(`Rendering nested table for ${fieldKey}:`, {
            listDisplayFields,
            nestedListDisplay,
            fieldKey,
            hasConfig: listDisplayFields.length > 0
        });

        if (listDisplayFields.length > 0) {
            // Use the configured list display fields
            visibleFields = listDisplayFields.map(fieldName => {
                // Try to find the field config
                const fieldDef = fieldConfig.find(f => f.name === fieldName);
                if (fieldDef) {
                    return fieldDef;
                }

                // If not found, try without _label suffix
                const baseFieldName = fieldName.replace('_label', '');
                const baseField = fieldConfig.find(f => f.name === baseFieldName);
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
            visibleFields = fieldConfig.filter(f =>
                f.name !== "id" &&
                !f.read_only &&
                f.name !== "license"
            );
        }

        console.log(`Visible fields for ${fieldKey}:`, visibleFields.map(f => f.name));

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
                            {visibleFields.map(field => (
                                <th key={field.name}>
                                    {field.label || field.name.replace(/_/g, " ").replace(/\b\w/g, l => l.toUpperCase())}
                                </th>
                            ))}
                        </tr>
                        </thead>
                        <tbody>
                        {items.map((item, idx) => (
                            <tr key={item.id || idx}>
                                {visibleFields.map(field => {
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
                                            // Integer fields: no decimals, with comma separator
                                            value = Math.round(numValue).toLocaleString('en-US');
                                        } else if (isDecimalField) {
                                            // Decimal fields: 2 decimals, with comma separator
                                            value = numValue.toLocaleString('en-US', {
                                                minimumFractionDigits: 2,
                                                maximumFractionDigits: 2
                                            });
                                        }
                                    } else if (field.name.includes("date") && value) {
                                        // Format date as dd-mm-yyyy
                                        try {
                                            const date = new Date(value);
                                            if (!isNaN(date.getTime())) {
                                                const day = String(date.getDate()).padStart(2, '0');
                                                const month = String(date.getMonth() + 1).padStart(2, '0');
                                                const year = date.getFullYear();
                                                value = `${day}-${month}-${year}`;
                                            }
                                        } catch (e) {
                                            // Keep original value
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

                                    return (
                                        <td key={col}>
                                            {col === "id" ? (
                                                <Link to={`${basePath}/${item.id}/edit`}>
                                                    {value || "-"}
                                                </Link>
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
