// TanStack Query hooks for the bill-of-entry feature.
//
// Conventions:
//   - queryFn returns response.data directly so callers get typed data.
//   - List hooks accept optional BOEListParams for server-side filtering.
//   - enabled: id !== null && id > 0 guards against queries with undefined ids.
//   - STALE_5_MIN for detail data; rows are always fresh (staleTime: 0).

import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import type { BOE, BOEListParams, RowDetail, PaginatedResponse, TaskStatusResponse } from './types'

const STALE_5_MIN = 5 * 60 * 1000

// ── List ───────────────────────────────────────────────────────────────────────

export function useBOEs(params?: BOEListParams): UseQueryResult<PaginatedResponse<BOE>> {
  return useQuery({
    queryKey: ['bill-of-entries', params],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<BOE>>(
        ENDPOINTS.BILL_OF_ENTRY.LIST,
        { params },
      )
      return data
    },
    staleTime: STALE_5_MIN,
  })
}

// ── Detail ─────────────────────────────────────────────────────────────────────

export function useBOE(id: number | null): UseQueryResult<BOE> {
  return useQuery({
    queryKey: ['bill-of-entries', id],
    queryFn: async () => {
      const { data } = await apiClient.get<BOE>(ENDPOINTS.BILL_OF_ENTRY.DETAIL(id!))
      return data
    },
    enabled: id !== null && id > 0,
    staleTime: STALE_5_MIN,
  })
}

// ── Rows ───────────────────────────────────────────────────────────────────────

export function useBOERows(boeId: number | null): UseQueryResult<RowDetail[]> {
  return useQuery({
    queryKey: ['bill-of-entries', boeId, 'rows'],
    queryFn: async () => {
      const { data } = await apiClient.get<RowDetail[]>(
        ENDPOINTS.BILL_OF_ENTRY.ROWS(boeId!),
      )
      return data
    },
    enabled: boeId !== null && boeId > 0,
    staleTime: 0, // always fresh — rows change with every BOE update
  })
}

// ── Async task status (for ledger upload polling) ─────────────────────────────

export function useTaskStatus(
  taskId: string | null,
): UseQueryResult<TaskStatusResponse> {
  return useQuery({
    queryKey: ['task-status', taskId],
    queryFn: async () => {
      const { data } = await apiClient.get<TaskStatusResponse>(
        `/api/v1/tasks/${taskId}/status/`,
      )
      return data
    },
    enabled: taskId !== null && taskId.length > 0,
    // Poll every 2 s while the task is still running; stop when terminal.
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (status === 'success' || status === 'failure') return false
      return 2000
    },
    staleTime: 0,
  })
}
