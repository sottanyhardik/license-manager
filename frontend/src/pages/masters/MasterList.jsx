import {useEffect, useState, useCallback, useRef} from "react";
import {Link, useParams, useLocation, useNavigate} from "react-router-dom";
import { toast } from 'react-toastify';
import api from "../../api/axios";
import {boeApi} from "../../services/api";
import AdvancedFilter from "../../components/AdvancedFilter";
import DataPagination from "../../components/DataPagination";
import DataTable from "../../components/DataTable";
import AccordionTable from "../../components/AccordionTable";
import LicenseBalanceModal from "../../components/LicenseBalanceModal";
import TransferLetterModal from "../../components/TransferLetterModal";
import {saveFilterState, restoreFilterState, shouldRestoreFilters} from "../../utils/filterPersistence";
import {useConfirmDialog} from "../../hooks/useConfirmDialog.jsx";

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
        (location.pathname.startsWith('/trades') ? 'trades' : null) ||
        (location.pathname.startsWith('/incentive-licenses') ? 'incentive-licenses' : null);
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

    // Filter state with default filters for allotments, bill-of-entries, and incentive-licenses
    const getDefaultFilters = () => {
        if (entityName === 'allotments') {
            return {
                type: 'AT',
                is_boe: 'False',
                is_allotted: 'all'
            };
        }
        if (entityName === 'bill-of-entries') {
            return {
                is_invoice: 'False'
            };
        }
        if (entityName === 'incentive-licenses') {
            return {
                sold_status: ''  // Empty string = "All" (shows both sold and unsold)
            };
        }
        return {};
    };

    const [filterParams, setFilterParams] = useState(getDefaultFilters());
    const backendDefaultsApplied = useRef(false);
    const pendingRequestRef = useRef(null);
    const abortControllerRef = useRef(null);

    // License Balance Modal state
    const [showBalanceModal, setShowBalanceModal] = useState(false);
    const [selectedLicenseId, setSelectedLicenseId] = useState(null);

    // Transfer Letter Modal state (for BOE)
    const [showTransferLetterModal, setShowTransferLetterModal] = useState(false);
    const [transferLetterType, setTransferLetterType] = useState('');
    const [transferLetterEntityId, setTransferLetterEntityId] = useState(null);

    // BOE card expanded rows
    const [linkModalTrade, setLinkModalTrade] = useState(null);
    const [linkSearch, setLinkSearch] = useState('');
    const [linkResults, setLinkResults] = useState([]);
    const [linkSearching, setLinkSearching] = useState(false);

    const openLinkModal = (trade) => { setLinkModalTrade(trade); setLinkSearch(''); setLinkResults([]); };
    const closeLinkModal = () => { setLinkModalTrade(null); setLinkSearch(''); setLinkResults([]); };

    const searchTradesForLink = async (query) => {
        if (!query.trim()) { setLinkResults([]); return; }
        setLinkSearching(true);
        try {
            const resp = await api.get('trades/', { params: { invoice_number: query, page_size: 10 } });
            const results = (resp.data.results || resp.data || []).filter(t => t.id !== linkModalTrade?.id && !t.linked_trade_id && !t.linked_trade_info);
            setLinkResults(results);
        } catch { setLinkResults([]); }
        finally { setLinkSearching(false); }
    };

    const confirmLink = async (partner) => {
        try {
            await api.post(`trades/${linkModalTrade.id}/link-trade/`, { partner_id: partner.id });
            toast.success(`Linked: ${linkModalTrade.invoice_number} ↔ ${partner.invoice_number}`);
            closeLinkModal();
            fetchData();
        } catch (err) { toast.error(err.response?.data?.error || 'Failed to link trades'); }
    };

    const [expandedPairs, setExpandedPairs] = useState(new Set());
    const togglePair = (pairKey) => {
        setExpandedPairs(prev => {
            const next = new Set(prev);
            if (next.has(pairKey)) next.delete(pairKey);
            else next.add(pairKey);
            return next;
        });
    };

    const [expandedBoeRows, setExpandedBoeRows] = useState(new Set());
    const toggleBoeRow = (id) => {
        setExpandedBoeRows(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    const [editingInvoiceId, setEditingInvoiceId] = useState(null);
    const [invoiceDraft, setInvoiceDraft] = useState('');
    const [invoiceSaving, setInvoiceSaving] = useState(false);

    // BOE Merge Modal state
    const [showMergeModal, setShowMergeModal] = useState(false);
    const [mergeBoeTarget, setMergeBoeTarget] = useState(null);
    const [mergeBoeSource, setMergeBoeSource] = useState(null);
    const [mergeBoeLoading, setMergeBoeLoading] = useState(false);
    const [mergeCandidates, setMergeCandidates] = useState([]);
    const [mergeCandidatesLoading, setMergeCandidatesLoading] = useState(false);

    const openMergeModal = async (item) => {
        setMergeBoeTarget(item);
        setMergeBoeSource(null);
        setShowMergeModal(true);
        setMergeCandidatesLoading(true);
        try {
            const resp = await boeApi.fetchBOEList({ search: item.bill_of_entry_number, is_invoice: 'all', page_size: 50 });
            const candidates = (resp.results || []).filter(b => b.id !== item.id && b.bill_of_entry_number === item.bill_of_entry_number);
            setMergeCandidates(candidates);
        } catch {
            toast.error('Failed to load merge candidates');
        } finally {
            setMergeCandidatesLoading(false);
        }
    };

    const closeMergeModal = () => {
        setShowMergeModal(false);
        setMergeBoeTarget(null);
        setMergeBoeSource(null);
        setMergeCandidates([]);
    };

    const doMerge = async () => {
        if (!mergeBoeTarget || !mergeBoeSource) return;
        setMergeBoeLoading(true);
        try {
            const resp = await boeApi.mergeBOE(mergeBoeTarget.id, mergeBoeSource.id);
            toast.success(resp.message || 'BOE merged successfully');
            closeMergeModal();
            fetchData(currentPage, pageSize, filterParams);
        } catch (err) {
            toast.error(err.response?.data?.error || 'Failed to merge BOE');
        } finally {
            setMergeBoeLoading(false);
        }
    };

    const startInvoiceEdit = (item) => {
        setEditingInvoiceId(item.id);
        setInvoiceDraft(item.invoice_no || '');
    };

    const cancelInvoiceEdit = () => {
        setEditingInvoiceId(null);
        setInvoiceDraft('');
    };

    const saveInvoiceEdit = async (itemId) => {
        setInvoiceSaving(true);
        try {
            await api.patch(`bill-of-entries/${itemId}/`, { invoice_no: invoiceDraft.trim() });
            setData(prev => prev.map(d => d.id === itemId ? { ...d, invoice_no: invoiceDraft.trim() } : d));
            setEditingInvoiceId(null);
        } catch (e) {
            console.error('Failed to update invoice_no:', e);
        } finally {
            setInvoiceSaving(false);
        }
    };

    // Confirmation dialog hook
    const { confirmDelete, confirmDangerousAction, confirmDialog } = useConfirmDialog();

    const fetchData = useCallback(async (page = 1, size = 25, filters = {}) => {
        // Abort any pending request and clear its key — the replacement request must always proceed
        if (abortControllerRef.current) {
            abortControllerRef.current.abort();
            pendingRequestRef.current = null;
        }

        // Create new AbortController for this request
        abortControllerRef.current = new AbortController();

        const requestKey = JSON.stringify({page, size, filters, entity: entityName});

        // Mark this request as pending
        pendingRequestRef.current = requestKey;

        setLoading(true);
        setError("");

        let aborted = false;

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
                    apiPath = `${entityName}/`;
                } else if (entityName === 'incentive-licenses') {
                    apiPath = `incentive-licenses/`;
                } else {
                    apiPath = `masters/${entityName}/`;
                }

                const {data: apiResponse} = await api.get(apiPath, {
                    params,
                    signal: abortControllerRef.current.signal
                });
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
            // Ignore abort errors — they're expected when a new request cancels the previous one.
            // Mark as aborted so finally doesn't clear loading (the new request is already in flight).
            if (err.name === 'AbortError' || err.name === 'CanceledError') {
                aborted = true;
                return;
            }
            const errorMsg = err.response?.data?.detail || "Failed to load data";
            setError(errorMsg);
            toast.error(errorMsg);
        } finally {
            // Don't stop the loading spinner for aborted requests — the replacement
            // request has already called setLoading(true) and is still in progress.
            if (!aborted) {
                setLoading(false);
                pendingRequestRef.current = null;
            }
        }
    }, [entityName]);

    // Load data only when entityName changes
    useEffect(() => {
        if (!entityName) return;

        // Reset flags when entity changes
        backendDefaultsApplied.current = false;
        pendingRequestRef.current = null;

        // Clear filters from other entities to prevent cross-contamination
        // This ensures each entity starts fresh unless explicitly restoring its own filters
        const allEntities = ['licenses', 'allotments', 'trades', 'bill-of-entries', 'incentive-licenses'];
        allEntities.forEach(entity => {
            if (entity !== entityName) {
                try {
                    sessionStorage.removeItem(`${entity}ListFilters`);
                    // Also clear the filter state key used by filterPersistence
                    sessionStorage.removeItem(`filterState_${entity}`);
                } catch {
                    // Silently handle error
                }
            }
        });

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
            const defaultFilters = getDefaultFilters();

            if (restored) {
                // Merge restored filters with default filters
                // For incentive-licenses, ensure sold_status is always set (use default if not in restored)
                const mergedFilters = {
                    ...restored.filters,
                    ...Object.fromEntries(
                        Object.entries(defaultFilters).filter(([key]) => !(key in restored.filters))
                    )
                };
                setFilterParams(mergedFilters);
                setCurrentPage(restored.pagination?.currentPage || 1);
                setPageSize(restored.pagination?.pageSize || 25);
                backendDefaultsApplied.current = true;
                fetchData(restored.pagination?.currentPage || 1, restored.pagination?.pageSize || 25, mergedFilters);
            } else {
                // Use default filters
                setCurrentPage(1);
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
        if (Object.keys(backendDefaults).length > 0 && Object.keys(hardcodedDefaults).length === 0) {
            setFilterParams(backendDefaults);
            backendDefaultsApplied.current = true;
            // Fetch data with the default filters
            fetchData(1, pageSize, backendDefaults);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [metadata.default_filters]);

    useEffect(() => {
        if (!linkModalTrade) return;
        const t = setTimeout(() => searchTradesForLink(linkSearch), 350);
        return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [linkSearch, linkModalTrade]);

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
        const confirmed = await confirmDelete('this record');
        if (!confirmed) {
            return;
        }

        try {
            if (entityName === 'bill-of-entries') {
                await boeApi.deleteBOE(item.id);
            } else {
                let apiPath;
                if (entityName === 'licenses' || entityName === 'allotments' || entityName === 'trades' || entityName === 'incentive-licenses') {
                    apiPath = `${entityName}/${item.id}/`;
                } else {
                    apiPath = `masters/${entityName}/${item.id}/`;
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
        // Optimistic UI update - update local state immediately
        setData(prevData =>
            prevData.map(dataItem =>
                dataItem.id === item.id
                    ? { ...dataItem, [field]: newValue }
                    : dataItem
            )
        );

        try {
            let apiPath;
            if (entityName === 'licenses' || entityName === 'allotments' || entityName === 'trades') {
                apiPath = `${entityName}/${item.id}/`;
            } else if (entityName === 'bill-of-entries') {
                apiPath = `bill-of-entries/${item.id}/`;
            } else {
                apiPath = `masters/${entityName}/${item.id}/`;
            }

            await api.patch(apiPath, { [field]: newValue });
            toast.success("Field updated successfully");
            // Refresh data to ensure consistency with backend
            fetchData(currentPage, pageSize, filterParams);
        } catch (err) {
            // Revert optimistic update on error
            setData(prevData =>
                prevData.map(dataItem =>
                    dataItem.id === item.id
                        ? { ...dataItem, [field]: !newValue }
                        : dataItem
                )
            );
            toast.error(err.response?.data?.detail || `Failed to update ${field}`);
            throw err; // Re-throw to let component know it failed
        }
    };

    const handleInlineUpdate = async (itemId, fieldName, newValue) => {
        try {
            let apiPath;
            if (entityName === 'licenses' || entityName === 'allotments' || entityName === 'trades') {
                apiPath = `${entityName}/${itemId}/`;
            } else if (entityName === 'bill-of-entries') {
                apiPath = `bill-of-entries/${itemId}/`;
            } else {
                apiPath = `masters/${entityName}/${itemId}/`;
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
                    apiPath = `licenses/export/`;
                } else if (entityName === 'allotments') {
                    apiPath = `allotments/download/`;
                } else if (entityName === 'bill-of-entries') {
                    apiPath = `bill-of-entries/export/`;
                } else if (entityName === 'trades') {
                    apiPath = `trades/export/`;
                } else {
                    apiPath = `masters/${entityName}/export/`;
                }

                if (format === 'pdf') {
                    // For PDF, use blob with Authorization header
                    const response = await api.get(apiPath, {
                        params,
                        responseType: 'blob',
                        headers: { Authorization: `Bearer ${localStorage.getItem('access')}` }
                    });
                    const blob = new Blob([response.data], { type: 'application/pdf' });
                    const url = window.URL.createObjectURL(blob);
                    // Open in new browser tab for viewing
                    window.open(url, '_blank');
                    // Also trigger download
                    const today = new Date().toISOString().split('T')[0];
                    const dlLink = document.createElement('a');
                    dlLink.href = url;
                    dlLink.setAttribute('download', `BOE-Report-${today}.pdf`);
                    document.body.appendChild(dlLink);
                    dlLink.click();
                    dlLink.remove();
                    // Revoke after enough time for both tab and download to complete
                    setTimeout(() => window.URL.revokeObjectURL(url), 30000);
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

    const handlePortExcelExport = async () => {
        try {
            const blob = await boeApi.exportBOEPortExcel(filterParams);
            const blobObj = new Blob([blob], {
                type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            });
            const url = window.URL.createObjectURL(blobObj);
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `port-boe-report_${new Date().toISOString().split('T')[0]}.xlsx`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
        } catch (err) {
            toast.error(err.response?.data?.detail || 'Failed to export Port Excel');
        }
    };

    const entityTitle = entityName
        ?.split("-")
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");

    return (
        <div className="container-fluid" style={{ backgroundColor: 'var(--bs-gray-50)', minHeight: '100vh', padding: '24px' }}>
            {/* Professional Header with Gradient */}
            <div style={{
                background: 'linear-gradient(135deg, #4F46E5 0%, #4338CA 100%)',
                padding: '32px',
                borderRadius: '12px',
                boxShadow: '0 4px 20px rgba(0,0,0,0.12)',
                color: 'white',
                marginBottom: '24px'
            }}>
                <div className="d-flex justify-content-between align-items-center flex-wrap">
                    <div>
                        {/* Breadcrumb */}
                        <div style={{ marginBottom: '12px', opacity: '0.9' }}>
                            <a
                                href="/"
                                onClick={(e) => { e.preventDefault(); navigate('/'); }}
                                style={{ color: 'white', textDecoration: 'none', fontSize: '0.9rem' }}
                            >
                                <i className="bi bi-house-door me-2"></i>Home
                            </a>
                            <span className="mx-2">/</span>
                            <span style={{ fontSize: '0.9rem' }}>{entityTitle}</span>
                        </div>
                        <h1 style={{ fontSize: '2rem', fontWeight: '700', marginBottom: '0' }}>
                            <i className="bi bi-grid-3x3-gap me-3"></i>
                            {entityTitle}
                        </h1>
                    </div>
                    <div className="btn-group" style={{ marginTop: '12px' }}>
                    <button
                        className="btn"
                        onClick={() => handleExport('xlsx')}
                        aria-label="Export to Excel"
                        title="Export to Excel"
                        style={{
                            backgroundColor: 'rgba(255, 255, 255, 0.2)',
                            border: '1px solid rgba(255, 255, 255, 0.3)',
                            color: 'white',
                            fontWeight: '500',
                            backdropFilter: 'blur(10px)'
                        }}
                    >
                        <i className="bi bi-file-earmark-excel me-1" aria-hidden="true"></i>
                        Excel
                    </button>
                    <button
                        className="btn"
                        onClick={() => handleExport('pdf')}
                        aria-label="Export to PDF"
                        title="Export to PDF"
                        style={{
                            backgroundColor: 'rgba(255, 255, 255, 0.2)',
                            border: '1px solid rgba(255, 255, 255, 0.3)',
                            color: 'white',
                            fontWeight: '500',
                            backdropFilter: 'blur(10px)'
                        }}
                    >
                        <i className="bi bi-file-earmark-pdf me-1" aria-hidden="true"></i>
                        PDF
                    </button>
                    {entityName === 'bill-of-entries' && (
                        <button
                            className="btn"
                            onClick={handlePortExcelExport}
                            aria-label="Port Excel Download"
                            title="Download port-wise BOE Excel (BOE No, Date, Port, Company, Qty, CIF INR, Item) using applied filters"
                            style={{
                                backgroundColor: 'rgba(255, 255, 255, 0.2)',
                                border: '1px solid rgba(255, 255, 255, 0.3)',
                                color: 'white',
                                fontWeight: '500',
                                backdropFilter: 'blur(10px)'
                            }}
                        >
                            <i className="bi bi-file-earmark-excel me-1" aria-hidden="true"></i>
                            Port Excel
                        </button>
                    )}
                    {entityName === 'bill-of-entries' && (
                        <button
                            className="btn"
                            style={{
                                backgroundColor: 'rgba(255, 255, 255, 0.2)',
                                border: '1px solid rgba(255, 255, 255, 0.3)',
                                color: 'white',
                                fontWeight: '500',
                                backdropFilter: 'blur(10px)'
                            }}
                            onClick={async () => {
                                const confirmed = await confirmDangerousAction(
                                    'Bulk Update Product Names',
                                    'This will update product names for ALL BOEs with empty product_name in the entire database. This may take some time. Continue?'
                                );
                                if (!confirmed) {
                                    return;
                                }

                                setLoading(true);
                                setError("");

                                try {
                                    const response = await api.post(`bill-of-entries/bulk-update-product-names/`);

                                    setLoading(false);

                                    if (response.data.success) {
                                        toast.success(response.data.message || `Processed ${response.data.total} BOEs: ${response.data.updated} updated, ${response.data.skipped} skipped`);

                                        // Refresh the list to show updated product names
                                        fetchData(currentPage, pageSize, filterParams);
                                    } else {
                                        setError('Failed to update product names');
                                    }
                                } catch (err) {
                                    setLoading(false);
                                    setError(err.response?.data?.error || err.response?.data?.message || 'Failed to update product names');
                                    toast.error(err.response?.data?.error || err.response?.data?.message || 'Failed to update product names');
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
                            entityName === 'allotments' ? '/allotments/create' :
                            entityName === 'trades' ? '/trades/create' :
                            `/masters/${entityName}/create`}
                        className="btn"
                        style={{
                            fontWeight: '600',
                            backgroundColor: 'white',
                            border: '2px solid white',
                            color: 'var(--primary-color)',
                            boxShadow: '0 2px 8px rgba(0,0,0,0.15)'
                        }}
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
                key={entityName} // Force remount when entity changes to clear search and filters
                filterConfig={metadata.filter_config || {}}
                searchFields={metadata.search_fields || []}
                onFilterChange={handleFilterChange}
                initialFilters={filterParams}
                defaultFilters={metadata.default_filters || {}}
            />

            {/* Table */}
            <div className="card border-0 shadow-sm" style={{ borderRadius: '12px' }}>
                <div className="card-body" style={{ padding: '24px' }}>
                    {/* BOE Card Layout */}
                    {entityName === 'bill-of-entries' && (
                        loading ? (
                            <div className="text-center py-5">
                                <div className="spinner-border text-primary" role="status"></div>
                                <div className="mt-2 text-muted">Loading Bill of Entries...</div>
                            </div>
                        ) : data.length === 0 ? (
                            <div className="text-center py-5 text-muted">
                                <i className="bi bi-inbox" style={{ fontSize: '2rem' }}></i>
                                <div className="mt-2">No bill of entries found</div>
                            </div>
                        ) : (
                            <div>
                                {data.map(item => {
                                    const isExpanded = expandedBoeRows.has(item.id);
                                    const itemCount = item.item_details?.length || 0;
                                    const fmtInr = (val) => val ? `₹${Number(val).toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '-';
                                    return (
                                        <div key={item.id} style={{
                                            display: 'block',
                                            background: '#ffffff',
                                            border: '1px solid #e2e8f0',
                                            borderLeft: '4px solid #4f46e5',
                                            borderRadius: '10px',
                                            marginBottom: '10px',
                                            overflow: 'hidden',
                                            boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                                        }}>
                                            {/* Row 1: Identity */}
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 14px', background: '#f8fafc', borderBottom: '1px solid #e2e8f0', flexWrap: 'wrap' }}>
                                                <span style={{ fontWeight: '700', fontSize: '1rem', color: '#1e1b4b', marginRight: '4px' }}>
                                                    {item.bill_of_entry_number || '-'}
                                                </span>
                                                {item.bill_of_entry_date && (
                                                    <span style={{ fontSize: '0.8rem', color: '#64748b', background: '#f1f5f9', padding: '2px 8px', borderRadius: '4px' }}>
                                                        <i className="bi bi-calendar3 me-1"></i>
                                                        {item.bill_of_entry_date}
                                                    </span>
                                                )}
                                                {item.port_name && (
                                                    <span style={{ fontSize: '0.8rem', color: '#0369a1', background: '#e0f2fe', padding: '2px 8px', borderRadius: '4px', fontWeight: '500' }}>
                                                        <i className="bi bi-geo-alt me-1"></i>{item.port_name}
                                                    </span>
                                                )}
                                                {item.company_name && (
                                                    <span style={{ fontSize: '0.8rem', color: '#7c3aed', background: '#ede9fe', padding: '2px 8px', borderRadius: '4px', fontWeight: '500' }}>
                                                        <i className="bi bi-building me-1"></i>{item.company_name}
                                                    </span>
                                                )}
                                                {editingInvoiceId === item.id ? (
                                                    <span style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                                                        <input
                                                            autoFocus
                                                            value={invoiceDraft}
                                                            onChange={e => setInvoiceDraft(e.target.value)}
                                                            onKeyDown={e => { if (e.key === 'Enter') saveInvoiceEdit(item.id); if (e.key === 'Escape') cancelInvoiceEdit(); }}
                                                            placeholder="Invoice number"
                                                            style={{ fontSize: '0.78rem', padding: '2px 6px', borderRadius: '4px', border: '1px solid #059669', width: '160px', outline: 'none' }}
                                                        />
                                                        <button onClick={() => saveInvoiceEdit(item.id)} disabled={invoiceSaving} style={{ fontSize: '0.72rem', padding: '2px 7px', borderRadius: '4px', background: '#059669', color: 'white', border: 'none', cursor: 'pointer' }}>
                                                            {invoiceSaving ? '…' : 'Save'}
                                                        </button>
                                                        <button onClick={cancelInvoiceEdit} style={{ fontSize: '0.72rem', padding: '2px 6px', borderRadius: '4px', background: '#e5e7eb', color: '#374151', border: 'none', cursor: 'pointer' }}>✕</button>
                                                    </span>
                                                ) : (
                                                    <span
                                                        onClick={() => startInvoiceEdit(item)}
                                                        title="Click to edit invoice number"
                                                        style={{ fontSize: '0.78rem', color: '#059669', background: '#d1fae5', padding: '2px 8px', borderRadius: '4px', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: '4px' }}
                                                    >
                                                        {item.invoice_no
                                                            ? <><i className="bi bi-receipt"></i> {item.invoice_no}</>
                                                            : <><i className="bi bi-plus-circle"></i> Add Invoice No</>
                                                        }
                                                        <i className="bi bi-pencil-fill" style={{ fontSize: '0.6rem', opacity: 0.6 }}></i>
                                                    </span>
                                                )}
                                            </div>

                                            {/* Row 2: Product + licenses + expand button */}
                                            <div style={{ padding: '10px 14px', background: '#ffffff', borderBottom: '1px solid #e2e8f0' }}>
                                                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', flexWrap: 'wrap' }}>
                                                    <div style={{ flex: 1, minWidth: '200px' }}>
                                                        <div style={{ fontSize: '0.7rem', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '3px' }}>Product</div>
                                                        <div style={{ fontSize: '0.875rem', color: '#1e293b', fontWeight: '500' }}>
                                                            {item.product_name || <span style={{ color: '#94a3b8', fontStyle: 'italic' }}>No product name</span>}
                                                        </div>
                                                    </div>
                                                    {item.licenses && (
                                                        <div style={{ flex: 1, minWidth: '140px' }}>
                                                            <div style={{ fontSize: '0.7rem', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '3px' }}>Licenses</div>
                                                            <div style={{ fontSize: '0.82rem', color: '#4f46e5', fontWeight: '500' }}>{item.licenses}</div>
                                                        </div>
                                                    )}
                                                    {itemCount > 0 && (
                                                        <button
                                                            onClick={() => toggleBoeRow(item.id)}
                                                            style={{ display: 'flex', alignItems: 'center', gap: '5px', fontSize: '0.8rem', color: '#4f46e5', background: '#eef2ff', border: '1px solid #c7d2fe', borderRadius: '6px', padding: '5px 10px', cursor: 'pointer', whiteSpace: 'nowrap', alignSelf: 'center' }}
                                                        >
                                                            <i className={`bi bi-${isExpanded ? 'chevron-up' : 'chevron-down'}`}></i>
                                                            {itemCount} Item{itemCount !== 1 ? 's' : ''}
                                                        </button>
                                                    )}
                                                </div>
                                            </div>

                                            {/* Row 3: Stats + Actions */}
                                            <div style={{ display: 'flex', alignItems: 'center', padding: '8px 14px', background: '#f8fafc', gap: '8px', flexWrap: 'wrap' }}>
                                                <div style={{ display: 'flex', gap: '20px', flex: 1, flexWrap: 'wrap' }}>
                                                    <div>
                                                        <div style={{ fontSize: '0.67rem', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase' }}>CIF (INR)</div>
                                                        <div style={{ fontSize: '0.875rem', color: '#1e293b', fontWeight: '700' }}>{fmtInr(item.total_inr)}</div>
                                                    </div>
                                                    <div>
                                                        <div style={{ fontSize: '0.67rem', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase' }}>CIF (FC)</div>
                                                        <div style={{ fontSize: '0.875rem', color: '#1e293b', fontWeight: '600' }}>{item.total_fc ? Number(item.total_fc).toLocaleString('en-IN', { maximumFractionDigits: 2 }) : '-'}</div>
                                                    </div>
                                                    <div>
                                                        <div style={{ fontSize: '0.67rem', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase' }}>Qty (MT)</div>
                                                        <div style={{ fontSize: '0.875rem', color: '#1e293b', fontWeight: '600' }}>{item.total_quantity ? Number(item.total_quantity).toLocaleString('en-IN', { maximumFractionDigits: 3 }) : '-'}</div>
                                                    </div>
                                                </div>
                                                <div style={{ display: 'flex', gap: '6px', flexShrink: 0 }}>
                                                    <button
                                                        onClick={() => { setTransferLetterType('boe'); setTransferLetterEntityId(item.id); setShowTransferLetterModal(true); }}
                                                        title="Transfer Letter"
                                                        style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#92400e', background: '#fef3c7', border: '1px solid #f59e0b', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}
                                                    >
                                                        <i className="bi bi-file-earmark-text"></i> TL
                                                    </button>
                                                    <button
                                                        onClick={() => openMergeModal(item)}
                                                        title="Merge BOE"
                                                        style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#7c3aed', background: '#ede9fe', border: '1px solid #c4b5fd', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}
                                                    >
                                                        <i className="bi bi-intersect"></i>
                                                    </button>
                                                    {(!item.product_name || item.product_name.trim() === '') && (
                                                        <button
                                                            onClick={async () => {
                                                                if (!window.confirm(`Update product name for BOE ${item.bill_of_entry_number}?`)) return;
                                                                try {
                                                                    const response = await api.post(`bill-of-entries/${item.id}/update-product-name/`);
                                                                    toast.success(response.data.message || 'Product name updated');
                                                                    fetchData(currentPage, pageSize, filterParams);
                                                                } catch (err) {
                                                                    toast.error(err.response?.data?.message || 'Failed to update product name');
                                                                }
                                                            }}
                                                            title="Update Product Name"
                                                            style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#0369a1', background: '#e0f2fe', border: '1px solid #38bdf8', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}
                                                        >
                                                            <i className="bi bi-arrow-repeat"></i>
                                                        </button>
                                                    )}
                                                    <button
                                                        onClick={() => { saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' }); navigate(`/masters/bill-of-entries/${item.id}/edit`); }}
                                                        title="Edit"
                                                        style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#1d4ed8', background: '#eff6ff', border: '1px solid #93c5fd', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}
                                                    >
                                                        <i className="bi bi-pencil"></i>
                                                    </button>
                                                    <button
                                                        onClick={() => handleDelete(item)}
                                                        title="Delete"
                                                        style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#b91c1c', background: '#fff1f2', border: '1px solid #fca5a5', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}
                                                    >
                                                        <i className="bi bi-trash"></i>
                                                    </button>
                                                </div>
                                            </div>

                                            {/* Expandable: Item Details */}
                                            {isExpanded && itemCount > 0 && (
                                                <div style={{ padding: '10px 14px', background: '#fafaf9', borderTop: '1px solid #e2e8f0' }}>
                                                    <div style={{ fontSize: '0.7rem', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>Item Details</div>
                                                    <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
                                                        {item.item_details.map((detail, idx) => (
                                                            <div key={detail.id || idx} style={{ display: 'flex', alignItems: 'center', gap: '8px', flexWrap: 'wrap', background: '#ffffff', border: '1px solid #e2e8f0', borderRadius: '6px', padding: '7px 12px', fontSize: '0.82rem' }}>
                                                                <span style={{ fontWeight: '600', color: '#4f46e5', minWidth: '90px' }}>{detail.license_number || '-'}</span>
                                                                <span style={{ flex: 1, color: '#334155', minWidth: '120px' }}>{detail.item_description || '-'}</span>
                                                                {detail.hs_code && <span style={{ background: '#f1f5f9', color: '#475569', padding: '1px 6px', borderRadius: '4px', fontSize: '0.75rem', whiteSpace: 'nowrap' }}>{detail.hs_code}</span>}
                                                                <span style={{ color: '#64748b', whiteSpace: 'nowrap' }}>Qty: <strong>{detail.qty || '-'}</strong></span>
                                                                <span style={{ color: '#64748b', whiteSpace: 'nowrap' }}>FC: <strong>{detail.cif_fc || '-'}</strong></span>
                                                                <span style={{ color: '#1e293b', fontWeight: '600', whiteSpace: 'nowrap' }}>INR: {fmtInr(detail.cif_inr)}</span>
                                                            </div>
                                                        ))}
                                                    </div>
                                                </div>
                                            )}
                                        </div>
                                    );
                                })}
                            </div>
                        )
                    )}

                    {/* Allotments Card Layout */}
                    {entityName === 'allotments' && (
                        loading ? (
                            <div className="text-center py-5">
                                <div className="spinner-border text-primary" role="status"></div>
                                <div className="mt-2 text-muted">Loading Allotments...</div>
                            </div>
                        ) : data.length === 0 ? (
                            <div className="text-center py-5 text-muted">
                                <i className="bi bi-inbox" style={{ fontSize: '2rem' }}></i>
                                <div className="mt-2">No allotments found</div>
                            </div>
                        ) : (
                            <div>
                                {data.map(item => {
                                    const fmtInr = (val) => val ? `₹${Number(val).toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '-';
                                    return (
                                        <div key={item.id} style={{
                                            display: 'block',
                                            background: '#ffffff',
                                            border: `1px solid ${item.is_boe ? '#86efac' : '#e2e8f0'}`,
                                            borderLeft: `4px solid ${item.is_boe ? '#22c55e' : '#4f46e5'}`,
                                            borderRadius: '10px',
                                            marginBottom: '10px',
                                            overflow: 'hidden',
                                            boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                                        }}>
                                            {/* Row 1: Identity */}
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 14px', background: '#f8fafc', borderBottom: '1px solid #e2e8f0', flexWrap: 'wrap' }}>
                                                <span style={{ fontWeight: '700', fontSize: '1rem', color: '#1e1b4b', marginRight: '4px' }}>
                                                    {item.invoice || <span style={{ fontStyle: 'italic', color: '#94a3b8', fontWeight: '400', fontSize: '0.875rem' }}>No Invoice</span>}
                                                </span>
                                                {item.estimated_arrival_date && (
                                                    <span style={{ fontSize: '0.8rem', color: '#64748b', background: '#f1f5f9', padding: '2px 8px', borderRadius: '4px' }}>
                                                        <i className="bi bi-calendar3 me-1"></i>{item.estimated_arrival_date}
                                                    </span>
                                                )}
                                                {item.port_name && (
                                                    <span style={{ fontSize: '0.8rem', color: '#0369a1', background: '#e0f2fe', padding: '2px 8px', borderRadius: '4px', fontWeight: '500' }}>
                                                        <i className="bi bi-geo-alt me-1"></i>{item.port_name}
                                                    </span>
                                                )}
                                                {item.company_name && (
                                                    <span style={{ fontSize: '0.8rem', color: '#7c3aed', background: '#ede9fe', padding: '2px 8px', borderRadius: '4px', fontWeight: '500' }}>
                                                        <i className="bi bi-building me-1"></i>{item.company_name}
                                                    </span>
                                                )}
                                                {item.is_boe && (
                                                    <span style={{ fontSize: '0.75rem', color: '#166534', background: '#dcfce7', padding: '2px 8px', borderRadius: '4px', fontWeight: '600' }}>
                                                        BOE ✓
                                                    </span>
                                                )}
                                                {item.is_approved && (
                                                    <span style={{ fontSize: '0.75rem', color: '#1d4ed8', background: '#dbeafe', padding: '2px 8px', borderRadius: '4px', fontWeight: '600' }}>
                                                        Approved
                                                    </span>
                                                )}
                                            </div>

                                            {/* Row 2: Item + Licenses */}
                                            <div style={{ padding: '10px 14px', background: '#ffffff', borderBottom: '1px solid #e2e8f0' }}>
                                                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '12px', flexWrap: 'wrap' }}>
                                                    <div style={{ flex: 1, minWidth: '200px' }}>
                                                        <div style={{ fontSize: '0.7rem', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '3px' }}>Item</div>
                                                        <div style={{ fontSize: '0.875rem', color: '#1e293b', fontWeight: '500' }}>
                                                            {item.item_name || <span style={{ color: '#94a3b8', fontStyle: 'italic' }}>No item name</span>}
                                                        </div>
                                                    </div>
                                                    {item.dfia_list && (
                                                        <div style={{ flex: 1, minWidth: '140px' }}>
                                                            <div style={{ fontSize: '0.7rem', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '3px' }}>Licenses</div>
                                                            <div style={{ fontSize: '0.82rem', color: '#4f46e5', fontWeight: '500' }}>{item.dfia_list}</div>
                                                        </div>
                                                    )}
                                                </div>
                                            </div>

                                            {/* Row 3: Stats + Actions */}
                                            <div style={{ display: 'flex', alignItems: 'center', padding: '8px 14px', background: '#f8fafc', gap: '8px', flexWrap: 'wrap' }}>
                                                <div style={{ display: 'flex', gap: '20px', flex: 1, flexWrap: 'wrap' }}>
                                                    <div>
                                                        <div style={{ fontSize: '0.67rem', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase' }}>Req Qty</div>
                                                        <div style={{ fontSize: '0.875rem', color: '#1e293b', fontWeight: '700' }}>{item.required_quantity ? Number(item.required_quantity).toLocaleString('en-IN', { maximumFractionDigits: 3 }) : '-'}</div>
                                                    </div>
                                                    <div>
                                                        <div style={{ fontSize: '0.67rem', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase' }}>Req Value</div>
                                                        <div style={{ fontSize: '0.875rem', color: '#1e293b', fontWeight: '600' }}>{fmtInr(item.required_value)}</div>
                                                    </div>
                                                    <div>
                                                        <div style={{ fontSize: '0.67rem', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase' }}>Balanced Qty</div>
                                                        <div style={{ fontSize: '0.875rem', color: item.balanced_quantity > 0 ? '#059669' : '#94a3b8', fontWeight: '600' }}>{item.balanced_quantity ? Number(item.balanced_quantity).toLocaleString('en-IN', { maximumFractionDigits: 3 }) : '-'}</div>
                                                    </div>
                                                </div>
                                                <div style={{ display: 'flex', gap: '6px', flexShrink: 0 }}>
                                                    <button onClick={() => { saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' }); navigate(`/allotments/${item.id}/edit`); }} title="Edit" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#1d4ed8', background: '#eff6ff', border: '1px solid #93c5fd', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                        <i className="bi bi-pencil"></i>
                                                    </button>
                                                    <button onClick={async () => {
                                                        if (!window.confirm(`Create a copy of allotment ${item.invoice || 'this allotment'}?`)) return;
                                                        try {
                                                            const r = await api.post(`allotments/${item.id}/copy/`);
                                                            toast.success('Allotment copied. Opening in edit mode...');
                                                            saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' });
                                                            navigate(`/allotments/${r.data.id}/edit`);
                                                        } catch (err) { toast.error(err.response?.data?.error || 'Failed to copy'); }
                                                    }} title="Copy" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#0369a1', background: '#e0f2fe', border: '1px solid #38bdf8', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                        <i className="bi bi-copy"></i>
                                                    </button>
                                                    <button onClick={() => { saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' }); navigate(`/allotments/${item.id}/allocate`); }} title="Allocate" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#166534', background: '#dcfce7', border: '1px solid #86efac', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                        <i className="bi bi-box-arrow-in-down"></i>
                                                    </button>
                                                    <button onClick={async () => {
                                                        try {
                                                            const r = await api.get(`allotment-actions/${item.id}/generate-pdf/`, { responseType: 'blob', headers: { Authorization: `Bearer ${localStorage.getItem('access')}` } });
                                                            const url = window.URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }));
                                                            window.open(url, '_blank');
                                                            setTimeout(() => window.URL.revokeObjectURL(url), 30000);
                                                        } catch (err) { toast.error(err.response?.data?.error || 'Failed to generate PDF'); }
                                                    }} title="Preview Allotment" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#92400e', background: '#fef3c7', border: '1px solid #f59e0b', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                        <i className="bi bi-eye"></i>
                                                    </button>
                                                    <button onClick={async () => {
                                                        try {
                                                            const r = await api.get(`allotment-actions/${item.id}/generate-pdf/`, { responseType: 'blob', headers: { Authorization: `Bearer ${localStorage.getItem('access')}` } });
                                                            const url = window.URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }));
                                                            const a = document.createElement('a');
                                                            a.href = url;
                                                            a.download = `Allotment-${item.invoice || item.id}.pdf`;
                                                            document.body.appendChild(a); a.click(); a.remove();
                                                            setTimeout(() => window.URL.revokeObjectURL(url), 10000);
                                                        } catch (err) { toast.error(err.response?.data?.error || 'Failed to download PDF'); }
                                                    }} title="Download Allotment" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#1e40af', background: '#eff6ff', border: '1px solid #93c5fd', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                        <i className="bi bi-download"></i>
                                                    </button>
                                                    <button onClick={() => handleDelete(item)} title="Delete" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#b91c1c', background: '#fff1f2', border: '1px solid #fca5a5', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                        <i className="bi bi-trash"></i>
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )
                    )}

                    {/* Licenses Card Layout */}
                    {entityName === 'licenses' && (
                        loading ? (
                            <div className="text-center py-5">
                                <div className="spinner-border text-primary" role="status"></div>
                                <div className="mt-2 text-muted">Loading Licenses...</div>
                            </div>
                        ) : data.length === 0 ? (
                            <div className="text-center py-5 text-muted">
                                <i className="bi bi-inbox" style={{ fontSize: '2rem' }}></i>
                                <div className="mt-2">No licenses found</div>
                            </div>
                        ) : (
                            <div>
                                {data.map(item => {
                                    const fmtInr = (val) => val ? `₹${Number(val).toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '-';
                                    const parseIndianDate = (s) => { if (!s) return null; const p = s.split('-'); return p.length === 3 ? new Date(p[2], p[1]-1, p[0]) : null; };
                                    const isExpired = item.license_expiry_date && parseIndianDate(item.license_expiry_date) < new Date();
                                    const statusColor = item.purchase_status_code === 'E1' ? { bg: '#dbeafe', text: '#1d4ed8' }
                                        : item.purchase_status_code === 'E5' ? { bg: '#dcfce7', text: '#166534' }
                                        : { bg: '#f1f5f9', text: '#475569' };
                                    return (
                                        <div key={item.id} style={{
                                            display: 'block',
                                            background: '#ffffff',
                                            border: `1px solid ${isExpired ? '#fca5a5' : '#e2e8f0'}`,
                                            borderLeft: `4px solid ${isExpired ? '#ef4444' : '#4f46e5'}`,
                                            borderRadius: '10px',
                                            marginBottom: '10px',
                                            overflow: 'hidden',
                                            boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                                        }}>
                                            {/* Row 1: Identity */}
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 14px', background: '#f8fafc', borderBottom: '1px solid #e2e8f0', flexWrap: 'wrap' }}>
                                                <span style={{ fontWeight: '700', fontSize: '1rem', color: '#1e1b4b', marginRight: '4px' }}>
                                                    {item.license_number || '-'}
                                                </span>
                                                {item.license_date && (
                                                    <span style={{ fontSize: '0.8rem', color: '#64748b', background: '#f1f5f9', padding: '2px 8px', borderRadius: '4px' }}>
                                                        <i className="bi bi-calendar3 me-1"></i>{item.license_date}
                                                    </span>
                                                )}
                                                {item.license_expiry_date && (
                                                    <span style={{ fontSize: '0.8rem', color: isExpired ? '#b91c1c' : '#64748b', background: isExpired ? '#fff1f2' : '#f1f5f9', padding: '2px 8px', borderRadius: '4px' }}>
                                                        <i className="bi bi-calendar-x me-1"></i>Exp: {item.license_expiry_date}
                                                    </span>
                                                )}
                                                {item.ledger_date && (
                                                    <span style={{ fontSize: '0.8rem', color: '#0f766e', background: '#ccfbf1', padding: '2px 8px', borderRadius: '4px' }}>
                                                        <i className="bi bi-journal-check me-1"></i>Ledger: {item.ledger_date}
                                                    </span>
                                                )}
                                                {item.port_name && (
                                                    <span style={{ fontSize: '0.8rem', color: '#0369a1', background: '#e0f2fe', padding: '2px 8px', borderRadius: '4px', fontWeight: '500' }}>
                                                        <i className="bi bi-geo-alt me-1"></i>{item.port_name}
                                                    </span>
                                                )}
                                                {item.exporter_name && (
                                                    <span style={{ fontSize: '0.8rem', color: '#7c3aed', background: '#ede9fe', padding: '2px 8px', borderRadius: '4px', fontWeight: '500' }}>
                                                        <i className="bi bi-building me-1"></i>{item.exporter_name}
                                                    </span>
                                                )}
                                                {item.exporter_iec && (
                                                    <span style={{ fontSize: '0.8rem', color: '#b45309', background: '#fef3c7', padding: '2px 8px', borderRadius: '4px', fontWeight: '500' }}>
                                                        <i className="bi bi-fingerprint me-1"></i>IEC: {item.exporter_iec}
                                                    </span>
                                                )}
                                                {item.purchase_status_label && (
                                                    <span style={{ fontSize: '0.75rem', color: statusColor.text, background: statusColor.bg, padding: '2px 8px', borderRadius: '4px', fontWeight: '600' }}>
                                                        {item.purchase_status_label}
                                                    </span>
                                                )}
                                                {(item.has_tl || item.has_copy) && (
                                                    <button onClick={async (e) => {
                                                        e.stopPropagation();
                                                        try {
                                                            const r = await api.get(`licenses/${item.id}/merged-documents/`, { responseType: 'blob', headers: { Authorization: `Bearer ${localStorage.getItem('access')}` } });
                                                            const url = window.URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }));
                                                            window.open(url, '_blank');
                                                            setTimeout(() => window.URL.revokeObjectURL(url), 100);
                                                        } catch (err) {
                                                            if (err.response?.status === 404) {
                                                                toast.warning('Document files are not available on this server. The files may not have been uploaded yet.');
                                                            } else {
                                                                toast.error(err.response?.data ? String(err.response.data).slice(0, 200) : 'Failed to load documents');
                                                            }
                                                        }
                                                    }} style={{ fontSize: '0.72rem', color: '#059669', background: '#d1fae5', padding: '2px 6px', borderRadius: '4px', fontWeight: '500', border: 'none', cursor: 'pointer' }}>
                                                        Copy
                                                    </button>
                                                )}
                                            </div>

                                            {/* Row 2: Norm class + Transfer */}
                                            <div style={{ padding: '10px 14px', background: '#ffffff', borderBottom: '1px solid #e2e8f0' }}>
                                                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '16px', flexWrap: 'wrap' }}>
                                                    {item.get_norm_class && (
                                                        <div style={{ minWidth: '120px' }}>
                                                            <div style={{ fontSize: '0.7rem', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '3px' }}>Norm Class</div>
                                                            <div style={{ fontSize: '0.875rem', color: '#1e293b', fontWeight: '500' }}>{item.get_norm_class}</div>
                                                        </div>
                                                    )}
                                                    {item.latest_transfer && (
                                                        <div style={{ flex: 1, minWidth: '160px' }}>
                                                            <div style={{ fontSize: '0.7rem', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '3px' }}>Latest Transfer</div>
                                                            <div style={{ fontSize: '0.82rem', color: '#334155' }}>{item.latest_transfer}</div>
                                                        </div>
                                                    )}
                                                    {!item.get_norm_class && !item.latest_transfer && (
                                                        <div style={{ fontSize: '0.82rem', color: '#94a3b8', fontStyle: 'italic' }}>No additional details</div>
                                                    )}
                                                </div>
                                            </div>

                                            {/* Row 3: Stats + Actions */}
                                            <div style={{ display: 'flex', alignItems: 'center', padding: '8px 14px', background: '#f8fafc', gap: '8px', flexWrap: 'wrap' }}>
                                                <div style={{ display: 'flex', gap: '20px', flex: 1, flexWrap: 'wrap' }}>
                                                    <div>
                                                        <div style={{ fontSize: '0.67rem', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase' }}>Balance CIF</div>
                                                        <div style={{ fontSize: '0.875rem', color: '#1e293b', fontWeight: '700' }}>{fmtInr(item.get_balance_cif)}</div>
                                                    </div>
                                                </div>
                                                <div style={{ display: 'flex', gap: '6px', flexShrink: 0 }}>
                                                    <button onClick={() => { saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' }); navigate(`/licenses/${item.id}/edit`); }} title="Edit" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#1d4ed8', background: '#eff6ff', border: '1px solid #93c5fd', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                        <i className="bi bi-pencil"></i>
                                                    </button>
                                                    <button onClick={() => { setSelectedLicenseId(item.id); setShowBalanceModal(true); }} title="View Balance" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#0369a1', background: '#e0f2fe', border: '1px solid #38bdf8', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                        <i className="bi bi-eye"></i>
                                                    </button>
                                                    <button onClick={async () => {
                                                        try {
                                                            const r = await api.get(`licenses/${item.id}/balance-pdf/`, { responseType: 'blob', headers: { Authorization: `Bearer ${localStorage.getItem('access')}` } });
                                                            const url = window.URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }));
                                                            window.open(url, '_blank');
                                                            setTimeout(() => window.URL.revokeObjectURL(url), 100);
                                                        } catch (err) { toast.error(err?.response?.data?.error || 'Failed to generate PDF'); }
                                                    }} title="Download PDF" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#92400e', background: '#fef3c7', border: '1px solid #f59e0b', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                        <i className="bi bi-file-pdf"></i>
                                                    </button>
                                                    <button onClick={async () => {
                                                        try {
                                                            const r = await api.get(`licenses/${item.id}/balance-excel/`, { responseType: 'blob', headers: { Authorization: `Bearer ${localStorage.getItem('access')}` } });
                                                            const blob = new Blob([r.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
                                                            const url = window.URL.createObjectURL(blob);
                                                            const a = document.createElement('a'); a.href = url; a.download = `${item.license_number || item.id}-balance.xlsx`; document.body.appendChild(a); a.click(); document.body.removeChild(a);
                                                            setTimeout(() => window.URL.revokeObjectURL(url), 100);
                                                        } catch (err) { toast.error(err?.response?.data?.error || 'Failed to generate Excel'); }
                                                    }} title="Download Excel" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#166534', background: '#dcfce7', border: '1px solid #86efac', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                        <i className="bi bi-file-earmark-excel"></i>
                                                    </button>
                                                    <button onClick={() => handleDelete(item)} title="Delete" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#b91c1c', background: '#fff1f2', border: '1px solid #fca5a5', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                        <i className="bi bi-trash"></i>
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )
                    )}

                    {/* Trades Card Layout */}
                    {entityName === 'trades' && (
                        loading ? (
                            <div className="text-center py-5"><div className="spinner-border text-primary" role="status"></div><div className="mt-2 text-muted">Loading Trades...</div></div>
                        ) : data.length === 0 ? (
                            <div className="text-center py-5 text-muted"><i className="bi bi-inbox" style={{ fontSize: '2rem' }}></i><div className="mt-2">No trades found</div></div>
                        ) : (() => {
                            const fmtInr = (val) => val ? `₹${Number(val).toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '-';

                            const renderTradeCard = (item) => {
                                const dirColor = item.direction === 'SALE' ? { border: '#86efac', left: '#22c55e', bg: '#dcfce7', text: '#166534' }
                                    : item.direction === 'PURCHASE' ? { border: '#93c5fd', left: '#3b82f6', bg: '#dbeafe', text: '#1d4ed8' }
                                    : item.direction === 'COMMISSION_SALE' ? { border: '#fdba74', left: '#f97316', bg: '#ffedd5', text: '#9a3412' }
                                    : { border: '#c4b5fd', left: '#8b5cf6', bg: '#ede9fe', text: '#5b21b6' };
                                const isLinked = !!(item.linked_trade_id || item.linked_trade_info);
                                return (
                                    <div key={item.id} style={{ display: 'block', background: '#ffffff', border: `1px solid ${dirColor.border}`, borderLeft: `4px solid ${dirColor.left}`, borderRadius: '10px', marginBottom: '10px', overflow: 'hidden', boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
                                        {/* Row 1: Identity */}
                                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 14px', background: '#f8fafc', borderBottom: '1px solid #e2e8f0', flexWrap: 'wrap' }}>
                                            <span style={{ fontWeight: '700', fontSize: '1rem', color: '#1e1b4b', marginRight: '4px' }}>
                                                {item.invoice_number || <span style={{ fontStyle: 'italic', color: '#94a3b8', fontWeight: '400', fontSize: '0.875rem' }}>No Invoice</span>}
                                            </span>
                                            <span style={{ fontSize: '0.78rem', fontWeight: '700', color: dirColor.text, background: dirColor.bg, padding: '2px 8px', borderRadius: '4px' }}>
                                                {item.direction_label || item.direction}
                                            </span>
                                            {item.license_type_label && (
                                                <span style={{ fontSize: '0.78rem', color: '#475569', background: '#f1f5f9', padding: '2px 8px', borderRadius: '4px' }}>{item.license_type_label}</span>
                                            )}
                                            {item.invoice_date && (
                                                <span style={{ fontSize: '0.8rem', color: '#64748b', background: '#f1f5f9', padding: '2px 8px', borderRadius: '4px' }}>
                                                    <i className="bi bi-calendar3 me-1"></i>{item.invoice_date}
                                                </span>
                                            )}
                                        </div>

                                        {/* Row 2: From → To + BOE */}
                                        <div style={{ padding: '10px 14px', background: '#ffffff', borderBottom: '1px solid #e2e8f0' }}>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flexWrap: 'wrap' }}>
                                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', flex: 1, minWidth: '200px' }}>
                                                    <div>
                                                        <div style={{ fontSize: '0.67rem', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px' }}>From</div>
                                                        <div style={{ fontSize: '0.875rem', color: '#1e293b', fontWeight: '500' }}>{item.from_company_label || '-'}</div>
                                                    </div>
                                                    <i className="bi bi-arrow-right" style={{ color: '#94a3b8', fontSize: '1rem' }}></i>
                                                    <div>
                                                        <div style={{ fontSize: '0.67rem', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px' }}>To</div>
                                                        <div style={{ fontSize: '0.875rem', color: '#1e293b', fontWeight: '500' }}>{item.to_company_label || '-'}</div>
                                                    </div>
                                                </div>
                                                {item.boe_label && (
                                                    <div style={{ minWidth: '100px' }}>
                                                        <div style={{ fontSize: '0.67rem', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px' }}>BOE</div>
                                                        <div style={{ fontSize: '0.82rem', color: '#4f46e5', fontWeight: '500' }}>{item.boe_label}</div>
                                                    </div>
                                                )}
                                                {item.incentive_license && (
                                                    <div style={{ minWidth: '100px' }}>
                                                        <div style={{ fontSize: '0.67rem', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px' }}>Incentive Lic</div>
                                                        <div style={{ fontSize: '0.82rem', color: '#059669', fontWeight: '500' }}>{item.incentive_license}</div>
                                                    </div>
                                                )}
                                            </div>
                                        </div>

                                        {/* Row 3: Stats + Actions */}
                                        <div style={{ display: 'flex', alignItems: 'center', padding: '8px 14px', background: '#f8fafc', gap: '8px', flexWrap: 'wrap' }}>
                                            <div style={{ display: 'flex', gap: '20px', flex: 1, flexWrap: 'wrap' }}>
                                                <div><div style={{ fontSize: '0.67rem', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase' }}>Total</div><div style={{ fontSize: '0.875rem', color: '#1e293b', fontWeight: '700' }}>{fmtInr(item.total_amount)}</div></div>
                                                <div><div style={{ fontSize: '0.67rem', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase' }}>Paid/Rcvd</div><div style={{ fontSize: '0.875rem', color: '#059669', fontWeight: '600' }}>{fmtInr(item.paid_or_received)}</div></div>
                                                <div><div style={{ fontSize: '0.67rem', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase' }}>Due</div><div style={{ fontSize: '0.875rem', color: item.due_amount > 0 ? '#b91c1c' : '#64748b', fontWeight: '600' }}>{fmtInr(item.due_amount)}</div></div>
                                            </div>
                                            <div style={{ display: 'flex', gap: '6px', flexShrink: 0 }}>
                                                <button onClick={() => { setTransferLetterType('trade'); setTransferLetterEntityId(item.id); setShowTransferLetterModal(true); }} title="Transfer Letter" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#92400e', background: '#fef3c7', border: '1px solid #f59e0b', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                    <i className="bi bi-file-earmark-text"></i> TL
                                                </button>
                                                {item.direction === 'SALE' && (<>
                                                    <button onClick={async () => {
                                                        try {
                                                            const r = await api.get(`trades/${item.id}/generate-bill-of-supply/`, { params: { include_signature: true }, responseType: 'blob' });
                                                            const url = window.URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }));
                                                            const a = document.createElement('a'); a.href = url; a.download = `Bill_of_Supply_${item.invoice_number}_with_sign.pdf`; document.body.appendChild(a); a.click(); a.remove();
                                                            window.URL.revokeObjectURL(url);
                                                        } catch (err) { toast.error('Failed to generate invoice'); }
                                                    }} title="Invoice (With Sign)" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#166534', background: '#dcfce7', border: '1px solid #86efac', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                        <i className="bi bi-file-pdf"></i> +Sign
                                                    </button>
                                                    <button onClick={async () => {
                                                        try {
                                                            const r = await api.get(`trades/${item.id}/generate-bill-of-supply/`, { params: { include_signature: false }, responseType: 'blob' });
                                                            const url = window.URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }));
                                                            const a = document.createElement('a'); a.href = url; a.download = `Bill_of_Supply_${item.invoice_number}_without_sign.pdf`; document.body.appendChild(a); a.click(); a.remove();
                                                            window.URL.revokeObjectURL(url);
                                                        } catch (err) { toast.error('Failed to generate invoice'); }
                                                    }} title="Invoice (Without Sign)" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#92400e', background: '#fef3c7', border: '1px solid #f59e0b', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                        <i className="bi bi-file-pdf"></i> -Sign
                                                    </button>
                                                </>)}
                                                {item.direction === 'PURCHASE' && !isLinked && (
                                                    <button onClick={async () => {
                                                        if (!window.confirm('Create a SALE trade from this PURCHASE trade?')) return;
                                                        try {
                                                            const resp = await api.get(`trades/${item.id}/`);
                                                            const p = resp.data;
                                                            const saleData = { direction: 'SALE', license_type: p.license_type || 'DFIA', from_company: p.to_company?.id || p.to_company, to_company: p.from_company?.id || p.from_company, boe: p.boe?.id || p.boe, invoice_number: '', invoice_date: new Date().toISOString().split('T')[0], remarks: p.remarks || '', from_pan: p.to_pan, from_gst: p.to_gst, from_addr_line_1: p.to_addr_line_1, from_addr_line_2: p.to_addr_line_2, to_pan: p.from_pan, to_gst: p.from_gst, to_addr_line_1: p.from_addr_line_1, to_addr_line_2: p.from_addr_line_2, lines: (p.lines || []).map(l => ({ sr_number: l.sr_number, description: l.description, hsn_code: l.hsn_code, mode: l.mode, qty_kg: l.qty_kg, rate_inr_per_kg: l.rate_inr_per_kg, cif_fc: l.cif_fc, exc_rate: l.exc_rate, cif_inr: l.cif_inr, fob_inr: l.fob_inr, pct: l.pct, amount_inr: l.amount_inr })), incentive_lines: [], payments: [] };
                                                            const nr = await api.post('trades/', saleData);
                                                            toast.success('SALE trade created. Opening in edit mode...');
                                                            saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' });
                                                            navigate(`/trades/${nr.data.id}/edit`);
                                                        } catch (err) { toast.error(err.response?.data?.non_field_errors?.[0] || 'Failed to copy trade'); }
                                                    }} title="Copy to Sale" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#1d4ed8', background: '#eff6ff', border: '1px solid #93c5fd', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                        <i className="bi bi-arrow-left-right"></i>
                                                    </button>
                                                )}
                                                {!isLinked && (
                                                    <button onClick={() => openLinkModal(item)} title="Link to existing trade" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#6366f1', background: '#eef2ff', border: '1px solid #a5b4fc', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                        <i className="bi bi-link-45deg"></i>
                                                    </button>
                                                )}
                                                <button onClick={() => { saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' }); navigate(`/trades/${item.id}/edit`); }} title="Edit" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#4f46e5', background: '#eef2ff', border: '1px solid #a5b4fc', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                    <i className="bi bi-pencil-fill"></i>
                                                </button>
                                                <button onClick={() => handleDelete(item)} title="Delete" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#b91c1c', background: '#fff1f2', border: '1px solid #fca5a5', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                    <i className="bi bi-trash"></i>
                                                </button>
                                            </div>
                                        </div>
                                    </div>
                                );
                            };

                            // Group linked trades into pairs; keep unpaired as singles
                            const seen = new Set();
                            const tradeGroups = [];
                            data.forEach(trade => {
                                if (seen.has(trade.id)) return;
                                seen.add(trade.id);
                                const linked = trade.linked_trade_info;
                                if (linked) {
                                    const partner = data.find(t => t.id === linked.id);
                                    if (partner && !seen.has(partner.id)) {
                                        seen.add(partner.id);
                                        const sale = trade.direction.includes('SALE') ? trade : partner;
                                        const purchase = trade.direction.includes('PURCHASE') ? trade : partner;
                                        tradeGroups.push({ type: 'pair', sale, purchase, pairKey: `pair-${Math.min(trade.id, partner.id)}` });
                                        return;
                                    }
                                }
                                tradeGroups.push({ type: 'single', trade, pairKey: `single-${trade.id}` });
                            });

                            return (
                                <div>
                                    {tradeGroups.map(group => {
                                        if (group.type === 'single') {
                                            return renderTradeCard(group.trade);
                                        }
                                        // Paired group
                                        const { sale, purchase, pairKey } = group;
                                        const isExpanded = expandedPairs.has(pairKey);
                                        const companies = `${sale.from_company_label || '-'} ↔ ${sale.to_company_label || '-'}`;
                                        return (
                                            <div key={pairKey} style={{ border: '1px solid #a5b4fc', borderLeft: '4px solid #6366f1', borderRadius: '10px', marginBottom: '10px', overflow: 'hidden', boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
                                                <div
                                                    style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 14px', background: '#eef2ff', cursor: 'pointer', flexWrap: 'wrap' }}
                                                    onClick={() => togglePair(pairKey)}
                                                >
                                                    <span style={{ fontSize: '0.78rem', fontWeight: '700', color: '#166534', background: '#dcfce7', padding: '2px 8px', borderRadius: '4px' }}>Sale</span>
                                                    <i className="bi bi-link-45deg" style={{ color: '#6366f1', fontSize: '1rem' }}></i>
                                                    <span style={{ fontSize: '0.78rem', fontWeight: '700', color: '#1d4ed8', background: '#dbeafe', padding: '2px 8px', borderRadius: '4px' }}>Purchase</span>
                                                    <span style={{ fontSize: '0.82rem', color: '#4f46e5', fontWeight: '600', flex: 1 }}>{companies}</span>
                                                    <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
                                                        {sale.invoice_date || ''}
                                                    </span>
                                                    <span style={{ fontSize: '0.8rem', color: '#64748b' }}>
                                                        Sale: {fmtInr(sale.total_amount)} · Purchase: {fmtInr(purchase.total_amount)}
                                                    </span>
                                                    <i className={`bi bi-chevron-${isExpanded ? 'up' : 'down'}`} style={{ color: '#6366f1' }}></i>
                                                </div>
                                                {isExpanded && (
                                                    <div style={{ padding: '8px', background: '#f8fafc', display: 'flex', flexDirection: 'column', gap: '8px' }}>
                                                        {renderTradeCard(sale)}
                                                        {renderTradeCard(purchase)}
                                                    </div>
                                                )}
                                            </div>
                                        );
                                    })}
                                </div>
                            );
                        })()
                    )}

                    {/* Incentive Licenses Card Layout */}
                    {entityName === 'incentive-licenses' && (
                        loading ? (
                            <div className="text-center py-5"><div className="spinner-border text-primary" role="status"></div><div className="mt-2 text-muted">Loading Incentive Licenses...</div></div>
                        ) : data.length === 0 ? (
                            <div className="text-center py-5 text-muted"><i className="bi bi-inbox" style={{ fontSize: '2rem' }}></i><div className="mt-2">No incentive licenses found</div></div>
                        ) : (
                            <div>
                                {data.map(item => {
                                    const fmtInr = (val) => val ? `₹${Number(val).toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '-';
                                    const parseIndianDate = (s) => { if (!s) return null; const p = s.split('-'); return p.length === 3 ? new Date(p[2], p[1]-1, p[0]) : null; };
                                    const isExpired = item.license_expiry_date && parseIndianDate(item.license_expiry_date) < new Date();
                                    const soldStyle = item.sold_status === 'YES' ? { border: '#fca5a5', left: '#ef4444', badge: '#fff1f2', badgeText: '#b91c1c', label: 'Sold' }
                                        : item.sold_status === 'PARTIAL' ? { border: '#fde68a', left: '#f59e0b', badge: '#fef3c7', badgeText: '#92400e', label: 'Partial' }
                                        : { border: '#86efac', left: '#22c55e', badge: '#dcfce7', badgeText: '#166534', label: 'Available' };
                                    return (
                                        <div key={item.id} style={{ display: 'block', background: '#ffffff', border: `1px solid ${soldStyle.border}`, borderLeft: `4px solid ${soldStyle.left}`, borderRadius: '10px', marginBottom: '10px', overflow: 'hidden', boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
                                            {/* Row 1: Identity */}
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 14px', background: '#f8fafc', borderBottom: '1px solid #e2e8f0', flexWrap: 'wrap' }}>
                                                <span style={{ fontWeight: '700', fontSize: '1rem', color: '#1e1b4b', marginRight: '4px' }}>{item.license_number || '-'}</span>
                                                {item.license_type && (
                                                    <span style={{ fontSize: '0.78rem', color: '#475569', background: '#f1f5f9', padding: '2px 8px', borderRadius: '4px', fontWeight: '500' }}>{item.license_type}</span>
                                                )}
                                                {item.license_date && (
                                                    <span style={{ fontSize: '0.8rem', color: '#64748b', background: '#f1f5f9', padding: '2px 8px', borderRadius: '4px' }}>
                                                        <i className="bi bi-calendar3 me-1"></i>{item.license_date}
                                                    </span>
                                                )}
                                                {item.license_expiry_date && (
                                                    <span style={{ fontSize: '0.8rem', color: isExpired ? '#b91c1c' : '#64748b', background: isExpired ? '#fff1f2' : '#f1f5f9', padding: '2px 8px', borderRadius: '4px' }}>
                                                        <i className="bi bi-calendar-x me-1"></i>Exp: {item.license_expiry_date}
                                                    </span>
                                                )}
                                                {item.port_name && (
                                                    <span style={{ fontSize: '0.8rem', color: '#0369a1', background: '#e0f2fe', padding: '2px 8px', borderRadius: '4px', fontWeight: '500' }}>
                                                        <i className="bi bi-geo-alt me-1"></i>{item.port_name}
                                                    </span>
                                                )}
                                                {item.exporter_name && (
                                                    <span style={{ fontSize: '0.8rem', color: '#7c3aed', background: '#ede9fe', padding: '2px 8px', borderRadius: '4px', fontWeight: '500' }}>
                                                        <i className="bi bi-building me-1"></i>{item.exporter_name}
                                                    </span>
                                                )}
                                                {item.exporter_iec && (
                                                    <span style={{ fontSize: '0.8rem', color: '#b45309', background: '#fef3c7', padding: '2px 8px', borderRadius: '4px', fontWeight: '500' }}>
                                                        <i className="bi bi-fingerprint me-1"></i>IEC: {item.exporter_iec}
                                                    </span>
                                                )}
                                                <span style={{ fontSize: '0.75rem', color: soldStyle.badgeText, background: soldStyle.badge, padding: '2px 8px', borderRadius: '4px', fontWeight: '600' }}>
                                                    {soldStyle.label}
                                                </span>
                                                {!item.is_active && (
                                                    <span style={{ fontSize: '0.72rem', color: '#64748b', background: '#f1f5f9', padding: '2px 6px', borderRadius: '4px' }}>Inactive</span>
                                                )}
                                            </div>

                                            {/* Row 3: Stats + Actions */}
                                            <div style={{ display: 'flex', alignItems: 'center', padding: '8px 14px', background: '#f8fafc', gap: '8px', flexWrap: 'wrap' }}>
                                                <div style={{ display: 'flex', gap: '20px', flex: 1, flexWrap: 'wrap' }}>
                                                    <div><div style={{ fontSize: '0.67rem', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase' }}>License Value</div><div style={{ fontSize: '0.875rem', color: '#1e293b', fontWeight: '700' }}>{fmtInr(item.license_value)}</div></div>
                                                    <div><div style={{ fontSize: '0.67rem', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase' }}>Sold Value</div><div style={{ fontSize: '0.875rem', color: '#b91c1c', fontWeight: '600' }}>{fmtInr(item.sold_value)}</div></div>
                                                    <div><div style={{ fontSize: '0.67rem', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase' }}>Balance</div><div style={{ fontSize: '0.875rem', color: item.balance_value > 0 ? '#059669' : '#94a3b8', fontWeight: '600' }}>{fmtInr(item.balance_value)}</div></div>
                                                </div>
                                                <div style={{ display: 'flex', gap: '6px', flexShrink: 0 }}>
                                                    <button onClick={() => { saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' }); navigate(`/masters/incentive-licenses/${item.id}/edit`); }} title="Edit" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#1d4ed8', background: '#eff6ff', border: '1px solid #93c5fd', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                        <i className="bi bi-pencil"></i>
                                                    </button>
                                                    <button onClick={() => handleDelete(item)} title="Delete" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#b91c1c', background: '#fff1f2', border: '1px solid #fca5a5', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                        <i className="bi bi-trash"></i>
                                                    </button>
                                                </div>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )
                    )}

                    {/* Use AccordionTable for entities with nested fields (except licenses, allotments, bill-of-entries), regular DataTable for others */}
                    {entityName !== 'bill-of-entries' && entityName !== 'allotments' && entityName !== 'licenses' && entityName !== 'trades' && entityName !== 'incentive-licenses' && (metadata.nested_field_defs && Object.keys(metadata.nested_field_defs).length > 0 ? (
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
                            lazyLoadNested={false}
                            customActions={entityName === 'trades' ? [
                                {
                                    label: 'Transfer Letter',
                                    icon: 'bi bi-file-earmark-text',
                                    className: 'btn btn-outline-info',
                                    onClick: (item) => {
                                        setTransferLetterType('trade');
                                        setTransferLetterEntityId(item.id);
                                        setShowTransferLetterModal(true);
                                    }
                                },
                                {
                                    label: 'Invoice (With Sign)',
                                    icon: 'bi bi-file-pdf',
                                    className: 'btn btn-outline-success',
                                    onClick: async (item) => {
                                        // Only allow for SALE transactions
                                        if (item.direction !== 'SALE') {
                                            toast.warning('Bill of Supply can only be generated for SALE transactions');
                                            return;
                                        }
                                        try {
                                            const response = await api.get(`trades/${item.id}/generate-bill-of-supply/`, {
                                                params: { include_signature: true },
                                                responseType: 'blob'
                                            });
                                            const blob = new Blob([response.data], { type: 'application/pdf' });
                                            const url = window.URL.createObjectURL(blob);
                                            const link = document.createElement('a');
                                            link.href = url;
                                            link.download = `Bill_of_Supply_${item.invoice_number}_${new Date().toISOString().split('T')[0]}_with_sign.pdf`;
                                            document.body.appendChild(link);
                                            link.click();
                                            link.remove();
                                            window.URL.revokeObjectURL(url);
                                            toast.success('Bill of Supply downloaded with signature');
                                        } catch (err) {
                                            toast.error(err.response?.data?.error || 'Failed to generate Bill of Supply PDF');
                                        }
                                    },
                                    // Only show for SALE transactions
                                    showIf: (item) => item.direction === 'SALE'
                                },
                                {
                                    label: 'Invoice (Without Sign)',
                                    icon: 'bi bi-file-pdf',
                                    className: 'btn btn-outline-warning',
                                    onClick: async (item) => {
                                        // Only allow for SALE transactions
                                        if (item.direction !== 'SALE') {
                                            toast.warning('Bill of Supply can only be generated for SALE transactions');
                                            return;
                                        }
                                        try {
                                            const response = await api.get(`trades/${item.id}/generate-bill-of-supply/`, {
                                                params: { include_signature: false },
                                                responseType: 'blob'
                                            });
                                            const blob = new Blob([response.data], { type: 'application/pdf' });
                                            const url = window.URL.createObjectURL(blob);
                                            const link = document.createElement('a');
                                            link.href = url;
                                            link.download = `Bill_of_Supply_${item.invoice_number}_${new Date().toISOString().split('T')[0]}_without_sign.pdf`;
                                            document.body.appendChild(link);
                                            link.click();
                                            link.remove();
                                            window.URL.revokeObjectURL(url);
                                            toast.success('Bill of Supply downloaded without signature');
                                        } catch (err) {
                                            toast.error(err.response?.data?.error || 'Failed to generate Bill of Supply PDF');
                                        }
                                    },
                                    // Only show for SALE transactions
                                    showIf: (item) => item.direction === 'SALE'
                                },
                                {
                                    label: 'Copy to Sale',
                                    icon: 'bi bi-arrow-left-right',
                                    className: 'btn btn-outline-primary',
                                    onClick: async (item) => {
                                        if (!window.confirm(`Create a SALE trade from this PURCHASE trade?`)) {
                                            return;
                                        }
                                        try {
                                            // Fetch full trade data
                                            const response = await api.get(`trades/${item.id}/`);
                                            const purchaseTrade = response.data;

                                            // Create new SALE trade with swapped companies
                                            const saleTradeData = {
                                                direction: 'SALE',
                                                license_type: purchaseTrade.license_type || 'DFIA',  // Copy license type
                                                from_company: purchaseTrade.to_company?.id || purchaseTrade.to_company,  // Swap: purchase TO becomes sale FROM
                                                to_company: purchaseTrade.from_company?.id || purchaseTrade.from_company,  // Swap: purchase FROM becomes sale TO
                                                boe: purchaseTrade.boe?.id || purchaseTrade.boe,
                                                invoice_number: '',  // Leave empty for user to fill
                                                invoice_date: new Date().toISOString().split('T')[0],  // Today's date
                                                remarks: purchaseTrade.remarks || '',
                                                // Copy company snapshot fields (swapped)
                                                from_pan: purchaseTrade.to_pan,
                                                from_gst: purchaseTrade.to_gst,
                                                from_addr_line_1: purchaseTrade.to_addr_line_1,
                                                from_addr_line_2: purchaseTrade.to_addr_line_2,
                                                to_pan: purchaseTrade.from_pan,
                                                to_gst: purchaseTrade.from_gst,
                                                to_addr_line_1: purchaseTrade.from_addr_line_1,
                                                to_addr_line_2: purchaseTrade.from_addr_line_2,
                                                // Copy lines without IDs (they're new records)
                                                lines: (purchaseTrade.lines || []).map(line => ({
                                                    sr_number: line.sr_number,
                                                    description: line.description,
                                                    hsn_code: line.hsn_code,
                                                    mode: line.mode,
                                                    qty_kg: line.qty_kg,
                                                    rate_inr_per_kg: line.rate_inr_per_kg,
                                                    cif_fc: line.cif_fc,
                                                    exc_rate: line.exc_rate,
                                                    cif_inr: line.cif_inr,
                                                    fob_inr: line.fob_inr,
                                                    pct: line.pct,
                                                    amount_inr: line.amount_inr
                                                })),
                                                incentive_lines: [],  // Empty incentive lines for new trade
                                                payments: []  // Empty payments for new trade
                                            };

                                            const newResponse = await api.post('trades/', saleTradeData);
                                            toast.success('SALE trade created successfully. Opening in edit mode...');

                                            // Save filter state before navigating
                                            saveFilterState(entityName, {
                                                filters: filterParams,
                                                pagination: { currentPage, pageSize },
                                                search: ''
                                            });

                                            // Navigate to edit page of the new SALE trade
                                            navigate(`/trades/${newResponse.data.id}/edit`);
                                        } catch (err) {
                                            console.error('Copy to sale error:', err.response?.data);
                                            // Show detailed error message
                                            if (err.response?.data) {
                                                const errorData = err.response.data;
                                                if (errorData.non_field_errors) {
                                                    toast.error(`Error: ${errorData.non_field_errors[0]}`);
                                                } else if (typeof errorData === 'object') {
                                                    const errorMsg = Object.entries(errorData)
                                                        .map(([field, errors]) => {
                                                            const msgs = Array.isArray(errors) ? errors : [errors];
                                                            return `${field}: ${msgs.join(', ')}`;
                                                        })
                                                        .join('\n');
                                                    toast.error(errorMsg || 'Failed to copy trade to sale');
                                                } else {
                                                    toast.error(errorData.error || errorData.detail || 'Failed to copy trade to sale');
                                                }
                                            } else {
                                                toast.error('Failed to copy trade to sale');
                                            }
                                        }
                                    },
                                    // Only show for PURCHASE transactions
                                    showIf: (item) => item.direction === 'PURCHASE'
                                }
                            ] : entityName === 'licenses' ? [
                                {
                                    label: 'View Balance',
                                    icon: 'bi bi-eye',
                                    className: 'btn btn-outline-info',
                                    onClick: (item) => {
                                        setSelectedLicenseId(item.id);
                                        setShowBalanceModal(true);
                                    }
                                },
                                {
                                    label: 'Ledger',
                                    icon: 'bi bi-file-pdf',
                                    className: 'btn btn-outline-primary',
                                    onClick: async (item) => {
                                        try {
                                            const response = await api.get(`license-actions/${item.id}/download-ledger/`, {
                                                responseType: 'blob',
                                                headers: { Authorization: `Bearer ${localStorage.getItem('access')}` }
                                            });
                                            const blob = new Blob([response.data], { type: 'application/pdf' });
                                            const url = window.URL.createObjectURL(blob);
                                            window.open(url, '_blank');
                                            setTimeout(() => window.URL.revokeObjectURL(url), 100);
                                        } catch (err) {
                                            toast.error(err?.response?.data?.error || 'Failed to generate ledger PDF');
                                        }
                                    }
                                }
                            ] : entityName === 'allotments' ? [
                                {
                                    label: 'Edit',
                                    icon: 'bi bi-pencil',
                                    className: 'btn btn-outline-primary',
                                    onClick: (item) => {
                                        saveFilterState(entityName, {
                                            filters: filterParams,
                                            pagination: { currentPage, pageSize },
                                            search: ''
                                        });
                                        navigate(`/allotments/${item.id}/edit`);
                                    }
                                },
                                {
                                    label: 'Copy',
                                    icon: 'bi bi-copy',
                                    className: 'btn btn-outline-info',
                                    onClick: async (item) => {
                                        if (!window.confirm(`Create a copy of allotment ${item.invoice_number || 'this allotment'}?`)) {
                                            return;
                                        }
                                        try {
                                            const response = await api.post(`allotments/${item.id}/copy/`);
                                            const newAllotmentId = response.data.id;
                                            toast.success('Allotment copied successfully. Opening in edit mode...');
                                            // Save filter state before navigating
                                            saveFilterState(entityName, {
                                                filters: filterParams,
                                                pagination: { currentPage, pageSize },
                                                search: ''
                                            });
                                            // Navigate to edit page of the new copy
                                            navigate(`/allotments/${newAllotmentId}/edit`);
                                        } catch (err) {
                                            toast.error(err.response?.data?.error || 'Failed to copy allotment');
                                        }
                                    }
                                },
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
                                    label: 'Preview',
                                    icon: 'bi bi-eye',
                                    className: 'btn btn-outline-warning',
                                    onClick: async (item) => {
                                        try {
                                            const response = await api.get(`allotment-actions/${item.id}/generate-pdf/`, {
                                                responseType: 'blob',
                                                headers: { Authorization: `Bearer ${localStorage.getItem('access')}` }
                                            });
                                            const blob = new Blob([response.data], { type: 'application/pdf' });
                                            const url = window.URL.createObjectURL(blob);
                                            window.open(url, '_blank');
                                            setTimeout(() => window.URL.revokeObjectURL(url), 30000);
                                        } catch (err) {
                                            toast.error(err.response?.data?.error || 'Failed to preview PDF');
                                        }
                                    }
                                },
                                {
                                    label: 'Download',
                                    icon: 'bi bi-download',
                                    className: 'btn btn-outline-primary',
                                    onClick: async (item) => {
                                        try {
                                            const response = await api.get(`allotment-actions/${item.id}/generate-pdf/`, {
                                                responseType: 'blob',
                                                headers: { Authorization: `Bearer ${localStorage.getItem('access')}` }
                                            });
                                            const blob = new Blob([response.data], { type: 'application/pdf' });
                                            const url = window.URL.createObjectURL(blob);
                                            const a = document.createElement('a');
                                            a.href = url;
                                            a.download = `Allotment-${item.invoice_number || item.id}.pdf`;
                                            document.body.appendChild(a); a.click(); a.remove();
                                            setTimeout(() => window.URL.revokeObjectURL(url), 10000);
                                        } catch (err) {
                                            toast.error(err.response?.data?.error || 'Failed to download PDF');
                                        }
                                    }
                                }
                            ] : entityName === 'bill-of-entries' ? [
                                {
                                    label: 'Transfer Letter',
                                    icon: 'bi bi-file-earmark-text',
                                    className: 'btn btn-outline-warning',
                                    onClick: (item) => {
                                        setTransferLetterType('boe');
                                        setTransferLetterEntityId(item.id);
                                        setShowTransferLetterModal(true);
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
                                            const response = await api.post(`bill-of-entries/${item.id}/update-product-name/`);
                                            toast.success(response.data.message || 'Product name updated successfully');
                                            // Refresh the list to show updated product name
                                            fetchData(currentPage, pageSize, filterParams);
                                        } catch (err) {
                                            toast.error(err.response?.data?.message || err.response?.data?.error || 'Failed to update product name');
                                        }
                                    },
                                    showIf: (item) => !item.product_name || item.product_name.trim() === ''
                                }
                            ] : []}
                            inlineEditable={metadata.inline_editable || []}
                            onInlineUpdate={handleInlineUpdate}
                        />
                    ) : (
                        loading ? (
                            <div className="text-center py-5">
                                <div className="spinner-border text-primary" role="status"></div>
                                <div className="mt-2 text-muted">Loading {entityTitle}...</div>
                            </div>
                        ) : data.length === 0 ? (
                            <div className="text-center py-5 text-muted">
                                <i className="bi bi-inbox" style={{ fontSize: '2rem' }}></i>
                                <div className="mt-2">No {entityTitle ? entityTitle.toLowerCase() : 'records'} found</div>
                            </div>
                        ) : (
                            <div>
                                {data.map(item => {
                                    // list_display is array of strings (field names)
                                    const cols = metadata.list_display || [];
                                    const fmtLabel = (col) => col.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
                                    const getVal = (col) => {
                                        const fieldKey = col.replace(/__/g, '_');
                                        const val = item[fieldKey] !== undefined ? item[fieldKey] : item[col];
                                        if (val === null || val === undefined || val === '') return null;
                                        if (typeof val === 'boolean') return val ? 'Yes' : 'No';
                                        if (typeof val === 'object') return JSON.stringify(val);
                                        return String(val);
                                    };
                                    const primaryCol = cols[0];
                                    const primaryVal = primaryCol ? getVal(primaryCol) : null;
                                    const badgeCols = cols.slice(1, 5);
                                    const extraCols = cols.slice(5);
                                    return (
                                        <div key={item.id} style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            background: '#ffffff',
                                            border: '1px solid #e2e8f0',
                                            borderLeft: '4px solid #4f46e5',
                                            borderRadius: '8px',
                                            marginBottom: '6px',
                                            padding: '10px 14px',
                                            gap: '12px',
                                            boxShadow: '0 1px 3px rgba(0,0,0,0.04)',
                                        }}>
                                            {/* Fields row — equal-width columns so all rows align */}
                                            <div style={{ flex: 1, display: 'flex', gap: '8px', alignItems: 'flex-start', minWidth: 0 }}>
                                                {cols.map((col, idx) => {
                                                    const v = getVal(col);
                                                    return (
                                                        <div key={col} style={{ flex: '1 1 0', minWidth: 0 }}>
                                                            <div style={{ fontSize: '0.65rem', color: '#94a3b8', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '2px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                                                {fmtLabel(col)}
                                                            </div>
                                                            <div style={{
                                                                fontSize: '0.875rem',
                                                                color: idx === 0 ? '#1e1b4b' : '#334155',
                                                                fontWeight: idx === 0 ? '600' : '400',
                                                                wordBreak: 'break-word',
                                                            }}>
                                                                {v ?? <span style={{ color: '#cbd5e1' }}>—</span>}
                                                            </div>
                                                        </div>
                                                    );
                                                })}
                                            </div>

                                            {/* Actions — always right-pinned */}
                                            <div style={{ display: 'flex', gap: '6px', flexShrink: 0, alignSelf: 'center' }}>
                                                <button
                                                    onClick={() => { saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' }); navigate(`/masters/${entityName}/${item.id}/edit`); }}
                                                    title="Edit"
                                                    style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#1d4ed8', background: '#eff6ff', border: '1px solid #93c5fd', borderRadius: '5px', padding: '4px 10px', cursor: 'pointer' }}
                                                >
                                                    <i className="bi bi-pencil"></i> Edit
                                                </button>
                                                <button
                                                    onClick={() => handleDelete(item)}
                                                    title="Delete"
                                                    style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '0.78rem', color: '#b91c1c', background: '#fff1f2', border: '1px solid #fca5a5', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}
                                                >
                                                    <i className="bi bi-trash"></i>
                                                </button>
                                            </div>
                                        </div>
                                    );
                                })}
                            </div>
                        )
                    ))}

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

            {/* License Balance Modal */}
            {entityName === 'licenses' && (
                <LicenseBalanceModal
                    show={showBalanceModal}
                    onHide={() => setShowBalanceModal(false)}
                    licenseId={selectedLicenseId}
                />
            )}

            {/* Transfer Letter Modal (for BOE and Trades) */}
            {(entityName === 'bill-of-entries' || entityName === 'trades') && (
                <TransferLetterModal
                    show={showTransferLetterModal}
                    onHide={() => setShowTransferLetterModal(false)}
                    type={transferLetterType}
                    entityId={transferLetterEntityId}
                />
            )}

            {/* Confirmation Dialog */}
            {confirmDialog}

            {/* Link Trade Modal */}
            {linkModalTrade && (
                <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 1060, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={closeLinkModal}>
                    <div style={{ background: '#fff', borderRadius: '12px', padding: '24px', width: '480px', maxWidth: '95vw', boxShadow: '0 8px 32px rgba(0,0,0,0.18)' }} onClick={e => e.stopPropagation()}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                            <h6 style={{ margin: 0, fontWeight: '700', color: '#1e1b4b' }}>
                                <i className="bi bi-link-45deg me-2" style={{ color: '#6366f1' }}></i>
                                Link Trade: <span style={{ color: '#6366f1' }}>{linkModalTrade.invoice_number || 'No Invoice'}</span>
                            </h6>
                            <button onClick={closeLinkModal} style={{ background: 'none', border: 'none', fontSize: '1.2rem', cursor: 'pointer', color: '#94a3b8' }}>
                                <i className="bi bi-x-lg"></i>
                            </button>
                        </div>
                        <input
                            autoFocus
                            type="text"
                            className="form-control"
                            placeholder="Search by invoice number..."
                            value={linkSearch}
                            onChange={e => setLinkSearch(e.target.value)}
                            style={{ marginBottom: '12px' }}
                        />
                        {linkSearching && <div style={{ textAlign: 'center', color: '#94a3b8', padding: '12px' }}><div className="spinner-border spinner-border-sm text-primary me-2"></div>Searching...</div>}
                        {!linkSearching && linkSearch && linkResults.length === 0 && (
                            <div style={{ textAlign: 'center', color: '#94a3b8', padding: '12px', fontSize: '0.875rem' }}>No unlinked trades found for "{linkSearch}"</div>
                        )}
                        {linkResults.map(t => (
                            <div key={t.id} onClick={() => confirmLink(t)} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 12px', border: '1px solid #e2e8f0', borderRadius: '8px', marginBottom: '8px', cursor: 'pointer', transition: 'background 0.15s' }}
                                onMouseEnter={e => e.currentTarget.style.background = '#f0f9ff'}
                                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                                <div>
                                    <div style={{ fontWeight: '600', fontSize: '0.9rem', color: '#1e293b' }}>{t.invoice_number || 'No Invoice'}</div>
                                    <div style={{ fontSize: '0.78rem', color: '#64748b' }}>{t.from_company_label} → {t.to_company_label}</div>
                                </div>
                                <div style={{ textAlign: 'right' }}>
                                    <span style={{ fontSize: '0.75rem', fontWeight: '700', color: t.direction.includes('SALE') ? '#166534' : '#1d4ed8', background: t.direction.includes('SALE') ? '#dcfce7' : '#dbeafe', padding: '2px 8px', borderRadius: '4px' }}>
                                        {t.direction_label || t.direction}
                                    </span>
                                    <div style={{ fontSize: '0.78rem', color: '#64748b', marginTop: '4px' }}>
                                        ₹{Number(t.total_amount).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                                    </div>
                                </div>
                            </div>
                        ))}
                        {!linkSearch && (
                            <div style={{ textAlign: 'center', color: '#94a3b8', fontSize: '0.875rem', padding: '8px' }}>Type an invoice number to search</div>
                        )}
                    </div>
                </div>
            )}

            {/* BOE Merge Modal */}
            {showMergeModal && mergeBoeTarget && (
                <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 1060, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={closeMergeModal}>
                    <div style={{ background: '#fff', borderRadius: '12px', padding: '24px', width: '560px', maxWidth: '95vw', boxShadow: '0 8px 32px rgba(0,0,0,0.18)' }} onClick={e => e.stopPropagation()}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                            <h6 style={{ margin: 0, fontWeight: '700', color: '#1e1b4b' }}>
                                <i className="bi bi-intersect me-2" style={{ color: '#7c3aed' }}></i>
                                Merge BOE: <span style={{ color: '#7c3aed' }}>{mergeBoeTarget.bill_of_entry_number}</span>
                            </h6>
                            <button onClick={closeMergeModal} style={{ background: 'none', border: 'none', fontSize: '1.2rem', cursor: 'pointer', color: '#94a3b8' }}>
                                <i className="bi bi-x-lg"></i>
                            </button>
                        </div>

                        {/* Target BOE info */}
                        <div style={{ background: '#f0fdf4', border: '1px solid #86efac', borderRadius: '8px', padding: '10px 14px', marginBottom: '16px', fontSize: '0.85rem' }}>
                            <div style={{ fontWeight: '600', color: '#166534', marginBottom: '4px' }}>Target BOE (will be kept &amp; updated)</div>
                            <div><i className="bi bi-geo-alt me-1"></i>{mergeBoeTarget.port_name}</div>
                            <div style={{ color: '#475569', fontSize: '0.78rem' }}>
                                {mergeBoeTarget.item_details?.length || 0} item(s) · {mergeBoeTarget.licenses || 'No licenses'}
                            </div>
                        </div>

                        <div style={{ fontWeight: '600', fontSize: '0.78rem', color: '#64748b', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>
                            Select source BOE to merge from (port replaces target, items moved, source deleted):
                        </div>

                        {mergeCandidatesLoading && (
                            <div style={{ textAlign: 'center', padding: '20px', color: '#94a3b8' }}>
                                <div className="spinner-border spinner-border-sm text-primary me-2"></div>Loading candidates...
                            </div>
                        )}

                        {!mergeCandidatesLoading && mergeCandidates.length === 0 && (
                            <div style={{ textAlign: 'center', padding: '20px', color: '#94a3b8', fontSize: '0.875rem' }}>
                                No other BOEs found with number {mergeBoeTarget.bill_of_entry_number}
                            </div>
                        )}

                        {mergeCandidates.map(candidate => (
                            <div
                                key={candidate.id}
                                onClick={() => setMergeBoeSource(prev => prev?.id === candidate.id ? null : candidate)}
                                style={{
                                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                    padding: '10px 14px', border: `2px solid ${mergeBoeSource?.id === candidate.id ? '#7c3aed' : '#e2e8f0'}`,
                                    borderRadius: '8px', marginBottom: '8px', cursor: 'pointer',
                                    background: mergeBoeSource?.id === candidate.id ? '#faf5ff' : '#ffffff',
                                    transition: 'all 0.15s'
                                }}
                            >
                                <div>
                                    <div style={{ fontWeight: '600', fontSize: '0.875rem', color: '#1e293b' }}>
                                        <i className="bi bi-geo-alt me-1" style={{ color: '#0369a1' }}></i>{candidate.port_name}
                                    </div>
                                    <div style={{ fontSize: '0.78rem', color: '#64748b' }}>
                                        {candidate.item_details?.length || 0} item(s) · {candidate.licenses || 'No licenses'}
                                    </div>
                                </div>
                                <div style={{ textAlign: 'right' }}>
                                    {candidate.total_inr && (
                                        <div style={{ fontWeight: '700', fontSize: '0.875rem', color: '#1e293b' }}>
                                            ₹{Number(candidate.total_inr).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                                        </div>
                                    )}
                                    {mergeBoeSource?.id === candidate.id && (
                                        <span style={{ fontSize: '0.72rem', color: '#7c3aed', fontWeight: '700' }}>✓ Selected</span>
                                    )}
                                </div>
                            </div>
                        ))}

                        {mergeBoeSource && (
                            <div style={{ background: '#faf5ff', border: '1px solid #c4b5fd', borderRadius: '8px', padding: '10px 14px', margin: '12px 0', fontSize: '0.82rem', color: '#4c1d95' }}>
                                <strong>What will happen:</strong>
                                <ul style={{ margin: '6px 0 0 0', paddingLeft: '20px' }}>
                                    <li>Target port will change to <strong>{mergeBoeSource.port_name}</strong></li>
                                    <li>Items from source will be moved to target (duplicates skipped)</li>
                                    <li>Source BOE ({mergeBoeSource.port_name}) will be permanently deleted</li>
                                </ul>
                            </div>
                        )}

                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
                            <button onClick={closeMergeModal} style={{ padding: '6px 16px', borderRadius: '6px', border: '1px solid #e2e8f0', background: '#f8fafc', cursor: 'pointer', fontSize: '0.875rem' }}>
                                Cancel
                            </button>
                            <button
                                onClick={doMerge}
                                disabled={!mergeBoeSource || mergeBoeLoading}
                                style={{ padding: '6px 16px', borderRadius: '6px', border: 'none', background: mergeBoeSource && !mergeBoeLoading ? '#7c3aed' : '#c4b5fd', color: 'white', cursor: mergeBoeSource && !mergeBoeLoading ? 'pointer' : 'not-allowed', fontSize: '0.875rem', fontWeight: '600', display: 'flex', alignItems: 'center', gap: '6px' }}
                            >
                                {mergeBoeLoading
                                    ? <><div className="spinner-border spinner-border-sm" style={{ width: '14px', height: '14px', borderWidth: '2px' }}></div>Merging...</>
                                    : <><i className="bi bi-intersect"></i>Confirm Merge</>
                                }
                            </button>
                        </div>
                    </div>
                </div>
            )}

        </div>
    );
}
