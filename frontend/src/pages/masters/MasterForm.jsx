import {useEffect, useState} from "react";
import {useLocation, useNavigate, useParams} from "react-router-dom";
import api from "../../api/axios";
import NestedFieldArray from "./NestedFieldArray";
import HybridSelect from "../../components/HybridSelect";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";

/**
 * Generic Master Form for Create/Edit
 *
 * URL Pattern:
 * - Create: /masters/:entity/create OR /licenses/create
 * - Edit: /masters/:entity/:id/edit OR /licenses/:id/edit
 */
export default function MasterForm() {
    const {entity, id} = useParams();
    const location = useLocation();
    const navigate = useNavigate();

    // Determine the actual entity name - either from params or from path
    const entityName = entity || (location.pathname.includes('/licenses') ? 'licenses' : null);
    const isEdit = Boolean(id);

    const [formData, setFormData] = useState({});
    const [metadata, setMetadata] = useState({});
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");
    const [fieldErrors, setFieldErrors] = useState({}); // Track field-level errors
    const [updatedFields, setUpdatedFields] = useState({}); // Track updated fields for highlighting

    // Helper function to parse date from YYYY-MM-DD to Date object
    const parseDate = (dateString) => {
        if (!dateString) return null;
        const date = new Date(dateString);
        return isNaN(date.getTime()) ? null : date;
    };

    // Helper function to format Date object to YYYY-MM-DD for API
    const formatDateForAPI = (date) => {
        if (!date) return null;
        return date.toISOString().split('T')[0];
    };

    // Fetch metadata and existing data
    useEffect(() => {
        if (!entityName) return;
        fetchMetadata();
        if (isEdit) {
            fetchRecord();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [entityName, id]);

    const fetchMetadata = async () => {
        try {
            const apiPath = entityName === 'licenses' ? '/licenses/' : `/masters/${entityName}/`;
            const {data} = await api.options(apiPath);
            setMetadata({
                form_fields: data.form_fields || [],
                nested_field_defs: data.nested_field_defs || {},
                field_meta: data.field_meta || {}
            });
        } catch (err) {
            console.error("Error fetching metadata:", err);
        }
    };

    const fetchRecord = async () => {
        setLoading(true);
        try {
            const apiPath = entityName === 'licenses' ? `/licenses/${id}/` : `/masters/${entityName}/${id}/`;
            const {data} = await api.get(apiPath);
            setFormData(data);
        } catch (err) {
            setError(err.response?.data?.detail || "Failed to load record");
        } finally {
            setLoading(false);
        }
    };

    const handleChange = (field, value) => {
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
                console.error("Error calculating expiry date:", err);
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
            alert(message.join('. ') || "No changes made");

        } catch (err) {
            console.error("Error fetching SION imports:", err);
            alert(err.response?.data?.detail || "Failed to fetch import items from SION");
        }
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSaving(true);
        setError("");
        setFieldErrors({});

        try {
            const apiPath = entityName === 'licenses' ? `/licenses/` : `/masters/${entityName}/`;

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
                    } else if (value !== null && value !== undefined && value !== '') {
                        formDataObj.append(fullKey, value);
                    }
                };

                Object.entries(formData).forEach(([key, value]) => {
                    appendToFormData(key, value);
                });

                if (isEdit) {
                    response = await api.patch(`${apiPath}${id}/`, formDataObj, {
                        headers: { 'Content-Type': 'multipart/form-data' }
                    });
                } else {
                    response = await api.post(apiPath, formDataObj, {
                        headers: { 'Content-Type': 'multipart/form-data' }
                    });
                }
            } else {
                // Use regular JSON for non-file data
                if (isEdit) {
                    response = await api.patch(`${apiPath}${id}/`, formData);
                } else {
                    response = await api.post(apiPath, formData);
                }
            }

            const redirectPath = entityName === 'licenses' ? '/licenses' : `/masters/${entityName}`;
            navigate(redirectPath);
        } catch (err) {
            console.error("Save error:", err.response?.data);

            // Handle field-level errors
            if (err.response?.data && typeof err.response.data === 'object') {
                setFieldErrors(err.response.data);

                // Create a user-friendly error message
                const errorMessages = [];
                Object.entries(err.response.data).forEach(([field, errors]) => {
                    if (Array.isArray(errors)) {
                        errors.forEach(error => {
                            if (typeof error === 'object' && error.non_field_errors) {
                                errorMessages.push(`${field}: ${error.non_field_errors.join(', ')}`);
                            } else {
                                errorMessages.push(`${field}: ${error}`);
                            }
                        });
                    }
                });

                setError(errorMessages.length > 0 ? errorMessages.join('\n') : "Validation errors occurred. Please check the form.");
            } else {
                setError(
                    err.response?.data?.detail ||
                    "Failed to save record"
                );
            }
        } finally {
            setSaving(false);
        }
    };

    const renderField = (fieldName) => {
        const fieldMeta = metadata.field_meta?.[fieldName] || {};
        const value = formData[fieldName] || "";

        // Handle date fields with DatePicker
        if (fieldName.includes("date") || fieldName.includes("_at") || fieldName.includes("_on")) {
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
            // Check if it's a many-to-many field (value is array)
            const isMulti = Array.isArray(value);

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
        if (fieldName.includes("price") || fieldName.includes("rate") || fieldName.includes("quantity") || fieldName.includes("duty")) {
            return (
                <input
                    type="number"
                    step="0.01"
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

                            <form onSubmit={handleSubmit}>
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

                                        return (
                                            <div key={field} className={`${colClass}`}>
                                                <div className="form-group-material">
                                                    <label className="form-label">
                                                        {field.replace(/_/g, " ")}
                                                    </label>
                                                    {renderField(field)}
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                                <hr/>
                                {/* Nested Fields */}
                                {Object.entries(metadata.nested_field_defs || {}).map(([nestedKey, nestedDef]) => (
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
                                    <button
                                        type="button"
                                        className="btn btn-secondary"
                                        onClick={() => navigate(entityName === 'licenses' ? '/licenses' : `/masters/${entityName}`)}
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
        </div>
    );
}
