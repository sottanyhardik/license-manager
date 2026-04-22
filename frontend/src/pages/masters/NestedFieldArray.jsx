import {useState} from "react";
import AsyncSelectField from "../../components/AsyncSelectField";
import Select from "react-select";
import AsyncCreatableSelect from "react-select/async-creatable";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import api from "../../api/axios";
import {formatDateForInput, parseDate as parseDateUtil} from "../../utils/dateFormatter";

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
                                             errors = [],
                                             entityName = "",
                                             formData = {}
                                         }) {

    // Use centralized date parser from utility
    const parseDate = (dateString) => {
        return parseDateUtil(dateString);
    };

    // Helper function to format Date object to YYYY-MM-DD for API
    const formatDateForAPI = (date) => {
        if (!date) return null;
        return formatDateForInput(date);
    };

    const handleAdd = () => {
        const newItem = {};
        fields.forEach(field => {
            // Use default value if specified
            if (field.default !== undefined) {
                newItem[field.name] = field.default;
            }
            // For number/decimal fields without defaults, use null instead of empty string
            else if (field.type === "number") {
                newItem[field.name] = null;
            }
            // For other fields, use empty string
            else {
                newItem[field.name] = "";
            }
        });
        onChange([...value, newItem]);
    };

    const handleRemove = (index) => {
        const newArray = value.filter((_, i) => i !== index);
        onChange(newArray);
    };

    const handleChange = (index, fieldName, fieldValue) => {
        const newArray = [...value];
        const updates = {[fieldName]: fieldValue};

        // Bill of Entry calculations for item_details
        if (entityName === "bill-of-entries" && fieldKey === "item_details") {
            const currentItem = {...newArray[index], ...updates};

            // Calculate cif_fc from cif_inr when cif_inr changes
            if (fieldName === "cif_inr" && fieldValue && formData.exchange_rate) {
                const cifInr = parseFloat(fieldValue);
                const exchangeRate = parseFloat(formData.exchange_rate);
                if (!isNaN(cifInr) && !isNaN(exchangeRate) && exchangeRate > 0) {
                    updates.cif_fc = (cifInr / exchangeRate).toFixed(2);
                }
            }

            // Calculate cif_inr from cif_fc when cif_fc changes
            if (fieldName === "cif_fc" && fieldValue && formData.exchange_rate) {
                const cifFc = parseFloat(fieldValue);
                const exchangeRate = parseFloat(formData.exchange_rate);
                if (!isNaN(cifFc) && !isNaN(exchangeRate) && exchangeRate > 0) {
                    updates.cif_inr = (cifFc * exchangeRate).toFixed(2);
                }
            }
        }

        // Trade line (DFIA) calculations
        if (entityName === "trades" && fieldKey === "lines") {
            const cur = {...newArray[index], ...updates};
            const mode = cur.mode;
            if (mode === 'QTY') {
                const qty = parseFloat(cur.qty_kg);
                const rate = parseFloat(cur.rate_inr_per_kg);
                if (!isNaN(qty) && !isNaN(rate)) updates.amount_inr = (qty * rate).toFixed(2);
            } else if (mode === 'CIF_INR') {
                const cif = parseFloat(cur.cif_inr);
                const pct = parseFloat(cur.pct);
                if (!isNaN(cif) && !isNaN(pct)) updates.amount_inr = (cif * pct / 100).toFixed(2);
            } else if (mode === 'FOB_INR') {
                const fob = parseFloat(cur.fob_inr);
                const pct = parseFloat(cur.pct);
                if (!isNaN(fob) && !isNaN(pct)) updates.amount_inr = (fob * pct / 100).toFixed(2);
            }
        }

        // Incentive trade line calculations
        if (entityName === "trades" && fieldKey === "incentive_lines") {
            const cur = {...newArray[index], ...updates};
            const lv = parseFloat(cur.license_value);
            const rp = parseFloat(cur.rate_pct);
            if (!isNaN(lv) && !isNaN(rp)) updates.amount_inr = (lv * rp / 100).toFixed(2);
        }

        newArray[index] = {
            ...newArray[index],
            ...updates
        };

        onChange(newArray);
    };

    const renderNestedField = (field, item, index) => {
        // Use nullish coalescing to preserve 0 values
        const fieldValue = item[field.name] ?? "";

        // Check if this field was recently updated
        const fieldPath = `${fieldKey}.${index}.${field.name}`;
        const isHighlighted = updatedFields[fieldPath];

        // Check if this field has an error
        const itemErrors = errors[index] || {};
        const fieldError = itemErrors[field.name];
        const hasError = fieldError && (Array.isArray(fieldError) ? fieldError.length > 0 : fieldError);

        // Apply appropriate class - error takes precedence over highlight
        const highlightClass = hasError
            ? "is-invalid border-danger"
            : (isHighlighted ? "border-warning border-2 bg-warning bg-opacity-10" : "");

        // Special handling for description field in import_license - show autocomplete and auto-fill hs_code
        if (fieldKey === "import_license" && field.name === "description") {
            const loadDescriptionOptions = async (inputValue) => {
                if (!inputValue || inputValue.length < 2) return [];

                try {
                    const params = {
                        search: inputValue
                    };
                    const response = await api.get("/masters/product-descriptions/", {params});

                    if (!response.data.results || response.data.results.length === 0) {
                        return [];
                    }

                    return response.data.results.map(desc => {
                        return {
                            value: desc.product_description,
                            label: desc.product_description,
                            hsCode: desc.hs_code // Store hs_code ID for auto-fill
                        };
                    });
                } catch (error) {
                    return [];
                }
            };

            const currentOption = fieldValue ? {value: fieldValue, label: fieldValue} : null;

            const handleDescriptionChange = (selected) => {
                const newArray = [...value];

                if (selected) {
                    // Update description and optionally auto-fill hs_code in a single update
                    const updates = {
                        [field.name]: selected.value
                    };

                    // Auto-fill hs_code if available and current hs_code is empty
                    if (selected.hsCode && !item.hs_code) {
                        updates.hs_code = selected.hsCode;
                    }

                    newArray[index] = {
                        ...newArray[index],
                        ...updates
                    };
                } else {
                    newArray[index] = {
                        ...newArray[index],
                        [field.name]: ""
                    };
                }

                onChange(newArray);
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
                            control: (base, state) => ({
                                ...base,
                                minHeight: "34px",
                                borderColor: hasError ? "#dc3545" : (isHighlighted ? "#ffc107" : "#dee2e6"),
                                boxShadow: hasError ? "0 0 0 0.2rem rgba(220, 53, 69, 0.25)" : (state.isFocused ? "0 0 0 0.2rem rgba(13, 110, 253, 0.25)" : "none")
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

        // Handle readonly/calculated fields
        if (field.readonly || field.read_only) {
            const displayVal = fieldValue !== "" && fieldValue !== null && fieldValue !== undefined ? fieldValue : "—";
            return (
                <div className="form-control form-control-sm d-flex align-items-center justify-content-between"
                    style={{ background: '#f0fdf4', color: '#065f46', fontWeight: '600', borderColor: '#a7f3d0', cursor: 'default' }}>
                    <span>{displayVal}</span>
                    <i className="bi bi-calculator text-success" style={{ fontSize: '0.7rem', opacity: 0.6 }}></i>
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
                // Special handling for license items - show license number, serial number, and description
                if (endpoint.includes("license-items")) {
                    return opt.label || `${opt.license_number || ''} - S.No.${opt.serial_number || ''} - ${opt.description || ''}`.trim();
                }

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
                            control: (base, state) => ({
                                ...base,
                                minHeight: "34px",
                                borderColor: hasError ? "#dc3545" : (isHighlighted ? "#ffc107" : "#dee2e6"),
                                boxShadow: hasError ? "0 0 0 0.2rem rgba(220, 53, 69, 0.25)" : (state.isFocused ? "0 0 0 0.2rem rgba(13, 110, 253, 0.25)" : "none")
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

    const FIELD_WIDTHS = {
        import_license: {
            serial_number: 'col-md-2',
            hs_code: 'col-md-3',
            description: 'col-md-5',
            unit: 'col-md-2',
            quantity: 'col-md-3',
            cif_fc: 'col-md-3',
            cif_inr: 'col-md-3',
            duty_type: 'col-md-3',
        },
        export_license: {
            description: 'col-md-6',
            net_quantity: 'col-md-3',
            start_serial_number: 'col-md-3',
            norm_class: 'col-md-4',
        },
        lines: {
            sr_number: 'col-md-5',
            description: 'col-md-6',
            hsn_code: 'col-md-3',
            mode: 'col-md-3',
            qty_kg: 'col-md-3',
            rate_inr_per_kg: 'col-md-3',
            cif_fc: 'col-md-3',
            exc_rate: 'col-md-3',
            cif_inr: 'col-md-3',
            fob_inr: 'col-md-3',
            pct: 'col-md-2',
            amount_inr: 'col-md-3',
        },
        incentive_lines: {
            incentive_license: 'col-md-5',
            license_value: 'col-md-3',
            rate_pct: 'col-md-2',
            amount_inr: 'col-md-3',
        },
        payments: {
            date: 'col-md-3',
            amount: 'col-md-3',
            note: 'col-md-6',
        },
    };

    const getItemTitle = (item) => {
        if (fieldKey === 'import_license') {
            const parts = [];
            if (item.serial_number) parts.push(`S.No. ${item.serial_number}`);
            if (item.description) parts.push(item.description.length > 35 ? item.description.substring(0, 35) + '…' : item.description);
            return parts.join(' — ');
        }
        if (fieldKey === 'export_license') {
            if (item.description) return item.description.length > 45 ? item.description.substring(0, 45) + '…' : item.description;
        }
        if (fieldKey === 'license_documents') {
            return item.type || item.document_type || '';
        }
        if (fieldKey === 'lines') {
            const parts = [];
            if (item.sr_number_label) parts.push(item.sr_number_label);
            if (item.description) parts.push(item.description.length > 35 ? item.description.substring(0, 35) + '…' : item.description);
            return parts.join(' — ');
        }
        if (fieldKey === 'incentive_lines') {
            const parts = [];
            if (item.incentive_license_label || item.incentive_license) parts.push(item.incentive_license_label || `License #${item.incentive_license}`);
            if (item.amount_inr) parts.push(`₹${item.amount_inr}`);
            return parts.join(' — ');
        }
        if (fieldKey === 'payments') {
            const parts = [];
            if (item.date) parts.push(item.date);
            if (item.amount) parts.push(`₹${item.amount}`);
            return parts.join(' — ');
        }
        return '';
    };

    const sectionLabel = label
        .split(" ")
        .map(w => w.charAt(0).toUpperCase() + w.slice(1))
        .join(" ");

    return (
        <div className="mb-4">
            <div className="d-flex justify-content-between align-items-center mb-3">
                <div>
                    <h6 className="mb-0 fw-semibold" style={{ color: 'var(--text-dark)' }}>
                        <i className="bi bi-table me-2" style={{ color: '#6366F1' }}></i>
                        {sectionLabel}
                        {value.length > 0 && (
                            <span className="badge ms-2" style={{ backgroundColor: '#e0e7ff', color: '#4F46E5', fontSize: '0.7rem' }}>
                                {value.length}
                            </span>
                        )}
                    </h6>
                </div>
                <button
                    type="button"
                    className="btn btn-sm btn-outline-success"
                    onClick={handleAdd}
                    style={{ borderRadius: '8px' }}
                >
                    <i className="bi bi-plus-lg me-1"></i>Add Item
                </button>
            </div>

            {value.length === 0 ? (
                <div className="text-center py-4" style={{ border: '2px dashed #d1d5db', borderRadius: '10px', color: 'var(--text-secondary)' }}>
                    <i className="bi bi-inbox d-block mb-1" style={{ fontSize: '1.5rem', opacity: 0.5 }}></i>
                    <small>No items yet — click <strong>Add Item</strong> to add the first one</small>
                </div>
            ) : (
                <div className="d-flex flex-column gap-2">
                    {value.map((item, index) => (
                        <div key={index} className="card border-0 shadow-sm" style={{ borderRadius: '10px' }}>
                            <div className="card-header bg-white border-bottom d-flex justify-content-between align-items-center py-2 px-3" style={{ borderRadius: '10px 10px 0 0' }}>
                                <span className="fw-semibold small d-flex align-items-center gap-2" style={{ color: '#6366F1', minWidth: 0 }}>
                                    <i className="bi bi-hash flex-shrink-0"></i>
                                    <span className="flex-shrink-0">Item {index + 1}</span>
                                    {getItemTitle(item) && (
                                        <span className="fw-normal text-muted text-truncate" style={{ fontSize: '0.78rem', maxWidth: 300 }}>
                                            — {getItemTitle(item)}
                                        </span>
                                    )}
                                </span>
                                <div className="d-flex gap-1 flex-shrink-0">
                                    {fieldKey === "export_license" && onFetchImports && (() => {
                                        const canFetch = item.norm_class && item.start_serial_number && item.net_quantity;
                                        return (
                                            <button
                                                type="button"
                                                className={`btn btn-sm ${canFetch ? 'btn-primary' : 'btn-outline-secondary'}`}
                                                onClick={() => onFetchImports(index, item)}
                                                disabled={!canFetch}
                                                title={!canFetch ? "Fill Norm Class, Net Quantity and Start Serial first" : "Auto-fill import items from SION norm"}
                                                style={{ borderRadius: '6px', fontSize: '0.78rem' }}
                                            >
                                                <i className="bi bi-magic me-1"></i>Fetch Imports
                                            </button>
                                        );
                                    })()}
                                    <button
                                        type="button"
                                        className="btn btn-sm btn-outline-danger"
                                        onClick={() => handleRemove(index)}
                                        title="Remove item"
                                        style={{ borderRadius: '6px' }}
                                    >
                                        <i className="bi bi-trash"></i>
                                    </button>
                                </div>
                            </div>
                            <div className="card-body p-3">
                                {errors[index]?.non_field_errors && (
                                    <div className="alert alert-danger d-flex align-items-center gap-2 py-2 mb-3">
                                        <i className="bi bi-exclamation-circle-fill flex-shrink-0"></i>
                                        <div className="small">
                                            {errors[index].non_field_errors.map((e, i) => <div key={i}>{e}</div>)}
                                        </div>
                                    </div>
                                )}

                                <div className="row g-3">
                                    {fields
                                        .filter(f => f.name !== "id")
                                        .map((field) => {
                                            const isTextarea = field.type === "textarea" ||
                                                (field.name.includes("note") || field.name.includes("comment"));
                                            const colClass = FIELD_WIDTHS[fieldKey]?.[field.name]
                                                || (isTextarea ? "col-12" : "col-md-4");
                                            return (
                                                <div key={field.name} className={colClass}>
                                                    <label className="form-label" style={{ fontSize: '0.75rem', fontWeight: '600', color: 'var(--text-secondary)', marginBottom: 4 }}>
                                                        {field.label || field.name.replace(/_/g, ' ')}
                                                        {field.required && <span className="text-danger ms-1">*</span>}
                                                    </label>
                                                    {renderNestedField(field, item, index)}
                                                    {errors[index]?.[field.name] && (
                                                        <div className="invalid-feedback d-block" style={{ fontSize: '0.75rem' }}>
                                                            <i className="bi bi-exclamation-circle me-1"></i>
                                                            {Array.isArray(errors[index][field.name])
                                                                ? errors[index][field.name].join(', ')
                                                                : errors[index][field.name]}
                                                        </div>
                                                    )}
                                                </div>
                                            );
                                        })}
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            )}

            {/* Totals footer for trade lines and payments */}
            {value.length > 0 && fieldKey === 'lines' && (() => {
                const totQty = value.reduce((s, i) => s + (parseFloat(i.qty_kg) || 0), 0);
                const totCif = value.reduce((s, i) => s + (parseFloat(i.cif_inr) || 0), 0);
                const totAmt = value.reduce((s, i) => s + (parseFloat(i.amount_inr) || 0), 0);
                return (
                    <div className="d-flex gap-4 justify-content-end align-items-center mt-2 px-2 py-2"
                        style={{ background: 'var(--bs-gray-50)', borderRadius: 8, fontSize: '0.83rem', borderTop: '2px solid #e5e7eb' }}>
                        <span className="text-muted">Totals:</span>
                        <span><span className="text-muted me-1">Qty</span><strong>{totQty.toFixed(3)} kg</strong></span>
                        <span><span className="text-muted me-1">CIF INR</span><strong>₹{totCif.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong></span>
                        <span style={{ color: '#065f46' }}><span className="text-muted me-1">Amount</span><strong>₹{totAmt.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong></span>
                    </div>
                );
            })()}
            {value.length > 0 && fieldKey === 'incentive_lines' && (() => {
                const totAmt = value.reduce((s, i) => s + (parseFloat(i.amount_inr) || 0), 0);
                return (
                    <div className="d-flex gap-4 justify-content-end align-items-center mt-2 px-2 py-2"
                        style={{ background: 'var(--bs-gray-50)', borderRadius: 8, fontSize: '0.83rem', borderTop: '2px solid #e5e7eb' }}>
                        <span className="text-muted">Total:</span>
                        <span style={{ color: '#065f46' }}><span className="text-muted me-1">Amount</span><strong>₹{totAmt.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</strong></span>
                    </div>
                );
            })()}
            {value.length > 0 && fieldKey === 'payments' && (() => {
                const totPaid = value.reduce((s, i) => s + (parseFloat(i.amount) || 0), 0);
                return (
                    <div className="d-flex gap-4 justify-content-end align-items-center mt-2 px-2 py-2"
                        style={{ background: '#f0fdf4', borderRadius: 8, fontSize: '0.83rem', borderTop: '2px solid #a7f3d0' }}>
                        <span className="text-muted">Total Paid:</span>
                        <span style={{ color: '#065f46', fontWeight: '700' }}>₹{totPaid.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                    </div>
                );
            })()}
        </div>
    );
}
