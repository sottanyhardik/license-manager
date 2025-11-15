import {useState} from "react";
import AsyncSelectField from "../../components/AsyncSelectField";
import Select from "react-select";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";

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
 * - fieldKey: The key of this nested field (e.g., "export_license", "import_license")
 * - onFetchImports: Optional callback to fetch import items from SION
 * - updatedFields: Object tracking which fields were recently updated (for highlighting)
 */
export default function NestedFieldArray({label, fields = [], value = [], onChange, fieldKey = "", onFetchImports, updatedFields = {}}) {

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

        // Check if this field was recently updated
        const fieldPath = `${fieldKey}.${index}.${field.name}`;
        const isHighlighted = updatedFields[fieldPath];
        const highlightClass = isHighlighted ? "border-warning border-2 bg-warning bg-opacity-10" : "";

        // Handle date fields with DatePicker
        if (field.type === "date" || field.name.includes("date") || field.name.includes("_at") || field.name.includes("_on")) {
            return (
                <DatePicker
                    selected={parseDate(fieldValue)}
                    onChange={(date) => handleChange(index, field.name, formatDateForAPI(date))}
                    dateFormat="dd-MM-yyyy"
                    className={`form-control form-control-sm ${highlightClass}`}
                    placeholderText="Select date"
                    isClearable
                    showYearDropdown
                    showMonthDropdown
                    dropdownMode="select"
                />
            );
        }

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
                <div className={highlightClass ? `${highlightClass} rounded` : ""}>
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
                </div>
            );
        }

        // Handle select fields with choices (like unit, currency, etc.)
        if (field.type === "select" && field.choices && Array.isArray(field.choices)) {
            const options = field.choices.map(choice => {
                if (Array.isArray(choice)) {
                    return {value: choice[0], label: choice[1]};
                }
                if (typeof choice === "object") {
                    return {value: choice.value, label: choice.label};
                }
                return {value: choice, label: choice};
            });

            const selectedOption = options.find(opt => opt.value === fieldValue) || null;

            return (
                <div className={highlightClass ? `${highlightClass} rounded` : ""}>
                    <Select
                        options={options}
                        value={selectedOption}
                        onChange={(selected) => handleChange(index, field.name, selected ? selected.value : null)}
                        isClearable
                        placeholder={`Select ${field.label || field.name}`}
                        className="react-select-sm"
                        classNamePrefix="react-select"
                        styles={{
                            control: (base) => ({
                                ...base,
                                minHeight: "34px",
                                borderColor: "#dee2e6"
                            }),
                            menu: (base) => ({
                                ...base,
                                zIndex: 9999
                            })
                        }}
                    />
                </div>
            );
        }

        // Handle boolean fields as switch
        if (field.type === "boolean" || typeof fieldValue === "boolean" || field.name.startsWith("is_") || field.name.startsWith("has_")) {
            const boolValue = typeof fieldValue === "boolean" ? fieldValue : false;
            return (
                <div className={`form-check form-switch ${highlightClass ? `${highlightClass} rounded p-2` : ""}`}>
                    <input
                        type="checkbox"
                        className="form-check-input"
                        role="switch"
                        id={`switch-${field.name}-${index}`}
                        checked={boolValue}
                        onChange={(e) => handleChange(index, field.name, e.target.checked)}
                    />
                    <label className="form-check-label" htmlFor={`switch-${field.name}-${index}`}>
                        {boolValue ? "Yes" : "No"}
                    </label>
                </div>
            );
        }

        // Handle different field types
        switch (field.type) {
            case "number":
                return (
                    <input
                        type="number"
                        step="0.01"
                        className={`form-control form-control-sm ${highlightClass}`}
                        value={fieldValue}
                        onChange={(e) => handleChange(index, field.name, e.target.value)}
                    />
                );
            case "integer":
                return (
                    <input
                        type="number"
                        className={`form-control form-control-sm ${highlightClass}`}
                        value={fieldValue}
                        onChange={(e) => handleChange(index, field.name, e.target.value)}
                    />
                );
            case "textarea":
                return (
                    <textarea
                        className={`form-control form-control-sm ${highlightClass}`}
                        rows="2"
                        value={fieldValue}
                        onChange={(e) => handleChange(index, field.name, e.target.value)}
                    />
                );
            default:
                return (
                    <input
                        type="text"
                        className={`form-control form-control-sm ${highlightClass}`}
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
                                <div className="btn-group btn-group-sm">
                                    {/* Show Fetch button only for export_license items and if callback is provided */}
                                    {fieldKey === "export_license" && onFetchImports && (
                                        <button
                                            type="button"
                                            className="btn btn-sm btn-primary"
                                            onClick={() => onFetchImports(index, item)}
                                            disabled={!item.norm_class || !item.start_serial_number}
                                            title={
                                                !item.norm_class || !item.start_serial_number
                                                    ? "Please select Norm Class and enter Start Serial Number first"
                                                    : "Fetch import items from SION norm class"
                                            }
                                        >
                                            <i className="bi bi-download me-1"></i>
                                            Fetch Imports
                                        </button>
                                    )}
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
