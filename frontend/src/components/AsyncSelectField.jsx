import {useState, useEffect} from "react";
import AsyncSelect from "react-select/async";
import api from "../api/axios";

/**
 * AsyncSelectField Component - Select2-like with API support
 *
 * Props:
 * - endpoint: API endpoint to fetch options (required)
 * - labelField: field name to use as label (default: 'name')
 * - valueField: field name to use as value (default: 'id')
 * - value: current selected value(s)
 * - onChange: callback function(value)
 * - isMulti: enable multi-select (default: false)
 * - placeholder: placeholder text
 * - isClearable: allow clearing selection (default: true)
 * - isDisabled: disable the select
 * - formatLabel: custom function to format option label
 */
export default function AsyncSelectField({
    endpoint,
    labelField = "name",
    valueField = "id",
    value,
    onChange,
    isMulti = false,
    placeholder = "Select...",
    isClearable = true,
    isDisabled = false,
    formatLabel = null,
    className = "",
    loadOnMount = false  // NEW: Control whether to load options on mount
}) {
    // Strip /api/ prefix if it exists to avoid double /api/api/
    let cleanEndpoint = endpoint?.startsWith('/api/') ? endpoint.substring(5) : endpoint;

    // Parse endpoint to separate base URL and existing query params
    const [baseEndpoint, queryString] = cleanEndpoint?.split('?') || [cleanEndpoint, ''];
    const existingParams = new URLSearchParams(queryString);

    const [selectedOption, setSelectedOption] = useState(null);

    const formatOption = (item) => {
        let label;

        if (formatLabel) {
            label = formatLabel(item);
        } else {
            label = item[labelField] || item[valueField] || String(item.id);
        }

        return {
            value: item[valueField],
            label: label,
            data: item
        };
    };

    const fetchOptionById = async (id) => {
        try {
            // Parse ID if it's a number string
            const numId = typeof id === 'string' ? parseInt(id, 10) : id;

            // Fetch from API using base endpoint (without query params for detail view)
            const {data} = await api.get(`${baseEndpoint}${numId}/`);
            return formatOption(data);
        } catch (err) {
            return null;
        }
    };

    const loadSelectedOption = async (val) => {
        if (!val) {
            setSelectedOption(null);
            return;
        }

        // If val is already a full object with id, use it directly
        if (typeof val === 'object' && !Array.isArray(val) && val[valueField]) {
            setSelectedOption(formatOption(val));
            return;
        }

        if (isMulti) {
            // For multi-select, val should be an array of IDs or objects
            let items = Array.isArray(val) ? val : [val];

            // Handle comma-separated string values for backward compatibility
            if (items.length === 1 && typeof items[0] === 'string' && items[0].includes(',')) {
                items = items[0].split(',').map(id => id.trim()).filter(id => id);
            }

            // Filter out empty/null values
            items = items.filter(item => item !== null && item !== undefined && item !== '');

            const options = [];

            for (const item of items) {
                // If item is an object, format it directly
                if (typeof item === 'object' && item[valueField]) {
                    options.push(formatOption(item));
                } else {
                    // Otherwise fetch by ID
                    const opt = await fetchOptionById(item);
                    if (opt) options.push(opt);
                }
            }

            setSelectedOption(options);
        } else {
            // For single select
            const opt = await fetchOptionById(val);
            setSelectedOption(opt);
        }
    };

    // Sync internal state with external value
    useEffect(() => {
        if (value) {
            loadSelectedOption(value);
        } else {
            setSelectedOption(null);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [value]);

    const loadOptions = async (inputValue) => {
        try {
            // Merge existing params with new params
            const params = new URLSearchParams(existingParams);
            params.set('search', inputValue);
            params.set('page_size', '50');

            const {data} = await api.get(`${baseEndpoint}?${params.toString()}`);

            const results = data.results || data || [];
            return results.map(item => formatOption(item));
        } catch (err) {
            return [];
        }
    };

    const handleChange = (selected) => {
        setSelectedOption(selected);

        if (isMulti) {
            // Return array of values for API compatibility
            const values = selected ? selected.map(opt => opt.value) : [];
            onChange(values);
        } else {
            // Return single value
            onChange(selected ? selected.value : null);
        }
    };

    return (
        <AsyncSelect
            cacheOptions
            defaultOptions={loadOnMount}  // If false, loads only when dropdown opens
            loadOptions={loadOptions}
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
