import {useState, useEffect, useCallback, useMemo} from "react";
import AsyncSelect from "react-select/async";
import api from "../api/axios";
import { useDebouncedCallback } from "../hooks/useDebounce";
import { Autocomplete, TextField, Chip, CircularProgress, Box } from "@mui/material";
import { useTheme } from "@mui/material/styles";

/**
 * Debounced AsyncSelectField Component
 *
 * A debounced version of AsyncSelectField that reduces API calls while typing.
 * Includes loading indicator during debounce period.
 *
 * @param {string} endpoint - API endpoint to fetch options (required)
 * @param {string} labelField - Field name to use as label (default: 'name')
 * @param {string} valueField - Field name to use as value (default: 'id')
 * @param {*} value - Current selected value(s)
 * @param {function} onChange - Callback function(value)
 * @param {boolean} isMulti - Enable multi-select (default: false)
 * @param {string} placeholder - Placeholder text
 * @param {boolean} isClearable - Allow clearing selection (default: true)
 * @param {boolean} isDisabled - Disable the select
 * @param {function} formatLabel - Custom function to format option label
 * @param {number} debounceDelay - Debounce delay in milliseconds (default: 300)
 * @param {boolean} loadOnMount - Control whether to load options on mount (default: false)
 * @param {string} fieldLabel - Label for MUI TextField (optional - enables MUI mode)
 * @param {number} limitTags - Maximum number of tags to show at once in multi-select (default: 2)
 *
 * @example
 * <DebouncedAsyncSelect
 *   endpoint="/companies/"
 *   value={selectedCompany}
 *   onChange={setSelectedCompany}
 *   debounceDelay={500}
 *   placeholder="Search companies..."
 *   fieldLabel="Company"
 *   limitTags={2}
 * />
 */
export default function DebouncedAsyncSelect({
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
    loadOnMount = false,
    debounceDelay = 300,
    fieldLabel = null,
    limitTags = 2,
}) {
    const muiTheme = useTheme();
    const [focused, setFocused] = useState(false);
    // Strip /api/ prefix if it exists to avoid double /api/api/
    let cleanEndpoint = endpoint?.startsWith('/api/') ? endpoint.substring(5) : endpoint;

    // Parse endpoint to separate base URL and existing query params
    const [baseEndpoint, queryString] = cleanEndpoint?.split('?') || [cleanEndpoint, ''];
    const existingParams = useMemo(() => new URLSearchParams(queryString), [queryString]);

    const [selectedOption, setSelectedOption] = useState(null);
    const [isSearching, setIsSearching] = useState(false);
    const [open, setOpen] = useState(false);
    const [options, setOptions] = useState([]);
    const [inputValue, setInputValue] = useState('');
    const useMUIMode = Boolean(fieldLabel);
    // muiTheme may be needed for future styling customization

    const formatOption = useCallback((item) => {
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
    }, [formatLabel, labelField, valueField]);

    const fetchOptionById = async (id) => {
        try {
            const numId = typeof id === 'string' ? parseInt(id, 10) : id;
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

        if (typeof val === 'object' && !Array.isArray(val) && val[valueField]) {
            setSelectedOption(formatOption(val));
            return;
        }

        if (isMulti) {
            let items = Array.isArray(val) ? val : [val];

            if (items.length === 1 && typeof items[0] === 'string' && items[0].includes(',')) {
                items = items[0].split(',').map(id => id.trim()).filter(id => id);
            }

            items = items.filter(item => item !== null && item !== undefined && item !== '');

            const options = [];

            for (const item of items) {
                if (typeof item === 'object' && item[valueField]) {
                    options.push(formatOption(item));
                } else {
                    const opt = await fetchOptionById(item);
                    if (opt) options.push(opt);
                }
            }

            setSelectedOption(options);
        } else {
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

    // Handle MUI Autocomplete options fetching
    // eslint-disable-next-line react-hooks/exhaustive-deps
    useEffect(() => {
        if (!useMUIMode) return;
        if (!open) {
            setOptions([]);
            return;
        }

        if (inputValue === '') {
            setOptions([]);
            return;
        }

        debouncedFetch(inputValue)
            .then(results => { setOptions(results || []); })
            .catch(() => { setOptions([]); });
    }, [inputValue, open, useMUIMode]);

    // Debounced API call function
    const fetchOptionsFromAPI = useCallback(async (inputValue) => {
        try {
            const params = new URLSearchParams(existingParams);
            params.set('search', inputValue);
            params.set('page_size', '50');

            const {data} = await api.get(`${baseEndpoint}?${params.toString()}`);

            const results = data.results || data || [];
            return results.map(item => formatOption(item));
        } catch (err) {
            return [];
        } finally {
            setIsSearching(false);
        }
    }, [baseEndpoint, existingParams, formatOption]);

    // Create debounced version
    const debouncedFetch = useDebouncedCallback(fetchOptionsFromAPI, debounceDelay);

    // Wrapper that returns a promise for react-select
    const loadOptions = (inputValue, callback) => {
        setIsSearching(true);

        // Call the debounced function and handle the result
        debouncedFetch(inputValue)
            .then(options => { if (callback) callback(options); })
            .catch(() => { if (callback) callback([]); });
    };

    const handleChange = (selected) => {
        setSelectedOption(selected);

        if (isMulti) {
            const values = selected ? selected.map(opt => opt.value) : [];
            onChange(values);
        } else {
            onChange(selected ? selected.value : null);
        }
    };

    // Use MUI Autocomplete if fieldLabel is provided
    if (useMUIMode) {
        const hiddenTagCount = isMulti && selectedOption && Array.isArray(selectedOption) && !focused
            ? Math.max(0, selectedOption.length - limitTags)
            : 0;

        return (
            <Autocomplete
                fullWidth
                open={open}
                onOpen={() => {
                    setOpen(true);
                    setFocused(true);
                }}
                onClose={() => {
                    setOpen(false);
                    setFocused(false);
                }}
                onFocus={() => setFocused(true)}
                onBlur={() => setFocused(false)}
                isOptionEqualToValue={(option, value) => {
                    if (!option || !value) return false;
                    return option.value === value.value;
                }}
                getOptionLabel={(option) => {
                    if (typeof option === 'string') return option;
                    return option.label || '';
                }}
                options={options}
                loading={isSearching}
                value={selectedOption || (isMulti ? [] : null)}
                onChange={(event, newValue) => {
                    handleChange(newValue);
                }}
                onInputChange={(event, newInputValue) => {
                    setInputValue(newInputValue);
                }}
                multiple={isMulti}
                disableCloseOnSelect={isMulti}
                filterOptions={(x) => x}
                noOptionsText={inputValue === '' ? 'Start typing to search...' : 'No options'}
                {...(isMulti && {
                    renderTags: (value, getTagProps) => {
                        const displayedTags = focused ? value : value.slice(0, limitTags);
                        return (
                            <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', alignItems: 'center' }}>
                                {displayedTags.map((option, index) => (
                                    <Chip
                                        {...getTagProps({ index })}
                                        key={option.value}
                                        label={option.label}
                                        size="small"
                                        sx={{ maxWidth: '100%' }}
                                    />
                                ))}
                                {!focused && hiddenTagCount > 0 && (
                                    <Chip
                                        label={`+${hiddenTagCount}`}
                                        size="small"
                                        variant="outlined"
                                        sx={{ maxWidth: '100%', pointerEvents: 'none' }}
                                    />
                                )}
                            </Box>
                        );
                    }
                })}
                slotProps={{
                    paper: {
                        sx: {
                            '& .MuiAutocomplete-listbox': {
                                maxHeight: '200px',
                            }
                        }
                    }
                }}
                renderInput={(params) => (
                    <TextField
                        {...params}
                        label={fieldLabel}
                        placeholder={placeholder}
                        variant="outlined"
                        size="medium"
                        sx={{
                            '& .MuiOutlinedInput-root': {
                                minHeight: '56px',
                                paddingY: 0.5
                            },
                            '& .MuiInputBase-input': {
                                fontSize: '0.875rem'
                            }
                        }}
                        slotProps={{
                            input: {
                                ...params.slotProps?.input,
                                endAdornment: (
                                    <>
                                        {isSearching ? <CircularProgress color="inherit" size={20} /> : null}
                                        {params.slotProps?.input?.endAdornment}
                                    </>
                                ),
                            },
                        }}
                    />
                )}
            />
        );
    }

    // Fall back to react-select for legacy use without fieldLabel
    return (
        <div className="position-relative">
            <AsyncSelect
                cacheOptions
                defaultOptions={loadOnMount}
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
                        borderColor: "var(--tb-border)"
                    }),
                    menu: (base) => ({
                        ...base,
                        zIndex: 9999
                    })
                }}
            />

            {/* Searching indicator */}
            {isSearching && (
                <div
                    className="position-absolute end-0 top-50 translate-middle-y"
                    style={{ pointerEvents: 'none', marginRight: '40px', zIndex: 10000 }}
                >
                    <span className="inline-block size-3.5 animate-spin rounded-full border-2 border-current border-t-transparent text-primary" aria-hidden="true" />
                </div>
            )}
        </div>
    );
}
