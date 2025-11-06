import React, { useEffect, useRef, useState } from "react";
import api from "../../../api/axios";
import { debounce } from "../../../utils/debounce";

const hiddenFields = ["id", "created_on", "modified_on", "created_by", "modified_by"];

// endpoints for FK autocomplete (customize to your app)
const foreignKeyEndpoints = {
  hsn_code: "/masters/hsn-code/",
  head_norm: "/masters/head-norm/",
  norm_class: "/masters/sion-norms/",
  company: "/masters/company/",
  port: "/masters/port/",
};

const MasterForm = ({ schema = {}, meta = {}, record, onSave, onCancel }) => {
  // Normalize incoming record (if FK fields are objects, convert to id)
  const normalizeRecord = (rec) => {
    if (!rec) return {};
    const out = { ...rec };
    Object.keys(rec).forEach((k) => {
      const val = rec[k];
      if (val && typeof val === "object" && "id" in val) out[k] = val.id;
    });
    return out;
  };

  const [formData, setFormData] = useState(normalizeRecord(record));
  const [fkOptions, setFkOptions] = useState({});
  const [searchTerm, setSearchTerm] = useState({});
  const [loadingField, setLoadingField] = useState(null);

  useEffect(() => {
    setFormData(normalizeRecord(record));
    if (record) {
      const st = {};
      Object.keys(record).forEach((k) => {
        const v = record[k];
        if (v && typeof v === "object") {
          st[k] = v.name || v.code || v.hsn_code || `${v.id}`;
        }
      });
      setSearchTerm((prev) => ({ ...prev, ...st }));
    }
  }, [record]);

  // debounce search — keep a stable ref to the debounced function
  const searchForeignKey = useRef(
    debounce(async (field, query) => {
      if (!foreignKeyEndpoints[field]) return;
      setLoadingField(field);
      try {
        const res = await api.get(`${foreignKeyEndpoints[field]}?search=${encodeURIComponent(query)}`);
        setFkOptions((prev) => ({ ...prev, [field]: res.data.results || res.data || [] }));
      } catch (err) {
        console.warn(`Search failed for ${field}:`, err);
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
    onSave(formData, !!formData.id);
  };

  const fieldsToRender = meta.formFields?.length
    ? meta.formFields
    : Object.keys(schema).filter((f) => !hiddenFields.includes(f));

  const renderField = (field, config = {}) => {
    // ForeignKey autocomplete
    if (foreignKeyEndpoints[field]) {
      const options = fkOptions[field] || [];
      return (
        <div className="position-relative">
          <input
            type="text"
            className="form-control"
            placeholder={`Search ${config.label || field}`}
            value={searchTerm[field] ?? (formData[field] ? String(formData[field]) : "")}
            onChange={(e) => {
              const val = e.target.value;
              setSearchTerm((prev) => ({ ...prev, [field]: val }));
              if (val && val.length >= 1) searchForeignKey(field, val);
            }}
          />
          {loadingField === field && <div className="small text-muted mt-1">Searching...</div>}
          {options.length > 0 && (
            <div
              className="dropdown-menu show w-100 mt-1"
              style={{ maxHeight: 200, overflowY: "auto" }}
            >
              {options.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  className={`dropdown-item ${formData[field] === opt.id ? "active" : ""}`}
                  onClick={() => {
                    setFormData((prev) => ({ ...prev, [field]: opt.id }));
                    setSearchTerm((prev) => ({
                      ...prev,
                      [field]: opt.name || opt.hsn_code || opt.description || opt.code || `#${opt.id}`,
                    }));
                  }}
                >
                  {opt.name || opt.hsn_code || opt.description || opt.code || `#${opt.id}`}
                </button>
              ))}
            </div>
          )}
        </div>
      );
    }

    // File / Image
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
              <img
                src={previewUrl}
                alt="preview"
                style={{ maxWidth: "120px", maxHeight: "120px", objectFit: "cover" }}
              />
            </div>
          )}
        </div>
      );
    }

    // Boolean
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

    // Choices / Select
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

    // textarea
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

    // default: number or text
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
          return (
            <div key={field} className="col-md-4">
              <label className="form-label fw-medium">{config.label || field}</label>
              {renderField(field, config)}
            </div>
          );
        })}
      </div>

      <div className="mt-3">
        <button type="submit" className="btn btn-primary me-2">
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
