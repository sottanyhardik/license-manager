// TanStack Query hooks for all master data endpoints.
//
// Conventions:
//   - All list + all-items hooks use staleTime: 10 min (masters change rarely).
//   - List hooks accept optional params (search, page, page_size) for
//     server-side pagination/filtering.
//   - *All() hooks pass ?all=true for unpaginated dropdown data.
//   - Mutation hooks invalidate the matching list query key on success so the
//     UI stays fresh without an explicit refetch call.
//   - queryFn returns only response.data so callers get typed data directly.

import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseMutationResult,
  type UseQueryResult,
} from '@tanstack/react-query'
import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import type {
  Company,
  ExchangeRate,
  HSCode,
  ItemGroup,
  ItemName,
  ListParams,
  PaginatedResponse,
  Port,
  SionNormClass,
} from './types'

const STALE_10_MIN = 10 * 60 * 1000

// ─── Companies ────────────────────────────────────────────────────────────────

export function useCompanies(
  params?: Pick<ListParams, 'search' | 'page' | 'page_size' | 'ordering'>,
): UseQueryResult<PaginatedResponse<Company>> {
  return useQuery({
    queryKey: ['masters', 'companies', params],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<Company>>(
        ENDPOINTS.MASTERS.COMPANIES,
        { params },
      )
      return data
    },
    staleTime: STALE_10_MIN,
  })
}

export function useCompaniesAll(): UseQueryResult<Company[]> {
  return useQuery({
    queryKey: ['masters', 'companies', 'all'],
    queryFn: async () => {
      const { data } = await apiClient.get<Company[]>(ENDPOINTS.MASTERS.COMPANIES, {
        params: { all: true },
      })
      return data
    },
    staleTime: STALE_10_MIN,
  })
}

type CompanyPayload = Omit<Company, 'id'>

export function useCreateCompany(): UseMutationResult<Company, Error, CompanyPayload> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload) => {
      const { data } = await apiClient.post<Company>(ENDPOINTS.MASTERS.COMPANIES, payload)
      return data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['masters', 'companies'] })
    },
  })
}

export function useUpdateCompany(): UseMutationResult<
  Company,
  Error,
  { id: number } & Partial<CompanyPayload>
> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...payload }) => {
      const { data } = await apiClient.patch<Company>(ENDPOINTS.MASTERS.COMPANY(id), payload)
      return data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['masters', 'companies'] })
    },
  })
}

export function useDeleteCompany(): UseMutationResult<void, Error, number> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id) => {
      await apiClient.delete(ENDPOINTS.MASTERS.COMPANY(id))
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['masters', 'companies'] })
    },
  })
}

// ─── Ports ────────────────────────────────────────────────────────────────────

export function usePorts(
  params?: Pick<ListParams, 'search' | 'page' | 'page_size' | 'ordering'>,
): UseQueryResult<PaginatedResponse<Port>> {
  return useQuery({
    queryKey: ['masters', 'ports', params],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<Port>>(ENDPOINTS.MASTERS.PORTS, {
        params,
      })
      return data
    },
    staleTime: STALE_10_MIN,
  })
}

export function usePortsAll(): UseQueryResult<Port[]> {
  return useQuery({
    queryKey: ['masters', 'ports', 'all'],
    queryFn: async () => {
      const { data } = await apiClient.get<Port[]>(ENDPOINTS.MASTERS.PORTS, {
        params: { all: true },
      })
      return data
    },
    staleTime: STALE_10_MIN,
  })
}

type PortPayload = Omit<Port, 'id'>

export function useCreatePort(): UseMutationResult<Port, Error, PortPayload> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload) => {
      const { data } = await apiClient.post<Port>(ENDPOINTS.MASTERS.PORTS, payload)
      return data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['masters', 'ports'] })
    },
  })
}

export function useUpdatePort(): UseMutationResult<Port, Error, { id: number } & Partial<PortPayload>> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...payload }) => {
      const { data } = await apiClient.patch<Port>(ENDPOINTS.MASTERS.PORT(id), payload)
      return data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['masters', 'ports'] })
    },
  })
}

export function useDeletePort(): UseMutationResult<void, Error, number> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id) => {
      await apiClient.delete(ENDPOINTS.MASTERS.PORT(id))
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['masters', 'ports'] })
    },
  })
}

// ─── HS Codes ─────────────────────────────────────────────────────────────────

export function useHSCodes(
  params?: Pick<ListParams, 'search' | 'page' | 'page_size' | 'ordering'>,
): UseQueryResult<PaginatedResponse<HSCode>> {
  return useQuery({
    queryKey: ['masters', 'hs-codes', params],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<HSCode>>(ENDPOINTS.MASTERS.HS_CODES, {
        params,
      })
      return data
    },
    staleTime: STALE_10_MIN,
  })
}

export function useHSCodesAll(): UseQueryResult<HSCode[]> {
  return useQuery({
    queryKey: ['masters', 'hs-codes', 'all'],
    queryFn: async () => {
      const { data } = await apiClient.get<HSCode[]>(ENDPOINTS.MASTERS.HS_CODES, {
        params: { all: true },
      })
      return data
    },
    staleTime: STALE_10_MIN,
  })
}

type HSCodePayload = Omit<HSCode, 'id'>

export function useCreateHSCode(): UseMutationResult<HSCode, Error, HSCodePayload> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload) => {
      const { data } = await apiClient.post<HSCode>(ENDPOINTS.MASTERS.HS_CODES, payload)
      return data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['masters', 'hs-codes'] })
    },
  })
}

export function useUpdateHSCode(): UseMutationResult<
  HSCode,
  Error,
  { id: number } & Partial<HSCodePayload>
> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...payload }) => {
      const { data } = await apiClient.patch<HSCode>(ENDPOINTS.MASTERS.HS_CODE(id), payload)
      return data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['masters', 'hs-codes'] })
    },
  })
}

export function useDeleteHSCode(): UseMutationResult<void, Error, number> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id) => {
      await apiClient.delete(ENDPOINTS.MASTERS.HS_CODE(id))
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['masters', 'hs-codes'] })
    },
  })
}

// ─── Item Groups ──────────────────────────────────────────────────────────────

export function useItemGroups(
  params?: Pick<ListParams, 'search' | 'page' | 'page_size' | 'ordering'>,
): UseQueryResult<PaginatedResponse<ItemGroup>> {
  return useQuery({
    queryKey: ['masters', 'item-groups', params],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<ItemGroup>>(
        ENDPOINTS.MASTERS.ITEM_GROUPS,
        { params },
      )
      return data
    },
    staleTime: STALE_10_MIN,
  })
}

export function useItemGroupsAll(): UseQueryResult<ItemGroup[]> {
  return useQuery({
    queryKey: ['masters', 'item-groups', 'all'],
    queryFn: async () => {
      const { data } = await apiClient.get<ItemGroup[]>(ENDPOINTS.MASTERS.ITEM_GROUPS, {
        params: { all: true },
      })
      return data
    },
    staleTime: STALE_10_MIN,
  })
}

type ItemGroupPayload = Omit<ItemGroup, 'id'>

export function useCreateItemGroup(): UseMutationResult<ItemGroup, Error, ItemGroupPayload> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload) => {
      const { data } = await apiClient.post<ItemGroup>(ENDPOINTS.MASTERS.ITEM_GROUPS, payload)
      return data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['masters', 'item-groups'] })
    },
  })
}

export function useUpdateItemGroup(): UseMutationResult<
  ItemGroup,
  Error,
  { id: number } & Partial<ItemGroupPayload>
> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...payload }) => {
      const { data } = await apiClient.patch<ItemGroup>(ENDPOINTS.MASTERS.ITEM_GROUP(id), payload)
      return data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['masters', 'item-groups'] })
    },
  })
}

export function useDeleteItemGroup(): UseMutationResult<void, Error, number> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id) => {
      await apiClient.delete(ENDPOINTS.MASTERS.ITEM_GROUP(id))
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['masters', 'item-groups'] })
    },
  })
}

// ─── Item Names ───────────────────────────────────────────────────────────────

export function useItemNames(
  params?: Pick<ListParams, 'search' | 'page' | 'page_size' | 'ordering'>,
): UseQueryResult<PaginatedResponse<ItemName>> {
  return useQuery({
    queryKey: ['masters', 'item-names', params],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<ItemName>>(
        ENDPOINTS.MASTERS.ITEM_NAMES,
        { params },
      )
      return data
    },
    staleTime: STALE_10_MIN,
  })
}

export function useItemNamesAll(): UseQueryResult<ItemName[]> {
  return useQuery({
    queryKey: ['masters', 'item-names', 'all'],
    queryFn: async () => {
      const { data } = await apiClient.get<ItemName[]>(ENDPOINTS.MASTERS.ITEM_NAMES, {
        params: { all: true },
      })
      return data
    },
    staleTime: STALE_10_MIN,
  })
}

type ItemNamePayload = Omit<ItemName, 'id'>

export function useCreateItemName(): UseMutationResult<ItemName, Error, ItemNamePayload> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload) => {
      const { data } = await apiClient.post<ItemName>(ENDPOINTS.MASTERS.ITEM_NAMES, payload)
      return data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['masters', 'item-names'] })
    },
  })
}

export function useUpdateItemName(): UseMutationResult<
  ItemName,
  Error,
  { id: number } & Partial<ItemNamePayload>
> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...payload }) => {
      const { data } = await apiClient.patch<ItemName>(ENDPOINTS.MASTERS.ITEM_NAME(id), payload)
      return data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['masters', 'item-names'] })
    },
  })
}

export function useDeleteItemName(): UseMutationResult<void, Error, number> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id) => {
      await apiClient.delete(ENDPOINTS.MASTERS.ITEM_NAME(id))
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['masters', 'item-names'] })
    },
  })
}

// ─── SION Norm Classes ────────────────────────────────────────────────────────

export function useSionNormClasses(
  params?: Pick<ListParams, 'search' | 'page' | 'page_size' | 'ordering'>,
): UseQueryResult<PaginatedResponse<SionNormClass>> {
  return useQuery({
    queryKey: ['masters', 'sion-norm-classes', params],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<SionNormClass>>(
        ENDPOINTS.MASTERS.SION_NORM_CLASSES,
        { params },
      )
      return data
    },
    staleTime: STALE_10_MIN,
  })
}

export function useSionNormClassesAll(): UseQueryResult<SionNormClass[]> {
  return useQuery({
    queryKey: ['masters', 'sion-norm-classes', 'all'],
    queryFn: async () => {
      const { data } = await apiClient.get<SionNormClass[]>(ENDPOINTS.MASTERS.SION_NORM_CLASSES, {
        params: { all: true },
      })
      return data
    },
    staleTime: STALE_10_MIN,
  })
}

type SionNormClassPayload = Omit<SionNormClass, 'id'>

export function useCreateSionNormClass(): UseMutationResult<
  SionNormClass,
  Error,
  SionNormClassPayload
> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload) => {
      const { data } = await apiClient.post<SionNormClass>(
        ENDPOINTS.MASTERS.SION_NORM_CLASSES,
        payload,
      )
      return data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['masters', 'sion-norm-classes'] })
    },
  })
}

export function useUpdateSionNormClass(): UseMutationResult<
  SionNormClass,
  Error,
  { id: number } & Partial<SionNormClassPayload>
> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...payload }) => {
      const { data } = await apiClient.patch<SionNormClass>(
        ENDPOINTS.MASTERS.SION_NORM_CLASS(id),
        payload,
      )
      return data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['masters', 'sion-norm-classes'] })
    },
  })
}

export function useDeleteSionNormClass(): UseMutationResult<void, Error, number> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id) => {
      await apiClient.delete(ENDPOINTS.MASTERS.SION_NORM_CLASS(id))
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['masters', 'sion-norm-classes'] })
    },
  })
}

// ─── Exchange Rates ───────────────────────────────────────────────────────────

export function useExchangeRates(
  params?: Pick<ListParams, 'search' | 'page' | 'page_size' | 'ordering'>,
): UseQueryResult<PaginatedResponse<ExchangeRate>> {
  return useQuery({
    queryKey: ['masters', 'exchange-rates', params],
    queryFn: async () => {
      const { data } = await apiClient.get<PaginatedResponse<ExchangeRate>>(
        ENDPOINTS.MASTERS.EXCHANGE_RATES,
        { params },
      )
      return data
    },
    staleTime: STALE_10_MIN,
  })
}

export function useExchangeRatesAll(): UseQueryResult<ExchangeRate[]> {
  return useQuery({
    queryKey: ['masters', 'exchange-rates', 'all'],
    queryFn: async () => {
      const { data } = await apiClient.get<ExchangeRate[]>(ENDPOINTS.MASTERS.EXCHANGE_RATES, {
        params: { all: true },
      })
      return data
    },
    staleTime: STALE_10_MIN,
  })
}

type ExchangeRatePayload = Omit<ExchangeRate, 'id'>

export function useCreateExchangeRate(): UseMutationResult<
  ExchangeRate,
  Error,
  ExchangeRatePayload
> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (payload) => {
      const { data } = await apiClient.post<ExchangeRate>(
        ENDPOINTS.MASTERS.EXCHANGE_RATES,
        payload,
      )
      return data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['masters', 'exchange-rates'] })
    },
  })
}

export function useUpdateExchangeRate(): UseMutationResult<
  ExchangeRate,
  Error,
  { id: number } & Partial<ExchangeRatePayload>
> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, ...payload }) => {
      const { data } = await apiClient.patch<ExchangeRate>(
        ENDPOINTS.MASTERS.EXCHANGE_RATE(id),
        payload,
      )
      return data
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['masters', 'exchange-rates'] })
    },
  })
}

export function useDeleteExchangeRate(): UseMutationResult<void, Error, number> {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (id) => {
      await apiClient.delete(ENDPOINTS.MASTERS.EXCHANGE_RATE(id))
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['masters', 'exchange-rates'] })
    },
  })
}
