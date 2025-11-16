import {useState} from "react";
import AsyncSelectField from "../../components/AsyncSelectField";
import Select from "react-select";
import AsyncCreatableSelect from "react-select/async-creatable";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import api from "../../api/axios";

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
 * - errors: Array of error objects for nested items
 */
export default function NestedFieldArray({
                                             label,
                                             fields = [],
                                             value = [],
                                             onChange,
                                             fieldKey = "",
                                             onFetchImports,
                                             updatedFields = {},
                                             errors = []
                                         }) {

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
        // Use nullish coalescing to preserve 0 values
        const fieldValue = item[field.name] ?? "";

        // Check if this field was recently updated
        const fieldPath = `${fieldKey}.${index}.${field.name}`;
        const isHighlighted = updatedFields[fieldPath];
        const highlightClass = isHighlighted ? "border-warning border-2 bg-warning bg-opacity-10" : "";

        // Special handling for description field in import_license - show autocomplete and auto-fill hs_code
        if (fieldKey === "import_license" && field.name === "description") {
            const loadDescriptionOptions = async (inputValue) => {
                if (!inputValue || inputValue.length < 2) return [];

                try {
                    const params = {
                        search: inputValue
                    };
                    const response = await api.get("/masters/product-descriptions/", {params});
                    console.log("Product descriptions response:", response.data);

                    if (!response.data.results || response.data.results.length === 0) {
                        console.log("No results found for:", inputValue);
                        return [];
                    }

                    return response.data.results.map(desc => {
                        console.log("Description item:", desc);
                        return {
                            value: desc.product_description,
                            label: desc.product_description,
                            hsCode: desc.hs_code // Store hs_code ID for auto-fill
                        };
                    });
                } catch (error) {
                    console.error("Error loading descriptions:", error);
                    return [];
                }
            };

            const currentOption = fieldValue ? {value: fieldValue, label: fieldValue} : null;

            const handleDescriptionChange = (selected) => {
                if (selected) {
                    // Update description
                    handleChange(index, field.name, selected.value);

                    // Auto-fill hs_code if available and current hs_code is empty
                    if (selected.hsCode && !item.hs_code) {
                        handleChange(index, "hs_code", selected.hsCode);
                    }
                } else {
                    handleChange(index, field.name, "");
                }
            };

            return (
                <div className={highlightClass ? `${highlightClass} rounded` : ""}>
                    <AsyncCreatableSelect
                        cacheOptions={false}
                        defaultOptions={false}
                        value={currentOption}
                        loadOptions={loadDescriptionOptions}
                        onChange={handleDescriptionChange}
                        onCreateOption={(inputValue) => handleChange(index, field.name, inputValue)}
                        placeholder="Type at least 2 characters to search..."
                        isClearable
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
                        noOptionsMessage={({inputValue}) =>
                            !inputValue || inputValue.length < 2
                                ? "Type at least 2 characters..."
                                : "No matches found. Press Enter to create."
                        }
                    />
                </div>
            );
        }

        // Handle date fields with DatePicker
        if (field.type === "date" || field.name.includes("date") || field.name.includes("_at") || field.name.includes("_on")) {
            return (
                <div className="w-100">
                    <DatePicker
                        selected={parseDate(fieldValue)}
                        onChange={(date) => handleChange(index, field.name, formatDateForAPI(date))}
                        dateFormat="dd-MM-yyyy"
                        className={`form-control form-control-sm ${highlightClass}`}
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

        // Handle file fields
        if (field.type === "file") {
            return (
                <div>
                    <input
                        type="file"
                        className={`form-control form-control-sm ${highlightClass}`}
                        onChange={(e) => {
                            const file = e.target.files[0];
                            if (file) {
                                handleChange(index, field.name, file);
                            }
                        }}
                    />
                    {fieldValue && typeof fieldValue === 'string' && (
                        <div className="mt-1">
                            <small className="text-muted">
                                Current: <a href={fieldValue} target="_blank" rel="noopener noreferrer">View file</a>
                            </small>
                        </div>
                    )}
                    {fieldValue && typeof fieldValue === 'object' && fieldValue.name && (
                        <div className="mt-1">
                            <small className="text-success">
                                Selected: {fieldValue.name}
                            </small>
                        </div>
                    )}
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
                            <div
                                className="card-header bg-light d-flex justify-content-between align-items-center py-2">
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
                                {/* Display errors for this item */}
                                {errors[index] && errors[index].non_field_errors && (
                                    <div className="alert alert-danger alert-sm mb-3">
                                        {errors[index].non_field_errors.map((error, errIdx) => (
                                            <div key={errIdx}>{error}</div>
                                        ))}
                                    </div>
                                )}

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
                                                <div key={field.name} className={`${colClass}`}>
                                                    <div className="form-group-material">
                                                        <label className="form-label">
                                                            {field.label || field.name}
                                                            {field.required && <span className="text-danger ms-1">*</span>}
                                                        </label>
                                                        {renderNestedField(field, item, index)}
                                                        {/* Display field-level errors */}
                                                        {errors[index] && errors[index][field.name] && (
                                                            <div className="invalid-feedback d-block">
                                                                {Array.isArray(errors[index][field.name])
                                                                    ? errors[index][field.name].join(', ')
                                                                    : errors[index][field.name]}
                                                            </div>
                                                        )}
                                                    </div>
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
