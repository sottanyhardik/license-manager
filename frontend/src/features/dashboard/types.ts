// Dashboard feature — API response types.
// These mirror the shapes returned by /api/v1/dashboard/* endpoints exactly.

export interface DashboardStats {
  total_licenses: number
  active_licenses: number
  expired_licenses: number
  null_licenses: number
  expiring_soon: number
  total_balance_cif: string
  recent_boes: number
  recent_allotments: number
  low_balance_licenses: number
  /** BD-003: Count of licenses whose balance_cif has gone negative. */
  negative_balance_licenses?: number
}

export interface UtilisationItem {
  license_number: string
  balance_cif: string
}

export interface ActivityItem {
  month: string
  boe_count: number
  allotment_count: number
}

export interface ExpiringLicense {
  license_number: string
  license_expiry_date: string
  balance_cif: string
  days_to_expiry: number
}
