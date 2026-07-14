// Non-component exports for LicenseFilters — split out to satisfy
// react-refresh/only-export-components (fast refresh requires component-only files).

import type { LicenseListParams } from '../types'

export interface LicenseFilterState {
  license_type: string
  company: number | null
  active_only: boolean
  ordering: string
  expiry_after: string
  expiry_before: string
}

export const DEFAULT_FILTERS: LicenseFilterState = {
  license_type: 'ALL',
  company: null,
  active_only: true,
  ordering: '-license_date',
  expiry_after: '',
  expiry_before: '',
}

export function filtersToParams(f: LicenseFilterState): LicenseListParams {
  const params: LicenseListParams = {}
  if (f.license_type && f.license_type !== 'ALL') params.license_type = f.license_type
  if (f.company) params.company = f.company
  if (f.active_only) params.active_only = true
  if (f.ordering) params.ordering = f.ordering
  if (f.expiry_after) params.expiry_after = f.expiry_after
  if (f.expiry_before) params.expiry_before = f.expiry_before
  return params
}
