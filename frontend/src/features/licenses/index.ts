// Public barrel for the licenses feature.
// Import from here in pages, app router, and other features.

// Types
export type {
  License,
  LicenseBalance,
  LicenseFlags,
  LicenseImportItem,
  LicenseExportItem,
  LicenseListParams,
  LicenseFormValues,
  LicenseType,
  ItemUsage,
  ItemUsageBOE,
  ItemUsageAllotment,
} from './types'

// Queries
export {
  useLicenses,
  useLicense,
  useLicenseItems,
  useLicenseBalance,
  useLicenseItemUsage,
} from './queries'

// Mutations
export {
  useCreateLicense,
  useUpdateLicense,
  useDeleteLicense,
  usePatchLicenseField,
  useGenerateLicensePDF,
} from './mutations'

// Components
export { LicenseStatusBadge } from './components/LicenseStatusBadge'
export { LicenseCard } from './components/LicenseCard'
export { LicenseBalancePanel } from './components/LicenseBalancePanel'
export { LicenseImportItems } from './components/LicenseImportItems'
export { LicenseFilters } from './components/LicenseFilters'
export {
  DEFAULT_FILTERS,
  filtersToParams,
  type LicenseFilterState,
} from './components/licenseFilterConstants'
export { LicenseFormModal } from './components/LicenseFormModal'

// Pages (lazy-loaded by the router — don't re-export from here to avoid
// pulling them into the main bundle; the router uses dynamic import directly).
