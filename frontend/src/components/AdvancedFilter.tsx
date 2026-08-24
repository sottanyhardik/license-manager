import { useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, ChevronUp, SlidersHorizontal } from "lucide-react";
import Select from "react-select";
import DebouncedAsyncSelect from "./DebouncedAsyncSelect";
import DebouncedSearchInput from "./DebouncedSearchInput";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import DateRangeFilter from "./DateRangeFilter";
import { FilterField, FilterGrid, FilterPanel } from "./filters/FilterPanel";

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
    const [showAdvanced, setShowAdvanced] = useState(false);
    const isInitialMount = useRef(true);
    const isAutoApplyInitialMount = useRef(true);
    const prevInitialFilters = useRef(initialFilters);
    const skipNextAutoApply = useRef(false);

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
    const activeEntries = Object.entries(filterValues).filter(([field, value]) => value !== "" && value !== null && value !== undefined && value !== "all" && String(value) !== String(defaultFilters[field] ?? ""));
    const hasActiveSearch = Boolean(searchTerm.trim());

    // shared style token for react-select border
    const rsControl = (base) => ({ ...base, minHeight: "44px", borderColor: "var(--tb-border)" });

    const renderFilterField = (fieldName, config) => {
        const filterType = config.type || "exact";
        const label = config.label || humanize(fieldName);

        // Shared Tailwind col wrapper — replaces Bootstrap col-md-4 / col-md-6
        const Col = ({ wide = false, children }) => <FilterField wide={wide}>{children}</FilterField>;

        switch (filterType) {
            case "icontains":
                return (
                    <Col key={fieldName}>
                        <Label className="mb-1.5">{label}</Label>
                        <Input placeholder={`Search ${label.toLowerCase()}`} value={filterValues[fieldName] || ""} onChange={(e) => handleFilterChange(fieldName, e.target.value)} />
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
                        <Label className="mb-1.5">{label} Range</Label>
                        <div className="grid grid-cols-2 gap-2">
                            <div>
                                <Input type="number" step="0.01" placeholder="Min" value={filterValues[minField] || ""} onChange={(e) => handleFilterChange(minField, e.target.value)} />
                                <p className="mt-0.5 text-[11px] text-muted-foreground">Min</p>
                            </div>
                            <div>
                                <Input type="number" step="0.01" placeholder="Max" value={filterValues[maxField] || ""} onChange={(e) => handleFilterChange(maxField, e.target.value)} />
                                <p className="mt-0.5 text-[11px] text-muted-foreground">Max</p>
                            </div>
                        </div>
                    </Col>
                );
            }

            case "exact": {
                if (config.choices && config.choices.length > 0) {
                    const opts = config.choices.map((c) => Array.isArray(c) ? { value: c[0], label: c[1] } : typeof c === "object" ? c : { value: c, label: c });
                    const selected = opts.find((o) => o.value === filterValues[fieldName]) || null;
                    return (
                        <Col key={fieldName}>
                            <Label className="mb-1.5">{label}</Label>
                            <Select options={opts} value={selected} onChange={(s) => handleFilterChange(fieldName, s ? s.value : "", true)} isClearable placeholder={`Select ${label.toLowerCase()}`} styles={{ control: rsControl }} classNamePrefix="react-select" />
                        </Col>
                    );
                }
                if (fieldName.startsWith("is_") || fieldName.startsWith("has_") || fieldName.includes("__is_") || fieldName.includes("__has_")) {
                    const cur = filterValues[fieldName];
                    const isAll = cur === "all" || (!cur && cur !== "True" && cur !== "False");
                    return (
                        <Col key={fieldName}>
                            <Label className="mb-1.5 block">{label}</Label>
                            <div className="flex gap-1">
                                {[{ val: "all", lbl: "All", cls: "secondary" }, { val: "True", lbl: "Yes", cls: "success" }, { val: "False", lbl: "No", cls: "danger" }].map(({ val, lbl, cls }) => {
                                    const active = val === "all" ? isAll : cur === val || cur === (val === "True");
                                    return (
                                        <button
                                            key={val}
                                            type="button"
                                            onClick={() => handleFilterChange(fieldName, val, true)}
                                            className={`rounded-md border px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer ${active ? (cls === "success" ? "border-success bg-success/15 text-success" : cls === "danger" ? "border-destructive bg-destructive/15 text-destructive" : "border-primary bg-primary/15 text-primary") : "border-border bg-card text-muted-foreground hover:bg-muted"}`}
                                        >{lbl}</button>
                                    );
                                })}
                            </div>
                        </Col>
                    );
                }
                return (
                    <Col key={fieldName}>
                        <Label className="mb-1.5">{label}</Label>
                        <Input placeholder={`Exact ${label.toLowerCase()}`} value={filterValues[fieldName] || ""} onChange={(e) => handleFilterChange(fieldName, e.target.value)} />
                    </Col>
                );
            }

            case "in":
                return (
                    <Col key={fieldName}>
                        <Label className="mb-1.5">{label}</Label>
                        <Input placeholder="Comma-separated values" value={filterValues[fieldName] || ""} onChange={(e) => handleFilterChange(fieldName, e.target.value)} />
                        <p className="mt-0.5 text-[11px] text-muted-foreground">Enter values separated by commas</p>
                    </Col>
                );

            case "fk":
                return (
                    <Col key={fieldName}>
                        <Label className="mb-1.5">{label}</Label>
                        <DebouncedAsyncSelect endpoint={config.fk_endpoint || config.endpoint} labelField={config.label_field || "name"} value={filterValues[fieldName] || ""} onChange={(val) => handleFilterChange(fieldName, val)} placeholder={`Select ${label.toLowerCase()}`} isClearable isMulti debounceDelay={300} />
                    </Col>
                );

            case "button_group": {
                const bgChoices = (config.choices || []).map((c) => Array.isArray(c) ? { value: c[0], label: c[1] } : typeof c === "object" ? c : { value: c, label: c });
                return (
                    <Col key={fieldName} wide>
                        <Label className="mb-1.5 block">{label}</Label>
                        <div className="flex flex-wrap gap-1">
                            {bgChoices.map((choice, idx) => {
                                const active = filterValues[fieldName] === choice.value || (!filterValues[fieldName] && choice.value === "");
                                const colorCls = choice.value === "" ? "" : choice.value === "YES" ? "border-destructive text-destructive" : choice.value === "NO" ? "border-success text-success" : choice.value === "PARTIAL" ? "border-warning text-warning" : "";
                                return (
                                    <button key={idx} type="button" onClick={() => handleFilterChange(fieldName, choice.value, true)} className={`rounded-md border px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer ${active ? "bg-primary/15 border-primary text-primary" : `bg-card ${colorCls || "border-border text-muted-foreground"} hover:bg-muted`}`}>
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
                        <Label className="mb-1.5">{label}</Label>
                        <Select
                            options={choiceOpts}
                            value={selectedChoices}
                            onChange={(selected) => handleFilterChange(fieldName, selected ? selected.map((s) => s.value).join(",") : "", true)}
                            isClearable isMulti
                            placeholder={`Select ${label.toLowerCase()}`}
                            classNamePrefix="react-select"
                            styles={{ control: rsControl, valueContainer: (b) => ({ ...b, flexWrap: "wrap" }), multiValue: (b) => ({ ...b, maxWidth: "100%" }), multiValueLabel: (b) => ({ ...b, whiteSpace: "normal", wordBreak: "break-word" }), menu: (b) => ({ ...b, zIndex: 9999 }) }}
                        />
                    </Col>
                );
            }

            case "exclude_fk": {
                // Metadata often already says "Exclude Exporter".  Avoid the
                // awkward "Exclude exclude exporter" helper text.
                const excludedSubject = label.replace(/^exclude\s+/i, "");
                return (
                    <Col key={fieldName}>
                        <Label className="mb-1.5">{label}</Label>
                        <DebouncedAsyncSelect endpoint={config.fk_endpoint || config.endpoint} labelField={config.label_field || "name"} value={filterValues[fieldName] || ""} onChange={(val) => handleFilterChange(fieldName, val)} placeholder={`Exclude ${excludedSubject.toLowerCase()}`} isClearable isMulti debounceDelay={300} />
                    </Col>
                );
            }

            default:
                return (
                    <Col key={fieldName}>
                        <Label className="mb-1.5">{label}</Label>
                        <Input placeholder={`Filter ${label.toLowerCase()}`} value={filterValues[fieldName] || ""} onChange={(e) => handleFilterChange(fieldName, e.target.value)} />
                    </Col>
                );
        }
    };

    if (Object.keys(filterConfig).length === 0 && searchFields.length === 0) return null;

    return (
        <div className="mb-4 space-y-3">
            {/* Search bar */}
            {searchFields.length > 0 && (
                <div className="max-w-2xl">
                    <DebouncedSearchInput
                        value={searchTerm}
                        onChange={setSearchTerm}
                        delay={400}
                        placeholder={`Search by ${searchFields.join(", ")}`}
                    />
                </div>
            )}

            {Object.keys(filterConfig).length > 0 && (
                <FilterPanel activeCount={activeEntries.length} isUpdating={isUpdating} onClear={handleResetFilters} clearDisabled={activeEntries.length === 0 && !hasActiveSearch} collapsible defaultOpen={activeEntries.length > 0}>
                    <FilterGrid>{primaryEntries.map(([fieldName, config]) => renderFilterField(fieldName, config))}</FilterGrid>
                    {secondaryEntries.length > 0 && <>
                        <div className="mt-4 border-t border-dashed border-border pt-3">
                            <Button type="button" variant="ghost" size="sm" onClick={() => setShowAdvanced((visible) => !visible)} aria-expanded={showAdvanced}>
                                <SlidersHorizontal className="size-3.5" />
                                {showAdvanced ? "Hide advanced filters" : `More filters (${secondaryEntries.length})`}
                                {showAdvanced ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
                            </Button>
                        </div>
                        {showAdvanced && <div className="mt-3"><FilterGrid>{secondaryEntries.map(([fieldName, config]) => renderFilterField(fieldName, config))}</FilterGrid></div>}
                    </>}
                </FilterPanel>
            )}
        </div>
    );
}
