// TanStack Query hooks for the allotments feature.
//
// Conventions:
//   - queryFn returns response data directly so callers get typed data.
//   - List hooks accept optional AllotmentListParams for server-side filtering.
//   - enabled: id > 0 guards against queries with zero/undefined ids.
//   - All successful mutations invalidate ['allotments'] so list stays fresh.
//   - staleTime: 30 s for list; detail uses 30 s too (allotments change often).

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query'
import { toast } from 'sonner'
import { normaliseApiErrorString } from '@/shared/utils/errors'
import {
  allocateItems,
  copyAllotment,
  createAllotment,
  deleteAllotment,
  deleteAllotmentItem,
  fetchAllotment,
  fetchAllotments,
  fetchAvailableLicenses,
  generateAllotmentPdf,
  updateAllotment,
} from './api'
import type {
  Allotment,
  AllocateItemsResponse,
  AllocationEntry,
  AllotmentFormValues,
  AllotmentListParams,
  AvailableLicensesParams,
  AvailableLicensesResponse,
  GeneratePdfResponse,
  PaginatedAllotments,
} from './types'

const STALE_30S = 30 * 1000

// ─── List ──────────────────────────────────────────────────────────────────────

export function useAllotments(
  params?: AllotmentListParams,
): UseQueryResult<PaginatedAllotments> {
  return useQuery({
    queryKey: ['allotments', params],
    queryFn: () => fetchAllotments(params),
    staleTime: STALE_30S,
  })
}

// ─── Detail ────────────────────────────────────────────────────────────────────

export function useAllotment(id: number | null): UseQueryResult<Allotment> {
  return useQuery({
    queryKey: ['allotments', id],
    queryFn: () => fetchAllotment(id!),
    enabled: id !== null && id > 0,
    staleTime: STALE_30S,
  })
}

// ─── Create ────────────────────────────────────────────────────────────────────

export function useCreateAllotment(): UseMutationResult<
  Allotment,
  Error,
  AllotmentFormValues
> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: createAllotment,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['allotments'] })
      toast.success('Allotment created successfully.')
    },
    onError: (err) => {
      toast.error(normaliseApiErrorString(err))
    },
  })
}

// ─── Update ────────────────────────────────────────────────────────────────────

export function useUpdateAllotment(
  id: number,
): UseMutationResult<Allotment, Error, Partial<AllotmentFormValues>> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (payload) => updateAllotment(id, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['allotments', id] })
      void qc.invalidateQueries({ queryKey: ['allotments'] })
      toast.success('Allotment updated successfully.')
    },
    onError: (err) => {
      toast.error(normaliseApiErrorString(err))
    },
  })
}

// ─── Delete ────────────────────────────────────────────────────────────────────

export function useDeleteAllotment(): UseMutationResult<void, Error, number> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: deleteAllotment,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['allotments'] })
      toast.success('Allotment deleted.')
    },
    onError: (err) => {
      toast.error(normaliseApiErrorString(err))
    },
  })
}

// ─── Generate PDF ──────────────────────────────────────────────────────────────

export function useGenerateAllotmentPdf(): UseMutationResult<
  GeneratePdfResponse,
  Error,
  number
> {
  return useMutation({
    mutationFn: generateAllotmentPdf,
    onSuccess: () => {
      toast.success('PDF generation started.')
    },
    onError: (err) => {
      toast.error(normaliseApiErrorString(err))
    },
  })
}

// ─── Available licenses (allocation panel) ─────────────────────────────────────

export function useAvailableLicenses(
  allotmentId: number | null,
  params: AvailableLicensesParams,
  enabled = true,
): UseQueryResult<AvailableLicensesResponse> {
  return useQuery({
    queryKey: ['allotments', allotmentId, 'available-licenses', params],
    queryFn: () => fetchAvailableLicenses(allotmentId!, params),
    enabled: enabled && allotmentId !== null && allotmentId > 0,
    staleTime: STALE_30S,
    placeholderData: (prev) => prev,
  })
}

// ─── Allocate items ────────────────────────────────────────────────────────────

export function useAllocateItems(
  allotmentId: number,
): UseMutationResult<AllocateItemsResponse, Error, AllocationEntry[]> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (items) => allocateItems(allotmentId, items),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['allotments', allotmentId] })
    },
    onError: (err) => {
      toast.error(normaliseApiErrorString(err))
    },
  })
}

// ─── Delete allotment item ─────────────────────────────────────────────────────

export function useDeleteAllotmentItem(
  allotmentId: number,
): UseMutationResult<{ message?: string }, Error, number> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (itemId) => deleteAllotmentItem(allotmentId, itemId),
    onSuccess: (data) => {
      void qc.invalidateQueries({ queryKey: ['allotments', allotmentId] })
      toast.success(data.message ?? 'Allocation removed.')
    },
    onError: (err) => {
      toast.error(normaliseApiErrorString(err))
    },
  })
}

// ─── Copy allotment ────────────────────────────────────────────────────────────

export function useCopyAllotment(): UseMutationResult<Allotment, Error, number> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: copyAllotment,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['allotments'] })
      toast.success('Allotment copied successfully.')
    },
    onError: (err) => {
      toast.error(normaliseApiErrorString(err))
    },
  })
}
