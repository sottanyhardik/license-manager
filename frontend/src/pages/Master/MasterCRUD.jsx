import React, { useCallback, useEffect, useState } from "react";
import api from "../../api/axios";
import MasterForm from "./components/MasterForm";
import MasterFilter from "./components/MasterFilter";
import MasterTable from "./components/MasterTable";

const PAGE_SIZE = 25;

const MasterCRUD = ({ endpoint, title }) => {
  const [schema, setSchema] = useState({});
  const [meta, setMeta] = useState({});
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState({});
  const [page, setPage] = useState(1);
  const [pageCount, setPageCount] = useState(1);
  const [editingRecord, setEditingRecord] = useState(null);
  const [showForm, setShowForm] = useState(false);

  // Robust schema fetch that tolerates several OPTIONS shapes
  const fetchSchema = useCallback(async () => {
    try {
      const res = await api.options(endpoint);
      const d = res.data || {};

      // Common places metadata may live
      const actionsPost = (d.actions && d.actions.POST) || {};
      const cfg = d.config || d.options || {};

      const listDisplay =
        d.list_display ||
        cfg.list_display ||
        d.list_display_fields ||
        actionsPost.list_display ||
        (Object.keys(actionsPost).length ? Object.keys(actionsPost) : Object.keys(d));

      const formFields =
        d.form_fields ||
        cfg.form_fields ||
        actionsPost.form_fields ||
        d.fields ||
        cfg.fields ||
        actionsPost.fields ||
        (Object.keys(actionsPost).length ? Object.keys(actionsPost) : Object.keys(d));

      const searchFields = d.search_fields || cfg.search_fields || actionsPost.search_fields || d.search || [];

      const filterFields =
        d.filter_fields ||
        cfg.filter_fields ||
        actionsPost.filter_fields ||
        (searchFields.length ? searchFields : listDisplay).slice(0, 6);

      // Read nested_field_defs (backend may expose 'nested_field_defs' or 'nestedFieldDefs')
      const nestedFieldDefs =
        d.nested_field_defs || d.nestedFieldDefs || cfg.nested_field_defs || cfg.nestedFieldDefs || {};

      const metaInfo = {
        listDisplay,
        formFields,
        searchFields,
        filterFields,
        nestedFieldDefs, // expose to forms
      };

      const schemaObj = Object.keys(actionsPost || {}).length
        ? actionsPost
        : cfg.schema || d.schema || d.fields || {};

      setSchema(schemaObj || {});
      setMeta(metaInfo);
    } catch (err) {
      console.error("Schema metadata load failed:", err);
      // safe fallback
      setSchema({});
      setMeta({
        listDisplay: [],
        formFields: [],
        searchFields: [],
        filterFields: [],
        nestedFieldDefs: {},
      });
    }
  }, [endpoint]);

  // fetch data with cancellation support
  const fetchData = useCallback(
    async (signal) => {
      setLoading(true);
      try {
        const params = { page, page_size: PAGE_SIZE, ...filters };
        const query = new URLSearchParams(params).toString();
        const res = await api.get(`${endpoint}?${query}`, { signal });
        const payload = res.data || {};

        if (payload.results) {
          setRecords(payload.results);
          const total = typeof payload.count === "number" ? payload.count : payload.results.length;
          setPageCount(Math.max(1, Math.ceil(total / PAGE_SIZE)));
        } else if (Array.isArray(payload)) {
          setRecords(payload);
          setPageCount(1);
        } else {
          // fallback if payload is an object with unknown shape
          setRecords(payload.results ?? []);
          setPageCount(1);
        }
      } catch (err) {
        if (err.name === "CanceledError" || err.name === "AbortError") {
          // intentionally aborted
        } else {
          console.error("Data fetch failed:", err);
        }
      } finally {
        setLoading(false);
      }
    },
    [endpoint, page, filters]
  );

  // load schema when endpoint changes
  useEffect(() => {
    if (!endpoint) return;
    fetchSchema();
    // reset UI state when endpoint changes
    setPage(1);
    setFilters({});
    setRecords([]);
    setEditingRecord(null);
    setShowForm(false);
  }, [endpoint, fetchSchema]);

  // fetch data when endpoint/page/filters change
  useEffect(() => {
    if (!endpoint) return;
    const controller = new AbortController();
    fetchData(controller.signal);
    return () => controller.abort();
  }, [endpoint, page, filters, fetchData]);

  const handleFilterChange = (f) => {
    setPage(1);
    setFilters(f || {});
  };

  const handleSave = async (formData, isEdit, nestedPayload = {}, fileFields = []) => {
    const form = new FormData();
    for (const key in formData) {
      const val = formData[key];
      if (val === undefined || val === null) continue;
      if (Array.isArray(val)) {
        val.forEach((v) => form.append(key, v));
      } else {
        form.append(key, val);
      }
    }

    // append nested payload: flatten object keys (arrays) into form fields
    for (const nKey in nestedPayload) {
      const arr = nestedPayload[nKey] || [];
      arr.forEach((item, idx) => {
        // bracket notation commonly parsed by backends: nestedKey[index][field]
        for (const k in item) {
          const keyName = `${nKey}[${idx}][${k}]`;
          const v = item[k];
          if (v === undefined || v === null) continue;
          form.append(keyName, v);
        }
      });
    }

    try {
      if (isEdit) {
        const id = formData.id;
        await api.put(`${endpoint}${id}/`, form);
      } else {
        await api.post(endpoint, form);
      }
      setShowForm(false);
      setEditingRecord(null);
      setPage(1);
      const controller = new AbortController();
      await fetchData(controller.signal);
    } catch (err) {
      console.error("Save failed:", err.response?.data || err);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Are you sure you want to delete this record?")) return;
    try {
      await api.delete(`${endpoint}${id}/`);
      const controller = new AbortController();
      await fetchData(controller.signal);
    } catch (err) {
      console.error("Delete failed:", err.response?.data || err);
    }
  };

  return (
    <div className="container py-4">
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h3 className="fw-semibold text-secondary">{title}</h3>
        <button
          className="btn btn-success"
          onClick={() => {
            setShowForm((s) => !s);
            setEditingRecord(null);
          }}
        >
          {showForm ? "Close" : "➕ Add New"}
        </button>
      </div>

      {!showForm && (
        <>
          <MasterFilter schema={schema} meta={meta} onFilterChange={handleFilterChange} />
          <MasterTable
            schema={schema}
            meta={meta}
            records={records}
            loading={loading}
            page={page}
            pageCount={pageCount}
            setPage={setPage}
            onEdit={(r) => {
              setEditingRecord(r);
              setShowForm(true);
            }}
            onDelete={handleDelete}
          />
        </>
      )}

      {showForm && (
        <MasterForm
          schema={schema}
          meta={meta}
          record={editingRecord}
          onSave={handleSave}
          onCancel={() => {
            setShowForm(false);
            setEditingRecord(null);
          }}
        />
      )}
    </div>
  );
};

export default MasterCRUD;
