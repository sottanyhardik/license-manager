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
  /** Scheme code display string (e.g. "DFIA", "RODTEP") — present in list. */
  scheme_code_display?: string | null
  license_date: string | null
  license_expiry_date: string | null
  is_expired?: boolean | null
  /** Days until expiry. Negative means already expired. */
  days_to_expiry?: number
  company?: number | null
  company_label?: string | null
  exporter_name?: string | null
  port_name?: string | null
  purchase_status?: string | null
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
  notes?: string
}
