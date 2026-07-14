// Barrel export for the masters feature.
// Import from '@/features/masters' to get types, query hooks, and components.
// Pages are lazy-loaded via router.tsx — do not import them here to avoid
// bundling them into the shared chunk.

// Types
export type {
  Company,
  Port,
  HSCode,
  ItemGroup,
  ItemName,
  SionNormClass,
  ExchangeRate,
  PaginatedResponse,
  ListParams,
} from './types'

// Query hooks — all master queries and mutations
export {
  // Companies
  useCompanies,
  useCompaniesAll,
  useCreateCompany,
  useUpdateCompany,
  useDeleteCompany,
  // Ports
  usePorts,
  usePortsAll,
  useCreatePort,
  useUpdatePort,
  useDeletePort,
  // HS Codes
  useHSCodes,
  useHSCodesAll,
  useCreateHSCode,
  useUpdateHSCode,
  useDeleteHSCode,
  // Item Groups
  useItemGroups,
  useItemGroupsAll,
  useCreateItemGroup,
  useUpdateItemGroup,
  useDeleteItemGroup,
  // Item Names
  useItemNames,
  useItemNamesAll,
  useCreateItemName,
  useUpdateItemName,
  useDeleteItemName,
  // SION Norm Classes
  useSionNormClasses,
  useSionNormClassesAll,
  useCreateSionNormClass,
  useUpdateSionNormClass,
  useDeleteSionNormClass,
  // Exchange Rates
  useExchangeRates,
  useExchangeRatesAll,
  useCreateExchangeRate,
  useUpdateExchangeRate,
  useDeleteExchangeRate,
} from './queries'

// Reusable components
export { MasterSelect } from './components/MasterSelect'
export type { MasterSelectProps } from './components/MasterSelect'
export { MasterDataTable } from './components/MasterDataTable'
export type { MasterDataTableProps } from './components/MasterDataTable'
