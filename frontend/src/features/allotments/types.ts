// Allotment feature types — shapes match /api/v1/allotments/* DRF responses.

export interface AllotmentItem {
  id: number
  item: number | null
  allotment: number | null
  cif_inr: string
  cif_fc: string
  qty: string
  is_boe: boolean
  // read-only from cached_property
  serial_number: string | null
  product_description: string
  license_number: string | null
  license_date: string | null
  license_expiry: string | null
  hs_code: string | null
  exporter: string | null
  port_code: string | null
}

export type AllotmentType = 'AT' | 'TR'

export interface Allotment {
  id: number
  company: number
  company_name: string
  type: AllotmentType
  port: number | null
  port_name: string | null
  related_company: number | null
  related_company_name: string | null
  item_name: string
  required_quantity: string
  unit_value_per_unit: string
  cif_fc: string | null
  cif_inr: string | null
  exchange_rate: string | null
  invoice: string | null
  estimated_arrival_date: string | null
  bl_detail: string | null
  is_boe: boolean
  is_allotted: boolean
  is_approved: boolean
  created_on: string | null
  modified_on: string | null
  // computed read-only
  required_value: string
  alloted_quantity: string
  allotted_value: string
  balanced_quantity: string
  dfia_list: string
  display_label: string
  allotment_details: AllotmentItem[]
}

export interface AllotmentListParams {
  search?: string
  page?: number
  page_size?: number
  company?: number
  port?: number
  type?: AllotmentType
  license_number?: string
  is_boe?: boolean
  is_allotted?: boolean
  is_approved?: boolean
  ordering?: string
}

export interface PaginatedAllotments {
  count: number
  next: string | null
  previous: string | null
  results: Allotment[]
}

export type AllotmentFormValues = {
  company: number | null
  type: AllotmentType
  port: number | null
  item_name: string
  required_quantity: string
  unit_value_per_unit: string
  cif_fc: string
  cif_inr: string
  exchange_rate: string
  invoice: string
  estimated_arrival_date: string
  bl_detail: string
  is_approved: boolean
}

export interface GeneratePdfResponse {
  task_id: string | null
}
