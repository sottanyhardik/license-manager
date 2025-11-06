// src/components/MasterForm.jsx
import React, { useEffect, useRef, useState } from "react";
import api from "../../../api/axios";
import { debounce } from "../../../utils/debounce";
import MasterNestedForm from "./MasterNestedForm";
import { getDisplayLabel, getFkEndpoints } from "../../../utils";

const hiddenFields = ["id", "created_on", "modified_on", "created_by", "modified_by"];

const MasterForm = ({ schema = {}, meta = {}, record, onSave, onCancel }) => {
  const normalizeRecord = (rec) => {
    if (!rec) return {};
    const out = { ...rec };
    Object.keys(rec).forEach((k) => {
      const v = rec[k];
      if (v && typeof v === "object" && "id" in v) out[k] = v.id;
    });
    return out;
  };

  // file fields from schema
  const fileFields = Object.entries(schema || {})
    .filter(([, cfg]) => cfg && (cfg.type === "file" || cfg.type === "image"))
    .map(([k]) => k);

  const [formData, setFormData] = useState(normalizeRecord(record));
  const [nestedData, setNestedData] = useState({});
  const [fkOptions, setFkOptions] = useState({});
  const [searchTerm, setSearchTerm] = useState({});
  const [loadingField, setLoadingField] = useState(null);

  // derive endpoints only for fields present in schema or meta.formFields
  const schemaFields = meta.formFields?.length ? meta.formFields : Object.keys(schema || {});
  const fkEndpoints = getFkEndpoints(schemaFields);

  useEffect(() => {
    const normalized = normalizeRecord(record);
    const nd = {};
    if (record) {
      Object.keys(record).forEach((k) => {
        if (Array.isArray(record[k])) {
          nd[k] = record[k];
          if (k in normalized) delete normalized[k];
        }
      });
    }
    setFormData(normalized);
    setNestedData(nd);

    if (record) {
      const st = {};
      Object.keys(record).forEach((k) => {
        const v = record[k];
        if (v && typeof v === "object") {
          st[k] = getDisplayLabel(v) || `${v.id}`;
        }
      });
      setSearchTerm((prev) => ({ ...prev, ...st }));
    }
  }, [record]);

  // debounce FK search
  const searchForeignKey = useRef(
    debounce(async (field, query) => {
      if (!fkEndpoints[field]) return;
      setLoadingField(field);
      try {
        const res = await api.get(`${fkEndpoints[field]}?search=${encodeURIComponent(query)}`);
        setFkOptions((prev) => ({ ...prev, [field]: res.data.results || res.data || [] }));
      } catch (err) {
        console.warn(`Search failed for ${field}:`, err);
        setFkOptions((prev) => ({ ...prev, [field]: [] }));
      } finally {
        setLoadingField(null);
      }
    }, 400)
  ).current;

  const handleChange = (e) => {
    const { name, type, files, value, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === "file" ? (files[0] || null) : type === "checkbox" ? checked : value,
    }));
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const mapping = meta?.nestedFieldMapping || null;
    const suffix = typeof meta?.nestedFieldSuffix === "string" ? meta.nestedFieldSuffix : null;

    const normalizedNested = {};
    Object.entries(nestedData || {}).forEach(([k, v]) => {
      if (mapping && mapping[k]) normalizedNested[mapping[k]] = v;
      else if (suffix) normalizedNested[String(k).endsWith(suffix) ? k : `${k}${suffix}`] = v;
      else normalizedNested[k] = v;
    });

    onSave(formData, !!formData.id, normalizedNested, fileFields);
  };

  const fieldsToRender = meta.formFields?.length
    ? meta.formFields
    : Object.keys(schema).filter((f) => !hiddenFields.includes(f));

  const nestedCandidates = new Set();
  Object.keys(nestedData).forEach((k) => nestedCandidates.add(k));
  Object.entries(schema || {}).forEach(([k, cfg]) => {
    if (cfg && (cfg.type === "nested" || cfg.type === "array" || cfg.widget === "nested")) nestedCandidates.add(k);
  });
  (meta.formFields || []).forEach((f) => {
    if (/(export|import|_set|_list|norms?)$/i.test(f)) nestedCandidates.add(f);
  });

  const renderField = (field, config = {}) => {
    if (nestedCandidates.has(field)) return null;

    if (fkEndpoints[field]) {
      const options = fkOptions[field] || [];
      const displayValue = (() => {
        const st = searchTerm[field];
        if (st && st.length > 0) return st;
        const found = options.find((o) => String(o.id) === String(formData[field]));
        return found ? getDisplayLabel(found) : formData[field] ?? "";
      })();

      return (
        <div className="position-relative">
          <input
            type="text"
            className="form-control"
            placeholder={`Search ${config.label || field}`}
            value={displayValue}
            onChange={(e) => {
              const val = e.target.value;
              setSearchTerm((prev) => ({ ...prev, [field]: val }));
              if (val && val.length >= 1) searchForeignKey(field, val);
            }}
            onFocus={() => {
              if (!options || options.length === 0) searchForeignKey(field, "");
            }}
            autoComplete="off"
          />
          {loadingField === field && <div className="small text-muted mt-1">Searching...</div>}
          {options.length > 0 && (
            <div className="dropdown-menu show w-100 mt-1" style={{ maxHeight: 200, overflowY: "auto" }}>
              {options.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  className={`dropdown-item ${String(formData[field]) === String(opt.id) ? "active" : ""}`}
                  onClick={() => {
                    setFormData((prev) => ({ ...prev, [field]: opt.id }));
                    setSearchTerm((prev) => ({ ...prev, [field]: getDisplayLabel(opt) }));
                  }}
                >
                  {getDisplayLabel(opt)}
                </button>
              ))}
            </div>
          )}
        </div>
      );
    }

    if (config.type === "file" || config.type === "image") {
      const current = formData[field];
      const previewUrl =
        current instanceof File
          ? URL.createObjectURL(current)
          : typeof current === "string" && current.length > 0
          ? current
          : null;

      return (
        <div>
          <input
            type="file"
            name={field}
            className="form-control"
            accept={config.type === "image" ? "image/*" : undefined}
            onChange={handleChange}
          />
          {previewUrl && (
            <div style={{ marginTop: 6 }}>
              <img src={previewUrl} alt="preview" style={{ maxWidth: "120px", maxHeight: "120px", objectFit: "cover" }} />
            </div>
          )}
        </div>
      );
    }

    if (config.type === "boolean") {
      return (
        <div className="form-check">
          <input
            className="form-check-input"
            type="checkbox"
            id={field}
            name={field}
            checked={!!formData[field]}
            onChange={handleChange}
          />
          <label className="form-check-label" htmlFor={field}>
            {config.label || field}
          </label>
        </div>
      );
    }

    if (config.choices && Array.isArray(config.choices)) {
      return (
        <select name={field} className="form-select" value={formData[field] ?? ""} onChange={handleChange}>
          <option value="">— select —</option>
          {config.choices.map((c) => {
            if (Array.isArray(c)) return <option key={c[0]} value={c[0]}>{c[1]}</option>;
            if (typeof c === "object") return <option key={c.value} value={c.value}>{c.label}</option>;
            return <option key={c} value={c}>{c}</option>;
          })}
        </select>
      );
    }

    if (config.type === "text" || config.widget === "textarea") {
      return (
        <textarea
          name={field}
          className="form-control"
          value={formData[field] ?? ""}
          onChange={handleChange}
          placeholder={config.label || field}
        />
      );
    }

    const inputType = config.type === "integer" || config.type === "number" ? "number" : "text";
    return (
      <input
        type={inputType}
        name={field}
        value={formData[field] ?? ""}
        onChange={handleChange}
        className="form-control"
        placeholder={config.label || field}
      />
    );
  };

  return (
    <form onSubmit={handleSubmit} className="border rounded p-3 bg-light" encType="multipart/form-data">
      <div className="row g-3">
        {fieldsToRender.map((field) => {
          const config = schema[field] || { label: field, type: "text" };
          if (hiddenFields.includes(field)) return null;
          if (nestedCandidates.has(field)) return null;
          return (
            <div key={field} className="col-md-4">
              <label className="form-label fw-medium">{config.label || field}</label>
              {renderField(field, config)}
            </div>
          );
        })}
      </div>

      {Array.from(nestedCandidates).length > 0 && (
        <div className="mt-4">
          <MasterNestedForm nestedData={nestedData} setNestedData={setNestedData} fkEndpoints={fkEndpoints} />
        </div>
      )}

      <div className="mt-3 d-flex gap-2">
        <button type="submit" className="btn btn-primary">
          {formData.id ? "Update" : "Save"}
        </button>
        <button type="button" className="btn btn-secondary" onClick={onCancel}>
          Cancel
        </button>
      </div>
    </form>
  );
};

export default MasterForm;
