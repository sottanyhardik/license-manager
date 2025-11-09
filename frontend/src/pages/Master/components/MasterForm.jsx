// File: src/components/master/components/MasterForm.jsx
import React, {useEffect, useRef, useState} from "react";
import MasterNestedForm from "./MasterNestedForm";
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
            if (!endpointForField) return;
            setLoadingField(field);
            try {
                const res = await api.get(`${endpointForField}?search=${encodeURIComponent(query)}`);
                const results = res.data?.results ?? res.data ?? [];
                setFkOptions((prev) => ({...prev, [field]: results}));
            } catch (err) {
                console.warn(`Search failed for ${field}:`, err);
                setFkOptions((prev) => ({...prev, [field]: []}));
            } finally {
                setLoadingField(null);
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

    // Autocomplete select renderer (for both static choices & remote FK)
    const renderAutocompleteOrFk = (field, config = {}) => {
        // detect fk endpoint
        const metaEntry = fkMeta[field];
        const endpointForField = (metaEntry && (metaEntry.endpoint || metaEntry.fk_endpoint)) || fkEndpoints[field];

        // FK remote search
        if (endpointForField) {
            const options = fkOptions[field] || [];
            const displayValue = (() => {
                const st = searchTerm[field];
                if (st && st.length > 0) return st;
                const found = options.find((o) => String(o.id) === String(formData[field]));
                return found ? getDisplayLabel(found) : formData[field] ?? "";
            })();

            const activeIdx = (options || []).findIndex((o) => String(o.id) === String(searchTerm[field])); // not critical
            return (
                <div className="position-relative">
                    <input
                        type="text"
                        className="form-control"
                        placeholder={`Search ${config.label || field}`}
                        value={displayValue}
                        onChange={(e) => {
                            const val = e.target.value;
                            setSearchTerm((prev) => ({...prev, [field]: val}));
                            setActiveField(field);
                            if (val && val.length >= 1) searchForeignKey(field, val);
                            else setFkOptions((prev) => ({...prev, [field]: []}));
                        }}
                        onFocus={() => {
                            if (blurTimeoutRef.current) {
                                clearTimeout(blurTimeoutRef.current);
                                blurTimeoutRef.current = null;
                            }
                            setActiveField(field);
                            if (!options || options.length === 0) searchForeignKey(field, "");
                        }}
                        onBlur={() => {
                            if (blurTimeoutRef.current) clearTimeout(blurTimeoutRef.current);
                            blurTimeoutRef.current = setTimeout(() => {
                                setActiveField(null);
                                blurTimeoutRef.current = null;
                            }, 150);
                        }}
                        onKeyDown={(e) => {
                            const opts = fkOptions[field] || [];
                            const active = opts.findIndex((o) => String(o.id) === String(formData[field]));
                            if (e.key === "ArrowDown") {
                                e.preventDefault();
                                // move highlight by index in options: toggled by storing a special active index map? for simplicity, do nothing here.
                            } else if (e.key === "Enter") {
                                // nothing
                            } else if (e.key === "Escape") {
                                setFkOptions((prev) => ({...prev, [field]: []}));
                                setActiveField(null);
                            }
                        }}
                        autoComplete="off"
                    />
                    {loadingField === field && <div className="small text-muted mt-1">Searching...</div>}
                    {Array.isArray(options) && options.length > 0 && activeField === field && (
                        <div className="dropdown-menu show w-100 mt-1"
                             style={{zIndex: 2000, maxHeight: 300, overflowY: "auto"}}>
                            {options.map((opt) => (
                                <button
                                    key={opt.id}
                                    type="button"
                                    className="dropdown-item text-start"
                                    onMouseDown={(ev) => {
                                        ev.preventDefault();
                                        setFormData((prev) => ({...prev, [field]: opt.id}));
                                        setSearchTerm((prev) => ({
                                            ...prev,
                                            [field]: getDisplayLabel(opt) || String(opt.id)
                                        }));
                                        setFkOptions((prev) => ({...prev, [field]: []}));
                                        setActiveField(null);
                                        if (blurTimeoutRef.current) {
                                            clearTimeout(blurTimeoutRef.current);
                                            blurTimeoutRef.current = null;
                                        }
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

        // static choices: client-side autocomplete
        if (config.choices && Array.isArray(config.choices)) {
            const options = normalizeChoices(config.choices);
            const display = searchTerm[field] ?? options.find((o) => String(o.value) === String(formData[field]))?.label ?? "";

            return (
                <div className="position-relative">
                    <input
                        type="text"
                        className="form-control"
                        placeholder={`Search ${config.label || field}`}
                        value={display}
                        onChange={(e) => {
                            const val = e.target.value;
                            setSearchTerm((prev) => ({...prev, [field]: val}));
                            setFkOptions((prev) => ({
                                ...prev,
                                [field]: options.filter((opt) => opt.label.toLowerCase().includes(val.toLowerCase()))
                            }));
                            setActiveField(field);
                        }}
                        onFocus={() => {
                            if (blurTimeoutRef.current) {
                                clearTimeout(blurTimeoutRef.current);
                                blurTimeoutRef.current = null;
                            }
                            setActiveField(field);
                            setFkOptions((prev) => ({...prev, [field]: options}));
                        }}
                        onBlur={() => {
                            if (blurTimeoutRef.current) clearTimeout(blurTimeoutRef.current);
                            blurTimeoutRef.current = setTimeout(() => {
                                setActiveField(null);
                                blurTimeoutRef.current = null;
                            }, 150);
                        }}
                        autoComplete="off"
                    />
                    {Array.isArray(fkOptions[field]) && fkOptions[field].length > 0 && activeField === field && (
                        <div className="dropdown-menu show w-100 mt-1" style={{zIndex: 2000}}>
                            {fkOptions[field].map((opt) => (
                                <button
                                    key={opt.value}
                                    type="button"
                                    className="dropdown-item text-start"
                                    onMouseDown={(ev) => {
                                        ev.preventDefault();
                                        setFormData((prev) => ({...prev, [field]: opt.value}));
                                        setSearchTerm((prev) => ({...prev, [field]: opt.label}));
                                        setFkOptions((prev) => ({...prev, [field]: []}));
                                        setActiveField(null);
                                        if (blurTimeoutRef.current) {
                                            clearTimeout(blurTimeoutRef.current);
                                            blurTimeoutRef.current = null;
                                        }
                                    }}
                                >
                                    {opt.label}
                                </button>
                            ))}
                        </div>
                    )}
                </div>
            );
        }

        return null;
    };

    const renderField = (field) => {
        const config = schema[field] || {label: field, type: "text"};
        if (hiddenFields.includes(field)) return null;
        if (Array.isArray(nestedData[field]) || (config && (config.type === "nested" || config.type === "array" || config.widget === "nested"))) return null;

        // FK or choices -> autocomplete
        const metaEntry = fkMeta[field];
        const endpointForField = (metaEntry && (metaEntry.endpoint || metaEntry.fk_endpoint)) || fkEndpoints[field];
        if (endpointForField || (config.choices && Array.isArray(config.choices))) return renderAutocompleteOrFk(field, config);

        // file/image
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
                        <div style={{marginTop: 6}}>
                            <img src={previewUrl} alt="preview"
                                 style={{maxWidth: "120px", maxHeight: "120px", objectFit: "cover"}}/>
                        </div>
                    )}
                </div>
            );
        }

        // boolean
        if (config.type === "boolean") {
            return (
                <div className="form-check">
                    <input className="form-check-input" type="checkbox" id={field} name={field}
                           checked={!!formData[field]} onChange={handleChange}/>
                    <label className="form-check-label" htmlFor={field}>{config.label || field}</label>
                </div>
            );
        }

        // textarea
        if (config.type === "text" || config.widget === "textarea") {
            return <textarea name={field} className="form-control" value={formData[field] ?? ""} onChange={handleChange}
                             placeholder={config.label || field}/>;
        }

        const inputType = config.type === "integer" || config.type === "number" ? "number" : "text";
        return <input type={inputType} name={field} value={formData[field] ?? ""} onChange={handleChange}
                      className="form-control" placeholder={config.label || field}/>;
    };

    return (
        <form onSubmit={handleSubmit} className="border rounded p-3 bg-light" encType="multipart/form-data">
            <div className="row g-3">
                {fieldsToRender.map((field) => (
                    <div key={field} className="col-md-4">
                        <label
                            className="form-label fw-medium">{(schema[field] && schema[field].label) || field}</label>
                        {renderField(field)}
                    </div>
                ))}
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
                <button type="submit" className="btn btn-primary">{formData.id ? "Update" : "Save"}</button>
                <button type="button" className="btn btn-secondary" onClick={onCancel}>Cancel</button>
            </div>
        </form>
    );
};

export default MasterForm;
