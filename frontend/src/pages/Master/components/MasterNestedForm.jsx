import React from "react";
import { Button, Form } from "react-bootstrap";

/**
 * MasterNestedForm
 * ---------------
 * Handles related (formset-like) nested fields dynamically for any parent record.
 * Displays labeled inputs for each nested item with Add / Remove buttons.
 */
const MasterNestedForm = ({ nestedData = {}, setNestedData }) => {
  if (!nestedData) return null;

  // Add a new empty row to a given nested key
  const handleAddRow = (key) => {
    setNestedData((prev) => ({
      ...prev,
      [key]: [...(prev[key] || []), {}],
    }));
  };

  // Remove a row by index
  const handleRemoveRow = (key, index) => {
    setNestedData((prev) => ({
      ...prev,
      [key]: prev[key].filter((_, i) => i !== index),
    }));
  };

  // Handle change in any nested field
  const handleChange = (key, index, field, value) => {
    setNestedData((prev) => {
      const updated = [...(prev[key] || [])];
      updated[index] = { ...updated[index], [field]: value };
      return { ...prev, [key]: updated };
    });
  };

  const hiddenFields = ["id", "created_on", "modified_on", "created_by", "modified_by"];

  return (
    <div className="nested-form-container">
      {Object.entries(nestedData).map(([key, items]) => (
        <div key={key} className="card border-0 shadow-sm mb-3">
          <div className="card-header bg-light d-flex justify-content-between align-items-center">
            <h6 className="fw-bold text-orange text-uppercase mb-0">
              {key
                .replace(/_/g, " ")
                .replace("norm", "Norm")
                .replace("export", "Export Norms")
                .replace("import", "Import Norms")}
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
              <p className="text-muted small">No entries yet.</p>
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
                  {Object.keys(item)
                    .filter((f) => !hiddenFields.includes(f))
                    .map((field) => (
                      <div key={field} className="col-md-4">
                        <Form.Group>
                          <Form.Label className="fw-medium text-secondary small">
                            {field.replace(/_/g, " ")}
                          </Form.Label>
                          <Form.Control
                            type="text"
                            value={item[field] || ""}
                            onChange={(e) =>
                              handleChange(key, index, field, e.target.value)
                            }
                          />
                        </Form.Group>
                      </div>
                    ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
};

export default MasterNestedForm;
