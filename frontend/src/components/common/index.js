/**
 * Common Components Index
 *
 * Central export point for all common/reusable components.
 * Import from this file for cleaner imports across the application.
 *
 * @example
 * import { LoadingSpinner, ErrorAlert, FormField, Modal } from '@/components/common';
 */

// Loading Components
export {
  LoadingSpinner,
  PageSpinner,
  ButtonSpinner,
  CardSpinner,
  InlineSpinner
} from './LoadingSpinner';

// Alert/Error Components
export {
  ErrorAlert,
  ErrorMessage,
  WarningMessage,
  InfoMessage,
  SuccessMessage,
  ValidationErrors,
  NonFieldErrors,
  ApiError
} from './ErrorAlert';

// Form Components
export {
  FormField,
  FormTextArea,
  FormSelect,
  FormCheckbox,
  FormRadio,
  FormGroup
} from './FormField';

// Modal Components
export {
  Modal,
  ConfirmModal,
  AlertModal
} from './Modal';
