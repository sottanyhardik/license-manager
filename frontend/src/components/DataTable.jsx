import {Link} from "react-router-dom";

/**
 * Reusable DataTable Component
 *
 * Props:
 * - data: array of data objects
 * - columns: array of column field names to display
 * - onEdit: callback function(item)
 * - onDelete: callback function(item)
 * - loading: boolean
 * - basePath: base URL path for edit links (e.g., "/masters/companies")
 */
export default function DataTable({
    data = [],
    columns = [],
    onEdit,
    onDelete,
    loading = false,
    basePath = ""
}) {
    const formatValue = (value, columnName) => {
        if (value === null || value === undefined) {
            return <span className="text-muted">-</span>;
        }
        if (typeof value === "boolean") {
            return value ? (
                <span className="badge bg-success">Yes</span>
            ) : (
                <span className="badge bg-secondary">No</span>
            );
        }
        // Format date fields as dd-mm-yyyy
        if (columnName && (columnName.includes("date") || columnName.includes("_at") || columnName.includes("_on"))) {
            try {
                const date = new Date(value);
                if (!isNaN(date.getTime())) {
                    const day = String(date.getDate()).padStart(2, '0');
                    const month = String(date.getMonth() + 1).padStart(2, '0');
                    const year = date.getFullYear();
                    return `${day}-${month}-${year}`;
                }
            } catch (e) {
                // If date parsing fails, fall through to default string conversion
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
                                return (
                                    <td key={column}>
                                        {formatValue(item[fieldKey] || item[column], column)}
                                    </td>
                                );
                            })}
                            <td className="text-center">
                                <div className="btn-group btn-group-sm">
                                    {onEdit && (
                                        <Link
                                            to={`${basePath}/${item.id}/edit`}
                                            className="btn btn-outline-primary"
                                            title="Edit"
                                        >
                                            <i className="bi bi-pencil"></i>
                                        </Link>
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
