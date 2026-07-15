// License feature types — shapes match /api/v1/licenses/* DRF responses.
// Nullable fields use string | null where the API may return null explicitly;
// optional (?) for fields that may be absent from list vs detail responses.

import type { PaginatedResponse, ListParams } from '@/shared/types/api'

export type { PaginatedResponse }

// ── Core entities ──────────────────────────────────────────────────────────────

export interface License {
  id: number
  license_number: string
  /** License type — present in detail responses. In list responses use
   * scheme_code_display or parse from license_number prefix. */
  license_type?: LicenseType
  license_date: string | null
  license_expiry_date: string | null
  is_expired?: boolean | null
  /** Days until expiry. Negative means already expired. */
  days_to_expiry?: number
  /** FK IDs — present in detail responses for edit form pre-fill */
  exporter?: number | null     // same FK as "company" in the form
  company?: number | null
  port?: number | null
  scheme_code?: number | null
  notification_number?: number | null
  purchase_status?: number | null
  /** Display strings (read-only from API) */
  company_label?: string | null
  exporter_name?: string | null
  port_name?: string | null
  port_display?: string | null
  scheme_code_display?: string | null
  notification_number_display?: string | null
  purchase_status_display?: string | null
  /** Scalar fields */
  file_number?: string | null
  registration_number?: string | null
  registration_date?: string | null
  ge_file_number?: number | null
  get_norm_class?: string | null
  /** Available CIF in the license's foreign currency (DFIA = USD). */
  balance_cif?: string | null
  latest_transfer?: string | null
  condition_sheet?: string | null
  balance_report_notes?: string | null
  has_tl?: boolean
  has_copy?: boolean
  balance?: LicenseBalance
  flags?: LicenseFlags
  import_license?: LicenseImportItem[]
  export_license?: LicenseExportItem[]
}

export type LicenseType = 'DFIA' | 'RODTEP' | 'ROSTL' | 'MEIS' | 'INCENTIVE' | string

export interface LicenseBalance {
  balance_cif: string
  ledger_date?: string | null
  /** Total authorised CIF = SUM(export items). */
  total_authorised?: string | null
  /** Total debited CIF = SUM(BOE RowDetails). */
  total_debited?: string | null
  /** Total allotted CIF = SUM(pending AllotmentItems). */
  total_allotted?: string | null
}

export interface LicenseFlags {
  is_expired: boolean
  near_expiry: boolean
  /** True when the license has at least one purchase/trade transaction. */
  has_purchases: boolean
  /** BD-003: Computed balance health status */
  balance_status?: 'healthy' | 'null' | 'negative'
}

// ── Import items (SR rows in the license) ─────────────────────────────────────

export interface LicenseImportItem {
  id: number
  serial_number: string | number
  description?: string | null
  hs_code?: string | null
  hs_code_label?: string | null
  /** Authorised quantity on the SR. */
  quantity: string
  /** Quantity consumed by BOEs. */
  debited_quantity: string
  /** Quantity allotted (not yet debited). */
  allotted_quantity: string
  /** Remaining available = quantity - debited - allotted. */
  available_quantity: string
  /** CIF in foreign currency for this item. */
  cif_fc?: string | null
  /** Balance CIF in foreign currency. */
  balance_cif_fc?: string | null
  /** Planned quantity from LicenseItemPlan (null if no plan exists). */
  planned_quantity?: string | null
  /** Planned CIF FC from LicenseItemPlan (null if no plan exists). */
  planned_cif_fc?: string | null
  /** Mapped item names from the masters. */
  items?: number[]
  items_detail?: Array<{ id: number; name: string }>
  condition_type?: string | null
  norm_class_label?: string | null
}

export interface LicenseExportItem {
  id: number
  description?: string | null
  norm_class_label?: string | null
  cif_fc?: string | null
  fob_fc?: string | null
}

// ── Export items (from /licenses/{id}/export-items/) ─────────────────────────

export interface ExportItem {
  id: number
  license: number
  description?: string | null
  item?: number | null
  item_label?: string | null
  norm_class?: number | null
  norm_class_label?: string | null
  duty_type?: string | null
  net_quantity?: string | null
  old_quantity?: string | null
  unit?: string | null
  fob_fc?: string | null
  fob_inr?: string | null
  currency?: string | null
  value_addition?: string | null
  cif_fc?: string | null
  cif_inr?: string | null
}

// ── Documents ────────────────────────────────────────────────────────────────

export interface LicenseDocument {
  id: number
  license: number
  type: 'LICENSE COPY' | 'TRANSFER LETTER' | 'OTHER'
  file: string
}

// ── History ───────────────────────────────────────────────────────────────────

export interface HistoryEvent {
  event_type: string
  description: string
  timestamp: string | null
  user: string | null
}

// ── Item usage (expanded row detail) ─────────────────────────────────────────

export interface ItemUsageBOE {
  id: number
  bill_of_entry_number: string
  date?: string | null
  port?: string | null
  company?: string | null
  quantity: string
  cif_fc: string
  cif_inr: string
}

export interface ItemUsageAllotment {
  id: number
  company?: string | null
  quantity: string
  cif_fc: string
  cif_inr: string
}

export interface ItemUsage {
  boes: ItemUsageBOE[]
  allotments: ItemUsageAllotment[]
}

// ── List / filter params ───────────────────────────────────────────────────────

export interface LicenseListParams extends ListParams {
  license_type?: string
  company?: number
  active_only?: boolean
  min_balance?: string
  expiry_before?: string
  expiry_after?: string
}

// ── Form values ────────────────────────────────────────────────────────────────

export interface LicenseFormValues {
  license_number: string
  license_type: string
  license_date: string
  license_expiry_date: string
  company: number | null
  port?: number | null
  scheme_code?: number | null
  notification_number?: number | null
  purchase_status?: number | null
  file_number?: string
  registration_number?: string
  registration_date?: string
  notes?: string
}
