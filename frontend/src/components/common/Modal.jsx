/**
 * Modal Component
 *
 * Comprehensive reusable modal wrapper component with extensive customization options.
 * Provides consistent modal dialogs across the application with proper accessibility,
 * keyboard navigation, and focus management.
 *
 * Features:
 * - Multiple sizes: sm, md, lg, xl, fullscreen
 * - Backdrop click handling
 * - ESC key support
 * - Optional close button
 * - Customizable header/body/footer
 * - Centered and scrollable variants
 * - Focus trap and restore
 * - Proper ARIA attributes
 * - Body scroll prevention
 * - Loading state
 * - Confirmation dialogs
 * - Custom animations
 *
 * @example
 * // Basic modal
 * <Modal
 *   show={show}
 *   onHide={handleClose}
 *   title="Edit Record"
 * >
 *   <Form />
 * </Modal>
 *
 * // Modal with custom footer
 * <Modal
 *   show={show}
 *   onHide={handleClose}
 *   title="Confirm Action"
 *   size="md"
 *   footer={
 *     <>
 *       <button className="btn btn-secondary" onClick={handleClose}>Cancel</button>
 *       <button className="btn btn-primary" onClick={handleSave}>Confirm</button>
 *     </>
 *   }
 * >
 *   Are you sure you want to proceed?
 * </Modal>
 *
 * // Fullscreen modal
 * <Modal
 *   show={show}
 *   onHide={handleClose}
 *   title="Full Page Form"
 *   size="fullscreen"
 *   scrollable
 * >
 *   <LongForm />
 * </Modal>
 */

import React, { useEffect, useRef, useCallback } from 'react';
import PropTypes from 'prop-types';

/**
 * Focus trap utility
 */
const useFocusTrap = (ref, active) => {
  useEffect(() => {
    if (!active || !ref.current) return;

    const focusableElements = ref.current.querySelectorAll(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );

    const firstElement = focusableElements[0];
    const lastElement = focusableElements[focusableElements.length - 1];

    const handleTabKey = (e) => {
      if (e.key !== 'Tab') return;

      if (e.shiftKey) {
        if (document.activeElement === firstElement) {
          lastElement?.focus();
          e.preventDefault();
        }
      } else {
        if (document.activeElement === lastElement) {
          firstElement?.focus();
          e.preventDefault();
        }
      }
    };

    document.addEventListener('keydown', handleTabKey);

    // Focus first element
    firstElement?.focus();

    return () => {
      document.removeEventListener('keydown', handleTabKey);
    };
  }, [ref, active]);
};

/**
 * Modal Component
 */
export const Modal = ({
  // Visibility
  show = false,
  onHide,

  // Content
  title,
  children,
  footer,

  // Size
  size = 'xl',

  // Behavior
  showCloseButton = true,
  closeOnBackdrop = true,
  closeOnEscape = true,

  // Styling
  headerClassName = '',
  bodyClassName = '',
  footerClassName = '',
  dialogClassName = '',

  // Layout
  centered = false,
  scrollable = false,
  fullscreen = false,

  // Loading
  loading = false,

  // Animation
  animation = true,
  backdropTransition = true,

  // Accessibility
  ariaLabelledBy,
  ariaDescribedBy,

  // Custom props
  className = '',
  style = {},
  backdropClassName = '',
  backdropStyle = {},

  // Advanced
  enforceFocus = true,
  autoFocus = true,
  restoreFocus = true,
  backdrop = true,

  ...props
}) => {
  const modalRef = useRef(null);
  const previousActiveElement = useRef(null);

  // Handle ESC key press
  useEffect(() => {
    if (!show || !closeOnEscape) return;

    const handleEscape = (e) => {
      if (e.key === 'Escape') {
        onHide();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [show, closeOnEscape, onHide]);

  // Prevent body scroll when modal is open
  useEffect(() => {
    if (show) {
      // Save scroll position
      const scrollY = window.scrollY;

      // Prevent scroll
      document.body.style.overflow = 'hidden';
      document.body.style.position = 'fixed';
      document.body.style.top = `-${scrollY}px`;
      document.body.style.width = '100%';

      return () => {
        // Restore scroll
        document.body.style.overflow = '';
        document.body.style.position = '';
        document.body.style.top = '';
        document.body.style.width = '';
        window.scrollTo(0, scrollY);
      };
    }
  }, [show]);

  // Save and restore focus
  useEffect(() => {
    if (show && autoFocus) {
      previousActiveElement.current = document.activeElement;
    }

    return () => {
      if (restoreFocus && previousActiveElement.current) {
        previousActiveElement.current?.focus();
      }
    };
  }, [show, autoFocus, restoreFocus]);

  // Focus trap
  useFocusTrap(modalRef, show && enforceFocus);

  // Handle backdrop click
  const handleBackdropClick = useCallback((e) => {
    if (closeOnBackdrop && e.target === e.currentTarget) {
      onHide();
    }
  }, [closeOnBackdrop, onHide]);

  if (!show) return null;

  // Size classes
  const getSizeClass = () => {
    if (fullscreen) {
      if (typeof fullscreen === 'string') {
        return `modal-fullscreen-${fullscreen}-down`;
      }
      return 'modal-fullscreen';
    }
    if (size === 'fullscreen') return 'modal-fullscreen';
    return `modal-${size}`;
  };

  const sizeClass = getSizeClass();
  const centeredClass = centered ? 'modal-dialog-centered' : '';
  const scrollableClass = scrollable ? 'modal-dialog-scrollable' : '';
  const animationClass = animation ? 'fade' : '';

  return (
    <>
      {/* Backdrop */}
      {backdrop && (
        <div
          className={`modal-backdrop ${animationClass} show ${backdropClassName}`}
          style={{
            backgroundColor: 'rgba(0, 0, 0, 0.5)',
            zIndex: 1050,
            ...backdropStyle
          }}
        />
      )}

      {/* Modal */}
      <div
        ref={modalRef}
        className={`modal ${animationClass} show d-block ${className}`}
        style={{
          zIndex: 1055,
          ...style
        }}
        onClick={handleBackdropClick}
        role="dialog"
        aria-modal="true"
        aria-labelledby={ariaLabelledBy || 'modal-title'}
        aria-describedby={ariaDescribedBy}
        tabIndex={-1}
        {...props}
      >
        <div
          className={`modal-dialog ${sizeClass} ${centeredClass} ${scrollableClass} ${dialogClassName}`.trim()}
        >
          <div className="modal-content">
            {/* Header */}
            {(title || showCloseButton) && (
              <div className={`modal-header ${headerClassName}`}>
                {title && (
                  <h5
                    id={ariaLabelledBy || 'modal-title'}
                    className="modal-title fw-bold"
                  >
                    {title}
                  </h5>
                )}
                {showCloseButton && (
                  <button
                    type="button"
                    className="btn-close"
                    onClick={onHide}
                    aria-label="Close"
                    disabled={loading}
                  />
                )}
              </div>
            )}

            {/* Body */}
            <div className={`modal-body ${bodyClassName}`}>
              {loading ? (
                <div className="text-center py-5">
                  <div className="spinner-border text-primary" role="status">
                    <span className="visually-hidden">Loading...</span>
                  </div>
                  <p className="mt-3 text-muted">Loading...</p>
                </div>
              ) : (
                children
              )}
            </div>

            {/* Footer */}
            {footer && !loading && (
              <div className={`modal-footer ${footerClassName}`}>
                {footer}
              </div>
            )}
          </div>
        </div>
      </div>
    </>
  );
};

Modal.propTypes = {
  /** Show/hide modal */
  show: PropTypes.bool.isRequired,
  /** Close handler */
  onHide: PropTypes.func.isRequired,
  /** Modal title */
  title: PropTypes.node,
  /** Modal content */
  children: PropTypes.node,
  /** Modal footer */
  footer: PropTypes.node,
  /** Modal size: sm, md, lg, xl, fullscreen */
  size: PropTypes.oneOf(['sm', 'md', 'lg', 'xl', 'fullscreen']),
  /** Show close button */
  showCloseButton: PropTypes.bool,
  /** Close on backdrop click */
  closeOnBackdrop: PropTypes.bool,
  /** Close on ESC key */
  closeOnEscape: PropTypes.bool,
  /** Header custom class */
  headerClassName: PropTypes.string,
  /** Body custom class */
  bodyClassName: PropTypes.string,
  /** Footer custom class */
  footerClassName: PropTypes.string,
  /** Dialog custom class */
  dialogClassName: PropTypes.string,
  /** Center modal vertically */
  centered: PropTypes.bool,
  /** Make body scrollable */
  scrollable: PropTypes.bool,
  /** Fullscreen mode */
  fullscreen: PropTypes.oneOfType([
    PropTypes.bool,
    PropTypes.oneOf(['sm', 'md', 'lg', 'xl', 'xxl'])
  ]),
  /** Loading state */
  loading: PropTypes.bool,
  /** Enable animation */
  animation: PropTypes.bool,
  /** Backdrop transition */
  backdropTransition: PropTypes.bool,
  /** ARIA labelledby */
  ariaLabelledBy: PropTypes.string,
  /** ARIA describedby */
  ariaDescribedBy: PropTypes.string,
  /** Additional class */
  className: PropTypes.string,
  /** Custom style */
  style: PropTypes.object,
  /** Backdrop class */
  backdropClassName: PropTypes.string,
  /** Backdrop style */
  backdropStyle: PropTypes.object,
  /** Enforce focus trap */
  enforceFocus: PropTypes.bool,
  /** Auto focus on open */
  autoFocus: PropTypes.bool,
  /** Restore focus on close */
  restoreFocus: PropTypes.bool,
  /** Show backdrop */
  backdrop: PropTypes.bool
};

/**
 * ConfirmModal - Pre-configured confirmation modal
 */
export const ConfirmModal = ({
  show,
  onHide,
  onConfirm,
  title = 'Confirm Action',
  message = 'Are you sure you want to proceed?',
  confirmText = 'Confirm',
  cancelText = 'Cancel',
  confirmVariant = 'primary',
  loading = false,
  ...props
}) => {
  const handleConfirm = async () => {
    if (onConfirm) {
      await onConfirm();
    }
    onHide();
  };

  return (
    <Modal
      show={show}
      onHide={onHide}
      title={title}
      size="md"
      centered
      footer={
        <>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onHide}
            disabled={loading}
          >
            {cancelText}
          </button>
          <button
            type="button"
            className={`btn btn-${confirmVariant}`}
            onClick={handleConfirm}
            disabled={loading}
          >
            {loading && (
              <span className="spinner-border spinner-border-sm me-2" role="status" />
            )}
            {confirmText}
          </button>
        </>
      }
      {...props}
    >
      <p className="mb-0">{message}</p>
    </Modal>
  );
};

ConfirmModal.propTypes = {
  show: PropTypes.bool.isRequired,
  onHide: PropTypes.func.isRequired,
  onConfirm: PropTypes.func,
  title: PropTypes.string,
  message: PropTypes.node,
  confirmText: PropTypes.string,
  cancelText: PropTypes.string,
  confirmVariant: PropTypes.string,
  loading: PropTypes.bool
};

/**
 * AlertModal - Pre-configured alert modal
 */
export const AlertModal = ({
  show,
  onHide,
  title = 'Alert',
  message,
  variant = 'info',
  okText = 'OK',
  ...props
}) => {
  const iconMap = {
    success: 'bi-check-circle-fill text-success',
    error: 'bi-x-circle-fill text-danger',
    warning: 'bi-exclamation-triangle-fill text-warning',
    info: 'bi-info-circle-fill text-info'
  };

  return (
    <Modal
      show={show}
      onHide={onHide}
      title={title}
      size="md"
      centered
      footer={
        <button type="button" className="btn btn-primary" onClick={onHide}>
          {okText}
        </button>
      }
      {...props}
    >
      <div className="d-flex align-items-start gap-3">
        <i className={`bi ${iconMap[variant]} fs-3`} />
        <p className="mb-0 flex-grow-1">{message}</p>
      </div>
    </Modal>
  );
};

AlertModal.propTypes = {
  show: PropTypes.bool.isRequired,
  onHide: PropTypes.func.isRequired,
  title: PropTypes.string,
  message: PropTypes.node,
  variant: PropTypes.oneOf(['success', 'error', 'warning', 'info']),
  okText: PropTypes.string
};

export default Modal;
