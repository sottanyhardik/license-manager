import { useState, useEffect, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import api from "../api/axios";
import HybridSelect from "../components/HybridSelect";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";

export default function TradeForm() {
    const { id } = useParams();
    const navigate = useNavigate();
    const isEdit = Boolean(id);

    const [formData, setFormData] = useState({
        direction: "PURCHASE",
        from_company: null,
        to_company: null,
        boe: null,
        invoice_number: "",
        invoice_date: new Date(),
        remarks: "",
        purchase_invoice_copy: null,
        lines: [],
        payments: []
    });

    const [billingMode, setBillingMode] = useState("CIF_INR");
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");
    const [fieldErrors, setFieldErrors] = useState({});

    // Helper function to format Date object to YYYY-MM-DD for API
    const formatDateForAPI = (date) => {
        if (!date) return null;
        if (!(date instanceof Date)) return date;
        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    };

    // Define handlePrefillFromBOE before useEffect
    const handlePrefillFromBOE = useCallback(async () => {
        if (!formData.boe) {
            return;
        }
        try {
            // boe can be either ID or object with id
            const boeId = typeof formData.boe === 'object' ? formData.boe.id : formData.boe;
            const { data } = await api.get(`/bill-of-entries/${boeId}/`);

            // Create lines from BOE item_details
            const lines = data.item_details?.map(item => ({
                sr_number: item.sr_number || null,
                description: item.item_description || "",
                hsn_code: item.hs_code || "49070000",
                mode: billingMode,
                qty_kg: parseFloat(item.qty) || 0,
                rate_inr_per_kg: 0,
                cif_fc: parseFloat(item.cif_fc) || 0,
                exc_rate: parseFloat(data.exchange_rate) || 0,
                cif_inr: parseFloat(item.cif_inr) || 0,
                fob_inr: 0, // BOE doesn't have FOB, calculate if needed
                pct: billingMode === "CIF_INR" ? 7.9 : billingMode === "FOB_INR" ? 7.9 : 0,
                amount_inr: 0
            })) || [];

            setFormData(prev => ({
                ...prev,
                lines: lines
            }));
        } catch (err) {
            console.error("BOE fetch error:", err);
            alert("Failed to fetch BOE details");
        }
    }, [formData.boe, billingMode]);

    // Fetch existing trade if editing
    useEffect(() => {
        if (isEdit) {
            fetchTrade();
        }
    }, [isEdit, id]);

    // Auto-prefill from BOE when BOE is selected
    useEffect(() => {
        if (formData.boe && !isEdit) {
            // Only auto-prefill in create mode, not edit mode
            handlePrefillFromBOE();
        }
    }, [formData.boe, isEdit, handlePrefillFromBOE]);

    const fetchTrade = async () => {
        try {
            const { data } = await api.get(`/trades/${id}/`);

            // Parse date fields
            if (data.invoice_date) {
                const parts = data.invoice_date.split('-');
                data.invoice_date = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]), 12, 0, 0);
            }

            // Parse payment dates
            if (data.payments) {
                data.payments = data.payments.map(payment => ({
                    ...payment,
                    date: payment.date ? new Date(payment.date + 'T12:00:00') : new Date()
                }));
            }

            setFormData(data);

            // Set billing mode from first line if exists
            if (data.lines && data.lines.length > 0) {
                setBillingMode(data.lines[0].mode);
            }
        } catch (err) {
            setError("Failed to load trade");
        }
    };

    const handlePrefillFromCompany = async () => {
        if (!formData.from_company) {
            alert("Please select From Company first");
            return;
        }
        try {
            // from_company can be either ID or object with id
            const companyId = typeof formData.from_company === 'object' ? formData.from_company.id : formData.from_company;
            const { data } = await api.get(`/masters/companies/${companyId}/`);
            setFormData(prev => ({
                ...prev,
                from_pan: data.pan || "",
                from_gst: data.gst_number || "",
                from_addr_line_1: data.address_line_1 || "",
                from_addr_line_2: data.address_line_2 || ""
            }));
        } catch (err) {
            alert("Failed to fetch company details");
        }
    };

    const handlePrefillToCompany = async () => {
        if (!formData.to_company) {
            alert("Please select To Company first");
            return;
        }
        try {
            // to_company can be either ID or object with id
            const companyId = typeof formData.to_company === 'object' ? formData.to_company.id : formData.to_company;
            const { data } = await api.get(`/masters/companies/${companyId}/`);
            setFormData(prev => ({
                ...prev,
                to_pan: data.pan || "",
                to_gst: data.gst_number || "",
                to_addr_line_1: data.address_line_1 || "",
                to_addr_line_2: data.address_line_2 || ""
            }));
        } catch (err) {
            alert("Failed to fetch company details");
        }
    };

    const handlePrefillInvoiceNumber = async () => {
        if (!formData.from_company) {
            alert("Please select From Company first");
            return;
        }
        try {
            // from_company can be either ID or object with id
            const companyId = typeof formData.from_company === 'object' ? formData.from_company.id : formData.from_company;
            const { data } = await api.get(`/trades/generate_invoice_number/`, {
                params: {
                    seller_company_id: companyId,
                    invoice_date: formatDateForAPI(formData.invoice_date)
                }
            });
            setFormData(prev => ({
                ...prev,
                invoice_number: data.invoice_number || ""
            }));
        } catch (err) {
            alert("Failed to generate invoice number");
        }
    };


    const handleAddLine = () => {
        setFormData(prev => ({
            ...prev,
            lines: [...prev.lines, {
                sr_number: null,
                description: "",
                hsn_code: "49070000",
                mode: billingMode,
                qty_kg: 0,
                rate_inr_per_kg: 0,
                cif_fc: 0,
                exc_rate: 0,
                cif_inr: 0,
                fob_inr: 0,
                pct: billingMode === "CIF_INR" ? 7.9 : billingMode === "FOB_INR" ? 7.9 : 0,
                amount_inr: 0
            }]
        }));
    };

    const handleRemoveLine = (index) => {
        setFormData(prev => ({
            ...prev,
            lines: prev.lines.filter((_, i) => i !== index)
        }));
    };

    const handleLineChange = (index, field, value) => {
        const updatedLines = [...formData.lines];
        updatedLines[index][field] = value;

        // Auto-calculate amount based on mode
        const line = updatedLines[index];
        line.mode = billingMode; // Update mode to current billing mode

        if (line.mode === "QTY") {
            line.amount_inr = (parseFloat(line.qty_kg) || 0) * (parseFloat(line.rate_inr_per_kg) || 0);
        } else if (line.mode === "CIF_INR") {
            line.amount_inr = (parseFloat(line.cif_inr) || 0) * ((parseFloat(line.pct) || 0) / 100);
        } else if (line.mode === "FOB_INR") {
            line.amount_inr = (parseFloat(line.fob_inr) || 0) * ((parseFloat(line.pct) || 0) / 100);
        }

        setFormData(prev => ({
            ...prev,
            lines: updatedLines
        }));
    };

    const handleAddPayment = () => {
        setFormData(prev => ({
            ...prev,
            payments: [...prev.payments, {
                date: new Date(),
                amount: 0,
                note: ""
            }]
        }));
    };

    const handleRemovePayment = (index) => {
        setFormData(prev => ({
            ...prev,
            payments: prev.payments.filter((_, i) => i !== index)
        }));
    };

    const handlePaymentChange = (index, field, value) => {
        const updatedPayments = [...formData.payments];
        updatedPayments[index][field] = value;
        setFormData(prev => ({
            ...prev,
            payments: updatedPayments
        }));
    };

    const calculateTotal = () => {
        return formData.lines.reduce((sum, line) => sum + (parseFloat(line.amount_inr) || 0), 0);
    };

    const calculateTotalPaid = () => {
        return formData.payments.reduce((sum, payment) => sum + (parseFloat(payment.amount) || 0), 0);
    };

    const handleFileChange = (e) => {
        const file = e.target.files[0];
        setFormData(prev => ({
            ...prev,
            purchase_invoice_copy: file
        }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSaving(true);
        setError("");
        setFieldErrors({});

        try {
            // Check if we have file upload
            const hasFile = formData.purchase_invoice_copy instanceof File;

            let payload;
            let headers = {};

            if (hasFile) {
                // Use FormData for file upload
                const formDataObj = new FormData();

                // Add regular fields - extract IDs from FK objects
                const fromCompanyId = typeof formData.from_company === 'object' ? formData.from_company?.id : formData.from_company;
                const toCompanyId = typeof formData.to_company === 'object' ? formData.to_company?.id : formData.to_company;
                const boeId = typeof formData.boe === 'object' ? formData.boe?.id : formData.boe;

                formDataObj.append('direction', formData.direction);
                if (fromCompanyId) formDataObj.append('from_company', fromCompanyId);
                if (toCompanyId) formDataObj.append('to_company', toCompanyId);
                if (boeId) formDataObj.append('boe', boeId);
                formDataObj.append('invoice_number', formData.invoice_number?.trim() || '');
                formDataObj.append('invoice_date', formatDateForAPI(formData.invoice_date));
                formDataObj.append('remarks', formData.remarks || '');

                // Add company snapshot fields
                if (formData.from_pan) formDataObj.append('from_pan', formData.from_pan);
                if (formData.from_gst) formDataObj.append('from_gst', formData.from_gst);
                if (formData.from_addr_line_1) formDataObj.append('from_addr_line_1', formData.from_addr_line_1);
                if (formData.from_addr_line_2) formDataObj.append('from_addr_line_2', formData.from_addr_line_2);
                if (formData.to_pan) formDataObj.append('to_pan', formData.to_pan);
                if (formData.to_gst) formDataObj.append('to_gst', formData.to_gst);
                if (formData.to_addr_line_1) formDataObj.append('to_addr_line_1', formData.to_addr_line_1);
                if (formData.to_addr_line_2) formDataObj.append('to_addr_line_2', formData.to_addr_line_2);

                // Add file
                formDataObj.append('purchase_invoice_copy', formData.purchase_invoice_copy);

                // Add lines as JSON string
                formDataObj.append('lines', JSON.stringify(formData.lines));

                // Add payments as JSON string
                const paymentsData = formData.payments.map(payment => ({
                    ...payment,
                    date: formatDateForAPI(payment.date)
                }));
                formDataObj.append('payments', JSON.stringify(paymentsData));

                payload = formDataObj;
                headers = { 'Content-Type': 'multipart/form-data' };
            } else {
                // Use regular JSON - extract IDs from FK objects
                const fromCompanyId = typeof formData.from_company === 'object' ? formData.from_company?.id : formData.from_company;
                const toCompanyId = typeof formData.to_company === 'object' ? formData.to_company?.id : formData.to_company;
                const boeId = typeof formData.boe === 'object' ? formData.boe?.id : formData.boe;

                payload = {
                    ...formData,
                    from_company: fromCompanyId,
                    to_company: toCompanyId,
                    boe: boeId || null,
                    invoice_number: formData.invoice_number?.trim() || '',
                    invoice_date: formatDateForAPI(formData.invoice_date),
                    payments: formData.payments.map(payment => ({
                        ...payment,
                        date: formatDateForAPI(payment.date)
                    }))
                };
            }

            if (isEdit) {
                await api.patch(`/trades/${id}/`, payload, { headers });
            } else {
                await api.post(`/trades/`, payload, { headers });
            }

            navigate("/trades");
        } catch (err) {
            console.error("Save error:", err.response?.data);

            // Handle field-level errors
            if (err.response?.data && typeof err.response.data === 'object') {
                setFieldErrors(err.response.data);

                // Create user-friendly error message
                const errorMessages = [];
                Object.entries(err.response.data).forEach(([field, errors]) => {
                    if (Array.isArray(errors)) {
                        errors.forEach(error => {
                            errorMessages.push(`${field}: ${error}`);
                        });
                    } else {
                        errorMessages.push(`${field}: ${errors}`);
                    }
                });

                setError(errorMessages.join('\n') || "Validation errors occurred");
            } else {
                setError(err.response?.data?.detail || "Failed to save trade");
            }
        } finally {
            setSaving(false);
        }
    };

    const handleDownloadPDF = async () => {
        if (!id) {
            alert("Please save the trade first");
            return;
        }
        // TODO: Implement PDF download
        alert("PDF download coming soon");
    };

    return (
        <div className="container-fluid mt-4">
            <nav aria-label="breadcrumb" className="mb-3">
                <ol className="breadcrumb">
                    <li className="breadcrumb-item">
                        <a href="#" onClick={(e) => { e.preventDefault(); navigate('/'); }}>Home</a>
                    </li>
                    <li className="breadcrumb-item">
                        <a href="#" onClick={(e) => { e.preventDefault(); navigate('/trades'); }}>Trades</a>
                    </li>
                    <li className="breadcrumb-item active" aria-current="page">
                        {isEdit ? "Edit Trade" : "Create Trade"}
                    </li>
                </ol>
            </nav>

            <h2>{isEdit ? "Edit Trade" : "Create Trade"}</h2>

            {error && (
                <div className="alert alert-danger alert-dismissible fade show">
                    <pre style={{ whiteSpace: 'pre-wrap', margin: 0 }}>{error}</pre>
                    <button
                        type="button"
                        className="btn-close"
                        onClick={() => setError("")}
                    ></button>
                </div>
            )}

            <form onSubmit={handleSubmit}>
                {/* Direction Selector */}
                <div className="card mb-4">
                    <div className="card-body">
                        <div className="row">
                            <div className="col-md-6">
                                <label className="form-label fw-bold">Transaction Type <span className="text-danger">*</span></label>
                                <div className="d-flex gap-4">
                                    <div className="form-check">
                                        <input
                                            className="form-check-input"
                                            type="radio"
                                            name="direction"
                                            id="directionPurchase"
                                            value="PURCHASE"
                                            checked={formData.direction === "PURCHASE"}
                                            onChange={(e) => setFormData(prev => ({ ...prev, direction: e.target.value }))}
                                        />
                                        <label className="form-check-label" htmlFor="directionPurchase">
                                            Purchase (Trade In)
                                        </label>
                                    </div>
                                    <div className="form-check">
                                        <input
                                            className="form-check-input"
                                            type="radio"
                                            name="direction"
                                            id="directionSale"
                                            value="SALE"
                                            checked={formData.direction === "SALE"}
                                            onChange={(e) => setFormData(prev => ({ ...prev, direction: e.target.value }))}
                                        />
                                        <label className="form-check-label" htmlFor="directionSale">
                                            Sale (Trade Out)
                                        </label>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Company Snapshots - Following Screenshot Layout */}
                <div className="row mb-4">
                    {/* From Company */}
                    <div className="col-md-6">
                        <div className="card">
                            <div className="card-body">
                                <button
                                    type="button"
                                    className="btn btn-warning btn-sm mb-3"
                                    onClick={handlePrefillFromCompany}
                                >
                                    Prefill From Company details
                                </button>

                                <h6>From Company Snapshot</h6>

                                <div className="mb-3">
                                    <label className="form-label">From Company <span className="text-danger">*</span></label>
                                    <HybridSelect
                                        fieldMeta={{
                                            endpoint: "/masters/companies/",
                                            label_field: "name"
                                        }}
                                        value={formData.from_company}
                                        onChange={(val) => setFormData(prev => ({ ...prev, from_company: val }))}
                                        isClearable={false}
                                        placeholder="Search and select company..."
                                    />
                                    {fieldErrors.from_company && (
                                        <div className="text-danger small">{fieldErrors.from_company}</div>
                                    )}
                                </div>

                                <div className="row">
                                    <div className="col-md-6 mb-2">
                                        <label className="form-label small">PAN</label>
                                        <input
                                            type="text"
                                            className="form-control form-control-sm"
                                            value={formData.from_pan || ""}
                                            onChange={(e) => setFormData(prev => ({ ...prev, from_pan: e.target.value }))}
                                        />
                                    </div>
                                    <div className="col-md-6 mb-2">
                                        <label className="form-label small">GST</label>
                                        <input
                                            type="text"
                                            className="form-control form-control-sm"
                                            value={formData.from_gst || ""}
                                            onChange={(e) => setFormData(prev => ({ ...prev, from_gst: e.target.value }))}
                                        />
                                    </div>
                                </div>

                                <div className="row">
                                    <div className="col-md-6 mb-2">
                                        <label className="form-label small">Address Line 1</label>
                                        <input
                                            type="text"
                                            className="form-control form-control-sm"
                                            value={formData.from_addr_line_1 || ""}
                                            onChange={(e) => setFormData(prev => ({ ...prev, from_addr_line_1: e.target.value }))}
                                        />
                                    </div>
                                    <div className="col-md-6 mb-2">
                                        <label className="form-label small">Address Line 2</label>
                                        <input
                                            type="text"
                                            className="form-control form-control-sm"
                                            value={formData.from_addr_line_2 || ""}
                                            onChange={(e) => setFormData(prev => ({ ...prev, from_addr_line_2: e.target.value }))}
                                        />
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>

                    {/* To Company */}
                    <div className="col-md-6">
                        <div className="card">
                            <div className="card-body">
                                <button
                                    type="button"
                                    className="btn btn-warning btn-sm mb-3"
                                    onClick={handlePrefillToCompany}
                                >
                                    Prefill To Company details
                                </button>

                                <h6>To Company Snapshot</h6>

                                <div className="mb-3">
                                    <label className="form-label">To Company <span className="text-danger">*</span></label>
                                    <HybridSelect
                                        fieldMeta={{
                                            endpoint: "/masters/companies/",
                                            label_field: "name"
                                        }}
                                        value={formData.to_company}
                                        onChange={(val) => setFormData(prev => ({ ...prev, to_company: val }))}
                                        isClearable={false}
                                        placeholder="Search and select company..."
                                    />
                                    {fieldErrors.to_company && (
                                        <div className="text-danger small">{fieldErrors.to_company}</div>
                                    )}
                                </div>

                                <div className="row">
                                    <div className="col-md-6 mb-2">
                                        <label className="form-label small">PAN</label>
                                        <input
                                            type="text"
                                            className="form-control form-control-sm"
                                            value={formData.to_pan || ""}
                                            onChange={(e) => setFormData(prev => ({ ...prev, to_pan: e.target.value }))}
                                        />
                                    </div>
                                    <div className="col-md-6 mb-2">
                                        <label className="form-label small">GST</label>
                                        <input
                                            type="text"
                                            className="form-control form-control-sm"
                                            value={formData.to_gst || ""}
                                            onChange={(e) => setFormData(prev => ({ ...prev, to_gst: e.target.value }))}
                                        />
                                    </div>
                                </div>

                                <div className="row">
                                    <div className="col-md-6 mb-2">
                                        <label className="form-label small">Address Line 1</label>
                                        <input
                                            type="text"
                                            className="form-control form-control-sm"
                                            value={formData.to_addr_line_1 || ""}
                                            onChange={(e) => setFormData(prev => ({ ...prev, to_addr_line_1: e.target.value }))}
                                        />
                                    </div>
                                    <div className="col-md-6 mb-2">
                                        <label className="form-label small">Address Line 2</label>
                                        <input
                                            type="text"
                                            className="form-control form-control-sm"
                                            value={formData.to_addr_line_2 || ""}
                                            onChange={(e) => setFormData(prev => ({ ...prev, to_addr_line_2: e.target.value }))}
                                        />
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>

                {/* Invoice Details Section - Matching Screenshot Layout */}
                <div className="row mb-3">
                    <div className="col-md-6">
                        <label className="form-label">Invoice Number (optional)</label>
                        <div className="d-flex gap-2">
                            <input
                                type="text"
                                className="form-control"
                                value={formData.invoice_number || ""}
                                onChange={(e) => setFormData(prev => ({ ...prev, invoice_number: e.target.value }))}
                            />
                        </div>
                    </div>
                    <div className="col-md-6">
                        <label className="form-label">Invoice Date</label>
                        <DatePicker
                            selected={formData.invoice_date instanceof Date ? formData.invoice_date : new Date(formData.invoice_date)}
                            onChange={(date) => setFormData(prev => ({ ...prev, invoice_date: date }))}
                            dateFormat="dd/MM/yyyy"
                            className="form-control"
                        />
                    </div>
                </div>

                <div className="mb-3">
                    <button
                        type="button"
                        className="btn btn-warning btn-sm"
                        onClick={handlePrefillInvoiceNumber}
                        disabled={formData.direction !== "SALE"}
                        title={formData.direction !== "SALE" ? "Only available for SALE transactions" : ""}
                    >
                        Prefill Invoice Number
                    </button>
                    <button
                        type="button"
                        className="btn btn-warning btn-sm ms-2"
                        onClick={handlePrefillFromBOE}
                        disabled={!formData.boe}
                    >
                        Prefill from BOE
                    </button>
                </div>

                {/* BOE and Remarks */}
                <div className="row mb-4">
                    <div className="col-md-6">
                        <label className="form-label">BOE (optional)</label>
                        <HybridSelect
                            fieldMeta={{
                                endpoint: isEdit ? "/bill-of-entries/" : "/bill-of-entries/?invoice_no__isnull=true",
                                label_field: "bill_of_entry_number"
                            }}
                            value={formData.boe}
                            onChange={(val) => setFormData(prev => ({ ...prev, boe: val }))}
                            isClearable={true}
                            placeholder="Search and select BOE (without invoice)..."
                        />
                    </div>
                    <div className="col-md-6">
                        <label className="form-label">Remarks</label>
                        <textarea
                            className="form-control"
                            rows="2"
                            value={formData.remarks || ""}
                            onChange={(e) => setFormData(prev => ({ ...prev, remarks: e.target.value }))}
                            placeholder="Enter any remarks..."
                        />
                    </div>
                </div>

                {/* Billing Mode - Matching Screenshot */}
                <div className="mb-3">
                    <label className="form-label fw-bold">Billing Mode</label>
                    <div className="d-flex gap-4">
                        <div className="form-check">
                            <input
                                className="form-check-input"
                                type="radio"
                                name="billingMode"
                                id="modeQTY"
                                value="QTY"
                                checked={billingMode === "QTY"}
                                onChange={(e) => {
                                    setBillingMode(e.target.value);
                                    setFormData(prev => ({
                                        ...prev,
                                        lines: prev.lines.map(line => ({ ...line, mode: e.target.value }))
                                    }));
                                }}
                            />
                            <label className="form-check-label" htmlFor="modeQTY">
                                By KG
                            </label>
                        </div>
                        <div className="form-check">
                            <input
                                className="form-check-input"
                                type="radio"
                                name="billingMode"
                                id="modeCIF"
                                value="CIF_INR"
                                checked={billingMode === "CIF_INR"}
                                onChange={(e) => {
                                    setBillingMode(e.target.value);
                                    setFormData(prev => ({
                                        ...prev,
                                        lines: prev.lines.map(line => ({ ...line, mode: e.target.value }))
                                    }));
                                }}
                            />
                            <label className="form-check-label" htmlFor="modeCIF">
                                By CIF INR (%)
                            </label>
                        </div>
                        <div className="form-check">
                            <input
                                className="form-check-input"
                                type="radio"
                                name="billingMode"
                                id="modeFOB"
                                value="FOB_INR"
                                checked={billingMode === "FOB_INR"}
                                onChange={(e) => {
                                    setBillingMode(e.target.value);
                                    setFormData(prev => ({
                                        ...prev,
                                        lines: prev.lines.map(line => ({ ...line, mode: e.target.value }))
                                    }));
                                }}
                            />
                            <label className="form-check-label" htmlFor="modeFOB">
                                By FOB INR (%)
                            </label>
                        </div>
                    </div>
                </div>

                {/* Trade Lines Table - Matching Screenshot */}
                <div className="table-responsive mb-3">
                    <table className="table table-bordered table-sm">
                        <thead className="table-light">
                            <tr>
                                <th style={{ width: "3%" }}>#</th>
                                <th style={{ width: "20%" }}>License (SR)</th>
                                <th style={{ width: "10%" }}>HSN</th>
                                {billingMode !== "QTY" && <th style={{ width: "10%" }}>CIF $</th>}
                                {billingMode !== "QTY" && <th style={{ width: "8%" }}>Exch Rate</th>}
                                {billingMode !== "QTY" && <th style={{ width: "10%" }}>CIF INR</th>}
                                {billingMode === "QTY" && <th style={{ width: "10%" }}>Qty (KG)</th>}
                                {billingMode === "QTY" && <th style={{ width: "10%" }}>Rate (INR/KG)</th>}
                                <th style={{ width: "8%" }}>Billing %</th>
                                <th style={{ width: "12%" }}>Amount</th>
                                <th style={{ width: "3%" }}></th>
                            </tr>
                        </thead>
                        <tbody>
                            {formData.lines.map((line, index) => (
                                <tr key={index}>
                                    <td className="text-center">{index + 1}</td>
                                    <td>
                                        <HybridSelect
                                            fieldMeta={{
                                                endpoint: "/license-items/",
                                                label_field: "label"
                                            }}
                                            value={line.sr_number}
                                            onChange={(val) => handleLineChange(index, 'sr_number', val)}
                                            isClearable={true}
                                            placeholder="Select License SR..."
                                        />
                                    </td>
                                    <td>
                                        <input
                                            type="text"
                                            className="form-control form-control-sm"
                                            value={line.hsn_code || "49070000"}
                                            onChange={(e) => handleLineChange(index, 'hsn_code', e.target.value)}
                                        />
                                    </td>
                                    {billingMode !== "QTY" && (
                                        <>
                                            <td>
                                                <input
                                                    type="number"
                                                    className="form-control form-control-sm text-end"
                                                    value={line.cif_fc || ""}
                                                    onChange={(e) => handleLineChange(index, 'cif_fc', parseFloat(e.target.value) || 0)}
                                                    step="0.01"
                                                />
                                            </td>
                                            <td>
                                                <input
                                                    type="number"
                                                    className="form-control form-control-sm text-end"
                                                    value={line.exc_rate || ""}
                                                    onChange={(e) => handleLineChange(index, 'exc_rate', parseFloat(e.target.value) || 0)}
                                                    step="0.01"
                                                />
                                            </td>
                                            <td>
                                                <input
                                                    type="number"
                                                    className="form-control form-control-sm text-end"
                                                    value={line.cif_inr || ""}
                                                    onChange={(e) => handleLineChange(index, 'cif_inr', parseFloat(e.target.value) || 0)}
                                                    step="0.01"
                                                />
                                            </td>
                                        </>
                                    )}
                                    {billingMode === "QTY" && (
                                        <>
                                            <td>
                                                <input
                                                    type="number"
                                                    className="form-control form-control-sm text-end"
                                                    value={line.qty_kg || ""}
                                                    onChange={(e) => handleLineChange(index, 'qty_kg', parseFloat(e.target.value) || 0)}
                                                    step="0.0001"
                                                />
                                            </td>
                                            <td>
                                                <input
                                                    type="number"
                                                    className="form-control form-control-sm text-end"
                                                    value={line.rate_inr_per_kg || ""}
                                                    onChange={(e) => handleLineChange(index, 'rate_inr_per_kg', parseFloat(e.target.value) || 0)}
                                                    step="0.01"
                                                />
                                            </td>
                                        </>
                                    )}
                                    <td>
                                        <input
                                            type="number"
                                            className="form-control form-control-sm text-end"
                                            value={line.pct || ""}
                                            onChange={(e) => handleLineChange(index, 'pct', parseFloat(e.target.value) || 0)}
                                            step="0.001"
                                        />
                                    </td>
                                    <td>
                                        <input
                                            type="text"
                                            className="form-control form-control-sm text-end fw-bold"
                                            value={line.amount_inr ? parseFloat(line.amount_inr).toFixed(2) : "0.00"}
                                            readOnly
                                            style={{ backgroundColor: '#f8f9fa' }}
                                        />
                                    </td>
                                    <td className="text-center">
                                        <button
                                            type="button"
                                            className="btn btn-danger btn-sm"
                                            onClick={() => handleRemoveLine(index)}
                                        >
                                            <i className="bi bi-trash"></i>
                                        </button>
                                    </td>
                                </tr>
                            ))}
                            <tr className="table-secondary fw-bold">
                                <td colSpan={billingMode === "QTY" ? 5 : 7} className="text-end">Total</td>
                                <td className="text-end">{calculateTotal().toFixed(2)}</td>
                                <td></td>
                            </tr>
                        </tbody>
                    </table>
                </div>

                <button
                    type="button"
                    className="btn btn-warning mb-4"
                    onClick={handleAddLine}
                >
                    Add Row
                </button>

                {/* Action Buttons - Matching Screenshot */}
                <div className="d-flex gap-2 mb-4">
                    <button
                        type="submit"
                        className="btn btn-warning"
                        disabled={saving}
                    >
                        {saving ? "Saving..." : "Save Trade"}
                    </button>
                    <button
                        type="button"
                        className="btn btn-secondary"
                        onClick={() => navigate("/trades")}
                    >
                        Cancel
                    </button>
                    {isEdit && (
                        <button
                            type="button"
                            className="btn btn-warning"
                            onClick={handleDownloadPDF}
                        >
                            Download PDF
                        </button>
                    )}
                </div>
            </form>
        </div>
    );
}
