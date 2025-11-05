import React, { useEffect, useState, useContext } from "react";
import { Table, Button, Modal, Form, Pagination, Spinner } from "react-bootstrap";
import api from "../api/axios";
import { ToastContext } from "../context/ToastContext";

const MasterCRUD = ({ title, endpoint, fields }) => {
  const { showToast } = useContext(ToastContext);
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(false);
  const [show, setShow] = useState(false);
  const [formData, setFormData] = useState({});
  const [editingId, setEditingId] = useState(null);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);

  const fetchData = async () => {
    setLoading(true);
    try {
      const res = await api.get(`${endpoint}?page=${page}&search=${search}`);
      setRecords(res.data.results || res.data);
      if (res.data.count) setTotalPages(Math.ceil(res.data.count / 25));
    } catch (err) {
      showToast("Failed to fetch data", "danger");
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchData();
  }, [page, search]);

  const handleChange = (e) =>
    setFormData({ ...formData, [e.target.name]: e.target.value });

  const handleSave = async () => {
    try {
      if (editingId) {
        await api.put(`${endpoint}${editingId}/`, formData);
        showToast("Record updated successfully!", "success");
      } else {
        await api.post(endpoint, formData);
        showToast("Record created successfully!", "success");
      }
      setShow(false);
      setEditingId(null);
      setFormData({});
      fetchData();
    } catch {
      showToast("Error saving data", "danger");
    }
  };

  const handleEdit = (record) => {
    setFormData(record);
    setEditingId(record.id);
    setShow(true);
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Are you sure you want to delete this record?")) return;
    try {
      await api.delete(`${endpoint}${id}/`);
      showToast("Deleted successfully!", "success");
      fetchData();
    } catch {
      showToast("Error deleting record", "danger");
    }
  };

    const renderPagination = () => {
    if (totalPages <= 1) return null;

    const maxPagesToShow = 5;
    let startPage = Math.max(1, page - Math.floor(maxPagesToShow / 2));
    let endPage = startPage + maxPagesToShow - 1;

    if (endPage > totalPages) {
      endPage = totalPages;
      startPage = Math.max(1, endPage - maxPagesToShow + 1);
    }

    const pages = [];
    for (let i = startPage; i <= endPage; i++) {
      pages.push(
        <Pagination.Item
          key={i}
          active={i === page}
          onClick={() => setPage(i)}
        >
          {i}
        </Pagination.Item>
      );
    }

    return (
      <div className="d-flex justify-content-center mt-3">
        <Pagination className="shadow-sm">
          <Pagination.Prev
            onClick={() => setPage((prev) => Math.max(1, prev - 1))}
            disabled={page === 1}
          />
          {startPage > 1 && (
            <>
              <Pagination.Item onClick={() => setPage(1)}>1</Pagination.Item>
              {startPage > 2 && <Pagination.Ellipsis disabled />}
            </>
          )}

          {pages}

          {endPage < totalPages && (
            <>
              {endPage < totalPages - 1 && <Pagination.Ellipsis disabled />}
              <Pagination.Item onClick={() => setPage(totalPages)}>
                {totalPages}
              </Pagination.Item>
            </>
          )}

          <Pagination.Next
            onClick={() => setPage((prev) => Math.min(totalPages, prev + 1))}
            disabled={page === totalPages}
          />
        </Pagination>
      </div>
    );
  };

  return (
    <div className="p-4 bg-white shadow-sm rounded">
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h5 className="fw-bold">{title}</h5>
        <Button className="btn-orange" onClick={() => setShow(true)}>
          + Add New
        </Button>
      </div>

      <Form.Control
        type="text"
        placeholder="Search..."
        className="mb-3"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
      />

      {loading ? (
        <div className="text-center py-5">
          <Spinner animation="border" variant="warning" />
        </div>
      ) : (
        <Table striped hover responsive>
          <thead>
            <tr>
              {fields.map((f) => (
                <th key={f.name}>{f.label}</th>
              ))}
              <th>Actions</th>
            </tr>
          </thead>
          <tbody>
            {records.length === 0 ? (
              <tr>
                <td colSpan={fields.length + 1} className="text-center text-muted">
                  No records found.
                </td>
              </tr>
            ) : (
              records.map((r) => (
                <tr key={r.id}>
                  {fields.map((f) => (
                    <td key={f.name}>{r[f.name]}</td>
                  ))}
                  <td>
                    <Button variant="outline-secondary" size="sm" onClick={() => handleEdit(r)}>
                      <i className="bi bi-pencil"></i>
                    </Button>{" "}
                    <Button variant="outline-danger" size="sm" onClick={() => handleDelete(r.id)}>
                      <i className="bi bi-trash"></i>
                    </Button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </Table>
      )}

      {renderPagination()}

      {/* Modal */}
      <Modal show={show} onHide={() => setShow(false)} centered>
        <Modal.Header closeButton>
          <Modal.Title>{editingId ? "Edit Record" : "Add New Record"}</Modal.Title>
        </Modal.Header>
        <Modal.Body>
          {fields.map((f) => (
            <Form.Group className="mb-3" key={f.name}>
              <Form.Label>{f.label}</Form.Label>
              <Form.Control
                type={f.type || "text"}
                name={f.name}
                value={formData[f.name] || ""}
                onChange={handleChange}
                required={f.required}
              />
            </Form.Group>
          ))}
        </Modal.Body>
        <Modal.Footer>
          <Button variant="secondary" onClick={() => setShow(false)}>
            Cancel
          </Button>
          <Button className="btn-orange" onClick={handleSave}>
            Save
          </Button>
        </Modal.Footer>
      </Modal>
    </div>
  );
};

export default MasterCRUD;