import {useState, useEffect, useCallback} from "react";

/**
 * Advanced DataFilter Component with support for:
 * - icontains (text search)
 * - date_range (from/to dates)
 * - range (min/max numeric)
 * - exact (exact match)
 * - in (multiple values)
 *
 * Props:
 * - filterConfig: object mapping field names to filter configs from backend
 * - searchFields: array of searchable fields
 * - onFilterChange: callback function(filterParams)
 */
export default function AdvancedFilter({filterConfig = {}, searchFields = [], onFilterChange}) {
    const [searchTerm, setSearchTerm] = useState("");
    const [filterValues, setFilterValues] = useState({});

    const handleSearchChange = (e) => {
        setSearchTerm(e.target.value);
    };

    const handleFilterChange = (field, value) => {
        setFilterValues(prev => ({
            ...prev,
            [field]: value
        }));
    };

    const handleApplyFilters = () => {
        const params = {};

        // Add search
        if (searchTerm) {
            params.search = searchTerm;
        }

        // Process filter values
        Object.entries(filterValues).forEach(([key, value]) => {
            if (value !== null && value !== undefined && value !== "") {
                params[key] = value;
            }
        });

        onFilterChange(params);
    };

    const handleResetFilters = () => {
        setSearchTerm("");
        setFilterValues({});
        onFilterChange({});
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
                return (
                    <div key={fieldName} className="col-md-6">
                        <label className="form-label">{label} Range</label>
                        <div className="row g-2">
                            <div className="col">
                                <input
                                    type="date"
                                    className="form-control"
                                    placeholder="From"
                                    value={filterValues[`${fieldName}_from`] || ""}
                                    onChange={(e) => handleFilterChange(`${fieldName}_from`, e.target.value)}
                                />
                                <small className="text-muted">From</small>
                            </div>
                            <div className="col">
                                <input
                                    type="date"
                                    className="form-control"
                                    placeholder="To"
                                    value={filterValues[`${fieldName}_to`] || ""}
                                    onChange={(e) => handleFilterChange(`${fieldName}_to`, e.target.value)}
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
        <div className="card mb-3">
            <div className="card-body">
                <h6 className="card-title mb-3">
                    <i className="bi bi-funnel me-2"></i>
                    Filters
                </h6>

                <div className="row g-3">
                    {/* Search Field */}
                    {searchFields.length > 0 && (
                        <div className="col-md-6">
                            <label className="form-label">
                                <i className="bi bi-search me-1"></i>
                                Search
                            </label>
                            <input
                                type="text"
                                className="form-control"
                                placeholder={`Search by ${searchFields.join(", ")}`}
                                value={searchTerm}
                                onChange={handleSearchChange}
                            />
                        </div>
                    )}

                    {/* Dynamic Filter Fields */}
                    {Object.entries(filterConfig).map(([fieldName, config]) =>
                        renderFilterField(fieldName, config)
                    )}
                </div>

                <div className="mt-3 d-flex gap-2">
                    <button
                        className="btn btn-primary"
                        onClick={handleApplyFilters}
                    >
                        <i className="bi bi-funnel-fill me-1"></i>
                        Apply Filters
                    </button>
                    <button
                        className="btn btn-secondary"
                        onClick={handleResetFilters}
                    >
                        <i className="bi bi-x-circle me-1"></i>
                        Clear Filters
                    </button>
                </div>
            </div>
        </div>
    );
}
