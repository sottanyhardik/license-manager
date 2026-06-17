import React from 'react';
import { getFieldError } from '../utils/formErrors';
import { TriangleAlert } from "lucide-react";

const TW_INPUT = "flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none transition-[color,box-shadow] placeholder:text-muted-foreground focus-visible:border-ring aria-invalid:border-destructive";

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

  return (
    <div className={className}>
      <label className="form-label font-bold">
        {label} {required && '*'}
      </label>
      <input
        type={type}
        name={name}
        className={TW_INPUT}
        aria-invalid={!!error}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        {...props}
      />
      {error && <div className="mt-0.5 text-[11.5px] text-destructive">{error}</div>}
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

  return (
    <div className={className}>
      <label className="form-label font-bold">
        {label} {required && '*'}
      </label>
      <textarea
        name={name}
        className={TW_INPUT}
        aria-invalid={!!error}
        value={value}
        onChange={onChange}
        placeholder={placeholder}
        rows={rows}
        {...props}
      />
      {error && <div className="mt-0.5 text-[11.5px] text-destructive">{error}</div>}
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

  return (
    <div className={className}>
      <label className="form-label font-bold">
        {label} {required && '*'}
      </label>
      <select
        name={name}
        className={`${TW_INPUT} cursor-pointer`}
        aria-invalid={!!error}
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
      {error && <div className="mt-0.5 text-[11.5px] text-destructive">{error}</div>}
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
    <div className="mb-3 flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-[13px] text-destructive" role="alert">
      <TriangleAlert className="size-4 mt-0.5 shrink-0" aria-hidden="true" />
      <div>
        <strong className="font-semibold">ERROR:</strong>
        <div className="mt-0.5 font-semibold uppercase">{formattedErrors}</div>
      </div>
    </div>
  );
};

export default FormField;
