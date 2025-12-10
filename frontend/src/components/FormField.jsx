import React from 'react';
import { getFieldError, getFieldErrorClass } from '../utils/formErrors';

/**
 * Reusable form field component with error handling
 */
export const FormField = ({
  label,
  name,
  type = 'text',
  value,
  onChange,
  fieldErrors = {},
  required = false,
  placeholder = '',
  className = 'col-md-6',
  ...props
}) => {
  const error = getFieldError(fieldErrors, name);
  const errorClass = getFieldErrorClass(fieldErrors, name);

  return (
    <div className={className}>
      <label className="form-label fw-bold">
        {label} {required && '*'}
      </label>
      <input
        type={type}
        name={name}
        className={`form-control ${errorClass}`}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        {...props}
      />
      {error && (
        <div className="invalid-feedback">{error}</div>
      )}
    </div>
  );
};

/**
 * Form textarea field with error handling
 */
export const FormTextArea = ({
  label,
  name,
  value,
  onChange,
  fieldErrors = {},
  required = false,
  placeholder = '',
  rows = 3,
  className = 'col-md-12',
  ...props
}) => {
  const error = getFieldError(fieldErrors, name);
  const errorClass = getFieldErrorClass(fieldErrors, name);

  return (
    <div className={className}>
      <label className="form-label fw-bold">
        {label} {required && '*'}
      </label>
      <textarea
        name={name}
        className={`form-control ${errorClass}`}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        rows={rows}
        {...props}
      />
      {error && (
        <div className="invalid-feedback">{error}</div>
      )}
    </div>
  );
};

/**
 * Form select field with error handling
 */
export const FormSelect = ({
  label,
  name,
  value,
  onChange,
  options = [],
  fieldErrors = {},
  required = false,
  className = 'col-md-6',
  ...props
}) => {
  const error = getFieldError(fieldErrors, name);
  const errorClass = getFieldErrorClass(fieldErrors, name);

  return (
    <div className={className}>
      <label className="form-label fw-bold">
        {label} {required && '*'}
      </label>
      <select
        name={name}
        className={`form-select ${errorClass}`}
        value={value}
        onChange={onChange}
        {...props}
      >
        {options.map((option, idx) => (
          <option key={idx} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {error && (
        <div className="invalid-feedback">{error}</div>
      )}
    </div>
  );
};

/**
 * Non-field errors alert component
 */
export const NonFieldErrors = ({ errors = [], formatFunction }) => {
  if (!errors || errors.length === 0) return null;

  const formattedErrors = formatFunction ? formatFunction(errors) : errors.join(' | ');

  return (
    <div className="alert alert-danger mb-3" role="alert">
      <strong><i className="bi bi-exclamation-triangle-fill me-2"></i>ERROR:</strong>
      <div className="mt-1" style={{ textTransform: 'uppercase', fontWeight: '600' }}>
        {formattedErrors}
      </div>
    </div>
  );
};

export default FormField;
