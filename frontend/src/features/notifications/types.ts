// Notification feature types — shapes match /api/v1/notifications/* DRF responses.
// BD-003: LicenseBalanceNotification tracks negative-balance exceptions.

export interface LicenseBalanceNotification {
  id: number
  license: number
  license_number: string
  status: 'active' | 'acknowledged' | 'resolved'
  balance_cif: string
  last_boe_reference: string
  acknowledged_by: number | null
  acknowledged_by_username: string | null
  acknowledged_at: string | null
  acknowledgement_remarks: string
  resolved_by: number | null
  resolved_by_username: string | null
  resolved_at: string | null
  resolution_remarks: string
  created_at: string
  updated_at: string
}
