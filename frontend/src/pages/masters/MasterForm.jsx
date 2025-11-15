import {useEffect, useState} from "react";
import {useNavigate, useParams} from "react-router-dom";
import api from "../../api/axios";
import NestedFieldArray from "./NestedFieldArray";
import HybridSelect from "../../components/HybridSelect";

/**
 * Generic Master Form for Create/Edit
 *
 * URL Pattern:
 * - Create: /masters/:entity/create
 * - Edit: /masters/:entity/:id/edit
 */
export default function MasterForm() {
    const {entity, id} = useParams();
    const navigate = useNavigate();
    const isEdit = Boolean(id);

    const [formData, setFormData] = useState({});
    const [metadata, setMetadata] = useState({});
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState("");

    // Fetch metadata and existing data
    useEffect(() => {
        fetchMetadata();
        if (isEdit) {
            fetchRecord();
        }
    }, [entity, id]);

    const fetchMetadata = async () => {
        try {
            const {data} = await api.options(`/masters/${entity}/`);
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
            const {data} = await api.get(`/masters/${entity}/${id}/`);
            setFormData(data);
        } catch (err) {
            setError(err.response?.data?.detail || "Failed to load record");
        } finally {
            setLoading(false);
        }
    };

    const handleChange = (field, value) => {
        setFormData(prev => ({
            ...prev,
            [field]: value
        }));
    };

    const handleSubmit = async (e) => {
        e.preventDefault();
        setSaving(true);
        setError("");

        try {
            if (isEdit) {
                await api.patch(`/masters/${entity}/${id}/`, formData);
            } else {
                await api.post(`/masters/${entity}/`, formData);
            }
            navigate(`/masters/${entity}`);
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

        // Handle boolean fields
        if (typeof value === "boolean") {
            return (
                <div className="form-check">
                    <input
                        type="checkbox"
                        className="form-check-input"
                        checked={value}
                        onChange={(e) => handleChange(fieldName, e.target.checked)}
                    />
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

    const entityTitle = entity
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
                                {/* Regular Fields */}
                                {metadata.form_fields?.map((field) => {
                                    // Skip nested fields (they're rendered separately below)
                                    if (metadata.nested_field_defs?.[field]) {
                                        return null;
                                    }

                                    return (
                                        <div key={field} className="mb-3">
                                            <label className="form-label text-capitalize">
                                                {field.replace(/_/g, " ")}
                                            </label>
                                            {renderField(field)}
                                        </div>
                                    );
                                })}

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
                                        onClick={() => navigate(`/masters/${entity}`)}
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
