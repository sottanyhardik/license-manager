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
