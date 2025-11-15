import {useEffect, useState, useCallback} from "react";
import {Link, useParams} from "react-router-dom";
import api from "../../api/axios";
import AdvancedFilter from "../../components/AdvancedFilter";
import DataPagination from "../../components/DataPagination";
import DataTable from "../../components/DataTable";
import AccordionTable from "../../components/AccordionTable";

/**
 * Generic Master List Page
 *
 * URL Pattern: /masters/:entity (e.g., /masters/companies)
 *
 * Fetches metadata from backend and displays:
 * - Filters
 * - Table with data
 * - Pagination
 */
export default function MasterList() {
    const {entity} = useParams();
    const [data, setData] = useState([]);
    const [metadata, setMetadata] = useState({});
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState("");

    // Pagination state
    const [currentPage, setCurrentPage] = useState(1);
    const [pageSize, setPageSize] = useState(25);
    const [totalPages, setTotalPages] = useState(1);
    const [hasNext, setHasNext] = useState(false);
    const [hasPrevious, setHasPrevious] = useState(false);

    // Filter state
    const [filterParams, setFilterParams] = useState({});

    const fetchData = useCallback(async (page = 1, size = 25, filters = {}) => {
        setLoading(true);
        setError("");

        try {
            const params = {
                page,
                page_size: size,
                ...filters
            };

            const {data: response} = await api.get(`/masters/${entity}/`, {params});

            setData(response.results || []);
            setMetadata({
                list_display: response.list_display || [],
                form_fields: response.form_fields || [],
                search_fields: response.search_fields || [],
                filter_fields: response.filter_fields || [],
                filter_config: response.filter_config || {},
                ordering_fields: response.ordering_fields || [],
                nested_field_defs: response.nested_field_defs || {},
                field_meta: response.field_meta || {}
            });

            // Pagination
            setCurrentPage(response.current_page || 1);
            setTotalPages(response.total_pages || 1);
            setPageSize(response.page_size || 25);
            setHasNext(response.has_next || false);
            setHasPrevious(response.has_previous || false);

        } catch (err) {
            console.error("Error fetching data:", err);
            setError(err.response?.data?.detail || "Failed to load data");
        } finally {
            setLoading(false);
        }
    }, [entity]);

    // Load data only when entity changes
    useEffect(() => {
        setCurrentPage(1);
        setFilterParams({});
        fetchData(1, 25, {});
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [entity]);

    const handleFilterChange = (filters) => {
        setFilterParams(filters);
        setCurrentPage(1);
        fetchData(1, pageSize, filters);
    };

    const handlePageChange = (page) => {
        setCurrentPage(page);
        fetchData(page, pageSize, filterParams);
    };

    const handlePageSizeChange = (size) => {
        setPageSize(size);
        setCurrentPage(1);
        fetchData(1, size, filterParams);
    };

    const handleDelete = async (item) => {
        if (!window.confirm(`Are you sure you want to delete this record?`)) {
            return;
        }

        try {
            await api.delete(`/masters/${entity}/${item.id}/`);
            fetchData(currentPage, pageSize, filterParams);
        } catch (err) {
            alert(err.response?.data?.detail || "Failed to delete record");
        }
    };

    const handleExport = async (format) => {
        try {
            const params = {
                ...filterParams,
                export: format
            };

            const response = await api.get(`/masters/${entity}/export/`, {
                params,
                responseType: 'blob'
            });

            // Create download link
            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `${entity}_${new Date().toISOString().split('T')[0]}.${format}`);
            document.body.appendChild(link);
            link.click();
            link.remove();
        } catch (err) {
            alert(err.response?.data?.detail || `Failed to export as ${format.toUpperCase()}`);
        }
    };

    const entityTitle = entity
        ?.split("-")
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");

    return (
        <div className="container-fluid mt-4">
            {/* Header */}
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h2>{entityTitle}</h2>
                <div className="btn-group">
                    <button
                        className="btn btn-outline-success"
                        onClick={() => handleExport('xlsx')}
                        title="Export to Excel"
                    >
                        <i className="bi bi-file-earmark-excel me-1"></i>
                        Excel
                    </button>
                    <button
                        className="btn btn-outline-danger"
                        onClick={() => handleExport('pdf')}
                        title="Export to PDF"
                    >
                        <i className="bi bi-file-earmark-pdf me-1"></i>
                        PDF
                    </button>
                    <Link
                        to={`/masters/${entity}/create`}
                        className="btn btn-primary"
                    >
                        <i className="bi bi-plus-circle me-2"></i>
                        Add New
                    </Link>
                </div>
            </div>

            {/* Error Display */}
            {error && (
                <div className="alert alert-danger alert-dismissible fade show">
                    {error}
                    <button
                        type="button"
                        className="btn-close"
                        onClick={() => setError("")}
                    ></button>
                </div>
            )}

            {/* Filters */}
            <AdvancedFilter
                filterConfig={metadata.filter_config || {}}
                searchFields={metadata.search_fields || []}
                onFilterChange={handleFilterChange}
            />

            {/* Table */}
            <div className="card">
                <div className="card-body">
                    {/* Use AccordionTable for SION classes, regular DataTable for others */}
                    {entity === "sion-classes" ? (
                        <AccordionTable
                            data={data}
                            columns={metadata.list_display || []}
                            loading={loading}
                            onDelete={handleDelete}
                            basePath={`/masters/${entity}`}
                        />
                    ) : (
                        <DataTable
                            data={data}
                            columns={metadata.list_display || []}
                            loading={loading}
                            onEdit={() => {}}
                            onDelete={handleDelete}
                            basePath={`/masters/${entity}`}
                        />
                    )}

                    {/* Pagination */}
                    {!loading && data.length > 0 && (
                        <DataPagination
                            currentPage={currentPage}
                            totalPages={totalPages}
                            pageSize={pageSize}
                            hasNext={hasNext}
                            hasPrevious={hasPrevious}
                            onPageChange={handlePageChange}
                            onPageSizeChange={handlePageSizeChange}
                        />
                    )}
                </div>
            </div>
        </div>
    );
}
