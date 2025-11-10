// File: src/components/master/components/MasterNestedForm.jsx
// (Full file — drop in replacing existing implementation)

import React, {useEffect, useMemo, useRef, useState} from "react";
import {Button, Form} from "react-bootstrap";
import api from "../../../api/axios";
import FieldRenderer from "./FieldRenderer";

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
 *  - rawOptions: optional raw OPTIONS payload from backend (used to read actions.POST.<field>.choices)
 */
const MasterNestedForm = ({
                              nestedData = {},
                              setNestedData,
                              fkEndpoints = {},
                              nestedFieldDefs = {},
                              rawOptions = {}
                          }) => {
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
                            toFetch.push({
                                mapKey,
                                endpoint,
                                id: val,
                                label_field: def.label_field || def.labelField || def.labelFieldName
                            });
                        }
                    } else {
                        displays[mapKey] = "";
                    }
                });
            });
        });
        setFkDisplayMap((prev) => ({...displays, ...prev}));

        // fetch single objects for primitive ids to resolve labels
        toFetch.forEach(({mapKey, endpoint, id}) => {
            const url = `${String(endpoint).endsWith("/") ? endpoint : `${endpoint}`}${String(id)}/`;
            (async () => {
                try {
                    const res = await api.get(url);
                    const obj = res.data;
                    setFkDisplayMap((p) => ({...p, [mapKey]: displayLabel(obj) || String(id)}));
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

    // getFieldChoices for nested fields - looks at fieldDef.choices or backend OPTIONS actions.POST.<field>.choices
    const getFieldChoices = (section, fieldDef) => {
        if (!fieldDef) return [];
        // explicit choices on fieldDef
        if (Array.isArray(fieldDef.choices) && fieldDef.choices.length) return fieldDef.choices;

        // rawOptions passed from parent (MasterForm sends meta.rawOptions)
        const raw = rawOptions || {};
        const actionsPost = (raw.actions && (raw.actions.POST || raw.actions.post)) || raw.actions || raw;
        const fname = fieldDef.name;
        if (actionsPost && actionsPost[fname] && Array.isArray(actionsPost[fname].choices)) {
            return actionsPost[fname].choices;
        }

        // fields.<field>.choices fallback
        if (raw.fields && raw.fields[fname] && Array.isArray(raw.fields[fname].choices)) {
            return raw.fields[fname].choices;
        }

        // raw[field].choices fallback
        if (raw[fname] && Array.isArray(raw[fname].choices)) return raw[fname].choices;

        return [];
    };

    // fetch fk options (search)
    const fetchFkOptions = async (mapKey, endpoint, query) => {
        if (!endpoint) return;
        setLoadingFk((s) => ({...s, [mapKey]: true}));
        try {
            const res = await api.get(`${endpoint}?search=${encodeURIComponent(query || "")}`);
            const results = res.data?.results ?? res.data ?? [];
            setFkOptionsMap((prev) => ({...prev, [mapKey]: results}));
            setFkActiveIdx((p) => ({...p, [mapKey]: results.length ? 0 : -1}));
        } catch (err) {
            console.warn("FK search failed", endpoint, err);
            setFkOptionsMap((prev) => ({...prev, [mapKey]: []}));
            setFkActiveIdx((p) => ({...p, [mapKey]: -1}));
        } finally {
            setLoadingFk((s) => ({...s, [mapKey]: false}));
        }
    };

    const makeEmptyRow = (section) => {
        const defs = nestedFieldDefs[section] || [];
        if (!Array.isArray(defs) || defs.length === 0) return {id: null};
        const row = {id: null};
        defs.forEach((d) => {
            row[d.name] = d.default ?? (d.type === "boolean" ? false : "");
        });
        return row;
    };

    const normalizedNestedData = useMemo(() => {
        const nd = {...(nestedData || {})};
        Object.keys(nestedFieldDefs || {}).forEach((k) => {
            if (!(k in nd)) nd[k] = [];
        });
        return nd;
    }, [nestedData, nestedFieldDefs]);

    const handleAddRow = (section) => {
        setNestedData((prev) => {
            const next = {...(prev || {})};
            next[section] = [...(next[section] || []), makeEmptyRow(section)];
            return next;
        });
    };

    const handleRemoveRow = (section, index) => {
        setNestedData((prev) => {
            const next = {...(prev || {})};
            next[section] = (next[section] || []).filter((_, i) => i !== index);
            return next;
        });
        // cleanup transient UI state
        setFkDisplayMap((prev) => {
            const copy = {...prev};
            Object.keys(copy).forEach((k) => {
                if (k.startsWith(`${section}__`) && k.endsWith(`__${index}`)) delete copy[k];
            });
            return copy;
        });
        setFkOptionsMap((prev) => {
            const copy = {...prev};
            Object.keys(copy).forEach((k) => {
                if (k.startsWith(`${section}__`) && k.endsWith(`__${index}`)) delete copy[k];
            });
            return copy;
        });
        setFkActiveIdx((p) => {
            const copy = {...p};
            Object.keys(copy).forEach((k) => {
                if (k.startsWith(`${section}__`) && k.endsWith(`__${index}`)) delete copy[k];
            });
            return copy;
        });
    };

    const handleChange = (section, index, field, value) =>
        setNestedData((prev) => {
            const next = {...(prev || {})};
            const arr = [...(next[section] || [])];
            arr[index] = {...arr[index], [field]: value};
            next[section] = arr;
            return next;
        });

    // typed FK input: debounced search
    const handleFkInput = (section, index, fieldDef, text) => {
        const mapKey = `${section}__${fieldDef.name}__${index}`;
        const endpoint = resolveFkEndpoint(section, fieldDef);
        setFkDisplayMap((p) => ({...p, [mapKey]: text}));

        if (debounceTimers.current[mapKey]) clearTimeout(debounceTimers.current[mapKey]);
        debounceTimers.current[mapKey] = setTimeout(() => {
            fetchFkOptions(mapKey, endpoint, text || "");
        }, 250);
    };

    const handlePickFk = (section, index, fieldDef, option) => {
        // store FK as id for submission
        handleChange(section, index, fieldDef.name, option.id);
        const mapKey = `${section}__${fieldDef.name}__${index}`;
        setFkDisplayMap((p) => ({...p, [mapKey]: displayLabel(option)}));
        setFkOptionsMap((p) => ({...p, [mapKey]: []}));
        setFkActiveIdx((p) => ({...p, [mapKey]: -1}));
    };

    const handleFkKeyDown = (e, section, index, fieldDef) => {
        const mapKey = `${section}__${fieldDef.name}__${index}`;
        const options = fkOptionsMap[mapKey] || [];
        const active = typeof fkActiveIdx[mapKey] === "number" ? fkActiveIdx[mapKey] : -1;

        if (e.key === "ArrowDown") {
            e.preventDefault();
            setFkActiveIdx((p) => ({...p, [mapKey]: Math.min((options.length || 0) - 1, (p[mapKey] || 0) + 1)}));
        } else if (e.key === "ArrowUp") {
            e.preventDefault();
            setFkActiveIdx((p) => ({...p, [mapKey]: Math.max(0, (p[mapKey] || 0) - 1)}));
        } else if (e.key === "Enter") {
            e.preventDefault();
            const idx = fkActiveIdx[mapKey] || 0;
            if (options && options[idx]) handlePickFk(section, index, fieldDef, options[idx]);
        } else if (e.key === "Escape") {
            setFkOptionsMap((p) => ({...p, [mapKey]: []}));
            setFkActiveIdx((p) => ({...p, [mapKey]: -1}));
        }
    };

    const renderControlForField = (section, rowIndex, fieldDef) => {
        const fname = fieldDef.name;
        const val = (normalizedNestedData[section] || [])[rowIndex]?.[fname];

        const invalidClass = (fieldDef.required && (val === null || val === "" || val === undefined)) ? "is-invalid" : "";
        const error = fieldDef.required && (val === null || val === "" || val === undefined) ? `${fieldDef.label || fname} is required` : null;

        // prepare wiring for FieldRenderer
        const mapKey = `${section}__${fname}__${rowIndex}`;
        const endpoint = resolveFkEndpoint(section, fieldDef);

        const choicesHelper = (f, cfg) => {
            // prefer explicit fieldDef choices
            return getFieldChoices(section, fieldDef);
        };

        const nestedSearchFn = async (_k, q) => {
            await fetchFkOptions(mapKey, endpoint, q);
            return fkOptionsMap[mapKey] || [];
        };

        const onChange = (v) => handleChange(section, rowIndex, fname, v);

        return (
            <>
                <FieldRenderer
                    fieldName={fname}
                    config={fieldDef}
                    value={val}
                    onChange={onChange}
                    getFieldChoices={choicesHelper}
                    resolveFkEndpoint={() => endpoint}
                    searchFn={(k, q) => nestedSearchFn(mapKey, q)}
                    fkOptions={fkOptionsMap[mapKey] || []}
                    setFkOptions={(arr) => setFkOptionsMap((p) => ({...p, [mapKey]: arr}))}
                    searchTerm={fkDisplayMap[mapKey] ?? ""}
                    setSearchTerm={(s) => setFkDisplayMap((p) => ({...p, [mapKey]: s}))}
                    loading={!!loadingFk[mapKey]}
                    active={typeof fkActiveIdx[mapKey] === "number" && fkActiveIdx[mapKey] >= 0}
                    setActive={(b) => setFkActiveIdx((p) => ({...p, [mapKey]: b ? 0 : -1}))}
                    placeholder={fieldDef.label || fname}
                />
                {error && <div className="invalid-feedback d-block">{error}</div>}
            </>
        );
    };

    return (
        <div className="nested-form-container">
            {keys.map((section) => {
                const items = normalizedNestedData[section] || [];
                const defs = nestedFieldDefs[section] || [];

                return (
                    <div key={section} className="card border-0 shadow-sm mb-3">
                        <div className="card-header bg-light d-flex justify-content-between align-items-center">
                            <h6 className="fw-bold text-orange text-uppercase mb-0">
                                {section.replace(/_/g, " ")}
                            </h6>
                            <div>
                                <Button size="sm" variant="outline-secondary"
                                        onClick={() => handleAddRow(section)}>Add</Button>
                            </div>
                        </div>

                        <div className="card-body p-2">
                            {(items || []).length === 0 ? (
                                <div className="text-muted small px-2">No rows</div>
                            ) : null}

                            {(items || []).map((row, rowIndex) => (
                                <div key={rowIndex} className="mb-3 border-bottom pb-2">
                                    <input type="hidden" value={row.id ?? ""}/>
                                    <div className="row g-2">
                                        {defs.map((fieldDef) => {
                                            const fname = fieldDef.name;
                                            return (
                                                <div key={fname} className="col-md-4">
                                                    <Form.Group>
                                                        <Form.Label
                                                            className="fw-medium text-capitalize small">{fieldDef.label || fname.replace(/_/g, " ")}</Form.Label>
                                                        {renderControlForField(section, rowIndex, fieldDef)}
                                                    </Form.Group>
                                                </div>
                                            );
                                        })}
                                    </div>
                                    <div className="mt-2 d-flex gap-2">
                                        <Button size="sm" variant="outline-danger"
                                                onClick={() => handleRemoveRow(section, rowIndex)}>Remove</Button>
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
