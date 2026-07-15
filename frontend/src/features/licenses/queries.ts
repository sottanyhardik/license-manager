// TanStack Query hooks for the licenses feature.
//
// Conventions:
//   - queryFn returns response.data directly so callers get typed data.
//   - List hooks accept optional LicenseListParams for server-side filtering.
//   - enabled: !!id guards against queries with undefined ids.
//   - STALE_5_MIN for detail data; list stays stale until navigated back.

import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import type {
  ExportItem,
  HistoryEvent,
  License,
  LicenseBalance,
  LicenseDocument,
  LicenseImportItem,
  LicenseListParams,
  ItemUsage,
  PaginatedResponse,
} from './types'

const STALE_5_MIN = 5 * 60 * 1000

// ─── List ──────────────────────────────────────────────────────────────────────

export function useLicenses(
  params?: LicenseListParams,
): UseQueryResult<PaginatedResponse<License>> {
  return useQuery({
    queryKey: ['licenses', params],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<License>>(
        ENDPOINTS.LICENSES.LIST,
        { params },
      )
      return data
    },
    staleTime: STALE_5_MIN,
  })
}

// ─── Detail ────────────────────────────────────────────────────────────────────

export function useLicense(id: number | null): UseQueryResult<License> {
  return useQuery({
    queryKey: ['licenses', id],
    queryFn: async () => {
      const { data } = await apiClient.get<License>(
        ENDPOINTS.LICENSES.DETAIL(id!),
      )
      return data
    },
    enabled: id !== null && id > 0,
    staleTime: STALE_5_MIN,
  })
}

// ─── Import items ──────────────────────────────────────────────────────────────

export function useLicenseItems(
  licenseId: number | null,
): UseQueryResult<LicenseImportItem[]> {
  return useQuery({
    queryKey: ['licenses', licenseId, 'items'],
    queryFn: async () => {
      const { data: payload } = await apiClient.get(
        ENDPOINTS.LICENSES.ITEMS(licenseId!),
      )
      // The axios interceptor wraps paginated responses as { data: T[], pagination: {...} }.
      // Extract the items array from whichever shape arrives.
      if (Array.isArray(payload)) return payload as LicenseImportItem[]
      if (payload && typeof payload === 'object' && 'data' in payload && Array.isArray(payload.data))
        return payload.data as LicenseImportItem[]
      return [] as LicenseImportItem[]
    },
    enabled: licenseId !== null && licenseId > 0,
    staleTime: STALE_5_MIN,
  })
}

// ─── Balance ──────────────────────────────────────────────────────────────────

export function useLicenseBalance(
  licenseId: number | null,
): UseQueryResult<LicenseBalance> {
  return useQuery({
    queryKey: ['licenses', licenseId, 'balance'],
    queryFn: async () => {
      const { data } = await apiClient.get<LicenseBalance>(
        ENDPOINTS.LICENSES.BALANCE(licenseId!),
      )
      return data
    },
    enabled: licenseId !== null && licenseId > 0,
    staleTime: STALE_5_MIN,
  })
}

// ─── Export items ─────────────────────────────────────────────────────────────

export function useLicenseExportItems(
  licenseId: number | null,
): UseQueryResult<ExportItem[]> {
  return useQuery({
    queryKey: ['licenses', licenseId, 'export-items'],
    queryFn: async () => {
      const { data: payload } = await apiClient.get(
        ENDPOINTS.LICENSES.EXPORT_ITEMS(licenseId!),
      )
      if (Array.isArray(payload)) return payload as ExportItem[]
      if (payload && typeof payload === 'object' && 'data' in payload && Array.isArray(payload.data))
        return payload.data as ExportItem[]
      return [] as ExportItem[]
    },
    enabled: licenseId !== null && licenseId > 0,
    staleTime: STALE_5_MIN,
  })
}

// ─── Documents ────────────────────────────────────────────────────────────────

export function useLicenseDocuments(
  licenseId: number | null,
): UseQueryResult<LicenseDocument[]> {
  return useQuery({
    queryKey: ['licenses', licenseId, 'documents'],
    queryFn: async () => {
      const res = await apiClient.get<{ data: LicenseDocument[] } | LicenseDocument[]>(
        ENDPOINTS.LICENSES.DOCUMENTS(licenseId!),
      )
      // Handle both envelope ({ data: [...] }) and direct array responses.
      const payload = res.data
      if (Array.isArray(payload)) return payload
      if (payload && 'data' in payload && Array.isArray(payload.data)) return payload.data
      return []
    },
    enabled: licenseId !== null && licenseId > 0,
    staleTime: STALE_5_MIN,
  })
}

// ─── History ──────────────────────────────────────────────────────────────────

export function useLicenseHistory(
  licenseId: number | null,
): UseQueryResult<HistoryEvent[]> {
  return useQuery({
    queryKey: ['licenses', licenseId, 'history'],
    queryFn: async () => {
      const { data: payload } = await apiClient.get(
        ENDPOINTS.LICENSES.HISTORY(licenseId!),
      )
      if (Array.isArray(payload)) return payload as HistoryEvent[]
      if (payload && typeof payload === 'object' && 'data' in payload && Array.isArray(payload.data))
        return payload.data as HistoryEvent[]
      return [] as HistoryEvent[]
    },
    enabled: licenseId !== null && licenseId > 0,
    staleTime: STALE_5_MIN,
  })
}

// ─── Item usage (expand-row detail) ──────────────────────────────────────────

export function useLicenseItemUsage(
  licenseId: number | null,
  itemId: number | null,
  type: 'import' | 'export' | null,
): UseQueryResult<ItemUsage> {
  return useQuery({
    queryKey: ['licenses', licenseId, 'item-usage', itemId, type],
    queryFn: async () => {
      const { data } = await apiClient.get<ItemUsage>(
        ENDPOINTS.LICENSES.ITEM_USAGE(licenseId!),
        { params: { item_id: itemId, type } },
      )
      return data
    },
    enabled:
      licenseId !== null &&
      licenseId > 0 &&
      itemId !== null &&
      itemId > 0 &&
      type !== null,
    staleTime: 0, // always fresh — usage changes with every BOE/allotment
  })
}
