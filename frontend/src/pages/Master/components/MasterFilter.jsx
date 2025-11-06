import React, { useState, useCallback } from "react";
import { debounce } from "../../../utils/debounce";

const MasterFilter = ({ schema = {}, meta = {}, onFilterChange }) => {
  const [filters, setFilters] = useState({});

  // choose fields: prefer meta.filterFields, fall back to search/list display, or schema keys
  const fields =
    (meta.filterFields && meta.filterFields.length && meta.filterFields) ||
    (meta.searchFields && meta.searchFields.length && meta.searchFields.slice(0, 6)) ||
    (meta.listDisplay && meta.listDisplay.length && meta.listDisplay.slice(0, 6)) ||
    Object.keys(schema).slice(0, 4);

  // stable debounced updater
  const debouncedUpdate = useCallback(
    debounce((name, value) => {
      setFilters((prev) => {
        const next = { ...prev, [name]: value };
        onFilterChange(next);
        return next;
      });
    }, 350),
    [onFilterChange]
  );

  return (
    <div className="row g-2 mb-3">
      {fields.map((field) => (
        <div key={field} className="col-md-3">
          <input
            type="text"
            name={field}
            defaultValue={filters[field] || ""}
            placeholder={`Filter by ${schema[field]?.label || field}`}
            className="form-control"
            onChange={(e) => debouncedUpdate(e.target.name, e.target.value)}
          />
        </div>
      ))}
    </div>
  );
};

export default MasterFilter;
