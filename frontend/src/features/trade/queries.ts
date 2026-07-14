// TanStack Query hooks for the trades feature.
//
// Conventions:
//   - queryFn returns response.data directly so callers get typed data.
//   - List hooks accept optional TradeListParams for server-side filtering.
//   - enabled: !!id guards against queries with undefined ids.
//   - STALE_5_MIN for detail data; list stays stale until navigated back.

import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import type { Trade, TradeListParams, PaginatedResponse } from './types'

const STALE_5_MIN = 5 * 60 * 1000

// ─── List ──────────────────────────────────────────────────────────────────────

export function useTrades(
  params?: TradeListParams,
): UseQueryResult<PaginatedResponse<Trade>> {
  return useQuery({
    queryKey: ['trades', params],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<Trade>>(
        ENDPOINTS.TRADES.LIST,
        { params },
      )
      return data
    },
    staleTime: STALE_5_MIN,
  })
}

// ─── Detail ────────────────────────────────────────────────────────────────────

export function useTrade(id: number | null): UseQueryResult<Trade> {
  return useQuery({
    queryKey: ['trades', id],
    queryFn: async () => {
      const { data } = await apiClient.get<Trade>(
        ENDPOINTS.TRADES.DETAIL(id!),
      )
      return data
    },
    enabled: id !== null && id > 0,
    staleTime: STALE_5_MIN,
  })
}

// ─── Summary ──────────────────────────────────────────────────────────────────

interface TradeSummaryData {
  subtotal_amount: string
  roundoff: string
  total_amount: string
  paid_or_received: string
  due_amount: string
}

export function useTradeSummary(id: number | null): UseQueryResult<TradeSummaryData> {
  return useQuery({
    queryKey: ['trades', id, 'summary'],
    queryFn: async () => {
      const { data } = await apiClient.get<TradeSummaryData>(
        ENDPOINTS.TRADES.SUMMARY(id!),
      )
      return data
    },
    enabled: id !== null && id > 0,
    staleTime: 0, // always fresh — amounts change with payments
  })
}
