// File: src/components/master/components/MasterForm.jsx
// (Full file — drop in replacing existing implementation)

import React, { useEffect, useRef, useState } from "react";
import MasterNestedForm from "./MasterNestedForm";
import { getDisplayLabel } from "../../../utils"; // your util
import { debounce } from "../../../utils/debounce"; // your util
import api from "../../../api/axios"; // use same api helper as MasterCRUD

const hiddenFields = ["id", "created_on", "modified_on", "created_by", "modified_by"];

/**
 * MasterForm
 * - Prepares payload (preserves nested ids, converts FK objects to ids)
 * - Delegates actual HTTP to onSave(formData, isEdit, nestedPayload, fileFields)
 */
const MasterForm = ({ schema = {}, meta = {}, record = {}, onSave, onCancel }) => {
  const fileFields = Object.entries(schema || {})
    .filter(([, cfg]) => cfg && (cfg.type === "file" || cfg.type === "image"))
    .map(([k]) => k);

  const normalizeRecord = (rec) => {
    if (!rec) return {};
    const out = { ...rec };
    Object.keys(rec).forEach((k) => {
      const v = rec[k];
      if (v && typeof v === "object" && "id" in v) out[k] = v.id;
    });
    return out;
  };

  const [formData, setFormData] = useState(normalizeRecord(record));
  const [nestedData, setNestedData] = useState({});
  const [fkOptions, setFkOptions] = useState({});
  const [searchTerm, setSearchTerm] = useState({});
  const [loadingField, setLoadingField] = useState(null);

  const originalRecordRef = useRef(record);
  useEffect(() => {
    originalRecordRef.current = record;
  }, [record]);

  // Field meta map (may come from backend OPTIONS)
  const fkMeta = meta?.field_meta || meta?.fieldMeta || {};
  const fkEndpoints = {};
  Object.entries(fkMeta || {}).forEach(([k, v]) => {
    if (v && (v.endpoint || v.fk_endpoint)) fkEndpoints[k] = v.endpoint || v.fk_endpoint;
  });

  // initialize nestedData from record + nested_field_defs if provided
  useEffect(() => {
    const normalized = normalizeRecord(record);
    const nd = {};
    if (record) {
      Object.keys(record).forEach((k) => {
        if (Array.isArray(record[k])) {
          nd[k] = (record[k] || []).map((item) => (item && typeof item === "object" ? { ...item } : item));
          if (k in normalized) delete normalized[k];
        }
      });
    }

    const defs = meta?.nested_field_defs || meta?.nestedFieldDefs || {};
    Object.keys(defs).forEach((k) => {
      if (!(k in nd)) nd[k] = [];
    });

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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [record, meta]);

  // --- API-backed FK search for top-level fields ---
  const searchForeignKey = debounce(async (field, query) => {
    const metaEntry = fkMeta[field];
    const endpointForField = (metaEntry && (metaEntry.endpoint || metaEntry.fk_endpoint)) || fkEndpoints[field];
    if (!endpointForField) return;
    setLoadingField(field);
    try {
      const res = await api.get(`${endpointForField}?search=${encodeURIComponent(query)}`);
      const results = res.data?.results ?? res.data ?? [];
      setFkOptions((prev) => ({ ...prev, [field]: results }));
      // if user typed something keep it in searchTerm for display
    } catch (err) {
      console.warn(`Search failed for ${field}:`, err);
      setFkOptions((prev) => ({ ...prev, [field]: [] }));
    } finally {
      setLoadingField(null);
    }
  }, 300);

  // fetch single object to resolve label when formData[field] is an id
  const fetchSingle_fk = async (field, id) => {
    if (id === undefined || id === null || id === "") return;
    const metaEntry = fkMeta[field];
    const endpointForField = (metaEntry && (metaEntry.endpoint || metaEntry.fk_endpoint)) || fkEndpoints[field];
    if (!endpointForField) return;
    try {
      const res = await api.get(`${endpointForField}${id}/`);
      const obj = res.data;
      setFkOptions((prev) => ({ ...prev, [field]: [obj] }));
      setSearchTerm((prev) => ({ ...prev, [field]: getDisplayLabel(obj) || String(obj.id) }));
    } catch (err) {
      // silent fail
    }
  };

  // whenever formData loaded that contains FK ids, fetch labels
  useEffect(() => {
    Object.entries(formData || {}).forEach(([k, v]) => {
      const metaEntry = fkMeta[k];
      const endpointForField = (metaEntry && (metaEntry.endpoint || metaEntry.fk_endpoint)) || fkEndpoints[k];
      if (!endpointForField) return;
      if (v && typeof v !== "object") {
        // primitive id, fetch single object for label
        fetchSingle_fk(k, v);
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [formData, fkMeta]);

  const handleChange = (e) => {
    const { name, type, files, value, checked } = e.target;
    setFormData((prev) => ({
      ...prev,
      [name]: type === "file" ? (files[0] || null) : type === "checkbox" ? checked : value,
    }));
  };

  // Normalize nested data for submission (convert FK object => id)
  const prepareNestedNormalized = (nestedDataObj) => {
    const out = {};
    Object.entries(nestedDataObj || {}).forEach(([k, arr]) => {
      out[k] = (arr || []).map((item) => {
        const copy = { ...(item || {}) };
        Object.keys(copy).forEach((f) => {
          const val = copy[f];
          if (val && typeof val === "object" && ("id" in val || "pk" in val)) {
            copy[f] = val.id ?? val.pk;
          }
        });
        if (copy.id === undefined && item && (item.id || item.pk)) {
          copy.id = item.id ?? item.pk;
        }
        return copy;
      });
    });
    return out;
  };

  const handleSubmit = (e) => {
    e && e.preventDefault();

    const preparedNested = prepareNestedNormalized(nestedData);

    const mapping = meta?.nestedFieldMapping || null;
    const suffix = typeof meta?.nestedFieldSuffix === "string" ? meta.nestedFieldSuffix : null;
    const normalizedNested = {};
    Object.entries(preparedNested || {}).forEach(([k, v]) => {
      if (mapping && mapping[k]) normalizedNested[mapping[k]] = v;
      else if (suffix) normalizedNested[String(k).endsWith(suffix) ? k : `${k}${suffix}`] = v;
      else normalizedNested[k] = v;
    });

    if (typeof onSave === "function") {
      onSave(formData, !!formData.id, normalizedNested, fileFields);
    }
  };

  // fields to render
  const fieldsToRender = meta.formFields?.length
    ? meta.formFields
    : Object.keys(schema).filter((f) => !hiddenFields.includes(f));

  const nestedCandidates = new Set();
  Object.keys(nestedData).forEach((k) => nestedCandidates.add(k));
  Object.entries(schema || {}).forEach(([k, cfg]) => {
    if (cfg && (cfg.type === "nested" || cfg.type === "array" || cfg.widget === "nested")) nestedCandidates.add(k);
  });
  (meta.formFields || []).forEach((f) => {
    if (/(export|import|_set|_list?)$/i.test(f)) nestedCandidates.add(f);
  });

  const renderField = (field, config = {}) => {
    if (nestedCandidates.has(field)) return null;

    // top-level FK support
    const metaEntry = fkMeta[field];
    const endpointForField = (metaEntry && (metaEntry.endpoint || metaEntry.fk_endpoint)) || fkEndpoints[field];

    if (endpointForField) {
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
          {Array.isArray(options) && options.length > 0 && (
            <div className="dropdown-menu show w-100 mt-1" style={{ zIndex: 2000 }}>
              {options.map((opt) => (
                <button
                  key={opt.id}
                  type="button"
                  className="dropdown-item text-start"
                  onMouseDown={(ev) => {
                    ev.preventDefault();
                    // store id, and set readable display
                    setFormData((prev) => ({ ...prev, [field]: opt.id }));
                    setSearchTerm((prev) => ({ ...prev, [field]: getDisplayLabel(opt) || String(opt.id) }));
                    setFkOptions((prev) => ({ ...prev, [field]: [] }));
                  }}
                >
                  {getDisplayLabel(opt) || String(opt.id)}
                </button>
              ))}
            </div>
          )}
        </div>
      );
    }

    // fallback by type (existing logic)
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
          {config.choices.map((c, i) => {
            if (Array.isArray(c)) return <option key={i} value={c[0]}>{c[1]}</option>;
            if (typeof c === "object") return <option key={i} value={c.value}>{c.label}</option>;
            return <option key={i} value={c}>{c}</option>;
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

      {((meta?.nested_field_defs && Object.keys(meta.nested_field_defs).length > 0) ||
        (meta?.nestedFieldDefs && Object.keys(meta.nestedFieldDefs).length > 0) ||
        (Object.keys(nestedData).length > 0)) && (
        <div className="mt-4">
          <MasterNestedForm
            nestedData={nestedData}
            setNestedData={setNestedData}
            fkEndpoints={fkEndpoints}
            nestedFieldDefs={meta?.nested_field_defs || meta?.nestedFieldDefs || {}}
          />
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