// HTTP functions for the allotments feature.
// All calls go through the shared apiClient (JWT interceptors, dedup, etc.).

import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import type {
  Allotment,
  AllotmentFormValues,
  AllotmentListParams,
  GeneratePdfResponse,
  PaginatedAllotments,
} from './types'

export async function fetchAllotments(
  params?: AllotmentListParams,
): Promise<PaginatedAllotments> {
  const { data } = await apiClient.get<PaginatedAllotments>(ENDPOINTS.ALLOTMENTS.LIST, { params })
  return data
}

export async function fetchAllotment(id: number): Promise<Allotment> {
  const { data } = await apiClient.get<Allotment>(ENDPOINTS.ALLOTMENTS.DETAIL(id))
  return data
}

export async function createAllotment(payload: AllotmentFormValues): Promise<Allotment> {
  const { data } = await apiClient.post<Allotment>(ENDPOINTS.ALLOTMENTS.LIST, payload)
  return data
}

export async function updateAllotment(
  id: number,
  payload: Partial<AllotmentFormValues>,
): Promise<Allotment> {
  const { data } = await apiClient.patch<Allotment>(ENDPOINTS.ALLOTMENTS.DETAIL(id), payload)
  return data
}

export async function deleteAllotment(id: number): Promise<void> {
  await apiClient.delete(ENDPOINTS.ALLOTMENTS.DETAIL(id))
}

export async function generateAllotmentPdf(id: number): Promise<GeneratePdfResponse> {
  const { data } = await apiClient.post<GeneratePdfResponse>(
    ENDPOINTS.ALLOTMENTS.GENERATE_PDF(id),
  )
  return data
}
