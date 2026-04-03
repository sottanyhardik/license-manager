/**
 * FormField Component
 *
 * Comprehensive reusable form field wrapper that handles all common form field types
 * with consistent styling, error handling, and accessibility.
 *
 * Features:
 * - Multiple field types: text, email, password, number, select, textarea, date, checkbox, radio
 * - Label rendering with required indicator
 * - Error display with validation states
 * - Help text support
 * - Disabled and readonly states
 * - Bootstrap styling with custom classes
 * - Accessible ARIA labels and descriptions
 * - Optional field prefix/suffix (icons, text)
 * - Character count for text fields
 * - Floating labels support
 *
 * @example
 * // Basic text input
 * <FormField
 *   label="Email"
 *   name="email"
 *   type="email"
 *   value={formData.email}
 *   onChange={(e) => setFieldValue('email', e.target.value)}
 *   error={errors.email}
 *   required
 * />
 *
 * // Select field
 * <FormField
 *   label="Country"
 *   name="country"
 *   type="select"
 *   value={formData.country}
 *   onChange={(e) => setFieldValue('country', e.target.value)}
 *   options={countries}
 *   placeholder="Select country..."
 * />
 *
 * // Textarea with character count
 * <FormField
 *   label="Description"
 *   name="description"
 *   type="textarea"
 *   value={formData.description}
 *   onChange={(e) => setFieldValue('description', e.target.value)}
 *   maxLength={500}
 *   showCharCount
 *   rows={4}
 * />
 */

import React from 'react';
import PropTypes from 'prop-types';
import { getFieldError, getFieldErrorClass } from '../../utils/formErrors';

/**
 * FormField Component
 */
export const FormField = ({
  // Field props
  label,
  name,
  type = 'text',
  value,
  onChange,
  onBlur,

  // Options for select/radio
  options = [],
  placeholder = '',

  // Validation
  error,
  errors = {}, // Alternative: pass errors object
  touched,
  required = false,

  // Layout
  className = 'col-md-6',
  labelClassName = '',
  inputClassName = '',

  // Additional features
  helpText = '',
  disabled = false,
  readOnly = false,
  prefix,
  suffix,
  showCharCount = false,
  maxLength,

  // Textarea specific
  rows = 3,

  // Checkbox/Radio specific
  checked,
  inline = false,

  // Floating label
  floating = false,

  // Custom props
  ...props
}) => {
  // Determine error message
  const fieldError = error || getFieldError(errors, name);
  const errorClass = error ? 'is-invalid' : getFieldErrorClass(errors, name);
  const showError = fieldError && (touched === undefined || touched);

  // Generate unique ID for accessibility
  const fieldId = props.id || `field-${name}`;
  const helpTextId = helpText ? `${fieldId}-help` : undefined;
  const errorId = showError ? `${fieldId}-error` : undefined;

  /**
   * Render input field
   */
  const renderInput = () => {
    const commonProps = {
      id: fieldId,
      name,
      value: value || '',
      onChange,
      onBlur,
      disabled,
      readOnly,
      className: `form-control ${errorClass} ${inputClassName}`,
      placeholder: floating ? label : placeholder,
      'aria-describedby': [helpTextId, errorId].filter(Boolean).join(' '),
      'aria-invalid': showError ? 'true' : 'false',
      'aria-required': required ? 'true' : 'false',
      maxLength,
      ...props
    };

    switch (type) {
      case 'textarea':
        return <textarea {...commonProps} rows={rows} />;

      case 'select':
        return (
          <select {...commonProps} className={`form-select ${errorClass} ${inputClassName}`}>
            {placeholder && <option value="">{placeholder}</option>}
            {options.map((option, idx) => {
              const optionValue = typeof option === 'object' ? option.value : option;
              const optionLabel = typeof option === 'object' ? option.label : option;
              const optionDisabled = typeof option === 'object' ? option.disabled : false;

              return (
                <option key={idx} value={optionValue} disabled={optionDisabled}>
                  {optionLabel}
                </option>
              );
            })}
          </select>
        );

      case 'checkbox':
        return (
          <div className={`form-check ${inline ? 'form-check-inline' : ''}`}>
            <input
              type="checkbox"
              id={fieldId}
              name={name}
              checked={checked !== undefined ? checked : value}
              onChange={onChange}
              onBlur={onBlur}
              disabled={disabled}
              className={`form-check-input ${errorClass} ${inputClassName}`}
              aria-describedby={[helpTextId, errorId].filter(Boolean).join(' ')}
              aria-invalid={showError ? 'true' : 'false'}
              {...props}
            />
            <label className="form-check-label" htmlFor={fieldId}>
              {label} {required && <span className="text-danger">*</span>}
            </label>
          </div>
        );

      case 'radio':
        return (
          <div>
            {options.map((option, idx) => {
              const optionValue = typeof option === 'object' ? option.value : option;
              const optionLabel = typeof option === 'object' ? option.label : option;
              const radioId = `${fieldId}-${idx}`;

              return (
                <div key={idx} className={`form-check ${inline ? 'form-check-inline' : ''}`}>
                  <input
                    type="radio"
                    id={radioId}
                    name={name}
                    value={optionValue}
                    checked={value === optionValue}
                    onChange={onChange}
                    onBlur={onBlur}
                    disabled={disabled}
                    className={`form-check-input ${errorClass} ${inputClassName}`}
                    aria-describedby={[helpTextId, errorId].filter(Boolean).join(' ')}
                    {...props}
                  />
                  <label className="form-check-label" htmlFor={radioId}>
                    {optionLabel}
                  </label>
                </div>
              );
            })}
          </div>
        );

      default:
        return <input type={type} {...commonProps} />;
    }
  };

  /**
   * Render field with prefix/suffix
   */
  const renderInputGroup = () => {
    if (!prefix && !suffix) {
      return renderInput();
    }

    return (
      <div className="input-group">
        {prefix && (
          <span className="input-group-text">
            {typeof prefix === 'string' && prefix.startsWith('bi-') ? (
              <i className={`bi ${prefix}`} />
            ) : (
              prefix
            )}
          </span>
        )}
        {renderInput()}
        {suffix && (
          <span className="input-group-text">
            {typeof suffix === 'string' && suffix.startsWith('bi-') ? (
              <i className={`bi ${suffix}`} />
            ) : (
              suffix
            )}
          </span>
        )}
      </div>
    );
  };

  // Checkbox and radio have different layout
  if (type === 'checkbox' || type === 'radio') {
    return (
      <div className={className}>
        {renderInput()}
        {helpText && (
          <div id={helpTextId} className="form-text">
            {helpText}
          </div>
        )}
        {showError && (
          <div id={errorId} className="invalid-feedback d-block">
            {fieldError}
          </div>
        )}
      </div>
    );
  }

  // Floating label layout
  if (floating) {
    return (
      <div className={className}>
        <div className="form-floating">
          {renderInputGroup()}
          <label htmlFor={fieldId}>
            {label} {required && <span className="text-danger">*</span>}
          </label>
        </div>
        {helpText && (
          <div id={helpTextId} className="form-text mt-1">
            {helpText}
          </div>
        )}
        {showCharCount && maxLength && (
          <div className="form-text text-end small">
            {(value || '').length} / {maxLength}
          </div>
        )}
        {showError && (
          <div id={errorId} className="invalid-feedback d-block">
            {fieldError}
          </div>
        )}
      </div>
    );
  }

  // Standard layout
  return (
    <div className={className}>
      {label && (
        <label htmlFor={fieldId} className={`form-label fw-bold ${labelClassName}`}>
          {label} {required && <span className="text-danger">*</span>}
        </label>
      )}
      {renderInputGroup()}
      {helpText && (
        <div id={helpTextId} className="form-text">
          {helpText}
        </div>
      )}
      {showCharCount && maxLength && (
        <div className="form-text text-end small">
          {(value || '').length} / {maxLength}
        </div>
      )}
      {showError && (
        <div id={errorId} className="invalid-feedback d-block">
          {fieldError}
        </div>
      )}
    </div>
  );
};

FormField.propTypes = {
  /** Field label */
  label: PropTypes.string,
  /** Field name */
  name: PropTypes.string.isRequired,
  /** Field type */
  type: PropTypes.oneOf([
    'text',
    'email',
    'password',
    'number',
    'tel',
    'url',
    'date',
    'datetime-local',
    'time',
    'month',
    'week',
    'color',
    'select',
    'textarea',
    'checkbox',
    'radio'
  ]),
  /** Field value */
  value: PropTypes.any,
  /** Change handler */
  onChange: PropTypes.func,
  /** Blur handler */
  onBlur: PropTypes.func,
  /** Options for select/radio fields */
  options: PropTypes.arrayOf(
    PropTypes.oneOfType([
      PropTypes.string,
      PropTypes.number,
      PropTypes.shape({
        value: PropTypes.any.isRequired,
        label: PropTypes.string.isRequired,
        disabled: PropTypes.bool
      })
    ])
  ),
  /** Placeholder text */
  placeholder: PropTypes.string,
  /** Error message */
  error: PropTypes.string,
  /** Errors object (alternative to error prop) */
  errors: PropTypes.object,
  /** Whether field is touched */
  touched: PropTypes.bool,
  /** Required field */
  required: PropTypes.bool,
  /** Container class */
  className: PropTypes.string,
  /** Label class */
  labelClassName: PropTypes.string,
  /** Input class */
  inputClassName: PropTypes.string,
  /** Help text */
  helpText: PropTypes.string,
  /** Disabled state */
  disabled: PropTypes.bool,
  /** Read-only state */
  readOnly: PropTypes.bool,
  /** Prefix element or icon */
  prefix: PropTypes.node,
  /** Suffix element or icon */
  suffix: PropTypes.node,
  /** Show character count */
  showCharCount: PropTypes.bool,
  /** Maximum length */
  maxLength: PropTypes.number,
  /** Textarea rows */
  rows: PropTypes.number,
  /** Checkbox checked state */
  checked: PropTypes.bool,
  /** Inline layout for checkbox/radio */
  inline: PropTypes.bool,
  /** Floating label */
  floating: PropTypes.bool,
  /** Field ID */
  id: PropTypes.string
};

/**
 * FormTextArea - Shorthand for textarea field
 */
export const FormTextArea = (props) => <FormField type="textarea" {...props} />;

/**
 * FormSelect - Shorthand for select field
 */
export const FormSelect = (props) => <FormField type="select" {...props} />;

/**
 * FormCheckbox - Shorthand for checkbox field
 */
export const FormCheckbox = (props) => <FormField type="checkbox" {...props} />;

/**
 * FormRadio - Shorthand for radio field
 */
export const FormRadio = (props) => <FormField type="radio" {...props} />;

/**
 * FormGroup - Group multiple fields together
 */
export const FormGroup = ({ title, children, className = 'mb-4' }) => (
  <div className={className}>
    {title && <h6 className="mb-3 fw-bold text-secondary">{title}</h6>}
    <div className="row g-3">{children}</div>
  </div>
);

FormGroup.propTypes = {
  title: PropTypes.string,
  children: PropTypes.node,
  className: PropTypes.string
};

export default FormField;
