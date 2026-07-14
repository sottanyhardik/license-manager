import { useMutation } from '@tanstack/react-query'
import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import type {
  BalanceReportParams,
  ItemReportParams,
  PivotReportParams,
  LedgerReportParams,
} from './types'

interface DispatchResult {
  task_id: string
}

export function useGenerateBalanceReport() {
  return useMutation<DispatchResult, Error, BalanceReportParams>({
    mutationFn: async (params) => {
      const { data } = await apiClient.post<DispatchResult>(
        ENDPOINTS.REPORTS.BALANCE,
        params,
      )
      return data
    },
  })
}

export function useGenerateItemReport() {
  return useMutation<DispatchResult, Error, ItemReportParams>({
    mutationFn: async (params) => {
      const { data } = await apiClient.post<DispatchResult>(
        ENDPOINTS.REPORTS.ITEMS,
        params,
      )
      return data
    },
  })
}

export function useGeneratePivotReport() {
  return useMutation<DispatchResult, Error, PivotReportParams>({
    mutationFn: async (params) => {
      const { data } = await apiClient.post<DispatchResult>(
        ENDPOINTS.REPORTS.PIVOT,
        params,
      )
      return data
    },
  })
}

export function useGenerateLedgerReport() {
  return useMutation<DispatchResult, Error, LedgerReportParams>({
    mutationFn: async (params) => {
      const { data } = await apiClient.post<DispatchResult>(
        ENDPOINTS.REPORTS.LEDGER,
        params,
      )
      return data
    },
  })
}
