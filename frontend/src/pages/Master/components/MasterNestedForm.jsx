import React from "react";
import { Button, Form } from "react-bootstrap";

/**
 * MasterNestedForm
 * ---------------
 * Handles related (formset-like) nested fields dynamically for any parent record.
 * Renders sections based on the union of nestedData keys and nestedFieldDefs keys.
 */
const MasterNestedForm = ({ nestedData = {}, setNestedData, fkEndpoints = {}, nestedFieldDefs = {} }) => {
  // build list of keys to render: union of nestedData keys and defs keys
  const keys = Array.from(new Set([...(Object.keys(nestedData || {})), ...(Object.keys(nestedFieldDefs || {}))]));

  if (!keys.length) return null;

  // Helper: create an empty row based on defs (or fallback to empty object)
  const makeEmptyRow = (key) => {
    const defs = nestedFieldDefs[key] || [];
    if (!Array.isArray(defs) || defs.length === 0) return {};
    const row = {};
    defs.forEach((d) => {
      row[d.name] = d.default ?? (d.type === "boolean" ? false : "");
    });
    return row;
  };

  // Ensure nestedData has keys for all defs (so empty sections render)
  const normalizedNestedData = { ...(nestedData || {}) };
  Object.keys(nestedFieldDefs || {}).forEach((k) => {
    if (!(k in normalizedNestedData)) normalizedNestedData[k] = [];
  });

  // Add a new empty row to a given nested key
  const handleAddRow = (key) => {
    setNestedData((prev) => {
      const next = { ...(prev || {}) };
      next[key] = [...(next[key] || []), makeEmptyRow(key)];
      return next;
    });
  };

  // Remove a row by index
  const handleRemoveRow = (key, index) => {
    setNestedData((prev) => {
      const next = { ...(prev || {}) };
      next[key] = (next[key] || []).filter((_, i) => i !== index);
      return next;
    });
  };

  // Handle change in any nested field
  const handleChange = (key, index, field, value) => {
    setNestedData((prev) => {
      const next = { ...(prev || {}) };
      const updated = [...(next[key] || [])];
      updated[index] = { ...updated[index], [field]: value };
      next[key] = updated;
      return next;
    });
  };

  const hiddenFields = ["id", "created_on", "modified_on", "created_by", "modified_by"];

  return (
    <div className="nested-form-container">
      {keys.map((key) => {
        const items = normalizedNestedData[key] || [];
        const defs = nestedFieldDefs[key] || [];

        return (
          <div key={key} className="card border-0 shadow-sm mb-3">
            <div className="card-header bg-light d-flex justify-content-between align-items-center">
              <h6 className="fw-bold text-uppercase mb-0">
                {(Array.isArray(defs) && defs.length && defs[0].label) ? defs[0].label : key.replace(/_/g, " ")}
              </h6>
              <Button
                size="sm"
                variant="success"
                onClick={() => handleAddRow(key)}
              >
                <i className="bi bi-plus-circle"></i> Add Row
              </Button>
            </div>

            <div className="card-body">
              {(!items || items.length === 0) && (
                <p className="text-muted small">No entries yet. Click "Add Row" to create one.</p>
              )}

              {items?.map((item, index) => (
                <div
                  key={index}
                  className="border rounded p-3 mb-3 bg-light-subtle position-relative"
                >
                  <Button
                    variant="outline-danger"
                    size="sm"
                    className="position-absolute top-0 end-0 m-2"
                    onClick={() => handleRemoveRow(key, index)}
                  >
                    <i className="bi bi-x-lg"></i>
                  </Button>

                  <div className="row g-3">
                    {/* If defs are available render fields from defs, otherwise fallback to keys of item */}
                    {(((Array.isArray(defs) && defs.length) ? defs : Object.keys(item).map((n) => ({ name: n, type: "string", label: n }))))
                      .filter((f) => !hiddenFields.includes(f.name))
                      .map((fieldDef) => {
                        const fname = fieldDef.name;
                        const ftype = (fieldDef.type || "string").toLowerCase();
                        const value = item[fname] ?? "";

                        const renderControl = () => {
                          if (fieldDef.choices && Array.isArray(fieldDef.choices)) {
                            return (
                              <Form.Select
                                value={value}
                                onChange={(e) => handleChange(key, index, fname, e.target.value)}
                              >
                                <option value="">— select —</option>
                                {fieldDef.choices.map((c) =>
                                  Array.isArray(c) ? (
                                    <option key={c[0]} value={c[0]}>
                                      {c[1]}
                                    </option>
                                  ) : typeof c === "object" ? (
                                    <option key={c.value} value={c.value}>
                                      {c.label}
                                    </option>
                                  ) : (
                                    <option key={c} value={c}>
                                      {c}
                                    </option>
                                  )
                                )}
                              </Form.Select>
                            );
                          }

                          if (ftype === "number" || ftype === "integer") {
                            return (
                              <Form.Control
                                type="number"
                                value={value}
                                onChange={(e) => handleChange(key, index, fname, e.target.value)}
                              />
                            );
                          }

                          if (ftype === "boolean") {
                            return (
                              <Form.Check
                                type="checkbox"
                                checked={!!value}
                                onChange={(e) => handleChange(key, index, fname, e.target.checked)}
                                label={fieldDef.label || fname}
                              />
                            );
                          }

                          // default: text
                          return (
                            <Form.Control
                              type="text"
                              value={value}
                              onChange={(e) => handleChange(key, index, fname, e.target.value)}
                            />
                          );
                        };

                        return (
                          <div key={fname} className="col-md-4">
                            <Form.Group>
                              <Form.Label className="fw-medium text-secondary small">
                                {fieldDef.label || fname.replace(/_/g, " ")}
                              </Form.Label>
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
