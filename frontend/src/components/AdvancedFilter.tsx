import { useCallback, useEffect, useRef, useState } from "react";
import { X } from "lucide-react";
import Select from "react-select";
import DebouncedAsyncSelect from "./DebouncedAsyncSelect";
import DebouncedSearchInput from "./DebouncedSearchInput";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import DateRangeFilter from "./DateRangeFilter";
import { FilterField, FilterGrid, FilterPanel } from "./filters/FilterPanel";
import { TextField, Stack, useTheme } from "@mui/material";

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
    isUpdating = false,
}: {
    filterConfig?: Record<string, any>;
    searchFields?: string[];
    onFilterChange?: (filters: Record<string, any>) => void;
    initialFilters?: Record<string, any>;
    defaultFilters?: Record<string, any>;
    resetToDefaults?: boolean;
    isUpdating?: boolean;
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
    }, [filterValues, searchTerm]);

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
    }, [searchTerm, filterValues, onFilterChange, toApiParams]);

    const handleFilterChange = (field, value, immediate = false) =>
        setFilterValues((prev) => {
            const next = { ...prev, [field]: value };
            if (immediate) {
                skipNextAutoApply.current = true;
                onFilterChange(toApiParams(next));
            }
            return next;
        });

    const handleResetFilters = () => {
        setSearchTerm("");
        setFilterValues(resetToDefaults ? defaultFilters : {});
    };

    const humanize = (fieldName: string) => fieldName
        .replace(/__?(gte|lte|icontains|exact)$/i, "")
        .replace(/_/g, " ")
        .replace(/\b\w/g, (c) => c.toUpperCase())
        .replace(/^Balance Balance /, "Balance ");
    const isLicenseFilter = Object.keys(filterConfig).some((name) => /license|exporter|notification|norm|purchase|expired|balance/i.test(name));
    const primaryFilterNames = isLicenseFilter
        ? ["exporter", "license_number", "notification_number", "norm_class", "purchase_status", "license_status", "is_expired"]
        : Object.keys(filterConfig).slice(0, 6);
    const primaryEntries = Object.entries(filterConfig).filter(([field]) => primaryFilterNames.includes(field));
    const secondaryEntries = Object.entries(filterConfig).filter(([field]) => !primaryFilterNames.includes(field));

    // shared style token for react-select with Material Design height (40-44px)
    const rsControl = (base) => ({
        ...base,
        minHeight: "42px",
        height: "42px",
        borderColor: muiTheme.palette.divider,
        borderRadius: muiTheme.shape.borderRadius,
        fontSize: "0.875rem",
    });

    const rsMultiSelectStyles = {
        control: rsControl,
        valueContainer: (base) => ({
            ...base,
            maxHeight: "100%",
            padding: "4px 8px",
            flexWrap: "wrap",
        }),
        multiValue: (base) => ({
            ...base,
            fontSize: "0.8125rem",
            margin: "2px 2px 2px 0",
            backgroundColor: muiTheme.palette.primary.light,
            color: muiTheme.palette.primary.contrastText,
            borderRadius: muiTheme.shape.borderRadius,
        }),
        multiValueLabel: (base) => ({
            ...base,
            whiteSpace: "nowrap",
            overflow: "hidden",
            textOverflow: "ellipsis",
            padding: "0 4px",
        }),
        multiValueRemove: (base) => ({
            ...base,
            color: muiTheme.palette.primary.contrastText,
            cursor: "pointer",
            paddingRight: "4px",
            '&:hover': {
                opacity: 0.8,
            }
        }),
        menu: (base) => ({
            ...base,
            zIndex: 9999
        })
    };

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
                            size="small"
                            label={label}
                            variant="outlined"
                            placeholder={`Search ${label.toLowerCase()}`}
                            value={filterValues[fieldName] || ""}
                            onChange={(e) => handleFilterChange(fieldName, e.target.value)}
                            sx={{
                              '& .MuiOutlinedInput-root': { height: '42px' },
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
                        <DateRangeFilter
                            label={`${label} Range`}
                            fromValue={fromValue}
                            toValue={toValue}
                            onFromChange={(v) => handleFilterChange(`${fieldName}_from`, v, true)}
                            onToChange={(v) => handleFilterChange(`${fieldName}_to`, v, true)}
                        />
                    </Col>
                );
            }

            case "range": {
                const minField = config.min_field || `${fieldName}_min`;
                const maxField = config.max_field || `${fieldName}_max`;
                return (
                    <Col key={fieldName} wide>
                        <Stack direction="row" spacing={1} sx={{ width: '100%' }}>
                            <TextField
                                size="small"
                                type="number"
                                label={`${label} Min`}
                                variant="outlined"
                                value={filterValues[minField] || ""}
                                onChange={(e) => handleFilterChange(minField, e.target.value)}
                                sx={{
                                  flex: 1,
                                  '& .MuiOutlinedInput-root': { height: '42px' },
                                  '& .MuiInputBase-input': { fontSize: '0.875rem' }
                                }}
                            />
                            <TextField
                                size="small"
                                type="number"
                                label={`${label} Max`}
                                variant="outlined"
                                value={filterValues[maxField] || ""}
                                onChange={(e) => handleFilterChange(maxField, e.target.value)}
                                sx={{
                                  flex: 1,
                                  '& .MuiOutlinedInput-root': { height: '42px' },
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
                    const selected = opts.find((o) => o.value === filterValues[fieldName]) || null;
                    return (
                        <Col key={fieldName}>
                            <Label className="mb-2">{label}</Label>
                            <Select options={opts} value={selected} onChange={(s) => handleFilterChange(fieldName, s ? s.value : "", true)} isClearable placeholder={`Select ${label.toLowerCase()}`} styles={{ control: rsControl }} classNamePrefix="react-select" />
                        </Col>
                    );
                }
                if (fieldName.startsWith("is_") || fieldName.startsWith("has_") || fieldName.includes("__is_") || fieldName.includes("__has_")) {
                    const cur = filterValues[fieldName];
                    const isAll = cur === "all" || (!cur && cur !== "True" && cur !== "False");
                    return (
                        <Col key={fieldName}>
                            <Label className="mb-2 block">{label}</Label>
                            <div className="flex gap-2">
                                {[{ val: "all", lbl: "All", cls: "secondary" }, { val: "True", lbl: "Yes", cls: "success" }, { val: "False", lbl: "No", cls: "danger" }].map(({ val, lbl, cls }) => {
                                    const active = val === "all" ? isAll : cur === val || cur === (val === "True");
                                    return (
                                        <button
                                            key={val}
                                            type="button"
                                            onClick={() => handleFilterChange(fieldName, val, true)}
                                            className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer ${active ? (cls === "success" ? "border-success bg-success/15 text-success" : cls === "danger" ? "border-destructive bg-destructive/15 text-destructive" : "border-primary bg-primary/15 text-primary") : "border-border bg-card text-muted-foreground hover:bg-muted"}`}
                                        >{lbl}</button>
                                    );
                                })}
                            </div>
                        </Col>
                    );
                }
                return (
                    <Col key={fieldName}>
                        <TextField
                            fullWidth
                            size="small"
                            label={label}
                            variant="outlined"
                            placeholder={`${label}`}
                            value={filterValues[fieldName] || ""}
                            onChange={(e) => handleFilterChange(fieldName, e.target.value)}
                            sx={{
                              '& .MuiOutlinedInput-root': { height: '42px' },
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
                            size="small"
                            label={label}
                            variant="outlined"
                            placeholder="Comma-separated values"
                            value={filterValues[fieldName] || ""}
                            onChange={(e) => handleFilterChange(fieldName, e.target.value)}
                            helperText="Enter values separated by commas"
                            sx={{
                              '& .MuiOutlinedInput-root': { height: '42px' },
                              '& .MuiInputBase-input': { fontSize: '0.875rem' }
                            }}
                        />
                    </Col>
                );

            case "fk":
                return (
                    <Col key={fieldName}>
                        <Label className="mb-2">{label}</Label>
                        <DebouncedAsyncSelect endpoint={config.fk_endpoint || config.endpoint} labelField={config.label_field || "name"} value={filterValues[fieldName] || ""} onChange={(val) => handleFilterChange(fieldName, val)} placeholder={`Select ${label.toLowerCase()}`} isClearable isMulti debounceDelay={300} />
                    </Col>
                );

            case "button_group": {
                const bgChoices = (config.choices || []).map((c) => Array.isArray(c) ? { value: c[0], label: c[1] } : typeof c === "object" ? c : { value: c, label: c });
                return (
                    <Col key={fieldName} wide>
                        <Label className="mb-2 block">{label}</Label>
                        <div className="flex flex-wrap gap-2">
                            {bgChoices.map((choice, idx) => {
                                const active = filterValues[fieldName] === choice.value || (!filterValues[fieldName] && choice.value === "");
                                const colorCls = choice.value === "" ? "" : choice.value === "YES" ? "border-destructive text-destructive" : choice.value === "NO" ? "border-success text-success" : choice.value === "PARTIAL" ? "border-warning text-warning" : "";
                                return (
                                    <button key={idx} type="button" onClick={() => handleFilterChange(fieldName, choice.value, true)} className={`rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer ${active ? "bg-primary/15 border-primary text-primary" : `bg-card ${colorCls || "border-border text-muted-foreground"} hover:bg-muted`}`}>
                                        {choice.label}
                                    </button>
                                );
                            })}
                        </div>
                    </Col>
                );
            }

            case "choice": {
                const choiceOpts = (config.choices || []).map((c) => Array.isArray(c) ? { value: c[0], label: c[1] } : typeof c === "object" ? c : { value: c, label: c });
                let selectedChoices = [];
                if (filterValues[fieldName]) {
                    const vals = typeof filterValues[fieldName] === "string" ? filterValues[fieldName].split(",") : filterValues[fieldName];
                    selectedChoices = choiceOpts.filter((o) => vals.includes(o.value));
                }
                return (
                    <Col key={fieldName}>
                        <Label className="mb-2">{label}</Label>
                        <Select
                            options={choiceOpts}
                            value={selectedChoices}
                            onChange={(selected) => handleFilterChange(fieldName, selected ? selected.map((s) => s.value).join(",") : "", true)}
                            isClearable isMulti
                            placeholder={`Select ${label.toLowerCase()}`}
                            classNamePrefix="react-select"
                            styles={rsMultiSelectStyles}
                        />
                    </Col>
                );
            }

            case "exclude_fk":
                return (
                    <Col key={fieldName}>
                        <Label className="mb-2">{label}</Label>
                        <DebouncedAsyncSelect endpoint={config.fk_endpoint || config.endpoint} labelField={config.label_field || "name"} value={filterValues[fieldName] || ""} onChange={(val) => handleFilterChange(fieldName, val)} placeholder={`Exclude ${label.toLowerCase()}`} isClearable isMulti debounceDelay={300} />
                    </Col>
                );

            default:
                return (
                    <Col key={fieldName}>
                        <Label className="mb-2">{label}</Label>
                        <Input placeholder={`Filter ${label.toLowerCase()}`} value={filterValues[fieldName] || ""} onChange={(e) => handleFilterChange(fieldName, e.target.value)} />
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
