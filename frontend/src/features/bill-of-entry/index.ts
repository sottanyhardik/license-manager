// Public barrel for the bill-of-entry feature.
// Import from here in pages, app router, and other features.

// Types
export type {
  BOE,
  BOEListParams,
  BOEFormValues,
  RowDetail,
  RowDetailFormValues,
  LedgerUploadResponse,
  TaskStatusResponse,
  PaginatedResponse,
} from './types'

// Queries
export {
  useBOEs,
  useBOE,
  useBOERows,
  useTaskStatus,
} from './queries'

// Mutations
export {
  useCreateBOE,
  useUpdateBOE,
  useAddBOERow,
  useUpdateBOERow,
  useDeleteBOERow,
  useResolveDispute,
  useUploadLedger,
} from './mutations'

// Components
export { default as BOERowsTable } from './components/BOERowsTable'
export { default as DisputeResolver } from './components/DisputeResolver'
export { default as LedgerUpload } from './components/LedgerUpload'

// Pages (lazy-loaded by the router — don't re-export from here to avoid
// pulling them into the main bundle; the router uses dynamic import directly).
export { default as BOEList } from './pages/BOEList'
export { default as BOEDetail } from './pages/BOEDetail'
