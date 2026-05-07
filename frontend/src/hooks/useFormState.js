/**
 * useFormState Hook
 *
 * Comprehensive form state management hook that handles all aspects of form state,
 * validation, unsaved changes tracking, and browser warnings.
 *
 * Features:
 * - Form data state management
 * - Field-level and form-level errors
 * - Unsaved changes detection
 * - Browser beforeunload warning
 * - Initial data comparison
 * - Field update helpers
 * - Form reset functionality
 * - Validation support (sync and async)
 * - Dirty state tracking per field
 *
 * @example
 * const {
 *   formData,
 *   errors,
 *   touched,
 *   isDirty,
 *   isValid,
 *   handleChange,
 *   handleBlur,
 *   setFieldValue,
 *   setFieldError,
 *   validateForm,
 *   resetForm,
 *   setFormData
 * } = useFormState(initialValues, {
 *   validate: (values) => {
 *     const errors = {};
 *     if (!values.email) errors.email = 'Email is required';
 *     return errors;
 *   },
 *   onSubmit: async (values) => {
 *     await api.post('/users', values);
 *   },
 *   enableReinitialize: true,
 *   warnBeforeUnload: true
 * });
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import PropTypes from 'prop-types';

/**
 * Compare two objects for equality
 */
const isEqual = (obj1, obj2) => {
  return JSON.stringify(obj1) === JSON.stringify(obj2);
};

/**
 * Deep clone an object
 */
const deepClone = (obj) => {
  if (obj === null || typeof obj !== 'object') return obj;
  return JSON.parse(JSON.stringify(obj));
};

/**
 * useFormState Hook
 *
 * @param {Object} initialValues - Initial form values
 * @param {Object} options - Configuration options
 * @param {Function} options.validate - Validation function that returns errors object
 * @param {Function} options.validateOnChange - Validate on field change (default: false)
 * @param {Function} options.validateOnBlur - Validate on field blur (default: true)
 * @param {boolean} options.enableReinitialize - Reset form when initialValues change (default: false)
 * @param {boolean} options.warnBeforeUnload - Warn user before leaving with unsaved changes (default: false)
 * @param {string} options.beforeUnloadMessage - Custom warning message
 * @returns {Object} Form state and handlers
 */
export const useFormState = (initialValues = {}, options = {}) => {
  const {
    validate,
    validateOnChange = false,
    validateOnBlur = true,
    enableReinitialize = false,
    warnBeforeUnload = false,
    beforeUnloadMessage = 'You have unsaved changes. Are you sure you want to leave?'
  } = options;

  // Store initial values reference
  const initialValuesRef = useRef(deepClone(initialValues));

  // Form state
  const [formData, setFormData] = useState(deepClone(initialValues));
  const [errors, setErrors] = useState({});
  const [touched, setTouched] = useState({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isValidating, setIsValidating] = useState(false);

  /**
   * Calculate if form has unsaved changes
   */
  const isDirty = !isEqual(formData, initialValuesRef.current);

  /**
   * Calculate if form is valid (no errors)
   */
  const isValid = Object.keys(errors).length === 0;

  /**
   * Validate entire form
   */
  const validateForm = useCallback(async (values = formData) => {
    if (!validate) return {};

    setIsValidating(true);
    try {
      const validationErrors = await Promise.resolve(validate(values));
      setErrors(validationErrors || {});
      return validationErrors || {};
    } catch (error) {
      console.error('Validation error:', error);
      return {};
    } finally {
      setIsValidating(false);
    }
  }, [validate, formData]);

  /**
   * Validate a single field
   */
  const validateField = useCallback(async (fieldName, value) => {
    if (!validate) return null;

    const testValues = { ...formData, [fieldName]: value };
    const validationErrors = await Promise.resolve(validate(testValues));

    return validationErrors[fieldName] || null;
  }, [validate, formData]);

  /**
   * Set value for a specific field
   */
  const setFieldValue = useCallback(async (fieldName, value) => {
    setFormData(prev => ({ ...prev, [fieldName]: value }));

    // Clear field error when value changes
    if (errors[fieldName]) {
      setErrors(prev => {
        const next = { ...prev };
        delete next[fieldName];
        return next;
      });
    }

    // Validate on change if enabled
    if (validateOnChange && validate) {
      const fieldError = await validateField(fieldName, value);
      if (fieldError) {
        setErrors(prev => ({ ...prev, [fieldName]: fieldError }));
      }
    }
  }, [errors, validateOnChange, validate, validateField]);

  /**
   * Set error for a specific field
   */
  const setFieldError = useCallback((fieldName, error) => {
    if (error) {
      setErrors(prev => ({ ...prev, [fieldName]: error }));
    } else {
      setErrors(prev => {
        const next = { ...prev };
        delete next[fieldName];
        return next;
      });
    }
  }, []);

  /**
   * Set multiple errors at once
   */
  const setFieldErrors = useCallback((errorObj) => {
    setErrors(prev => ({ ...prev, ...errorObj }));
  }, []);

  /**
   * Mark field as touched
   */
  const setFieldTouched = useCallback((fieldName, isTouched = true) => {
    setTouched(prev => ({ ...prev, [fieldName]: isTouched }));
  }, []);

  /**
   * Handle field change event
   */
  const handleChange = useCallback(async (e) => {
    const { name, value, type, checked } = e.target;
    const fieldValue = type === 'checkbox' ? checked : value;

    await setFieldValue(name, fieldValue);
  }, [setFieldValue]);

  /**
   * Handle field blur event
   */
  const handleBlur = useCallback(async (e) => {
    const { name, value } = e.target;

    setFieldTouched(name, true);

    // Validate on blur if enabled
    if (validateOnBlur && validate) {
      const fieldError = await validateField(name, value);
      if (fieldError) {
        setErrors(prev => ({ ...prev, [name]: fieldError }));
      }
    }
  }, [validateOnBlur, validate, validateField, setFieldTouched]);

  /**
   * Reset form to initial values
   */
  const resetForm = useCallback((newValues) => {
    const valuesToReset = newValues !== undefined ? newValues : initialValuesRef.current;

    setFormData(deepClone(valuesToReset));
    setErrors({});
    setTouched({});
    setIsSubmitting(false);

    if (newValues !== undefined) {
      initialValuesRef.current = deepClone(newValues);
    }
  }, []);

  /**
   * Set entire form data at once
   */
  const setFormDataBulk = useCallback((newData, shouldValidate = false) => {
    setFormData(deepClone(newData));

    if (shouldValidate && validate) {
      validateForm(newData);
    }
  }, [validate, validateForm]);

  /**
   * Set multiple field values at once
   */
  const setFieldValues = useCallback((values) => {
    setFormData(prev => ({ ...prev, ...values }));
  }, []);

  /**
   * Get field props helper
   * Returns props to spread on form inputs
   */
  const getFieldProps = useCallback((fieldName) => {
    return {
      name: fieldName,
      value: formData[fieldName] || '',
      onChange: handleChange,
      onBlur: handleBlur
    };
  }, [formData, handleChange, handleBlur]);

  /**
   * Get field meta helper
   * Returns metadata about field state
   */
  const getFieldMeta = useCallback((fieldName) => {
    return {
      value: formData[fieldName],
      error: errors[fieldName],
      touched: touched[fieldName] || false,
      initialValue: initialValuesRef.current[fieldName]
    };
  }, [formData, errors, touched]);

  /**
   * Get field helpers
   * Returns helper functions for a field
   */
  const getFieldHelpers = useCallback((fieldName) => {
    return {
      setValue: (value) => setFieldValue(fieldName, value),
      setTouched: (isTouched) => setFieldTouched(fieldName, isTouched),
      setError: (error) => setFieldError(fieldName, error)
    };
  }, [setFieldValue, setFieldTouched, setFieldError]);

  /**
   * Submit handler
   */
  const handleSubmit = useCallback(async (onSubmit) => {
    return async (e) => {
      if (e) {
        e.preventDefault();
      }

      // Mark all fields as touched
      const allTouched = Object.keys(formData).reduce((acc, key) => {
        acc[key] = true;
        return acc;
      }, {});
      setTouched(allTouched);

      // Validate form
      const validationErrors = await validateForm();

      if (Object.keys(validationErrors).length > 0) {
        return { success: false, errors: validationErrors };
      }

      // Submit
      setIsSubmitting(true);
      try {
        const result = await onSubmit(formData);

        // Reset initial values on successful submit
        initialValuesRef.current = deepClone(formData);

        return { success: true, data: result };
      } catch (error) {
        return { success: false, error };
      } finally {
        setIsSubmitting(false);
      }
    };
  }, [formData, validateForm]);

  /**
   * Reinitialize form when initial values change
   */
  useEffect(() => {
    if (enableReinitialize && !isEqual(initialValues, initialValuesRef.current)) {
      resetForm(initialValues);
    }
  }, [initialValues, enableReinitialize, resetForm]);

  /**
   * Warn before unload if form has unsaved changes
   */
  useEffect(() => {
    if (!warnBeforeUnload) return;

    const handleBeforeUnload = (e) => {
      if (isDirty) {
        e.preventDefault();
        e.returnValue = beforeUnloadMessage;
        return beforeUnloadMessage;
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);

    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, [isDirty, warnBeforeUnload, beforeUnloadMessage]);

  return {
    // Form data
    formData,
    setFormData: setFormDataBulk,

    // Field operations
    setFieldValue,
    setFieldValues,
    setFieldError,
    setFieldErrors,
    setFieldTouched,

    // Errors
    errors,
    setErrors,

    // Touched
    touched,
    setTouched,

    // Validation
    validateForm,
    validateField,
    isValid,
    isValidating,

    // Form state
    isDirty,
    isSubmitting,
    setIsSubmitting,

    // Handlers
    handleChange,
    handleBlur,
    handleSubmit,

    // Helpers
    getFieldProps,
    getFieldMeta,
    getFieldHelpers,

    // Reset
    resetForm
  };
};

// PropTypes for documentation
useFormState.propTypes = {
  initialValues: PropTypes.object,
  options: PropTypes.shape({
    validate: PropTypes.func,
    validateOnChange: PropTypes.bool,
    validateOnBlur: PropTypes.bool,
    enableReinitialize: PropTypes.bool,
    warnBeforeUnload: PropTypes.bool,
    beforeUnloadMessage: PropTypes.string
  })
};

export default useFormState;
