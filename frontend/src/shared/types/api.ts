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

export interface PaginatedResponse<T> {
  success: boolean
  data: {
    count: number
    next: string | null
    previous: string | null
    results: T[]
  }
  message: string | null
}
