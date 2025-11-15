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
    className = ""
}) {
    const [defaultOptions, setDefaultOptions] = useState([]);
    const [selectedOption, setSelectedOption] = useState(null);

    // Load default options on mount
    useEffect(() => {
        loadDefaultOptions();
    }, [endpoint]);

    // Sync internal state with external value
    useEffect(() => {
        if (value) {
            loadSelectedOption(value);
        } else {
            setSelectedOption(null);
        }
    }, [value]);

    const loadDefaultOptions = async () => {
        try {
            const {data} = await api.get(endpoint, {
                params: {page_size: 50} // Load first 50 options
            });

            const results = data.results || data || [];
            const options = results.map(item => formatOption(item));
            setDefaultOptions(options);
        } catch (err) {
            console.error("Error loading default options:", err);
            setDefaultOptions([]);
        }
    };

    const loadSelectedOption = async (val) => {
        if (!val) {
            setSelectedOption(null);
            return;
        }

        if (isMulti) {
            // For multi-select, val should be an array of IDs
            const ids = Array.isArray(val) ? val : [val];
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
            // Check if option exists in defaultOptions first
            const existing = defaultOptions.find(opt => opt.value === id);
            if (existing) return existing;

            // Otherwise fetch from API
            const {data} = await api.get(`${endpoint}${id}/`);
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
            defaultOptions={defaultOptions}
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
