// Bill-of-entry feature types — shapes match /api/v1/bill-of-entries/* DRF responses.
// Nullable fields use `string | null` where the API may return null explicitly;
// optional (?) for fields that may be absent from list vs detail responses.

import type { PaginatedResponse, ListParams } from '@/shared/types/api'

export type { PaginatedResponse }

// ── Row detail (single SR row inside a BOE) ───────────────────────────────────

export interface RowDetail {
  id: number
  sr_number: number
  row_type: 'AR' | 'AT'
  transaction_type: 'C' | 'D'
  cif_inr: string
  cif_fc: string
  qty: string
  is_frozen: boolean
  is_dispute: boolean
  license_number: string | null
  item_description: string | null
  hs_code: string | null
  item_serial_number: number | null
  condition_type: string | null
  purchase_status: string | null
}

// ── Bill of Entry ─────────────────────────────────────────────────────────────

export interface BOE {
  id: number
  company: number | null
  company_name: string | null
  bill_of_entry_number: string
  bill_of_entry_date: string | null
  port: number | null
  port_name: string | null
  exchange_rate: string
  product_name: string
  allotment: number[]
  invoice_no: string | null
  invoice_date: string | null
  is_fetch: boolean
  boe_pdf_copy: string | null
  failed: number
  appraisement: string | null
  /** CharField on backend — stays as string */
  ooc_date: string | null
  cha: string | null
  comments: string | null
  item_details: RowDetail[]
  total_inr: string
  total_fc: string
  total_quantity: string
  licenses: string
  unit_price: string
  created_on: string | null
  modified_on: string | null
}

// ── List / filter params ───────────────────────────────────────────────────────

export interface BOEListParams extends ListParams {
  company?: number
  port?: number
  is_fetch?: boolean
  bill_of_entry_date_after?: string
  bill_of_entry_date_before?: string
  bill_of_entry_number?: string
}

// ── Form values ────────────────────────────────────────────────────────────────

export interface BOEFormValues {
  company: number | null
  bill_of_entry_number: string
  bill_of_entry_date: string | null
  port: number | null
  exchange_rate: string
  product_name: string
  invoice_no: string | null
  invoice_date: string | null
  ooc_date: string | null
  cha: string | null
  comments: string | null
  appraisement: string | null
}

export interface RowDetailFormValues {
  sr_number: number
  transaction_type: 'C' | 'D'
  cif_inr: string
  cif_fc: string
  qty: string
}

// ── Ledger upload / async task ────────────────────────────────────────────────

export interface LedgerUploadResponse {
  task_id: string
  status: string
}

export interface TaskStatusResponse {
  task_id: string
  status: 'pending' | 'running' | 'success' | 'failure'
  result?: unknown
}
