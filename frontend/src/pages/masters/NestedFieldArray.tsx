import AsyncSelectField from "../../components/AsyncSelectField";
import ConditionBadge from "../../components/ConditionBadge";
import Select from "react-select";
import AsyncCreatableSelect from "react-select/async-creatable";
import DatePicker from "react-datepicker";
import "react-datepicker/dist/react-datepicker.css";
import api from "../../api/axios";
import {formatDateForInput, parseDate as parseDateUtil} from "../../utils/dateFormatter";
import { AlertCircle, Calculator, Hash, Inbox, Lock, Plus, Table, Trash2, Wand2 } from "lucide-react";
import { formatInr } from "./masterDisplayFormatters";

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
                                             formData = {},
                                             itemConditionsBySerial = {},
                                         }: {
    label?: string;
    fields?: any[];
    value?: any[];
    onChange?: (value: any[]) => void;
    fieldKey?: string;
    onFetchImports?: (...args: any[]) => any;
    updatedFields?: Record<string, any>;
    errors?: any[];
    entityName?: string;
    formData?: Record<string, any>;
    itemConditionsBySerial?: Record<string, any>;
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
        const updates: Record<string, any> = {[fieldName]: fieldValue};

        // Enforce max 3 decimal places for BOE numeric fields
        if (fieldKey === 'item_details' && ['cif_inr', 'cif_fc', 'qty'].includes(fieldName) && fieldValue !== '' && fieldValue !== null) {
            const strVal = String(fieldValue);
            const dotIdx = strVal.indexOf('.');
            if (dotIdx !== -1 && strVal.length - dotIdx - 1 > 3) {
                updates[fieldName] = parseFloat(fieldValue).toFixed(3);
            }
        }

        // Bill of Entry calculations for item_details
        if (entityName === "bill-of-entries" && fieldKey === "item_details") {
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

    const renderNestedField = (field, item, index, isFrozen = false) => {
        // Use nullish coalescing to preserve 0 values
        const fieldValue = item[field.name] ?? "";

        // Frozen number fields (cif_inr, cif_fc, qty) render as read-only display
        if (isFrozen && ['cif_inr', 'cif_fc', 'qty'].includes(field.name)) {
            const displayVal = fieldValue !== "" && fieldValue !== null && fieldValue !== undefined ? fieldValue : "—";
            return (
                <div className="flex h-8 items-center justify-between rounded-md border border-input bg-card px-2 py-1 text-sm"
                    style={{ background: 'var(--tb-brand-50)', color: 'var(--tb-brand-hover)', fontWeight: '600', borderColor: 'var(--tb-brand-200)', cursor: 'default' }}>
                    <span>{displayVal}</span>
                    <Lock className="size-4" aria-hidden="true" />
                </div>
            );
        }

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
                    const updates: Record<string, any> = {
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
                                height: "auto",
                                borderColor: hasError ? "#dc3545" : (isHighlighted ? "#ffc107" : "var(--tb-border)"),
                                boxShadow: hasError ? "0 0 0 0.2rem rgba(220, 53, 69, 0.25)" : (state.isFocused ? "0 0 0 0.2rem rgba(13, 110, 253, 0.25)" : "none")
                            }),
                            valueContainer: (base) => ({
                                ...base,
                                whiteSpace: "normal",
                                flexWrap: "wrap",
                                padding: "4px 8px",
                            }),
                            singleValue: (base) => ({
                                ...base,
                                whiteSpace: "normal",
                                overflow: "visible",
                                textOverflow: "clip",
                                position: "static",
                                transform: "none",
                                maxWidth: "100%",
                                lineHeight: "1.35",
                            }),
                            input: (base) => ({
                                ...base,
                                margin: 0,
                                padding: 0,
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
                <div className="flex h-8 items-center justify-between rounded-md border border-input bg-card px-2 py-1 text-sm"
                    style={{ background: 'var(--tb-success-soft)', color: 'var(--tb-success-text)', fontWeight: '600', borderColor: 'var(--tb-success-border)', cursor: 'default' }}>
                    <span>{displayVal}</span>
                    <Calculator className="size-4" aria-hidden="true" />
                </div>
            );
        }

        // Handle date fields with DatePicker
        if (field.type === "date" || field.name.includes("date") || field.name.includes("_at") || field.name.includes("_on")) {
            return (
                <div className="w-full">
                    {/* @ts-expect-error DatePicker onChange type mismatch */}
                    <DatePicker
                        selected={parseDate(fieldValue)}
                        onChange={(date) => handleChange(index, field.name, formatDateForAPI(date))}
                        dateFormat="dd-MM-yyyy"
                        className={`flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring ${highlightClass}`}
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
                                borderColor: hasError ? "#dc3545" : (isHighlighted ? "#ffc107" : "var(--tb-border)"),
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
                        className={`flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring ${highlightClass}`}
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
                        step={['cif_inr', 'cif_fc', 'qty'].includes(field.name) ? "0.001" : "0.01"}
                        className={`flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring ${highlightClass}`}
                        value={fieldValue}
                        onChange={(e) => handleChange(index, field.name, e.target.value)}
                    />
                );
            case "integer":
                return (
                    <input
                        type="number"
                        className={`flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring ${highlightClass}`}
                        value={fieldValue}
                        onChange={(e) => handleChange(index, field.name, e.target.value)}
                    />
                );
            case "textarea":
                return (
                    <textarea
                        className={`flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring ${highlightClass}`}
                        rows={field.name === "description" ? 3 : 2}
                        value={fieldValue}
                        onChange={(e) => handleChange(index, field.name, e.target.value)}
                    />
                );
            default:
                return (
                    <input
                        type="text"
                        className={`flex h-8 w-full rounded-md border border-input bg-card px-2 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring ${highlightClass}`}
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

    // Map Bootstrap col-md-N → Tailwind sm:col-span-N (12-col grid)
    const colToSpan = (cls) => {
        const m = (cls || '').match(/col(?:-md)?-(\d+)/);
        if (!m) return 'sm:col-span-4'; // default ~col-md-4
        const n = parseInt(m[1]);
        // Bootstrap col-12 → full width; col-md-2 → 2 spans; etc.
        const span = n === 12 ? 'col-span-full' : `sm:col-span-${n}`;
        return span;
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
            <div className="mb-3 flex items-center justify-between">
                <h6 className="flex items-center gap-2 text-sm font-semibold text-foreground">
                    <Table className="size-4" aria-hidden="true" />
                    {sectionLabel}
                    {value.length > 0 && (
                        <span className="rounded-md bg-primary/10 px-2 py-0.5 text-[11px] font-medium text-primary">{value.length}</span>
                    )}
                </h6>
                <button type="button" onClick={handleAdd} className="flex items-center gap-1.5 rounded-md border border-success/40 bg-success/10 px-2.5 py-1.5 text-xs font-medium text-success transition-colors hover:bg-success/20 cursor-pointer">
                    <Plus className="size-4" aria-hidden="true" />Add Item
                </button>
            </div>

            {value.length === 0 ? (
                <div className="rounded-lg border-2 border-dashed border-border py-8 text-center text-sm text-muted-foreground">
                    <Inbox className="size-4" aria-hidden="true" />
                    No items yet — click <strong>Add Item</strong> to add the first one
                </div>
            ) : (
                <div className="flex flex-col gap-2">
                    {value.map((item, index) => {
                        const isFrozen = fieldKey === 'item_details' && item.is_frozen;
                        return (
                        <div key={index} className="card" style={{ opacity: isFrozen ? 0.92 : 1 }}>
                            <div className="flex items-center justify-between border-b border-border px-3 py-2" style={{ background: isFrozen ? 'var(--tb-brand-50)' : 'var(--tb-card-bg)' }}>
                                <span className="flex min-w-0 items-center gap-2 text-sm font-semibold text-primary">
                                    <Hash className="size-4" aria-hidden="true" />
                                    <span className="shrink-0">Item {index + 1}</span>
                                    {isFrozen && (
                                        <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[10.5px] font-semibold text-primary">
                                            <Lock className="size-4" aria-hidden="true" />Ledger
                                        </span>
                                    )}
                                    {(fieldKey === "import_license" || fieldKey === "item_details" || fieldKey === "lines") && (
                                        <ConditionBadge type={item.condition_type || itemConditionsBySerial?.[item.serial_number]} />
                                    )}
                                    {getItemTitle(item) && (
                                        <span className="truncate text-xs font-normal text-muted-foreground" style={{ maxWidth: 300 }}>
                                            — {getItemTitle(item)}
                                        </span>
                                    )}
                                </span>
                                <div className="flex shrink-0 gap-1">
                                    {fieldKey === "export_license" && onFetchImports && (() => {
                                        const canFetch = item.norm_class && item.start_serial_number && item.net_quantity;
                                        return (
                                            <button
                                                type="button"
                                                onClick={() => onFetchImports(index, item)}
                                                disabled={!canFetch}
                                                title={!canFetch ? "Fill Norm Class, Net Quantity and Start Serial first" : "Auto-fill import items from SION norm"}
                                                className={`flex items-center gap-1 rounded px-2 py-1 text-xs font-medium cursor-pointer ${canFetch ? 'bg-primary text-primary-foreground' : 'border border-border text-muted-foreground'}`}
                                            >
                                                <Wand2 className="size-4" aria-hidden="true" />Fetch Imports
                                            </button>
                                        );
                                    })()}
                                    <button
                                        type="button"
                                        onClick={() => handleRemove(index)}
                                        disabled={isFrozen}
                                        title={isFrozen ? "Ledger rows cannot be deleted" : "Remove item"}
                                        className="flex size-7 cursor-pointer items-center justify-center rounded border border-destructive/30 text-destructive transition-colors hover:bg-destructive/10 disabled:cursor-not-allowed disabled:opacity-50"
                                    >
                                        {isFrozen ? <Lock className="size-3" aria-hidden="true" /> : <Trash2 className="size-3" aria-hidden="true" />}
                                    </button>
                                </div>
                            </div>
                            <div className="p-3">
                                {isFrozen && (
                                    <div className="mb-3 flex items-center gap-2 rounded-md border border-primary/20 bg-primary/10 px-3 py-2 text-[12.5px] text-primary">
                                        <Lock className="size-4" aria-hidden="true" />
                                        This row was imported from the ledger and is read-only.
                                    </div>
                                )}
                                {errors[index]?.non_field_errors && (
                                    <div className="mb-3 flex items-center gap-2 rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-[12.5px] text-destructive">
                                        <AlertCircle className="size-4" aria-hidden="true" />
                                        <div>{errors[index].non_field_errors.map((e, i) => <div key={i}>{e}</div>)}</div>
                                    </div>
                                )}

                                <div className="grid grid-cols-1 gap-3 sm:grid-cols-12">
                                    {fields
                                        .filter(f => f.name !== "id" && f.name !== "is_frozen")
                                        .map((field) => {
                                            const isTextarea = field.type === "textarea" ||
                                                (field.name.includes("note") || field.name.includes("comment"));
                                            const bsCol = FIELD_WIDTHS[fieldKey]?.[field.name]
                                                || (isTextarea ? "col-12" : "col-md-4");
                                            const colClass = colToSpan(bsCol);
                                            return (
                                                <div key={field.name} className={colClass} style={{ pointerEvents: isFrozen ? 'none' : undefined, opacity: isFrozen ? 0.7 : undefined }}>
                                                    <label className="mb-1 block text-[12px] font-semibold text-muted-foreground">
                                                        {field.label || field.name.replace(/_/g, ' ')}
                                                        {field.required && <span className="ml-0.5 text-destructive">*</span>}
                                                    </label>
                                                    {renderNestedField(field, item, index, isFrozen)}
                                                    {errors[index]?.[field.name] && (
                                                        <p className="mt-0.5 text-[11.5px] text-destructive">
                                                            <AlertCircle className="size-4" aria-hidden="true" />
                                                            {Array.isArray(errors[index][field.name])
                                                                ? errors[index][field.name].join(', ')
                                                                : errors[index][field.name]}
                                                        </p>
                                                    )}
                                                </div>
                                            );
                                        })}
                                </div>
                            </div>
                        </div>
                    );
                    })}
                </div>
            )}

            {/* Totals footer for trade lines and payments */}
            {value.length > 0 && fieldKey === 'lines' && (() => {
                const totQty = value.reduce((s, i) => s + (parseFloat(i.qty_kg) || 0), 0);
                const totCif = value.reduce((s, i) => s + (parseFloat(i.cif_inr) || 0), 0);
                const totAmt = value.reduce((s, i) => s + (parseFloat(i.amount_inr) || 0), 0);
                return (
                    <div className="mt-2 flex items-center justify-end gap-4 rounded-md border-t-2 border-border bg-muted/40 px-2 py-2 text-[13px]">
                        <span className="text-muted-foreground">Totals:</span>
                        <span><span className="text-muted-foreground mr-1">Qty</span><strong>{totQty.toFixed(3)} kg</strong></span>
                        <span><span className="text-muted-foreground mr-1">CIF INR</span><strong>{formatInr(totCif)}</strong></span>
                        <span className="text-success"><span className="text-muted-foreground mr-1">Amount</span><strong>{formatInr(totAmt)}</strong></span>
                    </div>
                );
            })()}
            {value.length > 0 && fieldKey === 'incentive_lines' && (() => {
                const totAmt = value.reduce((s, i) => s + (parseFloat(i.amount_inr) || 0), 0);
                return (
                    <div className="mt-2 flex items-center justify-end gap-4 rounded-md border-t-2 border-border bg-muted/40 px-2 py-2 text-[13px]">
                        <span className="text-muted-foreground">Total:</span>
                        <span className="text-success"><span className="text-muted-foreground mr-1">Amount</span><strong>{formatInr(totAmt)}</strong></span>
                    </div>
                );
            })()}
            {value.length > 0 && fieldKey === 'payments' && (() => {
                const totPaid = value.reduce((s, i) => s + (parseFloat(i.amount) || 0), 0);
                return (
                    <div className="mt-2 flex items-center justify-end gap-4 rounded-md border-t-2 border-success/40 bg-success/10 px-2 py-2 text-[13px]">
                        <span className="text-muted-foreground">Total Paid:</span>
                        <strong className="text-success">{formatInr(totPaid)}</strong>
                    </div>
                );
            })()}
        </div>
    );
}
