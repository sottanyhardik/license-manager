/**
 * ConfirmDialog Component
 *
 * Accessible confirmation dialog that replaces window.confirm()
 * with better UX and WCAG compliance.
 *
 * Features:
 * - Customizable message and actions
 * - Different severity levels (danger, warning, info)
 * - Keyboard accessible (ESC to cancel, Enter to confirm)
 * - Focus management
 * - ARIA attributes for screen readers
 *
 * @example
 * const [showConfirm, setShowConfirm] = useState(false);
 *
 * <ConfirmDialog
 *   show={showConfirm}
 *   title="Delete Record"
 *   message="Are you sure you want to delete this record? This action cannot be undone."
 *   severity="danger"
 *   confirmText="Delete"
 *   cancelText="Cancel"
 *   onConfirm={() => {
 *     handleDelete();
 *     setShowConfirm(false);
 *   }}
 *   onCancel={() => setShowConfirm(false)}
 * />
 */

import React, { useEffect, useRef } from 'react';

export const ConfirmDialog = ({
  show,
  title = "Confirm Action",
  message = "Are you sure you want to proceed?",
  severity = "warning", // danger, warning, info, success
  confirmText = "Confirm",
  cancelText = "Cancel",
  onConfirm,
  onCancel,
  showCancelButton = true,
  confirmButtonClassName = '',
  cancelButtonClassName = '',
}) => {
  const dialogRef = useRef(null);
  const confirmButtonRef = useRef(null);
  const previousFocusRef = useRef(null);

  // Severity-based styling
  const severityConfig = {
    danger: {
      icon: 'bi-exclamation-triangle-fill',
      iconColor: 'var(--danger-color)',
      confirmClass: 'btn-danger',
      headerClass: 'bg-danger-subtle'
    },
    warning: {
      icon: 'bi-exclamation-triangle',
      iconColor: 'var(--warning-color)',
      confirmClass: 'btn-warning',
      headerClass: 'bg-warning-subtle'
    },
    info: {
      icon: 'bi-info-circle',
      iconColor: 'var(--info-color)',
      confirmClass: 'btn-info',
      headerClass: 'bg-info-subtle'
    },
    success: {
      icon: 'bi-check-circle',
      iconColor: 'var(--success-color)',
      confirmClass: 'btn-success',
      headerClass: 'bg-success-subtle'
    }
  };

  const config = severityConfig[severity] || severityConfig.warning;

  // Focus management
  useEffect(() => {
    if (!show) return;

    // Save the currently focused element
    previousFocusRef.current = document.activeElement;

    // Focus the confirm button when dialog opens
    setTimeout(() => {
      if (confirmButtonRef.current) {
        confirmButtonRef.current.focus();
      }
    }, 100);

    // Trap focus within dialog
    const handleTabKey = (e) => {
      if (e.key !== 'Tab') return;

      if (!dialogRef.current) return;

      const focusableElements = dialogRef.current.querySelectorAll(
        'button:not([disabled]), [tabindex]:not([tabindex="-1"])'
      );

      if (focusableElements.length === 0) return;

      const firstElement = focusableElements[0];
      const lastElement = focusableElements[focusableElements.length - 1];

      if (e.shiftKey) {
        // Shift + Tab
        if (document.activeElement === firstElement) {
          e.preventDefault();
          lastElement.focus();
        }
      } else {
        // Tab
        if (document.activeElement === lastElement) {
          e.preventDefault();
          firstElement.focus();
        }
      }
    };

    document.addEventListener('keydown', handleTabKey);

    return () => {
      document.removeEventListener('keydown', handleTabKey);
      // Restore focus to the previously focused element
      if (previousFocusRef.current) {
        previousFocusRef.current.focus();
      }
    };
  }, [show]);

  // Handle ESC and Enter keys
  useEffect(() => {
    if (!show) return;

    const handleKeyDown = (e) => {
      if (e.key === 'Escape') {
        onCancel();
      } else if (e.key === 'Enter') {
        onConfirm();
      }
    };

    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, [show, onConfirm, onCancel]);

  // Prevent body scroll when dialog is open
  useEffect(() => {
    if (show) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }

    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [show]);

  if (!show) return null;

  return (
    <div
      className="modal show d-block"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)', zIndex: 1060 }}
      role="alertdialog"
      aria-modal="true"
      aria-labelledby="confirm-dialog-title"
      aria-describedby="confirm-dialog-message"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onCancel();
        }
      }}
    >
      <div
        ref={dialogRef}
        className="modal-dialog modal-dialog-centered"
        style={{ maxWidth: '500px' }}
      >
        <div className="modal-content" style={{ borderRadius: '12px', overflow: 'hidden' }}>
          {/* Header */}
          <div className={`modal-header ${config.headerClass} border-0`} style={{ padding: '1.5rem' }}>
            <div className="d-flex align-items-center w-100">
              <div
                className="d-flex align-items-center justify-content-center me-3"
                style={{
                  width: '48px',
                  height: '48px',
                  borderRadius: '50%',
                  backgroundColor: 'white'
                }}
              >
                <i
                  className={`bi ${config.icon}`}
                  style={{ fontSize: '1.5rem', color: config.iconColor }}
                  aria-hidden="true"
                ></i>
              </div>
              <h5 id="confirm-dialog-title" className="modal-title mb-0" style={{ fontWeight: '600' }}>
                {title}
              </h5>
            </div>
          </div>

          {/* Body */}
          <div className="modal-body" style={{ padding: '1.5rem' }}>
            <p id="confirm-dialog-message" style={{ marginBottom: 0, fontSize: '0.95rem', color: 'var(--bs-gray-600)' }}>
              {message}
            </p>
          </div>

          {/* Footer */}
          <div className="modal-footer border-0" style={{ padding: '1rem 1.5rem 1.5rem' }}>
            <div className="d-flex gap-2 w-100 justify-content-end">
              {showCancelButton && (
                <button
                  type="button"
                  className={`btn ${cancelButtonClassName || 'btn-outline-secondary'}`}
                  onClick={onCancel}
                  style={{ minWidth: '100px' }}
                  aria-label={cancelText}
                >
                  {cancelText}
                </button>
              )}
              <button
                ref={confirmButtonRef}
                type="button"
                className={`btn ${confirmButtonClassName || config.confirmClass}`}
                onClick={onConfirm}
                style={{ minWidth: '100px' }}
                aria-label={confirmText}
              >
                {confirmText}
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ConfirmDialog;
