import {useState} from "react";
import {Link} from "react-router-dom";

/**
 * Accordion Table Component
 *
 * Used for displaying SION Norm Classes with nested export/import norms
 * that expand/collapse on click.
 */
export default function AccordionTable({data, columns, loading, onDelete, basePath}) {
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

    const renderNestedTable = (items, title, type) => {
        if (!items || items.length === 0) {
            return (
                <div className="alert alert-info mb-0">
                    <small>No {title} defined.</small>
                </div>
            );
        }

        return (
            <div className="mb-3">
                <h6 className="text-primary mb-2">
                    <i className={`bi bi-${type === "export" ? "box-arrow-up" : "box-arrow-down"} me-2`}></i>
                    {title}
                </h6>
                <table className="table table-sm table-bordered mb-0">
                    <thead className="table-light">
                    <tr>
                        <th>Description</th>
                        <th>Quantity</th>
                        <th>Unit</th>
                        {type === "import" && <th>HSN Code</th>}
                    </tr>
                    </thead>
                    <tbody>
                    {items.map((item, idx) => (
                        <tr key={item.id || idx}>
                            <td>{item.description || "-"}</td>
                            <td className="text-end">{item.quantity || "-"}</td>
                            <td>{item.unit || "-"}</td>
                            {type === "import" && (
                                <td>{item.hsn_code_label || item.hsn_code || "-"}</td>
                            )}
                        </tr>
                    ))}
                    </tbody>
                </table>
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
                        <>
                            {/* Main Row */}
                            <tr key={item.id} className={isExpanded ? "table-active" : ""}>
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
                                    const value = item[fieldKey] || item[col];

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
                                        {renderNestedTable(item.export_norm, "Export Norms", "export")}
                                        {renderNestedTable(item.import_norm, "Import Norms", "import")}
                                    </td>
                                </tr>
                            )}
                        </>
                    );
                })}
                </tbody>
            </table>
        </div>
    );
}
