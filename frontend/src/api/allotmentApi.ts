/**
 * API service for allotment operations.
 *
 * Centralizes all API calls related to allotments.
 */

import api from './axios';
import type {ApiId, ApiParams, ApiRecord} from '@/types/api/common';

/** Normalised notification-number option. */
export interface NotificationOption {
    value: string;
    label: string;
    display_name: string;
}

/**
 * Fetch allotment details
 */
export const fetchAllotment = async <T = ApiRecord>(id: ApiId): Promise<T> => {
    const response = await api.get(`allotment-actions/${id}/available-licenses/`);
    return response.data;
};

/**
 * Fetch available licenses for allocation
 */
export const fetchAvailableLicenses = async <T = ApiRecord>(allotmentId: ApiId, params: ApiParams = {}): Promise<T> => {
    const response = await api.get(`allotment-actions/${allotmentId}/available-licenses/`, {
        params
    });
    return response.data;
};

/**
 * Allocate a license item to an allotment
 */
export const allocateItem = async <T = ApiRecord>(allotmentId: ApiId, itemId: ApiId, data: ApiRecord): Promise<T> => {
    const response = await api.post(
        `/allotment-actions/${allotmentId}/allocate-item/`,
        {
            item_id: itemId,
            ...data
        }
    );
    return response.data;
};

/**
 * Update an existing allocation
 */
export const updateAllocation = async <T = ApiRecord>(allotmentId: ApiId, allocationId: ApiId, data: ApiRecord): Promise<T> => {
    const response = await api.patch(
        `/allotment-actions/${allotmentId}/update-allocation/${allocationId}/`,
        data
    );
    return response.data;
};

/**
 * Delete an allocation
 */
export const deleteAllocation = async <T = ApiRecord>(allotmentId: ApiId, allocationId: ApiId): Promise<T> => {
    const response = await api.delete(
        `/allotment-actions/${allotmentId}/delete-allocation/${allocationId}/`
    );
    return response.data;
};

/**
 * Fetch notification options
 *
 * notification_number was migrated from a CharField-with-choices to a FK on
 * core.NotificationNumber, so DRF's OPTIONS metadata no longer enumerates
 * the values. Read them from the masters endpoint instead and normalize the
 * shape to {value, display_name, label} for legacy callers.
 */
export const fetchNotificationOptions = async (): Promise<NotificationOption[]> => {
    const response = await api.get('masters/notification-numbers/', {
        params: { page_size: 200, ordering: 'code' },
    });
    const results = response.data?.results ?? response.data ?? [];
    return results.map(({ code, label }: { code: string; label?: string }) => ({
        value: code,
        label: label ? `${code} — ${label}` : code,
        display_name: label ? `${code} — ${label}` : code,
    }));
};

/**
 * Export allotment to PDF
 */
export const exportAllotmentPDF = async (allotmentId: ApiId): Promise<Blob> => {
    const response = await api.get(`allotment-actions/${allotmentId}/export-pdf/`, {
        responseType: 'blob'
    });
    return response.data;
};

/**
 * Export allotment to Excel
 */
export const exportAllotmentExcel = async (allotmentId: ApiId): Promise<Blob> => {
    const response = await api.get(`allotment-actions/${allotmentId}/export-excel/`, {
        responseType: 'blob'
    });
    return response.data;
};

/**
 * Fetch allotment list with filters
 */
export const fetchAllotmentList = async <T = ApiRecord>(params: ApiParams = {}): Promise<T> => {
    const response = await api.get('allotments/', {params});
    return response.data;
};

/**
 * Create new allotment
 */
export const createAllotment = async <T = ApiRecord>(data: ApiRecord): Promise<T> => {
    const response = await api.post('allotments/', data);
    return response.data;
};

/**
 * Update allotment
 */
export const updateAllotment = async <T = ApiRecord>(id: ApiId, data: ApiRecord): Promise<T> => {
    const response = await api.patch(`allotments/${id}/`, data);
    return response.data;
};

/**
 * Delete allotment
 */
export const deleteAllotment = async <T = ApiRecord>(id: ApiId): Promise<T> => {
    const response = await api.delete(`allotments/${id}/`);
    return response.data;
};

/**
 * Convert allotment to Bill of Entry
 */
export const convertToBOE = async <T = ApiRecord>(allotmentId: ApiId, boeData: ApiRecord): Promise<T> => {
    const response = await api.post(
        `/allotment-actions/${allotmentId}/convert-to-boe/`,
        boeData
    );
    return response.data;
};

export default {
    fetchAllotment,
    fetchAvailableLicenses,
    allocateItem,
    updateAllocation,
    deleteAllocation,
    fetchNotificationOptions,
    exportAllotmentPDF,
    exportAllotmentExcel,
    fetchAllotmentList,
    createAllotment,
    updateAllotment,
    deleteAllotment,
    convertToBOE,
};
