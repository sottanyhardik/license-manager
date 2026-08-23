import {useContext, useEffect, useState, useCallback, useRef, useMemo} from "react";
import {Link, useParams, useLocation, useNavigate} from "react-router-dom";
import {AuthContext} from "../../context/AuthContext";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "../../api/axios";
import {boeApi} from "../../services/api";
import AdvancedFilter from "../../components/AdvancedFilter";
import DataPagination from "../../components/DataPagination";
import DataTable from "../../components/DataTable";
import AccordionTable from "../../components/AccordionTable";
import LicenseBalanceModal from "../../components/LicenseBalanceModal";
import OwnershipDetailsModal from "../../components/OwnershipDetailsModal";
import TransferLetterModal from "../../components/TransferLetterModal";
import EntityCard from "../../components/primitives/EntityCard";
import DetailTable from "../../components/primitives/DetailTable";
import {saveFilterState, restoreFilterState, shouldRestoreFilters} from "../../utils/filterPersistence";
import {openPdfPreview} from "../../utils/pdfPreview";
import {openLicenseCopyPdf} from "../../utils/licenseCopyPdf";
import LinkTradeModal from "./LinkTradeModal";
import BoeMergeModal from "./BoeMergeModal";
import IncentiveLicensesTable from "./tables/IncentiveLicensesTable";
import AllotmentsTable from "./tables/AllotmentsTable";
import GenericMasterCards from "./tables/GenericMasterCards";
import LicensesTable from "./tables/LicensesTable";
import TradesListView from "./TradesListView";
import {getDefaultFilters} from "./masterListConfig";
import LicensePlanningPanel from "../../components/planning/LicensePlanningPanel";
import {useConfirmDialog} from "../../hooks/useConfirmDialog.jsx";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { BookCheck, Building2, Calendar, CalendarX, CloudDownload, Eye, FileSpreadsheet, FileText, Fingerprint, Inbox, Layers, Loader2, MapPin, Network, Pencil, Plus, PlusCircle, Receipt, RefreshCw, Target, Trash2, TriangleAlert, X } from "lucide-react";

type TradeListItem = {
    id: number;
    direction?: string;
    linked_trade_info?: { id: number } | null;
    [key: string]: any;
};

type TradeGroup =
    | { type: "single"; trade: TradeListItem; pairKey: string }
    | { type: "pair"; sale: TradeListItem; purchase: TradeListItem; pairKey: string };

const EMPTY_LIST: any[] = [];

/**
 * Keeps the list's existing linked-trade presentation while avoiding an O(n²)
 * `Array.find` for every row. The API guarantees unique trade IDs; retaining
 * the first occurrence also preserves the previous `find` behaviour if a
 * malformed response contains a duplicate ID.
 */
// eslint-disable-next-line react-refresh/only-export-components
export function groupLinkedTrades(trades: TradeListItem[]): TradeGroup[] {
    const byId = new Map<number, TradeListItem>();
    for (const trade of trades) {
        if (!byId.has(trade.id)) byId.set(trade.id, trade);
    }

    const seen = new Set<number>();
    const groups: TradeGroup[] = [];
    for (const trade of trades) {
        if (seen.has(trade.id)) continue;
        seen.add(trade.id);

        const partnerId = trade.linked_trade_info?.id;
        const partner = partnerId == null ? undefined : byId.get(partnerId);
        if (partner && !seen.has(partner.id)) {
            seen.add(partner.id);
            const sale = trade.direction?.includes("SALE") ? trade : partner;
            const purchase = trade.direction?.includes("PURCHASE") ? trade : partner;
            groups.push({
                type: "pair",
                sale,
                purchase,
                pairKey: `pair-${Math.min(trade.id, partner.id)}`,
            });
            continue;
        }

        groups.push({ type: "single", trade, pairKey: `single-${trade.id}` });
    }
    return groups;
}

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
    const [error, setError] = useState("");

    // Pagination state
    const [currentPage, setCurrentPage] = useState(1);
    const [pageSize, setPageSize] = useState(25);

    // Filter state with default filters for allotments, bill-of-entries, and incentive-licenses
    const [filterParams, setFilterParams] = useState(() => getDefaultFilters(entityName));
    const backendDefaultsApplied = useRef(false);
    const qc = useQueryClient();

    // License Balance Modal state
    const [showBalanceModal, setShowBalanceModal] = useState(false);
    const [selectedLicenseId, setSelectedLicenseId] = useState(null);

    // Tracks license IDs currently fetching ownership from DGFT
    const [fetchingOwnershipIds, setFetchingOwnershipIds] = useState<Set<number>>(() => new Set());

    // Ownership details modal state
    const [showOwnershipModal, setShowOwnershipModal] = useState(false);
    const [ownershipLicense, setOwnershipLicense] = useState(null); // { id, number }

    // Utilization planning panel state
    const [showPlanModal, setShowPlanModal] = useState(false);
    const [planLicense, setPlanLicense] = useState(null); // { id, number, balance }

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
            invalidateList();
        } catch (err) { toast.error(err.response?.data?.error || 'Failed to link trades'); }
    };

    const [expandedPairs, setExpandedPairs] = useState<Set<string>>(() => new Set());
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

    const [expandedTrades, setExpandedTrades] = useState<Set<number>>(() => new Set());
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

    // Standalone loading flag for the "Fetch All Products" bulk action (not list loading)
    const [bulkActionLoading, setBulkActionLoading] = useState(false);

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
            invalidateList();
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
            setEditingInvoiceId(null);
            invalidateList();
        } catch (e) {
            toast.error('Failed to update invoice number');
        } finally {
            setInvoiceSaving(false);
        }
    };

    // Confirmation dialog hook
    const { confirmDelete, confirmDangerousAction, confirmDialog } = useConfirmDialog();

    // ---------------------------------------------------------------------------
    // Filter initialization — runs once on entity change to resolve the initial
    // filterParams from URL, session storage, or hardcoded defaults.
    // The result is stored in state; useQuery below reacts to it automatically.
    // ---------------------------------------------------------------------------
    useEffect(() => {
        if (!entityName) return;

        // Reset flags when entity changes
        backendDefaultsApplied.current = false;

        // Clear filters from other entities to prevent cross-contamination
        const allEntities = ['licenses', 'allotments', 'trades', 'bill-of-entries', 'incentive-licenses'];
        allEntities.forEach(entity => {
            if (entity !== entityName) {
                try {
                    sessionStorage.removeItem(`${entity}ListFilters`);
                    sessionStorage.removeItem(`filterState_${entity}`);
                } catch {
                    // Silently handle error
                }
            }
        });

        // Parse URL query parameters — keep in API format (__gte/__lte) so filterParams
        // is always in API format. uiFilterParams derives the UI format for display.
        const urlParams = new URLSearchParams(location.search);
        const urlFilters: Record<string, string> = {};
        for (const [key, value] of urlParams.entries()) {
            urlFilters[key] = value;
        }

        const hasUrlFilters = Object.keys(urlFilters).length > 0;
        if (hasUrlFilters) {
            setFilterParams(urlFilters);
            setCurrentPage(1);
            setPageSize(25);
            backendDefaultsApplied.current = true;
        } else {
            const shouldRestore = shouldRestoreFilters();
            const restored = shouldRestore ? restoreFilterState(entityName) : null;
            const defaultFilters = getDefaultFilters(entityName);

            if (restored) {
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
            } else {
                setFilterParams(defaultFilters);
                setCurrentPage(1);
                setPageSize(25);
                backendDefaultsApplied.current = true;
            }
        }
    }, [entityName, location.search]);

    // ---------------------------------------------------------------------------
    // Main list query — re-runs whenever entity, page, size, or filters change.
    // TanStack handles request de-duplication and cancellation.
    // ---------------------------------------------------------------------------
    const queryParams = useMemo(() => {
        const params: Record<string, string | number> = { page: currentPage, page_size: pageSize, ...filterParams };
        // A numeric (or comma-separated numeric) search on Allotments is a
        // licence-number lookup.  Send it through the exact backend filter so
        // multiple supplied licences use OR semantics; normal text remains the
        // existing general `search` behaviour.
        if (entityName === 'allotments' && typeof params.search === 'string') {
            const licences = [...new Set(params.search.split(',').map(value => value.trim()).filter(Boolean))];
            if (licences.length > 0 && licences.every(value => /^\d+$/.test(value))) {
                params.license_number = licences.join(',');
                delete params.search;
            }
        }
        return params;
    }, [currentPage, pageSize, filterParams, entityName]);

    /** Convert API-format filterParams (license_date__gte) to UI format (license_date_from)
     *  for correct display in AdvancedFilter inputs. */
    const uiFilterParams = useMemo<Record<string, string>>(() => {
        const ui: Record<string, string> = {};
        for (const [key, value] of Object.entries(filterParams)) {
            const v = String(value ?? "");
            if (key.endsWith("__gte")) {
                ui[`${key.slice(0, -5)}_from`] = v;
            } else if (key.endsWith("__lte")) {
                ui[`${key.slice(0, -5)}_to`] = v;
            } else {
                ui[key] = v;
            }
        }
        return ui;
    }, [filterParams]);

    const {
        data: listResponse,
        isLoading: loading,
        isFetching: isRefreshing,
        isError: listFailed,
        error: listError,
    } = useQuery({
        queryKey: ['entity-list', entityName, queryParams],
        queryFn: async ({ signal }) => {
            if (entityName === 'bill-of-entries') {
                return boeApi.fetchBOEList(queryParams);
            }
            let apiPath: string;
            if (entityName === 'licenses' || entityName === 'allotments' || entityName === 'trades') {
                apiPath = `${entityName}/`;
            } else if (entityName === 'incentive-licenses') {
                apiPath = `incentive-licenses/`;
            } else {
                apiPath = `masters/${entityName}/`;
            }
            const { data: apiResponse } = await api.get(apiPath, { params: queryParams, signal });
            return apiResponse;
        },
        enabled: Boolean(entityName),
        placeholderData: (prev) => prev,
    });

    // Derive list data and metadata from query result
    const data = listResponse?.results ?? EMPTY_LIST;
    const totalRecords = listResponse?.count ?? data.length;
    const totalPages = listResponse?.total_pages ?? 1;
    const hasNext = listResponse?.has_next ?? false;
    const hasPrevious = listResponse?.has_previous ?? false;

    // Metadata is response-derived. Keeping it out of local state avoids a
    // second complete MasterList render after every successful list request.
    const metadata = useMemo<Record<string, any>>(() => {
        if (!listResponse) return {};
        return {
            list_display: listResponse.list_display || [],
            form_fields: listResponse.form_fields || [],
            search_fields: listResponse.search_fields || [],
            filter_fields: listResponse.filter_fields || [],
            filter_config: listResponse.filter_config || {},
            ordering_fields: listResponse.ordering_fields || [],
            nested_field_defs: listResponse.nested_field_defs || {},
            nested_list_display: listResponse.nested_list_display || {},
            field_meta: listResponse.field_meta || {},
            default_filters: listResponse.default_filters || {},
            inline_editable: listResponse.inline_editable || [],
        };
    }, [listResponse]);

    // Update filterParams when backend default filters are received (for UI display only).
    useEffect(() => {
        if (backendDefaultsApplied.current && Object.keys(filterParams).length > 0) return;
        const backendDefaults = metadata.default_filters || {};
        const hardcodedDefaults = getDefaultFilters(entityName);
        if (Object.keys(backendDefaults).length > 0 && Object.keys(hardcodedDefaults).length === 0) {
            setFilterParams(backendDefaults);
            setCurrentPage(1);
            backendDefaultsApplied.current = true;
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [metadata.default_filters]);

    // Group once per response. Expansion, modal, and other local UI state no
    // longer repeats linked-trade grouping work for a large page of results.
    const tradeGroups = useMemo(
        () => entityName === "trades" ? groupLinkedTrades(data as TradeListItem[]) : [],
        [entityName, data],
    );

    // Surface list load failure to the error banner
    useEffect(() => {
        if (listFailed && listError) {
            const errorMsg = (listError as { response?: { data?: { detail?: string } } })?.response?.data?.detail || "Failed to load data";
            setError(errorMsg);
            toast.error(errorMsg);
        }
    }, [listFailed, listError]);

    // Helper to invalidate the current entity's list — used after mutations
    const invalidateList = useCallback(() => {
        qc.invalidateQueries({ queryKey: ['entity-list', entityName] });
    }, [qc, entityName]);

    // Fetch DGFT ownership for a single license — extracted from inline card
    const handleFetchOwnership = useCallback(async (item: { id: number; license_number?: string }) => {
        setFetchingOwnershipIds(prev => { const n = new Set(prev); n.add(item.id); return n; });
        try {
            const r = await api.post(`license-actions/${item.id}/fetch-ownership/`);
            const owner = r.data?.current_owner?.name || '—';
            toast.success(`Ownership updated: ${owner} (${r.data?.transfers_count ?? 0} transfers)`);
            invalidateList();
        } catch (err: any) {
            toast.error(err?.response?.data?.error || err?.message || 'Failed to fetch ownership');
        } finally {
            setFetchingOwnershipIds(prev => { const n = new Set(prev); n.delete(item.id); return n; });
        }
    }, [invalidateList]);

    useEffect(() => {
        if (!linkModalTrade) return;
        const t = setTimeout(() => searchTradesForLink(linkSearch), 350);
        return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [linkSearch, linkModalTrade]);

    const handleFilterChange = useCallback((filters: Record<string, unknown>) => {
        // filters arrives in API format (license_date__gte etc.) from AdvancedFilter.
        // Keep in API format — queryParams spreads filterParams directly into the API call.
        // uiFilterParams (derived via useMemo) converts back to UI format for display.
        setFilterParams(filters as Record<string, string>);
        setCurrentPage(1);
    }, []);

    useEffect(() => {
        if (entityName !== 'allotments') return;
        const params = new URLSearchParams();
        Object.entries(filterParams).forEach(([key, value]) => {
            if (value !== '' && value != null) params.set(key, String(value));
        });
        params.set('page', String(currentPage));
        const nextSearch = params.toString();
        if (nextSearch !== location.search.slice(1)) navigate({ search: nextSearch }, { replace: true });
    }, [entityName, filterParams, currentPage, location.search, navigate]);

    const handlePageChange = (page) => {
        setCurrentPage(page);
    };

    const handlePageSizeChange = (size) => {
        setPageSize(size);
        setCurrentPage(1);
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
            invalidateList();
        } catch (err) {
            toast.error(err.response?.data?.detail || "Failed to delete record");
        }
    };

    // Trade mutations remain owned here so the presentation component cannot
    // alter endpoints, permissions, filter persistence, or cache invalidation.
    const handleCopyTradeToCounterpart = useCallback(async (item: TradeListItem) => {
        const destination = item.direction === 'SALE' ? 'Purchase' : 'Sale';
        const confirmed = await confirmDangerousAction(
            `Copy to ${destination}`,
            `Create the linked ${destination} with the same companies, licence lines and commercial amounts?`,
        );
        if (!confirmed) return;

        try {
            const endpoint = item.direction === 'SALE' ? 'copy-to-purchase' : 'copy-to-sale';
            const response = await api.post(`trades/${item.id}/${endpoint}/`);
            toast.success(response.data.created ? `Linked ${destination} created` : `Linked ${destination} already exists`);
            invalidateList();
            navigate(`/trades/${response.data.counterpart.id}/edit`);
        } catch (err) {
            toast.error(err.response?.data?.error || `Failed to copy to ${destination}`);
        }
    }, [confirmDangerousAction, invalidateList, navigate]);

    const handleTradeTransferLetter = useCallback((item: TradeListItem) => {
        setTransferLetterType('trade');
        setTransferLetterEntityId(item.id);
        setShowTransferLetterModal(true);
    }, []);

    const handleToggleBoolean = async (item, field, newValue) => {
        // Optimistic UI update via query cache
        const queryKey = ['entity-list', entityName, queryParams];
        const previous = qc.getQueryData(queryKey);
        qc.setQueryData(queryKey, (old: typeof listResponse) => {
            if (!old) return old;
            return {
                ...old,
                results: (old.results || []).map((d: Record<string, unknown>) =>
                    d.id === item.id ? { ...d, [field]: newValue } : d
                ),
            };
        });

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
            invalidateList();
        } catch (err) {
            // Revert optimistic update on error
            qc.setQueryData(queryKey, previous);
            toast.error(err.response?.data?.detail || `Failed to update ${field}`);
            throw err;
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
            invalidateList();
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
        <div className="min-h-screen bg-[--tb-body-bg]">
            {/* Tabler-style page header */}
            <div className={cn("page-header", entityName === "licenses" && "mb-3 rounded-xl border border-border/70 bg-card px-4 py-3 shadow-sm")}>
                <div className="min-w-0">
                    <div className="page-pretitle">
                        <a
                            href="/"
                            onClick={(e) => { e.preventDefault(); navigate('/'); }}
                            className="text-inherit no-underline"
                        >
                            Home
                        </a>
                        <span className="mx-1.5 opacity-50">/</span>
                        {entityTitle}
                    </div>
                    <h1>{entityTitle}</h1>
                    {entityName === "licenses" && (
                        <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-muted-foreground">
                            <span className="font-medium text-foreground">Licence workspace</span>
                            <span aria-hidden="true" className="text-border">•</span>
                            <span className="tabular-nums">{totalRecords.toLocaleString("en-IN")} record{totalRecords === 1 ? "" : "s"}</span>
                            {isRefreshing && <span role="status">Updating…</span>}
                        </div>
                    )}
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
                            disabled={bulkActionLoading}
                            onClick={async () => {
                                const confirmed = await confirmDangerousAction(
                                    'Bulk Update Product Names',
                                    'This will update product names for ALL BOEs with empty product_name in the entire database. This may take some time. Continue?'
                                );
                                if (!confirmed) return;
                                setBulkActionLoading(true); setError("");
                                try {
                                    const response = await api.post(`bill-of-entries/bulk-update-product-names/`);
                                    if (response.data.success) {
                                        toast.success(response.data.message || `Processed ${response.data.total} BOEs: ${response.data.updated} updated, ${response.data.skipped} skipped`);
                                        invalidateList();
                                    } else {
                                        setError('Failed to update product names');
                                    }
                                } catch (err) {
                                    setError(err.response?.data?.error || err.response?.data?.message || 'Failed to update product names');
                                    toast.error(err.response?.data?.error || err.response?.data?.message || 'Failed to update product names');
                                } finally {
                                    setBulkActionLoading(false);
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
                initialFilters={uiFilterParams}
                defaultFilters={entityName === 'allotments' ? getDefaultFilters(entityName) : (metadata.default_filters || {})}
                resetToDefaults={entityName === 'allotments'}
                isUpdating={isRefreshing}
            />

            {/* Table */}
            <div className={cn("surface-card mt-4", entityName === "licenses" && "mt-3 overflow-hidden border-border/70 shadow-sm")}>
                <div className={cn("p-3.5", entityName === "licenses" && "p-2 sm:p-3")}>
                    {isRefreshing && !loading && (
                        <div role="status" className="mb-2 text-xs text-muted-foreground">Updating results…</div>
                    )}
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
                                                <span className="inline-flex items-center gap-1">
                                                    <input
                                                        autoFocus
                                                        value={invoiceDraft}
                                                        onChange={e => setInvoiceDraft(e.target.value)}
                                                        onKeyDown={e => { if (e.key === 'Enter') saveInvoiceEdit(item.id); if (e.key === 'Escape') cancelInvoiceEdit(); }}
                                                        placeholder="Invoice number"
                                                        className="w-40 rounded-md border border-success px-2 py-0.5 text-[0.82rem] outline-none"
                                                    />
                                                    <button type="button" onClick={() => saveInvoiceEdit(item.id)} disabled={invoiceSaving} className="cursor-pointer rounded-md bg-success px-2 py-0.5 text-xs text-white disabled:opacity-50">
                                                        {invoiceSaving ? '…' : 'Save'}
                                                    </button>
                                                    <button type="button" onClick={cancelInvoiceEdit} className="cursor-pointer rounded-md border border-border bg-muted px-2 py-0.5 text-xs text-muted-foreground">✕</button>
                                                </span>
                                            )
                                            : (
                                                <button
                                                    type="button"
                                                    onClick={() => startInvoiceEdit(item)}
                                                    title="Click to edit invoice number"
                                                    className="inline-flex cursor-pointer items-center gap-1 rounded-md border border-success bg-success/10 px-2 py-0.5 text-[0.82rem] font-medium text-success"
                                                >
                                                    {item.invoice_no
                                                        ? (<><Receipt className="size-4" aria-hidden="true" /> {item.invoice_no}</>)
                                                        : (<><PlusCircle className="size-4" aria-hidden="true" /> Add Invoice No</>)
                                                    }
                                                    <Pencil className="size-4" aria-hidden="true" />
                                                </button>
                                            ))
                                        : null;

                                    const boeTitleEl = item.bill_of_entry_number ? (
                                        <Link
                                            to={`/bill-of-entries/${item.id}/edit`}
                                            onClick={() => {
                                                saveFilterState(entityName, { filters: filterParams, pagination: { currentPage, pageSize }, search: '' });
                                            }}
                                            className="font-mono text-[16px] font-bold tracking-tight text-inherit underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:rounded"
                                        >
                                            {item.bill_of_entry_number}
                                        </Link>
                                    ) : '—';

                                    return (
                                        <EntityCard
                                            key={item.id}
                                            className={hasDispute ? 'is-dispute' : ''}
                                            accent={hasDispute ? 'danger' : 'primary'}
                                            title={boeTitleEl}
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
                                                { label: 'Unit Price', value: item.unit_price ? Number(item.unit_price).toLocaleString('en-IN', { maximumFractionDigits: 2 }) : '—' },
                                            ]}
                                            actions={[
                                                hasDispute && {
                                                    icon: 'check2-circle', title: 'Resolve Dispute', tone: 'danger',
                                                    onClick: async () => {
                                                        const confirmed = await confirmDangerousAction('Resolve Dispute', `Resolve ${disputeRows.length} dispute row(s) on BOE ${item.bill_of_entry_number}? This clears the dispute flag on all flagged rows.`);
                                                        if (!confirmed) return;
                                                        try {
                                                            const response = await api.post(`bill-of-entries/${item.id}/resolve-dispute/`);
                                                            toast.success(response.data.message || 'Dispute resolved');
                                                            invalidateList();
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
                                                        const confirmed = await confirmDangerousAction('Update Product Name', `Update product name for BOE ${item.bill_of_entry_number}?`);
                                                        if (!confirmed) return;
                                                        try {
                                                            const response = await api.post(`bill-of-entries/${item.id}/update-product-name/`);
                                                            toast.success(response.data.message || 'Product name updated');
                                                            invalidateList();
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
                                                                ? <span title="Not found in latest ledger upload — dispute" className="text-destructive text-sm"><TriangleAlert className="size-4" aria-hidden="true" /></span>
                                                                : null },
                                                        { key: 'license_number',   label: 'License',   bold: true, nowrap: true,
                                                            render: (v, row) => v && row.license_id ? (
                                                                <button
                                                                    type="button"
                                                                    onClick={() => openLicenseCopyPdf(row.license_id, v)}
                                                                    className={cn(row.is_dispute ? 'text-destructive' : 'text-primary', 'hover:underline underline-offset-2 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring', 'cursor-pointer')}
                                                                    title="Open License Copy PDF"
                                                                    aria-label={`Open License Copy PDF for ${v}`}
                                                                >
                                                                    {v}
                                                                </button>
                                                            ) : (
                                                                <span className={cn(row.is_dispute ? 'text-destructive' : 'text-primary')}>{v || '—'}</span>
                                                            ) },
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
                                            <div className="flex flex-wrap items-start gap-6">
                                                <div className="min-w-[200px] flex-1">
                                                    <div className="mb-0.5 text-[0.66rem] font-semibold uppercase tracking-[0.06em] text-muted-foreground">Product</div>
                                                    <div className="text-[14.5px] font-medium text-foreground">
                                                        {item.product_name || <span className="italic text-muted-foreground">No product name</span>}
                                                    </div>
                                                </div>
                                                {item.licenses && (
                                                    <div className="min-w-[140px] flex-1">
                                                        <div className="mb-0.5 text-[0.66rem] font-semibold uppercase tracking-[0.06em] text-muted-foreground">Licenses</div>
                                                        <div className="text-[13.5px] font-medium text-primary">{item.licenses}</div>
                                                    </div>
                                                )}
                                                {invoiceChip && (
                                                    <div className="self-center">
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
                        <AllotmentsTable
                            loading={loading}
                            data={data}
                            canWrite={canWrite}
                            entityName={entityName}
                            filterParams={filterParams}
                            currentPage={currentPage}
                            pageSize={pageSize}
                            navigate={navigate}
                            onDelete={handleDelete}
                            expandedAllotments={expandedAllotments}
                            toggleAllotment={toggleAllotment}
                        />
                    )}

                    {/* Licenses — extracted to dedicated component */}
                    {entityName === 'licenses' && (
                        <LicensesTable
                            loading={loading}
                            data={data}
                            canWrite={canWrite}
                            entityName={entityName}
                            filterParams={filterParams}
                            currentPage={currentPage}
                            pageSize={pageSize}
                            navigate={navigate}
                            onDelete={handleDelete}
                            fetchingOwnershipIds={fetchingOwnershipIds}
                            onFetchOwnership={handleFetchOwnership}
                            invalidateList={invalidateList}
                        />
                    )}

                    {/* Trades — dedicated presentation component; list lifecycle and mutations remain above. */}
                    {entityName === 'trades' && (
                        <TradesListView
                            loading={loading}
                            data={data}
                            tradeGroups={tradeGroups}
                            canWrite={canWrite}
                            entityName={entityName}
                            filterParams={filterParams}
                            currentPage={currentPage}
                            pageSize={pageSize}
                            navigate={navigate}
                            onDelete={handleDelete}
                            onOpenLink={openLinkModal}
                            onCopyToCounterpart={handleCopyTradeToCounterpart}
                            onTransferLetter={handleTradeTransferLetter}
                            expandedTrades={expandedTrades}
                            onToggleTrade={toggleTrade}
                            expandedPairs={expandedPairs}
                            onTogglePair={togglePair}
                        />
                    )}

                    {/* Incentive Licenses Card Layout */}
                    {entityName === 'incentive-licenses' && (
                        <IncentiveLicensesTable
                            loading={loading}
                            data={data}
                            canWrite={canWrite}
                            entityName={entityName}
                            filterParams={filterParams}
                            currentPage={currentPage}
                            pageSize={pageSize}
                            navigate={navigate}
                            onDelete={handleDelete}
                        />
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
                                        const confirmed = await confirmDangerousAction('Copy to Sale', 'Create a SALE trade from this PURCHASE trade?');
                                        if (!confirmed) { return; }
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
                                                boes: (purchaseTrade.boes || []).map(b => b?.id || b),
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
                                        const confirmed = await confirmDangerousAction('Copy Allotment', `Create a copy of allotment ${item.invoice_number || 'this allotment'}?`);
                                        if (!confirmed) { return; }
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
                                    icon: 'RefreshCw',
                                    className: 'btn btn-outline-info',
                                    onClick: async (item) => {
                                        const confirmed = await confirmDangerousAction('Update Product Name', `Update product name for BOE ${item.bill_of_entry_number}?`);
                                        if (!confirmed) { return; }
                                        try {
                                            const response = await api.post(`bill-of-entries/${item.id}/update-product-name/`);
                                            toast.success(response.data.message || 'Product name updated successfully');
                                            // Refresh the list to show updated product name
                                            invalidateList();
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
                        <GenericMasterCards
                            loading={loading}
                            data={data}
                            metadata={metadata}
                            entityName={entityName}
                            entityTitle={entityTitle}
                            filterParams={filterParams}
                            currentPage={currentPage}
                            pageSize={pageSize}
                            navigate={navigate}
                            onDelete={handleDelete}
                        />
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

            {/* Utilization Planning Panel */}
            {entityName === 'licenses' && (
                <LicensePlanningPanel
                    show={showPlanModal}
                    onHide={() => { setShowPlanModal(false); setPlanLicense(null); }}
                    licenseId={planLicense?.id}
                    licenseNumber={planLicense?.number}
                    balanceCif={planLicense?.balance || 0}
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
                <LinkTradeModal
                    linkModalTrade={linkModalTrade}
                    closeLinkModal={closeLinkModal}
                    linkSearch={linkSearch}
                    setLinkSearch={setLinkSearch}
                    linkSearching={linkSearching}
                    linkResults={linkResults}
                    confirmLink={confirmLink}
                />
            )}

            {/* BOE Merge Modal */}
            {showMergeModal && mergeBoeTarget && (
                <BoeMergeModal
                    mergeBoeTarget={mergeBoeTarget}
                    closeMergeModal={closeMergeModal}
                    mergeCandidatesLoading={mergeCandidatesLoading}
                    mergeCandidates={mergeCandidates}
                    mergeBoeSource={mergeBoeSource}
                    setMergeBoeSource={setMergeBoeSource}
                    mergeBoeLoading={mergeBoeLoading}
                    doMerge={doMerge}
                />
            )}

        </div>
    );
}
