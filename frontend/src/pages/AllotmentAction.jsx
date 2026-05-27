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
            const {data} = await api.options('/licenses/');
            const notificationChoices = data?.actions?.POST?.notification_number?.choices || [];
            setNotificationOptions(notificationChoices);
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
        <div style={{ backgroundColor: 'var(--bs-gray-50)', minHeight: '100vh', padding: '24px' }}>
            <div className="d-flex justify-content-between align-items-center mb-4 placeholder-glow">
                <div>
                    <div className="placeholder col-5" style={{ height: 28, borderRadius: 6, display: 'block' }}></div>
                    <div className="placeholder col-3 mt-1" style={{ height: 14, borderRadius: 4, display: 'block' }}></div>
                </div>
                <div className="d-flex gap-2">
                    {[80, 90, 110, 90, 100].map((w, i) => (
                        <div key={i} className="placeholder" style={{ width: w, height: 32, borderRadius: 6 }}></div>
                    ))}
                </div>
            </div>
            <div className="card border-0 shadow-sm mb-4 placeholder-glow" style={{ borderRadius: 12 }}>
                <div className="card-header bg-white py-3" style={{ borderRadius: '12px 12px 0 0' }}>
                    <div className="placeholder col-3" style={{ height: 18, borderRadius: 4 }}></div>
                </div>
                <div className="card-body d-flex gap-3 p-4">
                    {[1,2,3,4].map(i => <div key={i} className="placeholder flex-fill" style={{ borderRadius: 8, height: 72 }}></div>)}
                </div>
            </div>
            <div className="card border-0 shadow-sm placeholder-glow" style={{ borderRadius: 12 }}>
                <div className="card-header bg-white py-3" style={{ borderRadius: '12px 12px 0 0' }}>
                    <div className="placeholder col-4" style={{ height: 18, borderRadius: 4 }}></div>
                </div>
                <div className="card-body p-4">
                    {[1,2,3].map(i => <div key={i} className="placeholder w-100 mb-2" style={{ height: 90, borderRadius: 8 }}></div>)}
                </div>
            </div>
        </div>
    );

    return (
        <div style={{
            height: isModal ? '100%' : 'auto',
            display: 'flex',
            flexDirection: 'column',
            backgroundColor: isModal ? 'transparent' : 'var(--bs-gray-50)',
            padding: isModal ? '0' : '24px',
            minHeight: isModal ? 'auto' : '100vh'
        }}>
            {!isModal && (
                <div className="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-4">
                    <div>
                        <h4 className="mb-0 fw-bold" style={{ color: 'var(--text-dark)' }}>
                            <i className="bi bi-diagram-3 me-2" style={{ color: '#4F46E5' }}></i>
                            Allocate License Items
                        </h4>
                        {allotment && (
                            <small className="text-muted">
                                {allotment.item_name}
                                {allotment.invoice && <span className="ms-2">— Invoice #{allotment.invoice}</span>}
                            </small>
                        )}
                    </div>
                    <div className="d-flex gap-2 flex-wrap">
                        <button
                            className="btn btn-sm btn-outline-secondary"
                            onClick={() => {
                                if (isModal && onClose) { onClose(); }
                                sessionStorage.setItem('allotmentListFilters', JSON.stringify({ returnTo: 'edit', timestamp: new Date().getTime() }));
                                navigate(`/allotments/${id}/edit`);
                            }}
                            title="Edit Allotment"
                        >
                            <i className="bi bi-pencil-square me-1"></i>Edit
                        </button>
                        <button
                            className="btn btn-sm btn-outline-secondary"
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
                            <i className="bi bi-files me-1"></i>Copy
                        </button>
                        <button
                            className="btn btn-sm btn-primary"
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
                            style={{ background: 'linear-gradient(135deg,#4F46E5,#4338CA)', border: 'none' }}
                        >
                            <i className="bi bi-file-pdf me-1"></i>Download PDF
                        </button>
                        {allotment && allotment.allotment_details && allotment.allotment_details.length > 0 && (
                            <button
                                className="btn btn-sm btn-outline-secondary"
                                onClick={() => document.getElementById('transfer-letter-section')?.scrollIntoView({ behavior: 'smooth' })}
                                title="Generate Transfer Letter"
                            >
                                <i className="bi bi-file-earmark-text me-1"></i>Transfer Letter
                            </button>
                        )}
                        <button
                            className="btn btn-sm btn-outline-secondary"
                            onClick={() => {
                                sessionStorage.setItem('allotmentListFilters', JSON.stringify({ returnTo: 'list', timestamp: new Date().getTime() }));
                                navigate('/allotments');
                            }}
                        >
                            <i className="bi bi-arrow-left me-1"></i>Back
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
                // Use balanced_quantity from backend (already calculated correctly)
                const balanceQty = parseFloat(allotment.balanced_quantity || 0);
                const balanceValue = requiredValue - allotedValue;

                const progressPct = requiredQty > 0 ? Math.min(100, Math.round((allotedQty / requiredQty) * 100)) : 0;
                const progressColor = progressPct >= 100 ? '#10b981' : progressPct >= 60 ? '#4F46E5' : '#f59e0b';

                return (
                    <div className="card border-0 shadow-sm mb-4" style={{ borderRadius: '12px' }}>
                        <div className="card-header bg-white border-bottom d-flex justify-content-between align-items-center py-3" style={{ borderRadius: '12px 12px 0 0' }}>
                            <h6 className="mb-0 fw-semibold">
                                <i className="bi bi-info-circle me-2" style={{ color: '#4F46E5' }}></i>
                                Allotment Details
                                <span className="ms-2 text-muted fw-normal" style={{ fontSize: '0.85rem' }}>{allotment.item_name}</span>
                            </h6>
                            <span className="badge" style={{
                                background: progressPct >= 100 ? '#d1fae5' : 'rgba(79,70,229,0.1)',
                                color: progressPct >= 100 ? '#065f46' : '#4F46E5',
                                fontWeight: '600', fontSize: '0.75rem', padding: '5px 10px'
                            }}>
                                {progressPct}% Allotted
                            </span>
                        </div>
                        <div className="card-body" style={{ padding: '20px 24px' }}>
                            <div className="mb-4">
                                <div className="d-flex justify-content-between mb-1" style={{ fontSize: '0.72rem', color: 'var(--text-secondary)' }}>
                                    <span>Allotted: <strong>{allotedQty.toLocaleString()}</strong></span>
                                    <span>Required: <strong>{requiredQty.toLocaleString()}</strong></span>
                                </div>
                                <div style={{ height: 6, borderRadius: 4, background: '#e5e7eb', overflow: 'hidden' }}>
                                    <div style={{ height: '100%', borderRadius: 4, width: `${progressPct}%`, background: `linear-gradient(90deg, ${progressColor}, ${progressColor}cc)`, transition: 'width 0.4s ease' }} />
                                </div>
                            </div>
                            <div className="row g-3 align-items-stretch">
                                {/* Unit Price */}
                                <div className="col-lg-2 col-md-4">
                                    <div className="h-100 p-3 d-flex flex-column justify-content-center" style={{ backgroundColor: 'rgba(23,162,184,0.06)', borderRadius: '8px', border: '1px solid rgba(23,162,184,0.2)' }}>
                                        <small className="text-muted d-block mb-1" style={{ fontSize: '0.7rem', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.04em' }}>Unit Price</small>
                                        <strong style={{ fontSize: '1.15rem', color: 'var(--info-color)' }}>{unitPrice.toFixed(3)}</strong>
                                    </div>
                                </div>

                                {/* Required group */}
                                <div className="col-lg-3 col-md-8">
                                    <div className="h-100 p-3" style={{ backgroundColor: 'var(--bs-gray-50)', borderRadius: '8px', border: '1px solid #e9ecef', borderTop: '3px solid #6c757d' }}>
                                        <small className="d-block mb-2" style={{ fontSize: '0.68rem', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.06em', color: '#6c757d' }}>Required</small>
                                        <div className="d-flex gap-3">
                                            <div>
                                                <small className="text-muted d-block" style={{ fontSize: '0.7rem' }}>Quantity</small>
                                                <strong style={{ fontSize: '1.05rem', color: 'var(--text-dark)' }}>{requiredQty.toLocaleString()}</strong>
                                            </div>
                                            <div style={{ width: 1, backgroundColor: '#dee2e6' }} />
                                            <div>
                                                <small className="text-muted d-block" style={{ fontSize: '0.7rem' }}>Value</small>
                                                <strong style={{ fontSize: '1.05rem', color: 'var(--text-dark)' }}>{requiredValue.toFixed(2)}</strong>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                {/* Allotted group */}
                                <div className="col-lg-3 col-md-6">
                                    <div className="h-100 p-3" style={{ backgroundColor: 'rgba(40,167,69,0.04)', borderRadius: '8px', border: '1px solid rgba(40,167,69,0.2)', borderTop: '3px solid #28a745' }}>
                                        <small className="d-block mb-2" style={{ fontSize: '0.68rem', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.06em', color: '#28a745' }}>Allotted</small>
                                        <div className="d-flex gap-3">
                                            <div>
                                                <small className="text-muted d-block" style={{ fontSize: '0.7rem' }}>Quantity</small>
                                                <strong style={{ fontSize: '1.05rem', color: 'var(--success-color)' }}>{allotedQty.toLocaleString()}</strong>
                                            </div>
                                            <div style={{ width: 1, backgroundColor: 'rgba(40,167,69,0.2)' }} />
                                            <div>
                                                <small className="text-muted d-block" style={{ fontSize: '0.7rem' }}>Value</small>
                                                <strong style={{ fontSize: '1.05rem', color: 'var(--success-color)' }}>{allotedValue.toFixed(2)}</strong>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                {/* Balance group */}
                                <div className="col-lg-4 col-md-6">
                                    <div className="h-100 p-3" style={{ backgroundColor: 'rgba(79,70,229,0.04)', borderRadius: '8px', border: '1px solid rgba(79,70,229,0.2)', borderTop: '3px solid #4F46E5' }}>
                                        <small className="d-block mb-2" style={{ fontSize: '0.68rem', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.06em', color: '#4F46E5' }}>Balance</small>
                                        <div className="d-flex gap-3 align-items-end">
                                            <div>
                                                <small className="text-muted d-block" style={{ fontSize: '0.7rem' }}>Quantity</small>
                                                <strong style={{ fontSize: '1.05rem', color: 'var(--primary-color)' }}>{balanceQty.toLocaleString()}</strong>
                                            </div>
                                            <div style={{ width: 1, backgroundColor: 'rgba(79,70,229,0.2)' }} />
                                            <div>
                                                <small className="text-muted d-block" style={{ fontSize: '0.7rem' }}>Value <span className="text-muted" style={{ fontWeight: '400' }}>(+$20 buffer)</span></small>
                                                <strong style={{ fontSize: '1.05rem', color: 'var(--primary-color)' }}>{balanceValue.toFixed(2)}</strong>
                                            </div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                );
            })()}

            {/* Allotted Items Table */}
            {allotment && allotment.allotment_details && allotment.allotment_details.length > 0 && (
                <div className="card border-0 shadow-sm mb-4" style={{ borderRadius: '12px' }}>
                    <div className="card-header bg-white border-bottom d-flex justify-content-between align-items-center py-3" style={{ borderRadius: '12px 12px 0 0' }}>
                        <h6 className="mb-0 fw-semibold">
                            <i className="bi bi-check-square me-2" style={{ color: '#10b981' }}></i>
                            Allotted Items
                            <span className="ms-2 badge" style={{ background: 'rgba(16,185,129,0.1)', color: '#065f46', fontWeight: '600', fontSize: '0.72rem' }}>
                                {allotment.allotment_details.length}
                            </span>
                        </h6>
                        <button
                            className="btn btn-sm btn-outline-secondary"
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
                                <i className="bi bi-clipboard"></i> Copy
                            </button>
                    </div>
                    <div className="card-body p-0">
                        <div style={{overflowX: 'auto'}}>
                            <table className="table table-sm table-hover mb-0" style={{width: '100%'}}>
                                <thead style={{ backgroundColor: 'var(--bs-gray-50)', borderBottom: '2px solid #dee2e6' }}>
                                <tr>
                                    <th style={{minWidth: '120px', whiteSpace: 'nowrap', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>License</th>
                                    <th style={{minWidth: '70px', whiteSpace: 'nowrap', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>Serial</th>
                                    <th style={{minWidth: '300px', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>Description</th>
                                    <th style={{minWidth: '100px', whiteSpace: 'nowrap', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>HSN Code</th>
                                    <th style={{minWidth: '200px', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>Exporter</th>
                                    <th style={{minWidth: '180px', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>Transfer<br/>Status</th>
                                    <th style={{minWidth: '100px', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>License<br/>Date</th>
                                    <th style={{minWidth: '100px', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>Expiry<br/>Date</th>
                                    <th style={{minWidth: '100px', textAlign: 'right', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>Allotted<br/>Qty</th>
                                    <th style={{minWidth: '110px', textAlign: 'right', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>Allotted<br/>Value</th>
                                    <th style={{minWidth: '80px', whiteSpace: 'nowrap', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>Action</th>
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
                                                    <div className="text-muted" style={{fontSize: '0.75rem'}}>
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
                                        <td style={{whiteSpace: 'nowrap', fontSize: '0.85rem'}}>{detail.license_date}</td>
                                        <td style={{whiteSpace: 'nowrap', fontSize: '0.85rem'}}>{detail.license_expiry}</td>
                                        <td className="text-end" style={{whiteSpace: 'nowrap'}}>{parseInt(detail.qty || 0).toLocaleString()}</td>
                                        <td className="text-end" style={{whiteSpace: 'nowrap'}}>{parseFloat(detail.cif_fc || 0).toFixed(2)}</td>
                                        <td className="text-center" style={{whiteSpace: 'nowrap'}}>
                                            <button
                                                className="btn btn-outline-secondary btn-sm"
                                                onClick={() => handleDeleteAllotment(detail.id)}
                                                disabled={deletingItems[detail.id]}
                                                title="Remove this allocation"
                                            >
                                                {deletingItems[detail.id] ? (
                                                    <span className="spinner-border spinner-border-sm" role="status"></span>
                                                ) : (
                                                    <i className="bi bi-trash"></i>
                                                )}
                                            </button>
                                        </td>
                                    </tr>
                                ))}
                                </tbody>
                                <tfoot className="table-secondary">
                                <tr>
                                    <th colSpan="8" className="text-end">Total:</th>
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

            <div className="card border-0 shadow-sm mb-4" style={{ borderRadius: '12px' }}>
                <div className="card-header bg-white border-bottom d-flex justify-content-between align-items-center py-3" style={{ borderRadius: '12px 12px 0 0' }}>
                    <h6 className="mb-0 fw-semibold">
                        <i className="bi bi-list-check me-2" style={{ color: '#4F46E5' }}></i>
                        Available License Items
                        {pagination.totalItems > 0 && (
                            <span className="ms-2 text-muted fw-normal" style={{ fontSize: '0.82rem' }}>{pagination.totalItems} items</span>
                        )}
                    </h6>
                </div>
                <div className="card-body" style={{ padding: '20px 24px' }}>

                    {/* Show success/error messages near the table for better visibility */}
                    {error && (
                        <div className="alert alert-danger alert-dismissible fade show d-flex align-items-start gap-2" role="alert" style={{ borderRadius: '8px' }}>
                            <i className="bi bi-exclamation-triangle-fill flex-shrink-0 mt-1"></i>
                            <div className="flex-fill">{error}</div>
                            <button type="button" className="btn-close" onClick={() => setError("")}></button>
                        </div>
                    )}
                    {success && (
                        <div className="alert alert-success alert-dismissible fade show d-flex align-items-start gap-2" role="alert" style={{ borderRadius: '8px' }}>
                            <i className="bi bi-check-circle-fill flex-shrink-0 mt-1"></i>
                            <div className="flex-fill">{success}</div>
                            <button type="button" className="btn-close" onClick={() => setSuccess("")}></button>
                        </div>
                    )}

                    <div className="card border-0 mb-4" style={{ background: 'var(--bs-gray-50)', borderRadius: '10px', border: '1px solid #e5e7eb !important' }}>
                        <div className="card-header border-0 d-flex justify-content-between align-items-center py-2 px-3" style={{ background: 'transparent', borderBottom: '1px solid #e5e7eb' }}>
                            <span style={{ fontSize: '0.72rem', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#6b7280', display: 'flex', alignItems: 'center', gap: 6 }}>
                                <i className="bi bi-funnel"></i> Filters
                            </span>
                            <button
                                className="btn btn-sm btn-link text-muted p-0"
                                style={{ fontSize: '0.78rem', textDecoration: 'none' }}
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
                                <i className="bi bi-x-circle me-1"></i>Clear All
                            </button>
                        </div>
                        <div className="card-body" style={{ padding: '16px' }}>
                            <div className="row g-3">
                                <div className="col-md-12">
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
                                <div className="col-md-3">
                                    <label className="form-label">Norm Class</label>
                                    <HybridSelect
                                        fieldMeta={{endpoint: "masters/sion-classes/", label_field: "norm_class"}}
                                        value={filters.norm_class}
                                        onChange={(value) => setFilters({...filters, norm_class: value})}
                                        placeholder="All Norm Classes"
                                        isClearable={true}
                                    />
                                </div>
                                <div className="col-md-3">
                                    <label className="form-label">Notification Number</label>
                                    <select
                                        className="form-control form-control-sm"
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
                                <div className="col-md-3">
                                    <label className="form-label">License Number</label>
                                    <input
                                        type="text"
                                        className="form-control form-control-sm"
                                        placeholder="Filter by license number..."
                                        value={filters.license_number}
                                        onChange={(e) => setFilters({...filters, license_number: e.target.value})}
                                    />
                                </div>
                                <div className="col-md-3">
                                    <label className="form-label">Item Description</label>
                                    <input
                                        type="text"
                                        className="form-control form-control-sm"
                                        placeholder="Filter by item description..."
                                        value={filters.description}
                                        onChange={(e) => setFilters({...filters, description: e.target.value})}
                                    />
                                </div>
                                <div className="col-md-3">
                                    <label className="form-label">Exporter</label>
                                    <HybridSelect
                                        fieldMeta={{endpoint: "masters/companies/", label_field: "name"}}
                                        value={filters.exporter}
                                        onChange={(value) => setFilters({...filters, exporter: value})}
                                        placeholder="All Exporters"
                                        isClearable={true}
                                    />
                                </div>
                                <div className="col-md-3">
                                    <label className="form-label">Exclude Exporter</label>
                                    <HybridSelect
                                        fieldMeta={{endpoint: "masters/companies/", label_field: "name"}}
                                        value={filters.exclude_exporter}
                                        onChange={(value) => setFilters({...filters, exclude_exporter: value})}
                                        placeholder="None"
                                        isClearable={true}
                                    />
                                </div>
                                    <div className="col-md-3">
                                        <label className="form-label">HS Code</label>
                                        <input
                                            type="text"
                                            className="form-control form-control-sm"
                                            value={filters.hs_code}
                                            onChange={(e) => setFilters({...filters, hs_code: e.target.value})}
                                        />
                                    </div>
                                    <div className="col-md-3">
                                        <label className="form-label">Min Available Qty</label>
                                        <input
                                            type="number"
                                            className="form-control form-control-sm"
                                            value={filters.available_quantity_gte}
                                            onChange={(e) => setFilters({...filters, available_quantity_gte: e.target.value})}
                                        />
                                    </div>
                                    <div className="col-md-3">
                                        <label className="form-label">Max Available Qty</label>
                                        <input
                                            type="number"
                                            className="form-control form-control-sm"
                                            value={filters.available_quantity_lte}
                                            onChange={(e) => setFilters({...filters, available_quantity_lte: e.target.value})}
                                        />
                                    </div>
                                    <div className="col-md-3">
                                        <label className="form-label">Min Available Value</label>
                                        <input
                                            type="number"
                                            className="form-control form-control-sm"
                                            value={filters.available_value_gte}
                                            onChange={(e) => setFilters({...filters, available_value_gte: e.target.value})}
                                        />
                                    </div>
                                    <div className="col-md-3">
                                        <label className="form-label">Max Available Value</label>
                                        <input
                                            type="number"
                                            className="form-control form-control-sm"
                                            value={filters.available_value_lte}
                                            onChange={(e) => setFilters({...filters, available_value_lte: e.target.value})}
                                        />
                                    </div>
                                    <div className="col-md-3">
                                        <label className="form-label">Is Restricted</label>
                                        <select
                                            className="form-control form-control-sm"
                                            value={filters.is_restricted}
                                            onChange={(e) => setFilters({...filters, is_restricted: e.target.value})}
                                        >
                                            <option value="all">All</option>
                                            <option value="true">Restricted</option>
                                            <option value="false">Not Restricted</option>
                                        </select>
                                    </div>
                                    <div className="col-md-3">
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
                                    <div className="col-md-3">
                                        <label className="form-label">License Status</label>
                                        <select
                                            className="form-control form-control-sm"
                                            value={filters.license_status}
                                            onChange={(e) => setFilters({...filters, license_status: e.target.value})}
                                        >
                                            <option value="all">All</option>
                                            <option value="active">Active</option>
                                            <option value="expired">Expired</option>
                                            <option value="expiring_soon">Expiring Soon</option>
                                        </select>
                                    </div>
                                    <div className="col-md-3">
                                        <label className="form-label">Expiry Date From</label>
                                        <input
                                            type="date"
                                            className="form-control form-control-sm"
                                            value={filters.expiry_date_from}
                                            onChange={(e) => setFilters({...filters, expiry_date_from: e.target.value})}
                                        />
                                    </div>
                                    <div className="col-md-3">
                                        <label className="form-label">Expiry Date To</label>
                                        <input
                                            type="date"
                                            className="form-control form-control-sm"
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
                                    background: '#ffffff',
                                    border: `1px solid ${isReady ? 'var(--primary-color)' : '#e2e8f0'}`,
                                    borderLeft: `4px solid ${isReady ? 'var(--primary-color)' : '#cbd5e1'}`,
                                    borderRadius: '10px',
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
                                        background: '#f8fafc',
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
                                                fontWeight: '700', fontSize: '0.88rem', color: 'var(--primary-color)',
                                                marginRight: '4px', display: 'inline-flex', alignItems: 'center',
                                                textDecoration: 'underline', textUnderlineOffset: '3px', textDecorationStyle: 'dotted'
                                            }}
                                        >
                                            <i className="bi bi-file-earmark-text me-1" style={{fontSize: '0.8rem'}}></i>
                                            {item.license_number}
                                        </button>
                                        <span style={{
                                            background: 'var(--bs-gray-200)', color: 'var(--text-secondary)',
                                            borderRadius: '4px', padding: '1px 7px', fontSize: '0.75rem', fontWeight: '600'
                                        }}>#{item.serial_number}</span>
                                        <ConditionBadge type={item.condition_type} size="xs" />

                                        {item.hs_code_label && (
                                            <span style={{
                                                background: 'var(--indigo-50)', color: 'var(--primary-dark)',
                                                border: '1px solid var(--indigo-200)',
                                                borderRadius: '4px', padding: '1px 7px', fontSize: '0.75rem',
                                            }}>HS: {item.hs_code_label}</span>
                                        )}
                                        {item.notification_number && (
                                            <span style={{fontSize: '0.75rem', color: 'var(--text-secondary)'}}>
                                                Notif: {item.notification_number}
                                            </span>
                                        )}
                                        <span style={{
                                            marginLeft: 'auto', fontSize: '0.75rem', color: 'var(--text-secondary)',
                                            display: 'flex', alignItems: 'center', gap: '4px'
                                        }}>
                                            <i className="bi bi-calendar3" style={{fontSize: '0.7rem'}}></i>
                                            Exp: {item.license_expiry_date || '—'}
                                        </span>
                                        {/* Restriction is read-only — driven by the licence's
                                            condition_type. Use the shared badge. */}
                                        {item.condition_type
                                            ? <ConditionBadge type={item.condition_type} size="xs" />
                                            : (
                                                <span className="badge" style={{background: 'var(--success-bg)', color: 'var(--success-text)', border: '1px solid var(--success-border)', fontSize: '0.7rem'}}>
                                                    <i className="bi bi-unlock-fill me-1"></i>Open
                                                </span>
                                            )}
                                    </div>

                                    {/* ── Row 2: Description (full width) ── */}
                                    <div style={{padding: '10px 14px 8px', borderBottom: '1px solid #e2e8f0', background: '#ffffff'}}>
                                        <div style={{fontWeight: '600', fontSize: '0.85rem', color: 'var(--text-dark)', lineHeight: '1.4', marginBottom: '2px'}}>
                                            {item.description}
                                        </div>
                                        <div style={{fontSize: '0.78rem', color: 'var(--text-secondary)', marginBottom: '6px'}}>
                                            <i className="bi bi-building me-1" style={{fontSize: '0.7rem'}}></i>{item.exporter_name}
                                        </div>
                                        <div style={{display: 'flex', flexWrap: 'wrap', gap: '4px', alignItems: 'center'}}>
                                            {item.items_detail && item.items_detail.length > 0
                                                ? item.items_detail.map((i, idx) => (
                                                    <span key={idx} style={{
                                                        background: 'var(--indigo-50)', color: 'var(--primary-color)',
                                                        border: '1px solid var(--indigo-200)',
                                                        borderRadius: '4px', padding: '2px 8px',
                                                        fontSize: '0.73rem', fontWeight: '500',
                                                    }}>{i.name}</span>
                                                ))
                                                : <span style={{fontSize: '0.75rem', color: 'var(--text-secondary)'}}>No items</span>
                                            }
                                            {item.notes && (
                                                <span style={{fontSize: '0.72rem', color: 'var(--text-secondary)', fontStyle: 'italic', marginLeft: '4px'}}>
                                                    <i className="bi bi-sticky me-1"></i>{item.notes}
                                                </span>
                                            )}
                                        </div>
                                    </div>

                                    {/* ── Row 3: Stats + Inputs + Action (compact bottom bar) ── */}
                                    <div style={{display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: '0', background: '#f8fafc'}}>

                                        {/* Availability stats */}
                                        <div style={{display: 'flex', gap: '16px', padding: '10px 14px', flexShrink: 0}}>
                                            {[
                                                {label: 'Avail Qty', value: qty.toFixed(3)},
                                                {label: 'CIF FC', value: cifFc.toFixed(2)},
                                                {label: 'Avg', value: average},
                                            ].map(({label, value}) => (
                                                <div key={label}>
                                                    <div style={{fontSize: '0.62rem', color: 'var(--text-secondary)', textTransform: 'uppercase', letterSpacing: '0.4px'}}>{label}</div>
                                                    <div style={{fontWeight: '700', fontSize: '0.88rem', color: 'var(--text-dark)', lineHeight: '1.3'}}>{value}</div>
                                                </div>
                                            ))}
                                        </div>

                                        <div style={{width: '1px', height: '36px', background: '#e2e8f0', flexShrink: 0}} />

                                        {/* Allocation inputs */}
                                        <div style={{display: 'flex', gap: '10px', padding: '8px 14px', flexWrap: 'wrap', flex: 1, minWidth: '280px'}}>
                                            <div style={{flex: '1', minWidth: '130px'}}>
                                                <label style={{fontSize: '0.62rem', color: 'var(--text-secondary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.3px', display: 'block', marginBottom: '3px'}}>
                                                    Qty <span style={{fontWeight: '400', textTransform: 'none'}}>/ max {maxAllocation.qty}</span>
                                                </label>
                                                <div className="input-group input-group-sm">
                                                    <input type="number" className="form-control form-control-sm"
                                                        value={currentAllocation?.qty || ""}
                                                        onChange={(e) => handleQuantityChange(item.id, e.target.value)}
                                                        placeholder="Qty"
                                                        step="1" min="0" max={maxAllocation.qty}
                                                        style={{fontSize: '0.82rem'}}
                                                    />
                                                    <button className="btn btn-outline-secondary btn-sm" type="button"
                                                        onClick={() => handleMaxQuantity(item)}
                                                        style={{fontSize: '0.75rem', fontWeight: '600'}}>Max</button>
                                                </div>
                                            </div>
                                            <div style={{flex: '1', minWidth: '130px'}}>
                                                <label style={{fontSize: '0.62rem', color: 'var(--text-secondary)', fontWeight: '600', textTransform: 'uppercase', letterSpacing: '0.3px', display: 'block', marginBottom: '3px'}}>
                                                    Value <span style={{fontWeight: '400', textTransform: 'none'}}>/ max {maxAllocation.value.toFixed(2)}</span>
                                                </label>
                                                <div className="input-group input-group-sm">
                                                    <input type="number" className="form-control form-control-sm"
                                                        value={currentAllocation?.cif_fc || ""}
                                                        onChange={(e) => handleValueChange(item.id, e.target.value)}
                                                        placeholder="Value"
                                                        step="0.01" min="0"
                                                        style={{fontSize: '0.82rem'}}
                                                    />
                                                    <button className="btn btn-outline-secondary btn-sm" type="button"
                                                        onClick={() => handleMaxValue(item)}
                                                        style={{fontSize: '0.75rem', fontWeight: '600'}}>Max</button>
                                                </div>
                                            </div>
                                        </div>

                                        <div style={{width: '1px', height: '36px', background: '#e2e8f0', flexShrink: 0}} />

                                        {/* Confirm action */}
                                        <div style={{
                                            flexShrink: 0, padding: '8px 14px',
                                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                                        }}>
                                            <button
                                                className="btn btn-sm"
                                                style={{
                                                    background: isReady ? 'var(--primary-gradient)' : 'var(--bs-gray-100)',
                                                    border: 'none',
                                                    color: isReady ? 'white' : 'var(--text-secondary)',
                                                    fontWeight: '600',
                                                    fontSize: '0.82rem',
                                                    padding: '10px 16px',
                                                    borderRadius: '8px',
                                                    whiteSpace: 'nowrap',
                                                    transition: 'all 200ms',
                                                    cursor: isReady ? 'pointer' : 'not-allowed',
                                                }}
                                                onClick={() => handleConfirmAllot(item)}
                                                disabled={!isReady || saving[item.id]}
                                            >
                                                {saving[item.id] ? (
                                                    <>
                                                        <span className="spinner-border spinner-border-sm me-1" role="status"></span>
                                                        Saving…
                                                    </>
                                                ) : (
                                                    <>
                                                        <i className="bi bi-check2-circle me-1"></i>
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
                        <div className="text-center py-4">
                            <div className="spinner-border spinner-border-sm text-primary" role="status">
                                <span className="visually-hidden">Loading...</span>
                            </div>
                            <span className="ms-2 text-muted" style={{ fontSize: '0.9rem' }}>Loading items...</span>
                        </div>
                    )}

                    {!tableLoading && availableItems.length === 0 && (
                        <div className="text-center py-5" style={{ border: '2px dashed #d1d5db', borderRadius: '10px', background: 'white' }}>
                            <i className="bi bi-inbox d-block mb-2" style={{ fontSize: '2rem', color: '#9ca3af' }}></i>
                            <div className="fw-semibold text-muted mb-1">No available license items found</div>
                            <small className="text-muted">Try adjusting the filters above</small>
                        </div>
                    )}

                    {/* Pagination */}
                    {pagination.totalPages > 1 && (
                        <div className="d-flex justify-content-between align-items-center mt-3 pt-3" style={{ borderTop: '1px solid #dee2e6' }}>
                            <div className="text-muted" style={{ fontSize: '0.9rem' }}>
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
                                                            background: pagination.currentPage === pageNum ? 'linear-gradient(135deg, #4F46E5 0%, #4338CA 100%)' : 'white',
                                                            border: pagination.currentPage === pageNum ? 'none' : '1px solid #dee2e6',
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
