import {useState, useEffect, useCallback, useMemo, useRef} from "react";
import AsyncSelect from "react-select/async";
import api from "../api/axios";
import { useDebouncedCallback } from "../hooks/useDebounce";
import { Autocomplete, TextField, Chip, CircularProgress, Box } from "@mui/material";

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
    const [focused, setFocused] = useState(false);
    let cleanEndpoint = endpoint?.startsWith('/api/') ? endpoint.substring(5) : endpoint;
    const [baseEndpoint, queryString] = cleanEndpoint?.split('?') || [cleanEndpoint, ''];
    const existingParams = useMemo(() => new URLSearchParams(queryString), [queryString]);

    const [selectedOption, setSelectedOption] = useState(null);
    const [isSearching, setIsSearching] = useState(false);
    const [open, setOpen] = useState(false);
    const [options, setOptions] = useState([]);
    const [inputValue, setInputValue] = useState('');
    const useMUIMode = Boolean(fieldLabel);
    // muiTheme may be needed for future styling customization

    // Use a ref to track the current abort controller for request cancellation
    const abortControllerRef = useRef<AbortController | null>(null);

    const formatOption = useCallback((item) => {
        let label;

        if (formatLabel) {
            label = formatLabel(item);
        } else {
            // Try to get label from the configured labelField, fall back to other common label fields
            label = item[labelField] || item['label'] || item['name'] || item[valueField] || String(item.id);
        }

        return {
            value: item[valueField],
            label: label,
            data: item
        };
    }, [formatLabel, labelField, valueField]);

    // Cache for master data to resolve IDs to labels
    const masterCacheRef = useRef<Map<string | number, any>>(new Map());

    // Sync internal state with external value, resolving IDs to labels
    useEffect(() => {
        if (!value) {
            setSelectedOption(null);
            return;
        }

        const resolveValue = async () => {
            // Helper to resolve master data
            const getResolutionCache = async () => {
                if (masterCacheRef.current.size > 0) {
                    return masterCacheRef.current;
                }

                try {
                    const params = new URLSearchParams(existingParams);
                    params.set('page_size', '1000');
                    const fullUrl = `${baseEndpoint}?${params.toString()}`;
                    const { data } = await api.get(fullUrl);
                    const results = data.results || data || [];

                    const cache = new Map();
                    results.forEach((item: any) => {
                        // Cache by both string and number ID to handle mismatches
                        cache.set(item.id, item);
                        cache.set(String(item.id), item);
                    });

                    masterCacheRef.current = cache;
                    return cache;
                } catch (err: any) {
                    return new Map();
                }
            };

            if (typeof value === 'object' && !Array.isArray(value)) {
                if (value[valueField]) {
                    setSelectedOption(formatOption(value));
                }
                return;
            }

            if (isMulti) {
                let items = Array.isArray(value) ? value : [value];

                if (items.length === 1 && typeof items[0] === 'string' && items[0].includes(',')) {
                    items = items[0].split(',').map(id => id.trim()).filter(id => id);
                }

                items = items.filter(item => item !== null && item !== undefined && item !== '');

                const cache = await getResolutionCache();
                const options = [];

                for (const item of items) {
                    if (typeof item === 'object' && item[valueField]) {
                        options.push(formatOption(item));
                    } else {
                        const masterItem = cache.get(item);
                        if (masterItem) {
                            options.push(formatOption(masterItem));
                        } else {
                            // Fallback: use the item value as-is if not found in master data
                            options.push({
                                value: item,
                                label: String(item),
                                data: null
                            });
                        }
                    }
                }

                setSelectedOption(options);
            } else {
                if (typeof value === 'object' && value[valueField]) {
                    setSelectedOption(formatOption(value));
                } else {
                    const cache = await getResolutionCache();
                    const masterItem = cache.get(value);
                    if (masterItem) {
                        setSelectedOption(formatOption(masterItem));
                    } else {
                        setSelectedOption({
                            value: value,
                            label: String(value),
                            data: null
                        });
                    }
                }
            }
        };

        resolveValue();
    }, [value, valueField, isMulti, formatOption, baseEndpoint, existingParams]);

    // Debounced API call and fetch function declarations moved before useEffect
    // to avoid forward reference errors
    const _fetchOptionsFromAPI = useCallback(async (inputValue: string) => {
        try {
            // Cancel previous request if it's still pending
            if (abortControllerRef.current) {
                abortControllerRef.current.abort();
            }

            // Create new abort controller for this request
            const abortController = new AbortController();
            abortControllerRef.current = abortController;

            const params = new URLSearchParams(existingParams);
            params.set('search', inputValue);
            params.set('page_size', '50');

            const { data } = await api.get(`${baseEndpoint}?${params.toString()}`, {
                signal: abortController.signal
            });

            const results = data.results || data || [];
            return results.map(item => formatOption(item));
        } catch (err: any) {
            // Don't log abort errors - they're expected behavior
            if (err?.name !== 'AbortError' && err?.code !== 'ERR_CANCELED') {
                console.error('Fetch error:', err);
            }
            return [];
        } finally {
            setIsSearching(false);
        }
    }, [baseEndpoint, existingParams, formatOption]);

    // Create debounced version
    const _debouncedFetch = useDebouncedCallback(_fetchOptionsFromAPI, debounceDelay);

    // Handle MUI Autocomplete options fetching
    useEffect(() => {
        if (!useMUIMode) return;
        if (!open) {
            setOptions([]);
            return;
        }

        // Don't fetch with empty/whitespace search - wait for user to type
        if (inputValue.trim() === '') {
            setOptions([]);
            return;
        }

        _debouncedFetch(inputValue)
            .then(results => {
                if (results) setOptions(results);
            })
            .catch((err) => {
                // Ignore abort errors - they're expected when user types quickly
                if (err?.name !== 'AbortError' && err?.code !== 'ERR_CANCELED') {
                    setOptions([]);
                }
            });
    }, [inputValue, open, useMUIMode, _debouncedFetch]);

    // Wrapper that returns a promise for react-select
    const loadOptions = (inputValue: string, callback: any) => {
        setIsSearching(true);

        // Call the debounced function and handle the result
        _debouncedFetch(inputValue)
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

        const renderTagsFunc = isMulti
            ? (value: typeof selectedOption, getTagProps: (config: any) => any) => {
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
            : undefined;

        // Build the autocompleteProps without renderTags first
        const autocompleteProps: any = {
            fullWidth: true,
            open,
            onOpen: () => {
                setOpen(true);
                setFocused(true);
            },
            onClose: () => {
                setOpen(false);
                setFocused(false);
            },
            onFocus: () => setFocused(true),
            onBlur: () => setFocused(false),
            isOptionEqualToValue: (option: any, value: any) => {
                if (!option || !value) return false;
                return option.value === value.value;
            },
            getOptionLabel: (option: any) => {
                if (typeof option === 'string') return option;
                return option.label || '';
            },
            options,
            loading: isSearching,
            value: selectedOption || (isMulti ? [] : null),
            inputValue,
            onChange: (event: any, newValue: any) => {
                handleChange(newValue);
            },
            onInputChange: (event: any, newInputValue: string, reason: string) => {
                // Only update inputValue for actual user input, not for MUI's internal resets
                // reason="reset" happens when options change, which would clear the user's typing
                if (reason !== 'reset') {
                    setInputValue(newInputValue);
                }
            },
            multiple: isMulti,
            disableCloseOnSelect: isMulti,
            filterOptions: (x: any) => x,
            noOptionsText: inputValue === '' ? 'Start typing to search...' : 'No options',
            slotProps: {
                paper: {
                    sx: {
                        '& .MuiAutocomplete-listbox': {
                            maxHeight: '200px',
                        }
                    }
                }
            },
            renderInput: (params: any) => {
                // Exclude renderTags and renderInput from params spread
                // These cause prop warnings and aren't needed for TextField
                const { InputProps: baseInputProps, renderTags, renderInput, ...safeParams } = params;

                const newInputProps = {
                    ...baseInputProps,
                    endAdornment: (
                        <>
                            {isSearching ? <CircularProgress color="inherit" size={20} /> : null}
                            {baseInputProps?.endAdornment}
                        </>
                    ),
                };

                return (
                    <TextField
                        {...safeParams}
                        label={fieldLabel}
                        placeholder={placeholder}
                        InputProps={newInputProps}
                        sx={{
                            '& .MuiOutlinedInput-root': {
                                minHeight: '56px',
                                paddingY: 0.5
                            },
                            '& .MuiInputBase-input': {
                                fontSize: '0.875rem',
                                color: 'inherit',
                                opacity: 1,
                                caretColor: 'inherit'
                            },
                        }}
                    />
                );
            }
        };

        // Only add renderTags for multi-select to avoid prop warning on single-select
        if (isMulti && renderTagsFunc) {
            autocompleteProps.renderTags = renderTagsFunc;
        }

        return <Autocomplete {...autocompleteProps} />;
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
