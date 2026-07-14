// Master data types — shapes match /api/v1/masters/* DRF responses.
// All fields that may be absent from the API use optional (?) rather than
// nullable (| null) to keep downstream code cleaner.

export interface Company {
  id: number
  name: string
  address_line1?: string
  address_line2?: string
  city?: string
  state?: string
  pin?: string
  gstin?: string
  is_active: boolean
}

export interface Port {
  id: number
  port_code: string
  port_name: string
}

export interface HSCode {
  id: number
  hs_code: string
  description: string
}

export interface ItemGroup {
  id: number
  name: string
  description?: string
}

export interface ItemName {
  id: number
  name: string
  item_group?: number
  item_group_name?: string
}

export interface SionNormClass {
  id: number
  norm_class: string
  description?: string
}

export interface ExchangeRate {
  id: number
  currency: string
  rate: string
  date: string
}

// Generic paginated API response envelope used by all master list endpoints.
export interface PaginatedResponse<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

// Parameters accepted by paginated list endpoints.
export interface ListParams {
  search?: string
  page?: number
  page_size?: number
  ordering?: string
  all?: boolean
}
