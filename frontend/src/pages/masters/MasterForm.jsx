import {useEffect, useState} from "react";
import {useLocation, useNavigate, useParams} from "react-router-dom";
import { toast } from 'react-toastify';
import api from "../../api/axios";
import NestedFieldArray from "./NestedFieldArray";
import HybridSelect from "../../components/HybridSelect";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import {markNewItemCreated} from "../../utils/filterPersistence";
import {formatDateForInput, parseDate as parseDateUtil} from "../../utils/dateFormatter";
import * as validateFormUtil from "../../utils/formValidation";
import { ValidationRules } from "../../utils/formValidation";
import LicenseBalanceModal from "../../components/LicenseBalanceModal";
import {navigateToList} from "../../utils/navigationUtils";
import {useBackButton} from "../../hooks/useBackButton";

/**
 * Generic Master Form for Create/Edit
 *
 * URL Pattern:
 * - Create: /masters/:entity/create OR /licenses/create
 * - Edit: /masters/:entity/:id/edit OR /licenses/:id/edit
 */

const ENTITY_SECTIONS = {
    'bill-of-entries': [
        {
            title: 'Document Info',
            icon: 'receipt-cutoff',
            color: '#6366F1',
            fields: ['bill_of_entry_number', 'bill_of_entry_date', 'appraisement', 'ooc_date'],
            cols: { bill_of_entry_number: 'col-md-4', bill_of_entry_date: 'col-md-4', appraisement: 'col-md-4', ooc_date: 'col-md-4' },
        },
        {
            title: 'Parties & Location',
            icon: 'building',
            color: '#4F46E5',
            fields: ['company', 'allotment', 'port', 'cha'],
            cols: { company: 'col-md-4', allotment: 'col-md-4', port: 'col-md-4', cha: 'col-md-4' },
        },
        {
            title: 'Financial',
            icon: 'currency-dollar',
            color: '#10b981',
            fields: ['exchange_rate'],
            cols: { exchange_rate: 'col-md-4' },
        },
        {
            title: 'Invoice Details',
            icon: 'file-earmark-text',
            color: '#f59e0b',
            fields: ['product_name', 'invoice_no', 'invoice_date'],
            cols: { product_name: 'col-md-4', invoice_no: 'col-md-4', invoice_date: 'col-md-4' },
        },
        {
            title: 'Notes',
            icon: 'chat-left-text',
            color: '#6b7280',
            fields: ['comments'],
            cols: { comments: 'col-12' },
        },
    ],
    licenses: [
        {
            title: 'License Identification',
            icon: 'file-earmark-text',
            color: '#4F46E5',
            fields: ['license_number', 'license_date', 'license_expiry_date', 'port', 'iec', 'scheme_code', 'advance_auth_number'],
            cols: { license_number: 'col-md-4', license_date: 'col-md-4', license_expiry_date: 'col-md-4', port: 'col-md-4', iec: 'col-md-4', scheme_code: 'col-md-4', advance_auth_number: 'col-md-4' },
        },
        {
            title: 'Financial Details',
            icon: 'currency-dollar',
            color: '#10b981',
            fields: ['total_cif_fc', 'total_cif_inr', 'total_duty_amount', 'exchange_rate', 'duty_rate'],
            cols: { total_cif_fc: 'col-md-4', total_cif_inr: 'col-md-4', total_duty_amount: 'col-md-4', exchange_rate: 'col-md-4', duty_rate: 'col-md-4' },
        },
        {
            title: 'Status Flags',
            icon: 'toggle-on',
            color: '#6366F1',
            fields: ['is_expired', 'is_null_dfia', 'is_incentive'],
            cols: { is_expired: 'col-md-4', is_null_dfia: 'col-md-4', is_incentive: 'col-md-4' },
        },
        {
            title: 'Conditions & Notes',
            icon: 'chat-left-text',
            color: '#6b7280',
            fields: ['conditions', 'restrictions', 'comments', 'description', 'notes'],
            cols: {},
        },
    ],
    'incentive-licenses': [
        {
            title: 'License Details',
            icon: 'award',
            color: '#f59e0b',
            fields: ['license_type', 'license_number', 'license_date', 'license_expiry_date'],
            cols: { license_type: 'col-md-3', license_number: 'col-md-3', license_date: 'col-md-3', license_expiry_date: 'col-md-3' },
        },
        {
            title: 'Party & Port',
            icon: 'building',
            color: '#4F46E5',
            fields: ['exporter', 'port_code'],
            cols: { exporter: 'col-md-6', port_code: 'col-md-6' },
        },
        {
            title: 'Financial',
            icon: 'currency-rupee',
            color: '#10b981',
            fields: ['license_value'],
            cols: { license_value: 'col-md-4' },
        },
        {
            title: 'Status & Notes',
            icon: 'toggle-on',
            color: '#6b7280',
            fields: ['is_active', 'notes'],
            cols: { is_active: 'col-md-4' },
        },
    ],
    trades: [
        {
            title: 'Trade Details',
            icon: 'arrow-left-right',
            color: '#10b981',
            fields: ['direction', 'license_type', 'invoice_number', 'invoice_date'],
            cols: { direction: 'col-md-3', license_type: 'col-md-3', invoice_number: 'col-md-3', invoice_date: 'col-md-3' },
        },
        {
            title: 'Parties',
            icon: 'building',
            color: '#4F46E5',
            fields: ['from_company', 'to_company'],
            cols: { from_company: 'col-md-6', to_company: 'col-md-6' },
        },
        {
            title: 'References',
            icon: 'link-45deg',
            color: '#6366F1',
            fields: ['incentive_license', 'boe'],
            cols: { incentive_license: 'col-md-6', boe: 'col-md-6' },
        },
        {
            title: 'Documents & Notes',
            icon: 'file-earmark-arrow-up',
            color: '#6b7280',
            fields: ['purchase_invoice_copy', 'remarks'],
            cols: { purchase_invoice_copy: 'col-md-6' },
        },
    ],
};

export default function MasterForm({
    entityName: propEntityName,
    recordId: propRecordId,
    isModal = false,
    onClose,
    onSuccess
}) {
    const {entity, id} = useParams();
    const location = useLocation();
    const navigate = useNavigate();

    // Use prop values if provided (for modal), otherwise use URL params (for page)
    const entityName = propEntityName || entity ||
        (location.pathname.includes('/licenses') ? 'licenses' : null) ||
        (location.pathname.includes('/allotments') ? 'allotments' : null) ||
        (location.pathname.includes('/bill-of-entries') ? 'bill-of-entries' : null) ||
        (location.pathname.includes('/trades') ? 'trades' : null) ||
        (location.pathname.includes('/incentive-licenses') ? 'incentive-licenses' : null);
    const recordId = propRecordId || id;
    const isEdit = Boolean(recordId);

    const [formData, setFormData] = useState({});
    const [metadata, setMetadata] = useState({});
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [fetchingAllotment, setFetchingAllotment] = useState(false);
    const [error, setError] = useState("");
    const [fieldErrors, setFieldErrors] = useState({}); // Track field-level errors
    const [updatedFields, setUpdatedFields] = useState({}); // Track updated fields for highlighting
    const [showBalanceModal, setShowBalanceModal] = useState(false); // License balance modal state
    const [savedLicenseId, setSavedLicenseId] = useState(null); // Store saved license ID for modal
    const [activeNestedTab, setActiveNestedTab] = useState(null);
    const [boePdfFile, setBoePdfFile] = useState(null);
    const [boeParsing, setBoeParsing] = useState(false);
    const [boeParseSummary, setBoeParseSummary] = useState(null);

    // Enable browser back button support with filter preservation
    useBackButton(entityName, !isModal);

    // Use centralized date parser from utility
    const parseDate = (dateString) => {
        return parseDateUtil(dateString);
    };

    // Helper function to format Date object to YYYY-MM-DD for API
    const formatDateForAPI = (date) => {
        if (!date) return null;
        return formatDateForInput(date);
    };

    // Fetch metadata and existing data
    useEffect(() => {
        if (!entityName) return;
        fetchMetadata();
        if (isEdit) {
            fetchRecord();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [entityName, recordId]);

    const fetchMetadata = async () => {
        try {
            let apiPath;
            if (entityName === 'licenses' || entityName === 'allotments' || entityName === 'bill-of-entries' || entityName === 'trades') {
                apiPath = `${entityName}/`;
            } else if (entityName === 'incentive-licenses') {
                apiPath = `incentive-licenses/`;
            } else {
                apiPath = `masters/${entityName}/`;
            }

            // Use GET to fetch metadata (custom structure with form_fields, field_meta, etc.)
            const {data} = await api.get(apiPath);

            setMetadata({
                form_fields: data.form_fields || data.fields || [],
                nested_field_defs: data.nested_field_defs || {},
                field_meta: data.field_meta || {}
            });

            // Apply default values from field_meta when creating new record (not editing)
            if (!isEdit && data.field_meta) {
                const defaults = {};
                const fkDefaults = {}; // Store FK defaults to fetch labels

                Object.keys(data.field_meta).forEach(fieldName => {
                    const fieldConfig = data.field_meta[fieldName];
                    if (fieldConfig.default !== undefined && fieldConfig.default !== null) {
                        defaults[fieldName] = fieldConfig.default;

                        // Track FK fields with defaults to fetch their labels
                        // Note: type can be 'fk' or 'select' (enhanced by backend)
                        if ((fieldConfig.type === 'fk' || fieldConfig.type === 'select') && typeof fieldConfig.default === 'number') {
                            const endpoint = fieldConfig.fk_endpoint || fieldConfig.endpoint || data.fk_endpoint_overrides?.[fieldName];
                            const labelField = fieldConfig.label_field || data.label_field_overrides?.[fieldName] || 'name';

                            fkDefaults[fieldName] = {
                                id: fieldConfig.default,
                                endpoint: endpoint,
                                labelField: labelField
                            };
                        }
                    }
                });

                // For FK defaults, just set the ID - AsyncSelectField will fetch the label
                if (Object.keys(fkDefaults).length > 0) {
                    const fkValues = Object.keys(fkDefaults).reduce((acc, fieldName) => {
                        acc[fieldName] = fkDefaults[fieldName].id;
                        return acc;
                    }, {});

                    setFormData(prev => ({ ...prev, ...fkValues }));
                }

                // Only set non-FK defaults if we found any
                const nonFkDefaults = Object.keys(defaults)
                    .filter(key => !fkDefaults[key])
                    .reduce((obj, key) => {
                        obj[key] = defaults[key];
                        return obj;
                    }, {});

                if (Object.keys(nonFkDefaults).length > 0) {
                    setFormData(prevData => ({...prevData, ...nonFkDefaults}));
                }
            }
        } catch (err) {
            console.error('[MasterForm] Error fetching metadata:', err);
            console.error('[MasterForm] Error response:', err.response?.data);
            toast.error("Failed to load form metadata: " + (err.response?.data?.detail || err.message));
        }
    };

    const fetchRecord = async () => {
        setLoading(true);
        try {
            let apiPath;
            if (entityName === 'licenses' || entityName === 'allotments' || entityName === 'bill-of-entries' || entityName === 'trades') {
                apiPath = `${entityName}/${recordId}/`;
            } else if (entityName === 'incentive-licenses') {
                apiPath = `incentive-licenses/${recordId}/`;
            } else {
                apiPath = `masters/${entityName}/${recordId}/`;
            }
            const {data} = await api.get(apiPath);
            setFormData(data);
        } catch (err) {
            setError(err.response?.data?.detail || "Failed to load record");
        } finally {
            setLoading(false);
        }
    };

    const handleParseBoePdf = async () => {
        if (!boePdfFile) {
            toast.error("Please choose a BOE PDF first");
            return;
        }
        setBoeParsing(true);
        setBoeParseSummary(null);
        try {
            const fd = new FormData();
            fd.append("file", boePdfFile);
            const { data } = await api.post("bill-of-entries/parse-pdf/", fd, {
                headers: { "Content-Type": "multipart/form-data" },
            });
            const { parsed, prefill, matched_allotment_id, matched_company_id, matched_port_id, company_created, licences } = data;

            // Build patch — only fields we successfully extracted/matched
            const patch = {};
            if (parsed.be_number) patch.bill_of_entry_number = parsed.be_number;
            if (parsed.be_date) patch.bill_of_entry_date = parsed.be_date;
            if (matched_company_id) patch.company = parseInt(matched_company_id, 10);
            if (matched_port_id) patch.port = parseInt(matched_port_id, 10);
            if (matched_allotment_id) patch.allotment = [matched_allotment_id];
            if (prefill.exchange_rate) patch.exchange_rate = String(prefill.exchange_rate);
            if (parsed.item_description) patch.product_name = parsed.item_description;

            // Build BOE item_details rows from matched licence rows.
            // Multiple licence rows that point to the same license item (same
            // sr_number) are summed into a single row — the BOE form should
            // carry the total CIF/qty per license item, not duplicates.
            const matchedRows = (licences || []).filter(l => l.match_status === 'matched' && l.matched_item_id);
            if (matchedRows.length > 0) {
                const toNum = (v) => {
                    if (v === null || v === undefined || v === '') return 0;
                    const n = parseFloat(v);
                    return isNaN(n) ? 0 : n;
                };
                const byItem = new Map();
                for (const l of matchedRows) {
                    const key = parseInt(l.matched_item_id, 10);
                    const existing = byItem.get(key) || { sr_number: key, cif_inr: 0, cif_fc: 0, qty: 0 };
                    existing.cif_inr += toNum(l.cif_inr);
                    existing.cif_fc  += toNum(l.cif_fc);
                    existing.qty     += toNum(l.qty);
                    byItem.set(key, existing);
                }
                // Round to 2dp / 3dp like the form expects
                patch.item_details = Array.from(byItem.values()).map(r => ({
                    sr_number: r.sr_number,
                    cif_inr: Number(r.cif_inr.toFixed(2)),
                    cif_fc:  Number(r.cif_fc.toFixed(2)),
                    qty:     Number(r.qty.toFixed(3)),
                }));
            }

            setFormData(prev => ({ ...prev, ...patch }));
            // Highlight updated fields briefly
            setUpdatedFields(prev => ({
                ...prev,
                ...Object.keys(patch).reduce((acc, k) => { acc[k] = true; return acc; }, {}),
            }));

            const unmatched = (licences || []).filter(l => l.match_status !== 'matched').length;
            setBoeParseSummary({
                be_number: parsed.be_number,
                be_date: parsed.be_date,
                port_code: parsed.port_code,
                currency: parsed.currency,
                exchange_rate: prefill.exchange_rate,
                company_created,
                matched_allotment_id,
                matched_company_id,
                buyer_name: parsed.buyer_name,
                licences: licences || [],
                unmatched,
            });

            const bits = [`BOE ${parsed.be_number || ""} parsed`];
            if (company_created) bits.push("new company created");
            if (matched_allotment_id) bits.push(`matched allotment #${matched_allotment_id}`);
            bits.push(`${(licences || []).length} licence row(s), ${unmatched} unmatched`);
            toast.success(bits.join(" · "));
        } catch (err) {
            console.error("BOE parse error", err);
            const msg = err?.response?.data?.detail || "Failed to parse BOE PDF";
            toast.error(msg);
        } finally {
            setBoeParsing(false);
        }
    };

    const handleChange = async (field, value) => {
        const updates = {[field]: value};

        // Auto-calculate registration_number when license_number changes
        if (field === "license_number" && value && entityName === "licenses") {
            // Remove first character if it's a zero
            const regNumber = value.startsWith("0") ? value.substring(1) : value;
            updates.registration_number = regNumber;
        }

        // Auto-calculate registration_date when license_date changes
        if (field === "license_date" && value && entityName === "licenses") {
            updates.registration_date = value;

            // Also calculate license_expiry_date (license_date + 1 year)
            try {
                const licenseDate = new Date(value);
                licenseDate.setFullYear(licenseDate.getFullYear() + 1);
                const expiryDate = licenseDate.toISOString().split('T')[0];
                updates.license_expiry_date = expiryDate;
            } catch (err) {
                // Silently fail for date calculation errors
            }
        }

        // Auto-calculate license_expiry_date for incentive licenses (2 years from license_date)
        if (field === "license_date" && value && entityName === "incentive-licenses") {
            try {
                const licenseDate = new Date(value);
                licenseDate.setFullYear(licenseDate.getFullYear() + 2);
                const expiryDate = licenseDate.toISOString().split('T')[0];
                updates.license_expiry_date = expiryDate;
            } catch (err) {
                // Silently fail for date calculation errors
            }
        }

        // Fetch allotment details when allotment is selected in bill-of-entries
        if (field === "allotment" && entityName === "bill-of-entries") {
            // Handle both array and single value
            let allotmentIds = [];
            if (Array.isArray(value)) {
                allotmentIds = value;
            } else if (value) {
                allotmentIds = [value];
            }

            if (allotmentIds.length > 0) {
                setFetchingAllotment(true);
                try {
                    // Fetch details from all selected allotments
                    const allItemDetails = [];
                    let firstExchangeRate = null;
                    let firstProductName = null;
                    let firstPort = null;
                    let firstCompany = null;

                    for (const allotmentId of allotmentIds) {
                        const {data} = await api.get(`bill-of-entries/fetch-allotment-details/?allotment_id=${allotmentId}`);

                        // Use exchange_rate, product_name, port, and company from first allotment
                        if (!firstExchangeRate && data.exchange_rate) {
                            firstExchangeRate = data.exchange_rate;
                        }
                        if (!firstProductName && data.product_name) {
                            firstProductName = data.product_name;
                        }
                        if (!firstPort && data.port) {
                            firstPort = data.port;
                        }
                        if (!firstCompany && data.company) {
                            firstCompany = data.company;
                        }

                        // Merge all item details from all allotments
                        if (data.item_details && data.item_details.length > 0) {
                            allItemDetails.push(...data.item_details);
                        }
                    }

                    // Update form fields with fetched data
                    // Only set exchange_rate from allotment if the BOE doesn't already have one
                    const currentExcRate = parseFloat(formData.exchange_rate);
                    if (firstExchangeRate && (!currentExcRate || currentExcRate === 0)) {
                        updates.exchange_rate = firstExchangeRate;
                    }
                    if (firstProductName) {
                        updates.product_name = firstProductName;
                    }
                    if (firstPort) {
                        updates.port = firstPort;
                    }
                    if (firstCompany) {
                        updates.company = firstCompany;
                    }
                    if (allItemDetails.length > 0) {
                        // Preserve frozen (ledger-imported) rows — never overwrite them
                        const existingItems = formData.item_details || [];
                        const frozenItems = existingItems.filter(item => item.is_frozen);
                        const frozenSrNumbers = new Set(frozenItems.map(item => item.sr_number));
                        const filteredAllotmentItems = allItemDetails.filter(item => !frozenSrNumbers.has(item.sr_number));
                        updates.item_details = [...frozenItems, ...filteredAllotmentItems];
                    } else if ((formData.item_details || []).some(item => item.is_frozen)) {
                        // No new allotment items but frozen rows exist — keep them
                        updates.item_details = (formData.item_details || []).filter(item => item.is_frozen);
                    }
                } catch (err) {
                    toast.error("Failed to fetch allotment details: " + (err.response?.data?.error || err.message));
                } finally{
                    setFetchingAllotment(false);
                }
            }
        }

        // Allotment calculations
        if (entityName === "allotments") {
            // Get current form data with the new update applied
            const currentData = {...formData, ...updates};

            // Priority 1: Calculate cif_fc from unit_value_per_unit and required_quantity
            // Calculate whenever unit_value, quantity, or exchange_rate changes
            if ((field === "unit_value_per_unit" || field === "required_quantity" || field === "exchange_rate")
                && currentData.unit_value_per_unit && currentData.required_quantity) {
                const unitValue = parseFloat(currentData.unit_value_per_unit);
                const requiredQty = parseFloat(currentData.required_quantity);
                if (!isNaN(unitValue) && !isNaN(requiredQty) && requiredQty > 0) {
                    updates.cif_fc = (unitValue * requiredQty).toFixed(2);
                    currentData.cif_fc = updates.cif_fc; // Update for next calculation
                }
            }
            // Priority 2: If cif_fc provided but unit_value not, calculate unit_value
            else if (field === "cif_fc" && currentData.cif_fc && currentData.required_quantity && !currentData.unit_value_per_unit) {
                const cifFc = parseFloat(currentData.cif_fc);
                const requiredQty = parseFloat(currentData.required_quantity);
                if (!isNaN(cifFc) && !isNaN(requiredQty) && requiredQty > 0) {
                    // Round up to 3 decimal places
                    updates.unit_value_per_unit = (Math.ceil((cifFc / requiredQty) * 1000) / 1000).toFixed(3);
                    currentData.unit_value_per_unit = updates.unit_value_per_unit; // Update for reference
                }
            }

            // Calculate cif_fc from cif_inr and exchange_rate (if cif_inr and exchange_rate present)
            if ((field === "cif_inr" || field === "exchange_rate") && currentData.cif_inr && currentData.exchange_rate) {
                const cifInr = parseFloat(currentData.cif_inr);
                const exchangeRate = parseFloat(currentData.exchange_rate);
                if (!isNaN(cifInr) && !isNaN(exchangeRate) && exchangeRate > 0) {
                    updates.cif_fc = (cifInr / exchangeRate).toFixed(2);
                    currentData.cif_fc = updates.cif_fc; // Update for next calculation

                    // Also calculate unit_value_per_unit if we have required_quantity
                    if (currentData.required_quantity) {
                        const requiredQty = parseFloat(currentData.required_quantity);
                        if (!isNaN(requiredQty) && requiredQty > 0) {
                            updates.unit_value_per_unit = (Math.ceil((parseFloat(updates.cif_fc) / requiredQty) * 1000) / 1000).toFixed(3);
                        }
                    }
                }
            }
            // Calculate cif_inr from cif_fc and exchange_rate (if cif_fc and exchange_rate present)
            else if ((field === "cif_fc" || field === "exchange_rate") && currentData.cif_fc && currentData.exchange_rate) {
                const cifFc = parseFloat(currentData.cif_fc);
                const exchangeRate = parseFloat(currentData.exchange_rate);
                if (!isNaN(cifFc) && !isNaN(exchangeRate) && exchangeRate > 0) {
                    updates.cif_inr = (cifFc * exchangeRate).toFixed(2);
                }
            }

            // Calculate unit_value_per_unit from cif_fc and required_quantity
            if ((field === "cif_fc" || field === "required_quantity") && currentData.cif_fc && currentData.required_quantity) {
                const cifFc = parseFloat(currentData.cif_fc);
                const requiredQty = parseFloat(currentData.required_quantity);
                // Only auto-calculate unit price if it's not already set or if user is changing cif_fc/quantity
                if (!isNaN(cifFc) && !isNaN(requiredQty) && requiredQty > 0 &&
                    (field === "cif_fc" || field === "required_quantity")) {
                    updates.unit_value_per_unit = (Math.ceil((cifFc / requiredQty) * 1000) / 1000).toFixed(3);
                }
            }
        }

        setFormData(prev => ({
            ...prev,
            ...updates
        }));
    };

    const handleFetchImports = async (exportIndex, exportItem) => {
        // Validate required fields
        if (!exportItem.norm_class) {
            alert("Please select a Norm Class first");
            return;
        }

        if (!exportItem.start_serial_number) {
            alert("Please enter Start Serial Number first");
            return;
        }

        try {
            // Fetch the SION norm class with its import items
            const {data: sionData} = await api.get(`masters/sion-classes/${exportItem.norm_class}/`);

            if (!sionData.import_norm || sionData.import_norm.length === 0) {
                alert("No import items found for this SION norm class");
                return;
            }

            // Get start serial number from export item (form field only, not saved)
            const startSerial = parseInt(exportItem.start_serial_number) || 0;
            const existingImports = formData.import_license || [];

            // Track existing serial numbers to prevent duplicates
            const existingSerialNumbers = new Set(existingImports.map(item => item.serial_number));

            const updatedImports = [...existingImports];
            const newlyUpdatedFields = {};
            let addedCount = 0;
            let updatedCount = 0;

            // Process each SION import item
            sionData.import_norm.forEach((sionImport) => {
                const targetSerialNumber = startSerial + (sionImport.serial_number || 0);

                // Check if this serial number already exists
                const existingIndex = existingImports.findIndex(item => item.serial_number === targetSerialNumber);

                if (existingIndex >= 0) {
                    // Serial number exists - only update empty fields
                    const existing = existingImports[existingIndex];
                    let fieldsUpdated = false;

                    // Update hs_code if empty
                    if (!existing.hs_code && sionImport.hsn_code) {
                        updatedImports[existingIndex].hs_code = sionImport.hsn_code;
                        fieldsUpdated = true;
                        newlyUpdatedFields[`import_license.${existingIndex}.hs_code`] = true;
                    }

                    // Update description if empty
                    if (!existing.description && sionImport.description) {
                        updatedImports[existingIndex].description = sionImport.description;
                        fieldsUpdated = true;
                        newlyUpdatedFields[`import_license.${existingIndex}.description`] = true;
                    }

                    // Update unit if empty
                    if (!existing.unit && sionImport.unit) {
                        updatedImports[existingIndex].unit = sionImport.unit;
                        fieldsUpdated = true;
                        newlyUpdatedFields[`import_license.${existingIndex}.unit`] = true;
                    }

                    if (fieldsUpdated) updatedCount++;
                } else if (!existingSerialNumbers.has(targetSerialNumber)) {
                    // Serial number doesn't exist - add new item
                    const newIndex = updatedImports.length;
                    const netQty = parseFloat(exportItem.net_quantity) || 1;
                    const newItem = {
                        serial_number: targetSerialNumber,
                        hs_code: sionImport.hsn_code || null,
                        description: sionImport.description || "",
                        duty_type: sionImport.duty_type || "Basic",
                        quantity: parseFloat((netQty * (sionImport.quantity || 0)).toFixed(4)),
                        unit: sionImport.unit || "KG",
                        cif_fc: 0,
                        cif_inr: 0,
                        items: []
                    };

                    updatedImports.push(newItem);
                    existingSerialNumbers.add(targetSerialNumber);

                    // Mark all fields as updated for new items
                    Object.keys(newItem).forEach(key => {
                        newlyUpdatedFields[`import_license.${newIndex}.${key}`] = true;
                    });

                    addedCount++;
                }
            });

            // Update form data and highlighted fields
            handleChange("import_license", updatedImports);
            setUpdatedFields(prev => ({...prev, ...newlyUpdatedFields}));

            let message = [];
            if (addedCount > 0) message.push(`Added ${addedCount} new import items`);
            if (updatedCount > 0) message.push(`Updated ${updatedCount} existing items`);
            if (message.length > 0) {
                toast.success(message.join('. '));
            } else {
                toast.info("No changes made");
            }

        } catch (err) {
            toast.error(err.response?.data?.detail || "Failed to fetch import items from SION");
        }
    };

    // Frontend validation function
    const validateForm = () => {
        const errors = {};

        // Collect required fields from metadata and validate using utility
        if (metadata.form_fields) {
            metadata.form_fields.forEach(fieldName => {
                const fieldMeta = metadata.field_meta?.[fieldName] || {};
                const label = fieldMeta.label || fieldName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                const value = formData[fieldName];
                const rules = [];

                // Add required rule
                if (fieldMeta.required) {
                    rules.push(ValidationRules.REQUIRED);
                }

                // Add type-specific validations
                if (fieldMeta.type === 'email' || fieldName.includes('email')) {
                    rules.push(ValidationRules.EMAIL);
                }
                if (fieldMeta.type === 'url' || fieldName.includes('url')) {
                    rules.push(ValidationRules.URL);
                }
                if (fieldMeta.type === 'number' || fieldMeta.type === 'decimal' || fieldMeta.type === 'integer') {
                    if (fieldMeta.type === 'integer') {
                        rules.push(ValidationRules.INTEGER);
                    } else {
                        rules.push(ValidationRules.NUMBER);
                    }
                }
                if (fieldMeta.min_value !== undefined) {
                    rules.push({ type: ValidationRules.MIN_VALUE, value: fieldMeta.min_value });
                }
                if (fieldMeta.max_value !== undefined) {
                    rules.push({ type: ValidationRules.MAX_VALUE, value: fieldMeta.max_value });
                }
                if (fieldMeta.min_length) {
                    rules.push({ type: ValidationRules.MIN_LENGTH, value: fieldMeta.min_length });
                }
                if (fieldMeta.max_length) {
                    rules.push({ type: ValidationRules.MAX_LENGTH, value: fieldMeta.max_length });
                }

                // Validate field if it has rules
                if (rules.length > 0) {
                    const fieldErrors = validateFormUtil.validateField(value, rules, label);
                    if (fieldErrors.length > 0) {
                        errors[fieldName] = fieldErrors;
                    }
                }
            });
        }

        // License-specific validations
        if (entityName === 'licenses') {
            // Validate license number format
            if (formData.license_number && !/^[A-Z0-9/-]+$/.test(formData.license_number)) {
                errors.license_number = ['License number can only contain uppercase letters, numbers, hyphens, and slashes'];
            }

            // Validate dates
            if (formData.license_date && formData.license_expiry_date) {
                const licenseDate = new Date(formData.license_date);
                const expiryDate = new Date(formData.license_expiry_date);
                if (expiryDate <= licenseDate) {
                    errors.license_expiry_date = ['Expiry date must be after license date'];
                }
            }

            // Validate export items using validation utility
            if (formData.export_license && Array.isArray(formData.export_license)) {
                const exportSchema = {
                    description: {
                        rules: [ValidationRules.REQUIRED],
                        label: 'Description'
                    },
                    net_quantity: {
                        rules: [ValidationRules.REQUIRED, ValidationRules.NON_NEGATIVE],
                        label: 'Net Quantity'
                    }
                };
                const exportErrors = validateFormUtil.validateNestedArray(formData.export_license, exportSchema);
                if (exportErrors.length > 0) {
                    errors.export_license = exportErrors;
                }
            }

            // Validate import items using validation utility
            if (formData.import_license && Array.isArray(formData.import_license)) {
                const importSchema = {
                    hs_code: {
                        rules: [ValidationRules.REQUIRED],
                        label: 'HS Code'
                    },
                    description: {
                        rules: [ValidationRules.REQUIRED],
                        label: 'Description'
                    },
                    serial_number: {
                        rules: [ValidationRules.REQUIRED, ValidationRules.INTEGER],
                        label: 'Serial Number'
                    },
                    unit: {
                        rules: [ValidationRules.REQUIRED],
                        label: 'Unit'
                    }
                };
                const importErrors = validateFormUtil.validateNestedArray(formData.import_license, importSchema);
                if (importErrors.length > 0) {
                    errors.import_license = importErrors;
                }
            }

            // Validate documents (if adding new ones)
            if (formData.license_documents && Array.isArray(formData.license_documents)) {
                const docErrors = [];
                formData.license_documents.forEach((doc, index) => {
                    // Only validate if file is provided (new document)
                    if (doc.file && doc.file instanceof File) {
                        const docSchema = {
                            type: {
                                rules: [ValidationRules.REQUIRED],
                                label: 'Document Type'
                            }
                        };
                        const itemErrors = validateFormUtil.validateForm(doc, docSchema);
                        if (Object.keys(itemErrors).length > 0) {
                            docErrors[index] = itemErrors;
                        }
                    }
                });
                if (docErrors.length > 0) {
                    errors.license_documents = docErrors;
                }
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
        const validationErrors = validateForm();
        if (Object.keys(validationErrors).length > 0) {
            setFieldErrors(validationErrors);

            // Build user-friendly error messages
            const errorMessages = [];
            const fieldNameMap = {
                'license_number': 'License Number',
                'license_date': 'License Date',
                'license_expiry_date': 'License Expiry Date',
                'exporter': 'Exporter',
                'port': 'Port',
                'export_license': 'Export Items',
                'import_license': 'Import Items',
                'license_documents': 'Documents',
                'hs_code': 'HS Code',
                'description': 'Description',
                'quantity': 'Quantity',
                'serial_number': 'Serial Number',
                'type': 'Type',
                'file': 'File',
                'net_quantity': 'Net Quantity',
                'norm_class': 'Norm Class',
                'unit': 'Unit'
            };

            Object.entries(validationErrors).forEach(([field, fieldErrors]) => {
                const friendlyName = fieldNameMap[field] || field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

                if (Array.isArray(fieldErrors)) {
                    // Check if it's an array of error objects (nested items)
                    if (fieldErrors.some(item => item && typeof item === 'object')) {
                        fieldErrors.forEach((itemErrors, index) => {
                            if (itemErrors && typeof itemErrors === 'object') {
                                Object.entries(itemErrors).forEach(([subField, subErrors]) => {
                                    const subName = fieldNameMap[subField] || subField.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                                    const message = Array.isArray(subErrors) ? subErrors.join(', ') : subErrors;
                                    errorMessages.push(`${friendlyName} #${index + 1} - ${subName}: ${message}`);
                                });
                            }
                        });
                    } else {
                        // Simple array of error strings
                        errorMessages.push(`${friendlyName}: ${fieldErrors.join(', ')}`);
                    }
                } else if (typeof fieldErrors === 'string') {
                    errorMessages.push(`${friendlyName}: ${fieldErrors}`);
                }
            });

            const errorMsg = 'Please fix the following errors:\n\n' + errorMessages.join('\n');
            setError(errorMsg);
            toast.error('Please fix validation errors before submitting');

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
            let apiPath;
            if (entityName === 'licenses' || entityName === 'allotments' || entityName === 'bill-of-entries' || entityName === 'trades') {
                apiPath = `${entityName}/`;
            } else if (entityName === 'incentive-licenses') {
                apiPath = `incentive-licenses/`;
            } else {
                apiPath = `masters/${entityName}/`;
            }

            // Check if formData contains any File objects (including nested)
            const hasFiles = () => {
                const checkForFiles = (obj) => {
                    if (obj instanceof File) return true;
                    if (Array.isArray(obj)) {
                        return obj.some(item => checkForFiles(item));
                    }
                    if (obj && typeof obj === 'object') {
                        return Object.values(obj).some(val => checkForFiles(val));
                    }
                    return false;
                };
                return checkForFiles(formData);
            };

            let response;
            if (hasFiles()) {
                // Use FormData for file uploads
                const formDataObj = new FormData();

                // Helper function to append data to FormData
                const appendToFormData = (key, value, parentKey = '') => {
                    const fullKey = parentKey ? `${parentKey}.${key}` : key;

                    // Skip empty 'id' fields in nested arrays (for new items)
                    if (key === 'id' && (value === '' || value === null || value === undefined) && parentKey.includes('[')) {
                        return; // Don't append empty id fields for nested items
                    }

                    if (value instanceof File) {
                        formDataObj.append(fullKey, value);
                    } else if (Array.isArray(value)) {
                        value.forEach((item, index) => {
                            if (item instanceof File) {
                                formDataObj.append(`${fullKey}[${index}]`, item);
                            } else if (typeof item === 'object' && item !== null) {
                                Object.entries(item).forEach(([subKey, subValue]) => {
                                    appendToFormData(subKey, subValue, `${fullKey}[${index}]`);
                                });
                            } else {
                                formDataObj.append(`${fullKey}[${index}]`, item);
                            }
                        });
                    } else if (value && typeof value === 'object' && !(value instanceof Date)) {
                        Object.entries(value).forEach(([subKey, subValue]) => {
                            appendToFormData(subKey, subValue, fullKey);
                        });
                    } else if (value !== null && value !== undefined) {
                        // Allow empty strings for nested fields (important for nested arrays)
                        // Only skip truly null/undefined values
                        formDataObj.append(fullKey, value === '' ? '' : value);
                    }
                };

                Object.entries(formData).forEach(([key, value]) => {
                    appendToFormData(key, value);
                });

                if (isEdit) {
                    response = await api.patch(`${apiPath}${id}/`, formDataObj, {
                        headers: {'Content-Type': 'multipart/form-data'}
                    });
                } else {
                    response = await api.post(apiPath, formDataObj, {
                        headers: {'Content-Type': 'multipart/form-data'}
                    });
                }
            } else {
                // Use regular JSON for non-file data
                // Clean up date fields
                const cleanedFormData = {...formData};

                // Remove audit fields (should never be sent from frontend)
                delete cleanedFormData.created_on;
                delete cleanedFormData.created_by;
                delete cleanedFormData.modified_on;
                delete cleanedFormData.modified_by;

                Object.keys(cleanedFormData).forEach(key => {
                    if (key.includes('date') || key.includes('_at') || key.includes('_on')) {
                        const value = cleanedFormData[key];
                        if (value === '' || value === undefined) {
                            // Empty dates should be null
                            cleanedFormData[key] = null;
                        } else if (value instanceof Date) {
                            // Convert Date objects to YYYY-MM-DD
                            cleanedFormData[key] = formatDateForAPI(value);
                        } else if (typeof value === 'string' && value.length > 0) {
                            // Parse and reformat string dates (handles both YYYY-MM-DD and dd-MM-yyyy)
                            const date = parseDate(value);
                            if (date) {
                                cleanedFormData[key] = formatDateForAPI(date);
                            }
                        }
                    }
                });

                // Clean up nested arrays: remove empty 'id' fields for new items
                Object.keys(cleanedFormData).forEach(key => {
                    if (Array.isArray(cleanedFormData[key])) {
                        cleanedFormData[key] = cleanedFormData[key].map(item => {
                            if (item && typeof item === 'object') {
                                const cleanedItem = {...item};
                                // Remove id if it's empty string, null, or undefined
                                if (cleanedItem.id === '' || cleanedItem.id === null || cleanedItem.id === undefined) {
                                    delete cleanedItem.id;
                                }
                                return cleanedItem;
                            }
                            return item;
                        });
                    }
                });

                if (isEdit) {
                    response = await api.patch(`${apiPath}${recordId}/`, cleanedFormData);
                } else {
                    response = await api.post(apiPath, cleanedFormData);
                }
            }

            // Mark newly created items for highlighting in list
            if (!isEdit && response.data?.id) {
                markNewItemCreated(response.data.id);
            }

            // Set flag to restore filters when returning to list
            sessionStorage.setItem('allotmentListFilters', JSON.stringify({
                returnTo: 'list',
                timestamp: new Date().getTime()
            }));

            // Show success message
            toast.success(isEdit ? `${entityTitle} updated successfully` : `${entityTitle} created successfully`);

            // If modal mode, call onSuccess and onClose
            if (isModal && onSuccess) {
                const savedId = response.data?.id || recordId;
                onSuccess(savedId);
            }

            if (isModal && onClose) {
                onClose();
                return;
            }

            // Redirect based on entity type (only for non-modal)
            let redirectPath;
            if (entityName === 'licenses') {
                redirectPath = '/licenses';
            } else if (entityName === 'allotments') {
                // For allotments, redirect to action page after save
                const savedId = response.data.id || recordId;
                redirectPath = `/allotments/${savedId}/allocate`;
            } else if (entityName === 'bill-of-entries') {
                redirectPath = `/bill-of-entries`;
            } else if (entityName === 'trades') {
                redirectPath = `/trades`;
            } else if (entityName === 'incentive-licenses') {
                redirectPath = '/incentive-licenses';
            } else {
                redirectPath = `/masters/${entityName}`;
            }
            navigate(redirectPath);
        } catch (err) {
            console.error('Save error:', err.response?.data);

            // Handle field-level errors
            if (err.response?.data && typeof err.response.data === 'object') {
                // Format backend errors using utility
                const formattedErrors = validateFormUtil.formatBackendErrors(err.response.data);
                setFieldErrors(formattedErrors);

                // Create a user-friendly error message with better field names
                const errorMessages = [];
                const fieldNameMap = {
                    'license_number': 'License Number',
                    'license_date': 'License Date',
                    'license_expiry_date': 'License Expiry Date',
                    'exporter': 'Exporter',
                    'port': 'Port',
                    'export_license': 'Export Items',
                    'import_license': 'Import Items',
                    'license_documents': 'Documents',
                    'hs_code': 'HS Code',
                    'description': 'Description',
                    'quantity': 'Quantity',
                    'serial_number': 'Serial Number',
                    'type': 'Type',
                    'file': 'File',
                    'net_quantity': 'Net Quantity',
                    'norm_class': 'Norm Class',
                    'unit': 'Unit',
                    'cif_fc': 'CIF (FC)',
                    'cif_inr': 'CIF (INR)'
                };

                // Helper function to get friendly field name
                const getFriendlyFieldName = (fieldPath) => {
                    // Handle nested paths like export_license[0].hs_code
                    const match = fieldPath.match(/^(\w+)(?:\[(\d+)\])?\.?(\w+)?/);
                    if (match) {
                        const [, mainField, index, subField] = match;
                        const mainName = fieldNameMap[mainField] || mainField.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());

                        if (index !== undefined && subField) {
                            const subName = fieldNameMap[subField] || subField.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                            return `${mainName} #${parseInt(index) + 1} - ${subName}`;
                        } else if (index !== undefined) {
                            return `${mainName} #${parseInt(index) + 1}`;
                        }
                        return mainName;
                    }
                    return fieldNameMap[fieldPath] || fieldPath.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                };

                // Helper function to process errors recursively
                const processErrors = (errors, fieldPath = '') => {
                    if (Array.isArray(errors)) {
                        errors.forEach((error, index) => {
                            if (typeof error === 'object' && error !== null) {
                                // Handle nested field errors (like license_documents[0].type)
                                if (error.non_field_errors) {
                                    const friendlyName = getFriendlyFieldName(`${fieldPath}[${index}]`);
                                    errorMessages.push(`${friendlyName}: ${error.non_field_errors.join(', ')}`);
                                }
                                Object.entries(error).forEach(([key, value]) => {
                                    if (key !== 'non_field_errors') {
                                        const nestedPath = `${fieldPath}[${index}].${key}`;
                                        processErrors(value, nestedPath);
                                    }
                                });
                            } else if (typeof error === 'string') {
                                const friendlyName = getFriendlyFieldName(fieldPath);
                                errorMessages.push(`${friendlyName}: ${error}`);
                            }
                        });
                    } else if (typeof errors === 'string') {
                        const friendlyName = getFriendlyFieldName(fieldPath);
                        errorMessages.push(`${friendlyName}: ${errors}`);
                    } else if (typeof errors === 'object' && errors !== null) {
                        Object.entries(errors).forEach(([key, value]) => {
                            const nestedPath = fieldPath ? `${fieldPath}.${key}` : key;
                            processErrors(value, nestedPath);
                        });
                    }
                };

                // Handle top-level non_field_errors
                if (err.response.data.non_field_errors) {
                    errorMessages.push(...err.response.data.non_field_errors);
                }

                // Process all field errors
                Object.entries(err.response.data).forEach(([field, errors]) => {
                    if (field !== 'non_field_errors') {
                        processErrors(errors, field);
                    }
                });

                const errorMsg = errorMessages.length > 0
                    ? 'Please fix the following errors:\n\n' + errorMessages.join('\n')
                    : "Validation errors occurred. Please check the form.";
                setError(errorMsg);
                toast.error('Validation failed. Please check the form for errors.');

                // Scroll to first error
                setTimeout(() => {
                    const firstErrorField = document.querySelector('.is-invalid');
                    if (firstErrorField) {
                        firstErrorField.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        firstErrorField.focus();
                    }
                }, 100);
            } else {
                // Handle other error formats
                let errorMsg = "Failed to save record";

                if (err.response?.data?.detail) {
                    errorMsg = err.response.data.detail;
                } else if (err.response?.data?.error) {
                    errorMsg = err.response.data.error;
                } else if (err.response?.data?.message) {
                    errorMsg = err.response.data.message;
                } else if (typeof err.response?.data === 'string') {
                    errorMsg = err.response.data;
                } else if (err.response?.status === 400) {
                    errorMsg = "Invalid data provided. Please check your input.";
                } else if (err.response?.status === 403) {
                    errorMsg = "You don't have permission to perform this action.";
                } else if (err.response?.status === 404) {
                    errorMsg = "Record not found.";
                } else if (err.response?.status === 500) {
                    errorMsg = "Server error occurred. Please try again or contact support.";
                } else if (err.message) {
                    errorMsg = `Error: ${err.message}`;
                }

                setError(errorMsg);
                toast.error(errorMsg);
            }
        } finally {
            setSaving(false);
        }
    };

    const renderField = (fieldName) => {
        const fieldMeta = metadata.field_meta?.[fieldName] || {};

        // For m2m fields, default to empty array instead of empty string
        let value = formData[fieldName];
        if (value === undefined || value === null) {
            value = (fieldMeta.type === "m2m" || fieldMeta.type === "fk_multi") ? [] : "";
        }

        // Check if field has error
        const fieldError = fieldErrors[fieldName];
        const hasError = fieldError && (Array.isArray(fieldError) ? fieldError.length > 0 : fieldError);
        const errorClass = hasError ? 'is-invalid' : '';

        // Handle date fields with DatePicker
        if (fieldMeta.type === "date" || fieldName.includes("date") || fieldName.includes("_at") || fieldName.includes("_on")) {
            return (
                <div className="w-100">
                    <DatePicker
                        selected={parseDate(value)}
                        onChange={(date) => handleChange(fieldName, formatDateForAPI(date))}
                        dateFormat="dd-MM-yyyy"
                        className={`form-control ${errorClass}`}
                        wrapperClassName="w-100 d-block"
                        placeholderText="Select date"
                        isClearable
                        showYearDropdown
                        showMonthDropdown
                        dropdownMode="select"
                    />
                </div>
            );
        }

        // Handle FK Select fields or fields with choices using HybridSelect
        if (fieldMeta.type === "select" || fieldMeta.endpoint || fieldMeta.fk_endpoint || fieldMeta.choices) {
            // Check if it's a many-to-many field from metadata or if value is array
            const isMulti = fieldMeta.type === "m2m" || fieldMeta.type === "fk_multi" || Array.isArray(value);

            return (
                <HybridSelect
                    fieldMeta={fieldMeta}
                    value={value}
                    onChange={(val) => handleChange(fieldName, val)}
                    isMulti={isMulti}
                    placeholder={`Select ${fieldName.replace(/_/g, " ")}`}
                />
            );
        }

        // Handle file/image fields
        if (fieldName.includes("logo") || fieldName.includes("signature") || fieldName.includes("stamp") || fieldName.includes("image")) {
            const existingFileUrl = typeof value === 'string' && value ? value : null;
            const hasNewFile = value instanceof File;

            return (
                <div>
                    <input
                        type="file"
                        className={`form-control ${errorClass}`}
                        onChange={(e) => handleChange(fieldName, e.target.files[0])}
                        accept="image/*"
                    />
                    {existingFileUrl && !hasNewFile && (
                        <div className="mt-2">
                            <small className="text-muted">Current file:</small>
                            <div className="d-flex align-items-center gap-2 mt-1">
                                <a
                                    href={existingFileUrl}
                                    target="_blank"
                                    rel="noopener noreferrer"
                                    className="btn btn-sm btn-outline-primary"
                                >
                                    <i className="bi bi-eye me-1"></i>
                                    View Current
                                </a>
                                <img
                                    src={existingFileUrl}
                                    alt={fieldName}
                                    style={{
                                        maxHeight: '60px',
                                        maxWidth: '100px',
                                        objectFit: 'contain',
                                        border: '1px solid #ddd',
                                        borderRadius: '4px',
                                        padding: '4px'
                                    }}
                                />
                            </div>
                        </div>
                    )}
                    {hasNewFile && (
                        <div className="mt-2">
                            <small className="text-success">
                                <i className="bi bi-check-circle me-1"></i>
                                New file selected: {value.name}
                            </small>
                        </div>
                    )}
                </div>
            );
        }

        // Handle boolean fields as switch
        if (typeof value === "boolean" || fieldName.startsWith("is_") || fieldName.startsWith("has_")) {
            const boolValue = typeof value === "boolean" ? value : false;
            return (
                <div className="form-check form-switch">
                    <input
                        type="checkbox"
                        className="form-check-input"
                        role="switch"
                        id={`switch-${fieldName}`}
                        checked={boolValue}
                        onChange={(e) => handleChange(fieldName, e.target.checked)}
                    />
                    <label className="form-check-label" htmlFor={`switch-${fieldName}`}>
                        {boolValue ? "Yes" : "No"}
                    </label>
                </div>
            );
        }

        // Handle textarea for long text fields
        if (fieldName.includes("address") || fieldName.includes("description") || fieldName.includes("note")) {
            return (
                <textarea
                    className={`form-control ${errorClass}`}
                    rows="3"
                    value={value}
                    onChange={(e) => handleChange(fieldName, e.target.value)}
                />
            );
        }

        // Handle decimal/number fields
        if (fieldMeta.type === "number" || fieldName.includes("price") || fieldName.includes("rate") || fieldName.includes("quantity") || fieldName.includes("duty")) {
            return (
                <input
                    type="number"
                    step={fieldMeta.step || "0.01"}
                    className={`form-control ${errorClass}`}
                    value={value}
                    onChange={(e) => handleChange(fieldName, e.target.value)}
                />
            );
        }

        // Default text input
        return (
            <input
                type="text"
                className={`form-control ${errorClass}`}
                value={value}
                onChange={(e) => handleChange(fieldName, e.target.value)}
            />
        );
    };

    const handleModalClose = () => {
        setShowBalanceModal(false);
    };

    const entityTitle = entityName
        ?.split("-")
        .map(word => word.charAt(0).toUpperCase() + word.slice(1))
        .join(" ");

    const entityIconMap = {
        licenses: 'file-earmark-text',
        allotments: 'diagram-3',
        'bill-of-entries': 'receipt-cutoff',
        trades: 'arrow-left-right',
        'incentive-licenses': 'award',
    };
    const entityColorMap = {
        licenses: '#4F46E5',
        allotments: '#06b6d4',
        'bill-of-entries': '#6366F1',
        trades: '#10b981',
        'incentive-licenses': '#f59e0b',
    };
    const entityIcon = entityIconMap[entityName] || 'file-earmark';
    const entityColor = entityColorMap[entityName] || '#4F46E5';

    if (loading) {
        return (
            <div className="container-fluid" style={{ backgroundColor: 'var(--bs-gray-50)', minHeight: '100vh', padding: '20px 24px' }}>
                <div className="d-flex justify-content-between align-items-center mb-4">
                    <div>
                        <div className="placeholder-glow mb-1"><span className="placeholder col-3 rounded" style={{ height: 24 }}></span></div>
                        <div className="placeholder-glow"><span className="placeholder col-5 rounded" style={{ height: 14 }}></span></div>
                    </div>
                </div>
                <div className="card border-0 shadow-sm" style={{ borderRadius: '12px' }}>
                    <div className="card-body p-4">
                        <div className="row g-3">
                            {[...Array(6)].map((_, i) => (
                                <div key={i} className="col-md-4">
                                    <div className="placeholder-glow mb-1"><span className="placeholder col-6 rounded" style={{ height: 12 }}></span></div>
                                    <span className="placeholder col-12 rounded d-block" style={{ height: 38 }}></span>
                                </div>
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        );
    }

    return (
        <div className="container-fluid" style={{ backgroundColor: 'var(--bs-gray-50)', minHeight: '100vh', padding: '20px 24px' }}>
            {/* Compact Header */}
            <div className="d-flex justify-content-between align-items-center mb-4">
                <div>
                    <h4 className="mb-0 fw-bold" style={{ color: 'var(--text-dark)' }}>
                        <i className={`bi bi-${entityIcon} me-2`} style={{ color: entityColor }}></i>
                        {isEdit ? 'Edit' : 'New'} {entityTitle}
                    </h4>
                    <small className="text-muted">{isEdit ? 'Update existing record' : 'Create a new record'}</small>
                </div>
                <button
                    type="button"
                    className="btn btn-sm btn-outline-secondary"
                    onClick={() => {
                        if (isModal && onClose) { onClose(); return; }
                        navigateToList(navigate, entityName, { preserveFilters: true });
                    }}
                >
                    <i className="bi bi-arrow-left me-1"></i>Back to List
                </button>
            </div>

            <div className="card border-0 shadow-sm" style={{ borderRadius: '12px' }}>
                <div className="card-header bg-white border-bottom py-3" style={{ borderRadius: '12px 12px 0 0' }}>
                    <div className="d-flex align-items-center justify-content-between">
                        <h6 className="mb-0 fw-semibold">
                            <i className={`bi bi-${entityIcon} me-2`} style={{ color: entityColor }}></i>
                            {entityTitle} Details
                        </h6>
                        {entityName === 'trades' && formData.direction && (() => {
                            const dirColors = { PURCHASE: '#4F46E5', SALE: '#10b981', COMMISSION_PURCHASE: '#f59e0b', COMMISSION_SALE: '#6366F1' };
                            const dirLabels = { PURCHASE: 'Purchase', SALE: 'Sale', COMMISSION_PURCHASE: 'Commission Purchase', COMMISSION_SALE: 'Commission Sale' };
                            const dirIcons = { PURCHASE: 'cart-check', SALE: 'shop', COMMISSION_PURCHASE: 'percent', COMMISSION_SALE: 'percent' };
                            const ltColors = { DFIA: '#0ea5e9', INCENTIVE: '#f59e0b' };
                            const ltLabels = { DFIA: 'DFIA License', INCENTIVE: 'Incentive License' };
                            return (
                                <div className="d-flex gap-2">
                                    <span className="badge d-flex align-items-center gap-1" style={{ background: `${dirColors[formData.direction]}20`, color: dirColors[formData.direction], fontWeight: '600', fontSize: '0.78rem', padding: '5px 10px', borderRadius: 6 }}>
                                        <i className={`bi bi-${dirIcons[formData.direction]}`}></i>
                                        {dirLabels[formData.direction]}
                                    </span>
                                    {formData.license_type && (
                                        <span className="badge d-flex align-items-center gap-1" style={{ background: `${ltColors[formData.license_type]}20`, color: ltColors[formData.license_type], fontWeight: '600', fontSize: '0.78rem', padding: '5px 10px', borderRadius: 6 }}>
                                            <i className="bi bi-file-earmark-text"></i>
                                            {ltLabels[formData.license_type]}
                                        </span>
                                    )}
                                </div>
                            );
                        })()}
                    </div>
                </div>
                <div className="card-body" style={{ padding: '24px' }}>
                    {error && (
                        <div className="alert alert-danger d-flex align-items-start gap-2 mb-4">
                            <i className="bi bi-exclamation-triangle-fill flex-shrink-0 mt-1"></i>
                            <div>
                                <strong>Validation Error</strong>
                                <div className="mt-1" style={{ whiteSpace: 'pre-wrap', fontSize: '0.875rem' }}>{error}</div>
                            </div>
                        </div>
                    )}

                    {fetchingAllotment && (
                        <div className="alert alert-info d-flex align-items-center gap-2 mb-4">
                            <span className="spinner-border spinner-border-sm flex-shrink-0"></span>
                            Fetching allotment details...
                        </div>
                    )}

                    {entityName === 'bill-of-entries' && !isEdit && (
                        <section className="surface-card mb-4" style={{ padding: 20 }}>
                            <div className="d-flex align-items-start" style={{ gap: 16, flexWrap: 'wrap' }}>
                                <div
                                    aria-hidden="true"
                                    style={{
                                        width: 44, height: 44, borderRadius: 12,
                                        background: 'var(--indigo-50)', color: 'var(--primary-color)',
                                        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                                        flexShrink: 0,
                                    }}
                                >
                                    <i className="bi bi-file-earmark-pdf" style={{ fontSize: '1.15rem' }}></i>
                                </div>
                                <div style={{ flex: 1, minWidth: 0 }}>
                                    <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-primary)', letterSpacing: '-0.01em' }}>
                                        Import from BOE PDF
                                    </div>
                                    <div className="mt-1" style={{ fontSize: '0.8125rem', color: 'var(--text-secondary)' }}>
                                        Upload an ICEGATE BOE, then click <strong>Fetch</strong> to prefill the form and item rows.
                                    </div>
                                    <div className="d-flex align-items-center mt-3" style={{ gap: 10, flexWrap: 'wrap' }}>
                                        <input
                                            type="file"
                                            accept=".pdf,application/pdf"
                                            id="boe-pdf-input"
                                            className="form-control form-control-sm"
                                            style={{ maxWidth: 340 }}
                                            onChange={(e) => {
                                                setBoePdfFile(e.target.files?.[0] || null);
                                                setBoeParseSummary(null);
                                            }}
                                        />
                                        <button
                                            type="button"
                                            className="btn btn-primary btn-sm"
                                            onClick={handleParseBoePdf}
                                            disabled={!boePdfFile || boeParsing}
                                        >
                                            {boeParsing ? (
                                                <><span className="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Fetching…</>
                                            ) : (
                                                <><i className="bi bi-magic me-1"></i>Fetch</>
                                            )}
                                        </button>
                                    </div>
                                </div>
                            </div>
                            {boeParseSummary && (
                                <div
                                    className="mt-3"
                                    style={{
                                        background: 'var(--surface-sunken)',
                                        border: '1px solid var(--border-subtle)',
                                        borderRadius: 'var(--radius-md)',
                                        padding: '12px 14px',
                                        fontSize: '0.8125rem',
                                    }}
                                >
                                    <div style={{ color: 'var(--text-primary)' }}>
                                        <strong>BE {boeParseSummary.be_number}</strong>
                                        <span style={{ color: 'var(--text-tertiary)' }}> · </span>{boeParseSummary.be_date}
                                        <span style={{ color: 'var(--text-tertiary)' }}> · </span>port <code>{boeParseSummary.port_code}</code>
                                        <span style={{ color: 'var(--text-tertiary)' }}> · </span>1 {boeParseSummary.currency || 'USD'} = ₹{boeParseSummary.exchange_rate}
                                    </div>
                                    {boeParseSummary.company_created && (
                                        <div className="mt-1" style={{ color: '#065F46' }}>
                                            <i className="bi bi-check-circle-fill me-1"></i>
                                            New company created from buyer details ({boeParseSummary.buyer_name}).
                                        </div>
                                    )}
                                    {!boeParseSummary.company_created && boeParseSummary.matched_company_id && (
                                        <div className="mt-1" style={{ color: 'var(--text-secondary)' }}>
                                            <i className="bi bi-check2 me-1"></i>
                                            Matched existing company ({boeParseSummary.buyer_name}).
                                        </div>
                                    )}
                                    {boeParseSummary.matched_allotment_id && (
                                        <div className="mt-1" style={{ color: 'var(--primary-deeper)' }}>
                                            <i className="bi bi-info-circle me-1"></i>
                                            Matched existing allotment <strong>#{boeParseSummary.matched_allotment_id}</strong> by invoice number.
                                        </div>
                                    )}
                                    {boeParseSummary.licences?.length > 0 && (
                                        <details className="mt-2">
                                            <summary style={{ cursor: 'pointer', color: 'var(--text-secondary)' }}>
                                                {boeParseSummary.licences.length} licence row(s) — {boeParseSummary.unmatched} unmatched
                                            </summary>
                                            <ul className="mb-0 mt-2" style={{ paddingLeft: '1.1rem', color: 'var(--text-secondary)' }}>
                                                {boeParseSummary.licences.map((l, i) => {
                                                    const badge = l.match_status === 'matched'
                                                        ? <span style={{ color: '#065F46', marginLeft: 6 }}>✓ prefill item</span>
                                                        : l.match_status === 'license_only'
                                                            ? <span style={{ color: '#92400E', marginLeft: 6 }}>⚠ license found, sl#{l.licence_slno} missing</span>
                                                            : l.match_status === 'license_missing'
                                                                ? <span style={{ color: '#991B1B', marginLeft: 6 }}>✗ license not in DB</span>
                                                                : <span style={{ color: 'var(--text-tertiary)', marginLeft: 6 }}>— no data</span>;
                                                    return (
                                                        <li key={i} style={{ padding: '2px 0' }}>
                                                            License <code>{l.licence_number}</code> sl#{l.licence_slno} · CIF ₹{l.cif_inr} · ${l.cif_fc} · qty {l.qty} {l.uqc}
                                                            {badge}
                                                        </li>
                                                    );
                                                })}
                                            </ul>
                                        </details>
                                    )}
                                </div>
                            )}
                        </section>
                    )}

                    <form onSubmit={handleSubmit} encType="multipart/form-data">
                        {/* Regular Fields */}
                        {(() => {
                            const activeFields = (metadata.form_fields || []).filter(f => !metadata.nested_field_defs?.[f]);

                            const renderOneField = (field, colClass) => {
                                const isTextarea = !colClass && (field.includes("address") || field.includes("description") ||
                                    field.includes("note") || field.includes("comment") ||
                                    field.includes("condition") || field.includes("restriction"));
                                const col = colClass || (isTextarea ? "col-12" : "col-md-4");
                                const fieldMeta = metadata.field_meta?.[field] || {};
                                const label = fieldMeta.label || field.replace(/_/g, " ");
                                const helpText = fieldMeta.help_text;
                                const fieldError = fieldErrors[field];
                                const hasError = fieldError && (Array.isArray(fieldError) ? fieldError.length > 0 : fieldError);
                                return (
                                    <div key={field} className={col}>
                                        <label className="form-label" style={{ fontSize: '0.78rem', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: 6 }}>
                                            {label}{fieldMeta.required && <span className="text-danger ms-1">*</span>}
                                        </label>
                                        {renderField(field)}
                                        {hasError && (
                                            <div className="invalid-feedback d-block" style={{ fontSize: '0.78rem', marginTop: 4 }}>
                                                <i className="bi bi-exclamation-circle me-1"></i>
                                                {Array.isArray(fieldError) ? fieldError.join(', ') : fieldError}
                                            </div>
                                        )}
                                        {helpText && !hasError && (
                                            <small className="form-text d-block mt-1" style={{ color: 'var(--text-secondary)', fontSize: '0.73rem' }}>
                                                <i className="bi bi-info-circle me-1"></i>{helpText}
                                            </small>
                                        )}
                                    </div>
                                );
                            };

                            const sections = ENTITY_SECTIONS[entityName];
                            if (sections) {
                                const sectionedFields = new Set(sections.flatMap(s => s.fields));
                                const remainingFields = activeFields.filter(f => !sectionedFields.has(f));

                                return (
                                    <div className="d-flex flex-column gap-3">
                                        {sections.map(section => {
                                            const visibleFields = section.fields.filter(f => activeFields.includes(f));
                                            if (visibleFields.length === 0) return null;
                                            return (
                                                <div key={section.title} style={{ background: 'var(--bs-gray-50)', borderRadius: '10px', padding: '16px 20px', borderLeft: `3px solid ${section.color}` }}>
                                                    <div style={{ fontSize: '0.68rem', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.08em', color: section.color, marginBottom: '14px', display: 'flex', alignItems: 'center', gap: 6 }}>
                                                        <i className={`bi bi-${section.icon}`}></i> {section.title}
                                                    </div>
                                                    <div className="row g-3">
                                                        {visibleFields.map(f => renderOneField(f, section.cols?.[f]))}
                                                    </div>
                                                </div>
                                            );
                                        })}
                                        {remainingFields.length > 0 && (
                                            <div style={{ background: 'var(--bs-gray-50)', borderRadius: '10px', padding: '16px 20px', borderLeft: '3px solid #9ca3af' }}>
                                                <div style={{ fontSize: '0.68rem', fontWeight: '700', textTransform: 'uppercase', letterSpacing: '0.08em', color: '#6b7280', marginBottom: '14px' }}>
                                                    <i className="bi bi-three-dots me-1"></i> Other Fields
                                                </div>
                                                <div className="row g-3">
                                                    {remainingFields.map(f => renderOneField(f))}
                                                </div>
                                            </div>
                                        )}
                                    </div>
                                );
                            }

                            return (
                                <div className="row g-3">
                                    {activeFields.map(f => renderOneField(f))}
                                </div>
                            );
                        })()}

                        {/* Nested Fields */}
                        {entityName !== 'allotments' && Object.entries(metadata.nested_field_defs || {}).length > 0 && (
                            <div className="mt-4">
                                <div style={{ height: 2, background: `linear-gradient(90deg, ${entityColor} 0%, transparent 100%)`, marginBottom: 20, borderRadius: 1 }}></div>
                                {(entityName === 'licenses' || entityName === 'trades') ? (() => {
                                    const allNestedEntries = Object.entries(metadata.nested_field_defs || {});
                                    // For trades, filter tabs based on license_type
                                    const nestedEntries = entityName === 'trades'
                                        ? allNestedEntries.filter(([key]) => {
                                            const lt = formData.license_type;
                                            if (!lt) return true;
                                            if (lt === 'DFIA') return key !== 'incentive_lines';
                                            if (lt === 'INCENTIVE') return key !== 'lines';
                                            return true;
                                        })
                                        : allNestedEntries;
                                    const activeTab = (activeNestedTab && nestedEntries.some(([k]) => k === activeNestedTab))
                                        ? activeNestedTab
                                        : nestedEntries[0]?.[0];
                                    const tabIcons = {
                                        export_license: 'box-arrow-up',
                                        import_license: 'box-arrow-in-down',
                                        license_documents: 'file-earmark',
                                        lines: 'list-ul',
                                        incentive_lines: 'award',
                                        payments: 'cash-stack',
                                    };
                                    const tabLabels = {
                                        export_license: 'Export Items',
                                        import_license: 'Import Items',
                                        license_documents: 'Documents',
                                        lines: 'Trade Lines',
                                        incentive_lines: 'Incentive Lines',
                                        payments: 'Payments',
                                    };
                                    return (
                                        <>
                                            <ul className="nav nav-tabs" style={{ borderBottom: '2px solid #e5e7eb', gap: 2, marginBottom: 0 }}>
                                                {nestedEntries.map(([nestedKey]) => {
                                                    const count = (formData[nestedKey] || []).length;
                                                    const isActive = activeTab === nestedKey;
                                                    const hasErrors = (fieldErrors[nestedKey] || []).some(Boolean);
                                                    const label = tabLabels[nestedKey] || nestedKey.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
                                                    return (
                                                        <li key={nestedKey} className="nav-item">
                                                            <button
                                                                type="button"
                                                                className={`nav-link d-flex align-items-center gap-2 ${isActive ? 'active' : ''}`}
                                                                onClick={() => setActiveNestedTab(nestedKey)}
                                                                style={{ fontSize: '0.83rem', fontWeight: isActive ? '600' : '500', padding: '8px 16px', color: isActive ? entityColor : '#6b7280', borderColor: isActive ? `${entityColor} ${entityColor} white` : 'transparent', borderRadius: '8px 8px 0 0' }}
                                                            >
                                                                <i className={`bi bi-${tabIcons[nestedKey] || 'table'}`}></i>
                                                                {label}
                                                                {count > 0 && (
                                                                    <span className="badge rounded-pill" style={{ backgroundColor: isActive ? entityColor : '#e5e7eb', color: isActive ? 'white' : '#6b7280', fontSize: '0.7rem', padding: '2px 7px' }}>
                                                                        {count}
                                                                    </span>
                                                                )}
                                                                {hasErrors && <i className="bi bi-exclamation-circle-fill text-danger" style={{ fontSize: '0.75rem' }}></i>}
                                                            </button>
                                                        </li>
                                                    );
                                                })}
                                            </ul>
                                            <div style={{ border: '1px solid #e5e7eb', borderTop: 'none', borderRadius: '0 0 10px 10px', padding: '20px 16px', background: 'white' }}>
                                                {nestedEntries.map(([nestedKey, nestedDef]) => activeTab === nestedKey ? (
                                                    <NestedFieldArray
                                                        key={nestedKey}
                                                        label={nestedKey.replace(/_/g, " ")}
                                                        fields={nestedDef}
                                                        value={formData[nestedKey] || []}
                                                        onChange={(value) => handleChange(nestedKey, value)}
                                                        fieldKey={nestedKey}
                                                        onFetchImports={handleFetchImports}
                                                        updatedFields={updatedFields}
                                                        errors={fieldErrors[nestedKey] || []}
                                                        entityName={entityName}
                                                        formData={formData}
                                                    />
                                                ) : null)}
                                            </div>
                                        </>
                                    );
                                })() : Object.entries(metadata.nested_field_defs || {}).map(([nestedKey, nestedDef]) => (
                                    <NestedFieldArray
                                        key={nestedKey}
                                        label={nestedKey.replace(/_/g, " ")}
                                        fields={nestedDef}
                                        value={formData[nestedKey] || []}
                                        onChange={(value) => handleChange(nestedKey, value)}
                                        fieldKey={nestedKey}
                                        onFetchImports={entityName === "licenses" ? handleFetchImports : undefined}
                                        updatedFields={updatedFields}
                                        errors={fieldErrors[nestedKey] || []}
                                        entityName={entityName}
                                        formData={formData}
                                    />
                                ))}
                            </div>
                        )}

                        {/* Action Buttons */}
                        <div className="d-flex align-items-center gap-2 mt-4 pt-3" style={{ borderTop: '1px solid #e5e7eb' }}>
                            <button
                                type="submit"
                                className="btn btn-primary"
                                disabled={saving}
                                style={{
                                    padding: '10px 28px', fontWeight: '600',
                                    background: `linear-gradient(135deg, ${entityColor}, ${entityColor}cc)`,
                                    border: 'none', borderRadius: '8px'
                                }}
                            >
                                {saving ? (
                                    <><span className="spinner-border spinner-border-sm me-2"></span>Saving...</>
                                ) : (
                                    <><i className="bi bi-check-circle me-2"></i>{isEdit ? 'Update' : 'Create'}</>
                                )}
                            </button>

                            {entityName === 'licenses' && isEdit && (
                                <button
                                    type="button"
                                    className="btn btn-outline-info"
                                    onClick={() => { setSavedLicenseId(id); setShowBalanceModal(true); }}
                                    disabled={saving}
                                    style={{ padding: '10px 20px', fontWeight: '500', borderRadius: '8px' }}
                                >
                                    <i className="bi bi-eye me-2"></i>View Balance
                                </button>
                            )}

                            <button
                                type="button"
                                className="btn btn-outline-secondary"
                                onClick={() => {
                                    if (isModal && onClose) { onClose(); return; }
                                    navigateToList(navigate, entityName, { preserveFilters: true });
                                }}
                                disabled={saving}
                                style={{ padding: '10px 20px', fontWeight: '500', borderRadius: '8px' }}
                            >
                                <i className="bi bi-x-lg me-2"></i>Cancel
                            </button>
                        </div>
                    </form>
                </div>
            </div>

            {/* License Balance Modal */}
            {entityName === 'licenses' && (
                <LicenseBalanceModal
                    show={showBalanceModal}
                    onHide={handleModalClose}
                    licenseId={savedLicenseId}
                />
            )}
        </div>
    );
}
