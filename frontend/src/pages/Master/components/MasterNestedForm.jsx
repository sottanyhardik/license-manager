import React, { useEffect, useState } from "react";
import api from "../../../api/axios";
import { debounce } from "../../../utils/debounce.js";

const MasterNestedForm = ({ nestedData, setNestedData }) => {
  const [foreignOptions, setForeignOptions] = useState({});
  const [activeDropdown, setActiveDropdown] = useState(null);
  const [loadingField, setLoadingField] = useState(null);

  const fkEndpoints = {
    hsn_code: "/masters/hsn-code/",
    head_norm: "/masters/head-norm/",
    norm_class: "/masters/sion-norms/",
  };

  useEffect(() => {
    Object.keys(fkEndpoints).forEach((f) => loadOptions(f, ""));
  }, []);

  const loadOptions = async (field, query = "") => {
    try {
      setLoadingField(field);
      const res = await api.get(`${fkEndpoints[field]}?search=${encodeURIComponent(query)}`);
      setForeignOptions((prev) => ({ ...prev, [field]: res.data.results || res.data }));
    } catch (err) {
      console.warn("FK fetch failed for", field, err);
    } finally {
      setLoadingField(null);
    }
  };

  const debouncedSearch = debounce((field, value) => loadOptions(field, value), 400);

  const handleNestedChange = (parentKey, index, field, value) => {
    setNestedData((prev) => {
      const updated = { ...prev };
      updated[parentKey][index][field] = value;
      return updated;
    });
  };

  const addRow = (key) =>
    setNestedData((p) => ({ ...p, [key]: [...(p[key] || []), {}] }));

  const removeRow = (key, idx) =>
    setNestedData((p) => {
      const u = { ...p };
      u[key].splice(idx, 1);
      return u;
    });

  const renderField = (key, idx, field, value) => {
    const options = foreignOptions[field] || [];
    if (fkEndpoints[field]) {
      const displayText =
        typeof value === "object"
          ? value.name || value.hsn_code || value.description || value.code || ""
          : options.find((o) => o.id === value)?.name ||
            options.find((o) => o.id === value)?.hsn_code ||
            value ||
            "";
      return (
        <div className="position-relative">
          <input
            type="text"
            className="form-control"
            value={displayText}
            placeholder={`Search ${field}`}
            onFocus={() => setActiveDropdown(`${key}-${idx}-${field}`)}
            onChange={(e) => debouncedSearch(field, e.target.value)}
          />
          {activeDropdown === `${key}-${idx}-${field}` && options.length > 0 && (
            <ul
              className="list-group position-absolute w-100 shadow-sm"
              style={{ zIndex: 10, maxHeight: "180px", overflowY: "auto" }}
            >
              {options.map((opt) => (
                <li
                  key={opt.id}
                  className="list-group-item list-group-item-action"
                  onClick={() => {
                    handleNestedChange(key, idx, field, opt.id);
                    setActiveDropdown(null);
                  }}
                >
                  {opt.name || opt.hsn_code || opt.description || opt.code || `ID ${opt.id}`}
                </li>
              ))}
            </ul>
          )}
        </div>
      );
    }

    return (
      <input
        type={typeof value === "number" ? "number" : "text"}
        className="form-control"
        value={value || ""}
        onChange={(e) => handleNestedChange(key, idx, field, e.target.value)}
      />
    );
  };

  return (
    <div className="mt-4">
      {Object.keys(nestedData).map((key) => (
        <div key={key} className="border rounded bg-white p-3 mb-3">
          <h6 className="fw-bold text-secondary mb-2">
            {key.replace("_", " ").replace("norm", "Norm").toUpperCase()}
          </h6>
          {(nestedData[key] || []).map((row, i) => (
            <div key={i} className="row g-2 align-items-center mb-2">
              {Object.entries(row).map(([field, value]) => (
                <div key={field} className="col-md-3">
                  {renderField(key, i, field, value)}
                </div>
              ))}
              <div className="col-md-1">
                <button
                  type="button"
                  className="btn btn-outline-danger btn-sm"
                  onClick={() => removeRow(key, i)}
                >
                  ✖
                </button>
              </div>
            </div>
          ))}
          <button
            type="button"
            className="btn btn-outline-primary btn-sm"
            onClick={() => addRow(key)}
          >
            ➕ Add {key.replace("_", " ")}
          </button>
        </div>
      ))}
    </div>
  );
};

export default MasterNestedForm;
