/**
 * API service for Bill of Entry operations.
 *
 * Centralizes all API calls related to Bill of Entries.
 */

import api from '../../api/axios';

/**
 * Fetch BOE list with filters
 */
export const fetchBOEList = async (params = {}) => {
    const response = await api.get('/bill-of-entries/', {params});
    return response.data;
};

/**
 * Fetch single BOE details
 */
export const fetchBOE = async (id) => {
    const response = await api.get(`/bill-of-entries/${id}/`);
    return response.data;
};

/**
 * Create new Bill of Entry
 */
export const createBOE = async (data) => {
    const response = await api.post('/bill-of-entries/', data);
    return response.data;
};

/**
 * Update Bill of Entry
 */
export const updateBOE = async (id, data) => {
    const response = await api.patch(`/bill-of-entries/${id}/`, data);
    return response.data;
};

/**
 * Delete Bill of Entry
 */
export const deleteBOE = async (id) => {
    const response = await api.delete(`/bill-of-entries/${id}/`);
    return response.data;
};

/**
 * Export BOE list to PDF with filters
 */
export const exportBOEListPDF = async (params = {}) => {
    const response = await api.get('/bill-of-entries/export/', {
        params: {...params, _export: 'pdf'},
        responseType: 'blob'
    });
    return response.data;
};

/**
 * Export BOE list to Excel with filters
 */
export const exportBOEListExcel = async (params = {}) => {
    const response = await api.get('/bill-of-entries/export/', {
        params: {...params, _export: 'xlsx'},
        responseType: 'blob'
    });
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
};
