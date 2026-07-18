import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { toast } from "sonner";
import api from "../../../api/axios";
import { formatDateForInput, parseDate as parseDateUtil } from "../../../utils/dateFormatter";
import * as validateFormUtil from "../../../utils/formValidation";
import { ValidationRules } from "../../../utils/formValidation";
import { getMasterFormApiBase } from "../masterFormHelpers";
import { markNewItemCreated } from "../../../utils/filterPersistence";

/** Shared field name map used for both frontend validation messages and backend error formatting. */
const FIELD_NAME_MAP: Record<string, string> = {
    'license_number': 'License Number',
    'license_date': 'License Date',
    'license_expiry_date': 'License Expiry Date',
    'exporter': 'Exporter',
    'port': 'Port',
    'export_license': 'Export Items',
    'import_license': 'Import Items',
    'license_documents': 'Documents',
    'hs_code': 'HS Code',
    'description': 'Description',
    'quantity': 'Quantity',
    'serial_number': 'Serial Number',
    'type': 'Type',
    'file': 'File',
    'net_quantity': 'Net Quantity',
    'norm_class': 'Norm Class',
    'unit': 'Unit',
    'cif_fc': 'CIF (FC)',
    'cif_inr': 'CIF (INR)',
};

export interface UseMasterFormSubmitOptions {
    entityName: string | null | undefined;
    recordId: string | number | undefined;
    isEdit: boolean;
    isModal: boolean;
    formData: Record<string, any>;
    metadata: Record<string, any>;
    boePdfFile: File | null;
    entityTitle: string | undefined;
    onSuccess?: (id: number | string) => void;
    onClose?: () => void;
    navigate: ReturnType<typeof useNavigate>;
    setSaving: React.Dispatch<React.SetStateAction<boolean>>;
    setError: React.Dispatch<React.SetStateAction<string>>;
    setFieldErrors: React.Dispatch<React.SetStateAction<Record<string, any>>>;
}

export function useMasterFormSubmit({
    entityName,
    recordId,
    isEdit,
    isModal,
    formData,
    metadata,
    boePdfFile,
    entityTitle,
    onSuccess,
    onClose,
    navigate,
    setSaving,
    setError,
    setFieldErrors,
}: UseMasterFormSubmitOptions) {
    // Use centralized date parser from utility
    const parseDate = (dateString: any) => parseDateUtil(dateString);

    // Helper function to format Date object to YYYY-MM-DD for API
    const formatDateForAPI = (date: any) => {
        if (!date) return null;
        return formatDateForInput(date);
    };

    // Frontend validation function
    const validateForm = () => {
        const errors: Record<string, any> = {};

        // Collect required fields from metadata and validate using utility
        if (metadata.form_fields) {
            metadata.form_fields.forEach((fieldName: string) => {
                const fieldMeta = metadata.field_meta?.[fieldName] || {};
                const label = fieldMeta.label || fieldName.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase());
                const value = formData[fieldName];
                const rules: any[] = [];

                // Add required rule
                if (fieldMeta.required) {
                    rules.push(ValidationRules.REQUIRED);
                }

                // Add type-specific validations
                if (fieldMeta.type === 'email' || fieldName.includes('email')) {
                    rules.push(ValidationRules.EMAIL);
                }
                if (fieldMeta.type === 'url' || fieldName.includes('url')) {
                    rules.push(ValidationRules.URL);
                }
                if (fieldMeta.type === 'number' || fieldMeta.type === 'decimal' || fieldMeta.type === 'integer') {
                    if (fieldMeta.type === 'integer') {
                        rules.push(ValidationRules.INTEGER);
                    } else {
                        rules.push(ValidationRules.NUMBER);
                    }
                }
                if (fieldMeta.min_value !== undefined) {
                    rules.push({ type: ValidationRules.MIN_VALUE, value: fieldMeta.min_value });
                }
                if (fieldMeta.max_value !== undefined) {
                    rules.push({ type: ValidationRules.MAX_VALUE, value: fieldMeta.max_value });
                }
                if (fieldMeta.min_length) {
                    rules.push({ type: ValidationRules.MIN_LENGTH, value: fieldMeta.min_length });
                }
                if (fieldMeta.max_length) {
                    rules.push({ type: ValidationRules.MAX_LENGTH, value: fieldMeta.max_length });
                }

                // Validate field if it has rules
                if (rules.length > 0) {
                    const fieldErrors = validateFormUtil.validateField(value, rules, label);
                    if (fieldErrors.length > 0) {
                        errors[fieldName] = fieldErrors;
                    }
                }
            });
        }

        // License-specific validations
        if (entityName === 'licenses') {
            // Validate license number format
            if (formData.license_number && !/^[A-Z0-9/-]+$/.test(formData.license_number)) {
                errors.license_number = ['License number can only contain uppercase letters, numbers, hyphens, and slashes'];
            }

            // Validate dates
            if (formData.license_date && formData.license_expiry_date) {
                const licenseDate = new Date(formData.license_date);
                const expiryDate = new Date(formData.license_expiry_date);
                if (expiryDate <= licenseDate) {
                    errors.license_expiry_date = ['Expiry date must be after license date'];
                }
            }

            // Validate export items using validation utility
            if (formData.export_license && Array.isArray(formData.export_license)) {
                const exportSchema = {
                    description: {
                        rules: [ValidationRules.REQUIRED],
                        label: 'Description',
                    },
                    net_quantity: {
                        rules: [ValidationRules.REQUIRED, ValidationRules.NON_NEGATIVE],
                        label: 'Net Quantity',
                    },
                };
                const exportErrors = validateFormUtil.validateNestedArray(formData.export_license, exportSchema);
                if (exportErrors.length > 0) {
                    errors.export_license = exportErrors;
                }
            }

            // Validate import items using validation utility
            if (formData.import_license && Array.isArray(formData.import_license)) {
                const importSchema = {
                    hs_code: {
                        rules: [ValidationRules.REQUIRED],
                        label: 'HS Code',
                    },
                    description: {
                        rules: [ValidationRules.REQUIRED],
                        label: 'Description',
                    },
                    serial_number: {
                        rules: [ValidationRules.REQUIRED, ValidationRules.INTEGER],
                        label: 'Serial Number',
                    },
                    unit: {
                        rules: [ValidationRules.REQUIRED],
                        label: 'Unit',
                    },
                };
                const importErrors = validateFormUtil.validateNestedArray(formData.import_license, importSchema);
                if (importErrors.length > 0) {
                    errors.import_license = importErrors;
                }
            }

            // Validate documents (if adding new ones)
            if (formData.license_documents && Array.isArray(formData.license_documents)) {
                const docErrors: any[] = [];
                formData.license_documents.forEach((doc: any, index: number) => {
                    // Only validate if file is provided (new document)
                    if (doc.file && doc.file instanceof File) {
                        const docSchema = {
                            type: {
                                rules: [ValidationRules.REQUIRED],
                                label: 'Document Type',
                            },
                        };
                        const itemErrors = validateFormUtil.validateForm(doc, docSchema);
                        if (Object.keys(itemErrors).length > 0) {
                            docErrors[index] = itemErrors;
                        }
                    }
                });
                if (docErrors.length > 0) {
                    errors.license_documents = docErrors;
                }
            }
        }

        return errors;
    };

    const handleSubmit = async (e: React.FormEvent) => {
        e.preventDefault();
        setSaving(true);
        setError("");
        setFieldErrors({});

        // Frontend validation
        const validationErrors = validateForm();
        if (Object.keys(validationErrors).length > 0) {
            setFieldErrors(validationErrors);

            // Build user-friendly error messages
            const errorMessages: string[] = [];

            Object.entries(validationErrors).forEach(([field, fieldErrors]) => {
                const friendlyName = FIELD_NAME_MAP[field] || field.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase());

                if (Array.isArray(fieldErrors)) {
                    // Check if it's an array of error objects (nested items)
                    if (fieldErrors.some((item: any) => item && typeof item === 'object')) {
                        fieldErrors.forEach((itemErrors: any, index: number) => {
                            if (itemErrors && typeof itemErrors === 'object') {
                                Object.entries(itemErrors).forEach(([subField, subErrors]) => {
                                    const subName = FIELD_NAME_MAP[subField] || subField.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase());
                                    const message = Array.isArray(subErrors) ? (subErrors as string[]).join(', ') : subErrors;
                                    errorMessages.push(`${friendlyName} #${index + 1} - ${subName}: ${message}`);
                                });
                            }
                        });
                    } else {
                        // Simple array of error strings
                        errorMessages.push(`${friendlyName}: ${(fieldErrors as string[]).join(', ')}`);
                    }
                } else if (typeof fieldErrors === 'string') {
                    errorMessages.push(`${friendlyName}: ${fieldErrors}`);
                }
            });

            const errorMsg = 'Please fix the following errors:\n\n' + errorMessages.join('\n');
            setError(errorMsg);
            toast.error('Please fix validation errors before submitting');

            // Scroll to first error
            setTimeout(() => {
                const firstErrorField = document.querySelector('.is-invalid');
                if (firstErrorField) {
                    firstErrorField.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    (firstErrorField as HTMLElement).focus();
                }
            }, 100);

            setSaving(false);
            return;
        }

        try {
            const apiPath = getMasterFormApiBase(entityName);

            // Check if formData contains any File objects (including nested).
            // NOTE: boePdfFile is intentionally excluded here — it is uploaded
            // as a separate PATCH after the main JSON save so that nested arrays
            // like item_details are not broken by multipart encoding.
            const hasFiles = () => {
                const checkForFiles = (obj: any): boolean => {
                    if (obj instanceof File) return true;
                    if (Array.isArray(obj)) {
                        return obj.some(item => checkForFiles(item));
                    }
                    if (obj && typeof obj === 'object') {
                        return Object.values(obj).some(val => checkForFiles(val));
                    }
                    return false;
                };
                return checkForFiles(formData);
            };

            let response: any;
            if (hasFiles()) {
                // Use FormData for file uploads
                const formDataObj = new FormData();

                // Helper function to append data to FormData
                const appendToFormData = (key: string, value: any, parentKey = '') => {
                    const fullKey = parentKey ? `${parentKey}.${key}` : key;

                    // Skip empty 'id' fields in nested arrays (for new items)
                    if (key === 'id' && (value === '' || value === null || value === undefined) && parentKey.includes('[')) {
                        return; // Don't append empty id fields for nested items
                    }

                    if (value instanceof File) {
                        formDataObj.append(fullKey, value);
                    } else if (Array.isArray(value)) {
                        value.forEach((item, index) => {
                            if (item instanceof File) {
                                formDataObj.append(`${fullKey}[${index}]`, item);
                            } else if (typeof item === 'object' && item !== null) {
                                Object.entries(item).forEach(([subKey, subValue]) => {
                                    appendToFormData(subKey, subValue, `${fullKey}[${index}]`);
                                });
                            } else {
                                formDataObj.append(`${fullKey}[${index}]`, item);
                            }
                        });
                    } else if (value && typeof value === 'object' && !(value instanceof Date)) {
                        Object.entries(value).forEach(([subKey, subValue]) => {
                            appendToFormData(subKey, subValue, fullKey);
                        });
                    } else if (value !== null && value !== undefined) {
                        // Allow empty strings for nested fields (important for nested arrays)
                        // Only skip truly null/undefined values
                        formDataObj.append(fullKey, value === '' ? '' : value);
                    }
                };

                Object.entries(formData).forEach(([key, value]) => {
                    // boe_pdf_copy is handled by the dedicated PATCH below — never
                    // include the existing URL string (or even a new File) here, or
                    // DRF rejects the string as "not a file".
                    if (entityName === 'bill-of-entries' && key === 'boe_pdf_copy') return;
                    appendToFormData(key, value);
                });

                if (isEdit) {
                    response = await api.patch(`${apiPath}${recordId}/`, formDataObj, {
                        headers: { 'Content-Type': 'multipart/form-data' },
                    });
                } else {
                    response = await api.post(apiPath, formDataObj, {
                        headers: { 'Content-Type': 'multipart/form-data' },
                    });
                }
            } else {
                // Use regular JSON for non-file data
                // Clean up date fields
                const cleanedFormData: Record<string, any> = { ...formData };

                // Remove audit fields (should never be sent from frontend)
                delete cleanedFormData.created_on;
                delete cleanedFormData.created_by;
                delete cleanedFormData.modified_on;
                delete cleanedFormData.modified_by;

                // boe_pdf_copy comes back from GET as a URL string. Sending it on
                // PATCH triggers DRF's "submitted data was not a file" error. The
                // dedicated multipart PATCH below handles new uploads.
                if (entityName === 'bill-of-entries') {
                    delete cleanedFormData.boe_pdf_copy;
                }

                Object.keys(cleanedFormData).forEach(key => {
                    if (key.includes('date') || key.includes('_at') || key.includes('_on')) {
                        const value = cleanedFormData[key];
                        if (value === '' || value === undefined) {
                            // Empty dates should be null
                            cleanedFormData[key] = null;
                        } else if (value instanceof Date) {
                            // Convert Date objects to YYYY-MM-DD
                            cleanedFormData[key] = formatDateForAPI(value);
                        } else if (typeof value === 'string' && value.length > 0) {
                            // Parse and reformat string dates (handles both YYYY-MM-DD and dd-MM-yyyy)
                            const date = parseDate(value);
                            if (date) {
                                cleanedFormData[key] = formatDateForAPI(date);
                            }
                        }
                    }
                });

                // Clean up nested arrays: remove empty 'id' fields for new items
                Object.keys(cleanedFormData).forEach(key => {
                    if (Array.isArray(cleanedFormData[key])) {
                        cleanedFormData[key] = cleanedFormData[key].map((item: any) => {
                            if (item && typeof item === 'object') {
                                const cleanedItem = { ...item };
                                // Remove id if it's empty string, null, or undefined
                                if (cleanedItem.id === '' || cleanedItem.id === null || cleanedItem.id === undefined) {
                                    delete cleanedItem.id;
                                }
                                return cleanedItem;
                            }
                            return item;
                        });
                    }
                });

                if (isEdit) {
                    response = await api.patch(`${apiPath}${recordId}/`, cleanedFormData);
                } else {
                    response = await api.post(apiPath, cleanedFormData);
                }
            }

            // Mark newly created items for highlighting in list
            if (!isEdit && response.data?.id) {
                markNewItemCreated(response.data.id);
            }

            // Upload the BOE PDF copy separately (as multipart PATCH) so that
            // the main JSON save above is not broken by multipart encoding of nested arrays.
            if (entityName === 'bill-of-entries' && boePdfFile) {
                const savedId = response.data?.id || recordId;
                if (savedId) {
                    try {
                        const pdfFd = new FormData();
                        pdfFd.append('boe_pdf_copy', boePdfFile, boePdfFile.name);
                        pdfFd.append('is_fetch', 'true');
                        await api.patch(`bill-of-entries/${savedId}/`, pdfFd, {
                            headers: { 'Content-Type': 'multipart/form-data' },
                        });
                    } catch {
                        // Non-critical — main BOE was saved; log silently
                        console.warn('[BOE] Failed to upload PDF copy');
                    }
                }
            }

            // Set flag to restore filters when returning to list
            sessionStorage.setItem('allotmentListFilters', JSON.stringify({
                returnTo: 'list',
                timestamp: new Date().getTime(),
            }));

            // Show success message
            toast.success(isEdit ? `${entityTitle} updated successfully` : `${entityTitle} created successfully`);

            // If modal mode, call onSuccess and onClose
            if (isModal && onSuccess) {
                const savedId = response.data?.id || recordId;
                onSuccess(savedId);
            }

            if (isModal && onClose) {
                onClose();
                return;
            }

            // Redirect based on entity type (only for non-modal)
            let redirectPath: string;
            if (entityName === 'licenses') {
                redirectPath = '/licenses';
            } else if (entityName === 'allotments') {
                // For allotments, redirect to action page after save
                const savedId = response.data.id || recordId;
                redirectPath = `/allotments/${savedId}/allocate`;
            } else if (entityName === 'bill-of-entries') {
                redirectPath = `/bill-of-entries`;
            } else if (entityName === 'trades') {
                redirectPath = `/trades`;
            } else if (entityName === 'incentive-licenses') {
                redirectPath = '/incentive-licenses';
            } else {
                redirectPath = `/masters/${entityName}`;
            }
            navigate(redirectPath);
        } catch (err: any) {
            console.error('Save error:', err.response?.data);

            // Handle field-level errors
            if (err.response?.data && typeof err.response.data === 'object') {
                // Format backend errors using utility
                const formattedErrors = validateFormUtil.formatBackendErrors(err.response.data);
                setFieldErrors(formattedErrors);

                // Create a user-friendly error message with better field names
                const errorMessages: string[] = [];

                // Helper function to get friendly field name
                const getFriendlyFieldName = (fieldPath: string) => {
                    // Handle nested paths like export_license[0].hs_code
                    const match = fieldPath.match(/^(\w+)(?:\[(\d+)\])?\.?(\w+)?/);
                    if (match) {
                        const [, mainField, index, subField] = match;
                        const mainName = FIELD_NAME_MAP[mainField] || mainField.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase());

                        if (index !== undefined && subField) {
                            const subName = FIELD_NAME_MAP[subField] || subField.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase());
                            return `${mainName} #${parseInt(index) + 1} - ${subName}`;
                        } else if (index !== undefined) {
                            return `${mainName} #${parseInt(index) + 1}`;
                        }
                        return mainName;
                    }
                    return FIELD_NAME_MAP[fieldPath] || fieldPath.replace(/_/g, ' ').replace(/\b\w/g, (l: string) => l.toUpperCase());
                };

                // Helper function to process errors recursively
                const processErrors = (errors: any, fieldPath = '') => {
                    if (Array.isArray(errors)) {
                        errors.forEach((error: any, index: number) => {
                            if (typeof error === 'object' && error !== null) {
                                // Handle nested field errors (like license_documents[0].type)
                                if (error.non_field_errors) {
                                    const friendlyName = getFriendlyFieldName(`${fieldPath}[${index}]`);
                                    errorMessages.push(`${friendlyName}: ${error.non_field_errors.join(', ')}`);
                                }
                                Object.entries(error).forEach(([key, value]) => {
                                    if (key !== 'non_field_errors') {
                                        const nestedPath = `${fieldPath}[${index}].${key}`;
                                        processErrors(value, nestedPath);
                                    }
                                });
                            } else if (typeof error === 'string') {
                                const friendlyName = getFriendlyFieldName(fieldPath);
                                errorMessages.push(`${friendlyName}: ${error}`);
                            }
                        });
                    } else if (typeof errors === 'string') {
                        const friendlyName = getFriendlyFieldName(fieldPath);
                        errorMessages.push(`${friendlyName}: ${errors}`);
                    } else if (typeof errors === 'object' && errors !== null) {
                        Object.entries(errors).forEach(([key, value]) => {
                            const nestedPath = fieldPath ? `${fieldPath}.${key}` : key;
                            processErrors(value, nestedPath);
                        });
                    }
                };

                // Handle top-level non_field_errors
                if (err.response.data.non_field_errors) {
                    errorMessages.push(...err.response.data.non_field_errors);
                }

                // Process all field errors
                Object.entries(err.response.data).forEach(([field, errors]) => {
                    if (field !== 'non_field_errors') {
                        processErrors(errors, field);
                    }
                });

                const errorMsg = errorMessages.length > 0
                    ? 'Please fix the following errors:\n\n' + errorMessages.join('\n')
                    : "Validation errors occurred. Please check the form.";
                setError(errorMsg);
                toast.error('Validation failed. Please check the form for errors.');

                // Scroll to first error
                setTimeout(() => {
                    const firstErrorField = document.querySelector('.is-invalid');
                    if (firstErrorField) {
                        firstErrorField.scrollIntoView({ behavior: 'smooth', block: 'center' });
                        (firstErrorField as HTMLElement).focus();
                    }
                }, 100);
            } else {
                // Handle other error formats
                let errorMsg = "Failed to save record";

                if (err.response?.data?.detail) {
                    errorMsg = err.response.data.detail;
                } else if (err.response?.data?.error) {
                    errorMsg = err.response.data.error;
                } else if (err.response?.data?.message) {
                    errorMsg = err.response.data.message;
                } else if (typeof err.response?.data === 'string') {
                    errorMsg = err.response.data;
                } else if (err.response?.status === 400) {
                    errorMsg = "Invalid data provided. Please check your input.";
                } else if (err.response?.status === 403) {
                    errorMsg = "You don't have permission to perform this action.";
                } else if (err.response?.status === 404) {
                    errorMsg = "Record not found.";
                } else if (err.response?.status === 500) {
                    errorMsg = "Server error occurred. Please try again or contact support.";
                } else if (err.message) {
                    errorMsg = `Error: ${err.message}`;
                }

                setError(errorMsg);
                toast.error(errorMsg);
            }
        } finally {
            setSaving(false);
        }
    };

    return { handleSubmit };
}
