import {useEffect, useState} from "react";
import {useParams, useNavigate, useLocation} from "react-router-dom";
import api from "../api/axios";
import HybridSelect from "../components/HybridSelect";
import CreatableSelect from 'react-select/creatable';

export default function AllotmentAction() {
    const {id} = useParams();
    const navigate = useNavigate();
    const location = useLocation();

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
        available_quantity_gte: "50",
        available_quantity_lte: "",
        available_value_gte: "100",
        available_value_lte: "",
        notification_number: "",
        norm_class: "",
        hs_code: "",
        is_expired: "false"
    });
    const [isFirstLoad, setIsFirstLoad] = useState(true);
    const [notificationOptions, setNotificationOptions] = useState([]);
    const [pagination, setPagination] = useState({
        currentPage: 1,
        pageSize: 20,
        totalItems: 0,
        totalPages: 0
    });
    const [error, setError] = useState("");
    const [success, setSuccess] = useState("");
    const [deletingItems, setDeletingItems] = useState({});
    const [transferLetterData, setTransferLetterData] = useState({
        company: null,
        addressLine1: "",
        addressLine2: "",
        template: "",
        cifEdits: {}
    });
    const [companyOptions, setCompanyOptions] = useState([]);
    const [transferLetters, setTransferLetters] = useState([]);
    const [generatingTL, setGeneratingTL] = useState(false);

    useEffect(() => {
        fetchNotificationOptions();
        fetchTransferLetters();
    }, []);

    // Set description from allotment item_name on first load
    useEffect(() => {
        if (isFirstLoad && allotment?.item_name) {
            setFilters(prev => ({...prev, description: allotment.item_name}));
            setIsFirstLoad(false);
        }
    }, [allotment, isFirstLoad]);

    useEffect(() => {
        const timer = setTimeout(() => {
            setPagination(prev => ({...prev, currentPage: 1})); // Reset to page 1 on filter change
            fetchData(1);
        }, 300); // Debounce for 300ms
        return () => clearTimeout(timer);
    }, [id, search, filters]);

    useEffect(() => {
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
            console.error("Failed to load notification options:", err);
        }
    };

    const fetchTransferLetters = async () => {
        try {
            const {data} = await api.get('/masters/transfer-letters/');
            setTransferLetters(data.results || data || []);
        } catch (err) {
            console.error("Failed to load transfer letters:", err);
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
        const balancedQty = parseInt(allotment.balanced_quantity || 0);
        const requiredValue = parseFloat(allotment.required_value || 0);
        const requiredValueWithBuffer = parseFloat(allotment.required_value_with_buffer || (requiredValue + 20));
        const allottedValue = parseFloat(allotment.allotted_value || 0);
        const balancedValueWithBuffer = requiredValueWithBuffer - allottedValue;
        const availableQty = parseInt(item.available_quantity);
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
        const balancedQty = parseInt(allotment.balanced_quantity || 0);
        const requiredValue = parseFloat(allotment.required_value || 0);
        const requiredValueWithBuffer = parseFloat(allotment.required_value_with_buffer || (requiredValue + 20));
        const allottedValue = parseFloat(allotment.allotted_value || 0);
        const balancedValueWithBuffer = requiredValueWithBuffer - allottedValue;
        const availableCifFc = parseFloat(item.balance_cif_fc || 0);
        const availableQty = parseInt(item.available_quantity || 0);

        // Constrain to minimum of balanced quantity and available quantity
        if (inputQty > balancedQty) {
            inputQty = balancedQty;
        }
        if (inputQty > availableQty) {
            inputQty = availableQty;
        }

        // Calculate value from quantity
        let allocateCifFc = inputQty * unitPrice;

        // Log all values for debugging
        console.log('Allocation calculation:', {
            inputQty,
            unitPrice,
            calculatedValue: allocateCifFc,
            balancedQty,
            requiredValue,
            requiredValueWithBuffer,
            allottedValue,
            balancedValueWithBuffer,
            valueDifference: balancedValueWithBuffer - allocateCifFc,
            willAdjustForValue: allocateCifFc > balancedValueWithBuffer
        });

        // If calculated value exceeds balanced value with buffer, adjust quantity down
        if (allocateCifFc > balancedValueWithBuffer) {
            console.log('⚠️ Value exceeds buffer - adjusting quantity down');
            inputQty = Math.floor(balancedValueWithBuffer / unitPrice);
            allocateCifFc = inputQty * unitPrice;
            console.log('Adjusted to:', { inputQty, allocateCifFc });
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
                setError(`Error: ${data.errors[0].error}`);
            } else {
                setSuccess(`Successfully allocated ${allocation.qty} from ${item.license_number}`);
                // Clear this item's allocation
                const newAllocationData = {...allocationData};
                delete newAllocationData[item.id];
                setAllocationData(newAllocationData);
                // Refresh data immediately to update available quantities and allotted items
                fetchData(pagination.currentPage);
            }
        } catch (err) {
            setError(err.response?.data?.error || "Failed to allocate item");
        } finally {
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
            setSuccess(data.message || "Successfully removed allocation");
            // Refresh data immediately to update available quantities and allotted items
            fetchData(pagination.currentPage);
        } catch (err) {
            setError(err.response?.data?.error || "Failed to delete allocation");
        } finally {
            setDeletingItems({...deletingItems, [allotmentItemId]: false});
        }
    };

    const handleGenerateTransferLetter = async () => {
        if (!transferLetterData.template) {
            setError("Please select a transfer letter template");
            return;
        }

        // Get company name from company object
        const finalCompanyName = transferLetterData.company?.label || '';

        if (!finalCompanyName.trim()) {
            setError("Please select or enter a company name");
            return;
        }

        setGeneratingTL(true);
        setError("");
        setSuccess("");

        // Debug current state
        console.log('transferLetterData state:', transferLetterData);

        // Prepare request data
        const requestData = {
            company_name: finalCompanyName.trim(),
            address_line1: transferLetterData.addressLine1.trim(),
            address_line2: transferLetterData.addressLine2.trim(),
            template_id: transferLetterData.template,
            cif_edits: transferLetterData.cifEdits || {}
        };

        // Debug logging
        console.log('Transfer Letter Request Data:', requestData);
        console.log('Company object:', transferLetterData.company);
        console.log('Final company name used:', finalCompanyName);

        try {
            const response = await api.post(`/allotment-actions/${id}/generate-transfer-letter/`, requestData, {
                responseType: 'blob'
            });

            const url = window.URL.createObjectURL(new Blob([response.data]));
            const link = document.createElement('a');
            link.href = url;
            link.setAttribute('download', `TransferLetter_${transferLetterData.company?.label || id}.zip`);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
            setSuccess("Transfer letter generated successfully");
        } catch (err) {
            setError(err.response?.data?.error || "Failed to generate transfer letter");
        } finally {
            setGeneratingTL(false);
        }
    };

    const handleCifEdit = (detailId, value) => {
        setTransferLetterData(prev => ({
            ...prev,
            cifEdits: {
                ...prev.cifEdits,
                [detailId]: value
            }
        }));
    };

    const loadCompanyOptions = async (inputValue) => {
        try {
            const {data} = await api.get(`/masters/companies/?search=${inputValue}`);
            const results = data.results || data || [];
            return results.map(company => ({
                value: company.id,
                label: company.name,
                ...company
            }));
        } catch (err) {
            console.error("Failed to load companies:", err);
            return [];
        }
    };

    const handleCompanyChange = async (selectedCompany, actionMeta) => {
        console.log('Company changed:', selectedCompany, 'Action:', actionMeta);

        // Set the company
        setTransferLetterData(prev => ({
            ...prev,
            company: selectedCompany
        }));

        // Fetch and populate address if company is selected from existing options (not created)
        if (selectedCompany && selectedCompany.value && actionMeta.action !== 'create-option') {
            try {
                const {data} = await api.get(`/masters/companies/${selectedCompany.value}/`);
                console.log('Company details fetched:', data);

                setTransferLetterData(prev => ({
                    ...prev,
                    company: selectedCompany,
                    addressLine1: data.address_line_1 || "",
                    addressLine2: data.address_line_2 || ""
                }));
            } catch (err) {
                console.error("Failed to fetch company details:", err);
            }
        } else if (!selectedCompany) {
            // Clear everything when company is cleared
            setTransferLetterData(prev => ({
                ...prev,
                company: null,
                addressLine1: "",
                addressLine2: ""
            }));
        }
    };

    if (initialLoading) return <div className="p-4">Loading...</div>;

    return (
        <div className="container-fluid p-4">
            <div className="d-flex justify-content-between align-items-center mb-4">
                <h2>Allocate License Items</h2>
                <div className="d-flex gap-2">
                    <button
                        className="btn btn-info"
                        onClick={() => {
                            // Store current filters before navigating to edit
                            sessionStorage.setItem('allotmentListFilters', JSON.stringify({
                                returnTo: 'edit',
                                timestamp: new Date().getTime()
                            }));
                            navigate(`/allotments/${id}/edit`);
                        }}
                        title="Edit Allotment"
                    >
                        <i className="bi bi-pencil-square me-1"></i>
                        Edit
                    </button>
                    <button
                        className="btn btn-success"
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
                    >
                        <i className="bi bi-file-pdf me-1"></i>
                        Download PDF
                    </button>
                    {allotment && allotment.allotment_details && allotment.allotment_details.length > 0 && (
                        <button
                            className="btn btn-warning"
                            onClick={() => {
                                // Scroll to transfer letter section
                                document.getElementById('transfer-letter-section')?.scrollIntoView({ behavior: 'smooth' });
                            }}
                            title="Generate Transfer Letter"
                        >
                            <i className="bi bi-file-earmark-text me-1"></i>
                            Transfer Letter
                        </button>
                    )}
                    <button
                        className="btn btn-secondary"
                        onClick={() => {
                            // Store a flag to indicate we're returning to list
                            sessionStorage.setItem('allotmentListFilters', JSON.stringify({
                                returnTo: 'list',
                                timestamp: new Date().getTime()
                            }));
                            navigate('/allotments');
                        }}
                    >
                        Back to Allotments
                    </button>
                </div>
            </div>

            {error && <div className="alert alert-danger">{error}</div>}
            {success && <div className="alert alert-success">{success}</div>}

            {allotment && (() => {
                const unitPrice = parseFloat(allotment.unit_value_per_unit || 0);
                const requiredQty = parseInt(allotment.required_quantity || 0);
                const requiredValue = parseFloat(allotment.required_value || 0);
                const allotedQty = parseInt(allotment.alloted_quantity || 0);
                const allotedValue = parseFloat(allotment.allotted_value || 0);
                const balanceQty = requiredQty - allotedQty;
                const balanceValue = requiredValue - allotedValue;

                return (
                    <div className="card mb-4">
                        <div className="card-body">
                            <h5 className="card-title mb-3">Allotment Details - {allotment.item_name}</h5>
                            <div className="row">
                                <div className="col-md-2">
                                    <div className="mb-2">
                                        <small className="text-muted d-block">Unit Price</small>
                                        <strong className="text-info">{unitPrice.toFixed(3)}</strong>
                                    </div>
                                </div>
                                <div className="col-md-2">
                                    <div className="mb-2">
                                        <small className="text-muted d-block">Required Quantity</small>
                                        <strong>{requiredQty.toLocaleString()}</strong>
                                    </div>
                                </div>
                                <div className="col-md-2">
                                    <div className="mb-2">
                                        <small className="text-muted d-block">Required Value</small>
                                        <strong>{requiredValue.toFixed(2)}</strong>
                                    </div>
                                </div>
                                <div className="col-md-2">
                                    <div className="mb-2">
                                        <small className="text-muted d-block">Allotted Quantity</small>
                                        <strong className="text-success">{allotedQty.toLocaleString()}</strong>
                                    </div>
                                </div>
                                <div className="col-md-2">
                                    <div className="mb-2">
                                        <small className="text-muted d-block">Allotted Value</small>
                                        <strong className="text-success">{allotedValue.toFixed(2)}</strong>
                                    </div>
                                </div>
                                <div className="col-md-2">
                                    <div className="mb-2">
                                        <small className="text-muted d-block">Balance Quantity</small>
                                        <strong className="text-primary">{balanceQty.toLocaleString()}</strong>
                                    </div>
                                </div>
                                <div className="col-md-2">
                                    <div className="mb-2">
                                        <small className="text-muted d-block">Balance Value</small>
                                        <strong className="text-primary">{balanceValue.toFixed(2)} <small className="text-muted">(+$20 buffer)</small></strong>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                );
            })()}

            {/* Allotted Items Table */}
            {allotment && allotment.allotment_details && allotment.allotment_details.length > 0 && (
                <div className="card mb-4">
                    <div className="card-body">
                        <h5 className="mb-3">Allotted Items ({allotment.allotment_details.length})</h5>
                        <div className="table-responsive">
                            <table className="table table-sm table-bordered">
                                <thead className="table-light">
                                <tr>
                                    <th>License</th>
                                    <th>Serial</th>
                                    <th>Description</th>
                                    <th>Exporter</th>
                                    <th>License Date</th>
                                    <th>Expiry Date</th>
                                    <th>Allotted Qty</th>
                                    <th>Allotted Value (CIF FC)</th>
                                    <th style={{width: "80px"}}>Action</th>
                                </tr>
                                </thead>
                                <tbody>
                                {allotment.allotment_details.map((detail) => (
                                    <tr key={detail.id}>
                                        <td>{detail.license_number}</td>
                                        <td>{detail.serial_number}</td>
                                        <td>{detail.product_description}</td>
                                        <td>{detail.exporter}</td>
                                        <td>{detail.license_date}</td>
                                        <td>{detail.license_expiry}</td>
                                        <td className="text-end">{parseInt(detail.qty || 0).toLocaleString()}</td>
                                        <td className="text-end">{parseFloat(detail.cif_fc || 0).toFixed(2)}</td>
                                        <td className="text-center">
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
                                    <th colSpan="6" className="text-end">Total:</th>
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
                <div className="card mb-4" id="transfer-letter-section">
                    <div className="card-body">
                        <h5 className="mb-3">Generate Transfer Letter</h5>
                        <div className="row mb-3">
                            <div className="col-md-4">
                                <label className="form-label">Company <span className="text-danger">*</span></label>
                                <CreatableSelect
                                    value={transferLetterData.company}
                                    onChange={handleCompanyChange}
                                    onInputChange={(inputValue) => {
                                        if (inputValue.length >= 2) {
                                            loadCompanyOptions(inputValue).then(options => setCompanyOptions(options));
                                        }
                                    }}
                                    options={companyOptions}
                                    placeholder="Type to search or enter company name..."
                                    isClearable={true}
                                    formatCreateLabel={(inputValue) => `Use: "${inputValue}"`}
                                />
                                <small className="text-muted">Select from dropdown to auto-fill addresses, or type to create custom entry</small>
                            </div>
                            <div className="col-md-4">
                                <label className="form-label">Address Line 1</label>
                                <input
                                    type="text"
                                    className="form-control"
                                    value={transferLetterData.addressLine1}
                                    onChange={(e) => setTransferLetterData(prev => ({...prev, addressLine1: e.target.value}))}
                                    placeholder="Enter address line 1"
                                />
                            </div>
                            <div className="col-md-4">
                                <label className="form-label">Address Line 2</label>
                                <input
                                    type="text"
                                    className="form-control"
                                    value={transferLetterData.addressLine2}
                                    onChange={(e) => setTransferLetterData(prev => ({...prev, addressLine2: e.target.value}))}
                                    placeholder="Enter address line 2"
                                />
                            </div>
                        </div>
                        <div className="row mb-3">
                            <div className="col-md-6">
                                <label className="form-label">Template</label>
                                <select
                                    className="form-select"
                                    value={transferLetterData.template}
                                    onChange={(e) => setTransferLetterData(prev => ({...prev, template: e.target.value}))}
                                >
                                    <option value="">— Select Transfer Letter Template —</option>
                                    {transferLetters.map((tl) => (
                                        <option key={tl.id} value={tl.id}>{tl.name}</option>
                                    ))}
                                </select>
                            </div>
                        </div>

                        {/* Edit CIF (FC) per SR */}
                        <div className="mb-3">
                            <h6>Edit CIF (FC) per SR</h6>
                            <div className="table-responsive">
                                <table className="table table-sm table-bordered">
                                    <thead className="table-light">
                                    <tr>
                                        <th>#</th>
                                        <th>SR Number</th>
                                        <th>CIF FC (editable)</th>
                                    </tr>
                                    </thead>
                                    <tbody>
                                    {allotment.allotment_details.length === 0 ? (
                                        <tr>
                                            <td colSpan="3" className="text-center text-muted">No items to include.</td>
                                        </tr>
                                    ) : (
                                        allotment.allotment_details.map((detail, idx) => (
                                            <tr key={detail.id}>
                                                <td>{idx + 1}</td>
                                                <td>{detail.serial_number}</td>
                                                <td>
                                                    <input
                                                        type="number"
                                                        className="form-control form-control-sm"
                                                        value={transferLetterData.cifEdits[detail.id] !== undefined ? transferLetterData.cifEdits[detail.id] : parseFloat(detail.cif_fc || 0).toFixed(2)}
                                                        onChange={(e) => handleCifEdit(detail.id, e.target.value)}
                                                        step="0.01"
                                                    />
                                                </td>
                                            </tr>
                                        ))
                                    )}
                                    </tbody>
                                </table>
                            </div>
                        </div>

                        <div className="d-flex justify-content-end">
                            <button
                                className="btn btn-warning"
                                onClick={handleGenerateTransferLetter}
                                disabled={generatingTL || !transferLetterData.template}
                            >
                                {generatingTL ? (
                                    <>
                                        <span className="spinner-border spinner-border-sm me-2" role="status"></span>
                                        Generating...
                                    </>
                                ) : (
                                    <>
                                        <i className="bi bi-file-earmark-text me-2"></i>
                                        Generate Transfer Letter
                                    </>
                                )}
                            </button>
                        </div>
                    </div>
                </div>
            )}

            <div className="card mb-4">
                <div className="card-body">
                    <div className="d-flex justify-content-between align-items-center mb-3">
                        <h5 className="mb-0">Available License Items</h5>
                        <input
                            type="text"
                            className="form-control"
                            placeholder="Search licenses..."
                            value={search}
                            onChange={(e) => setSearch(e.target.value)}
                            style={{width: "300px"}}
                        />
                    </div>

                    <div className="card mb-3 bg-light">
                        <div className="card-body">
                            <div className="row g-3">
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
                                    <div className="col-md-12">
                                        <button
                                            className="btn btn-sm btn-secondary"
                                            onClick={() => setFilters({
                                                description: "",
                                                exporter: "",
                                                available_quantity_gte: "",
                                                available_quantity_lte: "",
                                                available_value_gte: "",
                                                available_value_lte: "",
                                                notification_number: "",
                                                norm_class: "",
                                                hs_code: "",
                                                is_expired: ""
                                            })}
                                        >
                                            Clear Filters
                                        </button>
                                    </div>
                                </div>
                            </div>
                        </div>

                    <div className="table-responsive">
                        <table className="table table-striped table-hover">
                            <thead>
                            <tr>
                                <th>License</th>
                                <th>Serial</th>
                                <th>HS Code</th>
                                <th>Description</th>
                                <th>Exporter</th>
                                <th>Notification</th>
                                <th>Available Qty</th>
                                <th>Available CIF FC</th>
                                <th>Expiry</th>
                                <th style={{width: "180px"}}>Allocate Qty</th>
                                <th style={{width: "180px"}}>Allocate Value</th>
                                <th style={{width: "150px"}}>Action</th>
                            </tr>
                            </thead>
                            <tbody>
                            {availableItems.map((item) => {
                                const maxAllocation = calculateMaxAllocation(item);
                                const currentAllocation = allocationData[item.id];

                                return (
                                    <tr key={item.id}>
                                        <td>{item.license_number}</td>
                                        <td>{item.serial_number}</td>
                                        <td>{item.hs_code_label || '-'}</td>
                                        <td>{item.description}</td>
                                        <td>{item.exporter_name}</td>
                                        <td>{item.notification_number || '-'}</td>
                                        <td>{parseFloat(item.available_quantity || 0).toFixed(3)}</td>
                                        <td>{parseFloat(item.balance_cif_fc || 0).toFixed(2)}</td>
                                        <td>{item.license_expiry_date}</td>
                                        <td>
                                            <div className="input-group input-group-sm">
                                                <input
                                                    type="number"
                                                    className="form-control"
                                                    value={currentAllocation?.qty || ""}
                                                    onChange={(e) => handleQuantityChange(item.id, e.target.value)}
                                                    placeholder="Quantity"
                                                    step="1"
                                                    min="0"
                                                    title={`Max allowed: ${maxAllocation.qty} (with $20 buffer)`}
                                                />
                                                <button
                                                    className="btn btn-outline-secondary"
                                                    type="button"
                                                    onClick={() => handleMaxQuantity(item)}
                                                    title={`Max: ${maxAllocation.qty} (includes $20 buffer)`}
                                                >
                                                    Max
                                                </button>
                                            </div>
                                        </td>
                                        <td>
                                            <div className="input-group input-group-sm">
                                                <input
                                                    type="number"
                                                    className="form-control"
                                                    value={currentAllocation?.cif_fc || ""}
                                                    onChange={(e) => handleValueChange(item.id, e.target.value)}
                                                    placeholder="Value"
                                                    step="0.01"
                                                    min="0"
                                                    title={`Max allowed: ${maxAllocation.value.toFixed(2)} (with $20 buffer)`}
                                                />
                                                <button
                                                    className="btn btn-outline-secondary"
                                                    type="button"
                                                    onClick={() => handleMaxValue(item)}
                                                    title={`Max: ${maxAllocation.value.toFixed(2)} (includes $20 buffer)`}
                                                >
                                                    Max
                                                </button>
                                            </div>
                                        </td>
                                        <td>
                                            <button
                                                className="btn btn-primary btn-sm"
                                                onClick={() => handleConfirmAllot(item)}
                                                disabled={!currentAllocation || parseFloat(currentAllocation.qty) <= 0 || saving[item.id]}
                                            >
                                                {saving[item.id] ? (
                                                    <>
                                                        <span className="spinner-border spinner-border-sm me-1" role="status"></span>
                                                        Allotting...
                                                    </>
                                                ) : (
                                                    "Confirm Allot"
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
                        <div className="d-flex justify-content-between align-items-center mt-3">
                            <div className="text-muted">
                                Showing {((pagination.currentPage - 1) * pagination.pageSize) + 1} to {Math.min(pagination.currentPage * pagination.pageSize, pagination.totalItems)} of {pagination.totalItems} items
                            </div>
                            <nav>
                                <ul className="pagination mb-0">
                                    <li className={`page-item ${pagination.currentPage === 1 ? 'disabled' : ''}`}>
                                        <button
                                            className="page-link"
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
        </div>
    );
}
