// Allotment feature types — shapes match /api/v1/allotments/* DRF responses.

import type { PaginatedResponse } from '@/shared/types/api'
export type { PaginatedResponse }

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

/** @deprecated Use PaginatedResponse<Allotment> from shared/types/api instead. */
export type PaginatedAllotments = PaginatedResponse<Allotment>

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

// ─── Allocation workflow types ─────────────────────────────────────────────────

export interface AvailableLicense {
  id: number
  license_id?: number
  license?: number
  license_number: string
  serial_number: string | number
  description: string
  exporter_name?: string
  available_quantity: string
  balance_cif_fc: string
  condition_type?: string
  hs_code_label?: string
  notification_number?: string
  license_expiry_date?: string
  items_detail?: Array<{ id: number; name: string }>
}

export interface AvailableLicensesParams {
  description?: string
  exporter?: string
  exclude_exporter?: string
  license_number?: string
  available_quantity_gte?: string
  available_quantity_lte?: string
  available_value_gte?: string
  available_value_lte?: string
  notification_number?: string
  norm_class?: string
  hs_code?: string
  is_expired?: string
  is_restricted?: string
  purchase_status?: string
  license_status?: string
  item_names?: string
  expiry_date_from?: string
  expiry_date_to?: string
  page?: number
  page_size?: number
}

export interface AllocationEntry {
  item_id: number
  qty: string
  cif_fc: string
}

export interface AllocateItemsResponse {
  created?: AllotmentItem[]
  errors?: Array<{ id?: number; error: string; plan_exceeded?: boolean }>
  allotment?: Allotment
  plan_exceeded?: boolean
  plan_data?: unknown
}

export interface AvailableLicensesResponse {
  available_items?: AvailableLicense[]
  results?: AvailableLicense[]
  count?: number
}

export interface PlanSplit {
  name: string
  qty: string
  unit_price: string
  planned_cif_fc: string
}

export interface PlanGroup {
  id: number
  description: string
  serials: string[]
  memberIds: number[]
  total_qty: string
  available_qty: string
  itemNames: string[]
  splits: PlanSplit[]
}

export interface TransferLetterPayload {
  parties: Array<{
    company_name: string
    address_line1: string
    address_line2: string
    template_id: number | string
  }>
  cif_edits: Record<string, string | number>
  include_license_copy: boolean
  selected_items: number[]
  include_todays_date: boolean
  format: 'zip' | 'pdf'
}
