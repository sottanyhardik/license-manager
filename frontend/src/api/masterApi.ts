/**
 * API service for master data operations.
 *
 * Centralizes all API calls related to master CRUD operations.
 */

import api from './axios';
import type {ApiId, ApiParams, ApiRecord} from '@/types/api/common';

/**
 * Fetch master list with pagination and filters
 */
export const fetchMasterList = async <T = ApiRecord>(endpoint: string, params: ApiParams = {}): Promise<T> => {
    const response = await api.get(endpoint, {params});
    return response.data;
};

/**
 * Fetch master metadata (field definitions, choices, etc.)
 */
export const fetchMasterMetadata = async <T = ApiRecord>(endpoint: string): Promise<T> => {
    const response = await api.options(endpoint);
    return response.data;
};

/**
 * Fetch single master record by ID
 */
export const fetchMasterRecord = async <T = ApiRecord>(endpoint: string, id: ApiId): Promise<T> => {
    const response = await api.get(`${endpoint}${id}/`);
    return response.data;
};

/**
 * Create new master record
 */
export const createMasterRecord = async <T = ApiRecord>(endpoint: string, data: ApiRecord): Promise<T> => {
    const response = await api.post(endpoint, data);
    return response.data;
};

/**
 * Update master record
 */
export const updateMasterRecord = async <T = ApiRecord>(endpoint: string, id: ApiId, data: ApiRecord): Promise<T> => {
    const response = await api.put(`${endpoint}${id}/`, data);
    return response.data;
};

/**
 * Partially update master record
 */
export const patchMasterRecord = async <T = ApiRecord>(endpoint: string, id: ApiId, data: ApiRecord): Promise<T> => {
    const response = await api.patch(`${endpoint}${id}/`, data);
    return response.data;
};

/**
 * Delete master record
 */
export const deleteMasterRecord = async <T = ApiRecord>(endpoint: string, id: ApiId): Promise<T> => {
    const response = await api.delete(`${endpoint}${id}/`);
    return response.data;
};

/**
 * Export master data to PDF
 */
export const exportMasterPDF = async (endpoint: string, params: ApiParams = {}): Promise<Blob> => {
    const response = await api.get(`${endpoint}export/pdf/`, {
        params,
        responseType: 'blob'
    });
    return response.data;
};

/**
 * Export master data to Excel
 */
export const exportMasterExcel = async (endpoint: string, params: ApiParams = {}): Promise<Blob> => {
    const response = await api.get(`${endpoint}export/excel/`, {
        params,
        responseType: 'blob'
    });
    return response.data;
};

/**
 * Bulk delete master records
 */
export const bulkDeleteMasterRecords = async <T = ApiRecord>(endpoint: string, ids: ApiId[]): Promise<T> => {
    const response = await api.post(`${endpoint}bulk_delete/`, {ids});
    return response.data;
};

/**
 * Fetch foreign key options for a field
 */
export const fetchForeignKeyOptions = async <T = ApiRecord>(endpoint: string, search = '', params: ApiParams = {}): Promise<T> => {
    const response = await api.get(endpoint, {
        params: {
            search,
            ...params
        }
    });
    return response.data;
};

/**
 * Download file attachment
 */
export const downloadFileAttachment = async (url: string): Promise<Blob> => {
    const response = await api.get(url, {
        responseType: 'blob'
    });
    return response.data;
};

export default {
    fetchMasterList,
    fetchMasterMetadata,
    fetchMasterRecord,
    createMasterRecord,
    updateMasterRecord,
    patchMasterRecord,
    deleteMasterRecord,
    exportMasterPDF,
    exportMasterExcel,
    bulkDeleteMasterRecords,
    fetchForeignKeyOptions,
    downloadFileAttachment,
};
