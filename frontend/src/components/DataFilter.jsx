import {useState} from "react";

/**
 * Reusable DataFilter Component
 *
 * Props:
 * - filters: array of filter field definitions from backend
 * - searchFields: array of searchable fields
 * - onFilterChange: callback function(filterParams)
 */
export default function DataFilter({filters = [], searchFields = [], onFilterChange}) {
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
        const params = {...filterValues};
        if (searchTerm) {
            params.search = searchTerm;
        }
        onFilterChange(params);
    };

    const handleResetFilters = () => {
        setSearchTerm("");
        setFilterValues({});
        onFilterChange({});
    };

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
                        <div className="col-md-4">
                            <label className="form-label">Search</label>
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
                    {filters.map((field) => (
                        <div key={field} className="col-md-4">
                            <label className="form-label text-capitalize">
                                {field.replace(/_/g, " ")}
                            </label>
                            <input
                                type="text"
                                className="form-control"
                                placeholder={`Filter by ${field.replace(/_/g, " ")}`}
                                value={filterValues[field] || ""}
                                onChange={(e) => handleFilterChange(field, e.target.value)}
                            />
                        </div>
                    ))}
                </div>

                <div className="mt-3">
                    <button
                        className="btn btn-primary me-2"
                        onClick={handleApplyFilters}
                    >
                        <i className="bi bi-search me-1"></i>
                        Apply
                    </button>
                    <button
                        className="btn btn-secondary"
                        onClick={handleResetFilters}
                    >
                        <i className="bi bi-x-circle me-1"></i>
                        Reset
                    </button>
                </div>
            </div>
        </div>
    );
}
