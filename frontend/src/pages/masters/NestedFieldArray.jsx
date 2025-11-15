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
            const isMulti = field.type === "fk_multi";

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
                    isMulti={isMulti}
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
            <div className="d-flex justify-content-between align-items-center mb-3">
                <label className="form-label fw-bold text-capitalize mb-0">
                    {label}
                </label>
                <button
                    type="button"
                    className="btn btn-sm btn-success"
                    onClick={handleAdd}
                >
                    <i className="bi bi-plus-circle me-1"></i>
                    Add Item
                </button>
            </div>

            {value.length === 0 ? (
                <div className="alert alert-info">
                    No items added. Click "Add Item" to add a new item.
                </div>
            ) : (
                <div className="nested-items-container">
                    {value.map((item, index) => (
                        <div key={index} className="card mb-3">
                            <div className="card-header bg-light d-flex justify-content-between align-items-center py-2">
                                <h6 className="mb-0">Item #{index + 1}</h6>
                                <button
                                    type="button"
                                    className="btn btn-sm btn-outline-danger"
                                    onClick={() => handleRemove(index)}
                                    title="Remove this item"
                                >
                                    <i className="bi bi-trash me-1"></i>
                                    Remove
                                </button>
                            </div>
                            <div className="card-body">
                                <div className="row">
                                    {fields
                                        .filter(f => f.name !== "id")
                                        .map((field) => {
                                            // Determine column width based on field type
                                            const isTextarea = field.type === "textarea" ||
                                                             field.name.includes("description") ||
                                                             field.name.includes("note") ||
                                                             field.name.includes("comment");

                                            const colClass = isTextarea ? "col-12" : "col-md-4";

                                            return (
                                                <div key={field.name} className={`${colClass} mb-3`}>
                                                    <label className="form-label small">
                                                        {field.label || field.name}
                                                        {field.required && <span className="text-danger">*</span>}
                                                    </label>
                                                    {renderNestedField(field, item, index)}
                                                </div>
                                            );
                                        })}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}
        </div>
    );
}
