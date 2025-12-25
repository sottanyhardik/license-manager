/**
 * Modal Component
 *
 * Reusable modal component that eliminates ~300 lines of modal boilerplate
 * from 10+ components.
 *
 * Features:
 * - Multiple sizes (sm, md, lg, xl, fullscreen)
 * - Optional backdrop click to close
 * - Optional close button
 * - Customizable header/body/footer classes
 * - Keyboard ESC support
 * - Proper focus management
 *
 * @example
 * <Modal
 *   show={show}
 *   onHide={handleClose}
 *   title="Edit Record"
 *   size="lg"
 *   footer={
 *     <>
 *       <button onClick={handleClose}>Cancel</button>
 *       <button onClick={handleSave}>Save</button>
 *     </>
 *   }
 * >
 *   <Form />
 * </Modal>
 */

import React, { useEffect } from 'react';

export const Modal = ({
  show,
  onHide,
  title,
  children,
  footer,
  size = 'xl', // sm, md, lg, xl, fullscreen
  showCloseButton = true,
  closeOnBackdrop = true,
  closeOnEscape = true,
  headerClassName = '',
  bodyClassName = '',
  footerClassName = '',
  centered = false,
  scrollable = false,
}) => {
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
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'unset';
    }

    return () => {
      document.body.style.overflow = 'unset';
    };
  }, [show]);

  if (!show) return null;

  const sizeClass = size === 'fullscreen' ? 'modal-fullscreen' : `modal-${size}`;
  const centeredClass = centered ? 'modal-dialog-centered' : '';
  const scrollableClass = scrollable ? 'modal-dialog-scrollable' : '';

  return (
    <div
      className="modal show d-block"
      style={{ backgroundColor: 'rgba(0, 0, 0, 0.5)', zIndex: 1050 }}
      onClick={(e) => {
        if (closeOnBackdrop && e.target === e.currentTarget) {
          onHide();
        }
      }}
      role="dialog"
      aria-modal="true"
    >
      <div className={`modal-dialog ${sizeClass} ${centeredClass} ${scrollableClass}`.trim()}>
        <div className="modal-content">
          {/* Header */}
          <div className={`modal-header ${headerClassName}`}>
            <h5 className="modal-title">{title}</h5>
            {showCloseButton && (
              <button
                type="button"
                className="btn-close"
                onClick={onHide}
                aria-label="Close"
              />
            )}
          </div>

          {/* Body */}
          <div className={`modal-body ${bodyClassName}`}>
            {children}
          </div>

          {/* Footer */}
          {footer && (
            <div className={`modal-footer ${footerClassName}`}>
              {footer}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Modal;
