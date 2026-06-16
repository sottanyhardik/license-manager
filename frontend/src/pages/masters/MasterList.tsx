import {useContext, useEffect, useState, useCallback, useRef} from "react";
import {Link, useParams, useLocation, useNavigate} from "react-router-dom";
import {AuthContext} from "../../context/AuthContext";
import { toast } from 'react-toastify';
import api from "../../api/axios";
import {boeApi} from "../../services/api";
import AdvancedFilter from "../../components/AdvancedFilter";
import DataPagination from "../../components/DataPagination";
import DataTable from "../../components/DataTable";
import AccordionTable from "../../components/AccordionTable";
import LicenseBalanceModal from "../../components/LicenseBalanceModal";
import OwnershipDetailsModal from "../../components/OwnershipDetailsModal";
import TransferLetterModal from "../../components/TransferLetterModal";
import { EntityCard, DetailTable } from "../../components/ui";
import {saveFilterState, restoreFilterState, shouldRestoreFilters} from "../../utils/filterPersistence";
import {openPdfPreview} from "../../utils/pdfPreview";
import {useConfirmDialog} from "../../hooks/useConfirmDialog.jsx";
import { Button } from "@/components/ui/button";
import { ArrowRight, BookCheck, Building2, Calendar, CalendarX, Eye, FileSpreadsheet, FileText, Fingerprint, Inbox, Layers, Loader2, MapPin, Network, Pencil, Plus, PlusCircle, Receipt, RefreshCw, Trash2, TriangleAlert, X } from "lucide-react";

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

    // Role-based write access per entity
    const {hasAnyRole, isSuperAdmin, hasRole} = useContext(AuthContext);
    const ENTITY_WRITE_ROLES = {
        'licenses':           ['LICENSE_MANAGER'],
        'allotments':         ['ALLOTMENT_MANAGER'],
        'bill-of-entries':    ['BOE_MANAGER'],
        'trades':             ['TRADE_MANAGER'],
        'incentive-licenses': ['INCENTIVE_LICENSE_MANAGER'],
    };
    // For known business entities: check the mapped write roles.
    // For masters (companies, ports, HS codes, etc.): superusers only.
    const canWrite = entityName in ENTITY_WRITE_ROLES
        ? hasAnyRole(ENTITY_WRITE_ROLES[entityName])
        : isSuperAdmin();

    // ACCOUNT_ACCESS users can edit invoice_no on BOE items only
    const canEditInvoice = canWrite || hasRole('ACCOUNT_ACCESS');
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

    // Tracks license IDs currently fetching ownership from DGFT
    const [fetchingOwnershipIds, setFetchingOwnershipIds] = useState(() => new Set());

    // Ownership details modal state
    const [showOwnershipModal, setShowOwnershipModal] = useState(false);
    const [ownershipLicense, setOwnershipLicense] = useState(null); // { id, number }

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
    const [pdfLoading, setPdfLoading] = useState(false);
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

    const [expandedAllotments, setExpandedAllotments] = useState(new Set());
    const toggleAllotment = (id) => {
        setExpandedAllotments(prev => {
            const next = new Set(prev);
            if (next.has(id)) next.delete(id);
            else next.add(id);
            return next;
        });
    };

    const [expandedTrades, setExpandedTrades] = useState(new Set());
    const toggleTrade = (id) => {
        setExpandedTrades(prev => {
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
            // Dedicated endpoint — accessible to ACCOUNT_ACCESS (and BOE_MANAGER).
            // Does NOT require full BOE edit permission.
            await api.post(`bill-of-entries/${itemId}/update-invoice-no/`, { invoice_no: invoiceDraft.trim() });
            setData(prev => prev.map(d => d.id === itemId ? { ...d, invoice_no: invoiceDraft.trim() } : d));
            setEditingInvoiceId(null);
        } catch (e) {
            toast.error('Failed to update invoice number');
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
                    setPdfLoading(true);
                    try {
                        const response = await api.get(apiPath, {
                            params,
                            responseType: 'blob',
                            headers: { Authorization: `Bearer ${localStorage.getItem('access')}` }
                        });
                        const blob = new Blob([response.data], { type: 'application/pdf' });
                        const opened = openPdfPreview(blob, `${entityName}_${new Date().toISOString().split('T')[0]}.pdf`);
                        if (!opened) {
                            toast.error('Pop-up blocked. Allow pop-ups for this site to view the PDF.');
                        }
                    } finally {
                        setPdfLoading(false);
                    }
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
        <div style={{ minHeight: '100vh', background: 'var(--tb-body-bg)' }}>
            {/* Tabler-style page header */}
            <div className="page-header">
                <div style={{ minWidth: 0 }}>
                    <div className="page-pretitle">
                        <a
                            href="/"
                            onClick={(e) => { e.preventDefault(); navigate('/'); }}
                            style={{ color: 'inherit', textDecoration: 'none' }}
                        >
                            Home
                        </a>
                        <span style={{ margin: '0 6px', opacity: 0.5 }}>/</span>
                        {entityTitle}
                    </div>
                    <h1>{entityTitle}</h1>
                </div>
                <div className="page-actions">
                    <Button variant="outline" size="sm" onClick={() => handleExport('xlsx')} title="Export to Excel">
                        <FileSpreadsheet className="size-3.5" />
                        Excel
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => handleExport('pdf')} title="Export to PDF" disabled={pdfLoading}>
                        {pdfLoading ? <Loader2 className="size-3.5 animate-spin" /> : <FileText className="size-3.5" />}
                        {pdfLoading ? "Generating…" : "PDF"}
                    </Button>
                    {entityName === 'bill-of-entries' && (
                        <Button variant="outline" size="sm" onClick={handlePortExcelExport} title="Download port-wise BOE Excel">
                            <FileSpreadsheet className="size-3.5" />
                            Port Excel
                        </Button>
                    )}
                    {entityName === 'bill-of-entries' && (
                        <Button
                            variant="outline"
                            size="sm"
                            title="Update all empty product names in entire database"
                            onClick={async () => {
                                const confirmed = await confirmDangerousAction(
                                    'Bulk Update Product Names',
                                    'This will update product names for ALL BOEs with empty product_name in the entire database. This may take some time. Continue?'
                                );
                                if (!confirmed) return;
                                setLoading(true); setError("");
                                try {
                                    const response = await api.post(`bill-of-entries/bulk-update-product-names/`);
                                    setLoading(false);
                                    if (response.data.success) {
                                        toast.success(response.data.message || `Processed ${response.data.total} BOEs: ${response.data.updated} updated, ${response.data.skipped} skipped`);
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
                        >
                            <RefreshCw className="size-3.5" />
                            Fetch All Products
                        </Button>
                    )}
                    {canWrite && (
                        <Button asChild size="sm">
                            <Link
                                to={entityName === 'licenses' ? '/licenses/create' :
                                    entityName === 'allotments' ? '/allotments/create' :
                                    entityName === 'trades' ? '/trades/create' :
                                    `/masters/${entityName}/create`}
                                onClick={() => {
                                    saveFilterState(entityName, {
                                        filters: filterParams,
                                        pagination: { currentPage, pageSize },
                                        search: ''
                                    });
                                }}
                            >
                                <Plus className="size-3.5" />
                                Add New
                            </Link>
                        </Button>
                    )}
                </div>
            </div>

            {/* Error Display */}
            {error && (
                <div className="mb-3 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-[13px] text-destructive">
                    <span className="flex-1">{error}</span>
                    <button type="button" aria-label="Dismiss" onClick={() => setError("")} className="cursor-pointer opacity-70 hover:opacity-100">
                        <X className="size-4" />
                    </button>
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
            <div className="surface-card" style={{ marginTop: 16 }}>
                <div style={{ padding: '14px 16px' }}>
                    {/* BOE Card Layout */}
                    {entityName === 'bill-of-entries' && (
                        loading ? (
                            <div className="text-center py-5">
                                <span className="inline-block size-5 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" />
                                <div className="mt-2 text-muted-foreground">Loading Bill of Entries...</div>
                            </div>
                        ) : data.length === 0 ? (
                            <div className="empty-state">
                                <div className="empty-icon"><Inbox className="size-4" aria-hidden="true" /></div>
                                <div className="empty-title">No bill of entries found</div>
                                <div className="empty-sub">Try adjusting filters or create a new BOE.</div>
                            </div>
                        ) : (
                            <div>
                                {data.map(item => {
                                    const fmtInr = (val) => val ? `₹${Number(val).toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '—';
                                    const fmtQty = (val) => val ? Number(val).toLocaleString('en-IN', { maximumFractionDigits: 3 }) : '—';
                                    const detailRows = item.item_details || [];
                                    const disputeRows = detailRows.filter(r => r.is_dispute);
                                    const hasDispute = disputeRows.length > 0;
                                    const invoiceChip = canEditInvoice
                                        ? (editingInvoiceId === item.id
                                            ? (
                                                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4 }}>
                                                    <input
                                                        autoFocus
                                                        value={invoiceDraft}
                                                        onChange={e => setInvoiceDraft(e.target.value)}
                                                        onKeyDown={e => { if (e.key === 'Enter') saveInvoiceEdit(item.id); if (e.key === 'Escape') cancelInvoiceEdit(); }}
                                                        placeholder="Invoice number"
                                                        style={{ fontSize: '0.82rem', padding: '3px 8px', borderRadius: 6, border: '1px solid var(--success-color)', width: 160, outline: 'none' }}
                                                    />
                                                    <button type="button" onClick={() => saveInvoiceEdit(item.id)} disabled={invoiceSaving} style={{ fontSize: 12, padding: '3px 8px', borderRadius: 6, background: 'var(--success-color)', color: '#fff', border: 'none', cursor: 'pointer' }}>
                                                        {invoiceSaving ? '…' : 'Save'}
                                                    </button>
                                                    <button type="button" onClick={cancelInvoiceEdit} style={{ fontSize: 12, padding: '3px 7px', borderRadius: 6, background: 'var(--surface-sunken)', color: 'var(--text-secondary)', border: '1px solid var(--border-default)', cursor: 'pointer' }}>✕</button>
                                                </span>
                                            )
                                            : (
                                                <button
                                                    type="button"
                                                    onClick={() => startInvoiceEdit(item)}
                                                    title="Click to edit invoice number"
                                                    style={{ display: 'inline-flex', alignItems: 'center', gap: 4, fontSize: '0.82rem', color: 'var(--success-text)', background: 'var(--success-bg)', border: '1px solid var(--success-border)', padding: '3px 8px', borderRadius: 6, cursor: 'pointer', fontWeight: 500 }}
                                                >
                                                    {item.invoice_no
                                                        ? (<><Receipt className="size-4" aria-hidden="true" /> {item.invoice_no}</>)
                                                        : (<><PlusCircle className="size-4" aria-hidden="true" /> Add Invoice No</>)
                                                    }
                                                    <Pencil className="size-4" aria-hidden="true" />
                                                </button>
                                            ))
                                        : null;

                                    return (
                                        <EntityCard
                                            key={item.id}
                                            className={hasDispute ? 'is-dispute' : ''}
                                            accent={hasDispute ? 'danger' : 'primary'}
                                            title={item.bill_of_entry_number || '—'}
                                            headerChips={[
                                                item.bill_of_entry_date && { icon: 'calendar3', label: item.bill_of_entry_date },
                                                item.port_name           && { icon: 'geo-alt', label: item.port_name, tone: 'info' },
                                                item.company_name        && { icon: 'building', label: item.company_name, tone: 'primary' },
                                                hasDispute && {
                                                    icon: 'exclamation-triangle-fill',
                                                    label: `${disputeRows.length} Dispute${disputeRows.length > 1 ? 's' : ''}`,
                                                    tone: 'danger',
                                                },
                                            ].filter(Boolean)}
                                            statusBadges={[]}
                                            summary={[
                                                { label: 'CIF (INR)', value: fmtInr(item.total_inr) },
                                                { label: 'CIF (FC)',  value: item.total_fc ? Number(item.total_fc).toLocaleString('en-IN', { maximumFractionDigits: 2 }) : '—' },
                                                { label: 'Qty (MT)',  value: fmtQty(item.total_quantity) },
                                            ]}
                                            actions={[
                                                hasDispute && {
                                                    icon: 'check2-circle', title: 'Resolve Dispute', tone: 'danger',
                                                    onClick: async () => {
                                                        if (!window.confirm(`Resolve ${disputeRows.length} dispute row(s) on BOE ${item.bill_of_entry_number}? This clears the dispute flag on all flagged rows.`)) return;
                                                        try {
                                                            const response = await api.post(`bill-of-entries/${item.id}/resolve-dispute/`);
                                                            toast.success(response.data.message || 'Dispute resolved');
                                                            fetchData(currentPage, pageSize, filterParams);
                                                        } catch (err) {
                                                            toast.error(err.response?.data?.detail || err.response?.data?.message || 'Failed to resolve dispute');
                                                        }
                                                    }
                                                },
                                                { icon: 'file-earmark-text', title: 'Transfer Letter', tone: 'warning',
                                                    onClick: () => { setTransferLetterType('boe'); setTransferLetterEntityId(item.id); setShowTransferLetterModal(true); } },
                                                { icon: 'intersect', title: 'Merge BOE', tone: 'info',
                                                    onClick: () => openMergeModal(item) },
                                                (!item.product_name || item.product_name.trim() === '') && {
                                                    icon: 'arrow-repeat', title: 'Update Product Name', tone: 'info',
                                                    onClick: async () => {
                                                        if (!window.confirm(`Update product name for BOE ${item.bill_of_entry_number}?`)) return;
                                                        try {
                                                            const response = await api.post(`bill-of-entries/${item.id}/update-product-name/`);
                                                            toast.success(response.data.message || 'Product name updated');
                                                            fetchData(currentPage, pageSize, filterParams);
                                                        } catch (err) {
                                                            toast.error(err.response?.data?.message || 'Failed to update product name');
                                                        }
                                                    }
                                                },
                                                canWrite && { icon: 'pencil', title: 'Edit', tone: 'primary',
                                                    onClick: () => { saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' }); navigate(`/bill-of-entries/${item.id}/edit`); } },
                                                canWrite && { icon: 'trash', title: 'Delete', tone: 'danger', onClick: () => handleDelete(item) },
                                            ].filter(Boolean)}
                                            viewOpen={expandedBoeRows.has(item.id)}
                                            onView={() => toggleBoeRow(item.id)}
                                            detailLabel={detailRows.length ? `${detailRows.length} Item${detailRows.length !== 1 ? 's' : ''}` : 'Details'}
                                            detail={() => (
                                                <DetailTable
                                                    columns={[
                                                        { key: 'is_dispute', label: '', nowrap: true, width: 28,
                                                            render: (v, row) => row.is_dispute
                                                                ? <span title="Not found in latest ledger upload — dispute" style={{ color: 'var(--tb-danger)', fontSize: 14.5 }}><TriangleAlert className="size-4" aria-hidden="true" /></span>
                                                                : null },
                                                        { key: 'license_number',   label: 'License',   bold: true, nowrap: true,
                                                            render: (v, row) => v
                                                                ? <span style={{ color: row.is_dispute ? 'var(--tb-danger-text)' : 'var(--primary-color)' }}>{v}</span>
                                                                : '—' },
                                                        { key: 'item_description', label: 'Item',      muted: true },
                                                        { key: 'hs_code',          label: 'HS Code',   nowrap: true,
                                                            render: v => v ? <code>{v}</code> : '—' },
                                                        { key: 'qty',              label: 'Qty',       align: 'right', nowrap: true,
                                                            render: v => fmtQty(v) },
                                                        { key: 'cif_fc',           label: 'CIF (FC)',  align: 'right', nowrap: true,
                                                            render: v => v ? Number(v).toLocaleString('en-IN', { maximumFractionDigits: 2 }) : '—' },
                                                        { key: 'cif_inr',          label: 'CIF (INR)', align: 'right', nowrap: true, bold: true,
                                                            render: v => fmtInr(v) },
                                                    ]}
                                                    rows={detailRows}
                                                    rowStyle={row => row.is_dispute ? { background: 'var(--tb-danger-soft)' } : undefined}
                                                />
                                            )}
                                        >
                                            <div style={{ display: 'flex', alignItems: 'flex-start', gap: 24, flexWrap: 'wrap' }}>
                                                <div style={{ flex: 1, minWidth: 200 }}>
                                                    <div style={{ fontSize: '0.66rem', color: 'var(--text-tertiary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2 }}>Product</div>
                                                    <div style={{ fontSize: 14.5, color: 'var(--text-primary)', fontWeight: 500 }}>
                                                        {item.product_name || <span style={{ color: 'var(--text-tertiary)', fontStyle: 'italic' }}>No product name</span>}
                                                    </div>
                                                </div>
                                                {item.licenses && (
                                                    <div style={{ flex: 1, minWidth: 140 }}>
                                                        <div style={{ fontSize: '0.66rem', color: 'var(--text-tertiary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2 }}>Licenses</div>
                                                        <div style={{ fontSize: 13.5, color: 'var(--primary-color)', fontWeight: 500 }}>{item.licenses}</div>
                                                    </div>
                                                )}
                                                {invoiceChip && (
                                                    <div style={{ alignSelf: 'center' }}>
                                                        {invoiceChip}
                                                    </div>
                                                )}
                                            </div>
                                        </EntityCard>
                                    );
                                })}
                            </div>
                        )
                    )}

                    {/* Allotments Card Layout */}
                    {entityName === 'allotments' && (
                        loading ? (
                            <div className="text-center py-5">
                                <span className="inline-block size-5 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" />
                                <div className="mt-2 text-muted-foreground">Loading Allotments...</div>
                            </div>
                        ) : data.length === 0 ? (
                            <div className="empty-state">
                                <div className="empty-icon"><Inbox className="size-4" aria-hidden="true" /></div>
                                <div className="empty-title">No allotments found</div>
                                <div className="empty-sub">Try adjusting filters or create a new allotment.</div>
                            </div>
                        ) : (
                            <div>
                                {data.map(item => {
                                    const fmtInr = (val) => val ? `₹${Number(val).toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '—';
                                    const fmtQty = (val) => val ? Number(val).toLocaleString('en-IN', { maximumFractionDigits: 3 }) : '—';
                                    const detailRows = item.allotment_details || [];
                                    return (
                                        <EntityCard
                                            key={item.id}
                                            accent={item.is_boe ? 'success' : 'primary'}
                                            title={item.invoice || <span style={{ fontStyle: 'italic', color: 'var(--text-tertiary)', fontWeight: 400 }}>No Invoice</span>}
                                            headerChips={[
                                                item.estimated_arrival_date && { icon: 'calendar3', label: item.estimated_arrival_date },
                                                item.port_name           && { icon: 'geo-alt', label: item.port_name, tone: 'info' },
                                                item.company_name        && { icon: 'building', label: item.company_name, tone: 'primary' },
                                            ].filter(Boolean)}
                                            statusBadges={[
                                                item.is_boe      && { tone: 'success', label: 'BOE ✓' },
                                                item.is_approved && { tone: 'info',    label: 'Approved' },
                                            ].filter(Boolean)}
                                            summary={[
                                                { label: 'Req Qty',      value: fmtQty(item.required_quantity) },
                                                { label: 'Req Value',    value: fmtInr(item.required_value) },
                                                { label: 'Balanced Qty', value: fmtQty(item.balanced_quantity), tone: (item.balanced_quantity > 0 ? 'success' : undefined) },
                                            ]}
                                            actions={[
                                                canWrite && { icon: 'pencil', title: 'Edit', tone: 'primary',
                                                    onClick: () => { saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' }); navigate(`/allotments/${item.id}/edit`); } },
                                                canWrite && { icon: 'copy', title: 'Copy', tone: 'info',
                                                    onClick: async () => {
                                                        if (!window.confirm(`Create a copy of allotment ${item.invoice || 'this allotment'}?`)) return;
                                                        try {
                                                            const r = await api.post(`allotments/${item.id}/copy/`);
                                                            toast.success('Allotment copied. Opening in edit mode...');
                                                            saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' });
                                                            navigate(`/allotments/${r.data.id}/edit`);
                                                        } catch (err) { toast.error(err.response?.data?.error || 'Failed to copy'); }
                                                    } },
                                                canWrite && { icon: 'box-arrow-in-down', title: 'Allocate', tone: 'success',
                                                    onClick: () => { saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' }); navigate(`/allotments/${item.id}/allocate`); } },
                                                { icon: 'file-pdf', title: 'Preview PDF', tone: 'warning',
                                                    onClick: async () => {
                                                        try {
                                                            const r = await api.get(`allotment-actions/${item.id}/generate-pdf/`, { responseType: 'blob', headers: { Authorization: `Bearer ${localStorage.getItem('access')}` } });
                                                            openPdfPreview(r.data, `${item.invoice_number || item.id}.pdf`);
                                                        } catch (err) { toast.error(err.response?.data?.error || 'Failed to generate PDF'); }
                                                    } },
                                                { icon: 'download', title: 'Download',
                                                    onClick: async () => {
                                                        try {
                                                            const r = await api.get(`allotment-actions/${item.id}/generate-pdf/`, { responseType: 'blob', headers: { Authorization: `Bearer ${localStorage.getItem('access')}` } });
                                                            const url = window.URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }));
                                                            const a = document.createElement('a');
                                                            a.href = url;
                                                            a.download = `Allotment-${item.invoice || item.id}.pdf`;
                                                            document.body.appendChild(a); a.click(); a.remove();
                                                            setTimeout(() => window.URL.revokeObjectURL(url), 10000);
                                                        } catch (err) { toast.error(err.response?.data?.error || 'Failed to download PDF'); }
                                                    } },
                                                canWrite && { icon: 'trash', title: 'Delete', tone: 'danger', onClick: () => handleDelete(item) },
                                            ].filter(Boolean)}
                                            viewOpen={expandedAllotments.has(item.id)}
                                            onView={() => toggleAllotment(item.id)}
                                            detailLabel={detailRows.length ? `${detailRows.length} Item${detailRows.length !== 1 ? 's' : ''}` : 'Details'}
                                            detail={() => (
                                                <DetailTable
                                                    columns={[
                                                        { key: 'license_number',     label: 'License',     bold: true, nowrap: true,
                                                            render: v => v ? <span style={{ color: 'var(--primary-color)' }}>{v}</span> : '—' },
                                                        { key: 'serial_number',      label: 'Sl#',         align: 'right', nowrap: true },
                                                        { key: 'product_description', label: 'Item',       muted: true },
                                                        { key: 'qty',                 label: 'Qty',        align: 'right', nowrap: true,
                                                            render: v => fmtQty(v) },
                                                        { key: 'cif_fc',              label: 'CIF (FC)',   align: 'right', nowrap: true,
                                                            render: v => v ? Number(v).toLocaleString('en-IN', { maximumFractionDigits: 2 }) : '—' },
                                                        { key: 'cif_inr',             label: 'CIF (INR)',  align: 'right', nowrap: true, bold: true,
                                                            render: v => fmtInr(v) },
                                                    ]}
                                                    rows={detailRows}
                                                    emptyMessage="No items have been allotted yet."
                                                />
                                            )}
                                        >
                                            {(item.item_name || item.dfia_list) && (
                                                <div style={{ display: 'flex', alignItems: 'flex-start', gap: 24, flexWrap: 'wrap' }}>
                                                    <div style={{ flex: 1, minWidth: 200 }}>
                                                        <div style={{ fontSize: '0.66rem', color: 'var(--text-tertiary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2 }}>Item</div>
                                                        <div style={{ fontSize: 14.5, color: 'var(--text-primary)', fontWeight: 500 }}>
                                                            {item.item_name || <span style={{ color: 'var(--text-tertiary)', fontStyle: 'italic' }}>No item name</span>}
                                                        </div>
                                                    </div>
                                                    {item.dfia_list && (
                                                        <div style={{ flex: 1, minWidth: 140 }}>
                                                            <div style={{ fontSize: '0.66rem', color: 'var(--text-tertiary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2 }}>Licenses</div>
                                                            <div style={{ fontSize: 13.5, color: 'var(--primary-color)', fontWeight: 500 }}>{item.dfia_list}</div>
                                                        </div>
                                                    )}
                                                </div>
                                            )}
                                        </EntityCard>
                                    );
                                })}
                            </div>
                        )
                    )}

                    {/* Licenses Card Layout */}
                    {entityName === 'licenses' && (
                        loading ? (
                            <div className="text-center py-5">
                                <span className="inline-block size-5 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" />
                                <div className="mt-2 text-muted-foreground">Loading Licenses...</div>
                            </div>
                        ) : data.length === 0 ? (
                            <div className="text-center py-5 text-muted-foreground">
                                <Inbox className="size-4" aria-hidden="true" />
                                <div className="mt-2">No licenses found</div>
                            </div>
                        ) : (
                            <div>
                                {data.map(item => {
                                    const fmtInr = (val) => val ? `₹${Number(val).toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '-';
                                    const parseIndianDate = (s) => { if (!s) return null; const p = s.split('-'); return p.length === 3 ? new Date(p[2], p[1]-1, p[0]) : null; };
                                    const isExpired = item.license_expiry_date && parseIndianDate(item.license_expiry_date) < new Date();
                                    const statusColor = item.purchase_status_code === 'E1' ? { bg: 'var(--tb-brand-100)', text: 'var(--tb-brand-hover)' }
                                        : item.purchase_status_code === 'E5' ? { bg: 'var(--tb-success-soft)', text: 'var(--tb-success-text)' }
                                        : { bg: 'var(--tb-gray-100)', text: 'var(--tb-text-secondary)' };
                                    return (
                                        <div key={item.id} style={{
                                            display: 'block',
                                            background: 'var(--tb-card-bg)',
                                            border: `1px solid ${isExpired ? 'var(--tb-danger-border)' : 'var(--tb-border-soft)'}`,
                                            borderLeft: `4px solid ${isExpired ? 'var(--tb-danger)' : 'var(--tb-brand)'}`,
                                            borderRadius: 'var(--tb-r-md)',
                                            marginBottom: '10px',
                                            overflow: 'hidden',
                                            boxShadow: '0 1px 4px rgba(0,0,0,0.06)',
                                        }}>
                                            {/* Row 1: Identity */}
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 14px', background: 'var(--tb-sunken)', borderBottom: '1px solid #e2e8f0', flexWrap: 'wrap' }}>
                                                <span style={{ fontWeight: '700', fontSize: 16, color: 'var(--tb-brand-active)', marginRight: '4px' }}>
                                                    {item.license_number || '-'}
                                                </span>
                                                {item.license_date && (
                                                    <span style={{ fontSize: 12.5, color: 'var(--tb-text-secondary)', background: 'var(--tb-gray-100)', padding: '2px 8px', borderRadius: 'var(--tb-r-sm)' }}>
                                                        <Calendar className="size-4" aria-hidden="true" />{item.license_date}
                                                    </span>
                                                )}
                                                {item.license_expiry_date && (
                                                    <span style={{ fontSize: 12.5, color: isExpired ? 'var(--tb-danger-text)' : 'var(--tb-text-secondary)', background: isExpired ? 'var(--tb-danger-soft)' : 'var(--tb-gray-100)', padding: '2px 8px', borderRadius: 'var(--tb-r-sm)' }}>
                                                        <CalendarX className="size-4" aria-hidden="true" />Exp: {item.license_expiry_date}
                                                    </span>
                                                )}
                                                {item.ledger_date && (
                                                    <span style={{ fontSize: 12.5, color: 'var(--tb-success-text)', background: 'var(--tb-success-soft)', padding: '2px 8px', borderRadius: 'var(--tb-r-sm)' }}>
                                                        <BookCheck className="size-4" aria-hidden="true" />Ledger: {item.ledger_date}
                                                    </span>
                                                )}
                                                {item.port_name && (
                                                    <span style={{ fontSize: 12.5, color: 'var(--tb-info-text)', background: 'var(--tb-info-soft)', padding: '2px 8px', borderRadius: 'var(--tb-r-sm)', fontWeight: '500' }}>
                                                        <MapPin className="size-4" aria-hidden="true" />{item.port_name}
                                                    </span>
                                                )}
                                                {item.exporter_name && (
                                                    <span style={{ fontSize: 12.5, color: 'var(--accent-color)', background: 'var(--tb-sunken)', padding: '2px 8px', borderRadius: 'var(--tb-r-sm)', fontWeight: '500' }}>
                                                        <Building2 className="size-4" aria-hidden="true" />{item.exporter_name}
                                                    </span>
                                                )}
                                                {item.exporter_iec && (
                                                    <span style={{ fontSize: 12.5, color: 'var(--tb-warning-text)', background: 'var(--tb-warning-soft)', padding: '2px 8px', borderRadius: 'var(--tb-r-sm)', fontWeight: '500' }}>
                                                        <Fingerprint className="size-4" aria-hidden="true" />IEC: {item.exporter_iec}
                                                    </span>
                                                )}
                                                {item.purchase_status_label && (
                                                    <span style={{ fontSize: 12, color: statusColor.text, background: statusColor.bg, padding: '2px 8px', borderRadius: 'var(--tb-r-sm)', fontWeight: '600' }}>
                                                        {item.purchase_status_label}
                                                    </span>
                                                )}
                                                {(item.has_tl || item.has_copy) && (
                                                    <button onClick={async (e) => {
                                                        e.stopPropagation();
                                                        try {
                                                            const r = await api.get(`licenses/${item.id}/merged-documents/`, { responseType: 'blob', headers: { Authorization: `Bearer ${localStorage.getItem('access')}` } });
                                                            openPdfPreview(r.data, `${item.license_number || item.id}-copy.pdf`);
                                                        } catch (err) {
                                                            if (err.response?.status === 404) {
                                                                toast.warning('Document files are not available on this server. The files may not have been uploaded yet.');
                                                            } else {
                                                                toast.error(err.response?.data ? String(err.response.data).slice(0, 200) : 'Failed to load documents');
                                                            }
                                                        }
                                                    }} style={{ fontSize: 11, color: 'var(--tb-success)', background: 'var(--tb-success-soft)', padding: '2px 6px', borderRadius: 'var(--tb-r-sm)', fontWeight: '500', border: 'none', cursor: 'pointer' }}>
                                                        Copy
                                                    </button>
                                                )}
                                                {item.has_condition_sheet && (
                                                    <span title="Condition sheet parsed from license copy" style={{ fontSize: 11, color: 'var(--tb-brand-active)', background: 'var(--tb-brand-100)', padding: '2px 8px', borderRadius: 'var(--tb-r-sm)', fontWeight: '600' }}>
                                                        <FileText className="size-4" aria-hidden="true" />Cond. Sheet
                                                    </span>
                                                )}
                                            </div>

                                            {/* Row 2: Norm class + Transfer */}
                                            <div style={{ padding: '10px 14px', background: 'var(--tb-card-bg)', borderBottom: '1px solid #e2e8f0' }}>
                                                <div style={{ display: 'flex', alignItems: 'flex-start', gap: '16px', flexWrap: 'wrap' }}>
                                                    {item.get_norm_class && (
                                                        <div style={{ minWidth: '120px' }}>
                                                            <div style={{ fontSize: 11, color: 'var(--tb-text-tertiary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '3px' }}>Norm Class</div>
                                                            <div style={{ fontSize: 14, color: 'var(--tb-text)', fontWeight: '500' }}>{item.get_norm_class}</div>
                                                        </div>
                                                    )}
                                                    {item.latest_transfer && (
                                                        <div style={{ flex: 1, minWidth: '160px' }}>
                                                            <div style={{ fontSize: 11, color: 'var(--tb-text-tertiary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '3px' }}>Latest Transfer</div>
                                                            <div style={{ fontSize: '0.82rem', color: 'var(--tb-gray-700)' }}>{item.latest_transfer}</div>
                                                        </div>
                                                    )}
                                                    {!item.get_norm_class && !item.latest_transfer && (
                                                        <div style={{ fontSize: '0.82rem', color: 'var(--tb-text-tertiary)', fontStyle: 'italic' }}>No additional details</div>
                                                    )}
                                                </div>
                                            </div>

                                            {/* Row 3: Stats + Actions */}
                                            <div style={{ display: 'flex', alignItems: 'center', padding: '8px 14px', background: 'var(--tb-sunken)', gap: '8px', flexWrap: 'wrap' }}>
                                                <div style={{ display: 'flex', gap: '20px', flex: 1, flexWrap: 'wrap' }}>
                                                    <div>
                                                        <div style={{ fontSize: '0.67rem', color: 'var(--tb-text-tertiary)', fontWeight: '600', textTransform: 'uppercase' }}>Balance CIF</div>
                                                        <div style={{ fontSize: 14, color: 'var(--tb-text)', fontWeight: '700' }}>{fmtInr(item.get_balance_cif)}</div>
                                                    </div>
                                                </div>
                                                <div style={{ display: 'flex', gap: '6px', flexShrink: 0 }}>
                                                    {canWrite && <button onClick={() => { saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' }); navigate(`/licenses/${item.id}/edit`); }} title="Edit" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: 12, color: 'var(--tb-brand-hover)', background: 'var(--tb-brand-50)', border: '1px solid #93c5fd', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                        <Pencil className="size-4" aria-hidden="true" />
                                                    </button>}
                                                    <button onClick={() => { setSelectedLicenseId(item.id); setShowBalanceModal(true); }} title="View Balance" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: 12, color: 'var(--tb-info-text)', background: 'var(--tb-info-soft)', border: '1px solid #38bdf8', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                        <Eye className="size-4" aria-hidden="true" />
                                                    </button>
                                                    <button
                                                        onClick={() => { setOwnershipLicense({ id: item.id, number: item.license_number }); setShowOwnershipModal(true); }}
                                                        title="View ownership & transfers"
                                                        style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: 12, color: 'var(--tb-brand-active)', background: 'var(--tb-brand-50)', border: '1px solid #a5b4fc', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                        <Network className="size-4" aria-hidden="true" />
                                                    </button>
                                                    {canWrite && <button
                                                        disabled={fetchingOwnershipIds.has(item.id)}
                                                        onClick={async () => {
                                                            setFetchingOwnershipIds(prev => { const n = new Set(prev); n.add(item.id); return n; });
                                                            try {
                                                                const r = await api.post(`license-actions/${item.id}/fetch-ownership/`);
                                                                const owner = r.data?.current_owner?.name || '—';
                                                                toast.success(`Ownership updated: ${owner} (${r.data?.transfers_count ?? 0} transfers)`);
                                                                fetchData(currentPage, pageSize, filterParams);
                                                            } catch (err) {
                                                                toast.error(err?.response?.data?.error || err?.message || 'Failed to fetch ownership');
                                                            } finally {
                                                                setFetchingOwnershipIds(prev => { const n = new Set(prev); n.delete(item.id); return n; });
                                                            }
                                                        }}
                                                        title="Fetch ownership from DGFT"
                                                        style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: 12, color: 'var(--accent-color)', background: 'var(--tb-sunken)', border: '1px solid #c4b5fd', borderRadius: '5px', padding: '4px 9px', cursor: fetchingOwnershipIds.has(item.id) ? 'wait' : 'pointer', opacity: fetchingOwnershipIds.has(item.id) ? 0.6 : 1 }}>
                                                        <span className={fetchingOwnershipIds.has(item.id) ? 'inline-block animate-spin' : ''}>{fetchingOwnershipIds.has(item.id) ? <RefreshCw className="size-4" /> : <CloudDownload className="size-4" />}</span>
                                                    </button>}
                                                    <button onClick={async () => {
                                                        try {
                                                            const r = await api.get(`licenses/${item.id}/balance-pdf/`, { responseType: 'blob', headers: { Authorization: `Bearer ${localStorage.getItem('access')}` } });
                                                            openPdfPreview(r.data, `${item.license_number || item.id}-balance.pdf`);
                                                        } catch (err) { toast.error(err?.response?.data?.error || 'Failed to generate PDF'); }
                                                    }} title="Download PDF" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: 12, color: 'var(--tb-warning-text)', background: 'var(--tb-warning-soft)', border: '1px solid var(--tb-warning-border)', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                        <FileText className="size-4" aria-hidden="true" />
                                                    </button>
                                                    <button onClick={async () => {
                                                        try {
                                                            const r = await api.get(`licenses/${item.id}/balance-excel/`, { responseType: 'blob', headers: { Authorization: `Bearer ${localStorage.getItem('access')}` } });
                                                            const blob = new Blob([r.data], { type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet' });
                                                            const url = window.URL.createObjectURL(blob);
                                                            const a = document.createElement('a'); a.href = url; a.download = `${item.license_number || item.id}-balance.xlsx`; document.body.appendChild(a); a.click(); document.body.removeChild(a);
                                                            setTimeout(() => window.URL.revokeObjectURL(url), 10000);
                                                        } catch (err) { toast.error(err?.response?.data?.error || 'Failed to generate Excel'); }
                                                    }} title="Download Excel" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: 12, color: 'var(--tb-success-text)', background: 'var(--tb-success-soft)', border: '1px solid #86efac', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                        <FileSpreadsheet className="size-4" aria-hidden="true" />
                                                    </button>
                                                    {canWrite && <button onClick={() => handleDelete(item)} title="Delete" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: 12, color: 'var(--tb-danger-text)', background: 'var(--tb-danger-soft)', border: '1px solid #fca5a5', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                        <Trash2 className="size-4" aria-hidden="true" />
                                                    </button>}
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
                            <div className="text-center py-5"><span className="inline-block size-5 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" /><div className="mt-2 text-muted-foreground">Loading Trades...</div></div>
                        ) : data.length === 0 ? (
                            <div className="text-center py-5 text-muted-foreground"><Inbox className="size-4" aria-hidden="true" /><div className="mt-2">No trades found</div></div>
                        ) : (() => {
                            const fmtInr = (val) => val ? `₹${Number(val).toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '-';

                            const renderTradeCard = (item) => {
                                const directionTone =
                                    item.direction === 'SALE'             ? 'success'
                                  : item.direction === 'PURCHASE'         ? 'info'
                                  : item.direction === 'COMMISSION_SALE'  ? 'warning'
                                  :                                          'primary';
                                const accent =
                                    item.direction === 'SALE'             ? 'success'
                                  : item.direction === 'PURCHASE'         ? 'info'
                                  : item.direction === 'COMMISSION_SALE'  ? 'warning'
                                  :                                          'primary';
                                const isLinked = !!(item.linked_trade_id || item.linked_trade_info);
                                const detailRows = item.lines || [];
                                return (
                                    <EntityCard
                                        key={item.id}
                                        accent={accent}
                                        title={item.invoice_number || <span style={{ fontStyle: 'italic', color: 'var(--text-tertiary)', fontWeight: 400 }}>No Invoice</span>}
                                        headerChips={[
                                            { tone: directionTone, label: item.direction_label || item.direction },
                                            item.license_type_label && { label: item.license_type_label },
                                            item.invoice_date       && { icon: 'calendar3', label: item.invoice_date },
                                        ].filter(Boolean)}
                                        summary={[
                                            { label: 'Total',     value: fmtInr(item.total_amount) },
                                            { label: 'Paid/Rcvd', value: fmtInr(item.paid_or_received), tone: 'success' },
                                            { label: 'Due',       value: fmtInr(item.due_amount), tone: item.due_amount > 0 ? 'danger' : undefined },
                                        ]}
                                        actions={[
                                            { icon: 'file-earmark-text', title: 'Transfer Letter', tone: 'warning',
                                                onClick: () => { setTransferLetterType('trade'); setTransferLetterEntityId(item.id); setShowTransferLetterModal(true); },
                                                children: 'TL' },
                                            ...(item.direction === 'SALE' ? [
                                                { icon: 'file-pdf', title: 'Invoice (With Sign)', tone: 'success',
                                                    onClick: async () => {
                                                        try {
                                                            const r = await api.get(`trades/${item.id}/generate-bill-of-supply/`, { params: { include_signature: true }, responseType: 'blob' });
                                                            const url = window.URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }));
                                                            const a = document.createElement('a'); a.href = url; a.download = `Bill_of_Supply_${item.invoice_number}_with_sign.pdf`; document.body.appendChild(a); a.click(); a.remove();
                                                            window.URL.revokeObjectURL(url);
                                                        } catch { toast.error('Failed to generate invoice'); }
                                                    } },
                                                { icon: 'file-pdf', title: 'Invoice (Without Sign)', tone: 'warning',
                                                    onClick: async () => {
                                                        try {
                                                            const r = await api.get(`trades/${item.id}/generate-bill-of-supply/`, { params: { include_signature: false }, responseType: 'blob' });
                                                            const url = window.URL.createObjectURL(new Blob([r.data], { type: 'application/pdf' }));
                                                            const a = document.createElement('a'); a.href = url; a.download = `Bill_of_Supply_${item.invoice_number}_without_sign.pdf`; document.body.appendChild(a); a.click(); a.remove();
                                                            window.URL.revokeObjectURL(url);
                                                        } catch { toast.error('Failed to generate invoice'); }
                                                    } },
                                            ] : []),
                                            canWrite && item.direction === 'PURCHASE' && !isLinked && {
                                                icon: 'arrow-left-right', title: 'Copy to Sale', tone: 'info',
                                                onClick: async () => {
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
                                                }
                                            },
                                            canWrite && !isLinked && { icon: 'link-45deg', title: 'Link to existing trade', tone: 'primary',
                                                onClick: () => openLinkModal(item) },
                                            canWrite && { icon: 'pencil-fill', title: 'Edit', tone: 'primary',
                                                onClick: () => { saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' }); navigate(`/trades/${item.id}/edit`); } },
                                            canWrite && { icon: 'trash', title: 'Delete', tone: 'danger', onClick: () => handleDelete(item) },
                                        ].filter(Boolean)}
                                        viewOpen={expandedTrades.has(item.id)}
                                        onView={() => toggleTrade(item.id)}
                                        detailLabel={detailRows.length ? `${detailRows.length} Line${detailRows.length !== 1 ? 's' : ''}` : 'Details'}
                                        detail={() => (
                                            <DetailTable
                                                columns={[
                                                    { key: 'sr_number_label', label: 'Sr#',        nowrap: true,
                                                        render: (v, row) => v || (row.sr_number != null ? String(row.sr_number) : '—') },
                                                    { key: 'description',     label: 'Description', muted: true },
                                                    { key: 'hsn_code',        label: 'HSN',         nowrap: true,
                                                        render: v => v ? <code>{v}</code> : '—' },
                                                    { key: 'qty_kg',          label: 'Qty (KG)',   align: 'right', nowrap: true,
                                                        render: v => v ? Number(v).toLocaleString('en-IN', { maximumFractionDigits: 3 }) : '—' },
                                                    { key: 'cif_fc',          label: 'CIF FC $',   align: 'right', nowrap: true,
                                                        render: v => v ? `$${Number(v).toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : '—' },
                                                    { key: 'cif_inr',         label: 'CIF INR',    align: 'right', nowrap: true,
                                                        render: v => v ? fmtInr(v) : '—' },
                                                    { key: 'amount_inr',      label: 'Amount',     align: 'right', nowrap: true, bold: true,
                                                        render: v => fmtInr(v) },
                                                ]}
                                                rows={detailRows}
                                                emptyMessage="No trade lines."
                                            />
                                        )}
                                    >
                                        <div style={{ display: 'flex', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
                                            <div style={{ display: 'flex', alignItems: 'center', gap: 12, flex: 1, minWidth: 220 }}>
                                                <div>
                                                    <div style={{ fontSize: '0.66rem', color: 'var(--text-tertiary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2 }}>From</div>
                                                    <div style={{ fontSize: 14.5, color: 'var(--text-primary)', fontWeight: 500 }}>{item.from_company_label || '—'}</div>
                                                </div>
                                                <ArrowRight className="size-4" aria-hidden="true" />
                                                <div>
                                                    <div style={{ fontSize: '0.66rem', color: 'var(--text-tertiary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2 }}>To</div>
                                                    <div style={{ fontSize: 14.5, color: 'var(--text-primary)', fontWeight: 500 }}>{item.to_company_label || '—'}</div>
                                                </div>
                                            </div>
                                            {item.boe_label && (
                                                <div style={{ minWidth: 100 }}>
                                                    <div style={{ fontSize: '0.66rem', color: 'var(--text-tertiary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2 }}>BOE</div>
                                                    <div style={{ fontSize: 13.5, color: 'var(--primary-color)', fontWeight: 500 }}>{item.boe_label}</div>
                                                </div>
                                            )}
                                            {item.incentive_license && (
                                                <div style={{ minWidth: 100 }}>
                                                    <div style={{ fontSize: '0.66rem', color: 'var(--text-tertiary)', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 2 }}>Incentive Lic</div>
                                                    <div style={{ fontSize: 13.5, color: 'var(--success-text)', fontWeight: 500 }}>{item.incentive_license}</div>
                                                </div>
                                            )}
                                        </div>
                                    </EntityCard>
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
                                            <div key={pairKey} style={{ border: '1px solid #a5b4fc', borderLeft: '4px solid #6366f1', borderRadius: 'var(--tb-r-md)', marginBottom: '10px', overflow: 'hidden', boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
                                                <div
                                                    style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 14px', background: 'var(--tb-brand-50)', cursor: 'pointer', flexWrap: 'wrap' }}
                                                    onClick={() => togglePair(pairKey)}
                                                >
                                                    <span style={{ fontSize: 12, fontWeight: '700', color: 'var(--tb-success-text)', background: 'var(--tb-success-soft)', padding: '2px 8px', borderRadius: 'var(--tb-r-sm)' }}>Sale</span>
                                                    <Link className="size-4" aria-hidden="true" />
                                                    <span style={{ fontSize: 12, fontWeight: '700', color: 'var(--tb-brand-hover)', background: 'var(--tb-brand-100)', padding: '2px 8px', borderRadius: 'var(--tb-r-sm)' }}>Purchase</span>
                                                    <span style={{ fontSize: '0.82rem', color: 'var(--tb-brand)', fontWeight: '600', flex: 1 }}>{companies}</span>
                                                    <span style={{ fontSize: 12.5, color: 'var(--tb-text-secondary)' }}>
                                                        {sale.invoice_date || ''}
                                                    </span>
                                                    <span style={{ fontSize: 12.5, color: 'var(--tb-text-secondary)' }}>
                                                        Sale: {fmtInr(sale.total_amount)} · Purchase: {fmtInr(purchase.total_amount)}
                                                    </span>
                                                    <ChevronDown className="size-4 transition-transform" style={{ color: 'var(--tb-brand)', transform: isExpanded ? 'rotate(180deg)' : 'rotate(0deg)' }} />
                                                </div>
                                                {isExpanded && (
                                                    <div style={{ padding: '8px', background: 'var(--tb-sunken)', display: 'flex', flexDirection: 'column', gap: '8px' }}>
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
                            <div className="text-center py-5"><span className="inline-block size-5 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" /><div className="mt-2 text-muted-foreground">Loading Incentive Licenses...</div></div>
                        ) : data.length === 0 ? (
                            <div className="text-center py-5 text-muted-foreground"><Inbox className="size-4" aria-hidden="true" /><div className="mt-2">No incentive licenses found</div></div>
                        ) : (
                            <div>
                                {data.map(item => {
                                    const fmtInr = (val) => val ? `₹${Number(val).toLocaleString('en-IN', { maximumFractionDigits: 0 })}` : '-';
                                    const parseIndianDate = (s) => { if (!s) return null; const p = s.split('-'); return p.length === 3 ? new Date(p[2], p[1]-1, p[0]) : null; };
                                    const isExpired = item.license_expiry_date && parseIndianDate(item.license_expiry_date) < new Date();
                                    const soldStyle = item.sold_status === 'YES' ? { border: 'var(--tb-danger-border)', left: 'var(--tb-danger)', badge: 'var(--tb-danger-soft)', badgeText: 'var(--tb-danger-text)', label: 'Sold' }
                                        : item.sold_status === 'PARTIAL' ? { border: 'var(--tb-warning-border)', left: 'var(--tb-warning)', badge: 'var(--tb-warning-soft)', badgeText: 'var(--tb-warning-text)', label: 'Partial' }
                                        : { border: 'var(--tb-success-border)', left: 'var(--tb-success)', badge: 'var(--tb-success-soft)', badgeText: 'var(--tb-success-text)', label: 'Available' };
                                    return (
                                        <div key={item.id} style={{ display: 'block', background: 'var(--tb-card-bg)', border: `1px solid ${soldStyle.border}`, borderLeft: `4px solid ${soldStyle.left}`, borderRadius: 'var(--tb-r-md)', marginBottom: '10px', overflow: 'hidden', boxShadow: '0 1px 4px rgba(0,0,0,0.06)' }}>
                                            {/* Row 1: Identity */}
                                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px 14px', background: 'var(--tb-sunken)', borderBottom: '1px solid #e2e8f0', flexWrap: 'wrap' }}>
                                                <span style={{ fontWeight: '700', fontSize: 16, color: 'var(--tb-brand-active)', marginRight: '4px' }}>{item.license_number || '-'}</span>
                                                {item.license_type && (
                                                    <span style={{ fontSize: 12, color: 'var(--tb-text-secondary)', background: 'var(--tb-gray-100)', padding: '2px 8px', borderRadius: 'var(--tb-r-sm)', fontWeight: '500' }}>{item.license_type}</span>
                                                )}
                                                {item.license_date && (
                                                    <span style={{ fontSize: 12.5, color: 'var(--tb-text-secondary)', background: 'var(--tb-gray-100)', padding: '2px 8px', borderRadius: 'var(--tb-r-sm)' }}>
                                                        <Calendar className="size-4" aria-hidden="true" />{item.license_date}
                                                    </span>
                                                )}
                                                {item.license_expiry_date && (
                                                    <span style={{ fontSize: 12.5, color: isExpired ? 'var(--tb-danger-text)' : 'var(--tb-text-secondary)', background: isExpired ? 'var(--tb-danger-soft)' : 'var(--tb-gray-100)', padding: '2px 8px', borderRadius: 'var(--tb-r-sm)' }}>
                                                        <CalendarX className="size-4" aria-hidden="true" />Exp: {item.license_expiry_date}
                                                    </span>
                                                )}
                                                {item.port_name && (
                                                    <span style={{ fontSize: 12.5, color: 'var(--tb-info-text)', background: 'var(--tb-info-soft)', padding: '2px 8px', borderRadius: 'var(--tb-r-sm)', fontWeight: '500' }}>
                                                        <MapPin className="size-4" aria-hidden="true" />{item.port_name}
                                                    </span>
                                                )}
                                                {item.exporter_name && (
                                                    <span style={{ fontSize: 12.5, color: 'var(--accent-color)', background: 'var(--tb-sunken)', padding: '2px 8px', borderRadius: 'var(--tb-r-sm)', fontWeight: '500' }}>
                                                        <Building2 className="size-4" aria-hidden="true" />{item.exporter_name}
                                                    </span>
                                                )}
                                                {item.exporter_iec && (
                                                    <span style={{ fontSize: 12.5, color: 'var(--tb-warning-text)', background: 'var(--tb-warning-soft)', padding: '2px 8px', borderRadius: 'var(--tb-r-sm)', fontWeight: '500' }}>
                                                        <Fingerprint className="size-4" aria-hidden="true" />IEC: {item.exporter_iec}
                                                    </span>
                                                )}
                                                <span style={{ fontSize: 12, color: soldStyle.badgeText, background: soldStyle.badge, padding: '2px 8px', borderRadius: 'var(--tb-r-sm)', fontWeight: '600' }}>
                                                    {soldStyle.label}
                                                </span>
                                                {!item.is_active && (
                                                    <span style={{ fontSize: 11, color: 'var(--tb-text-secondary)', background: 'var(--tb-gray-100)', padding: '2px 6px', borderRadius: 'var(--tb-r-sm)' }}>Inactive</span>
                                                )}
                                            </div>

                                            {/* Row 3: Stats + Actions */}
                                            <div style={{ display: 'flex', alignItems: 'center', padding: '8px 14px', background: 'var(--tb-sunken)', gap: '8px', flexWrap: 'wrap' }}>
                                                <div style={{ display: 'flex', gap: '20px', flex: 1, flexWrap: 'wrap' }}>
                                                    <div><div style={{ fontSize: '0.67rem', color: 'var(--tb-text-tertiary)', fontWeight: '600', textTransform: 'uppercase' }}>License Value</div><div style={{ fontSize: 14, color: 'var(--tb-text)', fontWeight: '700' }}>{fmtInr(item.license_value)}</div></div>
                                                    <div><div style={{ fontSize: '0.67rem', color: 'var(--tb-text-tertiary)', fontWeight: '600', textTransform: 'uppercase' }}>Sold Value</div><div style={{ fontSize: 14, color: 'var(--tb-danger-text)', fontWeight: '600' }}>{fmtInr(item.sold_value)}</div></div>
                                                    <div><div style={{ fontSize: '0.67rem', color: 'var(--tb-text-tertiary)', fontWeight: '600', textTransform: 'uppercase' }}>Balance</div><div style={{ fontSize: 14, color: item.balance_value > 0 ? 'var(--tb-success)' : 'var(--tb-text-tertiary)', fontWeight: '600' }}>{fmtInr(item.balance_value)}</div></div>
                                                </div>
                                                <div style={{ display: 'flex', gap: '6px', flexShrink: 0 }}>
                                                    {canWrite && <button onClick={() => { saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' }); navigate(`/incentive-licenses/${item.id}/edit`); }} title="Edit" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: 12, color: 'var(--tb-brand-hover)', background: 'var(--tb-brand-50)', border: '1px solid #93c5fd', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                        <Pencil className="size-4" aria-hidden="true" />
                                                    </button>}
                                                    {canWrite && <button onClick={() => handleDelete(item)} title="Delete" style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: 12, color: 'var(--tb-danger-text)', background: 'var(--tb-danger-soft)', border: '1px solid #fca5a5', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}>
                                                        <Trash2 className="size-4" aria-hidden="true" />
                                                    </button>}
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
                                    icon: 'FileText',
                                    className: 'btn btn-outline-info',
                                    onClick: (item) => {
                                        setTransferLetterType('trade');
                                        setTransferLetterEntityId(item.id);
                                        setShowTransferLetterModal(true);
                                    }
                                },
                                {
                                    label: 'Invoice (With Sign)',
                                    icon: 'FileText',
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
                                    icon: 'FileText',
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
                                    icon: 'ArrowLeftRight',
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
                                    icon: 'Eye',
                                    className: 'btn btn-outline-info',
                                    onClick: (item) => {
                                        setSelectedLicenseId(item.id);
                                        setShowBalanceModal(true);
                                    }
                                },
                                {
                                    label: 'Ledger',
                                    icon: 'FileText',
                                    className: 'btn btn-outline-primary',
                                    onClick: async (item) => {
                                        try {
                                            const response = await api.get(`license-actions/${item.id}/download-ledger/`, {
                                                responseType: 'blob',
                                                headers: { Authorization: `Bearer ${localStorage.getItem('access')}` }
                                            });
                                            openPdfPreview(response.data, `${item.license_number || item.id}-ledger.pdf`);
                                        } catch (err) {
                                            toast.error(err?.response?.data?.error || 'Failed to generate ledger PDF');
                                        }
                                    }
                                }
                            ] : entityName === 'allotments' ? [
                                {
                                    label: 'Edit',
                                    icon: 'Pencil',
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
                                    icon: 'Copy',
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
                                    icon: 'LogIn',
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
                                    icon: 'Eye',
                                    className: 'btn btn-outline-warning',
                                    onClick: async (item) => {
                                        try {
                                            const response = await api.get(`allotment-actions/${item.id}/generate-pdf/`, {
                                                responseType: 'blob',
                                                headers: { Authorization: `Bearer ${localStorage.getItem('access')}` }
                                            });
                                            openPdfPreview(response.data, `${item.invoice_number || item.id}.pdf`);
                                        } catch (err) {
                                            toast.error(err.response?.data?.error || 'Failed to preview PDF');
                                        }
                                    }
                                },
                                {
                                    label: 'Download',
                                    icon: 'Download',
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
                                    icon: 'FileText',
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
                                <span className="inline-block size-5 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" />
                                <div className="mt-2 text-muted-foreground">Loading {entityTitle}...</div>
                            </div>
                        ) : data.length === 0 ? (
                            <div className="text-center py-5 text-muted-foreground">
                                <Inbox className="size-4" aria-hidden="true" />
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
                                    return (
                                        <div key={item.id} style={{
                                            display: 'flex',
                                            alignItems: 'center',
                                            background: 'var(--tb-card-bg)',
                                            border: '1px solid #e2e8f0',
                                            borderLeft: '4px solid #4f46e5',
                                            borderRadius: 'var(--tb-r-md)',
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
                                                            <div style={{ fontSize: 10, color: 'var(--tb-text-tertiary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '2px', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
                                                                {fmtLabel(col)}
                                                            </div>
                                                            <div style={{
                                                                fontSize: 14,
                                                                color: idx === 0 ? 'var(--tb-brand-active)' : 'var(--tb-gray-700)',
                                                                fontWeight: idx === 0 ? '600' : '400',
                                                                wordBreak: 'break-word',
                                                            }}>
                                                                {v ?? <span style={{ color: 'var(--tb-border-strong)' }}>—</span>}
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
                                                    style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: 12, color: 'var(--tb-brand-hover)', background: 'var(--tb-brand-50)', border: '1px solid #93c5fd', borderRadius: '5px', padding: '4px 10px', cursor: 'pointer' }}
                                                >
                                                    <Pencil className="size-4" aria-hidden="true" /> Edit
                                                </button>
                                                <button
                                                    onClick={() => handleDelete(item)}
                                                    title="Delete"
                                                    style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: 12, color: 'var(--tb-danger-text)', background: 'var(--tb-danger-soft)', border: '1px solid #fca5a5', borderRadius: '5px', padding: '4px 9px', cursor: 'pointer' }}
                                                >
                                                    <Trash2 className="size-4" aria-hidden="true" />
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

            {/* Ownership Details Modal */}
            {entityName === 'licenses' && (
                <OwnershipDetailsModal
                    show={showOwnershipModal}
                    onHide={() => { setShowOwnershipModal(false); setOwnershipLicense(null); }}
                    licenseId={ownershipLicense?.id}
                    licenseNumber={ownershipLicense?.number}
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
                    <div style={{ background: 'var(--tb-card-bg)', borderRadius: 'var(--tb-r-md)', padding: '24px', width: '480px', maxWidth: '95vw', boxShadow: '0 8px 32px rgba(0,0,0,0.18)' }} onClick={e => e.stopPropagation()}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                            <h6 style={{ margin: 0, fontWeight: '700', color: 'var(--tb-brand-active)' }}>
                                <Link className="size-4" aria-hidden="true" />
                                Link Trade: <span style={{ color: 'var(--tb-brand)' }}>{linkModalTrade.invoice_number || 'No Invoice'}</span>
                            </h6>
                            <button onClick={closeLinkModal} style={{ background: 'none', border: 'none', fontSize: '1.2rem', cursor: 'pointer', color: 'var(--tb-text-tertiary)' }}>
                                <X className="size-4" aria-hidden="true" />
                            </button>
                        </div>
                        <input
                            autoFocus
                            type="text"
                            className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                            placeholder="Search by invoice number..."
                            value={linkSearch}
                            onChange={e => setLinkSearch(e.target.value)}
                            style={{ marginBottom: '12px' }}
                        />
                        {linkSearching && <div style={{ textAlign: 'center', color: 'var(--tb-text-tertiary)', padding: '12px' }}><span className="inline-block size-4 animate-spin rounded-full border-2 border-current border-t-transparent mr-2" aria-hidden="true" />Searching...</div>}
                        {!linkSearching && linkSearch && linkResults.length === 0 && (
                            <div style={{ textAlign: 'center', color: 'var(--tb-text-tertiary)', padding: '12px', fontSize: 14 }}>No unlinked trades found for "{linkSearch}"</div>
                        )}
                        {linkResults.map(t => (
                            <div key={t.id} onClick={() => confirmLink(t)} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px 12px', border: '1px solid #e2e8f0', borderRadius: 'var(--tb-r-md)', marginBottom: '8px', cursor: 'pointer', transition: 'background 0.15s' }}
                                onMouseEnter={e => e.currentTarget.style.background = 'var(--tb-info-soft)'}
                                onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                                <div>
                                    <div style={{ fontWeight: '600', fontSize: 14.5, color: 'var(--tb-text)' }}>{t.invoice_number || 'No Invoice'}</div>
                                    <div style={{ fontSize: 12, color: 'var(--tb-text-secondary)' }}>{t.from_company_label} → {t.to_company_label}</div>
                                </div>
                                <div style={{ textAlign: 'right' }}>
                                    <span style={{ fontSize: 12, fontWeight: '700', color: t.direction.includes('SALE') ? 'var(--tb-success-text)' : 'var(--tb-brand-hover)', background: t.direction.includes('SALE') ? 'var(--tb-success-soft)' : 'var(--tb-brand-100)', padding: '2px 8px', borderRadius: 'var(--tb-r-sm)' }}>
                                        {t.direction_label || t.direction}
                                    </span>
                                    <div style={{ fontSize: 12, color: 'var(--tb-text-secondary)', marginTop: '4px' }}>
                                        ₹{Number(t.total_amount).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                                    </div>
                                </div>
                            </div>
                        ))}
                        {!linkSearch && (
                            <div style={{ textAlign: 'center', color: 'var(--tb-text-tertiary)', fontSize: 14, padding: '8px' }}>Type an invoice number to search</div>
                        )}
                    </div>
                </div>
            )}

            {/* BOE Merge Modal */}
            {showMergeModal && mergeBoeTarget && (
                <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)', zIndex: 1060, display: 'flex', alignItems: 'center', justifyContent: 'center' }} onClick={closeMergeModal}>
                    <div style={{ background: 'var(--tb-card-bg)', borderRadius: 'var(--tb-r-md)', padding: '24px', width: '560px', maxWidth: '95vw', boxShadow: '0 8px 32px rgba(0,0,0,0.18)' }} onClick={e => e.stopPropagation()}>
                        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '16px' }}>
                            <h6 style={{ margin: 0, fontWeight: '700', color: 'var(--tb-brand-active)' }}>
                                <Layers className="size-4" aria-hidden="true" />
                                Merge BOE: <span style={{ color: 'var(--accent-color)' }}>{mergeBoeTarget.bill_of_entry_number}</span>
                            </h6>
                            <button onClick={closeMergeModal} style={{ background: 'none', border: 'none', fontSize: '1.2rem', cursor: 'pointer', color: 'var(--tb-text-tertiary)' }}>
                                <X className="size-4" aria-hidden="true" />
                            </button>
                        </div>

                        {/* Target BOE info */}
                        <div style={{ background: 'var(--tb-success-soft)', border: '1px solid #86efac', borderRadius: 'var(--tb-r-md)', padding: '10px 14px', marginBottom: '16px', fontSize: 13.5 }}>
                            <div style={{ fontWeight: '600', color: 'var(--tb-success-text)', marginBottom: '4px' }}>Target BOE (will be kept &amp; updated)</div>
                            <div><MapPin className="size-4" aria-hidden="true" />{mergeBoeTarget.port_name}</div>
                            <div style={{ color: 'var(--tb-text-secondary)', fontSize: 12 }}>
                                {mergeBoeTarget.item_details?.length || 0} item(s) · {mergeBoeTarget.licenses || 'No licenses'}
                            </div>
                        </div>

                        <div style={{ fontWeight: '600', fontSize: 12, color: 'var(--tb-text-secondary)', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '8px' }}>
                            Select source BOE to merge from (port replaces target, items moved, source deleted):
                        </div>

                        {mergeCandidatesLoading && (
                            <div style={{ textAlign: 'center', padding: '20px', color: 'var(--tb-text-tertiary)' }}>
                                <span className="inline-block size-4 animate-spin rounded-full border-2 border-current border-t-transparent mr-2" aria-hidden="true" />Loading candidates...
                            </div>
                        )}

                        {!mergeCandidatesLoading && mergeCandidates.length === 0 && (
                            <div style={{ textAlign: 'center', padding: '20px', color: 'var(--tb-text-tertiary)', fontSize: 14 }}>
                                No other BOEs found with number {mergeBoeTarget.bill_of_entry_number}
                            </div>
                        )}

                        {mergeCandidates.map(candidate => (
                            <div
                                key={candidate.id}
                                onClick={() => setMergeBoeSource(prev => prev?.id === candidate.id ? null : candidate)}
                                style={{
                                    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
                                    padding: '10px 14px', border: `2px solid ${mergeBoeSource?.id === candidate.id ? 'var(--accent-color)' : 'var(--tb-border-soft)'}`,
                                    borderRadius: 'var(--tb-r-md)', marginBottom: '8px', cursor: 'pointer',
                                    background: mergeBoeSource?.id === candidate.id ? 'var(--tb-sunken)' : 'var(--tb-card-bg)',
                                    transition: 'all 0.15s'
                                }}
                            >
                                <div>
                                    <div style={{ fontWeight: '600', fontSize: 14, color: 'var(--tb-text)' }}>
                                        <MapPin className="size-4" aria-hidden="true" />{candidate.port_name}
                                    </div>
                                    <div style={{ fontSize: 12, color: 'var(--tb-text-secondary)' }}>
                                        {candidate.item_details?.length || 0} item(s) · {candidate.licenses || 'No licenses'}
                                    </div>
                                </div>
                                <div style={{ textAlign: 'right' }}>
                                    {candidate.total_inr && (
                                        <div style={{ fontWeight: '700', fontSize: 14, color: 'var(--tb-text)' }}>
                                            ₹{Number(candidate.total_inr).toLocaleString('en-IN', { maximumFractionDigits: 0 })}
                                        </div>
                                    )}
                                    {mergeBoeSource?.id === candidate.id && (
                                        <span style={{ fontSize: 11, color: 'var(--accent-color)', fontWeight: '700' }}>✓ Selected</span>
                                    )}
                                </div>
                            </div>
                        ))}

                        {mergeBoeSource && (
                            <div style={{ background: 'var(--tb-sunken)', border: '1px solid #c4b5fd', borderRadius: 'var(--tb-r-md)', padding: '10px 14px', margin: '12px 0', fontSize: '0.82rem', color: 'var(--accent-color)' }}>
                                <strong>What will happen:</strong>
                                <ul style={{ margin: '6px 0 0 0', paddingLeft: '20px' }}>
                                    <li>Target port will change to <strong>{mergeBoeSource.port_name}</strong></li>
                                    <li>Items from source will be moved to target (duplicates skipped)</li>
                                    <li>Source BOE ({mergeBoeSource.port_name}) will be permanently deleted</li>
                                </ul>
                            </div>
                        )}

                        <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px', marginTop: '16px' }}>
                            <button onClick={closeMergeModal} style={{ padding: '6px 16px', borderRadius: 'var(--tb-r-sm)', border: '1px solid #e2e8f0', background: 'var(--tb-sunken)', cursor: 'pointer', fontSize: 14 }}>
                                Cancel
                            </button>
                            <button
                                onClick={doMerge}
                                disabled={!mergeBoeSource || mergeBoeLoading}
                                style={{ padding: '6px 16px', borderRadius: 'var(--tb-r-sm)', border: 'none', background: mergeBoeSource && !mergeBoeLoading ? 'var(--accent-color)' : 'var(--accent-light)', color: '#fff', cursor: mergeBoeSource && !mergeBoeLoading ? 'pointer' : 'not-allowed', fontSize: 14, fontWeight: '600', display: 'flex', alignItems: 'center', gap: '6px' }}
                            >
                                {mergeBoeLoading
                                    ? <><div className="" style={{ width: '14px', height: '14px', borderWidth: '2px' }}></div>Merging...</>
                                    : <><Layers className="size-4" aria-hidden="true" />Confirm Merge</>
                                }
                            </button>
                        </div>
                    </div>
                </div>
            )}

        </div>
    );
}
