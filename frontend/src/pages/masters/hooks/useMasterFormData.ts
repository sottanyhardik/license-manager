import { useEffect, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import api from "../../../api/axios";
import { primeFkDetailCache } from "../../../components/fkDetailCache";
import { getMasterFormApiBase } from "../masterFormHelpers";

export interface UseMasterFormDataOptions {
    entityName: string | null | undefined;
    recordId: string | number | undefined;
    isEdit: boolean;
    location: ReturnType<typeof useLocation>;
    navigate: ReturnType<typeof useNavigate>;
    /** Called after a successful fetchRecord when parse data is found in location state */
    applyLicenseParse: (data: Record<string, any>, fileOverride?: File | null, opts?: Record<string, any>) => void;
    setLicensePdfFile: (f: File | null) => void;
}

export function useMasterFormData({
    entityName,
    recordId,
    isEdit,
    location,
    navigate,
    applyLicenseParse,
    setLicensePdfFile,
}: UseMasterFormDataOptions) {
    const [formData, setFormData] = useState<Record<string, any>>({});
    const [metadata, setMetadata] = useState<Record<string, any>>({});
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [updatedFields, setUpdatedFields] = useState<Record<string, boolean>>({});
    const [activeNestedTab, setActiveNestedTab] = useState<string | null>(null);
    const [itemConditionsBySerial, setItemConditionsBySerial] = useState<Record<string, any>>({});

    // Fetch metadata and existing record
    useEffect(() => {
        if (!entityName) return;
        fetchMetadata();
        if (isEdit) {
            fetchRecord();
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [entityName, recordId]);

    const fetchMetadata = async () => {
        try {
            const apiPath = getMasterFormApiBase(entityName);

            // Use GET to fetch metadata (custom structure with form_fields, field_meta, etc.)
            const { data } = await api.get(apiPath);

            setMetadata({
                form_fields: data.form_fields || data.fields || [],
                nested_field_defs: data.nested_field_defs || {},
                field_meta: data.field_meta || {},
            });

            // Apply default values from field_meta when creating new record (not editing)
            if (!isEdit && data.field_meta) {
                const defaults: Record<string, any> = {};
                const fkDefaults: Record<string, any> = {}; // Store FK defaults to fetch labels

                Object.keys(data.field_meta).forEach(fieldName => {
                    const fieldConfig = data.field_meta[fieldName];
                    if (fieldConfig.default !== undefined && fieldConfig.default !== null) {
                        defaults[fieldName] = fieldConfig.default;

                        // Track FK fields with defaults to fetch their labels
                        // Note: type can be 'fk' or 'select' (enhanced by backend)
                        if ((fieldConfig.type === 'fk' || fieldConfig.type === 'select') && typeof fieldConfig.default === 'number') {
                            const endpoint = fieldConfig.fk_endpoint || fieldConfig.endpoint || data.fk_endpoint_overrides?.[fieldName];
                            const labelField = fieldConfig.label_field || data.label_field_overrides?.[fieldName] || 'name';

                            fkDefaults[fieldName] = {
                                id: fieldConfig.default,
                                endpoint: endpoint,
                                labelField: labelField,
                            };
                        }
                    }
                });

                // For FK defaults, just set the ID - AsyncSelectField will fetch the label
                if (Object.keys(fkDefaults).length > 0) {
                    const fkValues = Object.keys(fkDefaults).reduce<Record<string, any>>((acc, fieldName) => {
                        acc[fieldName] = fkDefaults[fieldName].id;
                        return acc;
                    }, {});

                    setFormData(prev => ({ ...prev, ...fkValues }));
                }

                // Only set non-FK defaults if we found any
                const nonFkDefaults = Object.keys(defaults)
                    .filter(key => !fkDefaults[key])
                    .reduce<Record<string, any>>((obj, key) => {
                        obj[key] = defaults[key];
                        return obj;
                    }, {});

                if (Object.keys(nonFkDefaults).length > 0) {
                    setFormData(prevData => ({ ...prevData, ...nonFkDefaults }));
                }
            }
        } catch (err: any) {
            console.error('[MasterForm] Error fetching metadata:', err);
            console.error('[MasterForm] Error response:', err.response?.data);
            toast.error("Failed to load form metadata: " + (err.response?.data?.detail || err.message));
        }
    };

    const fetchRecord = async () => {
        setLoading(true);
        try {
            const apiPath = `${getMasterFormApiBase(entityName)}${recordId}/`;
            const { data } = await api.get(apiPath);

            // Pre-populate the AsyncSelectField cache from the *_detail
            // fields the serializer already returns inline. Saves one GET
            // per FK per row when the page renders.
            if (entityName === 'licenses' && Array.isArray(data.import_license)) {
                data.import_license.forEach((row: any) => {
                    if (row.hs_code_detail) {
                        primeFkDetailCache('/masters/hs-codes/', row.hs_code_detail);
                    }
                    if (Array.isArray(row.items_detail)) {
                        row.items_detail.forEach((item: any) =>
                            primeFkDetailCache('/masters/item-names/', item)
                        );
                    }
                });
                // Rebuild the condition-badge map from persisted condition_type
                // so badges show on plain edit loads (no parse step required).
                const loadedConditions: Record<string, any> = {};
                data.import_license.forEach((row: any) => {
                    if (row.condition_type && row.serial_number != null) {
                        loadedConditions[row.serial_number] = row.condition_type;
                    }
                });
                setItemConditionsBySerial(loadedConditions);
            }
            setFormData(data);

            // If we arrived here via /licenses/create → existing-license redirect
            // (from handleParseLicensePdf), the parsed PDF response was passed in
            // location state. Re-apply it now so the user sees prefilled fields.
            const parseData = location.state?.licenseParseData;
            if (parseData && entityName === 'licenses') {
                const carriedFile = location.state?.licensePdfFile || null;
                if (carriedFile) {
                    setLicensePdfFile(carriedFile);
                }
                // Pass the file directly so the License Copy document gets
                // attached on this render — setLicensePdfFile is async.
                applyLicenseParse(parseData, carriedFile);
                // Clear the state so a manual reload doesn't re-apply it.
                navigate(location.pathname, { replace: true, state: null });
            }
        } catch (err: any) {
            setError(err.response?.data?.detail || "Failed to load record");
        } finally {
            setLoading(false);
        }
    };

    return {
        formData,
        setFormData,
        metadata,
        setMetadata,
        loading,
        error,
        setError,
        updatedFields,
        setUpdatedFields,
        activeNestedTab,
        setActiveNestedTab,
        itemConditionsBySerial,
        setItemConditionsBySerial,
    };
}
