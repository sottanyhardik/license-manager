import type { PaginatedResponse, ListParams } from '@/shared/types/api'
export type { PaginatedResponse }

// Direction choices from backend
export type TradeDirection = 'PURCHASE' | 'SALE' | 'COMMISSION_PURCHASE' | 'COMMISSION_SALE'
export type TradeLicenseType = 'DFIA' | 'INCENTIVE'
export type TradeBillingMode = 'QTY' | 'CIF_INR' | 'FOB_INR'

export interface TradeCompany {
  id: number
  name: string
}

export interface TradeLine {
  id?: number | string
  sr_number: number | { id: number; label?: string } | null
  sr_number_label?: string | null
  condition_type?: string
  description: string
  hsn_code: string
  mode: TradeBillingMode
  qty_kg: string       // Decimal as string from API
  rate_inr_per_kg: string
  cif_fc: string
  exc_rate: string
  cif_inr: string
  fob_inr: string
  pct: string          // 3 decimal places
  amount_inr: string
  computed_amount?: number
}

export interface IncentiveTradeLine {
  id?: number | string
  incentive_license: number | null
  incentive_license_label?: string | null
  license_value: string
  rate_pct: string     // 3 decimal places
  amount_inr: string
}

export interface TradePayment {
  id?: number | string
  date: string
  amount: string
  note: string
}

export interface LinkedTradeInfo {
  id: number
  direction: TradeDirection
  direction_label: string
  invoice_number: string
  total_amount: string
  paid_or_received: string
  due_amount: string
}

export interface Trade {
  id: number
  direction: TradeDirection
  direction_label: string
  license_type: TradeLicenseType
  license_type_label: string
  incentive_license: string | null   // comma-separated license numbers (read)
  boe: { id: number; bill_of_entry_number?: string } | null
  boe_label?: string | null
  from_company: TradeCompany | null
  to_company: TradeCompany | null
  from_company_label?: string
  to_company_label?: string
  from_pan?: string | null
  from_gst?: string | null
  from_addr_line_1?: string | null
  from_addr_line_2?: string | null
  to_pan?: string | null
  to_gst?: string | null
  to_addr_line_1?: string | null
  to_addr_line_2?: string | null
  invoice_number: string
  invoice_date: string | null
  remarks?: string | null
  subtotal_amount: string
  roundoff: string
  total_amount: string
  paid_or_received: string
  due_amount: string
  purchase_invoice_copy?: string | null
  lines: TradeLine[]
  incentive_lines: IncentiveTradeLine[]
  payments: TradePayment[]
  linked_trade_id?: number | null
  linked_trade_info?: LinkedTradeInfo | null
  created_on: string
}

export interface TradeListParams extends ListParams {
  direction?: TradeDirection
  license_type?: TradeLicenseType
  from_company?: number
  to_company?: number
  invoice_date_after?: string
  invoice_date_before?: string
  search?: string
}

export interface TradeFormValues {
  direction: TradeDirection
  license_type: TradeLicenseType
  incentive_license?: number | null
  boe?: number | null
  from_company: number | null
  to_company: number | null
  invoice_number: string
  invoice_date: string | null
  remarks?: string
  lines: TradeLine[]
  incentive_lines: IncentiveTradeLine[]
  payments: TradePayment[]
  auto_create_paired?: boolean
}
