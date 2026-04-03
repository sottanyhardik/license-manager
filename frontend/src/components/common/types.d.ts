/**
 * TypeScript definitions for common components and hooks
 * Provides IntelliSense support even in JavaScript projects
 */

import { ReactNode, CSSProperties, FormEvent, ChangeEvent, FocusEvent } from 'react';

// ============================================================================
// HOOKS
// ============================================================================

/**
 * useFormState Hook Types
 */
export interface FormStateOptions<T = any> {
  validate?: (values: T) => Record<string, string>;
  validateOnChange?: boolean;
  validateOnBlur?: boolean;
  enableReinitialize?: boolean;
  warnBeforeUnload?: boolean;
  beforeUnloadMessage?: string;
}

export interface FieldMeta {
  value: any;
  error?: string;
  touched: boolean;
  initialValue: any;
}

export interface FieldHelpers {
  setValue: (value: any) => void;
  setTouched: (touched: boolean) => void;
  setError: (error: string | null) => void;
}

export interface FormState<T = any> {
  formData: T;
  setFormData: (data: T, shouldValidate?: boolean) => void;
  setFieldValue: (fieldName: string, value: any) => Promise<void>;
  setFieldValues: (values: Partial<T>) => void;
  setFieldError: (fieldName: string, error: string | null) => void;
  setFieldErrors: (errors: Record<string, string>) => void;
  setFieldTouched: (fieldName: string, touched: boolean) => void;
  errors: Record<string, string>;
  setErrors: (errors: Record<string, string>) => void;
  touched: Record<string, boolean>;
  setTouched: (touched: Record<string, boolean>) => void;
  validateForm: (values?: T) => Promise<Record<string, string>>;
  validateField: (fieldName: string, value: any) => Promise<string | null>;
  isValid: boolean;
  isValidating: boolean;
  isDirty: boolean;
  isSubmitting: boolean;
  setIsSubmitting: (submitting: boolean) => void;
  handleChange: (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => Promise<void>;
  handleBlur: (e: FocusEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => Promise<void>;
  handleSubmit: (onSubmit: (values: T) => Promise<any>) => (e?: FormEvent) => Promise<{ success: boolean; data?: any; errors?: Record<string, string>; error?: any }>;
  getFieldProps: (fieldName: string) => {
    name: string;
    value: any;
    onChange: (e: ChangeEvent) => void;
    onBlur: (e: FocusEvent) => void;
  };
  getFieldMeta: (fieldName: string) => FieldMeta;
  getFieldHelpers: (fieldName: string) => FieldHelpers;
  resetForm: (newValues?: T) => void;
}

export function useFormState<T = any>(
  initialValues: T,
  options?: FormStateOptions<T>
): FormState<T>;

/**
 * useApiRequest Hook Types
 */
export interface ApiRequestOptions {
  onSuccess?: (data: any) => void;
  onError?: (error: any) => void;
  showSuccessToast?: boolean;
  showErrorToast?: boolean;
  successMessage?: string;
  errorMessage?: string;
  retry?: number;
  retryDelay?: number;
  retryExponential?: boolean;
  cache?: boolean;
  cacheTime?: number;
  timeout?: number;
  deduplicate?: boolean;
}

export interface ApiRequestConfig {
  cacheKey?: string;
  skipCache?: boolean;
  skipToast?: boolean;
}

export interface ApiRequestResult {
  success: boolean;
  data?: any;
  error?: string;
  errorData?: any;
  attempts?: number;
  cancelled?: boolean;
  fromCache?: boolean;
}

export interface ApiRequest {
  loading: boolean;
  error: string | null;
  data: any;
  retryCount: number;
  execute: (
    apiFunction: (config?: { signal: AbortSignal }) => Promise<any>,
    config?: ApiRequestConfig
  ) => Promise<ApiRequestResult>;
  get: (url: string, params?: any, config?: ApiRequestConfig) => Promise<ApiRequestResult>;
  post: (url: string, data?: any, config?: ApiRequestConfig) => Promise<ApiRequestResult>;
  put: (url: string, data?: any, config?: ApiRequestConfig) => Promise<ApiRequestResult>;
  patch: (url: string, data?: any, config?: ApiRequestConfig) => Promise<ApiRequestResult>;
  delete: (url: string, config?: ApiRequestConfig) => Promise<ApiRequestResult>;
  cancel: () => void;
  reset: () => void;
  clearCache: (cacheKey?: string) => void;
  setData: (data: any) => void;
  setError: (error: string | null) => void;
}

export function useApiRequest(options?: ApiRequestOptions): ApiRequest;
export function clearAllCache(): void;
export function getCacheStats(): { size: number; keys: string[] };

// ============================================================================
// COMPONENTS
// ============================================================================

/**
 * LoadingSpinner Component Types
 */
export type SpinnerSize = 'sm' | 'md' | 'lg' | 'xl';
export type SpinnerVariant = 'spinner' | 'grow' | 'dots' | 'bars';
export type SpinnerColor = 'primary' | 'secondary' | 'success' | 'danger' | 'warning' | 'info' | 'light' | 'dark';

export interface LoadingSpinnerProps {
  size?: SpinnerSize;
  variant?: SpinnerVariant;
  color?: SpinnerColor;
  text?: string;
  inline?: boolean;
  center?: boolean;
  overlay?: boolean;
  className?: string;
  style?: CSSProperties;
}

export const LoadingSpinner: React.FC<LoadingSpinnerProps>;
export const PageSpinner: React.FC<{ text?: string }>;
export const ButtonSpinner: React.FC<{ className?: string }>;
export const CardSpinner: React.FC<{ text?: string }>;
export const InlineSpinner: React.FC<{ text?: string }>;

/**
 * ErrorAlert Component Types
 */
export type AlertSeverity = 'error' | 'danger' | 'warning' | 'info' | 'success';
export type AlertVariant = 'filled' | 'outlined';

export interface ErrorAlertProps {
  severity?: AlertSeverity;
  title?: string;
  message?: string;
  errors?: string[];
  dismissible?: boolean;
  onDismiss?: () => void;
  showIcon?: boolean;
  icon?: string;
  action?: ReactNode;
  variant?: AlertVariant;
  autoDismiss?: boolean;
  autoDismissTimeout?: number;
  className?: string;
  style?: CSSProperties;
  children?: ReactNode;
}

export const ErrorAlert: React.FC<ErrorAlertProps>;
export const ErrorMessage: React.FC<{ message: string }>;
export const WarningMessage: React.FC<{ message: string }>;
export const InfoMessage: React.FC<{ message: string }>;
export const SuccessMessage: React.FC<{ message: string }>;
export const ValidationErrors: React.FC<{ errors?: Record<string, string>; title?: string }>;
export const NonFieldErrors: React.FC<{ errors?: string[]; formatFunction?: (errors: string[]) => any }>;
export const ApiError: React.FC<{ error?: any; title?: string }>;

/**
 * FormField Component Types
 */
export type FormFieldType =
  | 'text'
  | 'email'
  | 'password'
  | 'number'
  | 'tel'
  | 'url'
  | 'date'
  | 'datetime-local'
  | 'time'
  | 'month'
  | 'week'
  | 'color'
  | 'select'
  | 'textarea'
  | 'checkbox'
  | 'radio';

export interface SelectOption {
  value: any;
  label: string;
  disabled?: boolean;
}

export interface FormFieldProps {
  label?: string;
  name: string;
  type?: FormFieldType;
  value?: any;
  onChange?: (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => void;
  onBlur?: (e: FocusEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => void;
  options?: (string | number | SelectOption)[];
  placeholder?: string;
  error?: string;
  errors?: Record<string, string>;
  touched?: boolean;
  required?: boolean;
  className?: string;
  labelClassName?: string;
  inputClassName?: string;
  helpText?: string;
  disabled?: boolean;
  readOnly?: boolean;
  prefix?: ReactNode;
  suffix?: ReactNode;
  showCharCount?: boolean;
  maxLength?: number;
  rows?: number;
  checked?: boolean;
  inline?: boolean;
  floating?: boolean;
  id?: string;
}

export const FormField: React.FC<FormFieldProps>;
export const FormTextArea: React.FC<FormFieldProps>;
export const FormSelect: React.FC<FormFieldProps>;
export const FormCheckbox: React.FC<FormFieldProps>;
export const FormRadio: React.FC<FormFieldProps>;
export const FormGroup: React.FC<{ title?: string; children?: ReactNode; className?: string }>;

/**
 * Modal Component Types
 */
export type ModalSize = 'sm' | 'md' | 'lg' | 'xl' | 'fullscreen';
export type FullscreenBreakpoint = 'sm' | 'md' | 'lg' | 'xl' | 'xxl';

export interface ModalProps {
  show: boolean;
  onHide: () => void;
  title?: ReactNode;
  children?: ReactNode;
  footer?: ReactNode;
  size?: ModalSize;
  showCloseButton?: boolean;
  closeOnBackdrop?: boolean;
  closeOnEscape?: boolean;
  headerClassName?: string;
  bodyClassName?: string;
  footerClassName?: string;
  dialogClassName?: string;
  centered?: boolean;
  scrollable?: boolean;
  fullscreen?: boolean | FullscreenBreakpoint;
  loading?: boolean;
  animation?: boolean;
  backdropTransition?: boolean;
  ariaLabelledBy?: string;
  ariaDescribedBy?: string;
  className?: string;
  style?: CSSProperties;
  backdropClassName?: string;
  backdropStyle?: CSSProperties;
  enforceFocus?: boolean;
  autoFocus?: boolean;
  restoreFocus?: boolean;
  backdrop?: boolean;
}

export const Modal: React.FC<ModalProps>;

export interface ConfirmModalProps {
  show: boolean;
  onHide: () => void;
  onConfirm?: () => void | Promise<void>;
  title?: string;
  message?: ReactNode;
  confirmText?: string;
  cancelText?: string;
  confirmVariant?: string;
  loading?: boolean;
}

export const ConfirmModal: React.FC<ConfirmModalProps>;

export interface AlertModalProps {
  show: boolean;
  onHide: () => void;
  title?: string;
  message?: ReactNode;
  variant?: 'success' | 'error' | 'warning' | 'info';
  okText?: string;
}

export const AlertModal: React.FC<AlertModalProps>;
