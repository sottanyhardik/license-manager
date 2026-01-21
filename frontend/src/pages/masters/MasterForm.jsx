import {useEffect, useState} from "react";
import {useLocation, useNavigate, useParams} from "react-router-dom";
import { toast } from 'react-toastify';
import api from "../../api/axios";
import NestedFieldArray from "./NestedFieldArray";
import HybridSelect from "../../components/HybridSelect";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import {markNewItemCreated} from "../../utils/filterPersistence";
import {formatDateForInput} from "../../utils/dateFormatter";
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

    // Enable browser back button support with filter preservation
    useBackButton(entityName, !isModal);

    // Helper function to parse date from YYYY-MM-DD to Date object
    const parseDate = (dateString) => {
        if (!dateString) return null;

        // If it's already a Date object, return it
        if (dateString instanceof Date) {
            return isNaN(dateString.getTime()) ? null : dateString;
        }

        // Parse string date
        if (typeof dateString === 'string') {
            // Split the date string to avoid timezone issues
            const parts = dateString.split('-');
            if (parts.length === 3) {
                let year, month, day;

                // Check if it's YYYY-MM-DD format (year is 4 digits)
                if (parts[0].length === 4) {
                    year = parseInt(parts[0], 10);
                    month = parseInt(parts[1], 10) - 1; // Month is 0-indexed
                    day = parseInt(parts[2], 10);
                }
                // Check if it's dd-MM-yyyy format (first part is 1-2 digits)
                else if (parts[2].length === 4) {
                    day = parseInt(parts[0], 10);
                    month = parseInt(parts[1], 10) - 1; // Month is 0-indexed
                    year = parseInt(parts[2], 10);
                }
                // Unknown format, try default parsing
                else {
                    const date = new Date(dateString);
                    return isNaN(date.getTime()) ? null : date;
                }

                // Create date at noon local time to avoid timezone boundary issues
                const date = new Date(year, month, day, 12, 0, 0);
                return isNaN(date.getTime()) ? null : date;
            }
        }

        const date = new Date(dateString);
        return isNaN(date.getTime()) ? null : date;
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
                apiPath = `/${entityName}/`;
            } else if (entityName === 'incentive-licenses') {
                apiPath = `/incentive-licenses/`;
            } else {
                apiPath = `/masters/${entityName}/`;
            }

            console.log('[MasterForm] Fetching metadata from:', apiPath, 'for entity:', entityName);

            // Use GET to fetch metadata (custom structure with form_fields, field_meta, etc.)
            const {data} = await api.get(apiPath);

            console.log('[MasterForm] Metadata response:', {
                form_fields: data.form_fields,
                field_meta_keys: Object.keys(data.field_meta || {}),
                full_response_keys: Object.keys(data)
            });

            setMetadata({
                form_fields: data.form_fields || data.fields || [],
                nested_field_defs: data.nested_field_defs || {},
                field_meta: data.field_meta || {}
            });

            // Apply default values from field_meta when creating new record (not editing)
            if (!isEdit && data.field_meta) {
                const defaults = {};
                Object.keys(data.field_meta).forEach(fieldName => {
                    const fieldConfig = data.field_meta[fieldName];
                    if (fieldConfig.default !== undefined && fieldConfig.default !== null) {
                        defaults[fieldName] = fieldConfig.default;
                    }
                });

                // Only set defaults if we found any
                if (Object.keys(defaults).length > 0) {
                    setFormData(prevData => ({...prevData, ...defaults}));
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
                apiPath = `/${entityName}/${recordId}/`;
            } else if (entityName === 'incentive-licenses') {
                apiPath = `/incentive-licenses/${recordId}/`;
            } else {
                apiPath = `/masters/${entityName}/${recordId}/`;
            }
            const {data} = await api.get(apiPath);
            setFormData(data);
        } catch (err) {
            setError(err.response?.data?.detail || "Failed to load record");
        } finally {
            setLoading(false);
        }
    };

    const handleChange = async (field, value) => {
        // DEBUG: Log license_documents changes
        if (field === 'license_documents') {
            console.log('[MasterForm.handleChange] license_documents updated:', value);
        }

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
                        const {data} = await api.get(`/bill-of-entries/fetch-allotment-details/?allotment_id=${allotmentId}`);

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
                    if (firstExchangeRate) {
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
                        updates.item_details = allItemDetails;
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
            const {data: sionData} = await api.get(`/masters/sion-classes/${exportItem.norm_class}/`);

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
                    const newItem = {
                        serial_number: targetSerialNumber,
                        hs_code: sionImport.hsn_code || null,
                        description: sionImport.description || "",
                        duty_type: sionImport.duty_type || "Basic",
                        quantity: sionImport.quantity || 0,
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
        const requiredFields = [];

        // Collect required fields from metadata
        if (metadata.form_fields) {
            metadata.form_fields.forEach(fieldName => {
                const fieldMeta = metadata.field_meta?.[fieldName] || {};
                if (fieldMeta.required) {
                    requiredFields.push({
                        name: fieldName,
                        label: fieldMeta.label || fieldName.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
                    });
                }
            });
        }

        // Validate required fields
        requiredFields.forEach(field => {
            const value = formData[field.name];
            if (value === null || value === undefined || value === '') {
                errors[field.name] = [`${field.label} is required`];
            }
        });

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

            // Validate export items
            if (formData.export_license && Array.isArray(formData.export_license)) {
                const exportErrors = [];
                formData.export_license.forEach((item, index) => {
                    const itemErrors = {};

                    // HS Code is not required for export items (can be blank)
                    // Removed: if (!item.hs_code) { itemErrors.hs_code = ['HS Code is required']; }

                    if (!item.description || item.description.trim() === '') {
                        itemErrors.description = ['Description is required'];
                    }

                    // Net quantity can be 0 or greater (including 0)
                    const netQty = parseFloat(item.net_quantity);
                    if (item.net_quantity === '' || item.net_quantity === null || item.net_quantity === undefined) {
                        itemErrors.net_quantity = ['Net quantity is required'];
                    } else if (isNaN(netQty) || netQty < 0) {
                        itemErrors.net_quantity = ['Net quantity cannot be negative'];
                    }

                    if (!item.unit) {
                        itemErrors.unit = ['Unit is required'];
                    }

                    if (Object.keys(itemErrors).length > 0) {
                        exportErrors[index] = itemErrors;
                    }
                });
                if (exportErrors.length > 0) {
                    errors.export_license = exportErrors;
                }
            }

            // Validate import items
            if (formData.import_license && Array.isArray(formData.import_license)) {
                const importErrors = [];
                formData.import_license.forEach((item, index) => {
                    const itemErrors = {};

                    if (!item.hs_code) {
                        itemErrors.hs_code = ['HS Code is required'];
                    }
                    if (!item.description || item.description.trim() === '') {
                        itemErrors.description = ['Description is required'];
                    }
                    if (!item.serial_number && item.serial_number !== 0) {
                        itemErrors.serial_number = ['Serial number is required'];
                    }
                    if (!item.unit) {
                        itemErrors.unit = ['Unit is required'];
                    }

                    if (Object.keys(itemErrors).length > 0) {
                        importErrors[index] = itemErrors;
                    }
                });
                if (importErrors.length > 0) {
                    errors.import_license = importErrors;
                }
            }

            // Validate documents (if adding new ones)
            if (formData.license_documents && Array.isArray(formData.license_documents)) {
                const docErrors = [];
                formData.license_documents.forEach((doc, index) => {
                    const itemErrors = {};

                    // Only validate if file is provided (new document)
                    if (doc.file && doc.file instanceof File) {
                        if (!doc.type || doc.type.trim() === '') {
                            itemErrors.type = ['Document type is required'];
                        }
                    }

                    if (Object.keys(itemErrors).length > 0) {
                        docErrors[index] = itemErrors;
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
            // DEBUG: Log license_documents before sending
            if (entityName === 'licenses' && formData.license_documents) {
                console.log('=== DEBUG: license_documents before sending ===');
                console.log('Raw formData.license_documents:', formData.license_documents);
                formData.license_documents.forEach((doc, index) => {
                    console.log(`Document ${index}:`, {
                        type: doc.type,
                        typeOf: typeof doc.type,
                        file: doc.file,
                        fileType: doc.file ? doc.file.constructor.name : 'null',
                        allKeys: Object.keys(doc)
                    });
                });
            }

            let apiPath;
            if (entityName === 'licenses' || entityName === 'allotments' || entityName === 'bill-of-entries' || entityName === 'trades') {
                apiPath = `/${entityName}/`;
            } else if (entityName === 'incentive-licenses') {
                apiPath = `/incentive-licenses/`;
            } else {
                apiPath = `/masters/${entityName}/`;
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

                // DEBUG: Log FormData contents for license_documents
                if (entityName === 'licenses') {
                    console.log('=== DEBUG: FormData contents ===');
                    for (let [key, value] of formDataObj.entries()) {
                        if (key.includes('license_documents')) {
                            console.log(key, ':', value);
                        }
                    }
                }

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
                setFieldErrors(err.response.data);

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
                const errorMsg = err.response?.data?.detail || "Failed to save record";
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

    if (loading) {
        return (
            <div className="container mt-4">
                <div className="text-center py-5">
                    <div className="spinner-border text-primary"></div>
                    <p className="mt-2">Loading...</p>
                </div>
            </div>
        );
    }

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
                <h1 style={{ fontSize: '2rem', fontWeight: '700', marginBottom: '0' }}>
                    <i className={`bi ${isEdit ? 'bi-pencil-square' : 'bi-plus-circle'} me-3`}></i>
                    {isEdit ? "Edit" : "Create"} {entityTitle}
                </h1>
            </div>

            <div className="row">
                <div className="col-lg-12 mx-auto">
                    <div className="card border-0 shadow-sm" style={{ borderRadius: '12px' }}>
                        <div className="card-body" style={{ padding: '32px' }}>
                            {error && (
                                <div className="alert alert-danger">
                                    <strong>
                                        <i className="bi bi-exclamation-triangle-fill me-2"></i>
                                        Validation Error
                                    </strong>
                                    <div className="mt-2" style={{whiteSpace: 'pre-wrap'}}>
                                        {error}
                                    </div>
                                </div>
                            )}

                            {fetchingAllotment && (
                                <div className="alert alert-info">
                                    <span className="spinner-border spinner-border-sm me-2"></span>
                                    Fetching allotment details...
                                </div>
                            )}

                            <form onSubmit={handleSubmit} encType="multipart/form-data">
                                {/* Regular Fields - 3 columns layout */}
                                <div className="row">
                                    {metadata.form_fields?.map((field) => {
                                        // Skip nested fields (they're rendered separately below)
                                        if (metadata.nested_field_defs?.[field]) {
                                            return null;
                                        }

                                        // Full width for textarea fields
                                        const isTextarea = field.includes("address") || field.includes("description") ||
                                            field.includes("note") || field.includes("comment") ||
                                            field.includes("condition") || field.includes("restriction");

                                        const colClass = isTextarea ? "col-12" : "col-md-4";

                                        const fieldMeta = metadata.field_meta?.[field] || {};
                                        const label = fieldMeta.label || field.replace(/_/g, " ");
                                        const helpText = fieldMeta.help_text;

                                        const fieldError = fieldErrors[field];
                                        const hasError = fieldError && (Array.isArray(fieldError) ? fieldError.length > 0 : fieldError);

                                        return (
                                            <div key={field} className={`${colClass} mb-3`}>
                                                <div className="form-group-material">
                                                    <label className="form-label" style={{
                                                        fontWeight: '500',
                                                        color: '#374151',
                                                        marginBottom: '8px',
                                                        fontSize: '0.875rem'
                                                    }}>
                                                        {label}
                                                        {fieldMeta.required && <span className="text-danger ms-1">*</span>}
                                                    </label>
                                                    {renderField(field)}
                                                    {hasError && (
                                                        <div className="invalid-feedback d-block" style={{
                                                            fontSize: '0.8rem',
                                                            marginTop: '6px'
                                                        }}>
                                                            <i className="bi bi-exclamation-circle me-1"></i>
                                                            {Array.isArray(fieldError) ? fieldError.join(', ') : fieldError}
                                                        </div>
                                                    )}
                                                    {helpText && !hasError && (
                                                        <small className="form-text d-block mt-1" style={{
                                                            color: '#6b7280',
                                                            fontSize: '0.75rem'
                                                        }}>
                                                            <i className="bi bi-info-circle me-1"></i>
                                                            {helpText}
                                                        </small>
                                                    )}
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                                <hr style={{ margin: '32px 0', border: 'none', borderTop: '2px solid #e5e7eb' }}/>
                                {/* Nested Fields */}
                                {/* Don't show nested fields for allotments in form - use action page instead */}
                                {entityName !== 'allotments' && Object.entries(metadata.nested_field_defs || {}).map(([nestedKey, nestedDef]) => (
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
                                {/* Action Buttons */}
                                <div className="mt-4 pt-3" style={{ borderTop: '1px solid #e5e7eb' }}>
                                    <button
                                        type="submit"
                                        className="btn btn-primary me-2"
                                        disabled={saving}
                                        style={{
                                            padding: '12px 32px',
                                            fontWeight: '600',
                                            fontSize: '1rem',
                                            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                                            border: 'none'
                                        }}
                                    >
                                        {saving ? (
                                            <>
                                                <span className="spinner-border spinner-border-sm me-2"></span>
                                                Saving...
                                            </>
                                        ) : (
                                            <>
                                                <i className="bi bi-check-circle me-2"></i>
                                                {isEdit ? "Update" : "Create"}
                                            </>
                                        )}
                                    </button>

                                    {/* License Balance Actions button - only show for licenses in edit mode */}
                                    {entityName === 'licenses' && isEdit && (
                                        <button
                                            type="button"
                                            className="btn btn-info me-2"
                                            onClick={() => {
                                                setSavedLicenseId(id);
                                                setShowBalanceModal(true);
                                            }}
                                            disabled={saving}
                                            style={{ padding: '12px 24px', fontWeight: '500' }}
                                        >
                                            <i className="bi bi-eye me-2"></i>
                                            View Balance
                                        </button>
                                    )}

                                    <button
                                        type="button"
                                        className="btn btn-outline-secondary"
                                        onClick={() => {
                                            if (isModal && onClose) {
                                                onClose();
                                                return;
                                            }

                                            // Navigate back to list with filter restoration
                                            navigateToList(navigate, entityName, { preserveFilters: true });
                                        }}
                                        disabled={saving}
                                        style={{ padding: '12px 24px', fontWeight: '500' }}
                                    >
                                        <i className="bi bi-arrow-left me-2"></i>
                                        Back to List
                                    </button>
                                </div>
                            </form>
                        </div>
                    </div>
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
