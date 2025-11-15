import {useState} from "react";
import AsyncSelectField from "../../components/AsyncSelectField";

/**
 * NestedFieldArray Component
 *
 * Handles nested arrays like export_norm, import_norm for SionNormClass
 *
 * Props:
 * - label: Display label for the nested field array
 * - fields: Array of field definitions from backend
 * - value: Current array of nested objects
 * - onChange: Callback function(newArray)
 */
export default function NestedFieldArray({label, fields = [], value = [], onChange}) {

    const handleAdd = () => {
        const newItem = {};
        fields.forEach(field => {
            newItem[field.name] = "";
        });
        onChange([...value, newItem]);
    };

    const handleRemove = (index) => {
        const newArray = value.filter((_, i) => i !== index);
        onChange(newArray);
    };

    const handleChange = (index, fieldName, fieldValue) => {
        const newArray = [...value];
        newArray[index] = {
            ...newArray[index],
            [fieldName]: fieldValue
        };
        onChange(newArray);
    };

    const renderNestedField = (field, item, index) => {
        const fieldValue = item[field.name] || "";

        // Handle FK select fields using AsyncSelectField
        if (field.fk_endpoint || field.endpoint) {
            const endpoint = field.fk_endpoint || field.endpoint;
            const labelField = field.label_field || "name";

            // Custom label formatter
            const formatLabel = (opt) => {
                // Special handling for hs_code - show hs_code field
                if (endpoint.includes("hs-code")) {
                    return opt.hs_code || opt.name || opt.id;
                }

                // Special handling for ports - show code
                if (endpoint.includes("port")) {
                    return opt.code || opt.name || opt.id;
                }

                // Default: use labelField
                return opt[labelField] || opt.name || opt.id;
            };

            return (
                <AsyncSelectField
                    endpoint={endpoint}
                    labelField={labelField}
                    value={fieldValue}
                    onChange={(val) => handleChange(index, field.name, val)}
                    formatLabel={formatLabel}
                    placeholder={`Select ${field.label || field.name}`}
                    className="react-select-sm"
                />
            );
        }

        // Handle different field types
        switch (field.type) {
            case "number":
                return (
                    <input
                        type="number"
                        step="0.01"
                        className="form-control form-control-sm"
                        value={fieldValue}
                        onChange={(e) => handleChange(index, field.name, e.target.value)}
                    />
                );
            case "integer":
                return (
                    <input
                        type="number"
                        className="form-control form-control-sm"
                        value={fieldValue}
                        onChange={(e) => handleChange(index, field.name, e.target.value)}
                    />
                );
            case "textarea":
                return (
                    <textarea
                        className="form-control form-control-sm"
                        rows="2"
                        value={fieldValue}
                        onChange={(e) => handleChange(index, field.name, e.target.value)}
                    />
                );
            default:
                return (
                    <input
                        type="text"
                        className="form-control form-control-sm"
                        value={fieldValue}
                        onChange={(e) => handleChange(index, field.name, e.target.value)}
                    />
                );
        }
    };

    return (
        <div className="mb-4">
            <div className="d-flex justify-content-between align-items-center mb-2">
                <label className="form-label fw-bold text-capitalize mb-0">
                    {label}
                </label>
                <button
                    type="button"
                    className="btn btn-sm btn-success"
                    onClick={handleAdd}
                >
                    <i className="bi bi-plus-circle me-1"></i>
                    Add Row
                </button>
            </div>

            {value.length === 0 ? (
                <div className="alert alert-info">
                    No items added. Click "Add Row" to add a new item.
                </div>
            ) : (
                <div className="card">
                    <div className="card-body p-0">
                        <div className="table-responsive">
                            <table className="table table-sm table-bordered mb-0">
                                <thead className="table-light">
                                    <tr>
                                        {fields
                                            .filter(f => f.name !== "id")
                                            .map((field) => (
                                                <th key={field.name}>
                                                    {field.label || field.name}
                                                    {field.required && <span className="text-danger">*</span>}
                                                </th>
                                            ))}
                                        <th style={{width: "80px"}}>Actions</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {value.map((item, index) => (
                                        <tr key={index}>
                                            {fields
                                                .filter(f => f.name !== "id")
                                                .map((field) => (
                                                    <td key={field.name}>
                                                        {renderNestedField(field, item, index)}
                                                    </td>
                                                ))}
                                            <td className="text-center">
                                                <button
                                                    type="button"
                                                    className="btn btn-sm btn-outline-danger"
                                                    onClick={() => handleRemove(index)}
                                                    title="Remove"
                                                >
                                                    <i className="bi bi-trash"></i>
                                                </button>
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
