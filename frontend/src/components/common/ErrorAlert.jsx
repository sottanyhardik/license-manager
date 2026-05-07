/**
 * ErrorAlert Component
 *
 * Reusable alert component for displaying errors, warnings, success messages, and info.
 * Provides consistent feedback across the application with support for dismissal,
 * icons, custom actions, and multiple severity levels.
 *
 * Features:
 * - Multiple severity levels: error, warning, info, success
 * - Dismissible option with close button
 * - Icon support (Bootstrap Icons)
 * - Title and message support
 * - Custom actions/buttons
 * - Auto-dismiss after timeout
 * - List of errors display
 * - Variant styles (standard, filled, outlined)
 *
 * @example
 * // Basic error
 * <ErrorAlert severity="error" message="Something went wrong" />
 *
 * // With title and dismissible
 * <ErrorAlert
 *   severity="warning"
 *   title="Warning"
 *   message="This action cannot be undone"
 *   dismissible
 *   onDismiss={() => console.log('dismissed')}
 * />
 *
 * // With multiple errors
 * <ErrorAlert
 *   severity="error"
 *   title="Validation Errors"
 *   errors={['Email is required', 'Password is too short']}
 * />
 *
 * // With custom action
 * <ErrorAlert
 *   severity="info"
 *   message="Your session is about to expire"
 *   action={<button className="btn btn-sm btn-light">Extend Session</button>}
 * />
 */

import React, { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';

/**
 * Get icon class for severity level
 */
const getIcon = (severity) => {
  const iconMap = {
    error: 'bi-x-circle-fill',
    danger: 'bi-x-circle-fill',
    warning: 'bi-exclamation-triangle-fill',
    info: 'bi-info-circle-fill',
    success: 'bi-check-circle-fill'
  };
  return iconMap[severity] || iconMap.info;
};

/**
 * Get Bootstrap alert class for severity
 */
const getAlertClass = (severity, variant) => {
  const normalizedSeverity = severity === 'error' ? 'danger' : severity;

  if (variant === 'filled') {
    return `alert-${normalizedSeverity}`;
  } else if (variant === 'outlined') {
    return `alert-outline-${normalizedSeverity} border border-${normalizedSeverity}`;
  }
  return `alert-${normalizedSeverity}`;
};

/**
 * ErrorAlert Component
 */
export const ErrorAlert = ({
  severity = 'error',
  title = '',
  message = '',
  errors = [],
  dismissible = false,
  onDismiss,
  showIcon = true,
  icon,
  action,
  variant = 'filled',
  autoDismiss = false,
  autoDismissTimeout = 5000,
  className = '',
  style = {},
  children,
  ...props
}) => {
  const [visible, setVisible] = useState(true);

  const handleDismiss = useCallback(() => {
    setVisible(false);
    if (onDismiss) {
      onDismiss();
    }
  }, [onDismiss]);

  // Auto dismiss
  useEffect(() => {
    if (autoDismiss && visible) {
      const timer = setTimeout(() => {
        handleDismiss();
      }, autoDismissTimeout);

      return () => clearTimeout(timer);
    }
  }, [autoDismiss, autoDismissTimeout, visible, handleDismiss]);

  if (!visible) {
    return null;
  }

  // Don't render if no content
  if (!message && !title && errors.length === 0 && !children) {
    return null;
  }

  const alertIcon = icon || getIcon(severity);
  const alertClass = getAlertClass(severity, variant);

  return (
    <div
      className={`alert ${alertClass} ${dismissible ? 'alert-dismissible fade show' : ''} ${className}`}
      role="alert"
      style={style}
      {...props}
    >
      <div className="d-flex align-items-start">
        {/* Icon */}
        {showIcon && (
          <div className="me-2">
            <i className={`bi ${alertIcon} fs-5`} aria-hidden="true" />
          </div>
        )}

        {/* Content */}
        <div className="flex-grow-1">
          {/* Title */}
          {title && (
            <h6 className="alert-heading mb-1 fw-bold">
              {title}
            </h6>
          )}

          {/* Message */}
          {message && (
            <div className={title ? 'mt-1' : ''}>{message}</div>
          )}

          {/* Error list */}
          {errors.length > 0 && (
            <ul className={`mb-0 ${message || title ? 'mt-2' : ''}`}>
              {errors.map((error, index) => (
                <li key={index}>{error}</li>
              ))}
            </ul>
          )}

          {/* Children */}
          {children && (
            <div className={message || title || errors.length > 0 ? 'mt-2' : ''}>
              {children}
            </div>
          )}

          {/* Action */}
          {action && (
            <div className="mt-3">
              {action}
            </div>
          )}
        </div>

        {/* Dismiss button */}
        {dismissible && (
          <button
            type="button"
            className="btn-close"
            onClick={handleDismiss}
            aria-label="Close"
          />
        )}
      </div>
    </div>
  );
};

ErrorAlert.propTypes = {
  /** Severity level: error, warning, info, success */
  severity: PropTypes.oneOf(['error', 'danger', 'warning', 'info', 'success']),
  /** Alert title */
  title: PropTypes.string,
  /** Alert message */
  message: PropTypes.string,
  /** Array of error messages */
  errors: PropTypes.arrayOf(PropTypes.string),
  /** Show dismiss button */
  dismissible: PropTypes.bool,
  /** Callback when dismissed */
  onDismiss: PropTypes.func,
  /** Show icon */
  showIcon: PropTypes.bool,
  /** Custom icon class (Bootstrap Icons) */
  icon: PropTypes.string,
  /** Custom action/button */
  action: PropTypes.node,
  /** Alert variant: filled, outlined */
  variant: PropTypes.oneOf(['filled', 'outlined']),
  /** Auto dismiss after timeout */
  autoDismiss: PropTypes.bool,
  /** Auto dismiss timeout in ms */
  autoDismissTimeout: PropTypes.number,
  /** Additional CSS classes */
  className: PropTypes.string,
  /** Custom inline styles */
  style: PropTypes.object,
  /** Custom content */
  children: PropTypes.node
};

/**
 * ErrorMessage - Simple error message
 */
export const ErrorMessage = ({ message, ...props }) => (
  <ErrorAlert severity="error" message={message} showIcon={true} {...props} />
);

ErrorMessage.propTypes = {
  message: PropTypes.string.isRequired
};

/**
 * WarningMessage - Simple warning message
 */
export const WarningMessage = ({ message, ...props }) => (
  <ErrorAlert severity="warning" message={message} showIcon={true} {...props} />
);

WarningMessage.propTypes = {
  message: PropTypes.string.isRequired
};

/**
 * InfoMessage - Simple info message
 */
export const InfoMessage = ({ message, ...props }) => (
  <ErrorAlert severity="info" message={message} showIcon={true} {...props} />
);

InfoMessage.propTypes = {
  message: PropTypes.string.isRequired
};

/**
 * SuccessMessage - Simple success message
 */
export const SuccessMessage = ({ message, ...props }) => (
  <ErrorAlert severity="success" message={message} showIcon={true} {...props} />
);

SuccessMessage.propTypes = {
  message: PropTypes.string.isRequired
};

/**
 * ValidationErrors - Display validation errors from form
 */
export const ValidationErrors = ({ errors = {}, title = 'Validation Errors', ...props }) => {
  const errorList = Object.entries(errors).map(([field, message]) => {
    const fieldName = field.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    return `${fieldName}: ${message}`;
  });

  if (errorList.length === 0) return null;

  return (
    <ErrorAlert
      severity="error"
      title={title}
      errors={errorList}
      {...props}
    />
  );
};

ValidationErrors.propTypes = {
  errors: PropTypes.object,
  title: PropTypes.string
};

/**
 * NonFieldErrors - Display non-field errors from Django REST
 */
export const NonFieldErrors = ({ errors = [], formatFunction, ...props }) => {
  if (!errors || errors.length === 0) return null;

  const formattedErrors = formatFunction
    ? formatFunction(errors)
    : errors.map(err => String(err).toUpperCase());

  return (
    <ErrorAlert
      severity="error"
      title="ERROR"
      errors={formattedErrors}
      className="mb-3"
      {...props}
    />
  );
};

NonFieldErrors.propTypes = {
  errors: PropTypes.array,
  formatFunction: PropTypes.func
};

/**
 * ApiError - Display error from API response
 */
export const ApiError = ({ error, title = 'Error', ...props }) => {
  if (!error) return null;

  // Extract error message
  const message = typeof error === 'string'
    ? error
    : error?.response?.data?.detail ||
      error?.response?.data?.message ||
      error?.message ||
      'An unexpected error occurred';

  // Extract field errors if available
  const fieldErrors = error?.response?.data;
  const errorList = [];

  if (fieldErrors && typeof fieldErrors === 'object') {
    Object.entries(fieldErrors).forEach(([key, value]) => {
      if (key !== 'detail' && key !== 'message') {
        const errors = Array.isArray(value) ? value : [value];
        const fieldName = key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
        errors.forEach(err => {
          errorList.push(`${fieldName}: ${err}`);
        });
      }
    });
  }

  return (
    <ErrorAlert
      severity="error"
      title={title}
      message={errorList.length === 0 ? message : ''}
      errors={errorList}
      {...props}
    />
  );
};

ApiError.propTypes = {
  error: PropTypes.oneOfType([PropTypes.string, PropTypes.object]),
  title: PropTypes.string
};

export default ErrorAlert;
