import { useCallback, useEffect, useId, useRef, useState, type ReactNode } from "react";
import { ChevronDown, Filter, Loader2, X } from "lucide-react";
import Select from "react-select";
import DebouncedAsyncSelect from "./DebouncedAsyncSelect";
import DebouncedSearchInput from "./DebouncedSearchInput";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import DateRangeFilter from "./DateRangeFilter";
import { FilterField, FilterGrid, FilterPanel } from "./filters/FilterPanel";

function FilterCol({ wide = false, grid = false, children }: { wide?: boolean; grid?: boolean; children: ReactNode }) {
    return grid
        ? <div className={`min-w-0 ${wide ? "md:col-span-2" : ""}`}>{children}</div>
        : <FilterField wide={wide}>{children}</FilterField>;
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
    isUpdating = false,
    collapsible = false,
    layout = "default",
    toolbarStart,
    toolbarEnd,
}: {
    filterConfig?: Record<string, any>;
    searchFields?: string[];
    onFilterChange?: (filters: Record<string, any>) => void;
    initialFilters?: Record<string, any>;
    defaultFilters?: Record<string, any>;
    resetToDefaults?: boolean;
    isUpdating?: boolean;
    /** Compact single-row toolbar (search + Filters toggle) with a collapsible field grid. */
    collapsible?: boolean;
    /** "grid": responsive 1/2/3/4-column field grid (used with `collapsible`). */
    layout?: "default" | "grid";
    /** Collapsible mode only: content rendered at the start / end of the toolbar row. */
    toolbarStart?: ReactNode;
    toolbarEnd?: ReactNode;
}) {
    const panelId = useId();
    const [open, setOpen] = useState(false);
    const [searchTerm, setSearchTerm] = useState(String(initialFilters.search || ""));
    const { search: _search, ...initialFiltersWithoutSearch } = initialFilters;
    const [filterValues, setFilterValues] = useState({ ...defaultFilters, ...initialFiltersWithoutSearch });
    const isInitialMount = useRef(true);
    const isAutoApplyInitialMount = useRef(true);
    const prevInitialFilters = useRef(initialFilters);
    // Canonical key of the last filter state applied (emitted to the parent or
    // received from it). Replaces a "skip next auto-apply" flag, which could be
    // left armed and swallow a later text edit.
    const appliedKey = useRef<string | null>(null);
    const keyOf = (params: Record<string, any>) =>
        JSON.stringify(Object.keys(params).sort().map((k) => [k, params[k]]));

    const toApiParams = useCallback((nextValues?: Record<string, any>, nextSearch?: string) => {
        const params: Record<string, any> = {};
        const valuesObj = nextValues ?? filterValues;
        const searchStr = nextSearch ?? searchTerm;
        if (searchStr) params.search = searchStr;
        Object.entries(valuesObj).forEach(([key, value]) => {
            if (value === null || value === undefined || value === "") return;
            if (key.endsWith("_from")) params[`${key.replace("_from", "")}__gte`] = value;
            else if (key.endsWith("_to")) params[`${key.replace("_to", "")}__lte`] = value;
            else params[key] = value;
        });
        return params;
    }, [filterValues, searchTerm]);
    // Latest-value refs so the prop-sync effect can read current state without
    // re-running (and re-syncing) on every local edit.
    const searchTermRef = useRef(searchTerm);
    const toApiParamsRef = useRef(toApiParams);
    searchTermRef.current = searchTerm;
    toApiParamsRef.current = toApiParams;

    useEffect(() => {
        if (isInitialMount.current) {
            isInitialMount.current = false;
            prevInitialFilters.current = initialFilters;
            return;
        }
        if (JSON.stringify(prevInitialFilters.current) !== JSON.stringify(initialFilters)) {
            prevInitialFilters.current = initialFilters;
            const { search: _s, ...filtersWithoutSearch } = initialFilters;
            const nextValues = { ...defaultFilters, ...filtersWithoutSearch };
            const nextSearch = initialFilters.search !== undefined ? (initialFilters.search || "") : searchTermRef.current;
            const key = keyOf(toApiParamsRef.current(nextValues, nextSearch));
            // Echo of what this component just applied: local state is already
            // right (and may hold a newer, still-debounced edit) - leave it.
            if (key === appliedKey.current) return;
            appliedKey.current = key;
            if (initialFilters.search !== undefined) setSearchTerm(initialFilters.search || "");
            setFilterValues(() => nextValues);
        }
    }, [initialFilters, defaultFilters]);

    useEffect(() => {
        if (isAutoApplyInitialMount.current) {
            isAutoApplyInitialMount.current = false;
            appliedKey.current = keyOf(toApiParams());
            return;
        }
        const params = toApiParams();
        const key = keyOf(params);
        if (key === appliedKey.current) return;
        const timeoutId = setTimeout(() => { appliedKey.current = key; onFilterChange(params); }, 400);
        return () => clearTimeout(timeoutId);
    }, [searchTerm, filterValues, onFilterChange, toApiParams]);

    const handleFilterChange = (field, value, immediate = false) => {
        setFilterValues((prev) => {
            const next = { ...prev, [field]: value };
            if (immediate) {
                const params = toApiParams(next);
                appliedKey.current = keyOf(params);
                setTimeout(() => onFilterChange(params), 0);
            }
            return next;
        });
    };

    const handleResetFilters = () => {
        appliedKey.current = null; // always emit a reset, even if already empty
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

    // shared style token for react-select border
    const rsControl = (base) => ({ ...base, minHeight: "44px", borderColor: "var(--tb-border)" });

    const renderFilterField = (fieldName, config) => {
        const filterType = config.type || "exact";
        const label = config.label || humanize(fieldName);


        switch (filterType) {
            case "icontains":
                return (
                    <FilterCol grid={layout === "grid"} key={fieldName}>
                        <Label className="mb-2">{label}</Label>
                        <Input placeholder={`Search ${label.toLowerCase()}`} value={filterValues[fieldName] || ""} onChange={(e) => handleFilterChange(fieldName, e.target.value)} />
                    </FilterCol>
                );

            case "date_range": {
                const fromValue = filterValues[`${fieldName}_from`] || "";
                const toValue = filterValues[`${fieldName}_to`] || "";
                return (
                    <FilterCol grid={layout === "grid"} key={fieldName} wide>
                        <DateRangeFilter
                            label={`${label} Range`}
                            fromValue={fromValue}
                            toValue={toValue}
                            onFromChange={(v) => handleFilterChange(`${fieldName}_from`, v, true)}
                            onToChange={(v) => handleFilterChange(`${fieldName}_to`, v, true)}
                        />
                    </FilterCol>
                );
            }

            case "range": {
                const minField = config.min_field || `${fieldName}_min`;
                const maxField = config.max_field || `${fieldName}_max`;
                return (
                    <FilterCol grid={layout === "grid"} key={fieldName} wide>
                        <Label className="mb-2">{label} Range</Label>
                        <div className="grid grid-cols-2 gap-3">
                            <div>
                                <Input type="number" step="0.01" placeholder="Min" value={filterValues[minField] || ""} onChange={(e) => handleFilterChange(minField, e.target.value)} />
                                <p className="mt-1 text-xs text-muted-foreground">Min</p>
                            </div>
                            <div>
                                <Input type="number" step="0.01" placeholder="Max" value={filterValues[maxField] || ""} onChange={(e) => handleFilterChange(maxField, e.target.value)} />
                                <p className="mt-1 text-xs text-muted-foreground">Max</p>
                            </div>
                        </div>
                    </FilterCol>
                );
            }

            case "exact": {
                if (config.choices && config.choices.length > 0) {
                    const opts = config.choices.map((c) => Array.isArray(c) ? { value: c[0], label: c[1] } : typeof c === "object" ? c : { value: c, label: c });
                    const selected = opts.find((o) => o.value === filterValues[fieldName]) || null;
                    return (
                        <FilterCol grid={layout === "grid"} key={fieldName}>
                            <Label className="mb-2">{label}</Label>
                            <Select options={opts} value={selected} onChange={(s) => handleFilterChange(fieldName, s ? s.value : "", true)} isClearable placeholder={`Select ${label.toLowerCase()}`} styles={{ control: rsControl }} classNamePrefix="react-select" />
                        </FilterCol>
                    );
                }
                if (fieldName.startsWith("is_") || fieldName.startsWith("has_") || fieldName.includes("__is_") || fieldName.includes("__has_")) {
                    const cur = filterValues[fieldName];
                    const isAll = cur === "all" || (!cur && cur !== "True" && cur !== "False");
                    return (
                        <FilterCol grid={layout === "grid"} key={fieldName}>
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
                        </FilterCol>
                    );
                }
                return (
                    <FilterCol grid={layout === "grid"} key={fieldName}>
                        <Label className="mb-2">{label}</Label>
                        <Input placeholder={`Exact ${label.toLowerCase()}`} value={filterValues[fieldName] || ""} onChange={(e) => handleFilterChange(fieldName, e.target.value)} />
                    </FilterCol>
                );
            }

            case "in":
                return (
                    <FilterCol grid={layout === "grid"} key={fieldName}>
                        <Label className="mb-2">{label}</Label>
                        <Input placeholder="Comma-separated values" value={filterValues[fieldName] || ""} onChange={(e) => handleFilterChange(fieldName, e.target.value)} />
                        <p className="mt-1 text-xs text-muted-foreground">Enter values separated by commas</p>
                    </FilterCol>
                );

            case "fk":
                return (
                    <FilterCol grid={layout === "grid"} key={fieldName}>
                        <Label className="mb-2">{label}</Label>
                        <DebouncedAsyncSelect endpoint={config.fk_endpoint || config.endpoint} labelField={config.label_field || "name"} value={filterValues[fieldName] || ""} onChange={(val) => handleFilterChange(fieldName, val)} placeholder={`Select ${label.toLowerCase()}`} isClearable isMulti debounceDelay={300} />
                    </FilterCol>
                );

            case "button_group": {
                const bgChoices = (config.choices || []).map((c) => Array.isArray(c) ? { value: c[0], label: c[1] } : typeof c === "object" ? c : { value: c, label: c });
                return (
                    <FilterCol grid={layout === "grid"} key={fieldName} wide>
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
                    </FilterCol>
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
                    <FilterCol grid={layout === "grid"} key={fieldName}>
                        <Label className="mb-2">{label}</Label>
                        <Select
                            options={choiceOpts}
                            value={selectedChoices}
                            onChange={(selected) => handleFilterChange(fieldName, selected ? selected.map((s) => s.value).join(",") : "", true)}
                            isClearable isMulti
                            placeholder={`Select ${label.toLowerCase()}`}
                            classNamePrefix="react-select"
                            styles={{ control: rsControl, valueContainer: (b) => ({ ...b, flexWrap: "wrap" }), multiValue: (b) => ({ ...b, maxWidth: "100%" }), multiValueLabel: (b) => ({ ...b, whiteSpace: "normal", wordBreak: "break-word" }), menu: (b) => ({ ...b, zIndex: 9999 }) }}
                        />
                    </FilterCol>
                );
            }

            case "exclude_fk":
                return (
                    <FilterCol grid={layout === "grid"} key={fieldName}>
                        <Label className="mb-2">{label}</Label>
                        <DebouncedAsyncSelect endpoint={config.fk_endpoint || config.endpoint} labelField={config.label_field || "name"} value={filterValues[fieldName] || ""} onChange={(val) => handleFilterChange(fieldName, val)} placeholder={`Exclude ${label.toLowerCase()}`} isClearable isMulti debounceDelay={300} />
                    </FilterCol>
                );

            default:
                return (
                    <FilterCol grid={layout === "grid"} key={fieldName}>
                        <Label className="mb-2">{label}</Label>
                        <Input placeholder={`Filter ${label.toLowerCase()}`} value={filterValues[fieldName] || ""} onChange={(e) => handleFilterChange(fieldName, e.target.value)} />
                    </FilterCol>
                );
        }
    };

    if (Object.keys(filterConfig).length === 0 && searchFields.length === 0 && !collapsible) return null;

    if (collapsible) {
        const hasFilters = Object.keys(filterConfig).length > 0;
        const fields = [...primaryEntries, ...secondaryEntries].map(([fieldName, config]) => renderFilterField(fieldName, config));
        return (
            <div className="mb-3 rounded-lg border border-border/70 bg-card shadow-sm">
                <div className="flex flex-wrap items-center gap-x-3 gap-y-2 px-3 py-2">
                    {toolbarStart && <div className="min-w-0 flex-1">{toolbarStart}</div>}
                    {searchFields.length > 0 && (
                        <div className="w-full sm:w-64 lg:w-72">
                            <DebouncedSearchInput
                                value={searchTerm}
                                onChange={setSearchTerm}
                                delay={400}
                                placeholder={`Search by ${searchFields.join(", ")}`}
                                className="!h-9"
                            />
                        </div>
                    )}
                    {hasFilters && (
                        <Button type="button" variant="outline" size="sm" aria-expanded={open} aria-controls={panelId} onClick={() => setOpen((v) => !v)}>
                            <Filter className="size-3.5" aria-hidden="true" />
                            Filters
                            {activeEntries.length > 0 && <span className="rounded-full bg-primary/15 px-1.5 text-xs text-primary">{activeEntries.length}</span>}
                            <ChevronDown className={`size-3.5 transition-transform motion-reduce:transition-none ${open ? "rotate-180" : ""}`} aria-hidden="true" />
                        </Button>
                    )}
                    {isUpdating && <span role="status" className="inline-flex items-center gap-1 text-xs text-muted-foreground"><Loader2 className="size-3 animate-spin motion-reduce:animate-none" />Updating</span>}
                    {toolbarEnd && <div className="flex flex-wrap items-center gap-2">{toolbarEnd}</div>}
                </div>
                {hasFilters && (
                    <section id={panelId} aria-label="Filters" hidden={!open} className="border-t border-border/60 p-3">
                        <div className={layout === "grid" ? "grid grid-cols-1 gap-x-4 gap-y-3 md:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4" : "grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4"}>{fields}</div>
                        <div className="mt-3 flex justify-end">
                            <Button type="button" variant="ghost" size="sm" onClick={handleResetFilters} disabled={activeEntries.length === 0 && !searchTerm}>
                                <X className="size-3.5" aria-hidden="true" />Reset
                            </Button>
                        </div>
                    </section>
                )}
            </div>
        );
    }

    return (
        <div className="mb-4">
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
            {Object.keys(filterConfig).length > 0 && <FilterPanel activeCount={activeEntries.length} isUpdating={isUpdating} onClear={handleResetFilters} clearDisabled={activeEntries.length === 0 && !searchTerm}><FilterGrid>{primaryEntries.map(([fieldName, config]) => renderFilterField(fieldName, config))}{secondaryEntries.map(([fieldName, config]) => renderFilterField(fieldName, config))}</FilterGrid></FilterPanel>}
        </div>
    );
}
