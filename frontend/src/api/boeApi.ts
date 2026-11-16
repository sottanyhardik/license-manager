/**
 * API service for Bill of Entry operations.
 *
 * Centralizes all API calls related to Bill of Entries.
 */

import api from './axios';
import type {ApiId, ApiParams, ApiRecord} from '@/types/api/common';

/**
 * Fetch BOE list with filters
 */
export const fetchBOEList = async <T = ApiRecord>(params: ApiParams = {}): Promise<T> => {
    const response = await api.get('bill-of-entries/', {params});
    return response.data;
};

/**
 * Fetch single BOE details
 */
export const fetchBOE = async <T = ApiRecord>(id: ApiId): Promise<T> => {
    const response = await api.get(`bill-of-entries/${id}/`);
    return response.data;
};

/**
 * Create new Bill of Entry
 */
export const createBOE = async <T = ApiRecord>(data: ApiRecord): Promise<T> => {
    const response = await api.post('bill-of-entries/', data);
    return response.data;
};

/**
 * Update Bill of Entry
 */
export const updateBOE = async <T = ApiRecord>(id: ApiId, data: ApiRecord): Promise<T> => {
    const response = await api.patch(`bill-of-entries/${id}/`, data);
    return response.data;
};

/**
 * Delete Bill of Entry
 */
export const deleteBOE = async <T = ApiRecord>(id: ApiId): Promise<T> => {
    const response = await api.delete(`bill-of-entries/${id}/`);
    return response.data;
};

/**
 * Export BOE list to PDF with filters
 */
export const exportBOEListPDF = async (params: ApiParams = {}): Promise<Blob> => {
    const response = await api.get('bill-of-entries/export/', {
        params: {...params, _export: 'pdf'},
        responseType: 'blob'
    });
    return response.data;
};

/**
 * Export BOE list to Excel with filters
 */
export const exportBOEListExcel = async (params: ApiParams = {}): Promise<Blob> => {
    const response = await api.get('bill-of-entries/export/', {
        params: {...params, _export: 'xlsx'},
        responseType: 'blob'
    });
    return response.data;
};

/**
 * Export BOE list to Port Excel (simplified: BOE Number, BOE Date, Port, Quantity, Total CIF INR, Item Name)
 */
export const exportBOEPortExcel = async (params: ApiParams = {}): Promise<Blob> => {
    const response = await api.get('bill-of-entries/export/', {
        params: {...params, _export: 'port_xlsx'},
        responseType: 'blob'
    });
    return response.data;
};

/**
 * Merge source BOE into target BOE
 */
export const mergeBOE = async <T = ApiRecord>(targetId: ApiId, sourceId: ApiId): Promise<T> => {
    const response = await api.post(`bill-of-entries/${targetId}/merge/`, { source_boe_id: sourceId });
    return response.data;
};

export default {
    fetchBOEList,
    fetchBOE,
    createBOE,
    updateBOE,
    deleteBOE,
    exportBOEListPDF,
    exportBOEListExcel,
    exportBOEPortExcel,
    mergeBOE,
};
