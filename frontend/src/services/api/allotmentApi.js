/**
 * API service for allotment operations.
 *
 * Centralizes all API calls related to allotments.
 */

import api from '../../api/axios';

/**
 * Fetch allotment details
 */
export const fetchAllotment = async (id) => {
    const response = await api.get(`/allotment-actions/${id}/available-licenses/`);
    return response.data;
};

/**
 * Fetch available licenses for allocation
 */
export const fetchAvailableLicenses = async (allotmentId, params = {}) => {
    const response = await api.get(`/allotment-actions/${allotmentId}/available-licenses/`, {
        params
    });
    return response.data;
};

/**
 * Allocate a license item to an allotment
 */
export const allocateItem = async (allotmentId, itemId, data) => {
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
export const updateAllocation = async (allotmentId, allocationId, data) => {
    const response = await api.patch(
        `/allotment-actions/${allotmentId}/update-allocation/${allocationId}/`,
        data
    );
    return response.data;
};

/**
 * Delete an allocation
 */
export const deleteAllocation = async (allotmentId, allocationId) => {
    const response = await api.delete(
        `/allotment-actions/${allotmentId}/delete-allocation/${allocationId}/`
    );
    return response.data;
};

/**
 * Fetch notification options
 */
export const fetchNotificationOptions = async () => {
    const response = await api.options('/licenses/');
    const choices = response.data?.actions?.POST?.notification_number?.choices || [];
    return choices;
};

/**
 * Export allotment to PDF
 */
export const exportAllotmentPDF = async (allotmentId) => {
    const response = await api.get(`/allotment-actions/${allotmentId}/export-pdf/`, {
        responseType: 'blob'
    });
    return response.data;
};

/**
 * Export allotment to Excel
 */
export const exportAllotmentExcel = async (allotmentId) => {
    const response = await api.get(`/allotment-actions/${allotmentId}/export-excel/`, {
        responseType: 'blob'
    });
    return response.data;
};

/**
 * Fetch allotment list with filters
 */
export const fetchAllotmentList = async (params = {}) => {
    const response = await api.get('/allotments/', {params});
    return response.data;
};

/**
 * Create new allotment
 */
export const createAllotment = async (data) => {
    const response = await api.post('/allotments/', data);
    return response.data;
};

/**
 * Update allotment
 */
export const updateAllotment = async (id, data) => {
    const response = await api.patch(`/allotments/${id}/`, data);
    return response.data;
};

/**
 * Delete allotment
 */
export const deleteAllotment = async (id) => {
    const response = await api.delete(`/allotments/${id}/`);
    return response.data;
};

/**
 * Convert allotment to Bill of Entry
 */
export const convertToBOE = async (allotmentId, boeData) => {
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
