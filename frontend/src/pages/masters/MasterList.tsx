import {useContext, useEffect, useState, useCallback, useRef, useMemo} from "react";
import {Link, useParams, useLocation, useNavigate} from "react-router-dom";
import {AuthContext} from "../../context/AuthContext";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "../../api/axios";
import {boeApi} from "../../api";
import * as boeApiTyped from "@/api/boeApi";
import { qk } from "@/lib/queryKeys";
import {useBulkUpdateProductNames, useUpdateBoeInvoiceNo} from "@/features/bill-of-entry/useBoeRowActions";
import AdvancedFilter from "../../components/AdvancedFilter";
import ActiveFilters, { type ActiveFilterItem } from "@/components/ActiveFilters";
import DataPagination from "../../components/DataPagination";
import DataTable from "../../components/DataTable";
import AccordionTable from "../../components/AccordionTable";
import LicenseBalanceModal from "../../components/LicenseBalanceModal";
import OwnershipDetailsModal from "../../components/OwnershipDetailsModal";
import TransferLetterModal from "../../components/TransferLetterModal";
import {saveFilterState, restoreFilterState, shouldRestoreFilters} from "../../utils/filterPersistence";
import {openPdfPreview} from "../../utils/pdfPreview";
import LinkTradeModal from "./LinkTradeModal";
import BoeMergeModal from "./BoeMergeModal";
import IncentiveLicensesTable from "./tables/IncentiveLicensesTable";
import AllotmentsTable from "./tables/AllotmentsTable";
import GenericMasterCards, { type MasterBulkAction, type MasterBulkResult } from "./tables/GenericMasterCards";
import LicensesTable from "./tables/LicensesTable";
import TradesListView from "./TradesListView";
import BoeTable from "@/features/bill-of-entry/BoeTable";
import {getDefaultFilters, getMasterRecordKey} from "./masterListConfig";
import { masterEntities } from "../../routes/config";
import LicensePlanningPanel from "../../components/planning/LicensePlanningPanel";
import {useConfirmDialog} from "../../hooks/useConfirmDialog.jsx";
import PageHeader from "@/components/PageHeader";
import { Button } from "@/components/ui/button";
import { ActionMenu } from "@/components/shared";
import { cn } from "@/lib/utils";
import { BookCheck, Building2, Calendar, CalendarX, CloudDownload, Eye, FileSpreadsheet, FileText, Fingerprint, Layers, Loader2, MapPin, Network, Plus, RefreshCw, Target, Trash2, X } from "lucide-react";
import { ROLES, BOE_TRANSFER_LETTER_ROLES } from '../../routes/authorizationRoles';

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
/** Entities that use the compact register layout (toolbar header instead of PageHeader). */
const COMPACT_REGISTER = new Set(["licenses", "bill-of-entries"]);

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
/** Read `page` and filter params from a URL query string (API-format keys). */
function parseListUrl(search: string): { filters: Record<string, string>; page: number | null } {
    const filters: Record<string, string> = {};
    let page: number | null = null;
    for (const [key, value] of new URLSearchParams(search).entries()) {
        if (key === "page") {
            const parsed = Number.parseInt(value, 10);
            page = Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
            continue;
        }
        if (key === "page_size") continue;
        filters[key] = value;
    }
    return { filters, page };
}

/** Canonical (sorted) query encoding, used to recognise our own URL writes. */
function canonicalSearch(search: string): string {
    const params = new URLSearchParams(search);
    params.sort();
    return params.toString();
}

/**
 * Filter values travel as strings: arrays (multi-select FKs, list defaults)
 * become comma lists and booleans/numbers `String()`.  This is the form the URL
 * round-trip produced anyway, so normalising at the boundary keeps the React
 * Query key stable instead of refetching after the URL write.
 */
function normalizeFilterValues(filters: Record<string, unknown>): Record<string, string> {
    const out: Record<string, string> = {};
    for (const [key, value] of Object.entries(filters)) {
        if (Array.isArray(value)) out[key] = value.join(",");
        else if (value !== null && value !== undefined) out[key] = String(value);
    }
    return out;
}

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
        'licenses':           [ROLES.LICENSE_MANAGER],
        'allotments':         [ROLES.ALLOTMENT_MANAGER],
        'bill-of-entries':    [ROLES.BOE_MANAGER],
        'trades':             [ROLES.TRADE_MANAGER],
        'incentive-licenses': [ROLES.INCENTIVE_LICENSE_MANAGER],
    };
    // For known business entities: check the mapped write roles.
    // Master data is maintained by superusers and trusted user administrators.
    const canWrite = entityName in ENTITY_WRITE_ROLES
        ? hasAnyRole(ENTITY_WRITE_ROLES[entityName])
        : isSuperAdmin() || hasRole(ROLES.USER_MANAGER);

    // ACCOUNT_ACCESS users can edit invoice_no on BOE items only
    const canEditInvoice = canWrite || hasAnyRole([ROLES.ACCOUNT_ACCESS, ROLES.BOE_VIEWER]);
    // Mirrors backend TransferLetterPermission (BOE_VIEWER excluded by owner decision).
    const canTransferLetter = hasAnyRole(BOE_TRANSFER_LETTER_ROLES);
    const [error, setError] = useState("");

    // Pagination state
    // Seeded from the URL so the URL-sync effect (which runs in the same first
    // commit as the init effect) sees the deep-linked page/filters instead of
    // stale defaults and does not rewrite the URL back and forth.
    const [currentPage, setCurrentPage] = useState(() => parseListUrl(location.search).page ?? 1);
    const [pageSize, setPageSize] = useState(25);

    // Filter state with default filters for allotments, bill-of-entries, and incentive-licenses
    const [filterParams, setFilterParams] = useState<Record<string, string>>(() => {
        const { filters } = parseListUrl(location.search);
        return Object.keys(filters).length > 0 ? filters : getDefaultFilters(entityName);
    });
    const backendDefaultsApplied = useRef(false);
    // Canonical search string of the last URL write made by the sync effect.
    // The init effect skips that echo so it never re-seeds state (page size,
    // filters) from our own navigation; cleared on any external navigation.
    const ownSearchWrite = useRef<string | null>(null);
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

    // Standalone loading flag for the "Fetch All Products" bulk action (not list loading)
    const [bulkActionLoading, setBulkActionLoading] = useState(false);

    // BOE Merge Modal state
    const [showMergeModal, setShowMergeModal] = useState(false);
    const [mergeBoeTarget, setMergeBoeTarget] = useState(null);
    const [mergeBoeSource, setMergeBoeSource] = useState(null);
    const [mergeBoeLoading, setMergeBoeLoading] = useState(false);
    const [mergeError, setMergeError] = useState('');
    const [mergeCandidates, setMergeCandidates] = useState([]);
    const [mergeCandidatesLoading, setMergeCandidatesLoading] = useState(false);

    const openMergeModal = async (item) => {
        setMergeBoeTarget(item);
        setMergeBoeSource(null);
        setMergeError('');
        setShowMergeModal(true);
        setMergeCandidatesLoading(true);
        try {
            const resp = await boeApi.fetchBOEList<{ results?: Array<{ id: number; bill_of_entry_number: string }> }>({ search: item.bill_of_entry_number, is_invoice: 'all', page_size: 50 });
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
        setMergeError('');
        try {
            const resp = await boeApi.mergeBOE(mergeBoeTarget.id, mergeBoeSource.id);
            toast.success(boeApiTyped.describeBoeMerge(resp, mergeBoeTarget.id));
            closeMergeModal();
            invalidateList();
            // Merge moves items/links between licences: refresh every cached BOE view.
            void qc.invalidateQueries({ queryKey: qk.boes.all });
        } catch (err) {
            // Rejections (frozen both, hidden mismatch, trade/invoice links) arrive as {error}.
            const msg = boeApiTyped.extractBoeError(err, 'Failed to merge BOE');
            setMergeError(msg);
            toast.error(msg);
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
        try {
            // Dedicated endpoint — accessible to ACCOUNT_ACCESS, BOE_VIEWER (D2) and BOE_MANAGER.
            // Does NOT require full BOE edit permission.
            await updateInvoiceNo.mutateAsync({ id: itemId, invoiceNo: invoiceDraft.trim() });
            setEditingInvoiceId(null);
        } catch {
            // toast shown by the mutation's onError; keep the editor open
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

        // Echo of our own URL write: state is already the source of truth.
        // Single use and keyed on entity+search, so a later navigation that
        // happens to land on the same string (or another entity) re-initialises.
        const echoKey = `${entityName}|${canonicalSearch(location.search)}`;
        const isOwnEcho = ownSearchWrite.current === echoKey;
        ownSearchWrite.current = null;
        if (isOwnEcho) return;

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
        let urlPage: number | null = null;
        for (const [key, value] of urlParams.entries()) {
            // Pagination belongs to its own state. Keeping `page` in filters
            // makes the URL synchronization effect turn numeric page 1 into
            // string "1", producing a second React Query key/request for the
            // same list on initial navigation.
            if (key === "page") {
                const parsed = Number.parseInt(value, 10);
                urlPage = Number.isSafeInteger(parsed) && parsed > 0 ? parsed : null;
                continue;
            }
            if (key === "page_size") continue;
            urlFilters[key] = value;
        }

        const hasUrlFilters = Object.keys(urlFilters).length > 0;
        if (hasUrlFilters) {
            setFilterParams(urlFilters);
            setCurrentPage(urlPage ?? 1);
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
                setCurrentPage(urlPage ?? 1);
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
        if (entityName === 'licenses' && typeof params.search === 'string') {
            // A full numeric licence number is an identity lookup, not a
            // fuzzy search.  Sending it through the dedicated filter keeps
            // `/licenses?search=0310835340` scoped to that one licence.
            const licenceNumber = params.search.trim();
            if (/^\d{10}$/.test(licenceNumber)) {
                params.license_number = licenceNumber;
                delete params.search;
            }
        }
        if (entityName === 'allotments' && typeof params.search === 'string') {
            const licences = [...new Set(params.search.split(',').map(value => value.trim()).filter(Boolean))];
            if (licences.length > 0 && licences.every(value => /^\d+$/.test(value))) {
                params.license_number = licences.join(',');
                delete params.search;
            }
        }
        // Trades must always open with the most recent bill/invoice first.
        // In particular, do not let a legacy saved filter restore an older
        // ascending order when the user opens /trades?page=1.
        if (entityName === 'trades') {
            params.ordering = '-invoice_date';
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
            bulk_actions: listResponse.bulk_actions || [],
        };
    }, [listResponse]);

    // Update filterParams when backend default filters are received (for UI display only).
    useEffect(() => {
        if (backendDefaultsApplied.current && Object.keys(filterParams).length > 0) return;
        const backendDefaults = metadata.default_filters || {};
        const hardcodedDefaults = getDefaultFilters(entityName);
        if (Object.keys(backendDefaults).length > 0 && Object.keys(hardcodedDefaults).length === 0) {
            setFilterParams(normalizeFilterValues(backendDefaults));
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

    const updateInvoiceNo = useUpdateBoeInvoiceNo(invalidateList);
    const bulkUpdateProductNames = useBulkUpdateProductNames();

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
        setFilterParams(normalizeFilterValues(filters));
        setCurrentPage(1);
    }, []);

    useEffect(() => {
        // Keep every list's current search and filters in the URL.  The old
        // allotments-only synchronizer dropped `search` as soon as a user
        // paged or changed a filter on Licences, BOEs, Trades, or another
        // master list, leaving the visible search box disconnected from the
        // query.  All entities now use the same round-trippable state.
        if (!entityName) return;
        const params = new URLSearchParams();
        Object.entries(filterParams).forEach(([key, value]) => {
            if (value !== '' && value != null) params.set(key, String(value));
        });
        params.set('page', String(currentPage));
        // Compare canonical query encodings.  Comparing the raw URL string
        // (`%20`) with URLSearchParams output (`+`) can otherwise call
        // replace() forever without changing any actual filter state.
        params.sort();
        const nextSearch = params.toString();
        const current = new URLSearchParams(location.search);
        current.sort();
        if (nextSearch !== current.toString()) {
            ownSearchWrite.current = `${entityName}|${nextSearch}`;
            navigate({ search: nextSearch }, { replace: true });
        }
    }, [entityName, filterParams, currentPage, location.search, navigate]);

    const handlePageChange = (page) => {
        setCurrentPage(page);
    };

    const handlePageSizeChange = (size) => {
        setPageSize(size);
        setCurrentPage(1);
    };

    const handleDelete = async (item) => {
        // A paired trade cannot be deleted directly (the server refuses it).
        // Delete it through the unpair endpoint, which keeps the counterpart
        // as a standalone trade.
        if (entityName === 'trades' && (item.counterpart_id || item.counterpart_info)) {
            const counterpartLabel = item.direction === 'SALE' ? 'Purchase' : 'Sale';
            const thisLabel = item.direction === 'SALE' ? 'Sale' : 'Purchase';
            const confirmedUnpair = await confirmDangerousAction(
                `Delete ${thisLabel} and unlink`,
                `This ${thisLabel} is paired with a linked ${counterpartLabel}. Delete this ${thisLabel} and unlink it, and keep the ${counterpartLabel} as a standalone trade?`,
            );
            if (!confirmedUnpair) {
                return;
            }
            try {
                await api.post(`trades/${item.id}/unpair-and-delete/`);
                toast.success(`${thisLabel} deleted; linked ${counterpartLabel} kept`);
                invalidateList();
                return;
            } catch (err) {
                toast.error(err.response?.data?.error || err.response?.data?.detail || 'Failed to delete trade');
                return;
            }
        }

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
                    apiPath = `masters/${entityName}/${getMasterRecordKey(entityName, item)}/`;
                }
                await api.delete(apiPath);
            }
            toast.success("Record deleted successfully");
            invalidateList();
        } catch (err) {
            toast.error(err.response?.data?.detail || "Failed to delete record");
        }
    };

    // Generic master bulk actions: one request, per-record results (backend: core/services/master_bulk.py).
    const handleMasterBulk = useCallback(async (action: MasterBulkAction, keys: string[]): Promise<MasterBulkResult> => {
        try {
            const { data: result } = await api.post<MasterBulkResult>(`masters/${entityName}/bulk/`, { action, keys });
            if (result.failed === 0) toast.success(`${result.succeeded} ${result.succeeded === 1 ? "record" : "records"} updated`);
            else toast.warning(`${result.succeeded} of ${result.requested} done — ${result.failed} not changed`);
            return result;
        } catch (err) {
            toast.error(err.response?.data?.detail || err.response?.data?.keys?.[0] || err.response?.data?.action?.[0] || "Bulk action failed; nothing was changed");
            return { action, requested: keys.length, succeeded: 0, failed: keys.length, results: keys.map(key => ({ key, ok: false, error: "Request failed." })) };
        } finally {
            invalidateList();
            qc.invalidateQueries({ queryKey: ['master-count', entityName] });
            qc.invalidateQueries({ queryKey: ['master-record', entityName] });
        }
    }, [entityName, invalidateList, qc]);

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
                apiPath = `masters/${entityName}/${getMasterRecordKey(entityName, item)}/`;
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
                // Tables pass only `id`; code-keyed masters are addressed by code.
                const row = (data || []).find((d) => d.id === itemId) ?? { id: itemId };
                apiPath = `masters/${entityName}/${getMasterRecordKey(entityName, row)}/`;
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

    // Entities rendered with the compact register toolbar (breadcrumb + h1 + actions inside the filter bar).
    // Registered generic masters use the licence register toolbar too, under a "Masters" breadcrumb.
    const registeredMaster = masterEntities.find(m => m.entity === entityName);
    const isCompactRegister = !!entityName && (COMPACT_REGISTER.has(entityName) || !!registeredMaster);
    const breadcrumbParent = registeredMaster ? { label: "Masters", to: "/masters" } : { label: "Home", to: "/" };
    const entityTitles: Record<string, string> = {
        "bill-of-entries": "Bills of Entry",
    };
    const entityTitle = (entityName && entityTitles[entityName]) || registeredMaster?.label || entityName
        ?.split("-")
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");
    const entityDescriptions: Record<string, string> = {
        licenses: "Review license balances, planning, and utilization",
        allotments: "Manage allocations and track license usage",
        "incentive-licenses": "Review incentive balances, expiry, and utilization",
        "bill-of-entries": "Manage import entries, invoices, and product details",
        trades: "Manage linked purchase and sale transactions",
    };
    const workspaceDescription = entityName
        ? (entityDescriptions[entityName] || `Manage ${entityTitle?.toLowerCase()} records`)
        : "Manage records and operational data";

    const handleBulkUpdateProductNames = async () => {
        const confirmed = await confirmDangerousAction(
            'Bulk Update Product Names',
            'This will update product names for ALL BOEs with empty product_name in the entire database. This may take some time. Continue?'
        );
        if (!confirmed) return;
        setBulkActionLoading(true); setError("");
        try {
            const data = await bulkUpdateProductNames.mutateAsync();
            if (data.success) {
                toast.success(data.message || `Processed ${data.total} BOEs: ${data.updated} updated, ${data.skipped} skipped`);
                invalidateList();
            } else {
                setError('Failed to update product names');
            }
        } catch (err) {
            const message = boeApiTyped.extractBoeError(err, 'Failed to update product names');
            setError(message);
            toast.error(message);
        } finally {
            setBulkActionLoading(false);
        }
    };

    const headerActions = (
                    <>
                        <Button variant="outline" size="sm" onClick={() => handleExport('xlsx')} title="Export to Excel" aria-label="Export to Excel">
                            <FileSpreadsheet className="size-3.5" aria-hidden="true" />
                            <span className="hidden sm:inline">Excel</span>
                        </Button>
                        <Button variant="outline" size="sm" onClick={() => handleExport('pdf')} title="Export to PDF" disabled={pdfLoading} aria-label={pdfLoading ? "Generating PDF export" : "Export to PDF"}>
                            {pdfLoading ? <Loader2 className="size-3.5 animate-spin" aria-hidden="true" /> : <FileText className="size-3.5" aria-hidden="true" />}
                            <span className="hidden sm:inline">{pdfLoading ? "Generating…" : "PDF"}</span>
                        </Button>
                        {entityName === 'bill-of-entries' && (
                            <ActionMenu
                                label="More bill of entry actions"
                                items={[
                                    {
                                        id: "boe-port-excel",
                                        label: "Port-wise Excel",
                                        icon: FileSpreadsheet,
                                        onSelect: () => { void handlePortExcelExport(); },
                                    },
                                    {
                                        id: "boe-bulk-update-product-names",
                                        label: "Update all empty product names",
                                        icon: RefreshCw,
                                        tone: "danger",
                                        separatorBefore: true,
                                        disabled: bulkActionLoading,
                                        disabledReason: "Product name update in progress",
                                        onSelect: () => { void handleBulkUpdateProductNames(); },
                                    },
                                ]}
                            />
                        )}
                        {canWrite && (
                            <Button asChild size="sm">
                                <Link
                                    to={entityName === 'licenses' ? '/licenses/create' :
                                        entityName === 'allotments' ? '/allotments/create' :
                                        entityName === 'trades' ? '/trades/create' :
                                        entityName === 'bill-of-entries' ? '/bill-of-entries/create' :
                                        `/masters/${entityName}/create`}
                                    onClick={() => {
                                        saveFilterState(entityName, {
                                            filters: filterParams,
                                            pagination: { currentPage, pageSize },
                                            search: ''
                                        });
                                    }}
                                    aria-label="Add New"
                                    title="Add New"
                                >
                                    <Plus className="size-3.5" aria-hidden="true" />
                                    <span className="hidden sm:inline">Add New</span>
                                </Link>
                            </Button>
                        )}
                    </>
    );

    return (
        <div className="min-h-screen bg-background">
            {/* Unified PageHeader for all master entities */}
            {!isCompactRegister && <PageHeader
                pretitle={
                    <>
                        <a
                            href="/"
                            onClick={(e) => { e.preventDefault(); navigate('/'); }}
                            className="text-inherit no-underline hover:underline"
                        >
                            Home
                        </a>
                        <span className="mx-1.5 opacity-50">/</span>
                        <span>{entityTitle}</span>
                    </>
                }
                title={entityTitle}
                description={
                    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
                        <span className="font-medium text-foreground">{workspaceDescription}</span>
                        <span aria-hidden="true" className="text-border">•</span>
                        <span className="tabular-nums text-muted-foreground">{totalRecords.toLocaleString("en-IN")} record{totalRecords === 1 ? "" : "s"}</span>
                        {isRefreshing && <span role="status" className="text-muted-foreground">Updating…</span>}
                    </div>
                }
                actions={headerActions}
            />}

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
                {...(isCompactRegister ? {
                    collapsible: true,
                    layout: 'grid' as const,
                    toolbarStart: (
                        <div className="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-0.5">
                            <nav aria-label="Breadcrumb" className="text-xs text-muted-foreground">
                                <a href={breadcrumbParent.to} onClick={(e) => { e.preventDefault(); navigate(breadcrumbParent.to); }} className="text-inherit no-underline hover:underline">{breadcrumbParent.label}</a>
                                <span className="mx-1.5 opacity-50">/</span>
                                <span>{entityTitle}</span>
                            </nav>
                            <h1 className="text-lg font-semibold leading-tight tracking-tight text-foreground">{entityTitle}</h1>
                            <span className="text-xs tabular-nums text-muted-foreground">{totalRecords.toLocaleString("en-IN")} record{totalRecords === 1 ? "" : "s"}</span>
                        </div>
                    ),
                    toolbarEnd: headerActions,
                } : {})}
            />

            {/* Active Filters Display */}
            <MasterListActiveFiltersDisplay
                filterParams={filterParams}
                defaultFilters={entityName === 'allotments' ? getDefaultFilters(entityName) : (metadata.default_filters || {})}
                filterConfig={metadata.filter_config || {}}
                onFilterChange={handleFilterChange}
            />

            {/* Table */}
            <div className={cn("surface-card mt-4", isCompactRegister && "mt-3 overflow-hidden border-border/70 shadow-sm")}>
                <div className={cn("p-3.5", isCompactRegister && "p-2 sm:p-3")}>
                    {isRefreshing && !loading && (
                        <div role="status" className="mb-2 text-xs text-muted-foreground">Updating results…</div>
                    )}
                    {/* BOE compact data table */}
                    {entityName === 'bill-of-entries' && (
                        <BoeTable
                            loading={loading}
                            data={data}
                            canWrite={canWrite}
                            canEditInvoice={canEditInvoice}
                            canTransferLetter={canTransferLetter}
                            entityName={entityName}
                            filterParams={filterParams}
                            currentPage={currentPage}
                            pageSize={pageSize}
                            navigate={navigate}
                            onDelete={handleDelete}
                            invalidateList={invalidateList}
                            confirmDangerousAction={confirmDangerousAction}
                            onTransferLetter={(id) => { setTransferLetterType('boe'); setTransferLetterEntityId(id); setShowTransferLetterModal(true); }}
                            onMerge={openMergeModal}
                            editingInvoiceId={editingInvoiceId}
                            invoiceDraft={invoiceDraft}
                            setInvoiceDraft={setInvoiceDraft}
                            invoiceSaving={updateInvoiceNo.isPending}
                            startInvoiceEdit={startInvoiceEdit}
                            cancelInvoiceEdit={cancelInvoiceEdit}
                            saveInvoiceEdit={saveInvoiceEdit}
                        />
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
                                    showIf: () => canTransferLetter,
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
                                            const data = await boeApiTyped.updateProductName(item.id);
                                            toast.success(data.message || 'Product name updated successfully');
                                            // Refresh the list to show updated product name
                                            invalidateList();
                                        } catch (err) {
                                            toast.error(boeApiTyped.extractBoeError(err, 'Failed to update product name'));
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
                            canWrite={canWrite}
                            onBulk={handleMasterBulk}
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
                    mergeError={mergeError}
                    doMerge={doMerge}
                />
            )}

        </div>
    );
}

/**
 * ActiveFilters display for MasterList using AdvancedFilter
 * Converts API params (with __gte, __lte suffixes) to human-readable filter items
 */
function MasterListActiveFiltersDisplay({
    filterParams,
    defaultFilters,
    filterConfig,
    onFilterChange,
}: {
    filterParams: Record<string, any>;
    defaultFilters: Record<string, any>;
    filterConfig: Record<string, any>;
    onFilterChange: (params: Record<string, any>) => void;
}) {
    const activeFilters: ActiveFilterItem[] = useMemo(() => {
        const items: ActiveFilterItem[] = [];

        Object.entries(filterParams).forEach(([key, value]) => {
            // Skip empty values and defaults
            if (value === null || value === undefined || value === '' || value === false) {
                return;
            }

            const defaultValue = defaultFilters[key];
            if (defaultValue !== undefined && value === defaultValue) {
                return;
            }

            // Get field config for display
            const fieldConfig = Object.values(filterConfig).find(
                (f: any) => f.name === key || f.name?.replace(/__?(gte|lte|icontains|exact)$/i, '') === key
            ) as any;

            // Humanize field name
            const label = fieldConfig?.label || key
                .replace(/__?(gte|lte|icontains|exact)$/i, '')
                .replace(/_/g, ' ')
                .replace(/\b\w/g, (c) => c.toUpperCase());

            items.push({
                key,
                label,
                value: String(value),
            });
        });

        return items;
    }, [filterParams, defaultFilters, filterConfig]);

    // Don't display if no active filters
    if (activeFilters.length === 0) {
        return null;
    }

    return (
        <div className="mt-4 mb-4">
            <ActiveFilters
                filters={activeFilters}
                onRemove={(key) => {
                    const newParams = { ...filterParams };
                    delete newParams[key];
                    onFilterChange(newParams);
                }}
                onClearAll={() => onFilterChange({})}
                showCount={true}
                compact={false}
            />
        </div>
    );
}
