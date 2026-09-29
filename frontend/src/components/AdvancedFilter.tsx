import { useCallback, useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import DebouncedAsyncSelect from "./DebouncedAsyncSelect";
import DebouncedSearchInput from "./DebouncedSearchInput";
import { FilterField, FilterGrid, FilterPanel } from "./filters/FilterPanel";
import { TextField, Stack, useTheme, FormControl, InputLabel, Select as MuiSelect, MenuItem, Box, Autocomplete, Chip, ToggleButton, ToggleButtonGroup, FormLabel } from "@mui/material";

/**
 * Segmented filter control using MUI ToggleButtonGroup for button_group and is_* filters.
 * Provides consistent styling with other form controls.
 */
function SegmentedFilter({
    label,
    value,
    choices,
    onChange,
    muiTheme,
}: {
    label: string;
    value: string | null;
    choices: Array<{ value: string; label: string; cls?: string }>;
    onChange: (val: string) => void;
    muiTheme: any;
}) {
    const normalizedValue = value === "all" || !value ? "all" : value;

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1, width: '100%' }}>
            <FormLabel sx={{ fontSize: '0.875rem', fontWeight: 600, color: muiTheme.palette.text.secondary }}>
                {label}
            </FormLabel>
            <ToggleButtonGroup
                value={normalizedValue}
                exclusive
                onChange={(e, val) => {
                    if (val !== null) onChange(val);
                }}
                size="small"
                sx={{
                    display: 'flex',
                    gap: 0.5,
                    flexWrap: 'wrap',
                    '& .MuiToggleButton-root': {
                        textTransform: 'none',
                        fontSize: '0.8125rem',
                        fontWeight: 500,
                        padding: '6px 12px',
                        border: `1px solid ${muiTheme.palette.divider}`,
                        borderRadius: muiTheme.shape.borderRadius,
                        color: muiTheme.palette.text.primary,
                        '&.Mui-selected': {
                            backgroundColor: muiTheme.palette.primary.light,
                            color: muiTheme.palette.primary.dark,
                            borderColor: muiTheme.palette.primary.main,
                            '&:hover': {
                                backgroundColor: muiTheme.palette.primary.light,
                            }
                        }
                    }
                }}
            >
                {choices.map((choice) => (
                    <ToggleButton
                        key={choice.value}
                        value={choice.value}
                        sx={{
                            ...(choice.value === "False" && {
                                '&.Mui-selected': {
                                    backgroundColor: '#f3e5e5 !important',
                                    color: muiTheme.palette.error.main,
                                    borderColor: muiTheme.palette.error.main,
                                }
                            })
                        }}
                    >
                        {choice.label}
                    </ToggleButton>
                ))}
            </ToggleButtonGroup>
        </Box>
    );
}

/**
 * Advanced filter — supports icontains, date_range, range, exact, in, fk,
 * choice, exclude_fk, button_group. Text input applies after a 400ms debounce;
 * select, date and toggle controls apply immediately.
 * All state/logic preserved verbatim — only Bootstrap markup → Tailwind.
 */
export default function AdvancedFilter({
    filterConfig = {},
    searchFields = [],
    onFilterChange,
    initialFilters = {} as Record<string, any>,
    defaultFilters = {} as Record<string, any>,
    resetToDefaults = false,
}: {
    filterConfig?: Record<string, any>;
    searchFields?: string[];
    onFilterChange?: (filters: Record<string, any>) => void;
    initialFilters?: Record<string, any>;
    defaultFilters?: Record<string, any>;
    resetToDefaults?: boolean;
}) {
    const [searchTerm, setSearchTerm] = useState(String(initialFilters.search || ""));
    const { search: _search, ...initialFiltersWithoutSearch } = initialFilters;
    const [filterValues, setFilterValues] = useState({ ...defaultFilters, ...initialFiltersWithoutSearch });
    const isInitialMount = useRef(true);
    const isAutoApplyInitialMount = useRef(true);
    const prevInitialFilters = useRef(initialFilters);
    const skipNextAutoApply = useRef(false);
    const muiTheme = useTheme();

    const toApiParams = useCallback((nextValues = filterValues, nextSearch = searchTerm) => {
        const params: Record<string, any> = {};
        if (nextSearch) params.search = nextSearch;
        Object.entries(nextValues).forEach(([key, value]) => {
            if (value === null || value === undefined || value === "") return;
            if (key.endsWith("_from")) params[`${key.replace("_from", "")}__gte`] = value;
            else if (key.endsWith("_to")) params[`${key.replace("_to", "")}__lte`] = value;
            else params[key] = value;
        });
        return params;
    }, []);

    useEffect(() => {
        if (isInitialMount.current) {
            isInitialMount.current = false;
            prevInitialFilters.current = initialFilters;
            return;
        }
        if (JSON.stringify(prevInitialFilters.current) !== JSON.stringify(initialFilters)) {
            prevInitialFilters.current = initialFilters;
            skipNextAutoApply.current = true;
            if (initialFilters.search !== undefined) setSearchTerm(initialFilters.search || "");
            const { search: _s, ...filtersWithoutSearch } = initialFilters;
            setFilterValues(() => ({ ...defaultFilters, ...filtersWithoutSearch }));
        }
    }, [initialFilters, defaultFilters]);

    useEffect(() => {
        if (isAutoApplyInitialMount.current) { isAutoApplyInitialMount.current = false; return; }
        if (skipNextAutoApply.current) { skipNextAutoApply.current = false; return; }
        const timeoutId = setTimeout(() => onFilterChange(toApiParams()), 400);
        return () => clearTimeout(timeoutId);
    }, [searchTerm, filterValues, onFilterChange]);

    const handleFilterChange = (field, value, immediate = false) =>
        setFilterValues((prev) => {
            const next = { ...prev, [field]: value };
            if (immediate) {
                skipNextAutoApply.current = true;
                onFilterChange(toApiParams(next));
            }
            return next;
        });

    const humanize = (fieldName: string) => fieldName
        .replace(/__?(gte|lte|icontains|exact)$/i, "")
        .replace(/_/g, " ")
        .replace(/\b\w/g, (c) => c.toUpperCase())
        .replace(/^Balance Balance /, "Balance ");

    const formatRangeLabel = (baseLabel: string): string => {
        let label = baseLabel;
        // Remove "Balance Balance " if present (from config.label being "Balance Balance Cif")
        if (label.startsWith("Balance Balance ")) {
            label = label.replace(/^Balance Balance /, "Balance ");
        }
        // Uppercase CIF -> CIF
        label = label.replace(/\bCif\b/i, "CIF");
        return label;
    };
    const isLicenseFilter = Object.keys(filterConfig).some((name) => /license|exporter|notification|norm|purchase|expired|balance/i.test(name));
    const primaryFilterNames = isLicenseFilter
        ? ["exporter", "license_number", "notification_number", "norm_class", "purchase_status", "license_status", "is_expired"]
        : Object.keys(filterConfig).slice(0, 6);
    const primaryEntries = Object.entries(filterConfig).filter(([field]) => primaryFilterNames.includes(field));
    const secondaryEntries = Object.entries(filterConfig).filter(([field]) => !primaryFilterNames.includes(field));

    const renderFilterField = (fieldName, config) => {
        const filterType = config.type || "exact";
        const label = config.label || humanize(fieldName);

        // Shared col wrapper with proper MUI spacing
        const Col = ({ wide = false, children }) => (
            <FilterField wide={wide}>
                {children}
            </FilterField>
        );

        switch (filterType) {
            case "icontains":
                return (
                    <Col key={fieldName}>
                        <TextField
                            fullWidth
                            size="medium"
                            label={label}
                            variant="outlined"
                            placeholder={`Search ${label.toLowerCase()}`}
                            value={filterValues[fieldName] || ""}
                            onChange={(e) => handleFilterChange(fieldName, e.target.value)}
                            sx={{
                              '& .MuiOutlinedInput-root': { height: '56px', py: 0.5 },
                              '& .MuiInputBase-input': { fontSize: '0.875rem' }
                            }}
                        />
                    </Col>
                );

            case "date_range": {
                const fromValue = filterValues[`${fieldName}_from`] || "";
                const toValue = filterValues[`${fieldName}_to`] || "";
                return (
                    <Col key={fieldName} wide>
                        <FormControl component="fieldset" fullWidth>
                            <FormLabel sx={{ fontSize: '0.875rem', fontWeight: 600, mb: 1.5, color: muiTheme.palette.text.secondary }}>
                                {label} Range
                            </FormLabel>
                            <Stack direction="row" spacing={1.5} sx={{ width: '100%' }}>
                                <TextField
                                    size="medium"
                                    type="date"
                                    label="From"
                                    variant="outlined"
                                    value={fromValue}
                                    onChange={(e) => handleFilterChange(`${fieldName}_from`, e.target.value, true)}
                                    slotProps={{ inputLabel: { shrink: true } }}
                                    sx={{
                                        flex: 1,
                                        '& .MuiOutlinedInput-root': { height: '56px', py: 0.5 },
                                        '& .MuiInputBase-input': { fontSize: '0.875rem' }
                                    }}
                                />
                                <TextField
                                    size="medium"
                                    type="date"
                                    label="To"
                                    variant="outlined"
                                    value={toValue}
                                    onChange={(e) => handleFilterChange(`${fieldName}_to`, e.target.value, true)}
                                    slotProps={{ inputLabel: { shrink: true } }}
                                    sx={{
                                        flex: 1,
                                        '& .MuiOutlinedInput-root': { height: '56px', py: 0.5 },
                                        '& .MuiInputBase-input': { fontSize: '0.875rem' }
                                    }}
                                />
                            </Stack>
                        </FormControl>
                    </Col>
                );
            }

            case "range": {
                const minField = config.min_field || `${fieldName}_min`;
                const maxField = config.max_field || `${fieldName}_max`;
                const rangeLabel = formatRangeLabel(label);
                return (
                    <Col key={fieldName} wide>
                        <Stack direction="row" spacing={1.5} sx={{ width: '100%' }}>
                            <TextField
                                size="medium"
                                type="number"
                                label={`${rangeLabel} Min`}
                                variant="outlined"
                                value={filterValues[minField] || ""}
                                onChange={(e) => handleFilterChange(minField, e.target.value)}
                                sx={{
                                  flex: 1,
                                  '& .MuiOutlinedInput-root': { height: '56px', py: 0.5 },
                                  '& .MuiInputBase-input': { fontSize: '0.875rem' }
                                }}
                            />
                            <TextField
                                size="medium"
                                type="number"
                                label={`${rangeLabel} Max`}
                                variant="outlined"
                                value={filterValues[maxField] || ""}
                                onChange={(e) => handleFilterChange(maxField, e.target.value)}
                                sx={{
                                  flex: 1,
                                  '& .MuiOutlinedInput-root': { height: '56px', py: 0.5 },
                                  '& .MuiInputBase-input': { fontSize: '0.875rem' }
                                }}
                            />
                        </Stack>
                    </Col>
                );
            }

            case "exact": {
                if (config.choices && config.choices.length > 0) {
                    const opts = config.choices.map((c) => Array.isArray(c) ? { value: c[0], label: c[1] } : typeof c === "object" ? c : { value: c, label: c });
                    return (
                        <Col key={fieldName}>
                            <FormControl fullWidth size="small" variant="outlined">
                                <InputLabel id={`${fieldName}-label`}>{label}</InputLabel>
                                <MuiSelect
                                    labelId={`${fieldName}-label`}
                                    id={fieldName}
                                    value={filterValues[fieldName] || ""}
                                    label={label}
                                    onChange={(e) => handleFilterChange(fieldName, e.target.value, true)}
                                    sx={{
                                        height: '56px',
                                        '& .MuiOutlinedInput-input': { fontSize: '0.875rem' }
                                    }}
                                >
                                    <MenuItem value=""><em>Select {label.toLowerCase()}</em></MenuItem>
                                    {opts.map((opt) => (
                                        <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
                                    ))}
                                </MuiSelect>
                            </FormControl>
                        </Col>
                    );
                }
                if (fieldName.startsWith("is_") || fieldName.startsWith("has_") || fieldName.includes("__is_") || fieldName.includes("__has_")) {
                    return (
                        <Col key={fieldName}>
                            <SegmentedFilter
                                label={label}
                                value={filterValues[fieldName] || "all"}
                                choices={[
                                    { value: "all", label: "All" },
                                    { value: "True", label: "Yes" },
                                    { value: "False", label: "No" },
                                ]}
                                onChange={(val) => handleFilterChange(fieldName, val, true)}
                                muiTheme={muiTheme}
                            />
                        </Col>
                    );
                }
                return (
                    <Col key={fieldName}>
                        <TextField
                            fullWidth
                            size="medium"
                            label={label}
                            variant="outlined"
                            placeholder={`${label}`}
                            value={filterValues[fieldName] || ""}
                            onChange={(e) => handleFilterChange(fieldName, e.target.value)}
                            sx={{
                              '& .MuiOutlinedInput-root': { height: '56px', py: 0.5 },
                              '& .MuiInputBase-input': { fontSize: '0.875rem' }
                            }}
                        />
                    </Col>
                );
            }

            case "in":
                return (
                    <Col key={fieldName}>
                        <TextField
                            fullWidth
                            size="medium"
                            label={label}
                            variant="outlined"
                            placeholder="Comma-separated values"
                            value={filterValues[fieldName] || ""}
                            onChange={(e) => handleFilterChange(fieldName, e.target.value)}
                            helperText="Enter values separated by commas"
                            sx={{
                              '& .MuiOutlinedInput-root': { height: '56px', py: 0.5 },
                              '& .MuiInputBase-input': { fontSize: '0.875rem' }
                            }}
                        />
                    </Col>
                );

            case "fk":
                return (
                    <Col key={fieldName}>
                        <DebouncedAsyncSelect
                            endpoint={config.fk_endpoint || config.endpoint}
                            labelField={config.label_field || "name"}
                            value={filterValues[fieldName] || ""}
                            onChange={(val) => handleFilterChange(fieldName, val)}
                            placeholder={`Select ${label.toLowerCase()}`}
                            isClearable
                            isMulti
                            debounceDelay={300}
                            fieldLabel={label}
                        />
                    </Col>
                );

            case "button_group": {
                const bgChoices = (config.choices || []).map((c) => Array.isArray(c) ? { value: c[0], label: c[1] } : typeof c === "object" ? c : { value: c, label: c });
                return (
                    <Col key={fieldName} wide>
                        <SegmentedFilter
                            label={label}
                            value={filterValues[fieldName] || ""}
                            choices={bgChoices}
                            onChange={(val) => handleFilterChange(fieldName, val, true)}
                            muiTheme={muiTheme}
                        />
                    </Col>
                );
            }

            case "choice": {
                const choiceOpts = (config.choices || []).map((c) => Array.isArray(c) ? { value: c[0], label: c[1] } : typeof c === "object" ? c : { value: c, label: c });
                const selectedValues = filterValues[fieldName]
                    ? (typeof filterValues[fieldName] === "string" ? filterValues[fieldName].split(",") : filterValues[fieldName])
                    : [];
                const limitTags = 2;
                const hiddenCount = Math.max(0, selectedValues.length - limitTags);
                return (
                    <Col key={fieldName}>
                        <FormControl fullWidth size="small" variant="outlined">
                            <InputLabel id={`${fieldName}-label`}>{label}</InputLabel>
                            <MuiSelect
                                labelId={`${fieldName}-label`}
                                id={fieldName}
                                multiple
                                value={selectedValues}
                                label={label}
                                onChange={(e) => handleFilterChange(fieldName, typeof e.target.value === 'string' ? e.target.value.split(',') : e.target.value.join(','), true)}
                                renderValue={(selected) => (
                                    <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap', alignItems: 'center' }}>
                                        {selected.slice(0, limitTags).map((value) => {
                                            const opt = choiceOpts.find(o => o.value === value);
                                            return <Chip key={value} label={opt?.label || value} size="small" sx={{ maxWidth: '100%' }} />;
                                        })}
                                        {hiddenCount > 0 && (
                                            <Chip label={`+${hiddenCount}`} size="small" variant="outlined" sx={{ maxWidth: '100%', pointerEvents: 'none' }} />
                                        )}
                                    </Box>
                                )}
                                sx={{
                                    minHeight: '56px',
                                    '& .MuiOutlinedInput-input': { fontSize: '0.875rem' }
                                }}
                            >
                                {choiceOpts.map((opt) => (
                                    <MenuItem key={opt.value} value={opt.value}>{opt.label}</MenuItem>
                                ))}
                            </MuiSelect>
                        </FormControl>
                    </Col>
                );
            }

            case "exclude_fk":
                return (
                    <Col key={fieldName}>
                        <DebouncedAsyncSelect
                            endpoint={config.fk_endpoint || config.endpoint}
                            labelField={config.label_field || "name"}
                            value={filterValues[fieldName] || ""}
                            onChange={(val) => handleFilterChange(fieldName, val)}
                            placeholder={`Exclude ${label.toLowerCase()}`}
                            isClearable
                            isMulti
                            debounceDelay={300}
                            fieldLabel={label}
                        />
                    </Col>
                );

            default:
                return (
                    <Col key={fieldName}>
                        <TextField
                            fullWidth
                            size="medium"
                            label={label}
                            variant="outlined"
                            placeholder={`Filter ${label.toLowerCase()}`}
                            value={filterValues[fieldName] || ""}
                            onChange={(e) => handleFilterChange(fieldName, e.target.value)}
                            sx={{
                              '& .MuiOutlinedInput-root': { height: '56px', py: 0.5 },
                              '& .MuiInputBase-input': { fontSize: '0.875rem' }
                            }}
                        />
                    </Col>
                );
        }
    };

    if (Object.keys(filterConfig).length === 0 && searchFields.length === 0) return null;

    return (
        <div className="w-full mb-4">
            {/* Search bar */}
            {searchFields.length > 0 && (
                <div className="mb-3">
                    <DebouncedSearchInput
                        value={searchTerm}
                        onChange={setSearchTerm}
                        delay={400}
                        placeholder={`Search by ${searchFields.join(", ")}`}
                    />
                </div>
            )}

            {/* Compact primary toolbar with progressive disclosure. */}
            {Object.keys(filterConfig).length > 0 && <FilterPanel onFiltersChange={() => {}}><FilterGrid>{primaryEntries.map(([fieldName, config]) => renderFilterField(fieldName, config))}{secondaryEntries.map(([fieldName, config]) => renderFilterField(fieldName, config))}</FilterGrid></FilterPanel>}
        </div>
    );
}
