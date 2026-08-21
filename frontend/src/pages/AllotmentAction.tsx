import {useCallback, useEffect, useState, useMemo, useRef} from "react";
import {useParams, useNavigate, useLocation} from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "../api/axios";
import HybridSelect from "../components/HybridSelect";
import ConditionBadge from "../components/ConditionBadge";
import TransferLetterForm from "../components/TransferLetterForm";
import {openPdfPreview} from "../utils/pdfPreview";
import {useBackButton} from "../hooks/useBackButton";
import {usePurchaseStatusOptions} from "../hooks/useMasterOptions";
import {formatDate} from "../utils/dateFormatter";
import {useDebounce} from "@/hooks/useDebounce";
import AllotmentFilters from "./AllotmentFilters";
import LicensePlanningPanel from "../components/planning/LicensePlanningPanel";
import { ArrowLeft, Building2, Calendar, CheckCircle2, CheckSquare, Clipboard, FileText, Files, Filter, Inbox, Info, ListChecks, Network, PenSquare, StickyNote, Trash2, TriangleAlert, Unlock, X, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import EmptyState from "@/components/EmptyState";

interface PlanningOption {
    plan_line_id: number;
    item_name: string;
    remaining_quantity?: string;
    remaining_cif_fc?: string;
    [key: string]: any;
}
type SearchMode = "PLAN" | "ACTUAL";
type AllocationBasis = "PLAN" | "ACTUAL";
type DebitBasis = SearchMode;

interface AllocationInitialization {
    default_search_mode: SearchMode;
    default_allocation_basis: AllocationBasis;
    default_item: { id: number; name: string } | null;
    planning_target_item: { id: number; name: string } | null;
    sion: string | null;
    has_active_plan: boolean;
    plan_status: string;
    plan_message: string | null;
    reason_code?: string | null;
    message?: string | null;
}

interface AvailableItem {
    id: number;
    license_id?: number;
    license?: number;
    license_number: string;
    serial_number: string | number;
    condition_type?: string;
    hs_code_label?: string;
    notification_number?: string;
    license_expiry_date?: string;
    description: string;
    exporter_name?: string;
    items_detail?: Array<{ id?: number; name: string }>;
    available_quantity: string;
    balance_cif_fc: string;
    // Utilization-plan status for this item's product group (always present;
    // the numeric fields are only set when has_plan is true). Original = the
    // Plan tab / auto-plan cap (immutable from allotment code). Used = live
    // sum of existing allotments for the group. Remaining = Original − Used
    // — recomputed on every fetch, so it reflects allotment create/delete/edit
    // automatically with no client-side bookkeeping.
    has_plan?: boolean;
    original_planned_quantity?: string;
    used_planned_quantity?: string;
    remaining_planned_quantity?: string;
    original_planned_cif_fc?: string;
    used_planned_cif_fc?: string;
    remaining_planned_cif_fc?: string;
    has_active_plan?: boolean;
    remaining_planned_qty?: string;
    remaining_planned_cif?: string;
    display_plan_qty?: string;
    display_plan_cif?: string;
    max_allotment_qty?: string;
    max_allotment_cif?: string;
    can_create_allotment?: boolean;
    reason_code?: string | null;
    message?: string | null;
    actual_position?: { available_qty: string; balance_cif: string };
    plan_position?: { exists: boolean; is_active: boolean; status: string; plan_line_id: number | null; remaining_qty: string; remaining_cif: string };
    basis_options?: Record<"actual" | "plan", {
        enabled: boolean;
        max_qty: string;
        max_cif: string;
        allocation_limit?: { paired_max_qty: string; paired_max_cif: string; limiting_factor: string; can_allocate: boolean };
        reason_code?: string | null;
        message?: string | null;
    }>;
    // Plan mode (Debit Based On = Plan) only — one row per LicenseItemPlan
    // line. `id` is the plan line's own id (unique per split row); the real
    // underlying import item is `import_item_id` — the Confirm-allot payload
    // must submit that, never the plan line's id. `available_quantity`/
    // `balance_cif_fc` above are ALIASED to this row's own planned amount in
    // Plan mode (see backend `_available_licenses_plan_mode`), so this
    // interface's existing fields already cover display; these two are only
    // needed for submission + the new "Planned Item Name" column.
    import_item_id?: number;
    planned_item_name?: string;
    // Item-specific planning splits (DWP, SWP, PKO, etc.)
    // Only present when the item has planning relationships
    planning_options?: PlanningOption[];
}

function getAllocationErrorMessage(error: unknown): string {
    const data = (error as any)?.response?.data ?? error as any;
    const item = data?.item_name;
    if (data?.code === "NO_PLANNED_BALANCE") return `Cannot allocate ${item || "this item"}: no planned quantity or value remains.`;
    return data?.message || data?.detail || data?.error || data?.errors?.[0]?.message || data?.errors?.[0]?.error || "The allocation could not be completed.";
}

export default function AllotmentAction({ allotmentId: propId, isModal = false, onClose }) {
    const {id: paramId} = useParams();
    const navigate = useNavigate();
    const location = useLocation();
    const qc = useQueryClient();

    // Use prop ID if provided (for modal), otherwise use URL param (for page)
    const id = propId || paramId;

    const [allocationData, setAllocationData] = useState({});
    // When an allot is rejected for exceeding the utilization plan, we stash the
    // item here so the planning panel can open and retry the allot after editing.
    const [planModal, setPlanModal] = useState(null);
    const [filters, setFilters] = useState({
        description: "",
        exporter: "",
        exclude_exporter: "",
        license_number: "",
        available_quantity_gte: "50",
        available_quantity_lte: "",
        available_value_gte: "100",
        available_value_lte: "",
        notification_number: "",
        norm_class: "",
        hs_code: "",
        is_expired: "all",
        is_restricted: "all",
        // Purchase Status default is applied once the master data loads
        // (see the usePurchaseStatusOptions effect below) — never hardcoded.
        purchase_status: "",
        license_status: "active",
        item_id: "",
        expiry_date_from: "",
        expiry_date_to: "",
        // Plan balances are the safe default; Actual is an explicit override.
        // or 'plan' (one row per LicenseItemPlan line — see AvailableItem's
        // planned_item_name/import_item_id fields).
        debit_based_on: null as DebitBasis | null
    });
    // Purchase Status options + default selection both come from the
    // Purchase Status master (never hardcoded) — see useMasterOptions.ts.
    const { options: purchaseStatusOptions } = usePurchaseStatusOptions();
    const purchaseStatusDefaultApplied = useRef(false);
    useEffect(() => {
        if (!purchaseStatusDefaultApplied.current && purchaseStatusOptions.length > 0) {
            purchaseStatusDefaultApplied.current = true;
            setFilters(prev => ({...prev, purchase_status: purchaseStatusOptions.map(o => o.value).join(',')}));
        }
    }, [purchaseStatusOptions]);
    const [hydratedRouteId, setHydratedRouteId] = useState<string | number | null>(null);
    const [currentPage, setCurrentPage] = useState(1);
    const pageSize = 20;
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");
    const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

    // A draft is scoped to the selected balance source.  Never let a Qty/CIF
    // entered for one Planning Target be submitted after the target changes.
    const updateFilters = (nextFilters: typeof filters) => {
        if (filters.debit_based_on !== nextFilters.debit_based_on || filters.item_id !== nextFilters.item_id) {
            setAllocationData({});
        }
        setFilters(nextFilters);
    };

    // Keep text inputs responsive while avoiding a full licence-query reload
    // for each character typed into description, licence number, or HS code.
    const debouncedDescription = useDebounce(filters.description, 400);
    const debouncedLicenseNumber = useDebounce(filters.license_number, 400);
    const debouncedHsCode = useDebounce(filters.hs_code, 400);

    // Confirm dialogs (replaces window.confirm)
    const [deleteConfirm, setDeleteConfirm] = useState<{ show: boolean; allotmentItemId: number | null }>({ show: false, allotmentItemId: null });
    const [copyConfirm, setCopyConfirm] = useState(false);

    // Enable browser back button support with filter preservation
    useBackButton('allotments', !isModal);

    // ---------------------------------------------------------------------------
    // Queries
    // ---------------------------------------------------------------------------

    // Notification options — quasi-static, no need to re-fetch per session
    const { data: rawNotificationOptions = [] } = useQuery({
        queryKey: ['allotments-notification-options'],
        queryFn: () =>
            api.get('masters/notification-numbers/', { params: { page_size: 200, ordering: 'code' } })
               .then(r => (r.data?.results ?? r.data ?? []).map(({ code, label }) => ({
                   value: code,
                   display_name: label ? `${code} — ${label}` : code,
               }))),
        staleTime: Infinity,
    });
    const notificationOptions = rawNotificationOptions;

    // Available item names — quasi-static per session
    const { data: rawItemNames = [] } = useQuery({
        queryKey: ['allotments-item-names'],
        queryFn: () =>
            api.get('item-report/available-items/').then(r =>
                (r.data || []).map((item: { id: unknown; name: string }) => ({ value: item.id, label: item.name }))
            ),
        staleTime: Infinity,
    });
    const availableItemNames = rawItemNames;

    // Planned Item Name options (Plan mode filter) — item names actually
    // used as a planning-item target on at least one LicenseItemPlan line.
    const { data: rawPlannedItemNames = [] } = useQuery({
        queryKey: ['allotments-planned-item-names'],
        queryFn: () =>
            api.get('item-report/planned-item-names/').then(r =>
                (r.data || []).map((item: { id: unknown; name: string }) => ({ value: item.id, label: item.name }))
            ),
        staleTime: Infinity,
    });
    const isPlanMode = filters.debit_based_on === "PLAN";

    // Allotment header info (details, progress, allotted items)
    const {
        data: allotment,
        isError: allotmentFailed,
    } = useQuery({
        queryKey: ['allotments', id, 'info'],
        queryFn: () => api.get(`allotments/${id}/`).then(r => r.data),
        enabled: Boolean(id),
    });

    // The server is authoritative for route defaults.  In particular, a
    // Planning Target Item alone is metadata; it does not prove that a
    // current plan exists for the target and canonical SION.
    const {
        data: allocationInitialization,
        isLoading: initializationLoading,
        isError: initializationFailed,
        refetch: retryInitialization,
    } = useQuery<AllocationInitialization>({
        queryKey: ['allotment-allocation-initialization', id],
        queryFn: () => api.get(`allotment-actions/${id}/allocation-initialization/`).then(r => r.data),
        enabled: Boolean(id),
    });

    const itemFilterOptions = useMemo(() => {
        const options = isPlanMode ? rawPlannedItemNames : availableItemNames;
        if (isPlanMode && allotment?.planning_target_item && !options.some(option => String(option.value) === String(allotment.planning_target_item))) {
            return [{ value: allotment.planning_target_item, label: allotment.planning_target_item_name || String(allotment.planning_target_item) }, ...options];
        }
        return options;
    }, [isPlanMode, rawPlannedItemNames, availableItemNames, allotment]);

    // Do not infer a Plan default from target-item presence.  The backend
    // verifies the current plan identity and supplies the only valid default.
    useEffect(() => {
        if (!allotment || !allocationInitialization || hydratedRouteId === id) return;
        const defaultItem = allocationInitialization.default_item;
        setFilters(prev => ({
            ...prev,
            debit_based_on: allocationInitialization.default_search_mode,
            item_id: defaultItem == null ? "" : String(defaultItem.id),
            // This runs only once per route identity, so later filter edits
            // and allocation refetches remain entirely user-owned.
            description: allotment.item_name || "",
        }));
        setAllocationData({});
        setCurrentPage(1);
        setHydratedRouteId(id);
    }, [allotment, allocationInitialization, hydratedRouteId, id]);

    useEffect(() => {
        // A route change must never reuse an already-hydrated target.
        if (hydratedRouteId != null && hydratedRouteId !== id) {
            setHydratedRouteId(null);
        }
    }, [id, hydratedRouteId]);

    // Surface allotment load failure into the error banner
    useEffect(() => {
        if (allotmentFailed) {
            setError("Failed to load allotment info");
        }
    }, [allotmentFailed]);

    // Build API params from current filter state (skip empty values)
    const apiParams = useMemo(() => {
        const params: Record<string, string | number> = { page: currentPage, page_size: pageSize };
        Object.entries(filters).forEach(([k, v]) => {
            // These free-text filters are attached below from debounced state.
            if (k !== "description" && k !== "license_number" && k !== "hs_code" && v != null && v !== "") {
                params[k] = v as string;
            }
        });
        if (debouncedDescription) params.description = debouncedDescription;
        if (debouncedLicenseNumber) params.license_number = debouncedLicenseNumber;
        if (debouncedHsCode) params.hs_code = debouncedHsCode;
        if (filters.debit_based_on === "PLAN" && filters.item_id) {
            // The filter is the current target.  The route target only
            // supplies the initial selection, never a later override.
            params.planning_target_item_id = filters.item_id;
            if (String(filters.item_id) === String(allocationInitialization?.default_item?.id) && allocationInitialization?.sion) {
                params.sion = allocationInitialization.sion;
            }
        }
        return params;
    }, [filters, currentPage, pageSize, allocationInitialization, debouncedDescription, debouncedLicenseNumber, debouncedHsCode]);

    const planFiltersReady = hydratedRouteId === id
        && filters.debit_based_on === "PLAN";
    // Actual availability does not require a plan or a canonical Planning
    // Target Item.  An actual item identity is ideal, but Item Description is
    // also an established Actual-mode filter (for example, `7607`).
    const actualFiltersReady = hydratedRouteId === id
        && filters.debit_based_on === "ACTUAL"
        && Boolean(filters.item_id || debouncedDescription.trim());
    const filtersReady = planFiltersReady || actualFiltersReady;

    const previousDebitBasis = useRef<DebitBasis | null>(null);
    useEffect(() => {
        const currentDebitBasis = filters.debit_based_on;
        if (!currentDebitBasis) return;
        if (previousDebitBasis.current && previousDebitBasis.current !== currentDebitBasis) {
            // A Plan child is never an implicit selection in Actual mode.
            // Clear drafts as well, so an old Plan response cannot be submitted
            // after the user changes the authoritative mode.
            setAllocationData({});
            setCurrentPage(1);
        }
        previousDebitBasis.current = currentDebitBasis;
    }, [filters.debit_based_on]);

    // Available licenses list — re-fetches when filters or page changes,
    // but only after the first-load description filter has been applied.
    const {
        data: availableLicensesData,
        isLoading: initialLoading,
        isFetching: tableLoading,
    } = useQuery({
        queryKey: ['allotment-available-licenses', id, filters.debit_based_on, allotment?.planning_target_item ?? null, allotment?.planning_target_sion ?? null, apiParams],
        queryFn: () => api.get(`allotment-actions/${id}/available-licenses/`, { params: apiParams }).then(r => r.data),
        enabled: Boolean(id) && filtersReady,
        // Changing a filter should refresh just the results, not blank the
        // workspace and make the page appear to reload.
        placeholderData: (previousData) => previousData,
        refetchOnWindowFocus: false,
    });

    const availableItems: AvailableItem[] = useMemo(
        () => filtersReady ? (availableLicensesData?.available_items ?? availableLicensesData?.results ?? []) : [],
        [filtersReady, availableLicensesData],
    );
    const totalItems: number = availableLicensesData?.count ?? 0;
    const totalPages: number = totalItems > 0 ? Math.ceil(totalItems / pageSize) : 0;

    // Track unsaved changes
    useEffect(() => {
        if (Object.keys(allocationData).length > 0) {
            setHasUnsavedChanges(true);
        } else {
            setHasUnsavedChanges(false);
        }
    }, [allocationData]);

    // Warn user before leaving page with unsaved changes
    useEffect(() => {
        const handleBeforeUnload = (e) => {
            if (hasUnsavedChanges) {
                e.preventDefault();
                e.returnValue = '';
            }
        };
        window.addEventListener('beforeunload', handleBeforeUnload);
        return () => window.removeEventListener('beforeunload', handleBeforeUnload);
    }, [hasUnsavedChanges]);

    // ---------------------------------------------------------------------------
    // Mutations
    // ---------------------------------------------------------------------------

    const invalidateAllotment = () => {
        qc.invalidateQueries({ queryKey: ['allotments', id] });
    };

    const allocateMutation = useMutation({
        mutationFn: (payload: { item: AvailableItem; allocation: { qty: string; cif_fc: string } }) => {
            const followsPlan = filters.debit_based_on === "PLAN";
            // Description-driven Actual searches do not have a filter item ID.
            // The candidate's canonical actual item identity is still sent for
            // backend validation, rather than falling back to a plan identity.
            const actualItemId = filters.item_id || payload.item.items_detail?.[0]?.id;
            return api.post(`allotment-actions/${id}/allocate-items/`, {
                allocations: [{
                    // Plan mode's row id is the LicenseItemPlan line's own id
                    // (unique per split row) — allocation always targets the
                    // real underlying import item, via import_item_id when set.
                    item_id: payload.item.import_item_id ?? payload.item.id,
                    qty: payload.allocation.qty,
                    cif_fc: payload.allocation.cif_fc,
                    // Plan mode only: names the specific plan line (e.g. PKO
                    // vs Cheese) this allocation was made against, so the
                    // backend can decrement THAT line's own remaining balance
                    // independently of its siblings (see allocate_items).
                    ...(followsPlan ? { plan_line_id: payload.item.id } : {}),
                    debit_based_on: filters.debit_based_on,
                    search_mode: filters.debit_based_on,
                    allocation_basis: followsPlan ? "PLAN" : "ACTUAL",
                    ...(filters.debit_based_on === "PLAN" ? { planning_target_item_id: filters.item_id } : { actual_item_id: actualItemId }),
                }],
            }).then(r => r.data);
        },
        onSuccess: (data, { item, allocation }) => {
            if (data.errors && data.errors.length > 0) {
                const firstErr = data.errors[0];
                if (firstErr.plan_exceeded) {
                    setPlanModal({ error: firstErr, item });
                    return;
                }
                const errorMsg = getAllocationErrorMessage(firstErr);
                setError(errorMsg);
                toast.error(errorMsg);
                return;
            }

            const successMsg = `Successfully allocated ${allocation.qty} from ${item.license_number}`;
            setSuccess(successMsg);
            toast.success(successMsg);

            // Clear this item's allocation from local draft state
            setAllocationData(prev => {
                const next = { ...prev };
                delete next[item.id];
                return next;
            });

            // Invalidate so allotment header re-fetches updated balances + available list
            invalidateAllotment();
            qc.invalidateQueries({ queryKey: ['allotment-available-licenses', id] });
            setAllocationData(previous => {
                const next = { ...previous };
                delete next[item.id];
                return next;
            });

            // Scroll to transfer letter if balance is now exactly 0
            if (data.allotment) {
                const requiredQty = parseInt(data.allotment.required_quantity || 0);
                const allotedQty = parseInt(data.allotment.alloted_quantity || 0);
                if (requiredQty > 0 && (requiredQty - allotedQty) === 0) {
                    setTimeout(() => {
                        document.getElementById('transfer-letter-section')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
                    }, 800);
                }
            }
        },
        onError: (err: unknown) => {
            const errorMsg = getAllocationErrorMessage(err);
            setError(errorMsg);
            toast.error(errorMsg);
        },
    });

    const deleteAllocationMutation = useMutation({
        mutationFn: (allotmentItemId: number) =>
            api.delete(`allotment-actions/${id}/delete-item/${allotmentItemId}/`).then(r => r.data),
        onSuccess: (data) => {
            const successMsg = data.message || "Successfully removed allocation";
            setSuccess(successMsg);
            toast.success(successMsg);
            invalidateAllotment();
        },
        onError: (err: unknown) => {
            const errorMsg = (err as { response?: { data?: { error?: string } } }).response?.data?.error || "Failed to delete allocation";
            setError(errorMsg);
            toast.error(errorMsg);
        },
    });

    // Scroll to transfer letter section if navigated from list
    useEffect(() => {
        if (location.state?.scrollToTransferLetter && allotment) {
            setTimeout(() => {
                document.getElementById('transfer-letter-section')?.scrollIntoView({ behavior: 'smooth' });
            }, 500);
        }
    }, [location.state, allotment]);

    // Reset to page 1 when filters change
    useEffect(() => {
        setCurrentPage(1);
    }, [filters]);

    const calculateMaxAllocation = useCallback((item) => {
        // One server-generated paired Decimal cap is the only client cap.
        // React may display this value; it must not rebuild it from balances.
        const basis = filters.debit_based_on === "PLAN" ? "plan" : "actual";
        const limit = item.basis_options?.[basis];
        const pair = limit?.allocation_limit;
        return {
            qty: Number(pair?.paired_max_qty ?? "0"),
            value: Number(pair?.paired_max_cif ?? "0"),
            qtyText: pair?.paired_max_qty ?? "0",
            valueText: pair?.paired_max_cif ?? "0",
            enabled: Boolean(limit?.enabled && pair?.can_allocate),
            reasonCode: limit?.reason_code,
            message: limit?.message,
        };
    }, [filters.debit_based_on]);

    // A response/mode change can turn a formerly valid draft into an invalid
    // Plan allocation.  Remove it immediately; never leave a stale raw-value
    // draft available for Confirm.
    useEffect(() => {
        setAllocationData(previous => {
            let changed = false;
            const next = { ...previous };
            availableItems.forEach(item => {
                const max = calculateMaxAllocation(item);
                const draft = next[item.id];
                if (draft && (max.qty <= 0 || max.value <= 0 || Number(draft.qty) > max.qty || Number(draft.cif_fc) > max.value)) {
                    delete next[item.id];
                    changed = true;
                }
            });
            return changed ? next : previous;
        });
    }, [filters.debit_based_on, availableItems, calculateMaxAllocation]);

    const handleQuantityChange = (itemId, qty) => {
        const item = availableItems.find(i => i.id === itemId);
        if (!item || !calculateMaxAllocation(item).enabled) return;
        // Keep manual input intact. The locked server mutation validates the
        // Qty/CIF pair and reports any stale or over-cap value precisely.
        setAllocationData(previous => ({
            ...previous,
            [itemId]: { qty, cif_fc: previous[itemId]?.cif_fc || "" },
        }));
    };

    const handleValueChange = (itemId, value) => {
        const item = availableItems.find(i => i.id === itemId);
        if (!item || !calculateMaxAllocation(item).enabled) return;
        setAllocationData(previous => ({
            ...previous,
            [itemId]: { qty: previous[itemId]?.qty || "", cif_fc: value },
        }));
    };

    const handleMaxQuantity = (item) => {
        const maxAllocation = calculateMaxAllocation(item);
        if (!maxAllocation.enabled) return;
        setAllocationData({...allocationData, [item.id]: {qty: maxAllocation.qtyText, cif_fc: maxAllocation.valueText}});
    };

    const handleMaxValue = (item) => {
        const maxAllocation = calculateMaxAllocation(item);
        if (!maxAllocation.enabled) return;
        setAllocationData({...allocationData, [item.id]: {qty: maxAllocation.qtyText, cif_fc: maxAllocation.valueText}});
    };

    const handleConfirmAllot = (item) => {
        const max = calculateMaxAllocation(item);
        if (max.qty <= 0 || max.value <= 0) {
            const itemName = item.planned_item_name || item.description;
            const message = max.message || `Cannot allocate ${itemName}: no available quantity or value remains.`;
            setError(message);
            toast.error(message);
            return;
        }
        const allocation = allocationData[item.id];
        if (!allocation || parseFloat(allocation.qty) <= 0 || parseFloat(allocation.cif_fc) <= 0) {
            toast.error("Enter a positive quantity and CIF value.");
            setError("Enter a positive quantity and CIF value.");
            return;
        }
        setError("");
        setSuccess("");
        allocateMutation.mutate({ item, allocation });
    };

    const handleDeleteAllotment = (allotmentItemId) => {
        setDeleteConfirm({ show: true, allotmentItemId });
    };

    const confirmDelete = () => {
        if (deleteConfirm.allotmentItemId == null) return;
        setError("");
        setSuccess("");
        deleteAllocationMutation.mutate(deleteConfirm.allotmentItemId);
        setDeleteConfirm({ show: false, allotmentItemId: null });
    };

    if (initialLoading || initializationLoading) return (
        <div className="min-h-screen bg-background">
            <div className="flex justify-between items-center mb-4 animate-pulse">
                <div>
                    <div className="h-7 w-48 rounded-md bg-muted block"></div>
                    <div className="h-3.5 w-32 rounded bg-muted mt-1 block"></div>
                </div>
                <div className="flex gap-2">
                    {[80, 90, 110, 90, 100].map((w, i) => (
                        <div key={i} className="h-8 rounded-md bg-muted" style={{ width: w }}></div>
                    ))}
                </div>
            </div>
            <div className="mb-3 overflow-hidden rounded-xl border border-border bg-card">
                <div className="border-b border-border/60 px-5 py-3">
                    <div className="h-4 w-1/3 rounded bg-muted"></div>
                </div>
                <div className="flex gap-3 p-5">
                    {[1,2,3,4].map(i => <div key={i} className="flex-1 h-[72px] rounded-lg bg-muted"></div>)}
                </div>
            </div>
            <div className="overflow-hidden rounded-xl border border-border bg-card">
                <div className="border-b border-border/60 px-5 py-3">
                    <div className="h-4 w-1/4 rounded bg-muted"></div>
                </div>
                <div className="p-5 space-y-2">
                    {[1,2,3].map(i => <div key={i} className="h-[90px] rounded-lg bg-muted"></div>)}
                </div>
            </div>
        </div>
    );

    if (initializationFailed) return (
        <div className="min-h-screen bg-muted/40 p-6" role="alert">
            <div className="max-w-xl rounded-xl border border-destructive/30 bg-card p-5 text-sm">
                <h1 className="font-semibold text-foreground">Unable to load allocation rules. Retry before selecting licences.</h1>
                <button
                    type="button"
                    onClick={() => retryInitialization()}
                    className="mt-3 rounded bg-primary px-3 py-2 text-primary-foreground"
                >
                    Retry
                </button>
            </div>
        </div>
    );

    return (
        <div className={cn(
            "flex flex-col",
            isModal ? "h-full" : "min-h-screen p-6 bg-muted/40"
        )}>
            {!isModal && (
                <div className="flex justify-between items-center flex-wrap gap-2 mb-4">
                    <div>
                        <h4 className="font-bold text-foreground flex items-center gap-1.5">
                            <Network className="size-4" aria-hidden="true" />
                            Allocate License Items
                        </h4>
                        {allotment && (
                            <small className="text-muted-foreground">
                                {allotment.item_name}
                                {allotment.invoice && <span className="ml-2">— Invoice #{allotment.invoice}</span>}
                            </small>
                        )}
                    </div>
                    <div className="flex gap-2 flex-wrap">
                        <button
                            className="flex items-center gap-1.5 rounded border border-border bg-card px-2.5 py-1.5 text-xs font-medium text-muted-foreground cursor-pointer hover:bg-muted"
                            onClick={() => {
                                if (isModal && onClose) { onClose(); }
                                sessionStorage.setItem('allotmentListFilters', JSON.stringify({ returnTo: 'edit', timestamp: new Date().getTime() }));
                                navigate(`/allotments/${id}/edit`);
                            }}
                            title="Edit Allotment"
                        >
                            <PenSquare className="size-4" aria-hidden="true" />Edit
                        </button>
                        <button
                            className="flex items-center gap-1.5 rounded border border-border bg-card px-2.5 py-1.5 text-xs font-medium text-muted-foreground cursor-pointer hover:bg-muted"
                            onClick={() => setCopyConfirm(true)}
                            title="Create a copy of this allotment"
                        >
                            <Files className="size-4" aria-hidden="true" />Copy
                        </button>
                        <button
                            className="flex items-center gap-1.5 rounded bg-primary px-2.5 py-1.5 text-xs font-medium text-primary-foreground cursor-pointer hover:bg-primary/90"
                            onClick={async () => {
                                try {
                                    const response = await api.get(`allotment-actions/${id}/generate-pdf/`, { responseType: 'blob' });
                                    const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
                                    const link = document.createElement('a');
                                    link.href = url;
                                    link.setAttribute('download', `Allotment - ${allotment?.invoice || id}.pdf`);
                                    document.body.appendChild(link);
                                    link.click();
                                    link.remove();
                                    window.URL.revokeObjectURL(url);
                                } catch (err) {
                                    setError('Failed to download PDF');
                                }
                            }}
                            title="Download Allotment PDF"
                        >
                            <FileText className="size-4" aria-hidden="true" />Download PDF
                        </button>
                        {allotment && allotment.allotment_details && allotment.allotment_details.length > 0 && (
                            <button
                                className="flex items-center gap-1.5 rounded border border-border bg-card px-2.5 py-1.5 text-xs font-medium text-muted-foreground cursor-pointer hover:bg-muted"
                                onClick={() => document.getElementById('transfer-letter-section')?.scrollIntoView({ behavior: 'smooth' })}
                                title="Generate Transfer Letter"
                            >
                                <FileText className="size-4" aria-hidden="true" />Transfer Letter
                            </button>
                        )}
                        <button
                            className="flex items-center gap-1.5 rounded border border-border bg-card px-2.5 py-1.5 text-xs font-medium text-muted-foreground cursor-pointer hover:bg-muted"
                            onClick={() => {
                                sessionStorage.setItem('allotmentListFilters', JSON.stringify({ returnTo: 'list', timestamp: new Date().getTime() }));
                                navigate('/allotments');
                            }}
                        >
                            <ArrowLeft className="size-4" aria-hidden="true" />Back
                        </button>
                    </div>
                </div>
            )}

            {/* Scrollable content area */}
            <div className="flex-1 overflow-y-auto pr-2">

            {allotment && (() => {
                const unitPrice = parseFloat(allotment.unit_value_per_unit || 0);
                const requiredQty = parseInt(allotment.required_quantity || 0);
                const requiredValue = parseFloat(allotment.required_value || 0);
                const allotedQty = parseInt(allotment.alloted_quantity || 0);
                const allotedValue = parseFloat(allotment.allotted_value || 0);
                const balanceQty = parseFloat(allotment.balanced_quantity || 0);
                const balanceValue = requiredValue - allotedValue;
                const progressPct = requiredQty > 0 ? Math.min(100, Math.round((allotedQty / requiredQty) * 100)) : 0;
                const isComplete = progressPct >= 100;
                const progressBarCls = isComplete ? 'bg-success' : progressPct >= 60 ? 'bg-primary' : 'bg-warning';
                const progressTextCls = isComplete ? 'text-success' : progressPct >= 60 ? 'text-primary' : 'text-warning';
                const statusBadgeCls = isComplete
                    ? 'bg-success/10 text-success'
                    : progressPct >= 60
                    ? 'bg-primary/10 text-primary'
                    : 'bg-warning/10 text-warning';

                return (
                    <div className="mb-4 overflow-hidden rounded-xl border border-border bg-card shadow-sm">
                        {/* Header */}
                        <div className="flex items-center justify-between border-b border-border/60 px-5 py-3">
                            <div className="flex items-center gap-3">
                                <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-primary/10 border border-primary/20">
                                    <ListChecks className="size-4 text-primary" aria-hidden="true" />
                                </div>
                                <div>
                                    <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Allotment Details</p>
                                    <h3 className="text-sm font-bold leading-tight tracking-tight text-foreground">{allotment.item_name}</h3>
                                </div>
                            </div>
                            <div className="flex items-center gap-3">
                                <div className="flex items-center gap-2">
                                    <div className="h-1.5 w-24 overflow-hidden rounded-full bg-muted">
                                        <div className={cn("h-full rounded-full transition-[width] duration-500", progressBarCls)} style={{ width: `${progressPct}%` }} />
                                    </div>
                                    <span className={cn("text-xs font-bold tabular-nums", progressTextCls)}>{progressPct}%</span>
                                </div>
                                <span className={cn("rounded-full px-2.5 py-1 text-[11px] font-semibold leading-none", statusBadgeCls)}>
                                    {isComplete ? '✓ Complete' : 'In Progress'}
                                </span>
                            </div>
                        </div>

                        {/* 4-column stat grid with dividers */}
                        <div className="grid grid-cols-2 divide-y divide-border/40 sm:grid-cols-4 sm:divide-x sm:divide-y-0">
                            {/* Unit Price */}
                            <div className="flex flex-col px-5 py-4">
                                <div className="mb-2 flex items-center gap-1.5">
                                    <span className="size-2 shrink-0 rounded-full bg-info" />
                                    <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Unit Price</span>
                                </div>
                                <span className="text-[1.65rem] font-extrabold leading-none tabular-nums text-info">
                                    {unitPrice.toFixed(3)}
                                </span>
                                <span className="mt-1.5 text-[11px] text-muted-foreground">USD per unit</span>
                            </div>

                            {/* Required */}
                            <div className="flex flex-col px-5 py-4">
                                <div className="mb-2 flex items-center gap-1.5">
                                    <span className="size-2 shrink-0 rounded-full bg-muted-foreground/40" />
                                    <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Required</span>
                                </div>
                                <span className="text-[1.65rem] font-extrabold leading-none tabular-nums text-foreground">
                                    {requiredQty.toLocaleString()}
                                </span>
                                <span className="mt-1.5 text-[11px] font-semibold text-muted-foreground">
                                    ${requiredValue.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                </span>
                            </div>

                            {/* Allotted */}
                            <div className="flex flex-col px-5 py-4 bg-success/[0.04]">
                                <div className="mb-2 flex items-center gap-1.5">
                                    <span className="size-2 shrink-0 rounded-full bg-success" />
                                    <span className="text-[10px] font-bold uppercase tracking-widest text-success">Allotted</span>
                                </div>
                                <span className="text-[1.65rem] font-extrabold leading-none tabular-nums text-success">
                                    {allotedQty.toLocaleString()}
                                </span>
                                <span className="mt-1.5 text-[11px] font-semibold text-success">
                                    ${allotedValue.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                </span>
                            </div>

                            {/* Balance */}
                            <div className={cn("flex flex-col px-5 py-4", balanceQty <= 0 ? "bg-success/[0.06]" : "bg-primary/10")}>
                                <div className="mb-2 flex items-center gap-1.5">
                                    <span className={cn("size-2 shrink-0 rounded-full", balanceQty <= 0 ? "bg-success" : "bg-primary")} />
                                    <span className={cn("text-[10px] font-bold uppercase tracking-widest", balanceQty <= 0 ? "text-success" : "text-primary")}>Balance</span>
                                </div>
                                <span className={cn("text-[1.65rem] font-extrabold leading-none tabular-nums", balanceQty <= 0 ? "text-success" : "text-primary")}>
                                    {balanceQty.toLocaleString()}
                                </span>
                                <span className={cn("mt-1.5 text-[11px] font-semibold", balanceQty <= 0 ? "text-success" : "text-primary")}>
                                    ${balanceValue.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                    <span className="ml-1 font-normal opacity-50">+$20 buf</span>
                                </span>
                            </div>
                        </div>
                    </div>
                );
            })()}

            {/* Allotted Items Table */}
            {allotment && allotment.allotment_details && allotment.allotment_details.length > 0 && (
                <div className="mb-3 overflow-hidden rounded-xl border border-border bg-card shadow-sm">
                    <div className="flex justify-between items-center border-b border-border/60 px-5 py-3">
                        <h6 className="font-semibold text-foreground flex items-center gap-1.5">
                            <CheckSquare className="size-4" aria-hidden="true" />
                            Allotted Items
                            <span className="ml-1 rounded-full bg-success/10 px-2 py-0.5 text-[11px] font-bold text-success">{allotment.allotment_details.length}</span>
                        </h6>
                        <button
                            className="flex items-center gap-1.5 rounded border border-border bg-card px-2.5 py-1.5 text-xs font-medium text-muted-foreground cursor-pointer hover:bg-muted"
                            onClick={() => {
                                    const headers = ['License', 'Serial', 'Description', 'HSN Code', 'Exporter', 'Transfer Status', 'License Date', 'Expiry Date', 'Allotted Qty', 'Allotted Value'];
                                    const rows = allotment.allotment_details.map(detail => {
                                        const transferInfo = [detail.current_owner, detail.file_transfer_status].filter(Boolean).join(' - ') || '-';
                                        return [
                                            detail.license_number,
                                            detail.serial_number,
                                            detail.product_description,
                                            detail.hs_code || '-',
                                            detail.exporter,
                                            transferInfo,
                                            detail.license_date,
                                            detail.license_expiry,
                                            parseInt(detail.qty || 0).toLocaleString(),
                                            parseFloat(detail.cif_fc || 0).toFixed(2)
                                        ];
                                    });
                                    if (allotment.allotment_details.length > 1) {
                                        rows.push([
                                            '', '', '', '', '', '', '', 'Total DFIA allocation',
                                            parseInt(allotment.alloted_quantity || 0).toLocaleString(),
                                            `$${parseFloat(allotment.allotted_value || 0).toLocaleString('en-US', {
                                                minimumFractionDigits: 2,
                                                maximumFractionDigits: 2,
                                            })}`,
                                        ]);
                                    }
                                    const tsv = [headers.join('\t'), ...rows.map(row => row.join('\t'))].join('\n');
                                    navigator.clipboard.writeText(tsv).then(() => {
                                        toast.success('Copied to clipboard!');
                                    }).catch(() => {
                                        toast.error('Failed to copy');
                                    });
                                }}
                                title="Copy table data to clipboard"
                            >
                                <Clipboard className="size-4" aria-hidden="true" /> Copy
                            </button>
                    </div>
                    <div>
                        <div className="overflow-x-auto">
                            <table className="w-full text-sm">
                                <thead className="bg-muted/40 border-b-2 border-border">
                                <tr>
                                    <th scope="col" className="min-w-[120px] whitespace-nowrap font-semibold text-[12px] p-2">License</th>
                                    <th scope="col" className="min-w-[70px] whitespace-nowrap font-semibold text-[12px] p-2">Serial</th>
                                    <th scope="col" className="min-w-[240px] font-semibold text-[12px] p-2">Description</th>
                                    <th scope="col" className="min-w-[80px] whitespace-nowrap font-semibold text-[12px] p-2">HSN Code</th>
                                    <th scope="col" className="min-w-[160px] font-semibold text-[12px] p-2">Exporter</th>
                                    <th scope="col" className="min-w-[140px] font-semibold text-[12px] p-2">Transfer<br/>Status</th>
                                    <th scope="col" className="min-w-[100px] font-semibold text-[13.5px] px-2 py-3">License<br/>Date</th>
                                    <th scope="col" className="min-w-[100px] font-semibold text-[13.5px] px-2 py-3">Expiry<br/>Date</th>
                                    <th scope="col" className="min-w-[80px] text-right font-semibold text-[12px] p-2">Allotted<br/>Qty</th>
                                    <th scope="col" className="min-w-[90px] text-right font-semibold text-[12px] p-2">Allotted<br/>Value</th>
                                    <th scope="col" className="min-w-[64px] whitespace-nowrap font-semibold text-[12px] p-2">Action</th>
                                </tr>
                                </thead>
                                <tbody>
                                {allotment.allotment_details.map((detail) => (
                                    <tr key={detail.id} className="border-b border-border/40 transition-colors hover:bg-muted/30">
                                        <td className="px-3 py-1.5 font-mono text-[12.5px] font-semibold text-foreground whitespace-nowrap overflow-hidden text-ellipsis">{detail.license_number}</td>
                                        <td className="px-3 py-1.5 text-[12.5px] whitespace-nowrap"><span className="font-medium">{detail.serial_number}</span><ConditionBadge type={detail.condition_type} size="xs" /></td>
                                        <td className="px-3 py-1.5 text-[12.5px] break-words whitespace-normal">{detail.product_description}</td>
                                        <td className="px-3 py-1.5 font-mono text-[11.5px] text-muted-foreground whitespace-nowrap">{detail.hs_code || '-'}</td>
                                        <td className="px-3 py-1.5 text-[12.5px] break-words whitespace-normal">{detail.exporter}</td>
                                        <td className="px-3 py-1.5 text-[0.80rem] leading-[1.3] break-words whitespace-normal">
                                            {detail.current_owner && detail.file_transfer_status ? (
                                                <div>
                                                    <div className="mb-1 font-semibold">
                                                        {detail.current_owner}
                                                    </div>
                                                    <div className="text-muted-foreground text-[12px]">
                                                        {detail.file_transfer_status}
                                                    </div>
                                                </div>
                                            ) : detail.current_owner ? (
                                                <div className="font-semibold">{detail.current_owner}</div>
                                            ) : detail.file_transfer_status ? (
                                                <div className="text-muted-foreground">{detail.file_transfer_status}</div>
                                            ) : (
                                                <span className="text-muted-foreground">-</span>
                                            )}
                                        </td>
                                        <td className="px-3 py-1.5 text-[12px] text-muted-foreground whitespace-nowrap">{detail.license_date}</td>
                                        <td className="px-3 py-1.5 text-[12px] text-muted-foreground whitespace-nowrap">{detail.license_expiry}</td>
                                        <td className="px-3 py-1.5 text-right font-semibold tabular-nums text-[12.5px] whitespace-nowrap">{parseInt(detail.qty || 0).toLocaleString()}</td>
                                        <td className="px-3 py-1.5 text-right font-semibold tabular-nums text-[12.5px] whitespace-nowrap">{parseFloat(detail.cif_fc || 0).toFixed(2)}</td>
                                        <td className="px-2 py-1.5 text-center whitespace-nowrap">
                                            <button
                                                className="flex size-7 items-center justify-center rounded border border-destructive/30 text-destructive/70 hover:bg-destructive/10 hover:border-destructive cursor-pointer transition-colors"
                                                onClick={() => handleDeleteAllotment(detail.id)}
                                                disabled={deleteAllocationMutation.isPending && deleteAllocationMutation.variables === detail.id}
                                                title="Remove this allocation"
                                            >
                                                {deleteAllocationMutation.isPending && deleteAllocationMutation.variables === detail.id ? (
                                                    <span className="inline-block size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" />
                                                ) : (
                                                    <Trash2 className="size-4" aria-hidden="true" />
                                                )}
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                                </tbody>
                                {allotment.allotment_details.length > 1 && <tfoot>
                                    <tr className="bg-primary/5 border-t-2 border-primary/30">
                                        <th scope="row" colSpan={8} className="px-3 py-2 text-right text-[11px] font-bold uppercase tracking-wider text-muted-foreground">Total DFIA allocation</th>
                                        <td className="px-3 py-2 text-right text-[13px] font-extrabold tabular-nums text-foreground" aria-label="Total DFIA Quantity">{parseInt(allotment.alloted_quantity || 0).toLocaleString()}</td>
                                        <td className="px-3 py-2 text-right text-[13px] font-extrabold tabular-nums text-foreground" aria-label="Total DFIA Dollar value">${parseFloat(allotment.allotted_value || 0).toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}</td>
                                        <td></td>
                                    </tr>
                                </tfoot>}
                            </table>
                        </div>
                    </div>
                </div>
            )}

            {/* Transfer Letter Generation */}
            {allotment && allotment.allotment_details && allotment.allotment_details.length > 0 && (
                <div id="transfer-letter-section">
                    <TransferLetterForm
                        instanceId={id}
                        instanceType="allotment"
                        items={allotment.allotment_details.map(detail => ({
                            id: detail.id,
                            license_number: detail.license_number || '-',
                            cif_fc: detail.cif_fc || 0,
                            purchase_status: detail.purchase_status || 'N/A'
                        }))}
                        onSuccess={(msg) => toast.success(msg)}
                        onError={(msg) => toast.error(msg)}
                    />
                </div>
            )}

            <div className="mb-4 overflow-hidden rounded-xl border border-border bg-card shadow-sm">
                <div className="flex items-center justify-between border-b border-border/60 px-5 py-3.5">
                    <div className="flex items-center gap-2">
                        <ListChecks className="size-4 text-primary" aria-hidden="true" />
                        <span className="text-sm font-bold tracking-tight text-foreground">Available License Items</span>
                        {totalItems > 0 && (
                            <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-bold text-primary">{totalItems} items</span>
                        )}
                    </div>
                </div>
                <div className="p-5">

                    {allocationInitialization?.plan_status === "AMBIGUOUS_ACTIVE_PLAN" && (
                        <div className="mb-3 flex items-start gap-2 rounded-lg border border-amber-400/40 bg-amber-50 px-3.5 py-2.5 text-[13px] text-amber-900" role="alert">
                            <TriangleAlert className="size-4" aria-hidden="true" />
                            <div>{allocationInitialization.message || allocationInitialization.plan_message}</div>
                        </div>
                    )}

                    {/* Show success/error messages near the table for better visibility */}
                    {error && (
                        <div className="mb-3 flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-[13px] text-destructive" role="alert">
                            <TriangleAlert className="size-4" aria-hidden="true" />
                            <div className="flex-1">{error}</div>
                            <button type="button" className="ml-auto shrink-0 cursor-pointer opacity-60 hover:opacity-100" onClick={() => setError("")}><X className="size-3.5" /></button>
                        </div>
                    )}
                    {success && (
                        <div className="mb-3 flex items-start gap-2 rounded-lg border border-success/30 bg-success/10 px-3.5 py-2.5 text-[13px] text-success" role="alert">
                            <CheckCircle2 className="size-4" aria-hidden="true" />
                            <div className="flex-1">{success}</div>
                            <button type="button" className="ml-auto shrink-0 cursor-pointer opacity-60 hover:opacity-100" onClick={() => setSuccess("")}><X className="size-3.5" /></button>
                        </div>
                    )}

                    <AllotmentFilters
                        filters={filters}
                        setFilters={updateFilters}
                        availableItemNames={itemFilterOptions}
                        notificationOptions={notificationOptions}
                        purchaseStatusOptions={purchaseStatusOptions}
                        routePlanningTarget={null}
                        defaultSearchMode={allocationInitialization?.default_search_mode}
                        defaultItemId={allocationInitialization?.default_item?.id ?? null}
                    />

                    {filtersReady && (
                        <div className="mb-3 rounded-lg border border-primary/25 bg-primary/5 px-3 py-2 text-xs text-primary">
                            {filters.debit_based_on === "PLAN" ? <><strong>PLAN BALANCE MODE</strong> — Available values are based on current remaining planned Qty and CIF.</> : <><strong>ACTUAL BALANCE MODE</strong> — Available values are based on current raw licence-item availability.</>}
                        </div>
                    )}

                    <div className="max-h-[650px] overflow-y-auto pr-px">
                        {(() => {
                            // Group items by license
                            const groupedByLicense: Record<string, AvailableItem[]> = {};
                            availableItems.forEach(item => {
                                const key = item.license_number || item.license || 'unknown';
                                if (!groupedByLicense[key]) {
                                    groupedByLicense[key] = [];
                                }
                                groupedByLicense[key].push(item);
                            });

                            return Object.entries(groupedByLicense).map(([licenseKey, groupItems]) => {
                                const firstItem = groupItems[0];
                                const licenseId = firstItem.license_id || firstItem.license;

                                return (
                                    <div key={licenseKey} className="mb-2 overflow-hidden rounded-lg border border-border bg-card shadow-sm">
                                        {/* ── LICENSE HEADER (compact) ── */}
                                        <div className="px-3 py-1.5 bg-muted/50 border-b border-border/60 text-[12px]">
                                            <div className="flex items-center gap-2 flex-wrap">
                                                <button
                                                    onClick={async () => {
                                                        try {
                                                            const response = await api.get(`licenses/${licenseId}/merged-documents/`, { responseType: 'blob' });
                                                            openPdfPreview(response.data, `${licenseKey}-copy.pdf`);
                                                        } catch {
                                                            toast.error('Failed to load license document');
                                                        }
                                                    }}
                                                    title="View license document"
                                                    className="inline-flex items-center gap-1 bg-transparent border-none p-0 cursor-pointer font-bold text-[13px] text-primary underline decoration-dotted underline-offset-[2px] hover:opacity-80"
                                                >
                                                    <FileText className="size-3.5" aria-hidden="true" />
                                                    {licenseKey}
                                                </button>
                                                <span className="text-muted-foreground">|</span>
                                                <span className="text-muted-foreground">{formatDate(firstItem.license_expiry_date) || '—'}</span>
                                                <span className="text-foreground font-semibold">{firstItem.exporter_name || '—'}</span>
                                                {firstItem.license_expiry_date && (
                                                    <span className="text-muted-foreground">Exp: {formatDate(firstItem.license_expiry_date) || '—'}</span>
                                                )}
                                                {firstItem.notification_number && (
                                                    <span className="text-muted-foreground">Notif: {firstItem.notification_number}</span>
                                                )}
                                            </div>
                                        </div>

                                        {/* ── GROUPED ITEMS WITH ITEM-SPECIFIC PLANNING ── */}

                                        {/* ── ITEMS WITH ITEM-SPECIFIC PLANNING ── */}
                                        <div className="p-2 space-y-3">
                                            {groupItems.map((item, itemIdx) => {
                                                const maxAllocation = calculateMaxAllocation(item);
                                                const currentAllocation = allocationData[item.id];
                                                // Both figures are always shown. In Plan mode the row's
                                                // legacy available_* fields describe the plan line, so use
                                                // the explicit canonical positions for the common UI.
                                                const actualQty = parseFloat(item.actual_position?.available_qty ?? item.available_quantity ?? "0");
                                                const actualCif = parseFloat(item.actual_position?.balance_cif ?? item.balance_cif_fc ?? "0");
                                                const planQty = parseFloat(item.plan_position?.remaining_qty ?? item.remaining_planned_qty ?? "0");
                                                const planCif = parseFloat(item.plan_position?.remaining_cif ?? item.remaining_planned_cif ?? "0");
                                                const plannedQty = parseFloat(item.original_planned_quantity ?? "0");
                                                const plannedCif = parseFloat(item.original_planned_cif_fc ?? "0");
                                                const average = actualQty > 0 ? (actualCif / actualQty).toFixed(2) : '0.00';
                                                const isReady = currentAllocation && parseFloat(currentAllocation.qty) > 0 && parseFloat(currentAllocation.cif_fc) > 0;
                                                const isBlocked = !maxAllocation.enabled;

                                                return (
                                                    <div key={item.id} className="border border-border/60 rounded p-2 bg-muted/20">
                                                        {/* Item header with item-specific info */}
                                                        {itemIdx === 0 && (
                                                            <div className="px-1 py-1 mb-1.5 text-[12px] border-b border-border/60">
                                                                <div className="flex items-center gap-1.5 flex-wrap">
                                                                    <span className="font-bold text-foreground">{item.description}</span>
                                                                    {item.hs_code_label && (
                                                                        <>
                                                                            <span className="text-muted-foreground">·</span>
                                                                            <span className="text-muted-foreground">HS: {item.hs_code_label}</span>
                                                                        </>
                                                                    )}
                                                                </div>
                                                            </div>
                                                        )}

                                                        {/* Item identifier + availability info (compact inline) */}
                                                        <div className="flex items-center justify-between gap-2 mb-1.5 text-[11px] flex-wrap">
                                                            <div className="flex items-center gap-1.5">
                                                                <span className="font-semibold text-foreground">SR #{item.serial_number}</span>
                                                                {item.condition_type
                                                                    ? <ConditionBadge type={item.condition_type} size="xs" />
                                                                    : (
                                                                        <span className="inline-flex items-center gap-0.5 rounded border border-success/30 bg-success/10 px-1 py-px text-[9px] text-success">
                                                                            <Unlock className="size-2.5" aria-hidden="true" />Open
                                                                        </span>
                                                                    )}
                                                            </div>
                                                            <div className="flex items-center gap-1.5 text-muted-foreground ml-auto">
                                                                <span>Actual Qty: <span className="font-semibold text-foreground">{actualQty.toFixed(3)}</span></span>
                                                                <span>Actual $: <span className="font-semibold text-foreground">${actualCif.toFixed(2)}</span></span>
                                                                <span>Avg: <span className="font-semibold text-foreground">{average}</span></span>
                                                                {item.plan_position?.exists && <>
                                                                    <span>Planned Qty: <span className="font-semibold text-foreground">{plannedQty.toFixed(3)}</span></span>
                                                                    <span>Planned $: <span className="font-semibold text-foreground">${plannedCif.toFixed(2)}</span></span>
                                                                    <span>Plan Remaining Qty: <span className="font-semibold text-foreground">{planQty.toFixed(3)}</span></span>
                                                                    <span>Plan Remaining $: <span className="font-semibold text-foreground">${planCif.toFixed(2)}</span></span>
                                                                </>}
                                                                <span>Max Qty: <span className="font-semibold text-foreground">{maxAllocation.qty.toFixed(3)}</span></span>
                                                                <span>Max $: <span className="font-semibold text-foreground">${maxAllocation.value.toFixed(2)}</span></span>
                                                            </div>
                                                        </div>

                                                        {/* Allocation controls (compact inline) */}
                                                        {isBlocked ? <div className="rounded border border-amber-300 bg-amber-50 px-2 py-1 text-[11px] text-amber-900" role="status">
                                                            <strong className="mr-1">Allocation unavailable</strong>
                                                            {maxAllocation.message || "No quantity or CIF remains for the selected mode."}
                                                        </div> : <div className="flex items-center gap-1.5 flex-wrap text-[11px]">
                                                            <div className="flex items-center gap-1 flex-1 min-w-[200px]">
                                                                <label className="text-muted-foreground font-semibold whitespace-nowrap">Qty:</label>
                                                                <input
                                                                    type="number"
                                                                    className="flex h-7 flex-1 rounded border border-input bg-card px-1.5 py-0.5 text-[0.78rem] outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring"
                                                                    value={currentAllocation?.qty || ""}
                                                                    onChange={(e) => handleQuantityChange(item.id, e.target.value)}
                                                                    placeholder="Qty"
                                                                    step="1"
                                                                    min="0"
                                                                    max={maxAllocation.qty}
                                                                    title={`Max: ${maxAllocation.qty}`}
                                                                />
                                                                <button
                                                                    className="rounded border border-border bg-card px-1.5 py-0.5 font-semibold text-muted-foreground cursor-pointer hover:bg-muted whitespace-nowrap"
                                                                    type="button"
                                                                    onClick={() => handleMaxQuantity(item)}
                                                                    title={`Set to max: ${maxAllocation.qty}`}
                                                                >Max</button>
                                                            </div>

                                                            <div className="flex items-center gap-1 flex-1 min-w-[200px]">
                                                                <label className="text-muted-foreground font-semibold whitespace-nowrap">Value:</label>
                                                                <input
                                                                    type="number"
                                                                    className="flex h-7 flex-1 rounded border border-input bg-card px-1.5 py-0.5 text-[0.78rem] outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring"
                                                                    value={currentAllocation?.cif_fc || ""}
                                                                    onChange={(e) => handleValueChange(item.id, e.target.value)}
                                                                    placeholder="Value"
                                                                    step="0.01"
                                                                    min="0"
                                                                    title={`Max: ${maxAllocation.value.toFixed(2)}`}
                                                                />
                                                                <button
                                                                    className="rounded border border-border bg-card px-1.5 py-0.5 font-semibold text-muted-foreground cursor-pointer hover:bg-muted whitespace-nowrap"
                                                                    type="button"
                                                                    onClick={() => handleMaxValue(item)}
                                                                    title={`Set to max: ${maxAllocation.value.toFixed(2)}`}
                                                                >Max</button>
                                                            </div>

                                                            {/* Confirm button */}
                                                            <button
                                                                className={cn(
                                                                    "rounded px-2.5 py-1 font-semibold whitespace-nowrap transition-all duration-200",
                                                                    isReady
                                                                        ? "bg-gradient-to-br from-primary to-primary/70 text-primary-foreground cursor-pointer hover:opacity-90"
                                                                        : "bg-muted text-muted-foreground cursor-not-allowed"
                                                                )}
                                                                onClick={() => handleConfirmAllot(item)}
                                                                disabled={!isReady || (allocateMutation.isPending && allocateMutation.variables?.item?.id === item.id)}
                                                                title="Allocate this item"
                                                            >
                                                                {allocateMutation.isPending && allocateMutation.variables?.item?.id === item.id ? (
                                                                    <span className="inline-block size-2.5 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" />
                                                                ) : (
                                                                    'Confirm'
                                                                )}
                                                            </button>
                                                        </div>}
                                                    </div>
                                                );
                                            })}
                                        </div>
                                    </div>
                                );
                            });
                        })()}
                    </div>

                    {tableLoading && (
                        <div className="flex items-center justify-center gap-2 py-4 text-sm text-muted-foreground">
                            <span className="inline-block size-4 animate-spin rounded-full border-2 border-primary border-t-transparent" aria-hidden="true" />
                            Loading items…
                        </div>
                    )}

                    {!tableLoading && availableItems.length === 0 && (
                        <div className="rounded-xl border-2 border-dashed border-border bg-card">
                            <EmptyState
                                icon={Inbox}
                                title={availableLicensesData?.code === "ALLOTMENT_REQUIREMENT_EXHAUSTED" ? "Allotment fully allocated" : (isPlanMode ? "No applicable active plan" : "No available license items found")}
                                description={availableLicensesData?.code === "ALLOTMENT_REQUIREMENT_EXHAUSTED" ? "No further licence allocation is required." : (isPlanMode ? "PLAN remains selected. Choose ACTUAL to allocate from live licence availability." : "Try adjusting the filters above")}
                            />
                        </div>
                    )}

                    {/* Pagination */}
                    {totalPages > 1 && (
                        <div className="flex justify-between items-center mt-3 pt-3 border-t border-border">
                            <div className="text-muted-foreground text-[14.5px]">
                                Showing {((currentPage - 1) * pageSize) + 1} to {Math.min(currentPage * pageSize, totalItems)} of {totalItems} items
                            </div>
                            <nav aria-label="Pagination">
                                <ul className="flex items-center gap-1">
                                    <li>
                                        <button
                                            className="inline-flex h-8 items-center rounded-l-md border border-border bg-card px-3 text-sm font-medium text-foreground hover:bg-muted disabled:pointer-events-none disabled:opacity-40"
                                            onClick={() => setCurrentPage(prev => prev - 1)}
                                            disabled={currentPage === 1}
                                        >
                                            Previous
                                        </button>
                                    </li>
                                    {[...Array(totalPages)].map((_, idx) => {
                                        const pageNum = idx + 1;
                                        // Show first, last, current, and pages around current
                                        if (
                                            pageNum === 1 ||
                                            pageNum === totalPages ||
                                            (pageNum >= currentPage - 2 && pageNum <= currentPage + 2)
                                        ) {
                                            return (
                                                <li key={pageNum}>
                                                    <button
                                                        className={cn(
                                                            "inline-flex h-8 min-w-[32px] items-center justify-center rounded border px-2 text-sm font-medium transition-colors",
                                                            currentPage === pageNum
                                                                ? "bg-gradient-to-br from-primary to-primary/70 border-transparent text-primary-foreground"
                                                                : "border-border bg-card text-foreground hover:bg-muted"
                                                        )}
                                                        onClick={() => setCurrentPage(pageNum)}
                                                    >
                                                        {pageNum}
                                                    </button>
                                                </li>
                                            );
                                        } else if (
                                            pageNum === currentPage - 3 ||
                                            pageNum === currentPage + 3
                                        ) {
                                            return <li key={pageNum}><span className="inline-flex h-8 items-center px-1 text-sm text-muted-foreground">…</span></li>;
                                        }
                                        return null;
                                    })}
                                    <li>
                                        <button
                                            className="inline-flex h-8 items-center rounded-r-md border border-border bg-card px-3 text-sm font-medium text-foreground hover:bg-muted disabled:pointer-events-none disabled:opacity-40"
                                            onClick={() => setCurrentPage(prev => prev + 1)}
                                            disabled={currentPage === totalPages}
                                        >
                                            Next
                                        </button>
                                    </li>
                                </ul>
                            </nav>
                        </div>
                    )}
                </div>
            </div>

            {/* End scrollable content area */}
            </div>

            {/* Plan gate: when an allot exceeds the item's plan, open the license
                planner so the user can adjust splits, then retry the allot. */}
            <LicensePlanningPanel
                show={!!planModal}
                licenseId={planModal?.item?.license}
                licenseNumber={planModal?.item?.license_number}
                balanceCif={Number(planModal?.item?.balance_cif_fc || 0)}
                onHide={() => setPlanModal(null)}
                onSaved={() => {
                    const item = planModal?.item;
                    setPlanModal(null);
                    if (item) handleConfirmAllot(item);
                }}
            />

            {/* Delete allocation confirm dialog */}
            <ConfirmDialog
                show={deleteConfirm.show}
                title="Remove Allocation"
                message="Are you sure you want to remove this allocation?"
                severity="danger"
                confirmText="Remove"
                onConfirm={confirmDelete}
                onCancel={() => setDeleteConfirm({ show: false, allotmentItemId: null })}
            />

            {/* Copy allotment confirm dialog */}
            <ConfirmDialog
                show={copyConfirm}
                title="Copy Allotment"
                message="Are you sure you want to create a copy of this allotment?"
                severity="info"
                confirmText="Copy"
                onConfirm={async () => {
                    setCopyConfirm(false);
                    try {
                        const response = await api.post(`allotments/${id}/copy/`);
                        toast.success('Allotment copied successfully!');
                        navigate(`/allotments/${response.data.id}/edit`);
                    } catch (err: unknown) {
                        toast.error((err as { response?: { data?: { error?: string } } }).response?.data?.error || 'Failed to copy allotment');
                    }
                }}
                onCancel={() => setCopyConfirm(false)}
            />

        </div>
    );
}
