import {useState, Fragment} from "react";
import {Link} from "react-router-dom";

/**
 * Accordion Table Component
 *
 * Used for displaying records with nested arrays (like SION Norm Classes, Licenses)
 * that expand/collapse on click.
 */
export default function AccordionTable({data, columns, loading, onDelete, basePath, nestedFieldDefs = {}}) {
    const [expandedRows, setExpandedRows] = useState(new Set());

    const toggleRow = (id) => {
        const newExpanded = new Set(expandedRows);
        if (newExpanded.has(id)) {
            newExpanded.delete(id);
        } else {
            newExpanded.add(id);
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

        // Get visible columns from field config (exclude id and read-only fields)
        const visibleFields = fieldConfig.filter(f =>
            f.name !== "id" &&
            !f.read_only &&
            f.name !== "license"
        );

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

                                    // Format based on field type
                                    if (value === null || value === undefined) {
                                        value = "-";
                                    } else if (typeof value === "boolean") {
                                        value = value ? "Yes" : "No";
                                    } else if (Array.isArray(value)) {
                                        value = value.length > 0 ? value.join(", ") : "-";
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
                                        <td key={field.name} className={field.type === "number" ? "text-end" : ""}>
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
                                        {Object.entries(nestedFieldDefs).map(([fieldKey, fieldConfig]) => {
                                            const nestedItems = item[fieldKey];
                                            return (
                                                <div key={`${item.id}-${fieldKey}`}>
                                                    {renderNestedTable(nestedItems, fieldKey, fieldConfig)}
                                                </div>
                                            );
                                        })}
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
