// src/components/MasterNestedForm.jsx
import React, { useEffect, useRef, useState } from "react";
import api from "../../../api/axios";
import { debounce } from "../../../utils/debounce.js";
import { getDisplayLabel } from "../../../utils";

/*
  Accepts fkEndpoints prop (object field->endpoint). If not present, falls back
  to an empty object (no FK loads).
*/

const MasterNestedForm = ({ nestedData = {}, setNestedData, fkEndpoints = {} }) => {
  const [foreignOptions, setForeignOptions] = useState({});
  const [activeDropdown, setActiveDropdown] = useState(null);
  const [loadingField, setLoadingField] = useState(null);
  const [searchTerms, setSearchTerms] = useState({});
  const mountedRef = useRef(false);

  const loadOptions = async (field, query = "") => {
    const endpoint = fkEndpoints[field];
    if (!endpoint) {
      setForeignOptions((prev) => ({ ...prev, [field]: [] }));
      return;
    }
    setLoadingField(field);
    try {
      const res = await api.get(`${endpoint}?search=${encodeURIComponent(query)}`);
      const items = res?.data?.results ?? res?.data ?? [];
      setForeignOptions((prev) => ({ ...prev, [field]: items }));
    } catch (err) {
      if (err?.response) console.warn(`FK fetch for "${field}" returned ${err.response.status}`);
      else console.warn(`FK fetch for "${field}" failed: ${err?.message ?? err}`);
      setForeignOptions((prev) => ({ ...prev, [field]: [] }));
    } finally {
      setLoadingField((prev) => (prev === field ? null : prev));
    }
  };

  const debouncedSearchRef = useRef();
  if (!debouncedSearchRef.current) debouncedSearchRef.current = debounce((field, q) => loadOptions(field, q), 350);
  const debouncedSearch = debouncedSearchRef.current;

  useEffect(() => {
    if (mountedRef.current) return;
    mountedRef.current = true;
    // load options only for endpoints present in fkEndpoints
    Object.keys(fkEndpoints).forEach((f) => loadOptions(f, ""));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [fkEndpoints]);

  const handleNestedChange = (parentKey, index, field, value) => {
    setNestedData((prev) => {
      const prevArr = Array.isArray(prev[parentKey]) ? prev[parentKey] : [];
      const newArr = prevArr.map((r, i) => (i === index ? { ...r, [field]: value } : { ...r }));
      return { ...prev, [parentKey]: newArr };
    });
  };

  const addRow = (key) => {
    setNestedData((prev) => {
      const prevArr = Array.isArray(prev[key]) ? prev[key] : [];
      let newRow = {};
      if (prevArr.length > 0) {
        const sample = prevArr[0];
        Object.keys(sample).forEach((k) => (newRow[k] = ""));
      }
      return { ...prev, [key]: [...prevArr, newRow] };
    });
  };

  const removeRow = (key, idx) => {
    setNestedData((prev) => {
      const prevArr = Array.isArray(prev[key]) ? prev[key] : [];
      const newArr = prevArr.filter((_, i) => i !== idx);
      return { ...prev, [key]: newArr };
    });
  };

  const getDisplayText = (field, value, typed) => {
    if (typed && typed.length > 0) return typed;
    const options = foreignOptions[field] || [];
    if (value == null) return "";
    if (typeof value === "object") return getDisplayLabel(value);
    const found = options.find((o) => String(o.id) === String(value));
    return found ? getDisplayLabel(found) : String(value);
  };

  const renderField = (parentKey, idx, field, value) => {
    const options = foreignOptions[field] || [];
    const isFk = Object.prototype.hasOwnProperty.call(fkEndpoints, field);
    const inputId = `${parentKey}-${idx}-${field}`;

    if (isFk) {
      return (
        <div className="position-relative">
          <input
            id={inputId}
            type="text"
            className="form-control"
            placeholder={`Search ${field}`}
            value={getDisplayText(field, value, searchTerms[inputId])}
            onFocus={() => {
              setActiveDropdown(inputId);
              if (!options || options.length === 0) loadOptions(field, "");
            }}
            onChange={(e) => {
              const val = e.target.value;
              setSearchTerms((s) => ({ ...s, [inputId]: val }));
              debouncedSearch(field, val);
            }}
            onBlur={() => setTimeout(() => setActiveDropdown((cur) => (cur === inputId ? null : cur)), 150)}
            autoComplete="off"
          />

          {loadingField === field && <div className="small text-muted mt-1">Loading...</div>}

          {activeDropdown === inputId && options.length > 0 && (
            <ul className="list-group position-absolute w-100 shadow-sm" style={{ zIndex: 10, maxHeight: "180px", overflowY: "auto" }}>
              {options.map((opt) => (
                <li
                  key={opt.id}
                  className="list-group-item list-group-item-action"
                  onMouseDown={(ev) => {
                    ev.preventDefault();
                    handleNestedChange(parentKey, idx, field, opt.id);
                    setSearchTerms((s) => ({ ...s, [inputId]: "" }));
                    setActiveDropdown(null);
                  }}
                >
                  {getDisplayLabel(opt)}
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
        value={value ?? ""}
        onChange={(e) => handleNestedChange(parentKey, idx, field, e.target.value)}
      />
    );
  };

  if (!nestedData || Object.keys(nestedData).length === 0) return null;

  return (
    <div className="mt-4">
      {Object.keys(nestedData).map((key) => {
        const rows = Array.isArray(nestedData[key]) ? nestedData[key] : [];
        return (
          <div key={key} className="border rounded bg-white p-3 mb-3">
            <h6 className="fw-bold text-secondary mb-2">{key.replace(/_/g, " ").replace(/norm/gi, "Norm").toUpperCase()}</h6>

            {rows.length === 0 && <div className="mb-2 text-muted">No entries yet.</div>}

            {rows.map((row, i) => (
              <div key={i} className="row g-2 align-items-center mb-2">
                {Object.entries(row).map(([field, value]) => (
                  <div key={field} className="col-md-3">
                    {renderField(key, i, field, value)}
                  </div>
                ))}
                <div className="col-md-1">
                  <button type="button" className="btn btn-outline-danger btn-sm" onClick={() => removeRow(key, i)} aria-label={`Remove row ${i + 1}`}>
                    ✖
                  </button>
                </div>
              </div>
            ))}

            <button type="button" className="btn btn-outline-primary btn-sm" onClick={() => addRow(key)}>
              ➕ Add {key.replace(/_/g, " ")}
            </button>
          </div>
        );
      })}
    </div>
  );
};

export default MasterNestedForm;
