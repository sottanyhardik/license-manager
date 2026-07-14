// TanStack Query hooks for the dashboard feature.
//
// Conventions match licenses/queries.ts:
//   - queryFn returns response.data directly.
//   - staleTime = 5 min to match the backend cache TTL.

import { useQuery, type UseQueryResult } from '@tanstack/react-query'
import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import type { DashboardStats, UtilisationItem, ActivityItem, ExpiringLicense } from './types'

const STALE_5_MIN = 5 * 60 * 1000

// ─── Stats KPIs ───────────────────────────────────────────────────────────────

export function useDashboardStats(): UseQueryResult<DashboardStats> {
  return useQuery({
    queryKey: ['dashboard', 'stats'],
    queryFn: async () => {
      const { data } = await apiClient.get<DashboardStats>(ENDPOINTS.DASHBOARD.STATS)
      return data
    },
    staleTime: STALE_5_MIN,
  })
}

// ─── Utilisation chart ────────────────────────────────────────────────────────

export function useUtilisationChart(): UseQueryResult<UtilisationItem[]> {
  return useQuery({
    queryKey: ['dashboard', 'utilisation'],
    queryFn: async () => {
      const { data } = await apiClient.get<UtilisationItem[]>(
        ENDPOINTS.DASHBOARD.UTILISATION_CHART,
      )
      return data
    },
    staleTime: STALE_5_MIN,
  })
}

// ─── Activity chart ───────────────────────────────────────────────────────────

export function useActivityChart(): UseQueryResult<ActivityItem[]> {
  return useQuery({
    queryKey: ['dashboard', 'activity'],
    queryFn: async () => {
      const { data } = await apiClient.get<ActivityItem[]>(
        ENDPOINTS.DASHBOARD.ACTIVITY_CHART,
      )
      return data
    },
    staleTime: STALE_5_MIN,
  })
}

// ─── Expiring licenses ────────────────────────────────────────────────────────

export function useExpiringLicenses(): UseQueryResult<ExpiringLicense[]> {
  return useQuery({
    queryKey: ['dashboard', 'expiring'],
    queryFn: async () => {
      const { data } = await apiClient.get<ExpiringLicense[]>(
        ENDPOINTS.DASHBOARD.EXPIRING_LICENSES,
      )
      return data
    },
    staleTime: STALE_5_MIN,
  })
}
