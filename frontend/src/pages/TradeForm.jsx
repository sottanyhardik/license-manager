import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { toast } from 'react-toastify';
import api from "../api/axios";
import HybridSelect from "../components/HybridSelect";
import ConditionBadge from "../components/ConditionBadge";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import {formatDateForInput, parseDate} from "../utils/dateFormatter";
import * as validateFormUtil from "../utils/formValidation";
import { ValidationRules } from "../utils/formValidation";
import TransferLetterModal from "../components/TransferLetterModal";
import {navigateToList} from "../utils/navigationUtils";
import {useBackButton} from "../hooks/useBackButton";

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
    const [autoCreatePaired, setAutoCreatePaired] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");
    const [fieldErrors, setFieldErrors] = useState({});
    const [showTransferLetterModal, setShowTransferLetterModal] = useState(false);
    const isInitialLoadRef = useRef(true);
    const [initialFormData, setInitialFormData] = useState(null);
    const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

    // Enable browser back button support with filter preservation
    useBackButton('trades');

    // Track unsaved changes
    useEffect(() => {
        if (initialFormData) {
            const hasChanges = JSON.stringify(formData) !== JSON.stringify(initialFormData);
            setHasUnsavedChanges(hasChanges);
        }
    }, [formData, initialFormData]);

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

        // Only prefill if lines are empty (for create mode or when explicitly requested)
        // Don't auto-prefill in edit mode if lines already exist
        if (formData.lines && formData.lines.length > 0) {
            return;
        }

        // Show loading state
        const loadingToastId = toast.loading("Loading BOE details...");

        try {
            // boe can be either ID or object with id
            const boeId = typeof formData.boe === 'object' ? formData.boe.id : formData.boe;
            const { data } = await api.get(`bill-of-entries/${boeId}/`);

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

            toast.update(loadingToastId, {
                render: "BOE details loaded successfully",
                type: "success",
                isLoading: false,
                autoClose: 2000
            });
        } catch (err) {
            toast.update(loadingToastId, {
                render: "Failed to fetch BOE details",
                type: "error",
                isLoading: false,
                autoClose: 3000
            });
        }
    }, [formData.boe, formData.lines, billingMode]);

    const formDataRef = useRef(formData);
    formDataRef.current = formData;

    const fetchTrade = useCallback(async () => {
        try {
            const { data } = await api.get(`trades/${id}/`);

            // Parse date fields using centralized date parser
            if (data.invoice_date) {
                data.invoice_date = parseDate(data.invoice_date) || new Date();
            }

            // Parse payment dates
            if (data.payments) {
                data.payments = data.payments.map(payment => ({
                    ...payment,
                    date: payment.date ? parseDate(payment.date) || new Date() : new Date()
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
                                const { data: licenseData } = await api.get(`incentive-licenses/${line.incentive_license}/`);
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
            setInitialFormData(JSON.parse(JSON.stringify(data))); // Deep clone for initial snapshot

            // Set billing mode from first line if exists
            if (data.lines && data.lines.length > 0) {
                setBillingMode(data.lines[0].mode);
            }

            // Mark initial load as complete to enable BOE auto-prefill
            isInitialLoadRef.current = false;
        } catch (err) {
            setError("Failed to load trade");
        }
    }, [id]);

    // Fetch existing trade if editing
    useEffect(() => {
        if (isEdit) {
            fetchTrade();
        } else {
            isInitialLoadRef.current = false;
            setInitialFormData(JSON.parse(JSON.stringify(formDataRef.current)));
        }
    }, [isEdit, id, fetchTrade]);

    // Auto-prefill from BOE when BOE is selected (only if lines are empty)
    useEffect(() => {
        if (formData.boe) {
            handlePrefillFromBOE();
        }
    // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [formData.boe]);

    const handleFromCompanyChange = async (val) => {
        setFormData(prev => ({ ...prev, from_company: val }));

        // Auto-fetch company details
        if (val) {
            try {
                const companyId = typeof val === 'object' ? val.id : val;
                const { data } = await api.get(`masters/companies/${companyId}/`);
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
                const { data } = await api.get(`masters/companies/${companyId}/`);
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
            const { data } = await api.get(`trades/prefill-invoice-number/`, {
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
            try {
                const { data } = await api.get(`incentive-licenses/${value}/`);
                line.license_value = parseFloat(data.license_value) || 0;

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

    // Validation function for trade form
    const validateTradeForm = () => {
        const errors = {};

        // Basic field validation
        const basicSchema = {
            direction: { rules: [ValidationRules.REQUIRED], label: 'Direction' },
            invoice_date: { rules: [ValidationRules.REQUIRED, ValidationRules.DATE], label: 'Invoice Date' }
        };

        // Validate based on direction
        if (formData.direction === 'PURCHASE') {
            basicSchema.from_company = { rules: [ValidationRules.REQUIRED], label: 'From Company' };
        } else if (formData.direction === 'SALE') {
            basicSchema.to_company = { rules: [ValidationRules.REQUIRED], label: 'To Company' };
        }

        // Validate basic fields
        Object.keys(basicSchema).forEach(field => {
            const config = basicSchema[field];
            const value = formData[field];
            const fieldErrors = validateFormUtil.validateField(value, config.rules, config.label);
            if (fieldErrors.length > 0) {
                errors[field] = fieldErrors;
            }
        });

        // Validate lines
        if (formData.lines.length === 0 && formData.incentive_lines.length === 0) {
            errors.lines = ['At least one trade line or incentive line must be added'];
        }

        // Validate trade lines
        if (formData.lines.length > 0) {
            const lineSchema = {
                sr_number: { rules: [ValidationRules.REQUIRED], label: 'License Item' },
                amount_inr: { rules: [ValidationRules.REQUIRED, ValidationRules.NON_NEGATIVE], label: 'Amount (INR)' }
            };
            const lineErrors = validateFormUtil.validateNestedArray(formData.lines, lineSchema);
            if (lineErrors.length > 0) {
                errors.lines = lineErrors;
            }
        }

        // Validate payments
        if (formData.payments && formData.payments.length > 0) {
            const paymentSchema = {
                amount: { rules: [ValidationRules.REQUIRED, ValidationRules.POSITIVE_NUMBER], label: 'Payment Amount' },
                mode: { rules: [ValidationRules.REQUIRED], label: 'Payment Mode' },
                date: { rules: [ValidationRules.REQUIRED, ValidationRules.DATE], label: 'Payment Date' }
            };
            const paymentErrors = validateFormUtil.validateNestedArray(formData.payments, paymentSchema);
            if (paymentErrors.length > 0) {
                errors.payments = paymentErrors;
            }
        }

        return errors;
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSaving(true);
        setError("");
        setFieldErrors({});

        // Frontend validation
        const validationErrors = validateTradeForm();
        if (Object.keys(validationErrors).length > 0) {
            setFieldErrors(validationErrors);

            // Create detailed error message
            const errorDetails = [];
            Object.entries(validationErrors).forEach(([field, errors]) => {
                if (Array.isArray(errors)) {
                    if (typeof errors[0] === 'string') {
                        errorDetails.push(`${field}: ${errors.join(', ')}`);
                    } else {
                        // Nested array errors (like line items)
                        errors.forEach((lineError, index) => {
                            if (lineError && typeof lineError === 'object') {
                                Object.entries(lineError).forEach(([lineField, lineErrors]) => {
                                    errorDetails.push(`Line ${index + 1} - ${lineField}: ${lineErrors.join(', ')}`);
                                });
                            }
                        });
                    }
                } else if (typeof errors === 'object') {
                    Object.entries(errors).forEach(([subField, subErrors]) => {
                        errorDetails.push(`${field}.${subField}: ${subErrors}`);
                    });
                }
            });

            const detailedErrorMsg = "Validation errors:\n" + errorDetails.join('\n');
            setError(detailedErrorMsg);

            // Show first few errors in toast
            errorDetails.slice(0, 3).forEach(err => toast.error(err));
            if (errorDetails.length > 3) {
                toast.error(`And ${errorDetails.length - 3} more errors...`);
            }

            // Scroll to first error
            setTimeout(() => {
                const firstErrorField = document.querySelector('.is-invalid');
                if (firstErrorField) {
                    firstErrorField.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    firstErrorField.focus();
                }
            }, 100);

            setSaving(false);
            return;
        }

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
                formDataObj.append('license_type', formData.license_type);
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

                // Add lines as JSON string (clean up empty id fields and extract sr_number ID)
                const cleanedLines = formData.lines.map(line => {
                    const cleanedLine = {...line};
                    if (cleanedLine.id === '' || cleanedLine.id === null || cleanedLine.id === undefined) {
                        delete cleanedLine.id;
                    }
                    // Extract sr_number ID if it's an object
                    if (cleanedLine.sr_number && typeof cleanedLine.sr_number === 'object') {
                        cleanedLine.sr_number = cleanedLine.sr_number.id;
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

                // Clean up lines: remove empty id fields and extract sr_number ID
                const cleanedLines = formData.lines.map(line => {
                    const cleanedLine = {...line};
                    if (cleanedLine.id === '' || cleanedLine.id === null || cleanedLine.id === undefined) {
                        delete cleanedLine.id;
                    }
                    // Extract sr_number ID if it's an object
                    if (cleanedLine.sr_number && typeof cleanedLine.sr_number === 'object') {
                        cleanedLine.sr_number = cleanedLine.sr_number.id;
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
                    // Only include writable fields, not read-only display fields
                    direction: formData.direction,
                    license_type: formData.license_type,
                    from_company: fromCompanyId,
                    to_company: toCompanyId,
                    boe: boeId || null,
                    invoice_number: formData.invoice_number?.trim() || '',
                    invoice_date: formatDateForAPI(formData.invoice_date),
                    remarks: formData.remarks || '',
                    // Company snapshot fields
                    from_pan: formData.from_pan || '',
                    from_gst: formData.from_gst || '',
                    from_addr_line_1: formData.from_addr_line_1 || '',
                    from_addr_line_2: formData.from_addr_line_2 || '',
                    to_pan: formData.to_pan || '',
                    to_gst: formData.to_gst || '',
                    to_addr_line_1: formData.to_addr_line_1 || '',
                    to_addr_line_2: formData.to_addr_line_2 || '',
                    // Nested data
                    lines: cleanedLines,
                    incentive_lines: cleanedIncentiveLines,
                    payments: cleanedPayments,
                    auto_create_paired: autoCreatePaired,
                };
            }

            if (isEdit) {
                await api.patch(`trades/${id}/`, payload, { headers });
            } else {
                await api.post(`trades/`, payload, { headers });
            }

            const successMsg = isEdit
                ? "Trade updated successfully"
                : autoCreatePaired
                    ? `Trade created! Linked ${formData.direction === 'PURCHASE' ? 'Sale' : 'Purchase'} trade also created automatically.`
                    : "Trade created successfully";
            toast.success(successMsg);
            setHasUnsavedChanges(false); // Clear unsaved changes flag
            navigate("/trades");
        } catch (err) {
            console.error('Save error:', err.response?.data);

            // Handle field-level errors with improved formatting
            if (err.response?.data && typeof err.response.data === 'object') {
                const formattedErrors = validateFormUtil.formatBackendErrors(err.response.data);
                setFieldErrors(formattedErrors);

                // Create user-friendly error message
                const errorMessages = [];
                Object.entries(err.response.data).forEach(([field, errors]) => {
                    if (Array.isArray(errors)) {
                        errors.forEach(error => {
                            // Make field name more readable
                            const fieldLabel = field === 'non_field_errors'
                                ? 'Error'
                                : field.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
                            errorMessages.push(`${fieldLabel}: ${error}`);
                        });
                    } else {
                        const fieldLabel = field === 'non_field_errors'
                            ? 'Error'
                            : field.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());
                        errorMessages.push(`${fieldLabel}: ${errors}`);
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
            const response = await api.get(`trades/${id}/generate-bill-of-supply/`, {
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
            const response = await api.get(`trades/${id}/generate-purchase-invoice/`, {
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

    const directionMeta = {
        PURCHASE:           { label: 'Purchase',            icon: 'cart-check',   color: '#4F46E5' },
        SALE:               { label: 'Sale',                icon: 'shop',         color: '#10b981' },
        COMMISSION_PURCHASE:{ label: 'Commission Purchase', icon: 'percent',      color: '#f59e0b' },
        COMMISSION_SALE:    { label: 'Commission Sale',     icon: 'graph-up',     color: '#6366F1' },
    };

    return (
        <div className="container-fluid" style={{ backgroundColor: 'var(--bs-gray-50)', minHeight: '100vh', padding: '20px 24px' }}>
            {/* Compact Header */}
            <div className="d-flex justify-content-between align-items-center flex-wrap gap-2 mb-4">
                <div>
                    <h4 className="mb-0 fw-bold" style={{ color: 'var(--text-dark)' }}>
                        <i className="bi bi-arrow-left-right me-2" style={{ color: '#10b981' }}></i>
                        {isEdit ? 'Edit Trade' : 'New Trade'}
                    </h4>
                    <small className="text-muted">
                        {isEdit ? 'Update trade details' : 'Create a new trade transaction'}
                        {formData.direction && (
                            <span className="ms-2 badge" style={{ background: `${directionMeta[formData.direction]?.color}20`, color: directionMeta[formData.direction]?.color, fontSize: '0.75rem' }}>
                                <i className={`bi bi-${directionMeta[formData.direction]?.icon} me-1`}></i>
                                {directionMeta[formData.direction]?.label}
                            </span>
                        )}
                    </small>
                </div>
                <div className="d-flex gap-2">
                    {isEdit && (
                        <button type="button" className="btn btn-sm btn-outline-secondary"
                            onClick={() => setShowTransferLetterModal(true)}>
                            <i className="bi bi-file-earmark-text me-1"></i>Transfer Letter
                        </button>
                    )}
                    <button type="button" className="btn btn-sm btn-outline-secondary"
                        onClick={() => navigateToList(navigate, 'trades', { preserveFilters: true })}>
                        <i className="bi bi-arrow-left me-1"></i>Back to Trades
                    </button>
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
                {/* Transaction Type + License Type — combined card */}
                <div className="card border-0 shadow-sm mb-4" style={{ borderRadius: '12px' }}>
                    <div className="card-header bg-white border-bottom py-3" style={{ borderRadius: '12px 12px 0 0' }}>
                        <h6 className="mb-0 fw-semibold">
                            <i className="bi bi-toggles me-2" style={{ color: '#10b981' }}></i>
                            Trade Configuration
                        </h6>
                    </div>
                    <div className="card-body p-4">
                        <div className="row g-4">
                            <div className="col-md-6">
                                <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: 8 }}>
                                    TRANSACTION TYPE <span className="text-danger">*</span>
                                </label>
                                <div className="d-flex gap-2 flex-wrap">
                                    {Object.entries(directionMeta).map(([val, m]) => (
                                        <button key={val} type="button"
                                            onClick={() => setFormData(prev => ({ ...prev, direction: val }))}
                                            style={{
                                                border: `2px solid ${formData.direction === val ? m.color : '#e5e7eb'}`,
                                                background: formData.direction === val ? `${m.color}18` : 'white',
                                                color: formData.direction === val ? m.color : '#6b7280',
                                                borderRadius: '8px', padding: '8px 14px',
                                                fontWeight: formData.direction === val ? '600' : '500',
                                                fontSize: '0.83rem', cursor: 'pointer', transition: 'all 0.15s',
                                            }}>
                                            <i className={`bi bi-${m.icon} me-1`}></i>{m.label}
                                        </button>
                                    ))}
                                </div>
                            </div>
                            <div className="col-md-6">
                                <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: 8 }}>
                                    LICENSE TYPE <span className="text-danger">*</span>
                                </label>
                                <div className="d-flex gap-2">
                                    {[{ val:'DFIA', label:'DFIA License', icon:'file-earmark-text', color:'#4F46E5' },
                                      { val:'INCENTIVE', label:'Incentive License', icon:'award', color:'#f59e0b' }].map(m => (
                                        <button key={m.val} type="button"
                                            onClick={() => setFormData(prev => ({ ...prev, license_type: m.val, incentive_license: m.val === 'DFIA' ? null : prev.incentive_license }))}
                                            style={{
                                                border: `2px solid ${formData.license_type === m.val ? m.color : '#e5e7eb'}`,
                                                background: formData.license_type === m.val ? `${m.color}18` : 'white',
                                                color: formData.license_type === m.val ? m.color : '#6b7280',
                                                borderRadius: '8px', padding: '8px 16px',
                                                fontWeight: formData.license_type === m.val ? '600' : '500',
                                                fontSize: '0.83rem', cursor: 'pointer', transition: 'all 0.15s',
                                            }}>
                                            <i className={`bi bi-${m.icon} me-1`}></i>{m.label}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </div>
                        {!id && ['PURCHASE', 'SALE'].includes(formData.direction) && (
                            <div className="d-flex align-items-center gap-2 mt-3 p-2 rounded" style={{ background: '#f0f9ff', border: '1px solid #bae6fd' }}>
                                <input
                                    type="checkbox"
                                    id="autoCreatePaired"
                                    checked={autoCreatePaired}
                                    onChange={e => setAutoCreatePaired(e.target.checked)}
                                    style={{ cursor: 'pointer' }}
                                />
                                <label htmlFor="autoCreatePaired" style={{ cursor: 'pointer', fontSize: '0.875rem', color: '#0369a1', marginBottom: 0 }}>
                                    <i className="bi bi-link-45deg me-1"></i>
                                    Auto-create linked {formData.direction === 'PURCHASE' ? 'Sale' : 'Purchase'} trade with same lines
                                </label>
                            </div>
                        )}
                    </div>
                </div>

                {/* Company Snapshots */}
                <div className="row mb-4">
                    {/* From Company */}
                    <div className="col-md-6">
                        <div className="card border-0 shadow-sm h-100" style={{ borderRadius: '12px' }}>
                            <div className="card-header bg-white border-bottom py-3" style={{ borderRadius: '12px 12px 0 0' }}>
                                <h6 className="mb-0 fw-semibold">
                                    <i className="bi bi-building me-2" style={{ color: '#4F46E5' }}></i>
                                    From Company
                                </h6>
                            </div>
                            <div className="card-body" style={{ padding: '20px' }}>

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
                        <div className="card border-0 shadow-sm h-100" style={{ borderRadius: '12px' }}>
                            <div className="card-header bg-white border-bottom py-3" style={{ borderRadius: '12px 12px 0 0' }}>
                                <h6 className="mb-0 fw-semibold">
                                    <i className="bi bi-building me-2" style={{ color: '#10b981' }}></i>
                                    To Company
                                </h6>
                            </div>
                            <div className="card-body" style={{ padding: '20px' }}>
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

                {/* Invoice Details + BOE/Remarks card */}
                <div className="card border-0 shadow-sm mb-4" style={{ borderRadius: '12px' }}>
                    <div className="card-header bg-white border-bottom py-3" style={{ borderRadius: '12px 12px 0 0' }}>
                        <h6 className="mb-0 fw-semibold">
                            <i className="bi bi-file-earmark-text me-2" style={{ color: '#f59e0b' }}></i>
                            Invoice & Reference Details
                        </h6>
                    </div>
                    <div className="card-body p-4">
                <div className="row mb-3">
                    <div className="col-md-6">
                        <div className="d-flex justify-content-between align-items-center mb-2">
                            <label className="form-label mb-0" style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-secondary)' }}>Invoice Number (optional)</label>
                            <button
                                type="button"
                                className="btn btn-outline-primary btn-sm"
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
                            selected={formData.invoice_date instanceof Date ? formData.invoice_date : parseDate(formData.invoice_date)}
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
                <div className="row mb-0">
                    {formData.direction !== 'PURCHASE' && (
                        <div className="col-md-6">
                            <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-secondary)' }}>BOE (optional)</label>
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
                        <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-secondary)' }}>Remarks</label>
                        <textarea
                            className="form-control"
                            rows="2"
                            value={formData.remarks || ""}
                            onChange={(e) => setFormData(prev => ({ ...prev, remarks: e.target.value }))}
                            placeholder="Enter any remarks..."
                        />
                    </div>
                </div>
                    </div>
                </div>

                {/* Conditional rendering based on license type */}
                {formData.license_type === "DFIA" && (
                    <>
                        {/* Billing Mode card */}
                        <div className="card border-0 shadow-sm mb-4" style={{ borderRadius: '12px' }}>
                            <div className="card-header bg-white border-bottom py-3" style={{ borderRadius: '12px 12px 0 0' }}>
                                <h6 className="mb-0 fw-semibold">
                                    <i className="bi bi-calculator me-2" style={{ color: '#6366F1' }}></i>
                                    Billing Mode
                                </h6>
                            </div>
                            <div className="card-body p-4">
                                <div className="d-flex gap-2 flex-wrap">
                                    {[{ val:'QTY', label:'By Quantity (KG × Rate)', icon:'weight' },
                                      { val:'CIF_INR', label:'By CIF INR (%)', icon:'currency-rupee' },
                                      { val:'FOB_INR', label:'By FOB INR (%)', icon:'box-seam' }].map(m => (
                                        <button key={m.val} type="button"
                                            onClick={() => {
                                                setBillingMode(m.val);
                                                setFormData(prev => ({ ...prev, lines: prev.lines.map(line => ({ ...line, mode: m.val })) }));
                                            }}
                                            style={{
                                                border: `2px solid ${billingMode === m.val ? '#6366F1' : '#e5e7eb'}`,
                                                background: billingMode === m.val ? '#6366F118' : 'white',
                                                color: billingMode === m.val ? '#6366F1' : '#6b7280',
                                                borderRadius: '8px', padding: '8px 18px',
                                                fontWeight: billingMode === m.val ? '600' : '500',
                                                fontSize: '0.83rem', cursor: 'pointer', transition: 'all 0.15s',
                                            }}>
                                            <i className={`bi bi-${m.icon} me-2`}></i>{m.label}
                                        </button>
                                    ))}
                                </div>
                            </div>
                        </div>

                        {/* Trade Lines */}
                        <div className="card border-0 shadow-sm mb-4" style={{ borderRadius: '12px' }}>
                            <div className="card-header bg-white border-bottom d-flex justify-content-between align-items-center py-3" style={{ borderRadius: '12px 12px 0 0' }}>
                                <h6 className="mb-0 fw-semibold">
                                    <i className="bi bi-list-ul me-2" style={{ color: '#4F46E5' }}></i>
                                    Trade Lines
                                    {formData.lines.length > 0 && (
                                        <span className="badge ms-2 rounded-pill" style={{ backgroundColor: '#e0e7ff', color: '#4F46E5', fontSize: '0.7rem' }}>
                                            {formData.lines.length}
                                        </span>
                                    )}
                                </h6>
                                <button type="button" className="btn btn-sm btn-outline-success"
                                    onClick={handleAddLine} style={{ borderRadius: '8px' }}>
                                    <i className="bi bi-plus-lg me-1"></i>Add Row
                                </button>
                            </div>
                            <div className="card-body p-0">
                        <div className="table-responsive">
                    <table className="table table-sm mb-0" style={{ fontSize: '0.83rem' }}>
                        <thead style={{ background: 'var(--bs-gray-50)', borderBottom: '2px solid #e5e7eb' }}>
                            <tr>
                                <th className="px-3 py-2 text-muted fw-semibold" style={{ width: "3%" }}>#</th>
                                <th className="px-3 py-2 text-muted fw-semibold" style={{ width: "22%" }}>License (SR)</th>
                                <th className="px-3 py-2 text-muted fw-semibold" style={{ width: "9%" }}>HSN</th>
                                <th className="px-3 py-2 text-muted fw-semibold" style={{ width: "9%" }}>CIF $</th>
                                {billingMode === "CIF_INR" && (
                                    <>
                                        <th className="px-3 py-2 text-muted fw-semibold" style={{ width: "8%" }}>Exch Rate</th>
                                        <th className="px-3 py-2 text-muted fw-semibold" style={{ width: "10%" }}>CIF INR</th>
                                    </>
                                )}
                                {billingMode === "FOB_INR" && (
                                    <th className="px-3 py-2 text-muted fw-semibold" style={{ width: "10%" }}>FOB INR</th>
                                )}
                                {billingMode === "QTY" && (
                                    <>
                                        <th className="px-3 py-2 text-muted fw-semibold" style={{ width: "10%" }}>Qty (KG)</th>
                                        <th className="px-3 py-2 text-muted fw-semibold" style={{ width: "10%" }}>Rate (INR/KG)</th>
                                    </>
                                )}
                                {billingMode !== "QTY" && <th className="px-3 py-2 text-muted fw-semibold" style={{ width: "8%" }}>Billing %</th>}
                                <th className="px-3 py-2 text-muted fw-semibold" style={{ width: "12%" }}>Amount</th>
                                <th style={{ width: "3%" }}></th>
                            </tr>
                        </thead>
                        <tbody>
                            {formData.lines.map((line, index) => (
                                <tr key={index}>
                                    <td className="text-center">
                                        {index + 1}
                                        <ConditionBadge type={line.condition_type} size="xs" />
                                    </td>
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
                                            formatLabel={(option) => (
                                                <>
                                                    {option.label || `SR ${option.sr_number || option.id}`}
                                                    {option.condition_type && (
                                                        <ConditionBadge type={option.condition_type} size="xs" />
                                                    )}
                                                </>
                                            )}
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
                                    <td className="text-center px-2">
                                        <button type="button" className="btn btn-sm btn-outline-danger"
                                            onClick={() => handleRemoveLine(index)} style={{ borderRadius: '6px', padding: '2px 8px' }}>
                                            <i className="bi bi-trash"></i>
                                        </button>
                                    </td>
                                </tr>
                            ))}
                            {formData.lines.length > 0 && (
                                <tr style={{ background: '#f0fdf4', borderTop: '2px solid #a7f3d0' }}>
                                    <td colSpan={billingMode === "QTY" ? 6 : (billingMode === "CIF_INR" ? 6 : 5)} className="text-end fw-semibold px-3 py-2" style={{ color: '#065f46' }}>Total Amount</td>
                                    <td className="text-end fw-bold px-3 py-2" style={{ color: '#065f46' }}>₹{calculateTotal().toFixed(2)}</td>
                                    <td></td>
                                </tr>
                            )}
                        </tbody>
                    </table>
                </div>
                </div>
                </div>
                {fieldErrors.lines && formData.lines.length === 0 && (
                    <div className="alert alert-danger py-2 px-3 mt-2 small">
                        <i className="bi bi-exclamation-circle me-1"></i>
                        {Array.isArray(fieldErrors.lines) ? fieldErrors.lines[0] : fieldErrors.lines}
                    </div>
                )}
                    </>
                )}

                {/* Incentive License Lines */}
                {formData.license_type === "INCENTIVE" && (
                    <>
                        <div className="card border-0 shadow-sm mb-4" style={{ borderRadius: '12px' }}>
                            <div className="card-header bg-white border-bottom d-flex justify-content-between align-items-center py-3" style={{ borderRadius: '12px 12px 0 0' }}>
                                <h6 className="mb-0 fw-semibold">
                                    <i className="bi bi-award me-2" style={{ color: '#f59e0b' }}></i>
                                    Incentive Lines
                                    {formData.incentive_lines.length > 0 && (
                                        <span className="badge ms-2 rounded-pill" style={{ backgroundColor: '#fef3c7', color: '#92400e', fontSize: '0.7rem' }}>
                                            {formData.incentive_lines.length}
                                        </span>
                                    )}
                                </h6>
                                <button type="button" className="btn btn-sm btn-outline-success"
                                    onClick={handleAddIncentiveLine} style={{ borderRadius: '8px' }}>
                                    <i className="bi bi-plus-lg me-1"></i>Add Row
                                </button>
                            </div>
                            <div className="card-body p-0">
                        <div className="table-responsive">
                            <table className="table table-sm mb-0" style={{ fontSize: '0.83rem' }}>
                                <thead style={{ background: 'var(--bs-gray-50)', borderBottom: '2px solid #e5e7eb' }}>
                                    <tr>
                                        <th className="px-3 py-2 text-muted fw-semibold" style={{ width: "5%" }}>#</th>
                                        <th className="px-3 py-2 text-muted fw-semibold" style={{ width: "40%" }}>Incentive License</th>
                                        <th className="px-3 py-2 text-muted fw-semibold" style={{ width: "20%" }}>License Value (INR)</th>
                                        <th className="px-3 py-2 text-muted fw-semibold" style={{ width: "15%" }}>Rate (%)</th>
                                        <th className="px-3 py-2 text-muted fw-semibold" style={{ width: "15%" }}>Amount</th>
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
                                    {formData.incentive_lines.length > 0 && (
                                        <tr style={{ background: '#f0fdf4', borderTop: '2px solid #a7f3d0' }}>
                                            <td colSpan={4} className="text-end fw-semibold px-3 py-2" style={{ color: '#065f46' }}>Total Amount</td>
                                            <td className="text-end fw-bold px-3 py-2" style={{ color: '#065f46' }}>₹{calculateTotal().toFixed(2)}</td>
                                            <td></td>
                                        </tr>
                                    )}
                                </tbody>
                            </table>
                        </div>
                        </div>
                        </div>
                        {fieldErrors.incentive_lines && formData.incentive_lines.length === 0 && (
                            <div className="alert alert-danger py-2 px-3 mt-2 small">
                                <i className="bi bi-exclamation-circle me-1"></i>
                                {Array.isArray(fieldErrors.incentive_lines) ? fieldErrors.incentive_lines[0] : fieldErrors.incentive_lines}
                            </div>
                        )}
                    </>
                )}

                {/* Action Buttons */}
                <div className="d-flex align-items-center gap-2 mt-4 pt-3 mb-4" style={{ borderTop: '1px solid #e5e7eb' }}>
                    <button type="submit" className="btn btn-primary" disabled={saving}
                        style={{ padding: '10px 28px', fontWeight: '600', background: 'linear-gradient(135deg,#4F46E5,#4338CA)', border: 'none', borderRadius: '8px' }}>
                        {saving ? <><span className="spinner-border spinner-border-sm me-2"></span>Saving...</> : <><i className="bi bi-check-circle me-2"></i>Save Trade</>}
                    </button>
                    <button type="button" className="btn btn-outline-secondary" onClick={() => navigateToList(navigate, 'trades', { preserveFilters: true })}
                        style={{ padding: '10px 20px', fontWeight: '500', borderRadius: '8px' }}>
                        <i className="bi bi-x-lg me-2"></i>Cancel
                    </button>
                    {isEdit && (
                        <>
                            <button type="button" className="btn btn-outline-info" onClick={() => setShowTransferLetterModal(true)}
                                style={{ padding: '10px 18px', fontWeight: '500', borderRadius: '8px' }}>
                                <i className="bi bi-file-earmark-text me-1"></i>Transfer Letter
                            </button>
                            {formData.direction === 'SALE' && (
                                <div className="btn-group">
                                    <button type="button" className="btn btn-outline-secondary" onClick={() => handleDownloadPDF(true)}
                                        style={{ borderRadius: '8px 0 0 8px', fontWeight: '500' }}>
                                        <i className="bi bi-file-pdf me-1"></i>Bill of Supply
                                    </button>
                                    <button type="button" className="btn btn-outline-secondary dropdown-toggle dropdown-toggle-split"
                                        data-bs-toggle="dropdown" aria-expanded="false" style={{ borderRadius: '0 8px 8px 0' }}>
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
                                    <button type="button" className="btn btn-outline-secondary" onClick={() => handleDownloadPurchaseInvoice(true)}
                                        style={{ borderRadius: '8px 0 0 8px', fontWeight: '500' }}>
                                        <i className="bi bi-file-pdf me-1"></i>Purchase Invoice
                                    </button>
                                    <button type="button" className="btn btn-outline-secondary dropdown-toggle dropdown-toggle-split"
                                        data-bs-toggle="dropdown" aria-expanded="false" style={{ borderRadius: '0 8px 8px 0' }}>
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
