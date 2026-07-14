// TanStack Query mutation hooks for the licenses feature.
//
// All successful mutations invalidate ['licenses'] so list and detail
// views stay in sync without manual refetch calls.

import {
  useMutation,
  useQueryClient,
  type UseMutationResult,
} from '@tanstack/react-query'
import { toast } from 'sonner'
import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import { normaliseApiErrorString } from '@/shared/utils/errors'
import type { License, LicenseFormValues } from './types'

// ─── Create ────────────────────────────────────────────────────────────────────

export function useCreateLicense(): UseMutationResult<License, Error, LicenseFormValues> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (values: LicenseFormValues) => {
      const { data } = await apiClient.post<License>(ENDPOINTS.LICENSES.LIST, values)
      return data
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['licenses'] })
      toast.success('License created successfully.')
    },
    onError: (err) => {
      toast.error(normaliseApiErrorString(err))
    },
  })
}

// ─── Update ────────────────────────────────────────────────────────────────────

export function useUpdateLicense(
  id: number,
): UseMutationResult<License, Error, Partial<LicenseFormValues>> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (values: Partial<LicenseFormValues>) => {
      const { data } = await apiClient.patch<License>(
        ENDPOINTS.LICENSES.DETAIL(id),
        values,
      )
      return data
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['licenses'] })
      toast.success('License updated successfully.')
    },
    onError: (err) => {
      toast.error(normaliseApiErrorString(err))
    },
  })
}

// ─── Delete ────────────────────────────────────────────────────────────────────

export function useDeleteLicense(): UseMutationResult<void, Error, number> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(ENDPOINTS.LICENSES.DETAIL(id))
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['licenses'] })
      toast.success('License deleted successfully.')
    },
    onError: (err) => {
      toast.error(normaliseApiErrorString(err))
    },
  })
}

// ─── Inline field patch (condition sheet / notes / etc.) ──────────────────────

export function usePatchLicenseField(
  id: number,
): UseMutationResult<License, Error, Record<string, string>> {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: async (fields: Record<string, string>) => {
      const { data } = await apiClient.patch<License>(
        ENDPOINTS.LICENSES.DETAIL(id),
        fields,
      )
      return data
    },
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['licenses', id] })
    },
    onError: (err) => {
      toast.error(normaliseApiErrorString(err))
    },
  })
}

// ─── Generate PDF task ────────────────────────────────────────────────────────

export function useGenerateLicensePDF(): UseMutationResult<
  { task_id?: string; url?: string },
  Error,
  number
> {
  return useMutation({
    mutationFn: async (id: number) => {
      const { data } = await apiClient.post<{ task_id?: string; url?: string }>(
        ENDPOINTS.LICENSES.GENERATE_PDF(id),
      )
      return data
    },
    onSuccess: () => {
      toast.success('PDF generation started.')
    },
    onError: (err) => {
      toast.error(normaliseApiErrorString(err))
    },
  })
}
