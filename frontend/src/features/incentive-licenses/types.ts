// incentive-licenses/types.ts

export type LicenseType = 'RODTEP' | 'ROSTL' | 'MEIS'
export type SoldStatus = 'NO' | 'PARTIAL' | 'YES'

export interface IncentiveLicense {
  id: number
  license_type: LicenseType
  license_number: string
  license_date: string | null
  license_expiry_date: string | null
  exporter: number | null
  exporter_name: string | null
  port_code: number | null
  port_display: string | null
  license_value: string // Decimal as string
  sold_value: string // read-only, Decimal as string
  balance_value: string // read-only, Decimal as string
  sold_status: SoldStatus // read-only
  is_active: boolean
  notes: string
  created_on: string | null
  modified_on: string | null
}

export interface IncentiveLicenseFormValues {
  license_type: LicenseType | ''
  license_number: string
  license_date: string
  exporter: number | null
  port_code: number | null
  license_value: string
  is_active: boolean
  notes: string
}
