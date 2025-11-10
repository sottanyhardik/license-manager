// src/components/master/MasterCRUD.jsx
import React, {useCallback, useEffect, useMemo, useState} from "react";
import PropTypes from "prop-types";
import api from "../../api/axios";
import MasterForm from "./components/MasterForm";
import MasterFilter from "./components/MasterFilter";
import MasterTable from "./components/MasterTable";

const PAGE_SIZE = 25;

const MasterCRUD = ({endpoint, title}) => {
    const [schema, setSchema] = useState({});
    const [meta, setMeta] = useState({});
    const [records, setRecords] = useState([]);
    const [loading, setLoading] = useState(false);
    const [filters, setFilters] = useState({});
    const [page, setPage] = useState(1);
    const [pageCount, setPageCount] = useState(1);
    const [editingRecord, setEditingRecord] = useState(null);
    const [showForm, setShowForm] = useState(false);
    const [saving, setSaving] = useState(false);

    // --- File field helper ---
    const fileFields = useMemo(() => {
        if (!schema || typeof schema !== "object") return [];
        return Object.entries(schema)
            .filter(([, cfg]) => cfg && (cfg.type === "file" || cfg.type === "image"))
            .map(([k]) => k);
    }, [schema]);

    // --- Fetch schema / options ---
    const fetchSchema = useCallback(async () => {
        if (!endpoint) return;
        try {
            const res = await api.options(endpoint);
            const d = res.data || {};

            const nestedFieldDefs =
                d.nested_field_defs || d.nestedFieldDefs || d.config?.nested_field_defs || d.config?.nestedFieldDefs || {};

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

            const metaInfo = {
                listDisplay,
                formFields,
                searchFields,
                filterFields,
                nestedFieldDefs,
                rawOptions: d,
                field_meta: d.field_meta || d.config?.field_meta || {},
                fieldMeta: d.field_meta || d.config?.field_meta || {},
            };

            const schemaObj = Object.keys(actionsPost || {}).length
                ? actionsPost
                : cfg.schema || d.schema || d.fields || {};

            setSchema(schemaObj || {});
            setMeta(metaInfo);
        } catch (err) {
            console.error("⚠️ Schema metadata load failed:", err);
            setSchema({});
            setMeta({
                listDisplay: [],
                formFields: [],
                searchFields: [],
                filterFields: [],
                nestedFieldDefs: {},
                field_meta: {},
            });
        }
    }, [endpoint]);

    // --- Fetch data (paginated) ---
    const fetchData = useCallback(
        async (signal) => {
            if (!endpoint) return;
            setLoading(true);
            try {
                const params = {page, page_size: PAGE_SIZE, ...filters};
                const query = new URLSearchParams(params).toString();
                const res = await api.get(`${endpoint}?${query}`, {signal});
                const payload = res.data ?? {};

                if (payload.results) {
                    setRecords(payload.results);
                    const total = typeof payload.count === "number" ? payload.count : payload.results.length;
                    setPageCount(Math.max(1, Math.ceil(total / PAGE_SIZE)));
                } else if (Array.isArray(payload)) {
                    setRecords(payload);
                    setPageCount(1);
                } else {
                    setRecords(payload.results ?? []);
                    setPageCount(1);
                }
            } catch (err) {
                if (err.name !== "CanceledError" && err.name !== "AbortError") {
                    console.error("⚠️ Data fetch failed:", err);
                }
            } finally {
                setLoading(false);
            }
        },
        [endpoint, page, filters]
    );

    // --- Lifecycle: initial load and refetches ---
    useEffect(() => {
        if (!endpoint) return;
        fetchSchema();
        setPage(1);
        setFilters({});
        setRecords([]);
        setEditingRecord(null);
        setShowForm(false);
    }, [endpoint, fetchSchema]);

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

    // --- Helpers for submission ---
    /**
     * appendNestedToFormData
     * - Appends nested arrays in bracketed notation: section[idx][field]
     * - Always append an `id` key for nested rows (even if id === null/""), so backend sees the key.
     * - For id values that are null/undefined/empty -> append empty string ("") (so key exists).
     * - For other keys: skip undefined/null to avoid sending noise.
     * - Coerces primitives to proper strings for FormData append.
     */
    const appendNestedToFormData = (fd, nestedPayload) => {
        Object.entries(nestedPayload || {}).forEach(([section, arr]) => {
            (arr || []).forEach((item, idx) => {
                Object.entries(item || {}).forEach(([k, v]) => {
                    const keyName = `${section}[${idx}][${k}]`;
                    // Always include id keys (even if null/empty)
                    if (k === "id") {
                        if (v === undefined || v === null || v === "") {
                            fd.append(keyName, "");
                        } else {
                            fd.append(keyName, String(v));
                        }
                        return;
                    }

                    // For other fields: skip undefined/null
                    if (v === undefined || v === null) return;

                    // Files
                    if (v instanceof File || v instanceof Blob) {
                        fd.append(keyName, v);
                        return;
                    }

                    // primitives -> string
                    if (typeof v === "object") {
                        fd.append(keyName, JSON.stringify(v));
                    } else {
                        fd.append(keyName, String(v));
                    }
                });
            });
        });
    };

    /**
     * coerceValue
     * - Try to coerce a value according to meta.field_meta or nestedFieldDefs.
     * - Returns the coerced value (number, boolean, null, or original).
     */
    const coerceValue = (fieldName, value, section = null) => {
        // undefined or null -> return as-is (caller may later drop)
        if (value === undefined || value === null) return value;

        // first check nested field defs if section provided
        if (section && meta?.nestedFieldDefs && meta.nestedFieldDefs[section]) {
            const defs = meta.nestedFieldDefs[section] || [];
            const def = defs.find((d) => d.name === fieldName);
            if (def && def.type) {
                const t = String(def.type).toLowerCase();
                if ((t === "number" || t === "integer") && typeof value === "string") {
                    const n = Number(value);
                    if (!Number.isNaN(n)) return n;
                }
                if (t === "boolean" && typeof value === "string") {
                    const lower = value.trim().toLowerCase();
                    if (lower === "true") return true;
                    if (lower === "false") return false;
                }
                return value;
            }
        }

        // fallback to meta.field_meta for top-level
        const fm = meta?.field_meta || meta?.fieldMeta || {};
        const entry = fm[fieldName] || fm[fieldName.replace(/_date$/, "")] || null;
        if (entry && entry.type) {
            const t = String(entry.type).toLowerCase();
            if ((t === "number" || t === "integer") && typeof value === "string") {
                const n = Number(value);
                if (!Number.isNaN(n)) return n;
            }
            if (t === "boolean" && typeof value === "string") {
                const lower = value.trim().toLowerCase();
                if (lower === "true") return true;
                if (lower === "false") return false;
            }
        }

        // numeric-looking strings for id fields: leave to caller to normalize
        return value;
    };

    /**
     * buildJsonPayload
     * - Merge top-level and nested payload for JSON path.
     * - Normalize nested item ids: convert empty-string ids ("") to null explicitly.
     * - Preserve numeric ids as-is.
     * - Coerce types for numeric/boolean fields using meta.
     */
    const buildJsonPayload = (formDataObj, nestedPayload) => {
        // shallow copy top-level fields
        const out = {...formDataObj};

        // coerce top-level fields according to meta.field_meta when possible
        Object.keys(out).forEach((k) => {
            // skip files or complex objects handled separately
            const v = out[k];
            if (v === undefined) return;
            if (v === null) {
                out[k] = null;
                return;
            }
            // don't convert objects (except primitive wrappers)
            if (typeof v === "object" && !(v instanceof Date) && !(v instanceof String)) return;

            out[k] = coerceValue(k, v, null);
        });

        // deep-ish clone nested payload and normalize ids and coerce nested field types
        Object.entries(nestedPayload || {}).forEach(([section, arr]) => {
            out[section] = (arr || []).map((item) => {
                if (!item || typeof item !== "object") return item;
                const copy = {...item};
                // normalize id: "" -> null; numeric string -> number
                if ("id" in copy) {
                    if (copy.id === "" || copy.id === undefined) {
                        copy.id = null;
                    } else if (typeof copy.id === "string") {
                        const num = Number(copy.id);
                        copy.id = !Number.isNaN(num) ? num : copy.id;
                    }
                }
                // coerce other fields using nestedFieldDefs or field_meta when available
                Object.keys(copy).forEach((fld) => {
                    if (fld === "id") return;
                    const val = copy[fld];
                    if (val === undefined || val === null) return;
                    // Files / objects remain as-is (server may expect id or nested objects)
                    if (val instanceof File || typeof val === "object") return;
                    copy[fld] = coerceValue(fld, val, section);
                });
                return copy;
            });
        });

        return out;
    };

    // --- Save handler (called by MasterForm) ---
    const handleSave = async (formDataObj, isEdit, nestedPayload = {}, fileFieldsFromForm = []) => {
        setSaving(true);
        try {
            // 1️⃣ Clean payload for preview (for debugging, not mutated)
            const previewPayload = buildJsonPayload(formDataObj, nestedPayload);

            console.groupCollapsed(
                `%c🧾 MasterCRUD: Submitting ${isEdit ? "UPDATE" : "CREATE"} payload`,
                "color: #1976d2; font-weight: bold;"
            );
            console.log("➡️ Endpoint:", endpoint);
            console.log("FormData (raw):", formDataObj);
            console.log("Nested Payload:", nestedPayload);
            console.log("Merged Payload:", previewPayload);
            console.groupEnd();

            // 2️⃣ Determine upload type
            const shouldUseFormData =
                Array.isArray(fileFieldsFromForm) &&
                fileFieldsFromForm.some((ff) => {
                    const v = formDataObj?.[ff];
                    return v instanceof File || v instanceof Blob;
                });

            // 3️⃣ Submit
            if (shouldUseFormData) {
                const fd = new FormData();

                // Add top-level fields
                Object.entries(formDataObj || {}).forEach(([k, v]) => {
                    if (v === undefined || v === null) return;
                    if (fileFieldsFromForm.includes(k)) return; // handled below
                    if (v instanceof File || v instanceof Blob) {
                        fd.append(k, v);
                        return;
                    }
                    if (typeof v === "object") {
                        fd.append(k, JSON.stringify(v));
                    } else {
                        fd.append(k, String(v));
                    }
                });

                // Files
                fileFieldsFromForm.forEach((ff) => {
                    const f = formDataObj[ff];
                    if (f instanceof File || f instanceof Blob) fd.append(ff, f);
                });

                // Nested arrays (always include id keys even if blank)
                appendNestedToFormData(fd, nestedPayload);

                if (isEdit) {
                    const id = formDataObj.id;
                    console.log("🔄 PUT multipart/form-data for id:", id);
                    await api.put(`${endpoint}${id}/`, fd);
                } else {
                    console.log("🆕 POST multipart/form-data");
                    await api.post(endpoint, fd);
                }
            } else {
                // JSON payload
                const payload = buildJsonPayload(formDataObj, nestedPayload);

                // 🧩 Log payload before sending
                console.groupCollapsed("%c📦 JSON Payload Preview", "color:#009688;font-weight:bold");
                console.log(JSON.stringify(payload, null, 2));
                console.groupEnd();

                if (isEdit) {
                    const id = formDataObj.id;
                    console.log("🔄 PUT JSON for id:", id);
                    await api.put(`${endpoint}${id}/`, payload);
                } else {
                    console.log("🆕 POST JSON");
                    await api.post(endpoint, payload);
                }
            }

            // ✅ Refresh data after saving
            setShowForm(false);
            setEditingRecord(null);
            setPage(1);
            const controller = new AbortController();
            await fetchData(controller.signal);
        } catch (err) {
            console.error("❌ Save failed:", err?.response?.data ?? err);
            throw err;
        } finally {
            setSaving(false);
        }
    };

    // --- Delete handler ---
    const handleDelete = async (id) => {
        if (!window.confirm("Are you sure you want to delete this record?")) return;
        try {
            await api.delete(`${endpoint}${id}/`);
            const controller = new AbortController();
            await fetchData(controller.signal);
        } catch (err) {
            console.error("Delete failed:", err?.response?.data ?? err);
        }
    };

    // --- Render ---
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
                    <MasterFilter schema={schema} meta={meta} onFilterChange={handleFilterChange}/>
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
                <div className="card mb-4">
                    <div className="card-body">
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
                        {saving && <div className="mt-2 text-muted small">Saving…</div>}
                    </div>
                </div>
            )}
        </div>
    );
};

MasterCRUD.propTypes = {
    endpoint: PropTypes.string.isRequired,
    title: PropTypes.string,
};

MasterCRUD.defaultProps = {
    title: "Master CRUD",
};

export default MasterCRUD;
