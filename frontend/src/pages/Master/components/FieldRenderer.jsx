// File: src/components/master/components/FieldRenderer.jsx
import React, {useMemo} from "react";
import {Form} from "react-bootstrap";
import {getDisplayLabel} from "../../../utils";

/**
 * FieldRenderer
 *
 * Props:
 * - fieldName: string
 * - config: field config (from schema or fieldDef)
 * - value: current value
 * - onChange: (newValue) => void
 *
 * Helpers (caller should pass as needed):
 * - getFieldChoices(fieldName, config) => array (raw choices)
 * - resolveFkEndpoint(fieldName, config) => endpoint string | null
 * - searchFn(fieldNameOrMapKey, query) => Promise<array>
 * - fetchSingleFn(endpoint, id) => Promise<object>
 * - fkOptions: array of fetched FK options
 * - setFkOptions: (arr) => void
 * - searchTerm: string
 * - setSearchTerm: (s) => void
 * - loading: boolean
 * - active: boolean
 * - setActive: (b) => void
 */
export default function FieldRenderer({
                                          fieldName,
                                          config = {},
                                          value,
                                          onChange = () => {
                                          },
                                          getFieldChoices = () => [],
                                          resolveFkEndpoint = () => null,
                                          searchFn = null,
                                          fetchSingleFn = null,
                                          fkOptions = [],
                                          setFkOptions = null,
                                          searchTerm = "",
                                          setSearchTerm = null,
                                          loading = false,
                                          active = false,
                                          setActive = null,
                                          placeholder,
                                      }) {
    const t = String(config?.type || "").toLowerCase();
    const resolvedFkEndpoint = resolveFkEndpoint(fieldName, config);

    const normalizedChoices = useMemo(() => {
        const raw = getFieldChoices(fieldName, config) || [];
        if (!Array.isArray(raw)) return [];
        return raw.map((c) =>
            Array.isArray(c) ? {value: c[0], label: c[1]} : typeof c === "object" ? {
                value: c.value,
                label: c.label
            } : {value: c, label: String(c)}
        );
    }, [getFieldChoices, fieldName, config]);

    const displayValueForFk = (() => {
        if (searchTerm && searchTerm.length) return searchTerm;
        if (!fkOptions || fkOptions.length === 0) {
            if (value && typeof value === "object") return getDisplayLabel(value) || String(value.id ?? value.pk ?? "");
            return value ?? "";
        }
        const found = fkOptions.find((o) => String(o.id ?? o.value) === String(value));
        return found ? getDisplayLabel(found) : value ?? "";
    })();

    // 1) choices -> select
    if (normalizedChoices && normalizedChoices.length > 0) {
        return (
            <Form.Select
                value={value ?? ""}
                onChange={(e) => onChange(e.target.value)}
                aria-label={config.label || fieldName}
            >
                <option value="">{config.placeholder || `Select ${config.label || fieldName}`}</option>
                {normalizedChoices.map((opt) => (
                    <option key={String(opt.value)} value={opt.value}>
                        {opt.label}
                    </option>
                ))}
            </Form.Select>
        );
    }

    // 2) FK autocomplete
    if (resolvedFkEndpoint && typeof searchFn === "function") {
        return (
            <div className="position-relative">
                <input
                    type="text"
                    className="form-control"
                    placeholder={placeholder || config.label || fieldName}
                    value={displayValueForFk}
                    onChange={(e) => {
                        const v = e.target.value;
                        if (typeof setSearchTerm === "function") setSearchTerm(v);
                        if (typeof setActive === "function") setActive(true);
                        if (typeof searchFn === "function") {
                            searchFn(fieldName, v)
                                .then((res) => {
                                    if (typeof setFkOptions === "function") setFkOptions(res || []);
                                })
                                .catch(() => {
                                    if (typeof setFkOptions === "function") setFkOptions([]);
                                });
                        }
                    }}
                    onFocus={() => {
                        if (typeof setActive === "function") setActive(true);
                        if ((!fkOptions || fkOptions.length === 0) && typeof searchFn === "function") {
                            searchFn(fieldName, "")
                                .then((res) => {
                                    if (typeof setFkOptions === "function") setFkOptions(res || []);
                                })
                                .catch(() => {
                                    if (typeof setFkOptions === "function") setFkOptions([]);
                                });
                        }
                    }}
                    onBlur={() => {
                        if (typeof setActive === "function") setTimeout(() => setActive(false), 150);
                    }}
                />
                {loading && <div className="small text-muted mt-1">Searching...</div>}
                {Array.isArray(fkOptions) && fkOptions.length > 0 && active && (
                    <div className="dropdown-menu show w-100 mt-1"
                         style={{maxHeight: 240, overflowY: "auto", zIndex: 2000}}>
                        {fkOptions.map((opt) => (
                            <button
                                key={opt.id ?? opt.value ?? JSON.stringify(opt)}
                                type="button"
                                className="dropdown-item text-start"
                                onMouseDown={(ev) => {
                                    ev.preventDefault();
                                    onChange(opt.id ?? opt.value ?? opt);
                                    if (typeof setSearchTerm === "function") setSearchTerm(getDisplayLabel(opt) || String(opt.id ?? opt.value ?? ""));
                                    if (typeof setFkOptions === "function") setFkOptions([]);
                                    if (typeof setActive === "function") setActive(false);
                                }}
                            >
                                {getDisplayLabel(opt) || String(opt.id ?? opt.value ?? "")}
                            </button>
                        ))}
                    </div>
                )}
            </div>
        );
    }

    // 3) file / image
    if (t === "file" || t === "image") {
        const previewUrl =
            value instanceof File ? URL.createObjectURL(value) : typeof value === "string" && value.length > 0 ? value : null;
        return (
            <div>
                <input
                    type="file"
                    name={fieldName}
                    className="form-control"
                    accept={t === "image" ? "image/*" : undefined}
                    onChange={(e) => onChange(e.target.files && e.target.files[0] ? e.target.files[0] : null)}
                />
                {previewUrl && (
                    <div style={{marginTop: 6}}>
                        <img src={previewUrl} alt="preview"
                             style={{maxWidth: 120, maxHeight: 120, objectFit: "cover"}}/>
                    </div>
                )}
            </div>
        );
    }

    // 4) boolean
    if (t === "boolean") {
        return (
            <div className="form-check">
                <input
                    className="form-check-input"
                    type="checkbox"
                    id={fieldName}
                    checked={!!value}
                    onChange={(e) => onChange(e.target.checked)}
                />
                <label className="form-check-label" htmlFor={fieldName}>
                    {config.label || fieldName}
                </label>
            </div>
        );
    }

    // 5) textarea
    if (t === "text" || config.widget === "textarea") {
        return <textarea className="form-control" value={value ?? ""} onChange={(e) => onChange(e.target.value)}
                         placeholder={config.label || fieldName}/>;
    }

    // 6) default
    const inputType = t === "integer" || t === "number" ? "number" : "text";
    return <input type={inputType} className="form-control" value={value ?? ""}
                  onChange={(e) => onChange(e.target.value)} placeholder={config.label || fieldName}/>;
}
