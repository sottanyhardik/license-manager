// Generic parameters accepted by paginated list endpoints.
// Extended by feature-specific param interfaces (e.g. LicenseListParams).
export interface ListParams {
  search?: string
  page?: number
  page_size?: number
  ordering?: string
  all?: boolean
}

export interface APIResponse<T> {
  success: boolean
  data: T | null
  message: string | null
  errors?: Array<{ field: string; message: string }>
}

// Shape returned by list endpoints AFTER the envelope interceptor in client.ts
// has run.  The interceptor sets response.data to { data, pagination } when a
// top-level "pagination" key is present in the raw envelope.
// backend/shared/pagination.py emits:
//   { success, data: T[], message, pagination: { count, next, previous, page_size, total_pages } }
export interface PaginatedResponse<T> {
  data: T[]
  pagination: {
    count: number
    next: string | null
    previous: string | null
    page_size: number
    total_pages: number
  }
}
