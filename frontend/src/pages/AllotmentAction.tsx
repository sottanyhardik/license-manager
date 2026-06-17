import {useEffect, useState, useCallback, useRef} from "react";
import {useParams, useNavigate, useLocation} from "react-router-dom";
import { toast } from 'react-toastify';
import Select from "react-select";
import api from "../api/axios";
import HybridSelect from "../components/HybridSelect";
import ConditionBadge from "../components/ConditionBadge";
import TransferLetterForm from "../components/TransferLetterForm";
import {openPdfPreview} from "../utils/pdfPreview";
import {useBackButton} from "../hooks/useBackButton";
import { ArrowLeft, Building2, Calendar, CheckCircle2, CheckSquare, Clipboard, FileText, Files, Filter, Inbox, Info, ListChecks, Network, PenSquare, StickyNote, Trash2, TriangleAlert, Unlock, XCircle } from "lucide-react";

export default function AllotmentAction({ allotmentId: propId, isModal = false, onClose }) {
    const {id: paramId} = useParams();
    const navigate = useNavigate();
    const location = useLocation();

    // Use prop ID if provided (for modal), otherwise use URL param (for page)
    const id = propId || paramId;

    const [allotment, setAllotment] = useState(null);
    const [availableItems, setAvailableItems] = useState([]);
    const [allocationData, setAllocationData] = useState({});
    const [initialLoading, setInitialLoading] = useState(true);
    const [tableLoading, setTableLoading] = useState(false);
    const [saving, setSaving] = useState({});
    const [search] = useState("");
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
    const [notificationOptions, setNotificationOptions] = useState([]);
    const [availableItemNames, setAvailableItemNames] = useState([]);
    const [pagination, setPagination] = useState({
        currentPage: 1,
        pageSize: 20,
        totalItems: 0,
        totalPages: 0
    });
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");
    const [deletingItems, setDeletingItems] = useState({});
    const [initialAllocationData, setInitialAllocationData] = useState({});
    const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

    // Enable browser back button support with filter preservation
    useBackButton('allotments', !isModal);

    // Track unsaved changes
    useEffect(() => {
        if (Object.keys(initialAllocationData).length > 0) {
            const hasChanges = JSON.stringify(allocationData) !== JSON.stringify(initialAllocationData);
            setHasUnsavedChanges(hasChanges);
        }
    }, [allocationData, initialAllocationData]);

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

    // Refs for state fetchData reads but should not be reactive on
    const isFirstFetchRef = useRef(true);
    const initialAllocationDataRef = useRef(initialAllocationData);
    initialAllocationDataRef.current = initialAllocationData;
    const pageSizeRef = useRef(pagination.pageSize);
    pageSizeRef.current = pagination.pageSize;

    const fetchNotificationOptions = useCallback(async () => {
        try {
            const {data} = await api.get('masters/notification-numbers/', {
                params: {page_size: 200, ordering: 'code'},
            });
            const results = data?.results ?? data ?? [];
            setNotificationOptions(
                results.map(({code, label}) => ({
                    value: code,
                    display_name: label ? `${code} — ${label}` : code,
                }))
            );
        } catch (err) {
            // Silently fail for notification options
        }
    }, []);

    const fetchAvailableItemNames = useCallback(async () => {
        try {
            const {data} = await api.get('item-report/available-items/');
            const items = data || [];
            setAvailableItemNames(items.map(item => ({value: item.id, label: item.name})));
        } catch (err) {
            // Silently fail for item names
        }
    }, []);

    const fetchAllotmentInfo = useCallback(async () => {
        try {
            const {data} = await api.get(`allotments/${id}/`);
            setAllotment(data);
        } catch (err) {
            setError(err.response?.data?.detail || "Failed to load allotment info");
        }
    }, [id]);

    const fetchData = useCallback(async (page = 1) => {
        if (isFirstFetchRef.current) {
            setInitialLoading(true);
        } else {
            setTableLoading(true);
        }
        setError("");
        try {
            const params = {
                search,
                page,
                page_size: pageSizeRef.current
            };
            Object.keys(filters).forEach(key => {
                if (filters[key]) {
                    params[key] = filters[key];
                }
            });

            const {data} = await api.get(`allotment-actions/${id}/available-licenses/`, {
                params
            });
            setAllotment(data.allotment);
            setAvailableItems(data.available_items || data.results || []);

            if (Object.keys(initialAllocationDataRef.current).length === 0) {
                setInitialAllocationData({});
            }

            if (data.count !== undefined) {
                setPagination(prev => ({
                    ...prev,
                    totalItems: data.count,
                    totalPages: Math.ceil(data.count / prev.pageSize)
                }));
            }
            isFirstFetchRef.current = false;
        } catch (err) {
            setError(err.response?.data?.detail || "Failed to load data");
        } finally {
            setInitialLoading(false);
            setTableLoading(false);
        }
    }, [id, search, filters]);

    useEffect(() => {
        fetchNotificationOptions();
        fetchAvailableItemNames();
        fetchAllotmentInfo();
    }, [fetchNotificationOptions, fetchAvailableItemNames, fetchAllotmentInfo]);

    // Set description from allotment item_name on first load
    useEffect(() => {
        if (isFirstLoad && allotment?.item_name) {
            setFilters(prev => ({...prev, description: allotment.item_name}));
            setIsFirstLoad(false);
        }
    }, [allotment, isFirstLoad]);

    const fetchDataRef = useRef(fetchData);
    fetchDataRef.current = fetchData;

    useEffect(() => {
        if (isFirstLoad && !allotment?.item_name) {
            return;
        }

        const timer = setTimeout(() => {
            setPagination(prev => ({...prev, currentPage: 1}));
            fetchDataRef.current(1);
        }, 300);
        return () => clearTimeout(timer);
    }, [id, search, filters, isFirstLoad, allotment?.item_name]);

    useEffect(() => {
        if (isFirstLoad && !allotment?.item_name) {
            return;
        }
        fetchDataRef.current(pagination.currentPage);
    }, [pagination.currentPage, isFirstLoad, allotment?.item_name]);

    // Scroll to transfer letter section if navigated from list
    useEffect(() => {
        if (location.state?.scrollToTransferLetter && allotment) {
            setTimeout(() => {
                document.getElementById('transfer-letter-section')?.scrollIntoView({ behavior: 'smooth' });
            }, 500);
        }
    }, [location.state, allotment]);

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
        const availableQty = Math.floor(parseFloat(item.available_quantity || 0));
        const availableCifFc = parseFloat(item.balance_cif_fc || 0);

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

        // Belt-and-suspenders: clamp maxValue to all caps (restricted CIF + balanced
        // value) and truncate to 2 decimal places. Math.floor(X/Y)*Y can drift past
        // X by a float-epsilon, and .toFixed(2) can round half-cents UP — this
        // line ensures the requested cif_fc never crosses the backend's check.
        maxValue = Math.min(maxValue, availableCifFc, balancedValueWithBuffer);
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
        const availableCifFc = parseFloat(item.balance_cif_fc || 0);
        // Floor: backend rounds available_quantity DOWN to whole units, so we must too.
        const availableQty = Math.floor(parseFloat(item.available_quantity || 0));

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
        const availableCifFc = parseFloat(item.balance_cif_fc || 0);

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

    const handleConfirmAllot = async (item) => {
        const allocation = allocationData[item.id];
        if (!allocation || parseFloat(allocation.qty) <= 0) {
            toast.error("Please enter a valid quantity");
            setError("Please enter a valid quantity");
            return;
        }

        setSaving({...saving, [item.id]: true});
        setError("");
        setSuccess("");

        try {
            const {data} = await api.post(`allotment-actions/${id}/allocate-items/`, {
                allocations: [{
                    item_id: item.id,
                    qty: allocation.qty,
                    cif_fc: allocation.cif_fc
                }]
            });

            if (data.errors && data.errors.length > 0) {
                const errorMsg = `Error: ${data.errors[0].error}`;
                setError(errorMsg);
                toast.error(errorMsg);
            } else {
                const successMsg = `Successfully allocated ${allocation.qty} from ${item.license_number}`;
                setSuccess(successMsg);
                toast.success(successMsg);

                // Clear this item's allocation
                const newAllocationData = {...allocationData};
                delete newAllocationData[item.id];
                setAllocationData(newAllocationData);
                setInitialAllocationData(JSON.parse(JSON.stringify(newAllocationData))); // Update initial state after save

                // Update allotment data (for balance quantity/value display)
                if (data.allotment) {
                    setAllotment(data.allotment);
                }

                // Update all items from the same license
                const allocatedValue = parseFloat(allocation.cif_fc);
                const licenseNumber = item.license_number;

                setAvailableItems(prevItems => {
                    // First, update all items from the same license
                    const updatedItems = prevItems.map(i => {
                        // Only update items from the same license
                        if (i.license_number === licenseNumber) {
                            // For the allocated item, also update quantity
                            if (i.id === item.id) {
                                const allocatedQty = parseFloat(allocation.qty);
                                const itemAvailableQty = parseFloat(i.available_quantity);
                                const newAvailableQty = itemAvailableQty - allocatedQty;

                                // If fully allocated, mark for removal
                                if (newAvailableQty <= 0) {
                                    return null; // Will be filtered out
                                }

                                // Update both quantity and CIF FC (shared license balance)
                                const itemAvailableValue = parseFloat(i.balance_cif_fc);
                                const newAvailableValue = itemAvailableValue - allocatedValue;

                                return {
                                    ...i,
                                    available_quantity: newAvailableQty.toFixed(3),
                                    balance_cif_fc: Math.max(0, newAvailableValue).toFixed(2)
                                };
                            } else {
                                // For other items in same license, only update CIF FC (shared balance)
                                const itemAvailableValue = parseFloat(i.balance_cif_fc);
                                const newAvailableValue = itemAvailableValue - allocatedValue;

                                return {
                                    ...i,
                                    balance_cif_fc: Math.max(0, newAvailableValue).toFixed(2)
                                };
                            }
                        }
                        return i;
                    });

                    // Filter out null entries (fully allocated items)
                    return updatedItems.filter(i => i !== null);
                });

                // ONLY scroll to transfer letter section if balance quantity is exactly 0
                if (data.allotment) {
                    const requiredQty = parseInt(data.allotment.required_quantity || 0);
                    const allotedQty = parseInt(data.allotment.alloted_quantity || 0);
                    const balanceQty = requiredQty - allotedQty;

                    // Strict check: balance must be EXACTLY 0 (not negative, not positive)
                    if (balanceQty === 0 && requiredQty > 0) {
                        // Balance is complete, scroll to transfer letter section
                        setTimeout(() => {
                            const element = document.getElementById('transfer-letter-section');
                            if (element) {
                                element.scrollIntoView({ behavior: 'smooth', block: 'start' });
                            }
                        }, 800);
                    }
                }
            }
        } catch (err) {
            const errorMsg = err.response?.data?.error || "Failed to allocate item";
            setError(errorMsg);
            toast.error(errorMsg);
        } finally{
            setSaving({...saving, [item.id]: false});
        }
    };

    const handleDeleteAllotment = async (allotmentItemId) => {
        if (!window.confirm("Are you sure you want to remove this allocation?")) {
            return;
        }

        setDeletingItems({...deletingItems, [allotmentItemId]: true});
        setError("");
        setSuccess("");

        try {
            const {data} = await api.delete(`allotment-actions/${id}/delete-item/${allotmentItemId}/`);
            const successMsg = data.message || "Successfully removed allocation";
            setSuccess(successMsg);
            toast.success(successMsg);
            // Refresh data immediately to update available quantities and allotted items
            fetchData(pagination.currentPage);
        } catch (err) {
            const errorMsg = err.response?.data?.error || "Failed to delete allocation";
            setError(errorMsg);
            toast.error(errorMsg);
        } finally{
            setDeletingItems({...deletingItems, [allotmentItemId]: false});
        }
    };

    if (initialLoading) return (
        <div style={{ minHeight: '100vh', background: 'var(--tb-body-bg)' }}>
            <div className="flex justify-between items-center mb-4 placeholder-glow">
                <div>
                    <div className="placeholder col-5" style={{ height: 28, borderRadius: 6, display: 'block' }}></div>
                    <div className="placeholder col-3 mt-1" style={{ height: 14, borderRadius: 4, display: 'block' }}></div>
                </div>
                <div className="flex gap-2">
                    {[80, 90, 110, 90, 100].map((w, i) => (
                        <div key={i} className="placeholder" style={{ width: w, height: 32, borderRadius: 6 }}></div>
                    ))}
                </div>
            </div>
            <div className="card mb-3" style={{ borderRadius: 12 }}>
                <div className="card-header py-3" style={{ borderRadius: '12px 12px 0 0' }}>
                    <div className="placeholder col-3" style={{ height: 18, borderRadius: 4 }}></div>
                </div>
                <div className="flex gap-3 p-5">
                    {[1,2,3,4].map(i => <div key={i} className="placeholder flex-fill" style={{ borderRadius: 8, height: 72 }}></div>)}
                </div>
            </div>
            <div className="card" style={{ borderRadius: 12 }}>
                <div className="card-header py-3" style={{ borderRadius: '12px 12px 0 0' }}>
                    <div className="placeholder col-4" style={{ height: 18, borderRadius: 4 }}></div>
                </div>
                <div className="p-5">
                    {[1,2,3].map(i => <div key={i} className="placeholder w-full mb-2" style={{ height: 90, borderRadius: 8 }}></div>)}
                </div>
            </div>
        </div>
    );

    return (
        <div style={{
            height: isModal ? '100%' : 'auto',
            display: 'flex',
            flexDirection: 'column',
            backgroundColor: isModal ? 'transparent' : 'var(--tb-sunken)',
            padding: isModal ? '0' : '24px',
            minHeight: isModal ? 'auto' : '100vh'
        }}>
            {!isModal && (
                <div className="flex justify-between items-center flex-wrap gap-2 mb-4">
                    <div>
                        <h4 className="mb-0 font-bold" style={{ color: 'var(--tb-text)' }}>
                            <Network className="size-4" aria-hidden="true" />
                            Allocate License Items
                        </h4>
                        {allotment && (
                            <small className="text-muted">
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
                            onClick={async () => {
                                if (!window.confirm('Are you sure you want to create a copy of this allotment?')) return;
                                try {
                                    const response = await api.post(`allotments/${id}/copy/`);
                                    toast.success('Allotment copied successfully!');
                                    navigate(`/allotments/${response.data.id}/edit`);
                                } catch (err) {
                                    toast.error(err.response?.data?.error || 'Failed to copy allotment');
                                }
                            }}
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
                            style={{ background: 'linear-gradient(135deg, var(--tb-brand), var(--tb-brand-hover))', border: 'none' }}
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
            <div style={{flex: 1, overflowY: 'auto', paddingRight: '8px'}}>

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
                const progressColor = isComplete ? 'var(--tb-success)' : progressPct >= 60 ? 'var(--tb-brand)' : 'var(--tb-warning)';

                return (
                    <div className="mb-4 overflow-hidden rounded-xl border border-border bg-card shadow-sm">
                        {/* Header */}
                        <div className="flex items-center justify-between border-b border-border/60 px-5 py-3">
                            <div className="flex items-center gap-3">
                                <div className="flex size-8 shrink-0 items-center justify-center rounded-lg" style={{ background: 'var(--tb-brand-50)', border: '1px solid var(--tb-brand-100)' }}>
                                    <ListChecks className="size-4" style={{ color: 'var(--tb-brand)' }} aria-hidden="true" />
                                </div>
                                <div>
                                    <p className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Allotment Details</p>
                                    <h3 className="text-sm font-bold leading-tight tracking-tight text-foreground">{allotment.item_name}</h3>
                                </div>
                            </div>
                            <div className="flex items-center gap-3">
                                <div className="flex items-center gap-2">
                                    <div className="h-1.5 w-24 overflow-hidden rounded-full bg-muted">
                                        <div className="h-full rounded-full transition-[width] duration-500" style={{ width: `${progressPct}%`, background: progressColor }} />
                                    </div>
                                    <span className="text-xs font-bold tabular-nums" style={{ color: progressColor }}>{progressPct}%</span>
                                </div>
                                <span className="rounded-full px-2.5 py-1 text-[11px] font-semibold leading-none" style={{
                                    background: isComplete ? 'var(--tb-success-soft)' : progressPct >= 60 ? 'var(--tb-brand-50)' : 'var(--tb-warning-soft)',
                                    color: isComplete ? 'var(--tb-success-text)' : progressPct >= 60 ? 'var(--tb-brand)' : 'var(--tb-warning-text)',
                                }}>
                                    {isComplete ? '✓ Complete' : 'In Progress'}
                                </span>
                            </div>
                        </div>

                        {/* 4-column stat grid with dividers */}
                        <div className="grid grid-cols-2 divide-y divide-border/40 sm:grid-cols-4 sm:divide-x sm:divide-y-0">
                            {/* Unit Price */}
                            <div className="flex flex-col px-5 py-4">
                                <div className="mb-2 flex items-center gap-1.5">
                                    <span className="size-2 shrink-0 rounded-full" style={{ background: 'var(--tb-info)' }} />
                                    <span className="text-[10px] font-bold uppercase tracking-widest text-muted-foreground">Unit Price</span>
                                </div>
                                <span className="text-[1.65rem] font-extrabold leading-none tabular-nums" style={{ color: 'var(--tb-info)' }}>
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
                            <div className="flex flex-col px-5 py-4" style={{ background: 'rgba(16,185,129,0.04)' }}>
                                <div className="mb-2 flex items-center gap-1.5">
                                    <span className="size-2 shrink-0 rounded-full" style={{ background: 'var(--tb-success)' }} />
                                    <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: 'var(--tb-success-text)' }}>Allotted</span>
                                </div>
                                <span className="text-[1.65rem] font-extrabold leading-none tabular-nums" style={{ color: 'var(--tb-success)' }}>
                                    {allotedQty.toLocaleString()}
                                </span>
                                <span className="mt-1.5 text-[11px] font-semibold" style={{ color: 'var(--tb-success-text)' }}>
                                    ${allotedValue.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}
                                </span>
                            </div>

                            {/* Balance */}
                            <div className="flex flex-col px-5 py-4" style={{ background: balanceQty <= 0 ? 'rgba(16,185,129,0.06)' : 'var(--tb-brand-50)' }}>
                                <div className="mb-2 flex items-center gap-1.5">
                                    <span className="size-2 shrink-0 rounded-full" style={{ background: balanceQty <= 0 ? 'var(--tb-success)' : 'var(--tb-brand)' }} />
                                    <span className="text-[10px] font-bold uppercase tracking-widest" style={{ color: balanceQty <= 0 ? 'var(--tb-success-text)' : 'var(--tb-brand)' }}>Balance</span>
                                </div>
                                <span className="text-[1.65rem] font-extrabold leading-none tabular-nums" style={{ color: balanceQty <= 0 ? 'var(--tb-success)' : 'var(--tb-brand-active)' }}>
                                    {balanceQty.toLocaleString()}
                                </span>
                                <span className="mt-1.5 text-[11px] font-semibold" style={{ color: balanceQty <= 0 ? 'var(--tb-success-text)' : 'var(--tb-brand)' }}>
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
                <div className="card mb-3" style={{ borderRadius: 'var(--tb-r-md)' }}>
                    <div className="card-header border-bottom flex justify-between items-center py-3" style={{ borderRadius: '12px 12px 0 0' }}>
                        <h6 className="mb-0 font-semibold">
                            <CheckSquare className="size-4" aria-hidden="true" />
                            Allotted Items
                            <span className="ml-2 badge" style={{ background: 'rgba(16,185,129,0.1)', color: 'var(--tb-success-text)', fontWeight: '600', fontSize: 11 }}>
                                {allotment.allotment_details.length}
                            </span>
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
                        <div style={{overflowX: 'auto'}}>
                            <table className="w-full text-sm" style={{width: '100%'}}>
                                <thead style={{ backgroundColor: 'var(--tb-sunken)', borderBottom: '2px solid var(--tb-border)' }}>
                                <tr>
                                    <th style={{minWidth: '120px', whiteSpace: 'nowrap', fontWeight: '600', fontSize: 13.5, padding: '12px 8px'}}>License</th>
                                    <th style={{minWidth: '70px', whiteSpace: 'nowrap', fontWeight: '600', fontSize: 13.5, padding: '12px 8px'}}>Serial</th>
                                    <th style={{minWidth: '300px', fontWeight: '600', fontSize: 13.5, padding: '12px 8px'}}>Description</th>
                                    <th style={{minWidth: '100px', whiteSpace: 'nowrap', fontWeight: '600', fontSize: 13.5, padding: '12px 8px'}}>HSN Code</th>
                                    <th style={{minWidth: '200px', fontWeight: '600', fontSize: 13.5, padding: '12px 8px'}}>Exporter</th>
                                    <th style={{minWidth: '180px', fontWeight: '600', fontSize: 13.5, padding: '12px 8px'}}>Transfer<br/>Status</th>
                                    <th style={{minWidth: '100px', fontWeight: '600', fontSize: 13.5, padding: '12px 8px'}}>License<br/>Date</th>
                                    <th style={{minWidth: '100px', fontWeight: '600', fontSize: 13.5, padding: '12px 8px'}}>Expiry<br/>Date</th>
                                    <th style={{minWidth: '100px', textAlign: 'right', fontWeight: '600', fontSize: 13.5, padding: '12px 8px'}}>Allotted<br/>Qty</th>
                                    <th style={{minWidth: '110px', textAlign: 'right', fontWeight: '600', fontSize: 13.5, padding: '12px 8px'}}>Allotted<br/>Value</th>
                                    <th style={{minWidth: '80px', whiteSpace: 'nowrap', fontWeight: '600', fontSize: 13.5, padding: '12px 8px'}}>Action</th>
                                </tr>
                                </thead>
                                <tbody>
                                {allotment.allotment_details.map((detail) => (
                                    <tr key={detail.id}>
                                        <td style={{whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis'}}>{detail.license_number}</td>
                                        <td style={{whiteSpace: 'nowrap'}}>
                                            {detail.serial_number}
                                            <ConditionBadge type={detail.condition_type} size="xs" />
                                        </td>
                                        <td style={{wordWrap: 'break-word', whiteSpace: 'normal'}}>{detail.product_description}</td>
                                        <td style={{whiteSpace: 'nowrap'}}>{detail.hs_code || '-'}</td>
                                        <td style={{wordWrap: 'break-word', whiteSpace: 'normal'}}>{detail.exporter}</td>
                                        <td style={{wordWrap: 'break-word', whiteSpace: 'normal', fontSize: '0.80rem', lineHeight: '1.3'}}>
                                            {detail.current_owner && detail.file_transfer_status ? (
                                                <div>
                                                    <div className="mb-1" style={{fontWeight: '600'}}>
                                                        {detail.current_owner}
                                                    </div>
                                                    <div className="text-muted" style={{fontSize: 12}}>
                                                        {detail.file_transfer_status}
                                                    </div>
                                                </div>
                                            ) : detail.current_owner ? (
                                                <div style={{fontWeight: '600'}}>{detail.current_owner}</div>
                                            ) : detail.file_transfer_status ? (
                                                <div className="text-muted">{detail.file_transfer_status}</div>
                                            ) : (
                                                <span className="text-muted">-</span>
                                            )}
                                        </td>
                                        <td style={{whiteSpace: 'nowrap', fontSize: 13.5}}>{detail.license_date}</td>
                                        <td style={{whiteSpace: 'nowrap', fontSize: 13.5}}>{detail.license_expiry}</td>
                                        <td className="text-end" style={{whiteSpace: 'nowrap'}}>{parseInt(detail.qty || 0).toLocaleString()}</td>
                                        <td className="text-end" style={{whiteSpace: 'nowrap'}}>{parseFloat(detail.cif_fc || 0).toFixed(2)}</td>
                                        <td className="text-center" style={{whiteSpace: 'nowrap'}}>
                                            <button
                                                className="flex items-center gap-1.5 rounded border border-border bg-card px-2.5 py-1.5 text-xs font-medium text-muted-foreground cursor-pointer hover:bg-muted"
                                                onClick={() => handleDeleteAllotment(detail.id)}
                                                disabled={deletingItems[detail.id]}
                                                title="Remove this allocation"
                                            >
                                                {deletingItems[detail.id] ? (
                                                    <span className="inline-block size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent" aria-hidden="true" />
                                                ) : (
                                                    <Trash2 className="size-4" aria-hidden="true" />
                                                )}
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                                </tbody>
                                <tfoot className="table-secondary">
                                <tr>
                                    <th colSpan={8} className="text-end">Total:</th>
                                    <th className="text-end">{parseInt(allotment.alloted_quantity || 0).toLocaleString()}</th>
                                    <th className="text-end">{parseFloat(allotment.allotted_value || 0).toFixed(2)}</th>
                                    <th></th>
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

            <div className="card mb-3" style={{ borderRadius: 'var(--tb-r-md)' }}>
                <div className="card-header border-bottom flex justify-between items-center py-3" style={{ borderRadius: '12px 12px 0 0' }}>
                    <h6 className="mb-0 font-semibold">
                        <ListChecks className="size-4" aria-hidden="true" />
                        Available License Items
                        {pagination.totalItems > 0 && (
                            <span className="ml-2 text-muted-foreground font-normal" style={{ fontSize: '0.82rem' }}>{pagination.totalItems} items</span>
                        )}
                    </h6>
                </div>
                <div className="p-5">

                    {/* Show success/error messages near the table for better visibility */}
                    {error && (
                        <div className="alert alert-danger alert-dismissible fade show flex items-start gap-2" role="alert" style={{ borderRadius: 'var(--tb-r-md)' }}>
                            <TriangleAlert className="size-4" aria-hidden="true" />
                            <div className="flex-fill">{error}</div>
                            <button type="button" className="btn-close" onClick={() => setError("")}></button>
                        </div>
                    )}
                    {success && (
                        <div className="alert alert-success alert-dismissible fade show flex items-start gap-2" role="alert" style={{ borderRadius: 'var(--tb-r-md)' }}>
                            <CheckCircle2 className="size-4" aria-hidden="true" />
                            <div className="flex-fill">{success}</div>
                            <button type="button" className="btn-close" onClick={() => setSuccess("")}></button>
                        </div>
                    )}

                    <div className="card mb-3" style={{ background: 'var(--tb-sunken)', borderRadius: 'var(--tb-r-md)', border: '1px solid var(--tb-border)' }}>
                        <div className="card-header border-0 flex justify-between items-center py-2 px-3" style={{ background: 'transparent', borderBottom: '1px solid var(--tb-border-soft)' }}>
                            <span style={{ fontSize: 11, fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.08em', color: 'var(--tb-text-secondary)', display: 'flex', alignItems: 'center', gap: 6 }}>
                                <Filter className="size-4" aria-hidden="true" /> Filters
                            </span>
                            <button
                                className="cursor-pointer text-xs text-muted-foreground underline-offset-2 hover:underline bg-transparent border-0 p-0"
                                style={{ fontSize: 12, textDecoration: 'none' }}
                                onClick={() => setFilters({
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
                                    purchase_status: "GE,GO,SM,MI",
                                    license_status: "active",
                                    item_names: "",
                                    expiry_date_from: "",
                                    expiry_date_to: ""
                                })}
                            >
                                <XCircle className="size-4" aria-hidden="true" />Clear All
                            </button>
                        </div>
                        <div className="card-body" style={{ padding: '16px' }}>
                            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                                <div className="col-span-full sm:col-span-2 lg:col-span-4">
                                    <label className="form-label">Filter By Item Name</label>
                                    <Select
                                        isMulti
                                        value={filters.item_names ? filters.item_names.split(',').map(id => {
                                            const item = availableItemNames.find(i => i.value === parseInt(id));
                                            return item || {value: id, label: id};
                                        }) : []}
                                        onChange={(selected) => setFilters({...filters, item_names: selected ? selected.map(s => s.value).join(',') : ''})}
                                        options={availableItemNames}
                                        placeholder="All Item Names"
                                        className="basic-multi-select"
                                        classNamePrefix="select"
                                    />
                                </div>
                                <div>
                                    <label className="form-label">Norm Class</label>
                                    <HybridSelect
                                        fieldMeta={{endpoint: "masters/sion-classes/", label_field: "norm_class"}}
                                        value={filters.norm_class}
                                        onChange={(value) => setFilters({...filters, norm_class: value as string})}
                                        placeholder="All Norm Classes"
                                        isClearable={true}
                                    />
                                </div>
                                <div>
                                    <label className="form-label">Notification Number</label>
                                    <select
                                        className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                        value={filters.notification_number}
                                        onChange={(e) => setFilters({...filters, notification_number: e.target.value})}
                                    >
                                        <option value="">All</option>
                                        {notificationOptions.map((option) => (
                                            <option key={option.value} value={option.value}>
                                                {option.display_name}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                                <div>
                                    <label className="form-label">License Number</label>
                                    <input
                                        type="text"
                                        className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                        placeholder="Filter by license number..."
                                        value={filters.license_number}
                                        onChange={(e) => setFilters({...filters, license_number: e.target.value})}
                                    />
                                </div>
                                <div>
                                    <label className="form-label">Item Description</label>
                                    <input
                                        type="text"
                                        className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                        placeholder="Filter by item description..."
                                        value={filters.description}
                                        onChange={(e) => setFilters({...filters, description: e.target.value})}
                                    />
                                </div>
                                <div>
                                    <label className="form-label">Exporter</label>
                                    <HybridSelect
                                        fieldMeta={{endpoint: "masters/companies/", label_field: "name"}}
                                        value={filters.exporter}
                                        onChange={(value) => setFilters({...filters, exporter: value as string})}
                                        placeholder="All Exporters"
                                        isClearable={true}
                                    />
                                </div>
                                <div>
                                    <label className="form-label">Exclude Exporter</label>
                                    <HybridSelect
                                        fieldMeta={{endpoint: "masters/companies/", label_field: "name"}}
                                        value={filters.exclude_exporter}
                                        onChange={(value) => setFilters({...filters, exclude_exporter: value as string})}
                                        placeholder="None"
                                        isClearable={true}
                                    />
                                </div>
                                    <div>
                                        <label className="form-label">HS Code</label>
                                        <input
                                            type="text"
                                            className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                            value={filters.hs_code}
                                            onChange={(e) => setFilters({...filters, hs_code: e.target.value})}
                                        />
                                    </div>
                                    <div>
                                        <label className="form-label">Min Available Qty</label>
                                        <input
                                            type="number"
                                            className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                            value={filters.available_quantity_gte}
                                            onChange={(e) => setFilters({...filters, available_quantity_gte: e.target.value})}
                                        />
                                    </div>
                                    <div>
                                        <label className="form-label">Max Available Qty</label>
                                        <input
                                            type="number"
                                            className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                            value={filters.available_quantity_lte}
                                            onChange={(e) => setFilters({...filters, available_quantity_lte: e.target.value})}
                                        />
                                    </div>
                                    <div>
                                        <label className="form-label">Min Available Value</label>
                                        <input
                                            type="number"
                                            className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                            value={filters.available_value_gte}
                                            onChange={(e) => setFilters({...filters, available_value_gte: e.target.value})}
                                        />
                                    </div>
                                    <div>
                                        <label className="form-label">Max Available Value</label>
                                        <input
                                            type="number"
                                            className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                            value={filters.available_value_lte}
                                            onChange={(e) => setFilters({...filters, available_value_lte: e.target.value})}
                                        />
                                    </div>
                                    <div>
                                        <label className="form-label">Is Restricted</label>
                                        <select
                                            className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                            value={filters.is_restricted}
                                            onChange={(e) => setFilters({...filters, is_restricted: e.target.value})}
                                        >
                                            <option value="all">All</option>
                                            <option value="true">Restricted</option>
                                            <option value="false">Not Restricted</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label className="form-label">Purchase Status</label>
                                        <Select
                                            isMulti
                                            value={filters.purchase_status ? filters.purchase_status.split(',').map(s => ({
                                                value: s,
                                                label: s === 'GE' ? 'GE Purchase' : s === 'GO' ? 'GE Operating' : s === 'SM' ? 'SM Purchase' : s === 'MI' ? 'Conversion' : s === 'IP' ? 'IP' : 'CO'
                                            })) : []}
                                            onChange={(selected) => setFilters({...filters, purchase_status: selected ? selected.map(s => s.value).join(',') : ''})}
                                            options={[
                                                {value: 'GE', label: 'GE Purchase'},
                                                {value: 'GO', label: 'GE Operating'},
                                                {value: 'SM', label: 'SM Purchase'},
                                                {value: 'MI', label: 'Conversion'},
                                                {value: 'IP', label: 'IP'},
                                                {value: 'CO', label: 'CO'}
                                            ]}
                                            placeholder="All"
                                            className="basic-multi-select"
                                            classNamePrefix="select"
                                        />
                                    </div>
                                    <div>
                                        <label className="form-label">License Status</label>
                                        <select
                                            className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                            value={filters.license_status}
                                            onChange={(e) => setFilters({...filters, license_status: e.target.value})}
                                        >
                                            <option value="all">All</option>
                                            <option value="active">Active</option>
                                            <option value="expired">Expired</option>
                                            <option value="expiring_soon">Expiring Soon</option>
                                        </select>
                                    </div>
                                    <div>
                                        <label className="form-label">Expiry Date From</label>
                                        <input
                                            type="date"
                                            className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                            value={filters.expiry_date_from}
                                            onChange={(e) => setFilters({...filters, expiry_date_from: e.target.value})}
                                        />
                                    </div>
                                    <div>
                                        <label className="form-label">Expiry Date To</label>
                                        <input
                                            type="date"
                                            className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                            value={filters.expiry_date_to}
                                            onChange={(e) => setFilters({...filters, expiry_date_to: e.target.value})}
                                        />
                                    </div>
                                </div>
                            </div>
                        </div>

                    <div style={{ maxHeight: '650px', overflowY: 'auto', paddingRight: '2px' }}>
                        {availableItems.map((item) => {
                            const maxAllocation = calculateMaxAllocation(item);
                            const currentAllocation = allocationData[item.id];
                            const qty = parseFloat(item.available_quantity || 0);
                            const cifFc = parseFloat(item.balance_cif_fc || 0);
                            const average = qty > 0 ? (cifFc / qty).toFixed(2) : '0.00';
                            const isReady = currentAllocation && parseFloat(currentAllocation.qty) > 0;

                            return (
                                <div key={item.id} style={{
                                    display: 'block',
                                    background: 'var(--tb-card-bg)',
                                    border: `1px solid ${isReady ? 'var(--primary-color)' : 'var(--tb-border-soft)'}`,
                                    borderLeft: `4px solid ${isReady ? 'var(--primary-color)' : 'var(--tb-border-strong)'}`,
                                    borderRadius: 'var(--tb-r-md)',
                                    marginBottom: '10px',
                                    overflow: 'hidden',
                                    boxShadow: isReady ? '0 2px 12px rgba(79,70,229,0.12)' : '0 1px 3px rgba(0,0,0,0.06)',
                                }}>
                                    {/* ── Row 1: Identity bar ── */}
                                    <div style={{
                                        display: 'flex',
                                        alignItems: 'center',
                                        flexWrap: 'wrap',
                                        gap: '6px',
                                        padding: '9px 14px',
                                        background: 'var(--tb-sunken)',
                                        borderBottom: '1px solid #e2e8f0',
                                    }}>
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
                                            style={{
                                                background: 'none', border: 'none', padding: 0, cursor: 'pointer',
                                                fontWeight: '700', fontSize: 14, color: 'var(--primary-color)',
                                                marginRight: '4px', display: 'inline-flex', alignItems: 'center',
                                                textDecoration: 'underline', textUnderlineOffset: '3px', textDecorationStyle: 'dotted'
                                            }}
                                        >
                                            <FileText className="size-4" aria-hidden="true" />
                                            {item.license_number}
                                        </button>
                                        <span style={{
                                            background: 'var(--tb-border)', color: 'var(--text-secondary)',
                                            borderRadius: 'var(--tb-r-sm)', padding: '1px 7px', fontSize: 12, fontWeight: '600'
                                        }}>#{item.serial_number}</span>
                                        <ConditionBadge type={item.condition_type} size="xs" />

                                        {item.hs_code_label && (
                                            <span style={{
                                                background: 'var(--indigo-50)', color: 'var(--primary-dark)',
                                                border: '1px solid var(--indigo-200)',
                                                borderRadius: 'var(--tb-r-sm)', padding: '1px 7px', fontSize: 12,
                                            }}>HS: {item.hs_code_label}</span>
                                        )}
                                        {item.notification_number && (
                                            <span style={{fontSize: 12, color: 'var(--text-secondary)'}}>
                                                Notif: {item.notification_number}
                                            </span>
                                        )}
                                        <span style={{
                                            marginLeft: 'auto', fontSize: 12, color: 'var(--text-secondary)',
                                            display: 'flex', alignItems: 'center', gap: '4px'
                                        }}>
                                            <Calendar className="size-4" aria-hidden="true" />
                                            Exp: {item.license_expiry_date || '—'}
                                        </span>
                                        {/* Restriction is read-only — driven by the licence's
                                            condition_type. Use the shared badge. */}
                                        {item.condition_type
                                            ? <ConditionBadge type={item.condition_type} size="xs" />
                                            : (
                                                <span className="badge" style={{background: 'var(--success-bg)', color: 'var(--success-text)', border: '1px solid var(--success-border)', fontSize: 11}}>
                                                    <Unlock className="size-4" aria-hidden="true" />Open
                                                </span>
                                            )}
                                    </div>

                                    {/* ── Row 2: Description (full width) ── */}
                                    <div style={{padding: '10px 14px 8px', borderBottom: '1px solid #e2e8f0', background: 'var(--tb-card-bg)'}}>
                                        <div style={{fontWeight: '600', fontSize: 13.5, color: 'var(--tb-text)', lineHeight: '1.4', marginBottom: '2px'}}>
                                            {item.description}
                                        </div>
                                        <div style={{fontSize: 12, color: 'var(--text-secondary)', marginBottom: '6px'}}>
                                            <Building2 className="size-4" aria-hidden="true" />{item.exporter_name}
                                        </div>
                                        <div style={{display: 'flex', flexWrap: 'wrap', gap: '4px', alignItems: 'center'}}>
                                            {item.items_detail && item.items_detail.length > 0
                                                ? item.items_detail.map((i, idx) => (
                                                    <span key={idx} style={{
                                                        background: 'var(--indigo-50)', color: 'var(--primary-color)',
                                                        border: '1px solid var(--indigo-200)',
                                                        borderRadius: 'var(--tb-r-sm)', padding: '2px 8px',
                                                        fontSize: '0.73rem', fontWeight: '500',
                                                    }}>{i.name}</span>
                                                ))
                                                : <span style={{fontSize: 12, color: 'var(--text-secondary)'}}>No items</span>
                                            }
                                            {item.notes && (
                                                <span style={{fontSize: 11, color: 'var(--text-secondary)', fontStyle: 'italic', marginLeft: '4px'}}>
                                                    <StickyNote className="size-4" aria-hidden="true" />{item.notes}
                                                </span>
                                            )}
                                        </div>
                                    </div>

                                    {/* ── Row 3: Stats + Inputs + Action (compact bottom bar) ── */}
                                    <div style={{display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '0', background: 'var(--tb-sunken)'}}>

                                        {/* Availability stats */}
                                        <div style={{display: 'flex', gap: '16px', padding: '10px 14px', flexShrink: 0}}>
                                            {[
                                                {label: 'Avail Qty', value: qty.toFixed(3)},
                                                {label: 'CIF FC', value: cifFc.toFixed(2)},
                                                {label: 'Avg', value: average},
                                            ].map(({label, value}) => (
                                                <div key={label}>
                                                    <div style={{fontSize: '0.62rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.4px'}}>{label}</div>
                                                    <div style={{fontWeight: '700', fontSize: 14, color: 'var(--tb-text)', lineHeight: '1.3'}}>{value}</div>
                                                </div>
                                            ))}
                                        </div>

                                        <div style={{width: '1px', height: '36px', background: 'var(--tb-border-soft)', flexShrink: 0}} />

                                        {/* Allocation inputs */}
                                        <div style={{display: 'flex', gap: '10px', padding: '8px 14px', flexWrap: 'wrap', flex: 1, minWidth: '280px'}}>
                                            <div style={{flex: '1', minWidth: '130px'}}>
                                                <label style={{fontSize: '0.62rem', color: 'var(--text-secondary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.3px', display: 'block', marginBottom: '3px'}}>
                                                    Qty <span style={{fontWeight: '400', textTransform: 'none'}}>/ max {maxAllocation.qty}</span>
                                                </label>
                                                <div className="relative flex">
                                                    <input type="number" className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                                        value={currentAllocation?.qty || ""}
                                                        onChange={(e) => handleQuantityChange(item.id, e.target.value)}
                                                        placeholder="Qty"
                                                        step="1" min="0" max={maxAllocation.qty}
                                                        style={{fontSize: '0.82rem'}}
                                                    />
                                                    <button className="flex items-center gap-1.5 rounded border border-border bg-card px-2.5 py-1.5 text-xs font-medium text-muted-foreground cursor-pointer hover:bg-muted" type="button"
                                                        onClick={() => handleMaxQuantity(item)}
                                                        style={{fontSize: 12, fontWeight: '600'}}>Max</button>
                                                </div>
                                            </div>
                                            <div style={{flex: '1', minWidth: '130px'}}>
                                                <label style={{fontSize: '0.62rem', color: 'var(--text-secondary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.3px', display: 'block', marginBottom: '3px'}}>
                                                    Value <span style={{fontWeight: '400', textTransform: 'none'}}>/ max {maxAllocation.value.toFixed(2)}</span>
                                                </label>
                                                <div className="relative flex">
                                                    <input type="number" className="flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring "
                                                        value={currentAllocation?.cif_fc || ""}
                                                        onChange={(e) => handleValueChange(item.id, e.target.value)}
                                                        placeholder="Value"
                                                        step="0.01" min="0"
                                                        style={{fontSize: '0.82rem'}}
                                                    />
                                                    <button className="flex items-center gap-1.5 rounded border border-border bg-card px-2.5 py-1.5 text-xs font-medium text-muted-foreground cursor-pointer hover:bg-muted" type="button"
                                                        onClick={() => handleMaxValue(item)}
                                                        style={{fontSize: 12, fontWeight: '600'}}>Max</button>
                                                </div>
                                            </div>
                                        </div>

                                        <div style={{width: '1px', height: '36px', background: 'var(--tb-border-soft)', flexShrink: 0}} />

                                        {/* Confirm action */}
                                        <div style={{
                                            flexShrink: 0, padding: '8px 14px',
                                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                                        }}>
                                            <button
                                                className="flex items-center gap-1.5 rounded border border-border bg-card px-2.5 py-1.5 text-xs font-medium text-muted-foreground cursor-pointer hover:bg-muted"
                                                style={{
                                                    background: isReady ? 'var(--primary-gradient)' : 'var(--tb-gray-100)',
                                                    border: 'none',
                                                    color: isReady ? 'white' : 'var(--text-secondary)',
                                                    fontWeight: '600',
                                                    fontSize: '0.82rem',
                                                    padding: '10px 16px',
                                                    borderRadius: 'var(--tb-r-md)',
                                                    whiteSpace: 'nowrap',
                                                    transition: 'all 200ms',
                                                    cursor: isReady ? 'pointer' : 'not-allowed',
                                                }}
                                                onClick={() => handleConfirmAllot(item)}
                                                disabled={!isReady || saving[item.id]}
                                            >
                                                {saving[item.id] ? (
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
                        <div className="text-center py-5" style={{ border: '2px dashed #d1d5db', borderRadius: 'var(--tb-r-md)', background: 'var(--tb-card-bg)' }}>
                            <Inbox className="size-4" aria-hidden="true" />
                            <div className="font-semibold text-muted-foreground mb-1">No available license items found</div>
                            <small className="text-muted">Try adjusting the filters above</small>
                        </div>
                    )}

                    {/* Pagination */}
                    {pagination.totalPages > 1 && (
                        <div className="flex justify-between items-center mt-3 pt-3" style={{ borderTop: '1px solid var(--tb-border)' }}>
                            <div className="text-muted" style={{ fontSize: 14.5 }}>
                                Showing {((pagination.currentPage - 1) * pagination.pageSize) + 1} to {Math.min(pagination.currentPage * pagination.pageSize, pagination.totalItems)} of {pagination.totalItems} items
                            </div>
                            <nav>
                                <ul className="pagination mb-0">
                                    <li className={`page-item ${pagination.currentPage === 1 ? 'disabled' : ''}`}>
                                        <button
                                            className="page-link"
                                            style={{
                                                borderRadius: '6px 0 0 6px',
                                                fontWeight: '500'
                                            }}
                                            onClick={() => setPagination(prev => ({...prev, currentPage: prev.currentPage - 1}))}
                                            disabled={pagination.currentPage === 1}
                                        >
                                            Previous
                                        </button>
                                    </li>
                                    {[...Array(pagination.totalPages)].map((_, idx) => {
                                        const pageNum = idx + 1;
                                        // Show first, last, current, and pages around current
                                        if (
                                            pageNum === 1 ||
                                            pageNum === pagination.totalPages ||
                                            (pageNum >= pagination.currentPage - 2 && pageNum <= pagination.currentPage + 2)
                                        ) {
                                            return (
                                                <li key={pageNum} className={`page-item ${pagination.currentPage === pageNum ? 'active' : ''}`}>
                                                    <button
                                                        className="page-link"
                                                        style={{
                                                            background: pagination.currentPage === pageNum ? 'linear-gradient(135deg, var(--tb-brand), var(--tb-brand-hover))' : 'white',
                                                            border: pagination.currentPage === pageNum ? 'none' : '1px solid var(--tb-border)',
                                                            color: pagination.currentPage === pageNum ? 'white' : 'var(--primary-color)',
                                                            fontWeight: '500'
                                                        }}
                                                        onClick={() => setPagination(prev => ({...prev, currentPage: pageNum}))}
                                                    >
                                                        {pageNum}
                                                    </button>
                                                </li>
                                            );
                                        } else if (
                                            pageNum === pagination.currentPage - 3 ||
                                            pageNum === pagination.currentPage + 3
                                        ) {
                                            return <li key={pageNum} className="page-item disabled"><span className="page-link">...</span></li>;
                                        }
                                        return null;
                                    })}
                                    <li className={`page-item ${pagination.currentPage === pagination.totalPages ? 'disabled' : ''}`}>
                                        <button
                                            className="page-link"
                                            style={{
                                                borderRadius: '0 6px 6px 0',
                                                fontWeight: '500'
                                            }}
                                            onClick={() => setPagination(prev => ({...prev, currentPage: prev.currentPage + 1}))}
                                            disabled={pagination.currentPage === pagination.totalPages}
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

        </div>
    );
}
