/**
 * Comprehensive Form Validation Utility
 * Provides robust validation functions for all form types
 */

/**
 * Validation Rules
 */
export const ValidationRules = {
    REQUIRED: 'required',
    EMAIL: 'email',
    NUMBER: 'number',
    POSITIVE_NUMBER: 'positive_number',
    NON_NEGATIVE: 'non_negative',
    MIN_LENGTH: 'min_length',
    MAX_LENGTH: 'max_length',
    MIN_VALUE: 'min_value',
    MAX_VALUE: 'max_value',
    DATE: 'date',
    FUTURE_DATE: 'future_date',
    PAST_DATE: 'past_date',
    PHONE: 'phone',
    URL: 'url',
    ALPHANUMERIC: 'alphanumeric',
    DECIMAL: 'decimal',
    INTEGER: 'integer',
    CUSTOM: 'custom'
};

/**
 * Validate a single field value against rules
 * @param {*} value - Field value to validate
 * @param {Array|Object} rules - Validation rules
 * @param {string} fieldLabel - Human-readable field name
 * @returns {Array} Array of error messages (empty if valid)
 */
export function validateField(value, rules, fieldLabel = 'This field') {
    const errors = [];

    // Convert single rule to array
    if (!Array.isArray(rules)) {
        rules = [rules];
    }

    for (const rule of rules) {
        let ruleType = rule;
        let ruleValue = null;
        let customMessage = null;

        // Handle rule objects with parameters
        if (typeof rule === 'object' && rule !== null) {
            ruleType = rule.type;
            ruleValue = rule.value;
            customMessage = rule.message;
        }

        let error = null;

        switch (ruleType) {
            case ValidationRules.REQUIRED:
                if (value === null || value === undefined || value === '' ||
                    (Array.isArray(value) && value.length === 0) ||
                    (typeof value === 'string' && value.trim() === '')) {
                    error = customMessage || `${fieldLabel} is required`;
                }
                break;

            case ValidationRules.EMAIL:
                if (value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
                    error = customMessage || `${fieldLabel} must be a valid email address`;
                }
                break;

            case ValidationRules.NUMBER:
                if (value !== '' && value !== null && value !== undefined && isNaN(Number(value))) {
                    error = customMessage || `${fieldLabel} must be a number`;
                }
                break;

            case ValidationRules.POSITIVE_NUMBER:
                if (value !== '' && value !== null && value !== undefined) {
                    const num = Number(value);
                    if (isNaN(num) || num <= 0) {
                        error = customMessage || `${fieldLabel} must be a positive number`;
                    }
                }
                break;

            case ValidationRules.NON_NEGATIVE:
                if (value !== '' && value !== null && value !== undefined) {
                    const num = Number(value);
                    if (isNaN(num) || num < 0) {
                        error = customMessage || `${fieldLabel} cannot be negative`;
                    }
                }
                break;

            case ValidationRules.INTEGER:
                if (value !== '' && value !== null && value !== undefined) {
                    const num = Number(value);
                    if (isNaN(num) || !Number.isInteger(num)) {
                        error = customMessage || `${fieldLabel} must be an integer`;
                    }
                }
                break;

            case ValidationRules.DECIMAL:
                if (value !== '' && value !== null && value !== undefined) {
                    if (!/^-?\d+(\.\d+)?$/.test(String(value))) {
                        error = customMessage || `${fieldLabel} must be a valid decimal number`;
                    }
                }
                break;

            case ValidationRules.MIN_LENGTH:
                if (value && String(value).length < ruleValue) {
                    error = customMessage || `${fieldLabel} must be at least ${ruleValue} characters`;
                }
                break;

            case ValidationRules.MAX_LENGTH:
                if (value && String(value).length > ruleValue) {
                    error = customMessage || `${fieldLabel} must not exceed ${ruleValue} characters`;
                }
                break;

            case ValidationRules.MIN_VALUE:
                if (value !== '' && value !== null && value !== undefined) {
                    const num = Number(value);
                    if (!isNaN(num) && num < ruleValue) {
                        error = customMessage || `${fieldLabel} must be at least ${ruleValue}`;
                    }
                }
                break;

            case ValidationRules.MAX_VALUE:
                if (value !== '' && value !== null && value !== undefined) {
                    const num = Number(value);
                    if (!isNaN(num) && num > ruleValue) {
                        error = customMessage || `${fieldLabel} must not exceed ${ruleValue}`;
                    }
                }
                break;

            case ValidationRules.DATE:
                if (value && !(value instanceof Date) && isNaN(Date.parse(value))) {
                    error = customMessage || `${fieldLabel} must be a valid date`;
                }
                break;

            case ValidationRules.FUTURE_DATE:
                if (value) {
                    const date = new Date(value);
                    const today = new Date();
                    today.setHours(0, 0, 0, 0);
                    if (date < today) {
                        error = customMessage || `${fieldLabel} must be a future date`;
                    }
                }
                break;

            case ValidationRules.PAST_DATE:
                if (value) {
                    const date = new Date(value);
                    const today = new Date();
                    today.setHours(23, 59, 59, 999);
                    if (date > today) {
                        error = customMessage || `${fieldLabel} must be a past date`;
                    }
                }
                break;

            case ValidationRules.PHONE:
                if (value && !/^[+]?[\d\s\-()]{10,}$/.test(value)) {
                    error = customMessage || `${fieldLabel} must be a valid phone number`;
                }
                break;

            case ValidationRules.URL:
                if (value) {
                    try {
                        new URL(value);
                    } catch {
                        error = customMessage || `${fieldLabel} must be a valid URL`;
                    }
                }
                break;

            case ValidationRules.ALPHANUMERIC:
                if (value && !/^[a-zA-Z0-9]+$/.test(value)) {
                    error = customMessage || `${fieldLabel} must contain only letters and numbers`;
                }
                break;

            case ValidationRules.CUSTOM:
                if (ruleValue && typeof ruleValue === 'function') {
                    const customError = ruleValue(value);
                    if (customError) {
                        error = customMessage || customError;
                    }
                }
                break;

            default:
                console.warn(`Unknown validation rule: ${ruleType}`);
        }

        if (error) {
            errors.push(error);
        }
    }

    return errors;
}

/**
 * Validate entire form
 * @param {Object} formData - Form data object
 * @param {Object} validationSchema - Schema defining validation rules for each field
 * @returns {Object} Object with field names as keys and error arrays as values
 */
export function validateForm(formData, validationSchema) {
    const errors = {};

    Object.keys(validationSchema).forEach(fieldName => {
        const fieldConfig = validationSchema[fieldName];
        const fieldValue = formData[fieldName];

        let rules = fieldConfig.rules || fieldConfig;
        let label = fieldConfig.label || fieldName.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase());

        const fieldErrors = validateField(fieldValue, rules, label);

        if (fieldErrors.length > 0) {
            errors[fieldName] = fieldErrors;
        }
    });

    return errors;
}

/**
 * Validate nested array of objects (like line items)
 * @param {Array} items - Array of items to validate
 * @param {Object} itemSchema - Validation schema for each item
 * @returns {Array} Array of error objects (one per item)
 */
export function validateNestedArray(items, itemSchema) {
    const errors = [];

    if (!Array.isArray(items)) {
        return errors;
    }

    items.forEach((item, index) => {
        const itemErrors = validateForm(item, itemSchema);
        if (Object.keys(itemErrors).length > 0) {
            errors[index] = itemErrors;
        }
    });

    return errors;
}

/**
 * Format backend error response into frontend error structure
 * @param {Object} backendErrors - Error response from backend
 * @returns {Object} Formatted errors object
 */
export function formatBackendErrors(backendErrors) {
    const formattedErrors = {};

    if (!backendErrors || typeof backendErrors !== 'object') {
        return formattedErrors;
    }

    // Handle Django REST Framework error format
    Object.keys(backendErrors).forEach(field => {
        const fieldError = backendErrors[field];

        if (Array.isArray(fieldError)) {
            formattedErrors[field] = fieldError;
        } else if (typeof fieldError === 'string') {
            formattedErrors[field] = [fieldError];
        } else if (typeof fieldError === 'object') {
            // Handle nested errors
            formattedErrors[field] = formatBackendErrors(fieldError);
        }
    });

    return formattedErrors;
}

/**
 * Get first error message from errors object
 * @param {Object} errors - Errors object
 * @returns {string|null} First error message or null
 */
export function getFirstError(errors) {
    if (!errors || typeof errors !== 'object') {
        return null;
    }

    for (const field in errors) {
        const fieldErrors = errors[field];
        if (Array.isArray(fieldErrors) && fieldErrors.length > 0) {
            return fieldErrors[0];
        } else if (typeof fieldErrors === 'object') {
            const nestedError = getFirstError(fieldErrors);
            if (nestedError) return nestedError;
        }
    }

    return null;
}

/**
 * Check if form has any errors
 * @param {Object} errors - Errors object
 * @returns {boolean} True if there are errors
 */
export function hasErrors(errors) {
    if (!errors || typeof errors !== 'object') {
        return false;
    }

    return Object.keys(errors).some(field => {
        const fieldErrors = errors[field];
        if (Array.isArray(fieldErrors)) {
            return fieldErrors.length > 0;
        } else if (typeof fieldErrors === 'object') {
            return hasErrors(fieldErrors);
        }
        return false;
    });
}

/**
 * Display all validation errors as toast messages
 * @param {Object} errors - Errors object
 * @param {Function} toastFn - Toast function (e.g., toast.error)
 */
export function displayValidationErrors(errors, toastFn) {
    const flattenErrors = (errorsObj, prefix = '') => {
        const messages = [];

        Object.keys(errorsObj).forEach(field => {
            const fieldErrors = errorsObj[field];
            const fieldLabel = prefix ? `${prefix}.${field}` : field;

            if (Array.isArray(fieldErrors)) {
                fieldErrors.forEach(error => {
                    messages.push(`${fieldLabel}: ${error}`);
                });
            } else if (typeof fieldErrors === 'object') {
                messages.push(...flattenErrors(fieldErrors, fieldLabel));
            }
        });

        return messages;
    };

    const errorMessages = flattenErrors(errors);

    if (errorMessages.length > 0) {
        // Display first 5 errors
        errorMessages.slice(0, 5).forEach(msg => {
            toastFn(msg);
        });

        if (errorMessages.length > 5) {
            toastFn(`And ${errorMessages.length - 5} more errors...`);
        }
    }
}
