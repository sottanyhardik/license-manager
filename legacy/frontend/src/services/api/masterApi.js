/**
 * API service for master data operations.
 *
 * Centralizes all API calls related to master CRUD operations.
 */

import api from '../../api/axios';

/**
 * Fetch master list with pagination and filters
 */
export const fetchMasterList = async (endpoint, params = {}) => {
    const response = await api.get(endpoint, {params});
    return response.data;
};

/**
 * Fetch master metadata (field definitions, choices, etc.)
 */
export const fetchMasterMetadata = async (endpoint) => {
    const response = await api.options(endpoint);
    return response.data;
};

/**
 * Fetch single master record by ID
 */
export const fetchMasterRecord = async (endpoint, id) => {
    const response = await api.get(`${endpoint}${id}/`);
    return response.data;
};

/**
 * Create new master record
 */
export const createMasterRecord = async (endpoint, data) => {
    const response = await api.post(endpoint, data);
    return response.data;
};

/**
 * Update master record
 */
export const updateMasterRecord = async (endpoint, id, data) => {
    const response = await api.put(`${endpoint}${id}/`, data);
    return response.data;
};

/**
 * Partially update master record
 */
export const patchMasterRecord = async (endpoint, id, data) => {
    const response = await api.patch(`${endpoint}${id}/`, data);
    return response.data;
};

/**
 * Delete master record
 */
export const deleteMasterRecord = async (endpoint, id) => {
    const response = await api.delete(`${endpoint}${id}/`);
    return response.data;
};

/**
 * Export master data to PDF
 */
export const exportMasterPDF = async (endpoint, params = {}) => {
    const response = await api.get(`${endpoint}export/pdf/`, {
        params,
        responseType: 'blob'
    });
    return response.data;
};

/**
 * Export master data to Excel
 */
export const exportMasterExcel = async (endpoint, params = {}) => {
    const response = await api.get(`${endpoint}export/excel/`, {
        params,
        responseType: 'blob'
    });
    return response.data;
};

/**
 * Bulk delete master records
 */
export const bulkDeleteMasterRecords = async (endpoint, ids) => {
    const response = await api.post(`${endpoint}bulk_delete/`, {ids});
    return response.data;
};

/**
 * Fetch foreign key options for a field
 */
export const fetchForeignKeyOptions = async (endpoint, search = '', params = {}) => {
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
export const downloadFileAttachment = async (url) => {
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
