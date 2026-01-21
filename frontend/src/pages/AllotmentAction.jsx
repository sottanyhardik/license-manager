import {useEffect, useState} from "react";
import {useParams, useNavigate, useLocation} from "react-router-dom";
import { toast } from 'react-toastify';
import Select from "react-select";
import api from "../api/axios";
import HybridSelect from "../components/HybridSelect";
import TransferLetterForm from "../components/TransferLetterForm";
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
    const [search, setSearch] = useState("");
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
        is_expired: "false",
        is_restricted: "all",
        purchase_status: "GE,GO,SM,MI",  // GE Purchase, GE Operating, SM Purchase, Conversion
        license_status: "active",
        item_names: ""
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

    // Enable browser back button support with filter preservation
    useBackButton('allotments', !isModal);

    useEffect(() => {
        fetchNotificationOptions();
        fetchAvailableItemNames();
        // Fetch allotment info first to get item_name
        fetchAllotmentInfo();
    }, []);

    // Set description from allotment item_name on first load
    useEffect(() => {
        if (isFirstLoad && allotment?.item_name) {
            setFilters(prev => ({...prev, description: allotment.item_name}));
            setIsFirstLoad(false);
        }
    }, [allotment, isFirstLoad]);

    useEffect(() => {
        // Skip initial fetch if we're waiting for allotment data to set the description filter
        if (isFirstLoad && !allotment?.item_name) {
            return;
        }

        const timer = setTimeout(() => {
            setPagination(prev => ({...prev, currentPage: 1})); // Reset to page 1 on filter change
            fetchData(1);
        }, 300); // Debounce for 300ms
        return () => clearTimeout(timer);
    }, [id, search, filters, isFirstLoad, allotment?.item_name]);

    useEffect(() => {
        // Skip pagination fetch if we're still on first load waiting for description filter
        if (isFirstLoad && !allotment?.item_name) {
            return;
        }
        fetchData(pagination.currentPage);
    }, [pagination.currentPage]);

    // Scroll to transfer letter section if navigated from list
    useEffect(() => {
        if (location.state?.scrollToTransferLetter && allotment) {
            setTimeout(() => {
                document.getElementById('transfer-letter-section')?.scrollIntoView({ behavior: 'smooth' });
            }, 500);
        }
    }, [location.state, allotment]);

    const fetchNotificationOptions = async () => {
        try {
            // Fetch notification number options from licenses
            const {data} = await api.options('/licenses/');
            const notificationChoices = data?.actions?.POST?.notification_number?.choices || [];
            setNotificationOptions(notificationChoices);
        } catch (err) {
            // Silently fail for notification options
        }
    };

    const fetchAvailableItemNames = async () => {
        try {
            const {data} = await api.get('item-report/available-items/');
            const items = data || [];
            setAvailableItemNames(items.map(item => ({value: item.id, label: item.name})));
        } catch (err) {
            // Silently fail for item names
        }
    };

    const fetchAllotmentInfo = async () => {
        try {
            // Fetch just the allotment info without available items
            const {data} = await api.get(`/allotments/${id}/`);
            setAllotment(data);
        } catch (err) {
            setError(err.response?.data?.detail || "Failed to load allotment info");
        }
    };

    const fetchData = async (page = 1) => {
        // Use initialLoading only on first load, tableLoading for subsequent loads
        if (allotment === null) {
            setInitialLoading(true);
        } else {
            setTableLoading(true);
        }
        setError("");
        try {
            // Build params object, only include non-empty values
            const params = {
                search,
                page,
                page_size: pagination.pageSize
            };
            Object.keys(filters).forEach(key => {
                if (filters[key]) {
                    params[key] = filters[key];
                }
            });

            console.log('Fetching with params:', params);
            console.log('Current filters:', filters);

            const {data} = await api.get(`/allotment-actions/${id}/available-licenses/`, {
                params
            });
            setAllotment(data.allotment);
            setAvailableItems(data.available_items || data.results || []);

            // Update pagination info if provided by backend
            if (data.count !== undefined) {
                setPagination(prev => ({
                    ...prev,
                    totalItems: data.count,
                    totalPages: Math.ceil(data.count / prev.pageSize)
                }));
            }
        } catch (err) {
            setError(err.response?.data?.detail || "Failed to load data");
        } finally {
            setInitialLoading(false);
            setTableLoading(false);
        }
    };

    const calculateMaxAllocation = (item) => {
        if (!allotment?.unit_value_per_unit) return { qty: 0, value: 0 };

        const unitPrice = parseFloat(allotment.unit_value_per_unit);
        // Use balanced_quantity directly from backend (already calculated: required - allotted)
        const balancedQty = parseFloat(allotment.balanced_quantity || 0);
        const requiredValue = parseFloat(allotment.required_value || 0);
        const requiredValueWithBuffer = parseFloat(allotment.required_value_with_buffer || (requiredValue + 20));
        const allottedValue = parseFloat(allotment.allotted_value || 0);
        const balancedValueWithBuffer = requiredValueWithBuffer - allottedValue;
        const availableQty = parseFloat(item.available_quantity);
        const availableCifFc = parseFloat(item.balance_cif_fc || 0);

        // Max quantity is the minimum of balanced quantity and available quantity
        let maxQty = Math.min(balancedQty, availableQty);

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
        const availableQty = parseFloat(item.available_quantity || 0);

        // Constrain to minimum of balanced quantity and available quantity
        if (inputQty > balancedQty) {
            inputQty = balancedQty;
        }
        if (inputQty > availableQty) {
            inputQty = availableQty;
        }

        // Calculate value from quantity
        let allocateCifFc = inputQty * unitPrice;

        // If calculated value exceeds balanced value with buffer, adjust quantity down
        if (allocateCifFc > balancedValueWithBuffer) {
            inputQty = Math.floor(balancedValueWithBuffer / unitPrice);
            allocateCifFc = inputQty * unitPrice;
        }

        // If calculated value exceeds available CIF FC, adjust quantity down
        if (allocateCifFc > availableCifFc) {
            inputQty = Math.floor(availableCifFc / unitPrice);
            allocateCifFc = inputQty * unitPrice;
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
            const {data} = await api.post(`/allotment-actions/${id}/allocate-items/`, {
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
            const {data} = await api.delete(`/allotment-actions/${id}/delete-item/${allotmentItemId}/`);
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

    if (initialLoading) return <div className="p-4">Loading...</div>;

    return (
        <div style={{
            height: isModal ? '100%' : 'auto',
            display: 'flex',
            flexDirection: 'column',
            backgroundColor: isModal ? 'transparent' : '#f8f9fa',
            padding: isModal ? '0' : '24px',
            minHeight: isModal ? 'auto' : '100vh'
        }}>
            {!isModal && (
                <div style={{
                    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                    padding: '32px',
                    borderRadius: '12px',
                    boxShadow: '0 4px 20px rgba(0,0,0,0.12)',
                    color: 'white',
                    marginBottom: '24px',
                    flexShrink: 0
                }}>
                    <div className="d-flex justify-content-between align-items-center flex-wrap">
                        <h1 style={{ fontSize: '2rem', fontWeight: '700', marginBottom: '0' }}>
                            <i className="bi bi-diagram-3 me-3"></i>
                            Allocate License Items
                        </h1>
                        <div className="btn-group" style={{ marginTop: '12px' }}>
                            <button
                                className="btn"
                                onClick={() => {
                            if (isModal && onClose) {
                                // In modal mode, close the allocation modal and navigate to edit page
                                onClose();
                            }
                            // Navigate to edit page
                            sessionStorage.setItem('allotmentListFilters', JSON.stringify({
                                returnTo: 'edit',
                                timestamp: new Date().getTime()
                            }));
                            navigate(`/allotments/${id}/edit`);
                        }}
                        title="Edit Allotment"
                        style={{
                            backgroundColor: 'rgba(255, 255, 255, 0.2)',
                            border: '1px solid rgba(255, 255, 255, 0.3)',
                            color: 'white',
                            fontWeight: '500',
                            backdropFilter: 'blur(10px)'
                        }}
                    >
                        <i className="bi bi-pencil-square me-1"></i>
                        Edit
                    </button>
                    <button
                        className="btn"
                        onClick={async () => {
                            if (!window.confirm('Are you sure you want to create a copy of this allotment?')) {
                                return;
                            }
                            try {
                                const response = await api.post(`/allotments/${id}/copy/`);
                                toast.success('Allotment copied successfully!');
                                // Navigate to edit page of the new allotment
                                navigate(`/allotments/${response.data.id}/edit`);
                            } catch (err) {
                                toast.error(err.response?.data?.error || 'Failed to copy allotment');
                            }
                        }}
                        title="Create a copy of this allotment"
                        style={{
                            backgroundColor: 'rgba(255, 255, 255, 0.2)',
                            border: '1px solid rgba(255, 255, 255, 0.3)',
                            color: 'white',
                            fontWeight: '500',
                            backdropFilter: 'blur(10px)'
                        }}
                    >
                        <i className="bi bi-files me-1"></i>
                        Copy Allotment
                    </button>
                    <button
                        className="btn"
                        onClick={async () => {
                            try {
                                const response = await api.get(`/allotment-actions/${id}/generate-pdf/`, {
                                    responseType: 'blob'
                                });
                                const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
                                const link = document.createElement('a');
                                link.href = url;
                                link.setAttribute('download', `Allotment_${allotment?.company_name || id}_${new Date().toISOString().split('T')[0]}.pdf`);
                                document.body.appendChild(link);
                                link.click();
                                link.remove();
                                window.URL.revokeObjectURL(url);
                            } catch (err) {
                                setError('Failed to download PDF');
                            }
                        }}
                        title="Download Allotment PDF"
                        style={{
                            backgroundColor: 'white',
                            border: '2px solid white',
                            color: '#667eea',
                            fontWeight: '600',
                            boxShadow: '0 2px 8px rgba(0,0,0,0.15)'
                        }}
                    >
                        <i className="bi bi-file-pdf me-1"></i>
                        Download PDF
                    </button>
                    {allotment && allotment.allotment_details && allotment.allotment_details.length > 0 && (
                        <button
                            className="btn"
                            onClick={() => {
                                // Scroll to transfer letter section
                                document.getElementById('transfer-letter-section')?.scrollIntoView({ behavior: 'smooth' });
                            }}
                            title="Generate Transfer Letter"
                            style={{
                                backgroundColor: 'rgba(255, 255, 255, 0.2)',
                                border: '1px solid rgba(255, 255, 255, 0.3)',
                                color: 'white',
                                fontWeight: '500',
                                backdropFilter: 'blur(10px)'
                            }}
                        >
                            <i className="bi bi-file-earmark-text me-1"></i>
                            Transfer Letter
                        </button>
                    )}
                    {!isModal && (
                        <button
                            className="btn"
                            onClick={() => {
                                // Store a flag to indicate we're returning to list
                                sessionStorage.setItem('allotmentListFilters', JSON.stringify({
                                    returnTo: 'list',
                                    timestamp: new Date().getTime()
                                }));
                                navigate('/allotments');
                            }}
                            style={{
                                backgroundColor: 'rgba(255, 255, 255, 0.2)',
                                border: '1px solid rgba(255, 255, 255, 0.3)',
                                color: 'white',
                                fontWeight: '500',
                                backdropFilter: 'blur(10px)'
                            }}
                        >
                            <i className="bi bi-arrow-left me-1"></i>
                            Back to Allotments
                        </button>
                    )}
                        </div>
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

                return (
                    <div className="card border-0 shadow-sm mb-4" style={{ borderRadius: '12px' }}>
                        <div className="card-body" style={{ padding: '24px' }}>
                            <h5 className="card-title mb-4" style={{ fontWeight: '600', color: '#333' }}>
                                <i className="bi bi-info-circle me-2" style={{ color: '#667eea' }}></i>
                                Allotment Details - {allotment.item_name}
                            </h5>
                            <div className="row g-3">
                                <div className="col-md-3 col-lg-2">
                                    <div className="p-3" style={{ backgroundColor: '#f8f9fa', borderRadius: '8px', borderLeft: '3px solid #17a2b8' }}>
                                        <small className="text-muted d-block mb-1" style={{ fontSize: '0.75rem', fontWeight: '500' }}>Unit Price</small>
                                        <strong style={{ fontSize: '1.1rem', color: '#17a2b8' }}>{unitPrice.toFixed(3)}</strong>
                                    </div>
                                </div>
                                <div className="col-md-3 col-lg-2">
                                    <div className="p-3" style={{ backgroundColor: '#f8f9fa', borderRadius: '8px', borderLeft: '3px solid #6c757d' }}>
                                        <small className="text-muted d-block mb-1" style={{ fontSize: '0.75rem', fontWeight: '500' }}>Required Quantity</small>
                                        <strong style={{ fontSize: '1.1rem', color: '#333' }}>{requiredQty.toLocaleString()}</strong>
                                    </div>
                                </div>
                                <div className="col-md-3 col-lg-2">
                                    <div className="p-3" style={{ backgroundColor: '#f8f9fa', borderRadius: '8px', borderLeft: '3px solid #6c757d' }}>
                                        <small className="text-muted d-block mb-1" style={{ fontSize: '0.75rem', fontWeight: '500' }}>Required Value</small>
                                        <strong style={{ fontSize: '1.1rem', color: '#333' }}>{requiredValue.toFixed(2)}</strong>
                                    </div>
                                </div>
                                <div className="col-md-3 col-lg-2">
                                    <div className="p-3" style={{ backgroundColor: '#f8f9fa', borderRadius: '8px', borderLeft: '3px solid #28a745' }}>
                                        <small className="text-muted d-block mb-1" style={{ fontSize: '0.75rem', fontWeight: '500' }}>Allotted Quantity</small>
                                        <strong style={{ fontSize: '1.1rem', color: '#28a745' }}>{allotedQty.toLocaleString()}</strong>
                                    </div>
                                </div>
                                <div className="col-md-3 col-lg-2">
                                    <div className="p-3" style={{ backgroundColor: '#f8f9fa', borderRadius: '8px', borderLeft: '3px solid #28a745' }}>
                                        <small className="text-muted d-block mb-1" style={{ fontSize: '0.75rem', fontWeight: '500' }}>Allotted Value</small>
                                        <strong style={{ fontSize: '1.1rem', color: '#28a745' }}>{allotedValue.toFixed(2)}</strong>
                                    </div>
                                </div>
                                <div className="col-md-3 col-lg-2">
                                    <div className="p-3" style={{ backgroundColor: '#f8f9fa', borderRadius: '8px', borderLeft: '3px solid #667eea' }}>
                                        <small className="text-muted d-block mb-1" style={{ fontSize: '0.75rem', fontWeight: '500' }}>Balance Quantity</small>
                                        <strong style={{ fontSize: '1.1rem', color: '#667eea' }}>{balanceQty.toLocaleString()}</strong>
                                    </div>
                                </div>
                                <div className="col-md-3 col-lg-2">
                                    <div className="p-3" style={{ backgroundColor: '#f8f9fa', borderRadius: '8px', borderLeft: '3px solid #667eea' }}>
                                        <small className="text-muted d-block mb-1" style={{ fontSize: '0.75rem', fontWeight: '500' }}>Balance Value</small>
                                        <strong style={{ fontSize: '1.1rem', color: '#667eea' }}>
                                            {balanceValue.toFixed(2)}
                                            <small className="text-muted d-block" style={{ fontSize: '0.65rem', fontWeight: '400' }}>(+$20 buffer)</small>
                                        </strong>
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
                    <div className="card-body" style={{ padding: '24px' }}>
                        <div className="d-flex justify-content-between align-items-center mb-3">
                            <h5 className="mb-0" style={{ fontWeight: '600', color: '#333' }}>
                                <i className="bi bi-check-square me-2" style={{ color: '#28a745' }}></i>
                                Allotted Items ({allotment.allotment_details.length})
                            </h5>
                            <button
                                className="btn btn-sm"
                                style={{
                                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                                    border: '1px solid rgba(102, 126, 234, 0.3)',
                                    color: '#667eea',
                                    fontWeight: '500',
                                    padding: '6px 16px',
                                    borderRadius: '6px'
                                }}
                                onClick={() => {
                                    const headers = ['License', 'Serial', 'Description', 'Exporter', 'Transfer Status', 'License Date', 'Expiry Date', 'Allotted Qty', 'Allotted Value'];
                                    const rows = allotment.allotment_details.map(detail => {
                                        const transferInfo = [detail.current_owner, detail.file_transfer_status].filter(Boolean).join(' - ') || '-';
                                        return [
                                            detail.license_number,
                                            detail.serial_number,
                                            detail.product_description,
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
                        <div style={{overflowX: 'auto', borderRadius: '8px'}}>
                            <table className="table table-sm table-hover" style={{width: '100%', marginBottom: '0'}}>
                                <thead style={{ backgroundColor: '#f8f9fa', borderBottom: '2px solid #dee2e6' }}>
                                <tr>
                                    <th style={{minWidth: '120px', whiteSpace: 'nowrap', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>License</th>
                                    <th style={{minWidth: '70px', whiteSpace: 'nowrap', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>Serial</th>
                                    <th style={{minWidth: '300px', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>Description</th>
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
                                        <td style={{whiteSpace: 'nowrap'}}>{detail.serial_number}</td>
                                        <td style={{wordWrap: 'break-word', whiteSpace: 'normal'}}>{detail.product_description}</td>
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
                                                className="btn btn-danger btn-sm"
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
                                    <th colSpan="7" className="text-end">Total:</th>
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
                            cif_fc: detail.cif_fc,
                            purchase_status: detail.purchase_status || 'N/A'
                        }))}
                        onSuccess={(msg) => setSuccess(msg)}
                        onError={(msg) => setError(msg)}
                    />
                </div>
            )}

            <div className="card border-0 shadow-sm mb-4" style={{ borderRadius: '12px' }}>
                <div className="card-body" style={{ padding: '24px' }}>
                    <div className="d-flex justify-content-between align-items-center mb-3">
                        <h5 className="mb-0" style={{ fontWeight: '600', color: '#333' }}>
                            <i className="bi bi-list-check me-2" style={{ color: '#667eea' }}></i>
                            Available License Items
                        </h5>
                    </div>

                    {/* Show success/error messages near the table for better visibility */}
                    {error && (
                        <div className="alert alert-danger alert-dismissible fade show" role="alert" style={{ borderRadius: '8px' }}>
                            <i className="bi bi-exclamation-triangle-fill me-2"></i>
                            {error}
                            <button type="button" className="btn-close" onClick={() => setError("")}></button>
                        </div>
                    )}
                    {success && (
                        <div className="alert alert-success alert-dismissible fade show" role="alert" style={{ borderRadius: '8px' }}>
                            <i className="bi bi-check-circle-fill me-2"></i>
                            {success}
                            <button type="button" className="btn-close" onClick={() => setSuccess("")}></button>
                        </div>
                    )}

                    <div className="card mb-3 border-0 shadow-sm" style={{ backgroundColor: '#f8f9fa', borderRadius: '8px' }}>
                        <div className="card-body" style={{ padding: '20px' }}>
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
                                        fieldMeta={{endpoint: "/masters/sion-classes/", label_field: "norm_class"}}
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
                                        fieldMeta={{endpoint: "/masters/companies/", label_field: "name"}}
                                        value={filters.exporter}
                                        onChange={(value) => setFilters({...filters, exporter: value})}
                                        placeholder="All Exporters"
                                        isClearable={true}
                                    />
                                </div>
                                <div className="col-md-3">
                                    <label className="form-label">Exclude Exporter</label>
                                    <HybridSelect
                                        fieldMeta={{endpoint: "/masters/companies/", label_field: "name"}}
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
                                        <label className="form-label">Is Expired</label>
                                        <select
                                            className="form-control form-control-sm"
                                            value={filters.is_expired}
                                            onChange={(e) => setFilters({...filters, is_expired: e.target.value})}
                                        >
                                            <option value="">All</option>
                                            <option value="false">Not Expired</option>
                                            <option value="true">Expired</option>
                                        </select>
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
                                    <div className="col-md-12 mt-2">
                                        <button
                                            className="btn btn-sm"
                                            style={{
                                                backgroundColor: '#6c757d',
                                                border: 'none',
                                                color: 'white',
                                                fontWeight: '500',
                                                padding: '8px 20px',
                                                borderRadius: '6px'
                                            }}
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
                                                is_expired: "false",
                                                is_restricted: "all",
                                                purchase_status: "GE,GO,SM,MI",
                                                license_status: "active",
                                                item_names: ""
                                            })}
                                        >
                                            <i className="bi bi-x-circle me-1"></i>
                                            Clear Filters
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>

                    <div className="table-responsive" style={{ borderRadius: '8px', overflow: 'hidden' }}>
                        <table className="table table-sm table-hover" style={{fontSize: '0.875rem', marginBottom: '0'}}>
                            <thead className="sticky-top" style={{backgroundColor: '#f8f9fa', borderBottom: '2px solid #dee2e6', zIndex: 10}}>
                            <tr>
                                <th style={{minWidth: '100px', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>License</th>
                                <th style={{minWidth: '50px', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>Serial</th>
                                <th style={{minWidth: '90px', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>HS Code</th>
                                <th style={{minWidth: '200px', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>Description</th>
                                <th style={{minWidth: '150px', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>Exporter</th>
                                <th style={{minWidth: '90px', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>Notification</th>
                                <th style={{minWidth: '150px', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>Item Name</th>
                                <th style={{minWidth: '80px', textAlign: 'center', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>Is Restricted</th>
                                <th style={{minWidth: '100px', textAlign: 'right', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>Avail Qty</th>
                                <th style={{minWidth: '110px', textAlign: 'right', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>Avail CIF FC</th>
                                <th style={{minWidth: '80px', textAlign: 'right', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>Average</th>
                                <th style={{minWidth: '90px', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>Expiry</th>
                                <th style={{minWidth: '150px', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>Notes</th>
                                <th style={{minWidth: '150px', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>Allocate Qty</th>
                                <th style={{minWidth: '150px', fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>Allocate Value</th>
                                <th style={{minWidth: '130px', position: 'sticky', right: 0, backgroundColor: '#f8f9fa', zIndex: 5, fontWeight: '600', fontSize: '0.85rem', padding: '12px 8px'}}>Action</th>
                            </tr>
                            </thead>
                            <tbody>
                            {availableItems.map((item) => {
                                const maxAllocation = calculateMaxAllocation(item);
                                const currentAllocation = allocationData[item.id];

                                return (
                                    <tr key={item.id}>
                                        <td style={{fontSize: '0.8rem'}}>{item.license_number}</td>
                                        <td style={{fontSize: '0.8rem', textAlign: 'center'}}>{item.serial_number}</td>
                                        <td style={{fontSize: '0.8rem'}}>{item.hs_code_label || '-'}</td>
                                        <td style={{fontSize: '0.8rem', maxWidth: '250px', whiteSpace: 'normal'}}>{item.description}</td>
                                        <td style={{fontSize: '0.8rem'}}>{item.exporter_name}</td>
                                        <td style={{fontSize: '0.8rem', textAlign: 'center'}}>{item.notification_number || '-'}</td>
                                        <td style={{fontSize: '0.8rem'}}>
                                            {item.items_detail && item.items_detail.length > 0
                                                ? item.items_detail.map(i => i.name).join(', ')
                                                : '-'
                                            }
                                        </td>
                                        <td style={{fontSize: '0.8rem', textAlign: 'center'}}>
                                            {item.is_restricted ? (
                                                <span className="badge bg-warning text-dark">Yes</span>
                                            ) : (
                                                <span className="badge bg-success">No</span>
                                            )}
                                        </td>
                                        <td style={{fontSize: '0.8rem', textAlign: 'right', fontWeight: '500'}}>{parseFloat(item.available_quantity || 0).toFixed(3)}</td>
                                        <td style={{fontSize: '0.8rem', textAlign: 'right', fontWeight: '500'}}>{parseFloat(item.balance_cif_fc || 0).toFixed(2)}</td>
                                        <td style={{fontSize: '0.8rem', textAlign: 'right', color: 'var(--text-secondary)'}}>
                                            {(() => {
                                                const qty = parseFloat(item.available_quantity || 0);
                                                const value = parseFloat(item.balance_cif_fc || 0);
                                                const average = qty > 0 ? (value / qty) : 0;
                                                return average.toFixed(2);
                                            })()}
                                        </td>
                                        <td style={{fontSize: '0.8rem'}}>{item.license_expiry_date}</td>
                                        <td style={{fontSize: '0.8rem', maxWidth: '200px', whiteSpace: 'normal'}}>{item.notes || '-'}</td>
                                        <td>
                                            <div className="input-group input-group-sm" style={{minWidth: '140px'}}>
                                                <input
                                                    type="number"
                                                    className="form-control form-control-sm"
                                                    value={currentAllocation?.qty || ""}
                                                    onChange={(e) => handleQuantityChange(item.id, e.target.value)}
                                                    placeholder="Qty"
                                                    step="1"
                                                    min="0"
                                                    max={maxAllocation.qty}
                                                    title={`Max allowed: ${maxAllocation.qty} (with $20 buffer)`}
                                                    style={{fontSize: '0.8rem'}}
                                                />
                                                <button
                                                    className="btn btn-outline-secondary btn-sm"
                                                    type="button"
                                                    onClick={() => handleMaxQuantity(item)}
                                                    title={`Max: ${maxAllocation.qty} (includes $20 buffer)`}
                                                    style={{fontSize: '0.75rem', padding: '0.25rem 0.5rem'}}
                                                >
                                                    Max
                                                </button>
                                            </div>
                                        </td>
                                        <td>
                                            <div className="input-group input-group-sm" style={{minWidth: '140px'}}>
                                                <input
                                                    type="number"
                                                    className="form-control form-control-sm"
                                                    value={currentAllocation?.cif_fc || ""}
                                                    onChange={(e) => handleValueChange(item.id, e.target.value)}
                                                    placeholder="Value"
                                                    step="0.01"
                                                    min="0"
                                                    title={`Max allowed: ${maxAllocation.value.toFixed(2)} (with $20 buffer)`}
                                                    style={{fontSize: '0.8rem'}}
                                                />
                                                <button
                                                    className="btn btn-outline-secondary btn-sm"
                                                    type="button"
                                                    onClick={() => handleMaxValue(item)}
                                                    title={`Max: ${maxAllocation.value.toFixed(2)} (includes $20 buffer)`}
                                                    style={{fontSize: '0.75rem', padding: '0.25rem 0.5rem'}}
                                                >
                                                    Max
                                                </button>
                                            </div>
                                        </td>
                                        <td style={{position: 'sticky', right: 0, backgroundColor: 'white', zIndex: 4}}>
                                            <button
                                                className="btn btn-sm w-100"
                                                style={{
                                                    background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                                    border: 'none',
                                                    color: 'white',
                                                    fontWeight: '500',
                                                    fontSize: '0.8rem',
                                                    whiteSpace: 'nowrap',
                                                    padding: '6px 12px',
                                                    borderRadius: '6px',
                                                    opacity: (!currentAllocation || parseFloat(currentAllocation.qty) <= 0 || saving[item.id]) ? 0.6 : 1
                                                }}
                                                onClick={() => handleConfirmAllot(item)}
                                                disabled={!currentAllocation || parseFloat(currentAllocation.qty) <= 0 || saving[item.id]}
                                            >
                                                {saving[item.id] ? (
                                                    <>
                                                        <span className="spinner-border spinner-border-sm me-1" role="status"></span>
                                                        Saving...
                                                    </>
                                                ) : (
                                                    <>
                                                        <i className="bi bi-check-circle me-1"></i>
                                                        Confirm
                                                    </>
                                                )}
                                            </button>
                                        </td>
                                    </tr>
                                );
                            })}
                            </tbody>
                        </table>
                    </div>

                    {tableLoading && (
                        <div className="text-center p-3">
                            <div className="spinner-border spinner-border-sm text-primary" role="status">
                                <span className="visually-hidden">Loading...</span>
                            </div>
                            <span className="ms-2">Loading items...</span>
                        </div>
                    )}

                    {!tableLoading && availableItems.length === 0 && (
                        <div className="text-center text-muted p-4">
                            No available license items found
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
                                                            background: pagination.currentPage === pageNum ? 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)' : 'white',
                                                            border: pagination.currentPage === pageNum ? 'none' : '1px solid #dee2e6',
                                                            color: pagination.currentPage === pageNum ? 'white' : '#667eea',
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
