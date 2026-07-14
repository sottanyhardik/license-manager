// TanStack Query mutation hooks for the bill-of-entry feature.
//
// All successful mutations invalidate ['bill-of-entries'] so list and detail
// views stay in sync without manual refetch calls.

import { useMutation, useQueryClient, type UseMutationResult } from '@tanstack/react-query'
import { toast } from 'sonner'
import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import { normaliseApiErrorString } from '@/shared/utils/errors'
import type {
  BOE,
  BOEFormValues,
  RowDetail,
  RowDetailFormValues,
  LedgerUploadResponse,
} from './types'

// ── Create BOE ─────────────────────────────────────────────────────────────────

export function useCreateBOE(): UseMutationResult<BOE, Error, BOEFormValues> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (values: BOEFormValues) => {
      const { data } = await apiClient.post<BOE>(ENDPOINTS.BILL_OF_ENTRY.LIST, values)
      return data
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['bill-of-entries'] })
      toast.success('Bill of Entry created successfully.')
    },
    onError: (err) => {
      toast.error(normaliseApiErrorString(err))
    },
  })
}

// ── Update BOE (PATCH) ─────────────────────────────────────────────────────────

export function useUpdateBOE(
  id: number,
): UseMutationResult<BOE, Error, Partial<BOEFormValues>> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (values: Partial<BOEFormValues>) => {
      const { data } = await apiClient.patch<BOE>(
        ENDPOINTS.BILL_OF_ENTRY.DETAIL(id),
        values,
      )
      return data
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['bill-of-entries'] })
      toast.success('Bill of Entry updated successfully.')
    },
    onError: (err) => {
      toast.error(normaliseApiErrorString(err))
    },
  })
}

// ── Add row (POST to /rows/) ───────────────────────────────────────────────────

export function useAddBOERow(
  boeId: number,
): UseMutationResult<RowDetail, Error, RowDetailFormValues> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (values: RowDetailFormValues) => {
      const { data } = await apiClient.post<RowDetail>(
        ENDPOINTS.BILL_OF_ENTRY.ROWS(boeId),
        values,
      )
      return data
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['bill-of-entries'] })
      toast.success('Row added successfully.')
    },
    onError: (err) => {
      toast.error(normaliseApiErrorString(err))
    },
  })
}

// ── Update row (PATCH to /rows/:rowId/) — frozen rows rejected by backend ─────

export function useUpdateBOERow(
  boeId: number,
  rowId: number,
): UseMutationResult<RowDetail, Error, Partial<RowDetailFormValues>> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (values: Partial<RowDetailFormValues>) => {
      const { data } = await apiClient.patch<RowDetail>(
        ENDPOINTS.BILL_OF_ENTRY.ROW(boeId, rowId),
        values,
      )
      return data
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['bill-of-entries'] })
      toast.success('Row updated successfully.')
    },
    onError: (err) => {
      toast.error(normaliseApiErrorString(err))
    },
  })
}

// ── Delete row (DELETE /rows/:rowId/) — frozen rows rejected by backend ────────

export function useDeleteBOERow(
  boeId: number,
): UseMutationResult<void, Error, number> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (rowId: number) => {
      await apiClient.delete(ENDPOINTS.BILL_OF_ENTRY.ROW(boeId, rowId))
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['bill-of-entries'] })
      toast.success('Row deleted successfully.')
    },
    onError: (err) => {
      toast.error(normaliseApiErrorString(err))
    },
  })
}

// ── Resolve dispute row (POST /rows/:rowId/resolve-dispute/) ──────────────────

export function useResolveDispute(
  boeId: number,
  rowId: number,
): UseMutationResult<RowDetail, Error, { license_item_id: number }> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (payload: { license_item_id: number }) => {
      const { data } = await apiClient.post<RowDetail>(
        ENDPOINTS.BILL_OF_ENTRY.RESOLVE_DISPUTE(boeId, rowId),
        payload,
      )
      return data
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['bill-of-entries'] })
      toast.success('Dispute resolved successfully.')
    },
    onError: (err) => {
      toast.error(normaliseApiErrorString(err))
    },
  })
}

// ── Upload ledger (multipart/form-data) ───────────────────────────────────────

export function useUploadLedger(): UseMutationResult<LedgerUploadResponse, Error, FormData> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (formData: FormData) => {
      const { data } = await apiClient.post<LedgerUploadResponse>(
        ENDPOINTS.BILL_OF_ENTRY.UPLOAD_LEDGER,
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } },
      )
      return data
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['bill-of-entries'] })
      toast.success('Ledger upload started.')
    },
    onError: (err) => {
      toast.error(normaliseApiErrorString(err))
    },
  })
}
