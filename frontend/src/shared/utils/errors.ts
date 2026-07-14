import type { APIResponse } from '@/shared/types/api'
import axios from 'axios'

/**
 * Normalise any caught API error into a flat string array.
 * Handles: axios errors with APIResponse envelope, plain Error, unknown.
 */
export function normaliseApiError(error: unknown): string[] {
  if (!axios.isAxiosError(error)) {
    if (error instanceof Error) return [error.message]
    return ['An unexpected error occurred.']
  }

  const data = error.response?.data as Partial<APIResponse<unknown>> | undefined

  // Field-level validation errors
  if (data?.errors && Array.isArray(data.errors) && data.errors.length > 0) {
    return data.errors.map((e) => (e.field ? `${e.field}: ${e.message}` : e.message))
  }

  // Top-level message from the envelope
  if (data?.message) return [data.message]

  // HTTP status fallback
  const status = error.response?.status
  if (status === 401) return ['Your session has expired. Please log in again.']
  if (status === 403) return ['You do not have permission to perform this action.']
  if (status === 404) return ['The requested resource was not found.']
  if (status === 422) return ['Validation failed. Please check your input.']
  if (status != null && status >= 500) return ['A server error occurred. Please try again later.']

  return [error.message ?? 'An unexpected error occurred.']
}

/** Convenience: return a single joined string instead of an array. */
export function normaliseApiErrorString(error: unknown, separator = ' '): string {
  return normaliseApiError(error).join(separator)
}
