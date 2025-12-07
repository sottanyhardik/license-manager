import {useEffect, useState, useCallback, useRef} from "react";
import {Link, useParams, useLocation, useNavigate} from "react-router-dom";
import { toast } from 'react-toastify';
import api from "../../api/axios";
import {boeApi} from "../../services/api";
import AdvancedFilter from "../../components/AdvancedFilter";
import DataPagination from "../../components/DataPagination";
import DataTable from "../../components/DataTable";
import AccordionTable from "../../components/AccordionTable";
import {saveFilterState, restoreFilterState, shouldRestoreFilters, getNewlyCreatedItem} from "../../utils/filterPersistence";

/**
 * Generic Master List Page
 *
 * URL Pattern: /masters/:entity (e.g., /masters/companies) OR /licenses
 *
 * Fetches metadata from backend and displays:
 * - Filters
 * - Table with data
 * - Pagination
 */
export default function MasterList() {
    const {entity} = useParams();
    const location = useLocation();
    const navigate = useNavigate();

    // Determine the actual entity name - either from params or from path
    const entityName = entity ||
        (location.pathname.startsWith('/licenses') ? 'licenses' : null) ||
        (location.pathname.startsWith('/allotments') ? 'allotments' : null) ||
        (location.pathname.startsWith('/bill-of-entries') ? 'bill-of-entries' : null) ||
        (location.pathname.startsWith('/trades') ? 'trades' : null);
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

    // Filter state with default filters for allotments and bill-of-entries
    const getDefaultFilters = () => {
        if (entityName === 'allotments') {
            return {
                type: 'AT',
                is_boe: 'False',
                is_allotted: 'True'
            };
        }
        if (entityName === 'bill-of-entries') {
            return {
                is_invoice: 'False'
            };
        }
        return {};
    };

    const [filterParams, setFilterParams] = useState(getDefaultFilters());
    const backendDefaultsApplied = useRef(false);
    const pendingRequestRef = useRef(null);

    const fetchData = useCallback(async (page = 1, size = 25, filters = {}) => {
        // If there's already a pending request with same params, skip this one
        const requestKey = JSON.stringify({page, size, filters, entity: entityName});

        if (pendingRequestRef.current === requestKey) {
            return;
        }

        // Mark this request as pending
        pendingRequestRef.current = requestKey;

        setLoading(true);
        setError("");

        try {
            const params = {
                page,
                page_size: size,
                ...filters
            };

            let response;

            // Use dedicated API service for bill-of-entries
            if (entityName === 'bill-of-entries') {
                response = await boeApi.fetchBOEList(params);
            } else {
                // Determine API endpoint
                let apiPath;
                if (entityName === 'licenses' || entityName === 'allotments' || entityName === 'trades') {
                    apiPath = `/${entityName}/`;
                } else {
                    apiPath = `/masters/${entityName}/`;
                }

                const {data: apiResponse} = await api.get(apiPath, {params});
                response = apiResponse;
            }

            setData(response.results || []);
            setMetadata({
                list_display: response.list_display || [],
                form_fields: response.form_fields || [],
                search_fields: response.search_fields || [],
                filter_fields: response.filter_fields || [],
                filter_config: response.filter_config || {},
                ordering_fields: response.ordering_fields || [],
                nested_field_defs: response.nested_field_defs || {},
                nested_list_display: response.nested_list_display || {},
                field_meta: response.field_meta || {},
                default_filters: response.default_filters || {},
                inline_editable: response.inline_editable || []
            });

            // Pagination
            setCurrentPage(response.current_page || 1);
            setTotalPages(response.total_pages || 1);
            setPageSize(response.page_size || 25);
            setHasNext(response.has_next || false);
            setHasPrevious(response.has_previous || false);

        } catch (err) {
            const errorMsg = err.response?.data?.detail || "Failed to load data";
            setError(errorMsg);
            toast.error(errorMsg);
        } finally{
            setLoading(false);
            // Clear the pending request marker
            pendingRequestRef.current = null;
        }
    }, [entityName]);

    // Load data only when entityName changes
    useEffect(() => {
        if (!entityName) return;

        // Reset flags when entity changes
        backendDefaultsApplied.current = false;
        pendingRequestRef.current = null;

        // Parse URL query parameters
        const urlParams = new URLSearchParams(location.search);
        const urlFilters = {};
        for (const [key, value] of urlParams.entries()) {
            // Convert Django-style date filters to UI format
            // __gte (greater than or equal) -> _from
            // __lte (less than or equal) -> _to
            if (key.endsWith('__gte')) {
                const baseField = key.replace('__gte', '');
                urlFilters[`${baseField}_from`] = value;
            } else if (key.endsWith('__lte')) {
                const baseField = key.replace('__lte', '');
                urlFilters[`${baseField}_to`] = value;
            } else {
                urlFilters[key] = value;
            }
        }

        // Check if URL has filter parameters
        const hasUrlFilters = Object.keys(urlFilters).length > 0;

        if (hasUrlFilters) {
            // Use URL filters (highest priority - from dashboard cards)
            setFilterParams(urlFilters);
            setCurrentPage(1);
            backendDefaultsApplied.current = true;
            fetchData(1, 25, urlFilters);
        } else {
            // Check if we should restore filters from previous session
            const shouldRestore = shouldRestoreFilters();
            const restored = shouldRestore ? restoreFilterState(entityName) : null;

            if (restored) {
                // Restore previous filter state
                setFilterParams(restored.filters);
                setCurrentPage(restored.pagination?.currentPage || 1);
                setPageSize(restored.pagination?.pageSize || 25);
                backendDefaultsApplied.current = true;
                fetchData(restored.pagination?.currentPage || 1, restored.pagination?.pageSize || 25, restored.filters);
            } else {
                // Use default filters
                setCurrentPage(1);
                const defaultFilters = getDefaultFilters();
                setFilterParams(defaultFilters);
                backendDefaultsApplied.current = true;
                fetchData(1, 25, defaultFilters);
            }
        }

        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [entityName, location.search]);

    // Update filterParams when backend default filters are received (for UI display only)
    useEffect(() => {
        // Skip if we've already applied backend defaults for this entity
        if (backendDefaultsApplied.current && Object.keys(filterParams).length > 0) return;

        const backendDefaults = metadata.default_filters || {};
        const hardcodedDefaults = getDefaultFilters();

        // Only update UI state if we have backend defaults and no hardcoded defaults
        // Don't refetch - backend already applied them
        if (Object.keys(backendDefaults).length > 0 && Object.keys(hardcodedDefaults).length === 0) {
            setFilterParams(backendDefaults);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [metadata.default_filters]);

    const handleFilterChange = useCallback((filters) => {
        // Convert Django-style date filters back to UI format for state persistence
        // This ensures date values are preserved when passed back as initialFilters
        const convertedFilters = {};
        Object.entries(filters).forEach(([key, value]) => {
            if (key.endsWith('__gte')) {
                const baseField = key.replace('__gte', '');
                convertedFilters[`${baseField}_from`] = value;
            } else if (key.endsWith('__lte')) {
                const baseField = key.replace('__lte', '');
                convertedFilters[`${baseField}_to`] = value;
            } else {
                convertedFilters[key] = value;
            }
        });

        setFilterParams(convertedFilters);
        setCurrentPage(1);
        fetchData(1, pageSize, filters); // Send original format to API
    }, [fetchData, pageSize]);

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
            if (entityName === 'bill-of-entries') {
                await boeApi.deleteBOE(item.id);
            } else {
                let apiPath;
                if (entityName === 'licenses' || entityName === 'trades') {
                    apiPath = `/${entityName}/${item.id}/`;
                } else {
                    apiPath = `/masters/${entityName}/${item.id}/`;
                }
                await api.delete(apiPath);
            }
            toast.success("Record deleted successfully");
            fetchData(currentPage, pageSize, filterParams);
        } catch (err) {
            toast.error(err.response?.data?.detail || "Failed to delete record");
        }
    };

    const handleToggleBoolean = async (item, field, newValue) => {
        try {
            let apiPath;
            if (entityName === 'licenses' || entityName === 'allotments' || entityName === 'trades') {
                apiPath = `/${entityName}/${item.id}/`;
            } else if (entityName === 'bill-of-entries') {
                apiPath = `/bill-of-entries/${item.id}/`;
            } else {
                apiPath = `/masters/${entityName}/${item.id}/`;
            }

            await api.patch(apiPath, { [field]: newValue });
            toast.success("Field updated successfully");
            // Refresh data to show updated value
            fetchData(currentPage, pageSize, filterParams);
        } catch (err) {
            toast.error(err.response?.data?.detail || `Failed to update ${field}`);
            throw err; // Re-throw to let component know it failed
        }
    };

    const handleInlineUpdate = async (itemId, fieldName, newValue) => {
        try {
            let apiPath;
            if (entityName === 'licenses' || entityName === 'allotments' || entityName === 'trades') {
                apiPath = `/${entityName}/${itemId}/`;
            } else if (entityName === 'bill-of-entries') {
                apiPath = `/bill-of-entries/${itemId}/`;
            } else {
                apiPath = `/masters/${entityName}/${itemId}/`;
            }

            await api.patch(apiPath, { [fieldName]: newValue });
            toast.success(`${fieldName} updated successfully`);
            // Refresh data to show updated value
            fetchData(currentPage, pageSize, filterParams);
        } catch (err) {
            toast.error(err.response?.data?.detail || `Failed to update ${fieldName}`);
            throw err;
        }
    };

    const handleExport = async (format) => {
        try {
            if (entityName === 'bill-of-entries' && format === 'xlsx') {
                // Use boeApi for Excel export only
                const blob = await boeApi.exportBOEListExcel(filterParams);

                // Download blob
                const blobObj = new Blob([blob], {
                    type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                });
                const url = window.URL.createObjectURL(blobObj);
                const link = document.createElement('a');
                link.href = url;
                link.setAttribute('download', `${entityName}_${new Date().toISOString().split('T')[0]}.${format}`);
                document.body.appendChild(link);
                link.click();
                link.remove();
                window.URL.revokeObjectURL(url);
            } else {
                const params = {
                    ...filterParams,
                    _export: format
                };

                let apiPath;
                if (entityName === 'licenses') {
                    apiPath = `/licenses/export/`;
                } else if (entityName === 'allotments') {
                    apiPath = `/allotments/download/`;
                } else if (entityName === 'bill-of-entries') {
                    apiPath = `/bill-of-entries/export/`;
                } else if (entityName === 'trades') {
                    apiPath = `/trades/export/`;
                } else {
                    apiPath = `/masters/${entityName}/export/`;
                }

                if (format === 'pdf') {
                    // For PDF, open the URL directly with access token
                    const token = localStorage.getItem('access');
                    const queryParams = new URLSearchParams({...params, access_token: token}).toString();
                    const pdfUrl = `/api${apiPath}?${queryParams}`;
                    window.open(pdfUrl, '_blank');
                } else {
                    // For Excel, download as before
                    const response = await api.get(apiPath, {
                        params,
                        responseType: 'blob'
                    });

                    const blob = new Blob([response.data], {
                        type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                    });
                    const url = window.URL.createObjectURL(blob);
                    const link = document.createElement('a');
                    link.href = url;
                    link.setAttribute('download', `${entityName}_${new Date().toISOString().split('T')[0]}.${format}`);
                    document.body.appendChild(link);
                    link.click();
                    link.remove();
                    window.URL.revokeObjectURL(url);
                }
            }
        } catch (err) {
            toast.error(err.response?.data?.detail || `Failed to export as ${format.toUpperCase()}`);
        }
    };

    const entityTitle = entityName
        ?.split("-")
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");

    return (
        <div className="container-fluid mt-4">
            {/* Breadcrumb */}
            <nav aria-label="breadcrumb" className="mb-3">
                <ol className="breadcrumb">
                    <li className="breadcrumb-item">
                        <a href="/" onClick={(e) => { e.preventDefault(); navigate('/'); }}>Home</a>
                    </li>
                    <li className="breadcrumb-item active" aria-current="page">
                        {entityTitle}
                    </li>
                </ol>
            </nav>

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
                    {entityName === 'bill-of-entries' && (
                        <button
                            className="btn btn-outline-info"
                            onClick={async () => {
                                if (!window.confirm('This will update product names for ALL BOEs with empty product_name in the entire database. This may take some time. Continue?')) {
                                    return;
                                }

                                setLoading(true);
                                setError("");

                                try {
                                    const response = await api.post(`/bill-of-entries/bulk-update-product-names/`);

                                    setLoading(false);

                                    if (response.data.success) {
                                        alert(response.data.message || `Processed ${response.data.total} BOEs: ${response.data.updated} updated, ${response.data.skipped} skipped`);

                                        // Refresh the list to show updated product names
                                        fetchData(currentPage, pageSize, filterParams);
                                    } else {
                                        setError('Failed to update product names');
                                    }
                                } catch (err) {
                                    setLoading(false);
                                    setError(err.response?.data?.error || err.response?.data?.message || 'Failed to update product names');
                                    alert(err.response?.data?.error || err.response?.data?.message || 'Failed to update product names');
                                }
                            }}
                            title="Update all empty product names in entire database"
                        >
                            <i className="bi bi-arrow-repeat me-1"></i>
                            Fetch All Products
                        </button>
                    )}
                    <Link
                        to={entityName === 'licenses' ? '/licenses/create' :
                            entityName === 'trades' ? '/trades/create' :
                            `/masters/${entityName}/create`}
                        className="btn btn-primary"
                        onClick={() => {
                            // Save current filter state before navigating to create
                            saveFilterState(entityName, {
                                filters: filterParams,
                                pagination: { currentPage, pageSize },
                                search: ''
                            });
                        }}
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
                initialFilters={filterParams}
                defaultFilters={metadata.default_filters || {}}
            />

            {/* Table */}
            <div className="card">
                <div className="card-body">
                    {/* Use AccordionTable for entities with nested fields, regular DataTable for others */}
                    {metadata.nested_field_defs && Object.keys(metadata.nested_field_defs).length > 0 ? (
                        <AccordionTable
                            data={data}
                            columns={metadata.list_display || []}
                            loading={loading}
                            onDelete={handleDelete}
                            onToggleBoolean={handleToggleBoolean}
                            basePath={entityName === 'licenses' ? '/licenses' :
                                     (entityName === 'allotments' ? '/allotments' :
                                     (entityName === 'trades' ? '/trades' :
                                     `/masters/${entityName}`))}
                            nestedFieldDefs={metadata.nested_field_defs}
                            nestedListDisplay={metadata.nested_list_display || {}}
                            lazyLoadNested={entityName === 'licenses'}
                            customActions={entityName === 'trades' ? [
                                {
                                    label: 'Invoice PDF',
                                    icon: 'bi bi-file-pdf',
                                    className: 'btn btn-outline-danger',
                                    onClick: async (item) => {
                                        // Only allow for SALE transactions
                                        if (item.direction !== 'SALE') {
                                            alert('Bill of Supply can only be generated for SALE transactions');
                                            return;
                                        }
                                        try {
                                            const response = await api.get(`/trades/${item.id}/generate-bill-of-supply/`, {
                                                responseType: 'blob'
                                            });
                                            const blob = new Blob([response.data], { type: 'application/pdf' });
                                            const url = window.URL.createObjectURL(blob);
                                            const link = document.createElement('a');
                                            link.href = url;
                                            link.download = `Bill_of_Supply_${item.invoice_number}_${new Date().toISOString().split('T')[0]}.pdf`;
                                            document.body.appendChild(link);
                                            link.click();
                                            link.remove();
                                            window.URL.revokeObjectURL(url);
                                        } catch (err) {
                                            alert(err.response?.data?.error || 'Failed to generate Bill of Supply PDF');
                                        }
                                    },
                                    // Only show for SALE transactions
                                    showIf: (item) => item.direction === 'SALE'
                                }
                            ] : entityName === 'licenses' ? [
                                {
                                    label: 'Ledger',
                                    icon: 'bi bi-file-pdf',
                                    className: 'btn btn-outline-primary',
                                    onClick: async (item) => {
                                        try {
                                            const token = localStorage.getItem('access');
                                            const pdfUrl = `/api/license-actions/${item.id}/download-ledger/?access_token=${token}`;
                                            window.open(pdfUrl, '_blank');
                                        } catch (err) {
                                            alert(err || 'Failed to generate ledger PDF');
                                        }
                                    }
                                }
                            ] : entityName === 'allotments' ? [
                                {
                                    label: 'Allocate',
                                    icon: 'bi bi-box-arrow-in-down',
                                    className: 'btn btn-outline-success',
                                    onClick: (item) => {
                                        saveFilterState(entityName, {
                                            filters: filterParams,
                                            pagination: { currentPage, pageSize },
                                            search: ''
                                        });
                                        navigate(`/allotments/${item.id}/allocate`);
                                    }
                                },
                                {
                                    label: 'PDF',
                                    icon: 'bi bi-file-pdf',
                                    className: 'btn btn-outline-danger',
                                    onClick: async (item) => {
                                        try {
                                            const token = localStorage.getItem('access');
                                            const pdfUrl = `/api/allotment-actions/${item.id}/generate-pdf/?access_token=${token}`;
                                            window.open(pdfUrl, '_blank');
                                        } catch (err) {
                                            alert(err.response?.data?.error || 'Failed to generate PDF');
                                        }
                                    }
                                },
                                {
                                    label: 'Transfer Letter',
                                    icon: 'bi bi-file-earmark-text',
                                    className: 'btn btn-outline-warning',
                                    onClick: (item) => {
                                        saveFilterState(entityName, {
                                            filters: filterParams,
                                            pagination: { currentPage, pageSize },
                                            search: ''
                                        });
                                        navigate(`/allotments/${item.id}/allocate`, { state: { scrollToTransferLetter: true } });
                                    }
                                },
                                {
                                    label: 'Copy',
                                    icon: 'bi bi-files',
                                    className: 'btn btn-outline-primary',
                                    onClick: async (item) => {
                                        if (!window.confirm('Create a copy of this allotment without invoice and items?')) {
                                            return;
                                        }
                                        try {
                                            await api.post(`/allotments/${item.id}/copy/`);
                                            alert('Allotment copied successfully');
                                            fetchData(currentPage, pageSize, filterParams);
                                        } catch (err) {
                                            alert(err.response?.data?.error || 'Failed to copy allotment');
                                        }
                                    }
                                }
                            ] : entityName === 'bill-of-entries' ? [
                                {
                                    label: 'Transfer Letter',
                                    icon: 'bi bi-file-earmark-text',
                                    className: 'btn btn-outline-warning',
                                    onClick: (item) => {
                                        saveFilterState(entityName, {
                                            filters: filterParams,
                                            pagination: { currentPage, pageSize },
                                            search: ''
                                        });
                                        navigate(`/bill-of-entries/${item.id}/generate-transfer-letter`);
                                    }
                                },
                                {
                                    label: 'Update Product Name',
                                    icon: 'bi bi-arrow-repeat',
                                    className: 'btn btn-outline-info',
                                    onClick: async (item) => {
                                        if (!window.confirm(`Update product name for BOE ${item.bill_of_entry_number}?`)) {
                                            return;
                                        }
                                        try {
                                            const response = await api.post(`/bill-of-entries/${item.id}/update-product-name/`);
                                            alert(response.data.message || 'Product name updated successfully');
                                            // Refresh the list to show updated product name
                                            fetchData(currentPage, pageSize, filterParams);
                                        } catch (err) {
                                            alert(err.response?.data?.message || err.response?.data?.error || 'Failed to update product name');
                                        }
                                    },
                                    showIf: (item) => !item.product_name || item.product_name.trim() === ''
                                }
                            ] : []}
                            inlineEditable={metadata.inline_editable || []}
                            onInlineUpdate={handleInlineUpdate}
                        />
                    ) : (
                        <DataTable
                            data={data}
                            columns={metadata.list_display || []}
                            customActions={entityName === 'allotments' ? [
                                {
                                    label: 'Allocate',
                                    icon: 'bi bi-box-arrow-in-down',
                                    className: 'btn btn-outline-success',
                                    onClick: (item) => navigate(`/allotments/${item.id}/allocate`)
                                },
                                {
                                    label: 'PDF',
                                    icon: 'bi bi-file-pdf',
                                    className: 'btn btn-outline-danger',
                                    onClick: async (item) => {
                                        try {
                                            const token = localStorage.getItem('access');
                                            const pdfUrl = `/api/allotment-actions/${item.id}/generate-pdf/?access_token=${token}`;
                                            window.open(pdfUrl, '_blank');
                                        } catch (err) {
                                            alert(err.response?.data?.error || 'Failed to generate PDF');
                                        }
                                    }
                                },
                                {
                                    label: 'Transfer Letter',
                                    icon: 'bi bi-file-earmark-text',
                                    className: 'btn btn-outline-warning',
                                    onClick: (item) => {
                                        // Navigate to allocate page and scroll to transfer letter section
                                        navigate(`/allotments/${item.id}/allocate`, { state: { scrollToTransferLetter: true } })
                                    }
                                },
                                {
                                    label: 'Copy',
                                    icon: 'bi bi-files',
                                    className: 'btn btn-outline-primary',
                                    onClick: async (item) => {
                                        if (!window.confirm('Create a copy of this allotment without invoice and items?')) {
                                            return;
                                        }
                                        try {
                                            await api.post(`/allotments/${item.id}/copy/`);
                                            alert('Allotment copied successfully');
                                            fetchData(currentPage, pageSize, filterParams);
                                        } catch (err) {
                                            alert(err.response?.data?.error || 'Failed to copy allotment');
                                        }
                                    }
                                }
                            ] : entityName === 'bill-of-entries' ? [
                                {
                                    label: 'Transfer Letter',
                                    icon: 'bi bi-file-earmark-text',
                                    className: 'btn btn-outline-warning',
                                    onClick: (item) => {
                                        navigate(`/bill-of-entries/${item.id}/generate-transfer-letter`);
                                    }
                                },
                                {
                                    label: 'Update Product Name',
                                    icon: 'bi bi-arrow-repeat',
                                    className: 'btn btn-outline-info',
                                    onClick: async (item) => {
                                        if (!window.confirm(`Update product name for BOE ${item.bill_of_entry_number}?`)) {
                                            return;
                                        }
                                        try {
                                            const response = await api.post(`/bill-of-entries/${item.id}/update-product-name/`);
                                            alert(response.data.message || 'Product name updated successfully');
                                            // Refresh the list to show updated product name
                                            fetchData(currentPage, pageSize, filterParams);
                                        } catch (err) {
                                            alert(err.response?.data?.message || err.response?.data?.error || 'Failed to update product name');
                                        }
                                    },
                                    showIf: (item) => !item.product_name || item.product_name.trim() === ''
                                }
                            ] : []}
                            loading={loading}
                            onEdit={() => {}}
                            onDelete={handleDelete}
                            basePath={entityName === 'licenses' ? '/licenses' :
                                     (entityName === 'trades' ? '/trades' :
                                     `/masters/${entityName}`)}
                            inlineEditable={metadata.inline_editable || []}
                            onInlineUpdate={handleInlineUpdate}
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
