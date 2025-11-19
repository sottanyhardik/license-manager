/**
 * API service for license operations.
 *
 * Centralizes all API calls related to licenses.
 */

import api from '../../api/axios';

/**
 * Fetch license list with filters
 */
export const fetchLicenseList = async (params = {}) => {
    const response = await api.get('/licenses/', {params});
    return response.data;
};

/**
 * Fetch single license details
 */
export const fetchLicense = async (id) => {
    const response = await api.get(`/licenses/${id}/`);
    return response.data;
};

/**
 * Create new license
 */
export const createLicense = async (data) => {
    const response = await api.post('/licenses/', data);
    return response.data;
};

/**
 * Update license
 */
export const updateLicense = async (id, data) => {
    const response = await api.put(`/licenses/${id}/`, data);
    return response.data;
};

/**
 * Delete license
 */
export const deleteLicense = async (id) => {
    const response = await api.delete(`/licenses/${id}/`);
    return response.data;
};

/**
 * Fetch license import items
 */
export const fetchLicenseImportItems = async (licenseId) => {
    const response = await api.get(`/licenses/${licenseId}/import-items/`);
    return response.data;
};

/**
 * Fetch license export items
 */
export const fetchLicenseExportItems = async (licenseId) => {
    const response = await api.get(`/licenses/${licenseId}/export-items/`);
    return response.data;
};

/**
 * Fetch license balance summary
 */
export const fetchLicenseBalance = async (licenseId) => {
    const response = await api.get(`/licenses/${licenseId}/balance/`);
    return response.data;
};

/**
 * Export license ledger to PDF
 */
export const exportLicenseLedgerPDF = async (licenseId) => {
    const response = await api.get(`/licenses/${licenseId}/ledger-pdf/`, {
        responseType: 'blob'
    });
    return response.data;
};

/**
 * Export license item report
 */
export const exportLicenseItemReport = async (licenseId, params = {}) => {
    const response = await api.get(`/licenses/${licenseId}/item-report/`, {
        params,
        responseType: 'blob'
    });
    return response.data;
};

/**
 * Fetch license documents
 */
export const fetchLicenseDocuments = async (licenseId) => {
    const response = await api.get(`/licenses/${licenseId}/documents/`);
    return response.data;
};

/**
 * Upload license document
 */
export const uploadLicenseDocument = async (licenseId, formData) => {
    const response = await api.post(
        `/licenses/${licenseId}/documents/`,
        formData,
        {
            headers: {
                'Content-Type': 'multipart/form-data'
            }
        }
    );
    return response.data;
};

/**
 * Fetch license transactions (BOE entries)
 */
export const fetchLicenseTransactions = async (licenseId, params = {}) => {
    const response = await api.get(`/licenses/${licenseId}/transactions/`, {params});
    return response.data;
};

/**
 * Fetch license allocations
 */
export const fetchLicenseAllocations = async (licenseId, params = {}) => {
    const response = await api.get(`/licenses/${licenseId}/allocations/`, {params});
    return response.data;
};

/**
 * Check license validity
 */
export const checkLicenseValidity = async (licenseId) => {
    const response = await api.get(`/licenses/${licenseId}/check-validity/`);
    return response.data;
};

/**
 * Update license flags (is_active, is_expired, etc.)
 */
export const updateLicenseFlags = async (licenseId) => {
    const response = await api.post(`/licenses/${licenseId}/update-flags/`);
    return response.data;
};

/**
 * Fetch license options/metadata
 */
export const fetchLicenseOptions = async () => {
    const response = await api.options('/licenses/');
    return response.data;
};

export default {
    fetchLicenseList,
    fetchLicense,
    createLicense,
    updateLicense,
    deleteLicense,
    fetchLicenseImportItems,
    fetchLicenseExportItems,
    fetchLicenseBalance,
    exportLicenseLedgerPDF,
    exportLicenseItemReport,
    fetchLicenseDocuments,
    uploadLicenseDocument,
    fetchLicenseTransactions,
    fetchLicenseAllocations,
    checkLicenseValidity,
    updateLicenseFlags,
    fetchLicenseOptions,
};
