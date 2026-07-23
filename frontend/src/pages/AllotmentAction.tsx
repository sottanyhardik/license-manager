import {useEffect, useState, useMemo} from "react";
import {useParams, useNavigate, useLocation} from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import api from "../api/axios";
import HybridSelect from "../components/HybridSelect";
import ConditionBadge from "../components/ConditionBadge";
import TransferLetterForm from "../components/TransferLetterForm";
import {openPdfPreview} from "../utils/pdfPreview";
import {useBackButton} from "../hooks/useBackButton";
import AllotmentFilters from "./AllotmentFilters";
import LicensePlanningPanel from "../components/planning/LicensePlanningPanel";
import { ArrowLeft, Building2, Calendar, CheckCircle2, CheckSquare, Clipboard, FileText, Files, Filter, Inbox, Info, ListChecks, Network, PenSquare, StickyNote, Trash2, TriangleAlert, Unlock, X, XCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import EmptyState from "@/components/EmptyState";

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
    items_detail?: Array<{ name: string }>;
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
        purchase_status: "GE,GO,SM,MI",  // GE Purchase, GE Operating, SM Purchase, Conversion
        license_status: "active",
        item_names: "",
        expiry_date_from: "",
        expiry_date_to: ""
    });
    const [isFirstLoad, setIsFirstLoad] = useState(true);
    const [currentPage, setCurrentPage] = useState(1);
    const pageSize = 20;
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");
    const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

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

    // Allotment header info (details, progress, allotted items)
    const {
        data: allotment,
        isError: allotmentFailed,
    } = useQuery({
        queryKey: ['allotments', id, 'info'],
        queryFn: () => api.get(`allotments/${id}/`).then(r => r.data),
        enabled: Boolean(id),
    });

    // Set description filter from allotment item_name on first load
    useEffect(() => {
        if (isFirstLoad && allotment?.item_name) {
            setFilters(prev => ({ ...prev, description: allotment.item_name }));
            setIsFirstLoad(false);
        }
    }, [allotment, isFirstLoad]);

    // Surface allotment load failure into the error banner
    useEffect(() => {
        if (allotmentFailed) {
            setError("Failed to load allotment info");
        }
    }, [allotmentFailed]);

    // Build API params from current filter state (skip empty values)
    const apiParams = useMemo(() => {
        const params: Record<string, string | number> = { page: currentPage, page_size: pageSize };
        Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = v; });
        return params;
    }, [filters, currentPage, pageSize]);

    // Available licenses list — re-fetches when filters or page changes,
    // but only after the first-load description filter has been applied.
    const {
        data: availableLicensesData,
        isLoading: initialLoading,
        isFetching: tableLoading,
    } = useQuery({
        queryKey: ['allotments', id, 'available-licenses', apiParams],
        queryFn: () => api.get(`allotment-actions/${id}/available-licenses/`, { params: apiParams }).then(r => r.data),
        enabled: Boolean(id) && !isFirstLoad,
        placeholderData: (prev) => prev,
    });

    const availableItems: AvailableItem[] = availableLicensesData?.available_items ?? availableLicensesData?.results ?? [];
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
        mutationFn: (payload: { item: AvailableItem; allocation: { qty: string; cif_fc: string } }) =>
            api.post(`allotment-actions/${id}/allocate-items/`, {
                allocations: [{
                    item_id: payload.item.id,
                    qty: payload.allocation.qty,
                    cif_fc: payload.allocation.cif_fc,
                }],
            }).then(r => r.data),
        onSuccess: (data, { item, allocation }) => {
            if (data.errors && data.errors.length > 0) {
                const firstErr = data.errors[0];
                if (firstErr.plan_exceeded) {
                    setPlanModal({ error: firstErr, item });
                    return;
                }
                const errorMsg = `Error: ${firstErr.error}`;
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
            const errorMsg = (err as { response?: { data?: { error?: string } } }).response?.data?.error || "Failed to allocate item";
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

    const calculateMaxAllocation = (item) => {
        if (!allotment?.unit_value_per_unit) return { qty: 0, value: 0 };

        const unitPrice = parseFloat(allotment.unit_value_per_unit);
        // Use balanced_quantity directly from backend (already calculated: required - allotted)
        const balancedQty = parseFloat(allotment.balanced_quantity || 0);
        const requiredValue = parseFloat(allotment.required_value || 0);
        const requiredValueWithBuffer = parseFloat(allotment.required_value_with_buffer || (requiredValue + 20));
        const allottedValue = parseFloat(allotment.allotted_value || 0);
        const balancedValueWithBuffer = requiredValueWithBuffer - allottedValue;
        // Floor to integer — backend's calculate_available_quantity() rounds DOWN
        // to whole units, so any fractional part of the stored available_quantity
        // would be rejected on submit.
        const availableQty = Math.floor(parseFloat(item.available_quantity || "0"));
        const availableCifFc = parseFloat(item.balance_cif_fc || "0");

        // Max quantity is the minimum of balanced quantity and available quantity
        let maxQty = Math.floor(Math.min(balancedQty, availableQty));

        // Calculate value for this quantity
        let maxValue = maxQty * unitPrice;

        // Check if value exceeds available CIF FC (using balance_cif_fc)
        if (maxValue > availableCifFc) {
            // Adjust quantity based on available CIF FC
            maxQty = Math.floor(availableCifFc / unitPrice);
            maxValue = maxQty * unitPrice;
        }

        // Check if value exceeds balanced value (with $10 buffer already included)
        if (maxValue > balancedValueWithBuffer) {
            // Adjust quantity based on balanced value with buffer
            maxQty = Math.floor(balancedValueWithBuffer / unitPrice);
            maxValue = maxQty * unitPrice;
        }

        // Utilization-plan cap: the item can never be allotted past its
        // Remaining Planned Qty/$ (Original plan minus what's already
        // allotted to the group — see plan_status_for on the backend).
        // Effective Max = min(Available, Remaining Planned). Absent when the
        // item has no plan (has_plan false) — unconstrained, as before.
        // Same recompute-both-together pattern as the clamps above, so
        // maxQty and maxValue never end up inconsistent with each other.
        let remainingPlanValue = Infinity;
        if (item.has_plan) {
            const remainingPlanQty = Math.max(0, Math.floor(parseFloat(item.remaining_planned_quantity ?? "0")));
            remainingPlanValue = Math.max(0, parseFloat(item.remaining_planned_cif_fc ?? "0"));
            if (maxQty > remainingPlanQty) {
                maxQty = remainingPlanQty;
                maxValue = maxQty * unitPrice;
            }
            if (maxValue > remainingPlanValue) {
                maxQty = Math.floor(remainingPlanValue / unitPrice);
                maxValue = maxQty * unitPrice;
            }
        }

        // Belt-and-suspenders: clamp maxValue to all caps (restricted CIF +
        // balanced value + remaining plan) and truncate to 2 decimal places.
        // Math.floor(X/Y)*Y can drift past X by a float-epsilon, and
        // .toFixed(2) can round half-cents UP — this line ensures the
        // requested cif_fc never crosses the backend's check.
        maxValue = Math.min(maxValue, availableCifFc, balancedValueWithBuffer, remainingPlanValue);
        maxValue = Math.floor(maxValue * 100) / 100;

        return {
            qty: maxQty,
            value: maxValue
        };
    };

    const handleQuantityChange = (itemId, qty) => {
        const item = availableItems.find(i => i.id === itemId);
        if (!item) return;

        const unitPrice = parseFloat(allotment.unit_value_per_unit);
        let inputQty = parseInt(qty) || 0;

        // Get balance quantities and values with buffer
        // Use balanced_quantity from backend (already calculated: required - allotted)
        const balancedQty = parseFloat(allotment.balanced_quantity || 0);
        const requiredValue = parseFloat(allotment.required_value || 0);
        const requiredValueWithBuffer = parseFloat(allotment.required_value_with_buffer || (requiredValue + 20));
        const allottedValue = parseFloat(allotment.allotted_value || 0);
        const balancedValueWithBuffer = requiredValueWithBuffer - allottedValue;
        const availableCifFc = parseFloat(item.balance_cif_fc || "0");
        // Floor: backend rounds available_quantity DOWN to whole units, so we must too.
        const availableQty = Math.floor(parseFloat(item.available_quantity || "0"));

        // Show warning if user tries to exceed limits
        if (inputQty > balancedQty) {
            toast.warning(`Quantity adjusted to balanced quantity: ${balancedQty}`);
            inputQty = balancedQty;
        }
        if (inputQty > availableQty) {
            toast.warning(`Quantity adjusted to available quantity: ${availableQty}`);
            inputQty = availableQty;
        }

        // Calculate value from quantity
        let allocateCifFc = inputQty * unitPrice;

        // If calculated value exceeds balanced value with buffer, adjust quantity down
        if (allocateCifFc > balancedValueWithBuffer) {
            inputQty = Math.floor(balancedValueWithBuffer / unitPrice);
            allocateCifFc = inputQty * unitPrice;
            toast.warning(`Quantity adjusted to match value limit: ${inputQty}`);
        }

        // If calculated value exceeds available CIF FC, adjust quantity down
        if (allocateCifFc > availableCifFc) {
            inputQty = Math.floor(availableCifFc / unitPrice);
            allocateCifFc = inputQty * unitPrice;
            toast.warning(`Quantity adjusted to available CIF: ${inputQty}`);
        }

        // Utilization-plan cap: never allow more than what's left of the
        // item's plan (Original planned qty/$ minus what's already
        // allotted to its group). Clamp both qty and value together so the
        // field always ends in a valid, submittable state.
        if (item.has_plan) {
            const remainingPlanQty = Math.max(0, Math.floor(parseFloat(item.remaining_planned_quantity ?? "0")));
            const remainingPlanValue = Math.max(0, parseFloat(item.remaining_planned_cif_fc ?? "0"));
            if (inputQty > remainingPlanQty) {
                toast.error("Cannot allot quantity greater than remaining planned quantity.");
                inputQty = remainingPlanQty;
                allocateCifFc = inputQty * unitPrice;
            }
            if (allocateCifFc > remainingPlanValue) {
                toast.error("Cannot allot CIF value greater than remaining planned value.");
                inputQty = Math.floor(remainingPlanValue / unitPrice);
                allocateCifFc = inputQty * unitPrice;
            }
        }

        setAllocationData({
            ...allocationData,
            [itemId]: {
                qty: inputQty.toString(),
                cif_fc: allocateCifFc.toFixed(2)
            }
        });
    };

    const handleValueChange = (itemId, value) => {
        const item = availableItems.find(i => i.id === itemId);
        if (!item) return;

        const unitPrice = parseFloat(allotment.unit_value_per_unit);
        let inputValue = parseFloat(value) || 0;

        // Get balance values with buffer
        const balancedQty = parseInt(allotment.balanced_quantity || 0);
        const requiredValue = parseFloat(allotment.required_value || 0);
        const requiredValueWithBuffer = parseFloat(allotment.required_value_with_buffer || (requiredValue + 20));
        const allottedValue = parseFloat(allotment.allotted_value || 0);
        const balancedValueWithBuffer = requiredValueWithBuffer - allottedValue;
        const availableCifFc = parseFloat(item.balance_cif_fc || "0");

        // Constrain to balanced value with buffer
        if (inputValue > balancedValueWithBuffer) {
            inputValue = balancedValueWithBuffer;
        }

        // Constrain to available CIF FC
        if (inputValue > availableCifFc) {
            inputValue = availableCifFc;
        }

        // Calculate quantity from value (round down to integer)
        let allocateQty = Math.floor(inputValue / unitPrice);

        // Constrain to balanced quantity
        if (allocateQty > balancedQty) {
            allocateQty = balancedQty;
        }

        // Utilization-plan cap: never allow more than what's left of the
        // item's plan. Same rule as handleQuantityChange, entered from the
        // Value field instead of the Qty field.
        if (item.has_plan) {
            const remainingPlanQty = Math.max(0, Math.floor(parseFloat(item.remaining_planned_quantity ?? "0")));
            const remainingPlanValue = Math.max(0, parseFloat(item.remaining_planned_cif_fc ?? "0"));
            if (inputValue > remainingPlanValue) {
                toast.error("Cannot allot CIF value greater than remaining planned value.");
                inputValue = remainingPlanValue;
                allocateQty = Math.floor(inputValue / unitPrice);
            }
            if (allocateQty > remainingPlanQty) {
                toast.error("Cannot allot quantity greater than remaining planned quantity.");
                allocateQty = remainingPlanQty;
            }
        }

        // Recalculate value based on adjusted quantity
        const adjustedValue = (allocateQty * unitPrice).toFixed(2);

        setAllocationData({
            ...allocationData,
            [itemId]: {
                qty: allocateQty.toString(),
                cif_fc: adjustedValue
            }
        });
    };

    const handleMaxQuantity = (item) => {
        const maxAllocation = calculateMaxAllocation(item);
        setAllocationData({
            ...allocationData,
            [item.id]: {
                qty: maxAllocation.qty.toString(),
                cif_fc: maxAllocation.value.toFixed(2)
            }
        });
    };

    const handleMaxValue = (item) => {
        const maxAllocation = calculateMaxAllocation(item);
        setAllocationData({
            ...allocationData,
            [item.id]: {
                qty: maxAllocation.qty.toString(),
                cif_fc: maxAllocation.value.toFixed(2)
            }
        });
    };

    const handleConfirmAllot = (item) => {
        const allocation = allocationData[item.id];
        if (!allocation || parseFloat(allocation.qty) <= 0) {
            toast.error("Please enter a valid quantity");
            setError("Please enter a valid quantity");
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

    if (initialLoading) return (
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
                                <tfoot>
                                <tr className="bg-muted/40 border-t-2 border-border">
                                    <th scope="row" colSpan={8} className="px-3 py-1.5 text-right text-[11px] font-bold uppercase tracking-wider text-muted-foreground">Total</th>
                                    <td className="px-3 py-1.5 text-right text-[13px] font-extrabold tabular-nums text-foreground">{parseInt(allotment.alloted_quantity || 0).toLocaleString()}</td>
                                    <td className="px-3 py-1.5 text-right text-[13px] font-extrabold tabular-nums text-foreground">{parseFloat(allotment.allotted_value || 0).toFixed(2)}</td>
                                    <td></td>
                                </tr>
                                </tfoot>
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
                        setFilters={setFilters}
                        availableItemNames={availableItemNames}
                        notificationOptions={notificationOptions}
                    />

                    <div className="max-h-[650px] overflow-y-auto pr-px">
                        {availableItems.map((item) => {
                            const maxAllocation = calculateMaxAllocation(item);
                            const currentAllocation = allocationData[item.id];
                            const qty = parseFloat(item.available_quantity || "0");
                            const cifFc = parseFloat(item.balance_cif_fc || "0");
                            const average = qty > 0 ? (cifFc / qty).toFixed(2) : '0.00';
                            const isReady = currentAllocation && parseFloat(currentAllocation.qty) > 0;

                            return (
                                <div key={item.id} className={cn(
                                    "mb-2.5 overflow-hidden rounded-xl bg-card",
                                    isReady
                                        ? "border border-primary border-l-[4px] shadow-[0_2px_12px_rgba(79,70,229,0.12)]"
                                        : "border border-border/60 border-l-[4px] border-l-border shadow-[0_1px_3px_rgba(0,0,0,0.06)]"
                                )}>
                                    {/* ── Row 1: Identity bar ── */}
                                    <div className="flex items-center flex-wrap gap-1.5 px-3 py-1.5 bg-muted/40 border-b border-border">
                                        <button
                                            onClick={async () => {
                                                try {
                                                    const licenseId = item.license_id || item.license;
                                                    const response = await api.get(`licenses/${licenseId}/merged-documents/`, { responseType: 'blob' });
                                                    openPdfPreview(response.data, `${item.license_number || licenseId}-copy.pdf`);
                                                } catch {
                                                    toast.error('Failed to load license document');
                                                }
                                            }}
                                            title="View license document"
                                            className="mr-1 inline-flex items-center gap-1 bg-transparent border-none p-0 cursor-pointer font-bold text-[14px] text-primary underline decoration-dotted underline-offset-[3px]"
                                        >
                                            <FileText className="size-4" aria-hidden="true" />
                                            {item.license_number}
                                        </button>
                                        <span className="rounded-md bg-border px-[7px] py-px text-[12px] font-semibold text-muted-foreground">#{item.serial_number}</span>
                                        <ConditionBadge type={item.condition_type} size="xs" />

                                        {item.hs_code_label && (
                                            <span className="rounded-md border border-primary/20 bg-primary/5 px-[7px] py-px text-[12px] text-primary">HS: {item.hs_code_label}</span>
                                        )}
                                        {item.notification_number && (
                                            <span className="text-[12px] text-muted-foreground">
                                                Notif: {item.notification_number}
                                            </span>
                                        )}
                                        <span className="ml-auto flex items-center gap-1 text-[12px] text-muted-foreground">
                                            <Calendar className="size-4" aria-hidden="true" />
                                            Exp: {item.license_expiry_date || '—'}
                                        </span>
                                        {/* Restriction is read-only — driven by the licence's
                                            condition_type. Use the shared badge. */}
                                        {item.condition_type
                                            ? <ConditionBadge type={item.condition_type} size="xs" />
                                            : (
                                                <span className="inline-flex items-center gap-1 rounded border border-success/30 bg-success/10 px-[7px] py-px text-[11px] text-success">
                                                    <Unlock className="size-3" aria-hidden="true" />Open
                                                </span>
                                            )}
                                    </div>

                                    {/* ── Row 2: Compact description + exporter + chips ── */}
                                    <div className="flex items-center flex-wrap gap-1.5 px-3 py-[5px] bg-card border-b border-border/60">
                                        <span className="font-bold text-[13px] text-foreground">
                                            {item.description}
                                        </span>
                                        <span className="inline-block w-px h-3 bg-border shrink-0" />
                                        <span className="inline-flex items-center gap-[3px] text-[11.5px] text-muted-foreground">
                                            <Building2 className="size-3" aria-hidden="true" />{item.exporter_name}
                                        </span>
                                        {item.items_detail && item.items_detail.length > 0 && item.items_detail.map((i, idx) => (
                                            <span key={idx} className="rounded border border-primary/20 bg-primary/10 px-1.5 text-[0.7rem] font-semibold leading-[1.6] text-primary">{i.name}</span>
                                        ))}
                                    </div>

                                    {/* ── Row 2.5: Utilization-plan status (Original/Used/Remaining) —
                                        only rendered for items that actually carry a plan. This is the
                                        SAME Original/Used/Remaining the Max button below is capped to,
                                        and what the server re-checks on Confirm — shown here so the
                                        operator sees the cap before typing, not after a rejection. ── */}
                                    {item.has_plan && (() => {
                                        const origQty = Number(item.original_planned_quantity ?? 0);
                                        const usedQty = Number(item.used_planned_quantity ?? 0);
                                        const remQty  = Number(item.remaining_planned_quantity ?? 0);
                                        const origVal = Number(item.original_planned_cif_fc ?? 0);
                                        const usedVal = Number(item.used_planned_cif_fc ?? 0);
                                        const remVal  = Number(item.remaining_planned_cif_fc ?? 0);
                                        return (
                                            <div className="flex items-center flex-wrap gap-x-4 gap-y-1 bg-primary/5 border-b border-primary/10 px-3 py-[5px] text-[11.5px]">
                                                <span className="inline-flex items-center gap-1 font-semibold text-primary">
                                                    <ListChecks className="size-3" aria-hidden="true" />Plan
                                                </span>
                                                <span className="text-muted-foreground">
                                                    Qty — Original <b className="text-foreground font-semibold">{origQty.toFixed(3)}</b>
                                                    {' · '}Used <b className="text-foreground font-semibold">{usedQty.toFixed(3)}</b>
                                                    {' · '}Remaining <b className={cn("font-semibold", remQty <= 0 ? "text-destructive" : "text-foreground")}>{remQty.toFixed(3)}</b>
                                                </span>
                                                <span className="text-muted-foreground">
                                                    Value — Original <b className="text-foreground font-semibold">${origVal.toFixed(2)}</b>
                                                    {' · '}Used <b className="text-foreground font-semibold">${usedVal.toFixed(2)}</b>
                                                    {' · '}Remaining <b className={cn("font-semibold", remVal <= 0 ? "text-destructive" : "text-foreground")}>${remVal.toFixed(2)}</b>
                                                </span>
                                            </div>
                                        );
                                    })()}

                                    {/* ── Row 3: Stats + Inputs + Action (compact bottom bar) ── */}
                                    <div className="flex items-center flex-wrap bg-muted/40">

                                        {/* Availability stats */}
                                        <div className="flex gap-3 px-3 py-[7px] shrink-0">
                                            {[
                                                {label: 'Avail Qty', value: qty.toFixed(3)},
                                                {label: 'CIF FC', value: cifFc.toFixed(2)},
                                                {label: 'Avg', value: average},
                                            ].map(({label, value}) => (
                                                <div key={label}>
                                                    <div className="text-[0.62rem] text-muted-foreground uppercase tracking-[0.4px]">{label}</div>
                                                    <div className="font-bold text-[13px] text-foreground leading-[1.2]">{value}</div>
                                                </div>
                                            ))}
                                        </div>

                                        <div className="w-px h-9 bg-border/60 shrink-0" />

                                        {/* Allocation inputs */}
                                        <div className="flex gap-2 px-3 py-[7px] flex-wrap flex-1 min-w-[260px]">
                                            <div className="flex-1 min-w-[130px]">
                                                <label className="block mb-[3px] text-[0.62rem] text-muted-foreground font-semibold uppercase tracking-[0.3px]">
                                                    Qty <span className="font-normal normal-case">/ max {maxAllocation.qty}</span>
                                                </label>
                                                <div className="relative flex">
                                                    <input type="number" className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-[0.82rem] outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring"
                                                        value={currentAllocation?.qty || ""}
                                                        onChange={(e) => handleQuantityChange(item.id, e.target.value)}
                                                        placeholder="Qty"
                                                        step="1" min="0" max={maxAllocation.qty}
                                                    />
                                                    <button className="flex items-center gap-1.5 rounded border border-border bg-card px-2.5 py-1.5 text-[12px] font-semibold text-muted-foreground cursor-pointer hover:bg-muted" type="button"
                                                        onClick={() => handleMaxQuantity(item)}>Max</button>
                                                </div>
                                            </div>
                                            <div className="flex-1 min-w-[130px]">
                                                <label className="block mb-[3px] text-[0.62rem] text-muted-foreground font-semibold uppercase tracking-[0.3px]">
                                                    Value <span className="font-normal normal-case">/ max {maxAllocation.value.toFixed(2)}</span>
                                                </label>
                                                <div className="relative flex">
                                                    <input type="number" className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-[0.82rem] outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring"
                                                        value={currentAllocation?.cif_fc || ""}
                                                        onChange={(e) => handleValueChange(item.id, e.target.value)}
                                                        placeholder="Value"
                                                        step="0.01" min="0"
                                                    />
                                                    <button className="flex items-center gap-1.5 rounded border border-border bg-card px-2.5 py-1.5 text-[12px] font-semibold text-muted-foreground cursor-pointer hover:bg-muted" type="button"
                                                        onClick={() => handleMaxValue(item)}>Max</button>
                                                </div>
                                            </div>
                                        </div>

                                        <div className="w-px h-9 bg-border/60 shrink-0" />

                                        {/* Confirm action */}
                                        <div className="shrink-0 px-3 py-[7px] flex items-center justify-center">
                                            <button
                                                className={cn(
                                                    "flex items-center gap-1.5 rounded-xl px-4 py-2.5 text-[0.82rem] font-semibold whitespace-nowrap transition-all duration-200",
                                                    isReady
                                                        ? "bg-gradient-to-br from-primary to-primary/70 text-primary-foreground cursor-pointer hover:opacity-90"
                                                        : "bg-muted text-muted-foreground cursor-not-allowed"
                                                )}
                                                onClick={() => handleConfirmAllot(item)}
                                                disabled={!isReady || (allocateMutation.isPending && allocateMutation.variables?.item?.id === item.id)}
                                            >
                                                {allocateMutation.isPending && allocateMutation.variables?.item?.id === item.id ? (
                                                    <>
                                                        <span className="inline-block size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent mr-1" aria-hidden="true" />
                                                        Saving…
                                                    </>
                                                ) : (
                                                    <>
                                                        <CheckCircle2 className="size-4" aria-hidden="true" />
                                                        Confirm
                                                    </>
                                                )}
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            );
                        })}
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
                                title="No available license items found"
                                description="Try adjusting the filters above"
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
