// TanStack Query mutation hooks for the trades feature.
//
// All successful mutations invalidate ['trades'] so list and detail
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
import type { Trade, TradeFormValues } from './types'

function invalidate(qc: ReturnType<typeof useQueryClient>) {
  void qc.invalidateQueries({ queryKey: ['trades'] })
}

// ─── Create ────────────────────────────────────────────────────────────────────

export function useCreateTrade(): UseMutationResult<Trade, Error, TradeFormValues> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (values: TradeFormValues) => {
      const { data } = await apiClient.post<Trade>(ENDPOINTS.TRADES.LIST, values)
      return data
    },
    onSuccess: () => {
      invalidate(qc)
      toast.success('Trade created successfully.')
    },
    onError: (err) => {
      toast.error(normaliseApiErrorString(err))
    },
  })
}

// ─── Update ────────────────────────────────────────────────────────────────────

export function useUpdateTrade(
  id: number,
): UseMutationResult<Trade, Error, Partial<TradeFormValues>> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (values: Partial<TradeFormValues>) => {
      const { data } = await apiClient.patch<Trade>(
        ENDPOINTS.TRADES.DETAIL(id),
        values,
      )
      return data
    },
    onSuccess: () => {
      invalidate(qc)
      toast.success('Trade updated successfully.')
    },
    onError: (err) => {
      toast.error(normaliseApiErrorString(err))
    },
  })
}

// ─── Delete ────────────────────────────────────────────────────────────────────

export function useDeleteTrade(): UseMutationResult<void, Error, number> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id: number) => {
      await apiClient.delete(ENDPOINTS.TRADES.DETAIL(id))
    },
    onSuccess: () => {
      invalidate(qc)
      toast.success('Trade deleted successfully.')
    },
    onError: (err) => {
      toast.error(normaliseApiErrorString(err))
    },
  })
}

// ─── Generate Purchase Invoice PDF ───────────────────────────────────────────
// Downloads the PDF as a blob so the Authorization header is included.
// window.open() bypasses request interceptors and receives a 401 from the
// backend — an authenticated apiClient.get() with responseType:'blob' fixes this.

export function useGeneratePurchaseInvoice(): UseMutationResult<void, Error, number> {
  return useMutation({
    mutationFn: async (id: number) => {
      const response = await apiClient.get(ENDPOINTS.TRADES.PURCHASE_INVOICE_PDF(id), {
        responseType: 'blob',
      })
      const url = URL.createObjectURL(response.data as Blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `purchase-invoice-${id}.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    },
    onError: (err) => {
      toast.error(normaliseApiErrorString(err))
    },
  })
}

// ─── Generate Bill of Supply PDF ─────────────────────────────────────────────

export function useGenerateBillOfSupply(): UseMutationResult<void, Error, number> {
  return useMutation({
    mutationFn: async (id: number) => {
      const response = await apiClient.get(ENDPOINTS.TRADES.BILL_OF_SUPPLY_PDF(id), {
        responseType: 'blob',
      })
      const url = URL.createObjectURL(response.data as Blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `bill-of-supply-${id}.pdf`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
    },
    onError: (err) => {
      toast.error(normaliseApiErrorString(err))
    },
  })
}
