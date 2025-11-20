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
    const [selectedOption, setSelectedOption] = useState(null);

    // Sync internal state with external value
    useEffect(() => {
        if (value) {
            loadSelectedOption(value);
        } else {
            setSelectedOption(null);
        }
    }, [value]);

    // Only load default options if explicitly requested (not used for filters)
    const loadDefaultOptions = async () => {
        if (!loadOnMount) {
            // For lazy loading (filters), return empty and let loadOptions handle it
            return [];
        }

        try {
            const {data} = await api.get(endpoint, {
                params: {page_size: 50} // Load first 50 options
            });

            const results = data.results || data || [];
            return results.map(item => formatOption(item));
        } catch (err) {
            console.error("Error loading default options:", err);
            return [];
        }
    };

    const loadSelectedOption = async (val) => {
        if (!val) {
            setSelectedOption(null);
            return;
        }

        if (isMulti) {
            // For multi-select, val should be an array of IDs
            let ids = Array.isArray(val) ? val : [val];

            // Handle comma-separated string values
            if (ids.length === 1 && typeof ids[0] === 'string' && ids[0].includes(',')) {
                ids = ids[0].split(',').map(id => id.trim()).filter(id => id);
            }

            const options = [];

            for (const id of ids) {
                const opt = await fetchOptionById(id);
                if (opt) options.push(opt);
            }

            setSelectedOption(options);
        } else {
            // For single select
            const opt = await fetchOptionById(val);
            setSelectedOption(opt);
        }
    };

    const fetchOptionById = async (id) => {
        try {
            // Parse ID if it's a number string
            const numId = typeof id === 'string' ? parseInt(id, 10) : id;

            // Fetch from API
            const {data} = await api.get(`${endpoint}${numId}/`);
            return formatOption(data);
        } catch (err) {
            console.error(`Error fetching option ${id}:`, err);
            return null;
        }
    };

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

    const loadOptions = async (inputValue) => {
        try {
            const {data} = await api.get(endpoint, {
                params: {
                    search: inputValue,
                    page_size: 50
                }
            });

            const results = data.results || data || [];
            return results.map(item => formatOption(item));
        } catch (err) {
            console.error("Error loading options:", err);
            return [];
        }
    };

    const handleChange = (selected) => {
        setSelectedOption(selected);

        if (isMulti) {
            // Return array of values
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
