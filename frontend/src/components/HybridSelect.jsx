import Select from "react-select";
import AsyncSelectField from "./AsyncSelectField";

/**
 * HybridSelect Component - Intelligently chooses between static Select and AsyncSelect
 *
 * Props:
 * - fieldMeta: metadata from backend containing type, endpoint, choices, etc.
 * - value: current selected value(s)
 * - onChange: callback function(value)
 * - isMulti: enable multi-select (default: false)
 * - placeholder: placeholder text
 * - isClearable: allow clearing selection (default: true)
 * - isDisabled: disable the select
 * - staticOptions: array of static options [{value, label}] (overrides choices)
 */
export default function HybridSelect({
    fieldMeta = {},
    value,
    onChange,
    isMulti = false,
    placeholder = "Select...",
    isClearable = true,
    isDisabled = false,
    staticOptions = null,
    className = "",
    formatLabel: customFormatLabel = null  // Accept custom formatLabel prop
}) {
    // Determine if we should use AsyncSelect or static Select
    const useAsync = Boolean(fieldMeta.endpoint || fieldMeta.fk_endpoint);
    const hasChoices = Boolean(staticOptions || fieldMeta.choices);

    // For FK/ManyToMany fields, use AsyncSelect
    if (useAsync) {
        const endpoint = fieldMeta.endpoint || fieldMeta.fk_endpoint;
        const labelField = fieldMeta.label_field || "name";
        const valueField = fieldMeta.value_field || "id";

        // Custom label formatter based on field type
        const defaultFormatLabel = (item) => {
            // Special handling for hs_code - show hs_code field instead of id
            if (endpoint.includes("hs-code")) {
                return item.hs_code || item.name || item.id;
            }

            // Special handling for ports - show name (which includes code like "NHAVA SHEVA SEA (INNSA1)")
            if (endpoint.includes("port")) {
                return item.name || item.code || item.id;
            }

            // Default: use labelField
            return item[labelField] || item.name || item.id;
        };

        // Use custom formatLabel if provided, otherwise use default
        const formatLabel = customFormatLabel || defaultFormatLabel;

        return (
            <AsyncSelectField
                endpoint={endpoint}
                labelField={labelField}
                valueField={valueField}
                value={value}
                onChange={onChange}
                isMulti={isMulti}
                placeholder={placeholder}
                isClearable={isClearable}
                isDisabled={isDisabled}
                formatLabel={formatLabel}
                className={className}
                // Pre-populate the dropdown on first open so small lookup
                // tables (scheme codes, notification numbers, purchase
                // statuses, …) show their options without forcing the user
                // to type a search string. AsyncSelect still page-limits to
                // 50 results, so large endpoints (companies, hs-codes) stay
                // responsive.
                loadOnMount={true}
            />
        );
    }

    // For fields with fixed choices (like account_type, etc.)
    if (hasChoices) {
        let options = staticOptions;

        // If no staticOptions provided, try to parse from fieldMeta.choices
        if (!options && fieldMeta.choices) {
            options = fieldMeta.choices.map(choice => {
                if (Array.isArray(choice)) {
                    return {value: choice[0], label: choice[1]};
                }
                if (typeof choice === "object") {
                    return {value: choice.value, label: choice.label};
                }
                return {value: choice, label: choice};
            });
        }

        // Find selected option(s)
        let selectedOption = null;
        if (isMulti) {
            const values = Array.isArray(value) ? value : (value ? [value] : []);
            selectedOption = options.filter(opt => values.includes(opt.value));
        } else {
            selectedOption = options.find(opt => opt.value === value) || null;
        }

        const handleChange = (selected) => {
            if (isMulti) {
                const values = selected ? selected.map(opt => opt.value) : [];
                onChange(values);
            } else {
                onChange(selected ? selected.value : null);
            }
        };

        return (
            <Select
                options={options}
                value={selectedOption}
                onChange={handleChange}
                isMulti={isMulti}
                isClearable={isClearable}
                isDisabled={isDisabled}
                placeholder={placeholder}
                className={className}
                classNamePrefix="react-select"
                styles={{
                    control: (base) => ({
                        ...base,
                        minHeight: "38px",
                        borderColor: "#dee2e6"
                    }),
                    menu: (base) => ({
                        ...base,
                        zIndex: 9999
                    })
                }}
            />
        );
    }

    // Fallback to regular input if no special handling needed
    return (
        <input
            type="text"
            className="form-control"
            value={value || ""}
            onChange={(e) => onChange(e.target.value)}
            placeholder={placeholder}
            disabled={isDisabled}
        />
    );
}
