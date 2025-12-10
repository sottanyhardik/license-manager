/**
 * Utility functions for handling form errors from Django REST Framework
 */

/**
 * Extract field errors and non-field errors from DRF error response
 * @param {Object} errorResponse - The error response from axios
 * @returns {Object} { fieldErrors: {}, nonFieldErrors: [] }
 */
export const extractFormErrors = (errorResponse) => {
  const fieldErrors = {};
  let nonFieldErrors = [];

  if (!errorResponse || !errorResponse.response || !errorResponse.response.data) {
    return { fieldErrors, nonFieldErrors };
  }

  const data = errorResponse.response.data;

  // Handle DRF error format
  Object.keys(data).forEach(key => {
    if (key === 'non_field_errors' || key === 'detail') {
      // Non-field errors
      const errors = Array.isArray(data[key]) ? data[key] : [data[key]];
      nonFieldErrors = [...nonFieldErrors, ...errors];
    } else if (key === 'error') {
      // Generic error message
      nonFieldErrors.push(data[key]);
    } else {
      // Field-specific errors
      const errors = Array.isArray(data[key]) ? data[key] : [data[key]];
      fieldErrors[key] = errors.join(', ');
    }
  });

  return { fieldErrors, nonFieldErrors };
};

/**
 * Format non-field errors for display (capitalize text)
 * @param {Array} errors - Array of error messages
 * @returns {string} - Formatted error message
 */
export const formatNonFieldErrors = (errors) => {
  if (!errors || errors.length === 0) return '';
  return errors.map(err => String(err).toUpperCase()).join(' | ');
};

/**
 * Check if a field has an error
 * @param {Object} fieldErrors - Field errors object
 * @param {string} fieldName - Name of the field
 * @returns {boolean}
 */
export const hasFieldError = (fieldErrors, fieldName) => {
  return fieldErrors && fieldErrors[fieldName];
};

/**
 * Get error message for a field
 * @param {Object} fieldErrors - Field errors object
 * @param {string} fieldName - Name of the field
 * @returns {string|null}
 */
export const getFieldError = (fieldErrors, fieldName) => {
  return fieldErrors && fieldErrors[fieldName] ? fieldErrors[fieldName] : null;
};

/**
 * Get CSS class for form field based on error state
 * @param {Object} fieldErrors - Field errors object
 * @param {string} fieldName - Name of the field
 * @returns {string} - CSS class name
 */
export const getFieldErrorClass = (fieldErrors, fieldName) => {
  return hasFieldError(fieldErrors, fieldName) ? 'is-invalid' : '';
};
