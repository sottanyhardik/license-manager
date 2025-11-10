// File: src/components/master/components/MasterForm.jsx
import React, {useEffect, useRef, useState} from "react";
import MasterNestedForm from "./MasterNestedForm";
import FieldRenderer from "./FieldRenderer";
import {getDisplayLabel} from "../../../utils";
import {debounce} from "../../../utils/debounce";
import api from "../../../api/axios";

const hiddenFields = ["id", "created_on", "modified_on", "created_by", "modified_by"];

/**
 * MasterForm
 * - Full form renderer for model forms.
 * - Autocomplete for both `choices` and FK endpoints.
 * - Delegates save to onSave(formData, isEdit, nestedPayload, fileFields).
 */
const MasterForm = ({schema = {}, meta = {}, record = {}, onSave, onCancel}) => {
    // file inputs
    const fileFields = Object.entries(schema || {})
        .filter(([, cfg]) => cfg && (cfg.type === "file" || cfg.type === "image"))
        .map(([k]) => k);

    const normalizeRecord = (rec) => {
        if (!rec) return {};
        const out = {...rec};
        Object.keys(rec).forEach((k) => {
            const v = rec[k];
            if (v && typeof v === "object" && "id" in v) out[k] = v.id;
        });
        return out;
    };

    const [formData, setFormData] = useState(normalizeRecord(record));
    const [nestedData, setNestedData] = useState({});
    const [fkOptions, setFkOptions] = useState({}); // options for fields (remote or client-side)
    const [searchTerm, setSearchTerm] = useState({}); // display text per field
    const [loadingField, setLoadingField] = useState(null);
    const [activeField, setActiveField] = useState(null); // which dropdown is open
    const blurTimeoutRef = useRef(null);

    const originalRecordRef = useRef(record);
    useEffect(() => {
        originalRecordRef.current = record;
    }, [record]);

    // fk metadata helpers
    const fkMeta = meta?.field_meta || meta?.fieldMeta || {};
    const fkEndpoints = {};
    Object.entries(fkMeta || {}).forEach(([k, v]) => {
        if (v && (v.endpoint || v.fk_endpoint)) fkEndpoints[k] = v.endpoint || v.fk_endpoint;
    });

    // initialize nestedData + formData + display labels
    useEffect(() => {
        const normalized = normalizeRecord(record);
        const nd = {};
        if (record) {
            Object.keys(record).forEach((k) => {
                if (Array.isArray(record[k])) {
                    nd[k] = (record[k] || []).map((it) => (it && typeof it === "object" ? {...it} : it));
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
                if (v && typeof v === "object") st[k] = getDisplayLabel(v) || `${v.id}`;
            });
            setSearchTerm((prev) => ({...prev, ...st}));
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [record, meta]);

    // --- Remote FK search (debounced) ---
    const searchForeignKey = useRef(
        debounce(async (field, query) => {
            const metaEntry = fkMeta[field];
            const endpointForField = (metaEntry && (metaEntry.endpoint || metaEntry.fk_endpoint)) || fkEndpoints[field];
            if (!endpointForField) return [];
            setLoadingField(field);
            try {
                const res = await api.get(`${endpointForField}?search=${encodeURIComponent(query)}`);
                const results = res.data?.results ?? res.data ?? [];
                setFkOptions((prev) => ({...prev, [field]: results}));
                setLoadingField(null);
                return results;
            } catch (err) {
                console.warn(`Search failed for ${field}:`, err);
                setFkOptions((prev) => ({...prev, [field]: []}));
                setLoadingField(null);
                return [];
            }
        }, 300)
    ).current;

    // fetch single object to resolve label when formData[field] is an id
    const fetchSingle_fk = async (field, id) => {
        if (id === undefined || id === null || id === "") return;
        const metaEntry = fkMeta[field];
        const endpointForField = (metaEntry && (metaEntry.endpoint || metaEntry.fk_endpoint)) || fkEndpoints[field];
        if (!endpointForField) return;
        try {
            const res = await api.get(`${endpointForField}${id}/`);
            const obj = res.data;
            setFkOptions((prev) => ({...prev, [field]: [obj]}));
            setSearchTerm((prev) => ({...prev, [field]: getDisplayLabel(obj) || String(obj.id)}));
        } catch (err) {
            // silent
        }
    };

    // whenever formData loads with fk ids, fetch their labels
    useEffect(() => {
        Object.entries(formData || {}).forEach(([k, v]) => {
            const metaEntry = fkMeta[k];
            const endpointForField = (metaEntry && (metaEntry.endpoint || metaEntry.fk_endpoint)) || fkEndpoints[k];
            if (!endpointForField) return;
            if (v && typeof v !== "object") fetchSingle_fk(k, v);
        });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [formData, fkMeta]);

    useEffect(() => {
        return () => {
            if (blurTimeoutRef.current) clearTimeout(blurTimeoutRef.current);
        };
    }, []);

    const handleChange = (e) => {
        const {name, type, files, value, checked} = e.target;
        setFormData((prev) => ({
            ...prev,
            [name]: type === "file" ? (files[0] || null) : type === "checkbox" ? checked : value,
        }));
    };

    // prepare nested data for submit (convert FK objects to ids)
    const prepareNestedNormalized = (nestedDataObj) => {
        const out = {};
        Object.entries(nestedDataObj || {}).forEach(([k, arr]) => {
            out[k] = (arr || []).map((item) => {
                const copy = {...(item || {})};
                Object.keys(copy).forEach((f) => {
                    const val = copy[f];
                    if (val && typeof val === "object" && ("id" in val || "pk" in val)) {
                        copy[f] = val.id ?? val.pk;
                    }
                });
                if (copy.id === undefined && item && (item.id || item.pk)) copy.id = item.id ?? item.pk;
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

        if (typeof onSave === "function") onSave(formData, !!formData.id, normalizedNested, fileFields);
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

    // Helpers: normalize choices -> [{value,label}]
    const normalizeChoices = (choices) => {
        if (!Array.isArray(choices)) return [];
        return choices.map((c) => (Array.isArray(c) ? {
            value: c[0],
            label: c[1]
        } : typeof c === "object" ? {value: c.value, label: c.label} : {value: c, label: c}));
    };

    /**
     * getFieldChoices
     * - Look for choices in several places:
     *   1. explicit config.choices (schema[field].choices)
     *   2. meta.rawOptions.actions.POST[field].choices (DRF OPTIONS actions POST metadata)
     *   3. meta.field_meta choices entry
     *
     * Returns normalized array: [{ value, label }, ...]
     */
    const getFieldChoices = (field, config = {}) => {
        // explicit config choices first
        if (config && Array.isArray(config.choices) && config.choices.length) {
            return normalizeChoices(config.choices);
        }

        // schema-level choices
        if (schema[field] && Array.isArray(schema[field].choices) && schema[field].choices.length) {
            return normalizeChoices(schema[field].choices);
        }

        // DRF OPTIONS actions -> POST -> field -> choices
        const raw = meta?.rawOptions || meta?.raw_options || meta?.raw || meta?.options || {};
        const actionsPost =
            (raw.actions && (raw.actions.POST || raw.actions.post)) || raw.actions || raw;
        if (actionsPost && actionsPost[field] && Array.isArray(actionsPost[field].choices)) {
            return normalizeChoices(actionsPost[field].choices);
        }

        // fields.<field>.choices
        if (raw.fields && raw.fields[field] && Array.isArray(raw.fields[field].choices)) {
            return normalizeChoices(raw.fields[field].choices);
        }

        // raw[field].choices fallback
        if (raw[field] && Array.isArray(raw[field].choices)) {
            return normalizeChoices(raw[field].choices);
        }

        // fallback to meta.field_meta config
        const fm = meta?.field_meta || meta?.fieldMeta || {};
        if (fm[field] && Array.isArray(fm[field].choices) && fm[field].choices.length) {
            return normalizeChoices(fm[field].choices);
        }

        return [];
    };

    // render helper using FieldRenderer
    const renderField = (field) => {
        const config = schema[field] || {label: field, type: "text"};
        if (hiddenFields.includes(field)) return null;
        if (
            Array.isArray(nestedData[field]) ||
            (config && (config.type === "nested" || config.type === "array"))
        )
            return null;

        const metaEntry = fkMeta[field];
        const endpointForField =
            (metaEntry && (metaEntry.endpoint || metaEntry.fk_endpoint)) || fkEndpoints[field];

        return (
            <FieldRenderer
                fieldName={field}
                config={config}
                value={formData[field]}
                onChange={(v) => setFormData((prev) => ({...prev, [field]: v}))}
                getFieldChoices={(f, cfg) => getFieldChoices(f, cfg)}
                resolveFkEndpoint={() => endpointForField}
                searchFn={async (f, q) => {
                    // use searchForeignKey and also return the results
                    const res = await searchForeignKey(f, q);
                    return res || fkOptions[f] || [];
                }}
                fkOptions={fkOptions[field] || []}
                setFkOptions={(arr) => setFkOptions((prev) => ({...prev, [field]: arr}))}
                searchTerm={searchTerm[field] ?? ""}
                setSearchTerm={(s) => setSearchTerm((prev) => ({...prev, [field]: s}))}
                loading={loadingField === field}
                active={activeField === field}
                setActive={(b) => (b ? setActiveField(field) : setActiveField(null))}
                placeholder={`Search ${config.label || field}`}
            />
        );
    };

    return (
        <form
            onSubmit={handleSubmit}
            className="border rounded p-3 bg-light master-form"
            encType="multipart/form-data"
        >
            <div className="row g-3">
                {fieldsToRender.map((field) => (
                    <div key={field} className="col-md-4">
                        <label className="form-label fw-medium">
                            {(schema[field] && schema[field].label) || field}
                        </label>
                        {renderField(field)}
                    </div>
                ))}
            </div>

            {(meta?.nested_field_defs && Object.keys(meta.nested_field_defs).length > 0) ||
            (meta?.nestedFieldDefs && Object.keys(meta.nestedFieldDefs).length > 0) ||
            Object.keys(nestedData).length > 0 ? (
                <div className="mt-4">
                    <MasterNestedForm
                        nestedData={nestedData}
                        setNestedData={setNestedData}
                        fkEndpoints={fkEndpoints}
                        nestedFieldDefs={meta?.nested_field_defs || meta?.nestedFieldDefs || {}}
                        rawOptions={meta?.rawOptions || meta?.raw_options || meta?.raw || {}}
                    />
                </div>
            ) : null}

            <div className="mt-3 d-flex gap-2">
                <button type="submit" className="btn btn-primary">{formData.id ? "Update" : "Save"}</button>
                <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
            </div>
        </form>
    );
};

export default MasterForm;
