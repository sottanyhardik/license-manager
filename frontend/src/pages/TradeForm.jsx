import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from 'react-toastify';
import api from "../api/axios";
import HybridSelect from "../components/HybridSelect";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import {formatDateForInput} from "../utils/dateFormatter";
import TransferLetterModal from "../components/TransferLetterModal";

export default function TradeForm() {
    const { id } = useParams();
    const navigate = useNavigate();
    const isEdit = Boolean(id);

    const [formData, setFormData] = useState({
        direction: "PURCHASE",
        license_type: "DFIA",
        incentive_license: null,
        from_company: null,
        to_company: null,
        boe: null,
        invoice_number: "",
        invoice_date: new Date(),
        remarks: "",
        purchase_invoice_copy: null,
        lines: [],
        payments: [],
        incentive_lines: [] // New field for incentive license lines
    });

    const [billingMode, setBillingMode] = useState("CIF_INR");
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");
    const [fieldErrors, setFieldErrors] = useState({});
    const [showTransferLetterModal, setShowTransferLetterModal] = useState(false);
    const isInitialLoadRef = useRef(true);

    // Helper function to format Date object to YYYY-MM-DD for API
    const formatDateForAPI = (date) => {
        if (!date) return null;
        if (!(date instanceof Date)) return date;
        return formatDateForInput(date);
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
            toast.error("Failed to fetch BOE details");
        }
    }, [formData.boe, billingMode]);

    // Fetch existing trade if editing
    useEffect(() => {
        if (isEdit) {
            fetchTrade();
        } else {
            // In create mode, mark initial load as complete immediately
            isInitialLoadRef.current = false;
        }
    }, [isEdit, id]);

    // Auto-prefill from BOE when BOE is selected (works in both create and edit mode)
    // Skip during initial load to prevent overwriting existing trade data
    useEffect(() => {
        if (formData.boe && !isInitialLoadRef.current) {
            handlePrefillFromBOE();
        }
    }, [formData.boe, handlePrefillFromBOE]);


    const fetchTrade = async () => {
        try {
            const { data } = await api.get(`/trades/${id}/`);

            // Parse date fields
            if (data.invoice_date) {
                const originalDate = data.invoice_date;
                console.log('Original invoice_date from API:', originalDate);

                const parts = data.invoice_date.split('-');

                // Detect format: if first part is 4 digits, it's yyyy-MM-dd, else dd-MM-yyyy
                let year, month, day;
                if (parts[0].length === 4) {
                    // Format: yyyy-MM-dd
                    year = parseInt(parts[0]);
                    month = parseInt(parts[1]) - 1; // JS months are 0-indexed
                    day = parseInt(parts[2]);
                } else {
                    // Format: dd-MM-yyyy
                    day = parseInt(parts[0]);
                    month = parseInt(parts[1]) - 1; // JS months are 0-indexed
                    year = parseInt(parts[2]);
                }

                data.invoice_date = new Date(year, month, day, 12, 0, 0);
                console.log('Parsed to Date object:', data.invoice_date.toLocaleDateString(), data.invoice_date);
            }

            // Parse payment dates
            if (data.payments) {
                data.payments = data.payments.map(payment => ({
                    ...payment,
                    date: payment.date ? new Date(payment.date + 'T12:00:00') : new Date()
                }));
            }

            // Ensure incentive_lines is initialized
            if (!data.incentive_lines) {
                data.incentive_lines = [];
            }

            // For edit mode: if incentive_lines exist and have incentive_license IDs,
            // fetch the full license objects so HybridSelect can display them
            // Gracefully handle deleted/missing licenses
            if (data.incentive_lines && data.incentive_lines.length > 0) {
                const enrichedLines = await Promise.all(
                    data.incentive_lines.map(async (line) => {
                        if (line.incentive_license && typeof line.incentive_license === 'number') {
                            try {
                                const { data: licenseData } = await api.get(`/incentive-licenses/${line.incentive_license}/`);
                                return {
                                    ...line,
                                    incentive_license: licenseData.id // Keep as ID for HybridSelect
                                };
                            } catch (err) {
                                // License was deleted or doesn't exist
                                console.warn(`Incentive license ${line.incentive_license} not found (may have been deleted)`);
                                return {
                                    ...line,
                                    incentive_license: null, // Clear the invalid reference
                                    _deletedLicenseNote: `Previously linked to license ID ${line.incentive_license} (deleted)`
                                };
                            }
                        }
                        return line;
                    })
                );
                data.incentive_lines = enrichedLines;
            }

            setFormData(data);

            // Set billing mode from first line if exists
            if (data.lines && data.lines.length > 0) {
                setBillingMode(data.lines[0].mode);
            }

            // Mark initial load as complete to enable BOE auto-prefill
            isInitialLoadRef.current = false;
        } catch (err) {
            setError("Failed to load trade");
        }
    };

    const handleFromCompanyChange = async (val) => {
        setFormData(prev => ({ ...prev, from_company: val }));

        // Auto-fetch company details
        if (val) {
            try {
                const companyId = typeof val === 'object' ? val.id : val;
                const { data } = await api.get(`/masters/companies/${companyId}/`);
                setFormData(prev => ({
                    ...prev,
                    from_company: val,
                    from_pan: data.pan || "",
                    from_gst: data.gst_number || "",
                    from_addr_line_1: data.address_line_1 || "",
                    from_addr_line_2: data.address_line_2 || ""
                }));
            } catch (err) {
                toast.error("Failed to fetch company details");
            }
        }
    };

    const handleToCompanyChange = async (val) => {
        setFormData(prev => ({ ...prev, to_company: val }));

        // Auto-fetch company details
        if (val) {
            try {
                const companyId = typeof val === 'object' ? val.id : val;
                const { data } = await api.get(`/masters/companies/${companyId}/`);
                setFormData(prev => ({
                    ...prev,
                    to_company: val,
                    to_pan: data.pan || "",
                    to_gst: data.gst_number || "",
                    to_addr_line_1: data.address_line_1 || "",
                    to_addr_line_2: data.address_line_2 || ""
                }));
            } catch (err) {
                toast.error("Failed to fetch company details");
            }
        }
    };

    const handlePrefillInvoiceNumber = async () => {
        // For PURCHASE/COMMISSION_PURCHASE, use to_company (buyer); for SALE/COMMISSION_SALE, use from_company (seller)
        const isPurchaseType = formData.direction === 'PURCHASE' || formData.direction === 'COMMISSION_PURCHASE';
        const relevantCompany = isPurchaseType ? formData.to_company : formData.from_company;

        if (!relevantCompany) {
            const companyField = isPurchaseType ? 'To Company' : 'From Company';
            toast.warning(`Please select ${companyField} first`);
            return;
        }

        if (!formData.direction) {
            toast.warning("Please select transaction type first");
            return;
        }

        try {
            // Company can be either ID or object with id
            const companyId = typeof relevantCompany === 'object' ? relevantCompany.id : relevantCompany;
            const { data } = await api.get(`/trades/prefill-invoice-number/`, {
                params: {
                    direction: formData.direction,
                    company_id: companyId,
                    invoice_date: formatDateForAPI(formData.invoice_date)
                }
            });
            setFormData(prev => ({
                ...prev,
                invoice_number: data.invoice_number || ""
            }));
            toast.success(`Invoice number generated: ${data.invoice_number}`);
        } catch (err) {
            toast.error(err.response?.data?.error || "Failed to generate invoice number");
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

    const handleAddIncentiveLine = () => {
        setFormData(prev => ({
            ...prev,
            incentive_lines: [...prev.incentive_lines, {
                incentive_license: null,
                license_value: 0,
                rate_pct: 0,
                amount_inr: 0
            }]
        }));
    };

    const handleRemoveIncentiveLine = (index) => {
        setFormData(prev => ({
            ...prev,
            incentive_lines: prev.incentive_lines.filter((_, i) => i !== index)
        }));
    };

    const handleIncentiveLineChange = async (index, field, value) => {
        const updatedLines = [...formData.incentive_lines];
        updatedLines[index][field] = value;

        const line = updatedLines[index];

        // If incentive license is selected, fetch full details and auto-fill license_value
        if (field === 'incentive_license' && value) {
            console.log('Selected incentive license ID:', value);
            try {
                // Fetch the full license details from API
                const { data } = await api.get(`/incentive-licenses/${value}/`);
                console.log('Fetched incentive license data:', data);

                // Keep the ID as the value (don't replace with full object)
                // line.incentive_license is already set to 'value' on line 267

                // Auto-fill license_value from fetched data
                line.license_value = parseFloat(data.license_value) || 0;
                console.log('Auto-filled license_value:', line.license_value);

                // Trigger recalculation of amount if rate is already set
                if (line.rate_pct > 0) {
                    const licenseValue = parseFloat(line.license_value) || 0;
                    const ratePct = parseFloat(line.rate_pct) || 0;
                    line.amount_inr = Math.round(licenseValue * (ratePct / 100));
                }
            } catch (err) {
                console.error('Failed to fetch incentive license details:', err);
                toast.error('Failed to fetch license details');
            }
        }

        // Auto-calculate amount from license_value and rate_pct
        if (field === 'license_value' || field === 'rate_pct') {
            const licenseValue = parseFloat(line.license_value) || 0;
            const ratePct = parseFloat(line.rate_pct) || 0;
            line.amount_inr = Math.round(licenseValue * (ratePct / 100));
        }

        // If amount is changed, reverse calculate rate_pct
        if (field === 'amount_inr') {
            const licenseValue = parseFloat(line.license_value) || 0;
            const amount = parseFloat(line.amount_inr) || 0;
            if (licenseValue > 0) {
                line.rate_pct = Math.round((amount / licenseValue * 100) * 1000) / 1000;
            }
        }

        setFormData(prev => ({
            ...prev,
            incentive_lines: updatedLines
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

        // Auto-calculate derived fields
        const line = updatedLines[index];
        line.mode = billingMode; // Update mode to current billing mode

        // Calculate CIF_INR from CIF_FC and Exchange Rate if available (only in CIF_INR mode)
        if (line.mode === "CIF_INR" && (field === 'cif_fc' || field === 'exc_rate') && line.cif_fc && line.exc_rate) {
            line.cif_inr = parseFloat((parseFloat(line.cif_fc) * parseFloat(line.exc_rate)).toFixed(2));
        }

        // Auto-calculate Exchange Rate from CIF INR and CIF $ if both exist (only in CIF_INR mode)
        if (line.mode === "CIF_INR" && (field === 'cif_inr' || field === 'cif_fc') && line.cif_inr && line.cif_fc) {
            const cifInr = parseFloat(line.cif_inr) || 0;
            const cifFc = parseFloat(line.cif_fc) || 0;
            if (cifFc > 0) {
                line.exc_rate = Math.round((cifInr / cifFc) * 100) / 100;
            }
        }

        // If license item (sr_number) is selected and we're in CIF/FOB mode, get quantity from license item
        if (field === 'sr_number' && value && (line.mode === "CIF_INR" || line.mode === "FOB_INR")) {
            // The sr_number is the license import item object with quantity
            if (value.quantity) {
                line.qty_kg = parseFloat(value.quantity);
            }
        }

        // Auto-calculate amount or rate based on mode
        // If amount_inr is being changed, calculate rate (reverse calculation)
        // Otherwise, calculate amount from rate

        if (field === 'amount_inr') {
            // Reverse calculation: calculate rate from amount (round to 3 decimals)
            const amount = parseFloat(line.amount_inr) || 0;

            if (line.mode === "QTY") {
                const qty = parseFloat(line.qty_kg) || 0;
                if (qty > 0) {
                    line.rate_inr_per_kg = Math.round((amount / qty) * 1000) / 1000;
                }
            } else if (line.mode === "CIF_INR") {
                const cif = parseFloat(line.cif_inr) || 0;
                if (cif > 0) {
                    line.pct = Math.round((amount / cif * 100) * 1000) / 1000;
                }
            } else if (line.mode === "FOB_INR") {
                const fob = parseFloat(line.fob_inr) || 0;
                if (fob > 0) {
                    line.pct = Math.round((amount / fob * 100) * 1000) / 1000;
                }
            }
        } else {
            // Forward calculation: calculate amount from rate (round to whole number)
            if (line.mode === "QTY") {
                line.amount_inr = Math.round((parseFloat(line.qty_kg) || 0) * (parseFloat(line.rate_inr_per_kg) || 0));
            } else if (line.mode === "CIF_INR") {
                line.amount_inr = Math.round((parseFloat(line.cif_inr) || 0) * ((parseFloat(line.pct) || 0) / 100));
            } else if (line.mode === "FOB_INR") {
                line.amount_inr = Math.round((parseFloat(line.fob_inr) || 0) * ((parseFloat(line.pct) || 0) / 100));
            }
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
        if (formData.license_type === "INCENTIVE") {
            return formData.incentive_lines.reduce((sum, line) => sum + (parseFloat(line.amount_inr) || 0), 0);
        }
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

                // Add lines as JSON string (clean up empty id fields)
                const cleanedLines = formData.lines.map(line => {
                    const cleanedLine = {...line};
                    if (cleanedLine.id === '' || cleanedLine.id === null || cleanedLine.id === undefined) {
                        delete cleanedLine.id;
                    }
                    // Always set HSN code to 49070000
                    cleanedLine.hsn_code = '49070000';
                    return cleanedLine;
                });
                formDataObj.append('lines', JSON.stringify(cleanedLines));

                // Add incentive_lines as JSON string (clean up empty id fields)
                const cleanedIncentiveLines = formData.incentive_lines.map(line => {
                    const cleanedLine = {...line};
                    if (cleanedLine.id === '' || cleanedLine.id === null || cleanedLine.id === undefined) {
                        delete cleanedLine.id;
                    }
                    // Extract incentive_license ID if it's an object
                    if (cleanedLine.incentive_license && typeof cleanedLine.incentive_license === 'object') {
                        cleanedLine.incentive_license = cleanedLine.incentive_license.id;
                    }
                    return cleanedLine;
                });
                formDataObj.append('incentive_lines', JSON.stringify(cleanedIncentiveLines));

                // Add payments as JSON string (clean up empty id fields)
                const paymentsData = formData.payments.map(payment => {
                    const cleanedPayment = {...payment, date: formatDateForAPI(payment.date)};
                    if (cleanedPayment.id === '' || cleanedPayment.id === null || cleanedPayment.id === undefined) {
                        delete cleanedPayment.id;
                    }
                    return cleanedPayment;
                });
                formDataObj.append('payments', JSON.stringify(paymentsData));

                payload = formDataObj;
                headers = { 'Content-Type': 'multipart/form-data' };
            } else {
                // Use regular JSON - extract IDs from FK objects
                const fromCompanyId = typeof formData.from_company === 'object' ? formData.from_company?.id : formData.from_company;
                const toCompanyId = typeof formData.to_company === 'object' ? formData.to_company?.id : formData.to_company;
                const boeId = typeof formData.boe === 'object' ? formData.boe?.id : formData.boe;

                // Clean up lines: remove empty id fields
                const cleanedLines = formData.lines.map(line => {
                    const cleanedLine = {...line};
                    if (cleanedLine.id === '' || cleanedLine.id === null || cleanedLine.id === undefined) {
                        delete cleanedLine.id;
                    }
                    // Always set HSN code to 49070000
                    cleanedLine.hsn_code = '49070000';
                    return cleanedLine;
                });

                // Clean up incentive_lines: remove empty id fields and extract IDs
                const cleanedIncentiveLines = formData.incentive_lines.map(line => {
                    const cleanedLine = {...line};
                    if (cleanedLine.id === '' || cleanedLine.id === null || cleanedLine.id === undefined) {
                        delete cleanedLine.id;
                    }
                    // Extract incentive_license ID if it's an object
                    if (cleanedLine.incentive_license && typeof cleanedLine.incentive_license === 'object') {
                        cleanedLine.incentive_license = cleanedLine.incentive_license.id;
                    }
                    return cleanedLine;
                });

                // Clean up payments: remove empty id fields
                const cleanedPayments = formData.payments.map(payment => {
                    const cleanedPayment = {...payment, date: formatDateForAPI(payment.date)};
                    if (cleanedPayment.id === '' || cleanedPayment.id === null || cleanedPayment.id === undefined) {
                        delete cleanedPayment.id;
                    }
                    return cleanedPayment;
                });

                payload = {
                    ...formData,
                    from_company: fromCompanyId,
                    to_company: toCompanyId,
                    boe: boeId || null,
                    invoice_number: formData.invoice_number?.trim() || '',
                    invoice_date: formatDateForAPI(formData.invoice_date),
                    lines: cleanedLines,
                    incentive_lines: cleanedIncentiveLines,
                    payments: cleanedPayments
                };
            }

            if (isEdit) {
                await api.patch(`/trades/${id}/`, payload, { headers });
            } else {
                await api.post(`/trades/`, payload, { headers });
            }

            toast.success(isEdit ? "Trade updated successfully" : "Trade created successfully");
            navigate("/trades");
        } catch (err) {
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

                const errorMsg = errorMessages.join('\n') || "Validation errors occurred";
                setError(errorMsg);
                toast.error(errorMsg);
            } else {
                const errorMsg = err.response?.data?.detail || "Failed to save trade";
                setError(errorMsg);
                toast.error(errorMsg);
            }
        } finally {
            setSaving(false);
        }
    };

    const handleDownloadPDF = async (includeSignature = true) => {
        if (!id) {
            toast.warning("Please save the trade first");
            return;
        }

        // Check if this is a SALE transaction
        if (formData.direction !== 'SALE') {
            toast.warning("Bill of Supply can only be generated for SALE transactions");
            return;
        }

        try {
            const response = await api.get(`/trades/${id}/generate-bill-of-supply/`, {
                params: {
                    include_signature: includeSignature
                },
                responseType: 'blob'
            });

            // Create blob link to download
            const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
            const link = document.createElement('a');
            link.href = url;
            const signSuffix = includeSignature ? '_with_sign' : '_without_sign';
            const filename = `Bill_of_Supply_${formData.invoice_number || id}_${new Date().toISOString().split('T')[0]}${signSuffix}.pdf`;
            link.setAttribute('download', filename);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
            toast.success(`Bill of Supply downloaded ${includeSignature ? 'with' : 'without'} signature`);
        } catch (err) {
            toast.error('Failed to download Bill of Supply. Please try again.');
        }
    };

    const handleDownloadPurchaseInvoice = async (includeSignature = true) => {
        if (!id) {
            toast.warning("Please save the trade first");
            return;
        }

        // Check if this is a PURCHASE transaction
        if (formData.direction !== 'PURCHASE') {
            toast.warning("Purchase Invoice can only be generated for PURCHASE transactions");
            return;
        }

        try {
            const response = await api.get(`/trades/${id}/generate-purchase-invoice/`, {
                params: {
                    include_signature: includeSignature
                },
                responseType: 'blob'
            });

            // Create blob link to download
            const url = window.URL.createObjectURL(new Blob([response.data], { type: 'application/pdf' }));
            const link = document.createElement('a');
            link.href = url;
            const signSuffix = includeSignature ? '_with_sign' : '_without_sign';
            const filename = `Purchase_Invoice_${formData.invoice_number || id}_${new Date().toISOString().split('T')[0]}${signSuffix}.pdf`;
            link.setAttribute('download', filename);
            document.body.appendChild(link);
            link.click();
            link.remove();
            window.URL.revokeObjectURL(url);
            toast.success(`Purchase Invoice downloaded ${includeSignature ? 'with' : 'without'} signature`);
        } catch (err) {
            toast.error('Failed to download Purchase Invoice. Please try again.');
        }
    };

    return (
        <div className="container-fluid" style={{ backgroundColor: '#f8f9fa', minHeight: '100vh', padding: '24px' }}>
            {/* Professional Header with Gradient */}
            <div style={{
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                padding: '32px',
                borderRadius: '12px',
                boxShadow: '0 4px 20px rgba(0,0,0,0.12)',
                color: 'white',
                marginBottom: '24px'
            }}>
                <div>
                    <div style={{ marginBottom: '12px', opacity: '0.9' }}>
                        <a
                            href="#"
                            onClick={(e) => { e.preventDefault(); navigate('/'); }}
                            style={{ color: 'white', textDecoration: 'none', fontSize: '0.9rem' }}
                        >
                            <i className="bi bi-house-door me-2"></i>Home
                        </a>
                        <span className="mx-2">/</span>
                        <a
                            href="#"
                            onClick={(e) => { e.preventDefault(); navigate('/trades'); }}
                            style={{ color: 'white', textDecoration: 'none', fontSize: '0.9rem' }}
                        >
                            Trades
                        </a>
                        <span className="mx-2">/</span>
                        <span style={{ fontSize: '0.9rem' }}>{isEdit ? "Edit Trade" : "Create Trade"}</span>
                    </div>
                    <h1 style={{ fontSize: '2rem', fontWeight: '700', marginBottom: '0' }}>
                        <i className={`bi ${isEdit ? 'bi-pencil-square' : 'bi-plus-circle'} me-3`}></i>
                        {isEdit ? "Edit Trade" : "Create Trade"}
                    </h1>
                </div>
            </div>

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
                {/* Transaction Type Selector */}
                <div className="card border-0 shadow-sm mb-4" style={{ borderRadius: '12px' }}>
                    <div className="card-body" style={{ padding: '24px' }}>
                        <div className="row">
                            <div className="col-md-12">
                                <label className="form-label fw-bold">Transaction Type <span className="text-danger">*</span></label>
                                <div className="d-flex gap-4 flex-wrap">
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
                                    <div className="form-check">
                                        <input
                                            className="form-check-input"
                                            type="radio"
                                            name="direction"
                                            id="directionCommissionPurchase"
                                            value="COMMISSION_PURCHASE"
                                            checked={formData.direction === "COMMISSION_PURCHASE"}
                                            onChange={(e) => setFormData(prev => ({ ...prev, direction: e.target.value }))}
                                        />
                                        <label className="form-check-label" htmlFor="directionCommissionPurchase">
                                            Commission Purchase
                                        </label>
                                    </div>
                                    <div className="form-check">
                                        <input
                                            className="form-check-input"
                                            type="radio"
                                            name="direction"
                                            id="directionCommissionSale"
                                            value="COMMISSION_SALE"
                                            checked={formData.direction === "COMMISSION_SALE"}
                                            onChange={(e) => setFormData(prev => ({ ...prev, direction: e.target.value }))}
                                        />
                                        <label className="form-check-label" htmlFor="directionCommissionSale">
                                            Commission Sale
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
                                <h6>From Company Snapshot</h6>

                                <div className="mb-3">
                                    <label className="form-label">From Company <span className="text-danger">*</span></label>
                                    <HybridSelect
                                        fieldMeta={{
                                            endpoint: "/masters/companies/",
                                            label_field: "name"
                                        }}
                                        value={formData.from_company}
                                        onChange={handleFromCompanyChange}
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
                                <h6>To Company Snapshot</h6>

                                <div className="mb-3">
                                    <label className="form-label">To Company <span className="text-danger">*</span></label>
                                    <HybridSelect
                                        fieldMeta={{
                                            endpoint: "/masters/companies/",
                                            label_field: "name"
                                        }}
                                        value={formData.to_company}
                                        onChange={handleToCompanyChange}
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
                        <div className="d-flex justify-content-between align-items-center mb-2">
                            <label className="form-label mb-0">Invoice Number (optional)</label>
                            <button
                                type="button"
                                className="btn btn-warning btn-sm"
                                onClick={handlePrefillInvoiceNumber}
                                disabled={
                                    !formData.direction ||
                                    ((formData.direction === 'PURCHASE' || formData.direction === 'COMMISSION_PURCHASE') && !formData.to_company) ||
                                    ((formData.direction === 'SALE' || formData.direction === 'COMMISSION_SALE') && !formData.from_company)
                                }
                                title={
                                    !formData.direction
                                        ? "Select Transaction Type first"
                                        : ((formData.direction === 'PURCHASE' || formData.direction === 'COMMISSION_PURCHASE') && !formData.to_company)
                                            ? "Select To Company (buyer) for PURCHASE/COMMISSION_PURCHASE invoice"
                                            : ((formData.direction === 'SALE' || formData.direction === 'COMMISSION_SALE') && !formData.from_company)
                                                ? "Select From Company (seller) for SALE/COMMISSION_SALE invoice"
                                                : formData.direction === 'PURCHASE'
                                                    ? "Generate invoice number: P-PREFIX/FY/NNNN"
                                                    : formData.direction === 'SALE'
                                                        ? "Generate invoice number: PREFIX/FY/NNNN"
                                                        : formData.direction === 'COMMISSION_PURCHASE'
                                                            ? "Generate invoice number: COM-P-PREFIX/FY/NNNN"
                                                            : "Generate invoice number: COM-PREFIX/FY/NNNN"
                                }
                            >
                                <i className="bi bi-magic me-1"></i>
                                Prefill Invoice Number
                            </button>
                        </div>
                        <input
                            type="text"
                            className="form-control"
                            value={formData.invoice_number || ""}
                            onChange={(e) => setFormData(prev => ({ ...prev, invoice_number: e.target.value }))}
                        />
                    </div>
                    <div className="col-md-6">
                        <label className="form-label">Invoice Date</label>
                        <DatePicker
                            selected={formData.invoice_date instanceof Date ? formData.invoice_date : new Date(formData.invoice_date)}
                            onChange={(date) => setFormData(prev => ({ ...prev, invoice_date: date }))}
                            dateFormat="dd-MM-yyyy"
                            className="form-control"
                        />
                    </div>
                </div>

                {/* Purchase Invoice Copy Upload - Only for PURCHASE direction */}
                {formData.direction === "PURCHASE" && (
                    <div className="row mb-3">
                        <div className="col-md-6">
                            <label className="form-label">Purchase Invoice Copy (optional)</label>
                            <input
                                type="file"
                                className="form-control"
                                accept=".pdf,.jpg,.jpeg,.png"
                                onChange={(e) => {
                                    const file = e.target.files?.[0];
                                    setFormData(prev => ({ ...prev, purchase_invoice_copy: file || null }));
                                }}
                            />
                            <small className="text-muted">Accepted formats: PDF, JPG, PNG (Max 10MB)</small>

                            {/* Show existing file if editing and file exists */}
                            {isEdit && formData.purchase_invoice_copy && typeof formData.purchase_invoice_copy === 'string' && (
                                <div className="mt-2">
                                    <a
                                        href={formData.purchase_invoice_copy}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="btn btn-sm btn-primary text-white"
                                    >
                                        <i className="bi bi-file-earmark-pdf me-1"></i>
                                        View Current Invoice Copy
                                    </a>
                                    <button
                                        type="button"
                                        className="btn btn-sm btn-outline-danger ms-2"
                                        onClick={() => setFormData(prev => ({ ...prev, purchase_invoice_copy: null }))}
                                    >
                                        <i className="bi bi-trash me-1"></i>
                                        Remove
                                    </button>
                                </div>
                            )}

                            {/* Show selected file name if new file selected */}
                            {formData.purchase_invoice_copy instanceof File && (
                                <div className="mt-2">
                                    <span className="badge bg-success">
                                        <i className="bi bi-check-circle me-1"></i>
                                        {formData.purchase_invoice_copy.name}
                                    </span>
                                </div>
                            )}
                        </div>
                    </div>
                )}


                {/* BOE and Remarks */}
                <div className="row mb-4">
                    {formData.direction !== 'PURCHASE' && (
                        <div className="col-md-6">
                            <label className="form-label">BOE (optional)</label>
                            <HybridSelect
                                fieldMeta={{
                                    endpoint: (() => {
                                        // In create mode: only show BOEs without invoice
                                        if (!isEdit) {
                                            return "/bill-of-entries/?invoice_no__isnull=true";
                                        }
                                        // In edit mode: show BOEs without invoice OR current BOE OR BOEs with current invoice
                                        const currentBoeId = formData.boe ? (typeof formData.boe === 'object' ? formData.boe.id : formData.boe) : null;
                                        const currentInvoice = formData.invoice_number ? encodeURIComponent(formData.invoice_number) : null;

                                        let endpoint = "/bill-of-entries/?available_for_trade=true";
                                        if (currentBoeId) {
                                            endpoint += `&current_boe=${currentBoeId}`;
                                        }
                                        if (currentInvoice) {
                                            endpoint += `&current_invoice=${currentInvoice}`;
                                        }
                                        return endpoint;
                                    })(),
                                    label_field: "bill_of_entry_number"
                                }}
                                value={formData.boe}
                                onChange={(val) => setFormData(prev => ({ ...prev, boe: val }))}
                                isClearable={true}
                                placeholder="Search and select BOE (without invoice)..."
                            />
                        </div>
                    )}
                    <div className={formData.direction === 'PURCHASE' ? 'col-md-12' : 'col-md-6'}>
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

                {/* License Type - Placed before Billing Mode */}
                <div className="card mb-4">
                    <div className="card-body">
                        <div className="row">
                            <div className="col-md-12">
                                <label className="form-label fw-bold">License Type <span className="text-danger">*</span></label>
                                <div className="d-flex gap-4">
                                    <div className="form-check">
                                        <input
                                            className="form-check-input"
                                            type="radio"
                                            name="license_type"
                                            id="licenseTypeDFIA"
                                            value="DFIA"
                                            checked={formData.license_type === "DFIA"}
                                            onChange={(e) => setFormData(prev => ({
                                                ...prev,
                                                license_type: e.target.value,
                                                incentive_license: null // Clear incentive license when switching to DFIA
                                            }))}
                                        />
                                        <label className="form-check-label" htmlFor="licenseTypeDFIA">
                                            DFIA License
                                        </label>
                                    </div>
                                    <div className="form-check">
                                        <input
                                            className="form-check-input"
                                            type="radio"
                                            name="license_type"
                                            id="licenseTypeIncentive"
                                            value="INCENTIVE"
                                            checked={formData.license_type === "INCENTIVE"}
                                            onChange={(e) => setFormData(prev => ({ ...prev, license_type: e.target.value }))}
                                        />
                                        <label className="form-check-label" htmlFor="licenseTypeIncentive">
                                            Incentive License (RODTEP/ROSTL/MEIS)
                                        </label>
                                    </div>
                                </div>
                            </div>
                        </div>

                    </div>
                </div>

                {/* Conditional rendering based on license type */}
                {formData.license_type === "DFIA" && (
                    <>
                        {/* Billing Mode - Only for DFIA */}
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

                        {/* Trade Lines Table - For DFIA */}
                        <div className="table-responsive mb-3">
                    <table className="table table-bordered table-sm">
                        <thead className="table-light">
                            <tr>
                                <th style={{ width: "3%" }}>#</th>
                                <th style={{ width: "20%" }}>License (SR)</th>
                                <th style={{ width: "10%" }}>HSN</th>
                                <th style={{ width: "10%" }}>CIF $</th>
                                {billingMode === "CIF_INR" && (
                                    <>
                                        <th style={{ width: "8%" }}>Exch Rate</th>
                                        <th style={{ width: "10%" }}>CIF INR</th>
                                    </>
                                )}
                                {billingMode === "FOB_INR" && (
                                    <th style={{ width: "10%" }}>FOB INR</th>
                                )}
                                {billingMode === "QTY" && (
                                    <>
                                        <th style={{ width: "10%" }}>Qty (KG)</th>
                                        <th style={{ width: "10%" }}>Rate (INR/KG)</th>
                                    </>
                                )}
                                {billingMode !== "QTY" && <th style={{ width: "8%" }}>Billing %</th>}
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
                                            formatLabel={(option) =>
                                                option.label || `SR ${option.sr_number || option.id}`
                                            }
                                        />
                                    </td>
                                    <td>
                                        <input
                                            type="text"
                                            className="form-control form-control-sm"
                                            value="49070000"
                                            readOnly
                                        />
                                    </td>
                                    <td>
                                        <input
                                            type="number"
                                            className="form-control form-control-sm text-end"
                                            value={line.cif_fc || ""}
                                            onChange={(e) => handleLineChange(index, 'cif_fc', parseFloat(e.target.value) || 0)}
                                            step="0.01"
                                        />
                                    </td>
                                    {billingMode === "CIF_INR" && (
                                        <>
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
                                    {billingMode === "FOB_INR" && (
                                        <td>
                                            <input
                                                type="number"
                                                className="form-control form-control-sm text-end"
                                                value={line.fob_inr || ""}
                                                onChange={(e) => handleLineChange(index, 'fob_inr', parseFloat(e.target.value) || 0)}
                                                step="0.01"
                                            />
                                        </td>
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
                                    {billingMode !== "QTY" && (
                                        <td>
                                            <input
                                                type="number"
                                                className="form-control form-control-sm text-end"
                                                value={line.pct || ""}
                                                onChange={(e) => handleLineChange(index, 'pct', parseFloat(e.target.value) || 0)}
                                                step="0.001"
                                            />
                                        </td>
                                    )}
                                    <td>
                                        <input
                                            type="number"
                                            step="0.01"
                                            className="form-control form-control-sm text-end fw-bold"
                                            value={line.amount_inr || ""}
                                            onChange={(e) => handleLineChange(index, 'amount_inr', e.target.value)}
                                            placeholder="0.00"
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
                                <td colSpan={billingMode === "QTY" ? 6 : (billingMode === "CIF_INR" ? 6 : 5)} className="text-end">Total</td>
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
                    </>
                )}

                {/* Incentive License Lines Table - Only for INCENTIVE */}
                {formData.license_type === "INCENTIVE" && (
                    <>
                        <div className="table-responsive mb-3">
                            <table className="table table-bordered table-sm">
                                <thead className="table-light">
                                    <tr>
                                        <th style={{ width: "5%" }}>#</th>
                                        <th style={{ width: "40%" }}>Incentive License</th>
                                        <th style={{ width: "20%" }}>License Value (INR)</th>
                                        <th style={{ width: "15%" }}>Rate (%)</th>
                                        <th style={{ width: "15%" }}>Amount</th>
                                        <th style={{ width: "5%" }}></th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {formData.incentive_lines.map((line, index) => (
                                        <tr key={index}>
                                            <td className="text-center">{index + 1}</td>
                                            <td>
                                                <HybridSelect
                                                    fieldMeta={{
                                                        endpoint: "/incentive-licenses/",
                                                        label_field: "license_number"
                                                    }}
                                                    value={line.incentive_license}
                                                    onChange={(val) => handleIncentiveLineChange(index, 'incentive_license', val)}
                                                    isClearable={true}
                                                    placeholder="Select Incentive License..."
                                                    formatLabel={(option) =>
                                                        `${option.license_type} - ${option.license_number} (${option.exporter_name || 'N/A'})`
                                                    }
                                                />
                                            </td>
                                            <td>
                                                <input
                                                    type="number"
                                                    className="form-control form-control-sm text-end"
                                                    value={line.license_value || ""}
                                                    onChange={(e) => handleIncentiveLineChange(index, 'license_value', parseFloat(e.target.value) || 0)}
                                                    step="0.01"
                                                    placeholder="0.00"
                                                />
                                            </td>
                                            <td>
                                                <input
                                                    type="number"
                                                    className="form-control form-control-sm text-end"
                                                    value={line.rate_pct || ""}
                                                    onChange={(e) => handleIncentiveLineChange(index, 'rate_pct', parseFloat(e.target.value) || 0)}
                                                    step="0.001"
                                                    placeholder="0.000"
                                                />
                                            </td>
                                            <td>
                                                <input
                                                    type="number"
                                                    step="0.01"
                                                    className="form-control form-control-sm text-end fw-bold"
                                                    value={line.amount_inr || ""}
                                                    onChange={(e) => handleIncentiveLineChange(index, 'amount_inr', e.target.value)}
                                                    placeholder="0.00"
                                                />
                                            </td>
                                            <td className="text-center">
                                                <button
                                                    type="button"
                                                    className="btn btn-danger btn-sm"
                                                    onClick={() => handleRemoveIncentiveLine(index)}
                                                >
                                                    <i className="bi bi-trash"></i>
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                    <tr className="table-secondary fw-bold">
                                        <td colSpan={4} className="text-end">Total</td>
                                        <td className="text-end">{calculateTotal().toFixed(2)}</td>
                                        <td></td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>

                        <button
                            type="button"
                            className="btn btn-warning mb-4"
                            onClick={handleAddIncentiveLine}
                        >
                            Add Row
                        </button>
                    </>
                )}

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
                        <>
                            <button
                                type="button"
                                className="btn btn-info"
                                onClick={() => setShowTransferLetterModal(true)}
                                title="Generate Transfer Letter"
                            >
                                <i className="bi bi-file-earmark-text me-1"></i>
                                Generate Transfer Letter
                            </button>
                            {formData.direction === 'SALE' && (
                                <div className="btn-group">
                                    <button
                                        type="button"
                                        className="btn btn-warning"
                                        onClick={() => handleDownloadPDF(true)}
                                        title="Download Bill of Supply with signature & stamp"
                                    >
                                        <i className="bi bi-file-pdf me-1"></i>
                                        Bill of Supply
                                    </button>
                                    <button
                                        type="button"
                                        className="btn btn-warning dropdown-toggle dropdown-toggle-split"
                                        data-bs-toggle="dropdown"
                                        aria-expanded="false"
                                    >
                                        <span className="visually-hidden">Toggle Dropdown</span>
                                    </button>
                                    <ul className="dropdown-menu">
                                        <li>
                                            <a
                                                className="dropdown-item"
                                                href="#"
                                                onClick={(e) => {
                                                    e.preventDefault();
                                                    handleDownloadPDF(true);
                                                }}
                                            >
                                                <i className="bi bi-check-circle me-2"></i>
                                                With Signature & Stamp
                                            </a>
                                        </li>
                                        <li>
                                            <a
                                                className="dropdown-item"
                                                href="#"
                                                onClick={(e) => {
                                                    e.preventDefault();
                                                    handleDownloadPDF(false);
                                                }}
                                            >
                                                <i className="bi bi-x-circle me-2"></i>
                                                Without Signature & Stamp
                                            </a>
                                        </li>
                                    </ul>
                                </div>
                            )}
                            {formData.direction === 'PURCHASE' && (
                                <div className="btn-group">
                                    <button
                                        type="button"
                                        className="btn btn-success"
                                        onClick={() => handleDownloadPurchaseInvoice(true)}
                                        title="Download Purchase Invoice with signature & stamp"
                                    >
                                        <i className="bi bi-file-pdf me-1"></i>
                                        Purchase Invoice
                                    </button>
                                    <button
                                        type="button"
                                        className="btn btn-success dropdown-toggle dropdown-toggle-split"
                                        data-bs-toggle="dropdown"
                                        aria-expanded="false"
                                    >
                                        <span className="visually-hidden">Toggle Dropdown</span>
                                    </button>
                                    <ul className="dropdown-menu">
                                        <li>
                                            <a
                                                className="dropdown-item"
                                                href="#"
                                                onClick={(e) => {
                                                    e.preventDefault();
                                                    handleDownloadPurchaseInvoice(true);
                                                }}
                                            >
                                                <i className="bi bi-check-circle me-2"></i>
                                                With Signature & Stamp
                                            </a>
                                        </li>
                                        {formData.purchase_invoice_copy && typeof formData.purchase_invoice_copy === 'string' && (
                                            <li>
                                                <a
                                                    className="dropdown-item"
                                                    href={formData.purchase_invoice_copy}
                                                    target="_blank"
                                                    rel="noopener noreferrer"
                                                >
                                                    <i className="bi bi-file-earmark-pdf me-2"></i>
                                                    Original Invoice Copy
                                                </a>
                                            </li>
                                        )}
                                    </ul>
                                </div>
                            )}
                        </>
                    )}
                </div>
            </form>

            {/* Transfer Letter Modal */}
            {isEdit && showTransferLetterModal && (
                <TransferLetterModal
                    show={showTransferLetterModal}
                    onHide={() => setShowTransferLetterModal(false)}
                    type="trade"
                    entityId={id}
                />
            )}
        </div>
    );
}
