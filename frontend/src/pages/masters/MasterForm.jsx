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
        (location.pathname.includes('/trades') ? 'trades' : null);
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
            } else {
                apiPath = `/masters/${entityName}/`;
            }

            // Use GET to fetch metadata (custom structure with form_fields, field_meta, etc.)
            const {data} = await api.get(apiPath);
            setMetadata({
                form_fields: data.form_fields || [],
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
            toast.error("Failed to load form metadata");
        }
    };

    const fetchRecord = async () => {
        setLoading(true);
        try {
            let apiPath;
            if (entityName === 'licenses' || entityName === 'allotments' || entityName === 'bill-of-entries' || entityName === 'trades') {
                apiPath = `/${entityName}/${recordId}/`;
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

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSaving(true);
        setError("");
        setFieldErrors({});

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
            } else {
                redirectPath = `/masters/${entityName}`;
            }
            navigate(redirectPath);
        } catch (err) {
            // Handle field-level errors
            if (err.response?.data && typeof err.response.data === 'object') {
                setFieldErrors(err.response.data);

                // Create a user-friendly error message
                const errorMessages = [];

                // Helper function to process errors recursively
                const processErrors = (errors, fieldPath = '') => {
                    if (Array.isArray(errors)) {
                        errors.forEach((error, index) => {
                            if (typeof error === 'object' && error !== null) {
                                // Handle nested field errors (like license_documents[0].type)
                                if (error.non_field_errors) {
                                    errorMessages.push(`${fieldPath}: ${error.non_field_errors.join(', ')}`);
                                }
                                Object.entries(error).forEach(([key, value]) => {
                                    if (key !== 'non_field_errors') {
                                        const nestedPath = fieldPath ? `${fieldPath}[${index}].${key}` : `${key}[${index}]`;
                                        processErrors(value, nestedPath);
                                    }
                                });
                            } else if (typeof error === 'string') {
                                const displayPath = fieldPath || 'Form';
                                errorMessages.push(`${displayPath}: ${error}`);
                            }
                        });
                    } else if (typeof errors === 'string') {
                        const displayPath = fieldPath || 'Form';
                        errorMessages.push(`${displayPath}: ${errors}`);
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
                    ? errorMessages.join('\n')
                    : "Validation errors occurred. Please check the form.";
                setError(errorMsg);
                toast.error(errorMsg);
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

        // Handle date fields with DatePicker
        if (fieldMeta.type === "date" || fieldName.includes("date") || fieldName.includes("_at") || fieldName.includes("_on")) {
            return (
                <div className="w-100">
                    <DatePicker
                        selected={parseDate(value)}
                        onChange={(date) => handleChange(fieldName, formatDateForAPI(date))}
                        dateFormat="dd-MM-yyyy"
                        className="form-control"
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
            return (
                <input
                    type="file"
                    className="form-control"
                    onChange={(e) => handleChange(fieldName, e.target.files[0])}
                />
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
                    className="form-control"
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
                    className="form-control"
                    value={value}
                    onChange={(e) => handleChange(fieldName, e.target.value)}
                />
            );
        }

        // Default text input
        return (
            <input
                type="text"
                className="form-control"
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
        <div className="container mt-4">
            <div className="row">
                <div className="col-lg-12 mx-auto">
                    <div className="card">
                        <div className="card-header bg-primary text-white">
                            <h4 className="mb-0">
                                {isEdit ? "Edit" : "Create"} {entityTitle}
                            </h4>
                        </div>

                        <div className="card-body">
                            {error && (
                                <div className="alert alert-danger">
                                    {error}
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

                                        return (
                                            <div key={field} className={`${colClass}`}>
                                                <div className="form-group-material">
                                                    <label className="form-label">
                                                        {label}
                                                        {fieldMeta.required && <span className="text-danger">*</span>}
                                                    </label>
                                                    {renderField(field)}
                                                    {helpText && (
                                                        <small className="form-text text-muted d-block mt-1">
                                                            {helpText}
                                                        </small>
                                                    )}
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                                <hr/>
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
                                <div className="mt-4">
                                    <button
                                        type="submit"
                                        className="btn btn-primary me-2"
                                        disabled={saving}
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
                                        >
                                            <i className="bi bi-eye me-2"></i>
                                            View Balance
                                        </button>
                                    )}

                                    <button
                                        type="button"
                                        className="btn btn-secondary"
                                        onClick={() => {
                                            if (isModal && onClose) {
                                                onClose();
                                                return;
                                            }

                                            // Set flag to restore filters when canceling
                                            sessionStorage.setItem('allotmentListFilters', JSON.stringify({
                                                returnTo: 'list',
                                                timestamp: new Date().getTime()
                                            }));

                                            if (entityName === 'licenses') {
                                                navigate('/licenses');
                                            } else if (entityName === 'allotments') {
                                                navigate('/allotments');
                                            } else if (entityName === 'bill-of-entries') {
                                                navigate('/bill-of-entries');
                                            } else if (entityName === 'trades') {
                                                navigate('/trades');
                                            } else {
                                                navigate(`/masters/${entityName}`);
                                            }
                                        }}
                                        disabled={saving}
                                    >
                                        Cancel
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
