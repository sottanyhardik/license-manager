import {useEffect, useState} from "react";
import {useNavigate, useParams, useLocation} from "react-router-dom";
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

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSaving(true);
        setError("");

        try {
            const apiPath = entityName === 'licenses' ? `/licenses/` : `/masters/${entityName}/`;
            if (isEdit) {
                await api.patch(`${apiPath}${id}/`, formData);
            } else {
                await api.post(apiPath, formData);
            }
            const redirectPath = entityName === 'licenses' ? '/licenses' : `/masters/${entityName}`;
            navigate(redirectPath);
        } catch (err) {
            setError(
                err.response?.data?.detail ||
                JSON.stringify(err.response?.data) ||
                "Failed to save record"
            );
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
                <DatePicker
                    selected={parseDate(value)}
                    onChange={(date) => handleChange(fieldName, formatDateForAPI(date))}
                    dateFormat="dd-MM-yyyy"
                    className="form-control"
                    placeholderText="Select date"
                    isClearable
                    showYearDropdown
                    showMonthDropdown
                    dropdownMode="select"
                />
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
                <div className="col-lg-10 mx-auto">
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
                                            <div key={field} className={`${colClass} mb-3`}>
                                                <label className="form-label text-capitalize">
                                                    {field.replace(/_/g, " ")}
                                                </label>
                                                {renderField(field)}
                                            </div>
                                        );
                                    })}
                                </div>

                                {/* Nested Fields */}
                                {Object.entries(metadata.nested_field_defs || {}).map(([nestedKey, nestedDef]) => (
                                    <NestedFieldArray
                                        key={nestedKey}
                                        label={nestedKey.replace(/_/g, " ")}
                                        fields={nestedDef}
                                        value={formData[nestedKey] || []}
                                        onChange={(value) => handleChange(nestedKey, value)}
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
