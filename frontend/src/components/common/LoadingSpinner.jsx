/**
 * LoadingSpinner Component
 *
 * Reusable loading spinner component with multiple variants, sizes, and layouts.
 * Provides consistent loading indicators across the application.
 *
 * Features:
 * - Multiple sizes: sm, md, lg, xl
 * - Multiple variants: spinner, dots, bars, grow
 * - Optional text display
 * - Center and inline layout options
 * - Custom colors using Bootstrap theme colors
 * - Accessible ARIA labels
 * - Overlay mode for blocking UI
 *
 * @example
 * // Basic spinner
 * <LoadingSpinner />
 *
 * // Large spinner with text
 * <LoadingSpinner size="lg" text="Loading data..." />
 *
 * // Inline spinner in button
 * <button disabled>
 *   <LoadingSpinner size="sm" variant="spinner" inline /> Saving...
 * </button>
 *
 * // Full page overlay
 * <LoadingSpinner overlay text="Processing..." />
 *
 * // Dots variant
 * <LoadingSpinner variant="dots" color="success" />
 */

import React from 'react';
import PropTypes from 'prop-types';

/**
 * LoadingSpinner Component
 */
export const LoadingSpinner = ({
  size = 'md',
  variant = 'spinner',
  color = 'primary',
  text = '',
  inline = false,
  center = true,
  overlay = false,
  className = '',
  style = {},
  ...props
}) => {
  // Size mappings
  const sizeMap = {
    sm: { spinner: '1rem', text: 'small' },
    md: { spinner: '2rem', text: 'base' },
    lg: { spinner: '3rem', text: 'h6' },
    xl: { spinner: '4rem', text: 'h5' }
  };

  const spinnerSize = sizeMap[size]?.spinner || sizeMap.md.spinner;
  const textClass = sizeMap[size]?.text || sizeMap.md.text;

  /**
   * Render spinner variant
   */
  const renderSpinner = () => {
    switch (variant) {
      case 'spinner':
        return (
          <div
            className={`spinner-border text-${color}`}
            role="status"
            style={{ width: spinnerSize, height: spinnerSize }}
            aria-label="Loading"
          >
            <span className="visually-hidden">Loading...</span>
          </div>
        );

      case 'grow':
        return (
          <div
            className={`spinner-grow text-${color}`}
            role="status"
            style={{ width: spinnerSize, height: spinnerSize }}
            aria-label="Loading"
          >
            <span className="visually-hidden">Loading...</span>
          </div>
        );

      case 'dots':
        return (
          <div className="d-flex align-items-center gap-2" role="status" aria-label="Loading">
            <div
              className={`spinner-grow text-${color}`}
              style={{ width: `calc(${spinnerSize} * 0.4)`, height: `calc(${spinnerSize} * 0.4)` }}
            >
              <span className="visually-hidden">Loading...</span>
            </div>
            <div
              className={`spinner-grow text-${color}`}
              style={{
                width: `calc(${spinnerSize} * 0.4)`,
                height: `calc(${spinnerSize} * 0.4)`,
                animationDelay: '0.15s'
              }}
            >
              <span className="visually-hidden">Loading...</span>
            </div>
            <div
              className={`spinner-grow text-${color}`}
              style={{
                width: `calc(${spinnerSize} * 0.4)`,
                height: `calc(${spinnerSize} * 0.4)`,
                animationDelay: '0.3s'
              }}
            >
              <span className="visually-hidden">Loading...</span>
            </div>
          </div>
        );

      case 'bars':
        return (
          <div className="d-flex align-items-end gap-1" role="status" aria-label="Loading">
            {[0, 0.15, 0.3].map((delay, i) => (
              <div
                key={i}
                className={`bg-${color}`}
                style={{
                  width: `calc(${spinnerSize} * 0.25)`,
                  height: spinnerSize,
                  animation: `bar-scale 1s ${delay}s infinite ease-in-out`,
                  transformOrigin: 'bottom'
                }}
              />
            ))}
            <span className="visually-hidden">Loading...</span>
          </div>
        );

      default:
        return (
          <div
            className={`spinner-border text-${color}`}
            role="status"
            style={{ width: spinnerSize, height: spinnerSize }}
            aria-label="Loading"
          >
            <span className="visually-hidden">Loading...</span>
          </div>
        );
    }
  };

  /**
   * Render content (spinner + text)
   */
  const renderContent = () => {
    const content = (
      <>
        {renderSpinner()}
        {text && (
          <div
            className={`mt-2 text-${color} ${textClass === 'small' ? 'small' : ''} ${
              textClass.startsWith('h') ? textClass : ''
            }`}
          >
            {text}
          </div>
        )}
      </>
    );

    // Inline layout
    if (inline) {
      return (
        <div className={`d-inline-flex align-items-center gap-2 ${className}`} style={style} {...props}>
          {renderSpinner()}
          {text && <span className={`text-${color}`}>{text}</span>}
        </div>
      );
    }

    // Center layout
    if (center) {
      return (
        <div
          className={`d-flex flex-column justify-content-center align-items-center ${className}`}
          style={style}
          {...props}
        >
          {content}
        </div>
      );
    }

    // Default layout
    return (
      <div className={`text-center ${className}`} style={style} {...props}>
        {content}
      </div>
    );
  };

  // Overlay mode
  if (overlay) {
    return (
      <div
        className="position-fixed top-0 start-0 w-100 h-100 d-flex justify-content-center align-items-center"
        style={{
          backgroundColor: 'rgba(255, 255, 255, 0.9)',
          zIndex: 9999,
          backdropFilter: 'blur(5px)',
          ...style
        }}
        {...props}
      >
        <div className="text-center">
          {renderSpinner()}
          {text && (
            <div className={`mt-3 text-${color} ${textClass.startsWith('h') ? textClass : ''}`}>
              {text}
            </div>
          )}
        </div>
      </div>
    );
  }

  return renderContent();
};

LoadingSpinner.propTypes = {
  /** Size of the spinner: sm, md, lg, xl */
  size: PropTypes.oneOf(['sm', 'md', 'lg', 'xl']),
  /** Spinner variant: spinner, grow, dots, bars */
  variant: PropTypes.oneOf(['spinner', 'grow', 'dots', 'bars']),
  /** Bootstrap theme color */
  color: PropTypes.oneOf([
    'primary',
    'secondary',
    'success',
    'danger',
    'warning',
    'info',
    'light',
    'dark'
  ]),
  /** Optional text to display */
  text: PropTypes.string,
  /** Display inline with other elements */
  inline: PropTypes.bool,
  /** Center the spinner */
  center: PropTypes.bool,
  /** Show as full-page overlay */
  overlay: PropTypes.bool,
  /** Additional CSS classes */
  className: PropTypes.string,
  /** Custom inline styles */
  style: PropTypes.object
};

/**
 * PageSpinner - Full page centered spinner
 */
export const PageSpinner = ({ text = 'Loading...', ...props }) => (
  <div className="d-flex justify-content-center align-items-center" style={{ minHeight: '400px' }}>
    <LoadingSpinner size="lg" text={text} {...props} />
  </div>
);

PageSpinner.propTypes = {
  text: PropTypes.string
};

/**
 * ButtonSpinner - Small spinner for buttons
 */
export const ButtonSpinner = ({ className = '', ...props }) => (
  <LoadingSpinner
    size="sm"
    variant="spinner"
    inline
    center={false}
    className={`me-2 ${className}`}
    {...props}
  />
);

ButtonSpinner.propTypes = {
  className: PropTypes.string
};

/**
 * CardSpinner - Spinner for card loading states
 */
export const CardSpinner = ({ text = 'Loading...', ...props }) => (
  <div className="card">
    <div className="card-body py-5">
      <LoadingSpinner size="md" text={text} {...props} />
    </div>
  </div>
);

CardSpinner.propTypes = {
  text: PropTypes.string
};

/**
 * InlineSpinner - Small inline spinner with text
 */
export const InlineSpinner = ({ text = 'Loading...', ...props }) => (
  <div className="d-flex align-items-center gap-2 text-muted">
    <LoadingSpinner size="sm" inline color="secondary" {...props} />
    <span>{text}</span>
  </div>
);

InlineSpinner.propTypes = {
  text: PropTypes.string
};

// CSS for bars animation (add to your global CSS or use styled-components)
// @keyframes bar-scale {
//   0%, 40%, 100% { transform: scaleY(0.4); }
//   20% { transform: scaleY(1.0); }
// }

export default LoadingSpinner;
