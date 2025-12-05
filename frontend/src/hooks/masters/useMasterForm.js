/**
 * Custom hook for Master Form logic.
 *
 * Centralizes state management and business logic for master form operations,
 * including form state, validation, auto-calculations, and API interactions.
 */

import {useCallback, useEffect, useState} from 'react';
import {useNavigate} from 'react-router-dom';
import {toast} from 'react-toastify';
import {masterApi} from '../../services/api';
import {formCalculator} from '../../services/calculators';
import {useApiCall} from '../useApiCall';

export const useMasterForm = (endpoint, recordId = null, options = {}) => {
    const {
        onSuccess,
        onError,
        enableAutoCalculation = true,
    } = options;

    const navigate = useNavigate();

    // State
    const [formData, setFormData] = useState({});
    const [originalData, setOriginalData] = useState({});
    const [metadata, setMetadata] = useState(null);
    const [loading, setLoading] = useState(true);
    const [errors, setErrors] = useState({});
    const [touched, setTouched] = useState({});
    const [isDirty, setIsDirty] = useState(false);

    // API calls
    const {execute: executeSave, loading: saving} = useApiCall({
        onSuccess: (data) => {
            if (onSuccess) onSuccess(data);
        },
        onError: (error) => {
            if (onError) onError(error);
        }
    });

    // Fetch metadata and record data on mount
    useEffect(() => {
        fetchInitialData();
    }, [endpoint, recordId]);

    // Fetch metadata and record data
    const fetchInitialData = async () => {
        setLoading(true);
        try {
            // Fetch metadata
            const meta = await masterApi.fetchMasterMetadata(endpoint);
            setMetadata(meta);

            // Fetch record if editing
            if (recordId) {
                const record = await masterApi.fetchMasterRecord(endpoint, recordId);
                setFormData(record);
                setOriginalData(record);
            } else {
                // Initialize with default values from metadata
                const defaults = {};
                if (meta?.actions?.POST) {
                    Object.entries(meta.actions.POST).forEach(([fieldName, fieldMeta]) => {
                        if (fieldMeta.default !== undefined) {
                            defaults[fieldName] = fieldMeta.default;
                        }
                    });
                }
                setFormData(defaults);
                setOriginalData(defaults);
            }
        } catch (error) {
            toast.error('Failed to load form data');
        } finally {
            setLoading(false);
        }
    };

    // Handle field change
    const handleChange = useCallback((fieldName, value) => {
        setFormData(prev => {
            const updated = {...prev, [fieldName]: value};

            // Apply auto-calculations if enabled
            if (enableAutoCalculation) {
                const autoCalcUpdates = formCalculator.autoCalculateFields(
                    updated,
                    fieldName,
                    value
                );
                Object.assign(updated, autoCalcUpdates);
            }

            return updated;
        });

        // Mark field as touched
        setTouched(prev => ({...prev, [fieldName]: true}));

        // Mark form as dirty
        setIsDirty(true);

        // Clear field error
        setErrors(prev => {
            const newErrors = {...prev};
            delete newErrors[fieldName];
            return newErrors;
        });
    }, [enableAutoCalculation]);

    // Handle nested field change
    const handleNestedChange = useCallback((fieldName, index, nestedFieldName, value) => {
        setFormData(prev => {
            const updated = {...prev};
            if (!Array.isArray(updated[fieldName])) {
                updated[fieldName] = [];
            }
            if (!updated[fieldName][index]) {
                updated[fieldName][index] = {};
            }
            updated[fieldName][index][nestedFieldName] = value;
            return updated;
        });

        setIsDirty(true);
    }, []);

    // Add nested item
    const addNestedItem = useCallback((fieldName, defaultItem = {}) => {
        setFormData(prev => ({
            ...prev,
            [fieldName]: [...(prev[fieldName] || []), defaultItem]
        }));
        setIsDirty(true);
    }, []);

    // Remove nested item
    const removeNestedItem = useCallback((fieldName, index) => {
        setFormData(prev => ({
            ...prev,
            [fieldName]: prev[fieldName].filter((_, i) => i !== index)
        }));
        setIsDirty(true);
    }, []);

    // Validate form
    const validateForm = useCallback(() => {
        const newErrors = {};

        if (!metadata?.actions?.POST) return newErrors;

        Object.entries(metadata.actions.POST).forEach(([fieldName, fieldMeta]) => {
            const value = formData[fieldName];

            // Check required fields
            if (fieldMeta.required && !value && value !== 0) {
                newErrors[fieldName] = 'This field is required';
            }

            // Validate numeric fields
            if (fieldMeta.type === 'integer' || fieldMeta.type === 'decimal') {
                if (value) {
                    const validation = formCalculator.validateNumericField(
                        value,
                        fieldMeta.min_value,
                        fieldMeta.max_value
                    );
                    if (!validation.isValid) {
                        newErrors[fieldName] = validation.error;
                    }
                }
            }

            // Validate date fields
            if (fieldMeta.type === 'date' && value) {
                const validation = formCalculator.validateDateField(value);
                if (!validation.isValid) {
                    newErrors[fieldName] = validation.error;
                }
            }
        });

        setErrors(newErrors);
        return newErrors;
    }, [formData, metadata]);

    // Handle submit
    const handleSubmit = async (e) => {
        if (e) e.preventDefault();

        // Validate
        const validationErrors = validateForm();
        if (Object.keys(validationErrors).length > 0) {
            return {success: false, errors: validationErrors};
        }

        // Save
        const result = await executeSave(async () => {
            if (recordId) {
                return await masterApi.updateMasterRecord(endpoint, recordId, formData);
            } else {
                return await masterApi.createMasterRecord(endpoint, formData);
            }
        });

        if (result.success) {
            setIsDirty(false);
            setOriginalData(result.data);
        }

        return result;
    };

    // Reset form
    const resetForm = useCallback(() => {
        setFormData(originalData);
        setErrors({});
        setTouched({});
        setIsDirty(false);
    }, [originalData]);

    // Check if field has error and is touched
    const getFieldError = useCallback((fieldName) => {
        return touched[fieldName] ? errors[fieldName] : null;
    }, [touched, errors]);

    // Get field metadata
    const getFieldMetadata = useCallback((fieldName) => {
        return metadata?.actions?.POST?.[fieldName] || null;
    }, [metadata]);

    // Check if field is required
    const isFieldRequired = useCallback((fieldName) => {
        return metadata?.actions?.POST?.[fieldName]?.required || false;
    }, [metadata]);

    return {
        // State
        formData,
        metadata,
        loading,
        saving,
        errors,
        touched,
        isDirty,
        isEdit: !!recordId,

        // Actions
        handleChange,
        handleNestedChange,
        addNestedItem,
        removeNestedItem,
        handleSubmit,
        resetForm,
        validateForm,

        // Helpers
        getFieldError,
        getFieldMetadata,
        isFieldRequired,
        setFormData,
        setErrors,
    };
};

export default useMasterForm;
