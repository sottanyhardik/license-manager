import {useState, useEffect, useRef} from "react";
import AsyncSelectField from "./AsyncSelectField";
import Select from "react-select";

/**
 * Advanced DataFilter Component with support for:
 * - icontains (text search)
 * - date_range (from/to dates)
 * - range (min/max numeric)
 * - exact (exact match)
 * - in (multiple values)
 * - fk (foreign key select)
 * - choice (choice field select)
 *
 * Props:
 * - filterConfig: object mapping field names to filter configs from backend
 * - searchFields: array of searchable fields
 * - onFilterChange: callback function(filterParams)
 */
export default function AdvancedFilter({filterConfig = {}, searchFields = [], onFilterChange, initialFilters = {}, defaultFilters = {}}) {
    // Initialize search term from initialFilters if present
    const [searchTerm, setSearchTerm] = useState(initialFilters.search || "");
    // Merge default filters with initial filters - defaultFilters are fallback values
    // Remove 'search' from filterValues as it's managed separately
    const {search: _search, ...initialFiltersWithoutSearch} = initialFilters;
    const [filterValues, setFilterValues] = useState({...defaultFilters, ...initialFiltersWithoutSearch});
    const isInitialMount = useRef(true);
    const prevInitialFilters = useRef(initialFilters);
    const skipNextAutoApply = useRef(false);

    // Update filterValues and searchTerm when initialFilters change
    useEffect(() => {
        // On initial mount, don't update (already set in useState)
        if (isInitialMount.current) {
            isInitialMount.current = false;
            prevInitialFilters.current = initialFilters;
            return;
        }

        // Only update if initialFilters actually changed (not just a re-render)
        if (JSON.stringify(prevInitialFilters.current) !== JSON.stringify(initialFilters)) {
            prevInitialFilters.current = initialFilters;
            skipNextAutoApply.current = true; // Skip auto-apply since parent is updating

            // Update search term if present
            if (initialFilters.search !== undefined) {
                setSearchTerm(initialFilters.search || "");
            }

            // Update filter values (excluding search)
            const {search: _s, ...filtersWithoutSearch} = initialFilters;
            // Merge with existing filterValues to preserve any local changes
            setFilterValues(prev => {
                const merged = {...defaultFilters, ...filtersWithoutSearch};
                return merged;
            });
        }
    }, [initialFilters, defaultFilters]);

    // Auto-apply filters with debounce
    useEffect(() => {
        // Skip auto-apply if the change came from parent (initialFilters update)
        if (skipNextAutoApply.current) {
            skipNextAutoApply.current = false;
            return;
        }

        const timeoutId = setTimeout(() => {
            const params = {};

            // Add search
            if (searchTerm) {
                params.search = searchTerm;
            }

            // Process filter values
            Object.entries(filterValues).forEach(([key, value]) => {
                // Include all non-empty values, including "all" to explicitly disable defaults
                if (value !== null && value !== undefined && value !== "") {
                    // Convert UI format to Django format for date ranges
                    // _from -> __gte (greater than or equal)
                    // _to -> __lte (less than or equal)
                    if (key.endsWith('_from')) {
                        const baseField = key.replace('_from', '');
                        params[`${baseField}__gte`] = value;
                    } else if (key.endsWith('_to')) {
                        const baseField = key.replace('_to', '');
                        params[`${baseField}__lte`] = value;
                    } else {
                        params[key] = value;
                    }
                }
            });

            onFilterChange(params);
        }, 800); // Increased to 800ms to allow users to finish typing dates

        return () => clearTimeout(timeoutId);
    }, [searchTerm, filterValues, onFilterChange]);

    const handleSearchChange = (e) => {
        setSearchTerm(e.target.value);
    };

    const handleFilterChange = (field, value) => {
        setFilterValues(prev => ({
            ...prev,
            [field]: value
        }));
    };

    const handleResetFilters = () => {
        setSearchTerm("");
        setFilterValues({});
    };

    const renderFilterField = (fieldName, config) => {
        const filterType = config.type || "exact";
        const label = fieldName.replace(/_/g, " ").replace(/\b\w/g, c => c.toUpperCase());

        switch (filterType) {
            case "icontains":
                return (
                    <div key={fieldName} className="col-md-4">
                        <label className="form-label">{label}</label>
                        <input
                            type="text"
                            className="form-control"
                            placeholder={`Search ${label.toLowerCase()}`}
                            value={filterValues[fieldName] || ""}
                            onChange={(e) => handleFilterChange(fieldName, e.target.value)}
                        />
                    </div>
                );

            case "date_range":
                const fromValue = filterValues[`${fieldName}_from`] || "";
                const toValue = filterValues[`${fieldName}_to`] || "";

                return (
                    <div key={fieldName} className="col-md-6">
                        <label className="form-label">{label} Range</label>
                        <div className="row g-2">
                            <div className="col">
                                <input
                                    type="date"
                                    className="form-control"
                                    placeholder="From"
                                    value={fromValue}
                                    onChange={(e) => {
                                        handleFilterChange(`${fieldName}_from`, e.target.value);
                                    }}
                                />
                                <small className="text-muted">From</small>
                            </div>
                            <div className="col">
                                <input
                                    type="date"
                                    className="form-control"
                                    placeholder="To"
                                    value={toValue}
                                    onChange={(e) => {
                                        handleFilterChange(`${fieldName}_to`, e.target.value);
                                    }}
                                />
                                <small className="text-muted">To</small>
                            </div>
                        </div>
                    </div>
                );

            case "range":
                const minField = config.min_field || `${fieldName}_min`;
                const maxField = config.max_field || `${fieldName}_max`;

                return (
                    <div key={fieldName} className="col-md-6">
                        <label className="form-label">{label} Range</label>
                        <div className="row g-2">
                            <div className="col">
                                <input
                                    type="number"
                                    step="0.01"
                                    className="form-control"
                                    placeholder="Min"
                                    value={filterValues[minField] || ""}
                                    onChange={(e) => handleFilterChange(minField, e.target.value)}
                                />
                                <small className="text-muted">Min</small>
                            </div>
                            <div className="col">
                                <input
                                    type="number"
                                    step="0.01"
                                    className="form-control"
                                    placeholder="Max"
                                    value={filterValues[maxField] || ""}
                                    onChange={(e) => handleFilterChange(maxField, e.target.value)}
                                />
                                <small className="text-muted">Max</small>
                            </div>
                        </div>
                    </div>
                );

            case "exact":
                // Check if this is a boolean field (starts with is_ or has_)
                if (fieldName.startsWith("is_") || fieldName.startsWith("has_")) {
                    return (
                        <div key={fieldName} className="col-md-4">
                            <label className="form-label d-block">{label}</label>
                            <div className="btn-group" role="group">
                                <input
                                    type="radio"
                                    className="btn-check"
                                    name={`${fieldName}-options`}
                                    id={`${fieldName}-all`}
                                    checked={filterValues[fieldName] === "all" || (!filterValues[fieldName] && filterValues[fieldName] !== "True" && filterValues[fieldName] !== "False")}
                                    onChange={() => handleFilterChange(fieldName, "all")}
                                />
                                <label className="btn btn-outline-secondary" htmlFor={`${fieldName}-all`}>
                                    All
                                </label>

                                <input
                                    type="radio"
                                    className="btn-check"
                                    name={`${fieldName}-options`}
                                    id={`${fieldName}-yes`}
                                    checked={filterValues[fieldName] === "True" || filterValues[fieldName] === true}
                                    onChange={() => handleFilterChange(fieldName, "True")}
                                />
                                <label className="btn btn-outline-success" htmlFor={`${fieldName}-yes`}>
                                    Yes
                                </label>

                                <input
                                    type="radio"
                                    className="btn-check"
                                    name={`${fieldName}-options`}
                                    id={`${fieldName}-no`}
                                    checked={filterValues[fieldName] === "False" || filterValues[fieldName] === false}
                                    onChange={() => handleFilterChange(fieldName, "False")}
                                />
                                <label className="btn btn-outline-danger" htmlFor={`${fieldName}-no`}>
                                    No
                                </label>
                            </div>
                        </div>
                    );
                }

                return (
                    <div key={fieldName} className="col-md-4">
                        <label className="form-label">{label}</label>
                        <input
                            type="text"
                            className="form-control"
                            placeholder={`Exact ${label.toLowerCase()}`}
                            value={filterValues[fieldName] || ""}
                            onChange={(e) => handleFilterChange(fieldName, e.target.value)}
                        />
                    </div>
                );

            case "in":
                return (
                    <div key={fieldName} className="col-md-4">
                        <label className="form-label">{label}</label>
                        <input
                            type="text"
                            className="form-control"
                            placeholder="Comma-separated values"
                            value={filterValues[fieldName] || ""}
                            onChange={(e) => handleFilterChange(fieldName, e.target.value)}
                        />
                        <small className="text-muted">Enter values separated by commas</small>
                    </div>
                );

            case "fk":
                // Foreign Key filter with async multi-select
                return (
                    <div key={fieldName} className="col-md-4">
                        <label className="form-label">{label}</label>
                        <AsyncSelectField
                            endpoint={config.fk_endpoint || config.endpoint}
                            labelField={config.label_field || "name"}
                            value={filterValues[fieldName] || ""}
                            onChange={(val) => handleFilterChange(fieldName, val)}
                            placeholder={`Select ${label.toLowerCase()}`}
                            isClearable
                            isMulti
                        />
                    </div>
                );

            case "choice":
                // Choice field filter with static multi-select
                const choiceOptions = config.choices?.map(choice => {
                    if (Array.isArray(choice)) {
                        return {value: choice[0], label: choice[1]};
                    }
                    if (typeof choice === "object") {
                        return {value: choice.value, label: choice.label};
                    }
                    return {value: choice, label: choice};
                }) || [];

                // Handle multi-select values (comma-separated string or array)
                let selectedChoices = [];
                if (filterValues[fieldName]) {
                    const values = typeof filterValues[fieldName] === 'string'
                        ? filterValues[fieldName].split(',')
                        : filterValues[fieldName];
                    selectedChoices = choiceOptions.filter(opt => values.includes(opt.value));
                }

                return (
                    <div key={fieldName} className="col-md-4">
                        <label className="form-label">{label}</label>
                        <Select
                            options={choiceOptions}
                            value={selectedChoices}
                            onChange={(selected) => {
                                // Convert array of selected options to comma-separated string
                                const values = selected ? selected.map(s => s.value).join(',') : '';
                                handleFilterChange(fieldName, values);
                            }}
                            isClearable
                            isMulti
                            placeholder={`Select ${label.toLowerCase()}`}
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
                    </div>
                );

            case "exclude_fk":
                // Exclude Foreign Key filter with async multi-select
                return (
                    <div key={fieldName} className="col-md-4">
                        <label className="form-label">{label}</label>
                        <AsyncSelectField
                            endpoint={config.fk_endpoint || config.endpoint}
                            labelField={config.label_field || "name"}
                            value={filterValues[fieldName] || ""}
                            onChange={(val) => handleFilterChange(fieldName, val)}
                            placeholder={`Exclude ${label.toLowerCase()}`}
                            isClearable
                            isMulti
                        />
                    </div>
                );

            default:
                return (
                    <div key={fieldName} className="col-md-4">
                        <label className="form-label">{label}</label>
                        <input
                            type="text"
                            className="form-control"
                            placeholder={`Filter ${label.toLowerCase()}`}
                            value={filterValues[fieldName] || ""}
                            onChange={(e) => handleFilterChange(fieldName, e.target.value)}
                        />
                    </div>
                );
        }
    };

    const hasFilters = Object.keys(filterConfig).length > 0 || searchFields.length > 0;

    if (!hasFilters) {
        return null;
    }

    return (
        <div className="mb-4">

            {/* Search Bar on Top */}
            {searchFields.length > 0 && (
                <div className="mb-3">
                    <div className="input-group input-group-lg">
                        <span className="input-group-text bg-white">
                            <i className="bi bi-search"></i>
                        </span>
                        <input
                            type="text"
                            className="form-control form-control-lg"
                            placeholder={`Search by ${searchFields.join(", ")}`}
                            value={searchTerm}
                            onChange={handleSearchChange}
                        />
                        {searchTerm && (
                            <button
                                className="btn btn-outline-secondary"
                                type="button"
                                onClick={() => setSearchTerm("")}
                            >
                                <i className="bi bi-x-lg"></i>
                            </button>
                        )}
                    </div>
                </div>
            )}

            {/* Filter Card */}
            {Object.keys(filterConfig).length > 0 && (
                <div className="card">
                    <div className="card-body">
                        <h6 className="card-title mb-3">
                            <i className="bi bi-funnel me-2"></i>
                            Filters
                        </h6>

                        <div className="row g-3">
                            {/* Dynamic Filter Fields */}
                            {Object.entries(filterConfig).map(([fieldName, config]) =>
                                renderFilterField(fieldName, config)
                            )}
                        </div>

                        <div className="mt-3 d-flex justify-content-between align-items-center">
                            <button
                                className="btn btn-secondary"
                                onClick={handleResetFilters}
                            >
                                <i className="bi bi-x-circle me-1"></i>
                                Clear Filters
                            </button>
                            <small className="text-muted">
                                <i className="bi bi-lightning-charge me-1"></i>
                                Filters apply automatically as you type
                            </small>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
}
