import React, { useEffect, useState, useContext } from "react";
import { Card, Button, Form, Table, Spinner } from "react-bootstrap";
import api from "../../api/axios";
import { ToastContext } from "../../context/ToastContext";
import { debounce } from "../../utils/debounce";

const SionNorms = () => {
  const { showToast } = useContext(ToastContext);
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(false);

  // Dropdown and autocomplete options
  const [headNorms, setHeadNorms] = useState([]);
  const [hsnOptions, setHsnOptions] = useState([]);

  // Form state
  const [formData, setFormData] = useState({
    head_norm: "",
    head_norm_name: "",
    norm_class: "",
    description: "",
    export_norm: [],
    import_norm: [],
  });
  const [editingId, setEditingId] = useState(null);
  const [showForm, setShowForm] = useState(false);

  // Fetch all SION norms
  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await api.get("masters/sion-classes/");
      setRecords(res.data.results || res.data);
    } catch {
      showToast("Failed to fetch SION norms", "danger");
    }
    setLoading(false);
  };

  // Fetch Head Norm choices
  const fetchHeadNorms = async () => {
    try {
      const res = await api.get("masters/head-sion-norms/");
      setHeadNorms(res.data.results || res.data);
    } catch {
      showToast("Failed to load Head Norms", "danger");
    }
  };

  // Debounced HSN code search
  const fetchHsnCodes = debounce(async (query) => {
    if (!query) return setHsnOptions([]);
    try {
      const res = await api.get(`masters/hs-codes/?search=${query}`);
      setHsnOptions(res.data.results || res.data);
    } catch {
      setHsnOptions([]);
    }
  }, 400);

  useEffect(() => {
    fetchData();
    fetchHeadNorms();
  }, []);

  // Handle form field changes
  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData({ ...formData, [name]: value });

    if (name === "head_norm") {
      const selected = headNorms.find((h) => h.id.toString() === value);
      setFormData({
        ...formData,
        head_norm: value,
        head_norm_name: selected ? selected.name : "",
      });
    }
  };

  const addExportRow = () =>
    setFormData({
      ...formData,
      export_norm: [
        ...formData.export_norm,
        { description: "", quantity: "", unit: "" },
      ],
    });

  const addImportRow = () =>
    setFormData({
      ...formData,
      import_norm: [
        ...formData.import_norm,
        { description: "", quantity: "", unit: "", hsn_code: "", hsn_code_label: "" },
      ],
    });

  const handleNestedChange = (type, index, field, value) => {
    const updated = [...formData[type]];
    updated[index][field] = value;
    setFormData({ ...formData, [type]: updated });
  };

  const removeRow = (type, index) => {
    const updated = [...formData[type]];
    updated.splice(index, 1);
    setFormData({ ...formData, [type]: updated });
  };

  const handleSave = async () => {
    try {
      const payload = {
        ...formData,
        head_norm: Number(formData.head_norm),
        import_norm: formData.import_norm.map((i) => ({
          ...i,
          hsn_code: i.hsn_code ? Number(i.hsn_code) : null,
        })),
      };

      if (editingId) {
        await api.put(`masters/sion-classes/${editingId}/`, payload);
        showToast("SION Norm updated!", "success");
      } else {
        await api.post("masters/sion-classes/", payload);
        showToast("SION Norm created!", "success");
      }
      fetchData();
      setShowForm(false);
      setEditingId(null);
      setFormData({
        head_norm: "",
        head_norm_name: "",
        norm_class: "",
        description: "",
        export_norm: [],
        import_norm: [],
      });
    } catch {
      showToast("Error saving data", "danger");
    }
  };

  const handleEdit = (record) => {
    setFormData({
      ...record,
      head_norm: record.head_norm,
      head_norm_name: record.head_norm_name || "",
    });
    setEditingId(record.id);
    setShowForm(true);
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this SION Norm?")) return;
    try {
      await api.delete(`masters/sion-classes/${id}/`);
      showToast("Deleted successfully!", "success");
      fetchData();
    } catch {
      showToast("Error deleting record", "danger");
    }
  };

  // UI
  if (loading)
    return (
      <div className="text-center py-5">
        <Spinner animation="border" variant="warning" />
      </div>
    );

  return (
    <div className="p-4 bg-white shadow-sm rounded">
      <div className="d-flex justify-content-between mb-3">
        <h5 className="fw-bold">SION Norms</h5>
        <Button className="btn-orange" onClick={() => setShowForm(!showForm)}>
          {showForm ? "Close Form" : "+ Add New"}
        </Button>
      </div>

      {showForm && (
        <Card className="mb-4 border-0 shadow-sm">
          <Card.Body>
            <Form>
              <Form.Group className="mb-3">
                <Form.Label>Head Norm</Form.Label>
                <Form.Select
                  name="head_norm"
                  value={formData.head_norm}
                  onChange={handleChange}
                  required
                >
                  <option value="">-- Select Head Norm --</option>
                  {headNorms.map((h) => (
                    <option key={h.id} value={h.id}>
                      {h.name}
                    </option>
                  ))}
                </Form.Select>
              </Form.Group>

              <Form.Group className="mb-3">
                <Form.Label>Norm Class</Form.Label>
                <Form.Control
                  name="norm_class"
                  value={formData.norm_class}
                  onChange={handleChange}
                  required
                />
              </Form.Group>

              <Form.Group className="mb-3">
                <Form.Label>Description</Form.Label>
                <Form.Control
                  as="textarea"
                  name="description"
                  value={formData.description}
                  onChange={handleChange}
                />
              </Form.Group>

              {/* EXPORT FORMSET */}
              <h6 className="mt-4">Export Norms</h6>
              <Table bordered size="sm">
                <thead>
                  <tr>
                    <th>Description</th>
                    <th>Quantity</th>
                    <th>Unit</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {formData.export_norm.map((row, i) => (
                    <tr key={i}>
                      <td>
                        <Form.Control
                          value={row.description}
                          onChange={(e) =>
                            handleNestedChange(
                              "export_norm",
                              i,
                              "description",
                              e.target.value
                            )
                          }
                        />
                      </td>
                      <td>
                        <Form.Control
                          type="number"
                          value={row.quantity}
                          onChange={(e) =>
                            handleNestedChange(
                              "export_norm",
                              i,
                              "quantity",
                              e.target.value
                            )
                          }
                        />
                      </td>
                      <td>
                        <Form.Control
                          value={row.unit}
                          onChange={(e) =>
                            handleNestedChange(
                              "export_norm",
                              i,
                              "unit",
                              e.target.value
                            )
                          }
                        />
                      </td>
                      <td>
                        <Button
                          variant="outline-danger"
                          size="sm"
                          onClick={() => removeRow("export_norm", i)}
                        >
                          <i className="bi bi-trash"></i>
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <Button variant="outline-primary" size="sm" onClick={addExportRow}>
                + Add Export
              </Button>

              {/* IMPORT FORMSET */}
              <h6 className="mt-4">Import Norms</h6>
              <Table bordered size="sm">
                <thead>
                  <tr>
                    <th>Description</th>
                    <th>Quantity</th>
                    <th>Unit</th>
                    <th>HSN Code</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {formData.import_norm.map((row, i) => (
                    <tr key={i}>
                      <td>
                        <Form.Control
                          value={row.description}
                          onChange={(e) =>
                            handleNestedChange(
                              "import_norm",
                              i,
                              "description",
                              e.target.value
                            )
                          }
                        />
                      </td>
                      <td>
                        <Form.Control
                          type="number"
                          value={row.quantity}
                          onChange={(e) =>
                            handleNestedChange(
                              "import_norm",
                              i,
                              "quantity",
                              e.target.value
                            )
                          }
                        />
                      </td>
                      <td>
                        <Form.Control
                          value={row.unit}
                          onChange={(e) =>
                            handleNestedChange(
                              "import_norm",
                              i,
                              "unit",
                              e.target.value
                            )
                          }
                        />
                      </td>
                      <td>
                        <Form.Control
                          list={`hsn-options-${i}`}
                          value={row.hsn_code_label || ""}
                          onChange={(e) => {
                            handleNestedChange(
                              "import_norm",
                              i,
                              "hsn_code_label",
                              e.target.value
                            );
                            fetchHsnCodes(e.target.value);
                          }}
                          placeholder="Search HSN Code..."
                        />
                        <datalist id={`hsn-options-${i}`}>
                          {hsnOptions.map((opt) => (
                            <option
                              key={opt.id}
                              value={`${opt.hs_code} — ${opt.product_description}`}
                              onClick={() =>
                                handleNestedChange(
                                  "import_norm",
                                  i,
                                  "hsn_code",
                                  opt.id
                                )
                              }
                            />
                          ))}
                        </datalist>
                      </td>
                      <td>
                        <Button
                          variant="outline-danger"
                          size="sm"
                          onClick={() => removeRow("import_norm", i)}
                        >
                          <i className="bi bi-trash"></i>
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              <Button variant="outline-primary" size="sm" onClick={addImportRow}>
                + Add Import
              </Button>

              <div className="mt-4 text-end">
                <Button variant="secondary" onClick={() => setShowForm(false)}>
                  Cancel
                </Button>{" "}
                <Button className="btn-orange" onClick={handleSave}>
                  Save
                </Button>
              </div>
            </Form>
          </Card.Body>
        </Card>
      )}

      {/* LIST VIEW */}
      <Table striped bordered hover responsive>
        <thead>
          <tr>
            <th>Norm Class</th>
            <th>Description</th>
            <th>Head Norm</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {records.map((r) => (
            <tr key={r.id}>
              <td>{r.norm_class}</td>
              <td>{r.description}</td>
              <td>{r.head_norm_name || r.head_norm}</td>
              <td>
                <Button
                  variant="outline-secondary"
                  size="sm"
                  onClick={() => handleEdit(r)}
                >
                  <i className="bi bi-pencil"></i>
                </Button>{" "}
                <Button
                  variant="outline-danger"
                  size="sm"
                  onClick={() => handleDelete(r.id)}
                >
                  <i className="bi bi-trash"></i>
                </Button>
              </td>
            </tr>
          ))}
        </tbody>
      </Table>
    </div>
  );
};

export default SionNorms;
