/**
 * Centralised API error message extraction.
 *
 * DRF returns errors in several shapes depending on the error type:
 *   { detail: "..." }          – authentication / permission errors
 *   { message: "..." }         – some custom views
 *   { error: "..." }           – our generic api_error() helper
 *   { field: ["msg", ...] }    – field-level validation errors (handled by useForm)
 *
 * This utility picks the first human-readable string it can find,
 * falling back to the native JS Error message and finally a safe default.
 */
export function getErrorMessage(error) {
  return (
    error?.response?.data?.detail ||
    error?.response?.data?.message ||
    error?.response?.data?.error ||
    error?.message ||
    'An unexpected error occurred'
  );
}
