// File: src/components/master/components/MasterNestedForm.jsx
// (Full file — drop in replacing existing implementation)

import React, { useEffect, useMemo, useRef, useState } from "react";
import { Button, Form } from "react-bootstrap";
import api from "../../../api/axios"; // use same api helper as MasterCRUD

/**
 * MasterNestedForm
 * - Renders nested sections (union of nestedData keys and nestedFieldDefs keys)
 * - FK search-select inputs (with keyboard navigation)
 * - Client-side `required` validation from nestedFieldDefs
 * - Hidden `id` input per nested row to ensure `id` is present in nestedData and also available in DOM
 *
 * Props:
 *  - nestedData: { sectionKey: [ { ...row }, ... ] }
 *  - setNestedData: setter for nestedData
 *  - fkEndpoints: mapping { fieldName: "/api/..." } (optional)
 *  - nestedFieldDefs: { sectionKey: [ { name, type, label, required, fk_endpoint?, choices?, ... }, ... ] }
 */
const MasterNestedForm = ({ nestedData = {}, setNestedData, fkEndpoints = {}, nestedFieldDefs = {} }) => {
  const keys = useMemo(
    () => Array.from(new Set([...(Object.keys(nestedData || {})), ...(Object.keys(nestedFieldDefs || {}))])),
    [nestedData, nestedFieldDefs]
  );

  const [fkOptionsMap, setFkOptionsMap] = useState({});
  const [fkDisplayMap, setFkDisplayMap] = useState({});
  const [loadingFk, setLoadingFk] = useState({});
  const [fkActiveIdx, setFkActiveIdx] = useState({});
  const debounceTimers = useRef({});

  useEffect(() => {
    return () => {
      Object.values(debounceTimers.current).forEach(clearTimeout);
    };
  }, []);

  // initialize display map: if nestedData contains object or id, create display values.
  useEffect(() => {
    const displays = {};
    const toFetch = []; // [{mapKey, endpoint, id}]
    Object.keys(nestedData || {}).forEach((section) => {
      (nestedData[section] || []).forEach((row, idx) => {
        Object.entries(row || {}).forEach(([fld, val]) => {
          const defs = nestedFieldDefs[section] || [];
          const def = defs.find((d) => d.name === fld);
          if (!def) return;
          const mapKey = `${section}__${fld}__${idx}`;
          if (val && typeof val === "object") {
            displays[mapKey] = val.name || val.title || val.label || val.display || "";
          } else if (val || val === 0) {
            // primitive id — resolve label if possible later
            displays[mapKey] = "";
            const endpoint = resolveFkEndpoint(section, def);
            if (endpoint) {
              toFetch.push({ mapKey, endpoint, id: val, label_field: def.label_field || def.labelField || def.labelFieldName });
            }
          } else {
            displays[mapKey] = "";
          }
        });
      });
    });
    setFkDisplayMap((prev) => ({ ...displays, ...prev }));

    // fetch single objects for primitive ids to resolve labels
    toFetch.forEach(({ mapKey, endpoint, id }) => {
      // make sure endpoint ends with '/'
      const url = `${String(endpoint).endsWith("/") ? endpoint : `${endpoint}`}${String(id)}/`;
      (async () => {
        try {
          const res = await api.get(url);
          const obj = res.data;
          setFkDisplayMap((p) => ({ ...p, [mapKey]: displayLabel(obj) || String(id) }));
        } catch (err) {
          // ignore fetch errors
        }
      })();
    });

    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nestedData, nestedFieldDefs]);

  const displayLabel = (obj) => {
    if (!obj) return "";
    return obj.name ?? obj.title ?? obj.label ?? obj.display ?? (obj.hs_code ? `${obj.hs_code}` : (obj.id !== undefined ? String(obj.id) : ""));
  };

  const resolveFkEndpoint = (section, fieldDef) => {
    if (!fieldDef) return null;
    return (
      fieldDef.fk_endpoint ||
      fieldDef.endpoint ||
      fieldDef.lookup ||
      fieldDef.foreign_key_endpoint ||
      fkEndpoints[fieldDef.name] ||
      fkEndpoints[`${section}.${fieldDef.name}`] ||
      null
    );
  };

  // fetch fk options (search)
  const fetchFkOptions = async (mapKey, endpoint, query) => {
    if (!endpoint) return;
    setLoadingFk((s) => ({ ...s, [mapKey]: true }));
    try {
      const res = await api.get(`${endpoint}?search=${encodeURIComponent(query || "")}`);
      const results = res.data?.results ?? res.data ?? [];
      setFkOptionsMap((prev) => ({ ...prev, [mapKey]: results }));
      setFkActiveIdx((p) => ({ ...p, [mapKey]: results.length ? 0 : -1 }));
    } catch (err) {
      console.warn("FK search failed", endpoint, err);
      setFkOptionsMap((prev) => ({ ...prev, [mapKey]: [] }));
      setFkActiveIdx((p) => ({ ...p, [mapKey]: -1 }));
    } finally {
      setLoadingFk((s) => ({ ...s, [mapKey]: false }));
    }
  };

  const makeEmptyRow = (section) => {
    const defs = nestedFieldDefs[section] || [];
    if (!Array.isArray(defs) || defs.length === 0) return { id: null };
    const row = { id: null };
    defs.forEach((d) => {
      row[d.name] = d.default ?? (d.type === "boolean" ? false : "");
    });
    return row;
  };

  const normalizedNestedData = useMemo(() => {
    const nd = { ...(nestedData || {}) };
    Object.keys(nestedFieldDefs || {}).forEach((k) => {
      if (!(k in nd)) nd[k] = [];
    });
    return nd;
  }, [nestedData, nestedFieldDefs]);

  const handleAddRow = (section) => {
    setNestedData((prev) => {
      const next = { ...(prev || {}) };
      next[section] = [...(next[section] || []), makeEmptyRow(section)];
      return next;
    });
  };

  const handleRemoveRow = (section, index) => {
    setNestedData((prev) => {
      const next = { ...(prev || {}) };
      next[section] = (next[section] || []).filter((_, i) => i !== index);
      return next;
    });
    // cleanup transient UI state
    setFkDisplayMap((prev) => {
      const copy = { ...prev };
      Object.keys(copy).forEach((k) => {
        if (k.startsWith(`${section}__`) && k.endsWith(`__${index}`)) delete copy[k];
      });
      return copy;
    });
    setFkOptionsMap((prev) => {
      const copy = { ...prev };
      Object.keys(copy).forEach((k) => {
        if (k.startsWith(`${section}__`) && k.endsWith(`__${index}`)) delete copy[k];
      });
      return copy;
    });
    setFkActiveIdx((p) => {
      const copy = { ...p };
      Object.keys(copy).forEach((k) => {
        if (k.startsWith(`${section}__`) && k.endsWith(`__${index}`)) delete copy[k];
      });
      return copy;
    });
  };

  const handleChange = (section, index, field, value) =>
    setNestedData((prev) => {
      const next = { ...(prev || {}) };
      const arr = [...(next[section] || [])];
      arr[index] = { ...arr[index], [field]: value };
      next[section] = arr;
      return next;
    });

  // typed FK input: debounced search
  const handleFkInput = (section, index, fieldDef, text) => {
    const mapKey = `${section}__${fieldDef.name}__${index}`;
    const endpoint = resolveFkEndpoint(section, fieldDef);
    setFkDisplayMap((p) => ({ ...p, [mapKey]: text }));

    if (debounceTimers.current[mapKey]) clearTimeout(debounceTimers.current[mapKey]);
    debounceTimers.current[mapKey] = setTimeout(() => {
      fetchFkOptions(mapKey, endpoint, text || "");
    }, 250);
  };

  const handlePickFk = (section, index, fieldDef, option) => {
    // store FK as id for submission
    handleChange(section, index, fieldDef.name, option.id);
    const mapKey = `${section}__${fieldDef.name}__${index}`;
    setFkDisplayMap((p) => ({ ...p, [mapKey]: displayLabel(option) }));
    setFkOptionsMap((p) => ({ ...p, [mapKey]: [] }));
    setFkActiveIdx((p) => ({ ...p, [mapKey]: -1 }));
  };

  const handleFkKeyDown = (e, section, index, fieldDef) => {
    const mapKey = `${section}__${fieldDef.name}__${index}`;
    const options = fkOptionsMap[mapKey] || [];
    const active = typeof fkActiveIdx[mapKey] === "number" ? fkActiveIdx[mapKey] : -1;

    if (e.key === "ArrowDown") {
      e.preventDefault();
      if (options.length === 0) return;
      const nextIdx = active < options.length - 1 ? active + 1 : 0;
      setFkActiveIdx((p) => ({ ...p, [mapKey]: nextIdx }));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (options.length === 0) return;
      const nextIdx = active > 0 ? active - 1 : options.length - 1;
      setFkActiveIdx((p) => ({ ...p, [mapKey]: nextIdx }));
    } else if (e.key === "Enter") {
      if (options.length > 0 && active >= 0) {
        e.preventDefault();
        handlePickFk(section, index, fieldDef, options[active]);
      }
    } else if (e.key === "Escape") {
      setFkOptionsMap((p) => ({ ...p, [mapKey]: [] }));
      setFkActiveIdx((p) => ({ ...p, [mapKey]: -1 }));
    }
  };

  const validateField = (section, index, fieldDef, value) => {
    if (!fieldDef) return null;
    const required = fieldDef.required === true;
    if (!required) return null;
    if ((fieldDef.type === "number" || fieldDef.type === "integer") && (value === 0 || value === "0")) {
      return null;
    }
    if (value === null || value === undefined || value === "") {
      return "Required";
    }
    return null;
  };

  const hiddenFields = ["id", "created_on", "modified_on", "created_by", "modified_by"];

  return (
    <div className="nested-form-container">
      {keys.map((section) => {
        const items = normalizedNestedData[section] || [];
        const defs = nestedFieldDefs[section] || [];

        return (
          <div key={section} className="card border-0 shadow-sm mb-3">
            <div className="card-header bg-light d-flex justify-content-between align-items-center">
              <h6 className="fw-bold text-uppercase mb-0">{section.replace(/_/g, " ")}</h6>
              <Button size="sm" variant="success" onClick={() => handleAddRow(section)}>
                <i className="bi bi-plus-circle" /> Add Row
              </Button>
            </div>

            <div className="card-body">
              {items.length === 0 && <p className="text-muted small">No entries yet. Click "Add Row" to create one.</p>}

              {items.map((item, rowIndex) => (
                <div key={rowIndex} className="border rounded p-3 mb-3 bg-light-subtle position-relative">
                  {/* Hidden id input so DOM-based serialization can pick it up if needed */}
                  <input type="hidden" value={item?.id ?? item?.pk ?? ""} name={`${section}[${rowIndex}][id]`} data-nested-id />

                  <Button variant="outline-danger" size="sm" className="position-absolute top-0 end-0 m-2" onClick={() => handleRemoveRow(section, rowIndex)}>
                    <i className="bi bi-x-lg" />
                  </Button>

                  <div className="row g-3">
                    {(
                      (Array.isArray(defs) && defs.length) ? defs : Object.keys(item || {}).map((n) => ({ name: n, type: "string", label: n }))
                    )
                      .filter((f) => !hiddenFields.includes(f.name))
                      .map((fieldDef) => {
                        const fname = fieldDef.name;
                        const ftype = (fieldDef.type || "string").toLowerCase();
                        const value = item?.[fname] ?? "";
                        const mapKey = `${section}__${fname}__${rowIndex}`;
                        const fkEndpoint = resolveFkEndpoint(section, fieldDef);

                        const error = validateField(section, rowIndex, fieldDef, value);
                        const invalidClass = error ? "is-invalid" : "";

                        const renderControl = () => {
                          if (fkEndpoint) {
                            const options = fkOptionsMap[mapKey] || [];
                            const display = fkDisplayMap[mapKey] ?? (typeof value === "object" ? displayLabel(value) : "");
                            const active = fkActiveIdx[mapKey] ?? -1;

                            return (
                              <div className="position-relative">
                                <input
                                  type="text"
                                  className={`form-control ${invalidClass}`}
                                  placeholder={fieldDef.label || fname}
                                  value={display}
                                  onChange={(e) => handleFkInput(section, rowIndex, fieldDef, e.target.value)}
                                  onFocus={(e) => {
                                    if (!options || options.length === 0) handleFkInput(section, rowIndex, fieldDef, e.target.value ?? "");
                                  }}
                                  onKeyDown={(e) => handleFkKeyDown(e, section, rowIndex, fieldDef)}
                                  autoComplete="off"
                                />
                                {loadingFk[mapKey] && <div className="small text-muted mt-1">Searching...</div>}
                                {error && <div className="invalid-feedback">{error}</div>}
                                {options.length > 0 && (
                                  <div className="dropdown-menu show w-100 mt-1" style={{ maxHeight: 220, overflowY: "auto", zIndex: 2000 }}>
                                    {options.map((opt, idx) => (
                                      <button
                                        type="button"
                                        key={opt.id ?? idx}
                                        className={`dropdown-item text-start ${idx === active ? "active" : ""}`}
                                        onMouseDown={(ev) => {
                                          ev.preventDefault();
                                          handlePickFk(section, rowIndex, fieldDef, opt);
                                        }}
                                      >
                                        {displayLabel(opt)}
                                      </button>
                                    ))}
                                  </div>
                                )}
                              </div>
                            );
                          }

                          if (Array.isArray(fieldDef.choices) && fieldDef.choices.length) {
                            return (
                              <>
                                <Form.Select className={invalidClass} value={value} onChange={(e) => handleChange(section, rowIndex, fname, e.target.value)}>
                                  <option value="">— select —</option>
                                  {fieldDef.choices.map((c, ci) =>
                                    Array.isArray(c) ? (
                                      <option key={ci} value={c[0]}>{c[1]}</option>
                                    ) : typeof c === "object" ? (
                                      <option key={ci} value={c.value}>{c.label}</option>
                                    ) : (
                                      <option key={ci} value={c}>{c}</option>
                                    )
                                  )}
                                </Form.Select>
                                {error && <div className="invalid-feedback d-block">{error}</div>}
                              </>
                            );
                          }

                          if (ftype === "number" || ftype === "integer") {
                            return (
                              <>
                                <Form.Control className={invalidClass} type="number" value={value} onChange={(e) => handleChange(section, rowIndex, fname, e.target.value)} />
                                {error && <div className="invalid-feedback d-block">{error}</div>}
                              </>
                            );
                          }

                          if (ftype === "boolean") {
                            return <Form.Check type="checkbox" checked={!!value} onChange={(e) => handleChange(section, rowIndex, fname, e.target.checked)} label={fieldDef.label || fname} />;
                          }

                          return (
                            <>
                              <Form.Control className={invalidClass} type="text" value={value} onChange={(e) => handleChange(section, rowIndex, fname, e.target.value)} />
                              {error && <div className="invalid-feedback d-block">{error}</div>}
                            </>
                          );
                        };

                        return (
                          <div key={fname} className="col-md-4">
                            <Form.Group>
                              <Form.Label className="fw-medium text-secondary small">{fieldDef.label || fname.replace(/_/g, " ")}</Form.Label>
                              {renderControl()}
                            </Form.Group>
                          </div>
                        );
                      })}
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
};

export default MasterNestedForm;
