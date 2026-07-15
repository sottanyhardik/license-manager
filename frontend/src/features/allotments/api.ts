// HTTP functions for the allotments feature.
// All calls go through the shared apiClient (JWT interceptors, dedup, etc.).

import apiClient from '@/shared/api/client'
import { ENDPOINTS } from '@/shared/api/endpoints'
import type {
  Allotment,
  AllotmentFormValues,
  AllotmentListParams,
  AllocateItemsResponse,
  AllocationEntry,
  AvailableLicense,
  AvailableLicensesParams,
  AvailableLicensesResponse,
  GeneratePdfResponse,
  PaginatedAllotments,
  TransferLetterPayload,
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

export async function fetchAvailableLicenses(
  allotmentId: number,
  params: AvailableLicensesParams,
): Promise<AvailableLicensesResponse> {
  const { data } = await apiClient.get<AvailableLicensesResponse>(
    ENDPOINTS.ALLOTMENTS.AVAILABLE_LICENSES(allotmentId),
    { params },
  )
  return data as AvailableLicensesResponse
}

export async function allocateItems(
  allotmentId: number,
  items: AllocationEntry[],
): Promise<AllocateItemsResponse> {
  const { data } = await apiClient.post<AllocateItemsResponse>(
    ENDPOINTS.ALLOTMENTS.ALLOCATE_ITEMS(allotmentId),
    { allocations: items },
  )
  return data as AllocateItemsResponse
}

export async function deleteAllotmentItem(
  allotmentId: number,
  itemId: number,
): Promise<{ message?: string }> {
  const { data } = await apiClient.delete<{ message?: string }>(
    ENDPOINTS.ALLOTMENTS.DELETE_ITEM(allotmentId, itemId),
  )
  return data as { message?: string }
}

export async function generateAllotmentTransferLetter(
  allotmentId: number,
  payload: TransferLetterPayload,
): Promise<Blob> {
  const response = await apiClient.post(
    ENDPOINTS.ALLOTMENTS.GENERATE_TRANSFER_LETTER(allotmentId),
    payload,
    { responseType: 'blob' },
  )
  return response.data as Blob
}

export async function copyAllotment(allotmentId: number): Promise<Allotment> {
  const { data } = await apiClient.post<Allotment>(
    ENDPOINTS.ALLOTMENTS.COPY(allotmentId),
  )
  return data as Allotment
}

// Re-export AvailableLicense so callers can import from api.ts
export type { AvailableLicense }
