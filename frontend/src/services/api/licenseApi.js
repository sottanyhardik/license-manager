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
    const response = await api.get('licenses/', {params});
    return response.data;
};

/**
 * Fetch single license details
 */
export const fetchLicense = async (id) => {
    const response = await api.get(`licenses/${id}/`);
    return response.data;
};

/**
 * Create new license
 */
export const createLicense = async (data) => {
    const response = await api.post('licenses/', data);
    return response.data;
};

/**
 * Update license
 */
export const updateLicense = async (id, data) => {
    const response = await api.put(`licenses/${id}/`, data);
    return response.data;
};

/**
 * Delete license
 */
export const deleteLicense = async (id) => {
    const response = await api.delete(`licenses/${id}/`);
    return response.data;
};

/**
 * Fetch license import items
 */
export const fetchLicenseImportItems = async (licenseId) => {
    const response = await api.get(`licenses/${licenseId}/import-items/`);
    return response.data;
};

/**
 * Fetch license export items
 */
export const fetchLicenseExportItems = async (licenseId) => {
    const response = await api.get(`licenses/${licenseId}/export-items/`);
    return response.data;
};

/**
 * Fetch license balance summary
 */
export const fetchLicenseBalance = async (licenseId) => {
    const response = await api.get(`licenses/${licenseId}/balance/`);
    return response.data;
};

/**
 * Export license ledger to PDF
 */
export const exportLicenseLedgerPDF = async (licenseId) => {
    const response = await api.get(`licenses/${licenseId}/ledger-pdf/`, {
        responseType: 'blob'
    });
    return response.data;
};

/**
 * Export license item report
 */
export const exportLicenseItemReport = async (licenseId, params = {}) => {
    const response = await api.get(`licenses/${licenseId}/item-report/`, {
        params,
        responseType: 'blob'
    });
    return response.data;
};

/**
 * Fetch license documents
 */
export const fetchLicenseDocuments = async (licenseId) => {
    const response = await api.get(`licenses/${licenseId}/documents/`);
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
    const response = await api.get(`licenses/${licenseId}/transactions/`, {params});
    return response.data;
};

/**
 * Fetch license allocations
 */
export const fetchLicenseAllocations = async (licenseId, params = {}) => {
    const response = await api.get(`licenses/${licenseId}/allocations/`, {params});
    return response.data;
};

/**
 * Check license validity
 */
export const checkLicenseValidity = async (licenseId) => {
    const response = await api.get(`licenses/${licenseId}/check-validity/`);
    return response.data;
};

/**
 * Update license flags (is_active, is_expired, etc.)
 */
export const updateLicenseFlags = async (licenseId) => {
    const response = await api.post(`licenses/${licenseId}/update-flags/`);
    return response.data;
};

/**
 * Fetch license options/metadata
 */
export const fetchLicenseOptions = async () => {
    const response = await api.options('/licenses/');
    return response.data;
};

// ---------------------------------------------------------------------------
// Utilization planning (per-import-item plan that caps allotment)
// ---------------------------------------------------------------------------

/**
 * Fetch all plan lines for a license.
 */
export const fetchItemPlans = async (licenseId) => {
    const response = await api.get('license-item-plans/', {params: {license: licenseId}});
    return response.data;
};

/**
 * Create/update many plan lines for a license in one call.
 * lines = [{import_item, planned_quantity, planned_cif_fc, planned_cif_inr?, note?}]
 */
export const bulkUpsertItemPlans = async (licenseId, lines) => {
    const response = await api.post('license-item-plans/bulk-upsert/', {
        license: licenseId,
        lines,
    });
    return response.data;
};

/**
 * Create a single plan line.
 */
export const createItemPlan = async (data) => {
    const response = await api.post('license-item-plans/', data);
    return response.data;
};

/**
 * Update a single plan line (used by the "modify plan" modal at allot time).
 */
export const updateItemPlan = async (planId, data) => {
    const response = await api.patch(`license-item-plans/${planId}/`, data);
    return response.data;
};

/**
 * Delete a single plan line.
 */
export const deleteItemPlan = async (planId) => {
    const response = await api.delete(`license-item-plans/${planId}/`);
    return response.data;
};

/**
 * Compute the norm-based (E1/E5/E132) plan to pre-fill the manual plan.
 * Returns { norm, plan: { <item_id>: {planned_quantity, unit_price, planned_cif} } }.
 */
export const fetchNormPrefill = async (licenseId) => {
    const response = await api.get('license-item-plans/norm-prefill/', {params: {license: licenseId}});
    return response.data;
};

/**
 * Compute AND save an E1 auto-plan for a license (Rule 1 + Rule 2 waterfall).
 * Only valid for E1 licenses — returns an error for other norms.
 * Full-replace semantics: any existing manual plan is overwritten.
 * Returns { norm, planned, remaining_cif, lines }.
 * @deprecated Use autoPlan() — the unified endpoint handles both E1 and E5.
 */
export const e1AutoPlan = async (licenseId) => {
    const response = await api.post('license-item-plans/e1-auto-plan/', {license: licenseId});
    return response.data;
};

/**
 * Unified Auto Plan — detects the licence norm (E1 or E5) on the server and
 * runs the appropriate waterfall, then saves the result in one transaction.
 * Full-replace semantics: any existing manual plan is overwritten.
 * Returns { norm, planned, remaining_cif, lines }.
 */
export const autoPlan = async (licenseId) => {
    const response = await api.post('license-item-plans/auto-plan/', {license: licenseId});
    return response.data;
};

/**
 * Batch Auto Plan — runs Auto Plan for every eligible DFIA license (E1/E5/E132).
 * Skips licenses that are already ≥99% planned.  Failures are isolated per-license.
 * Returns { total, planned, already_planned, skipped_unknown_norm, failed, errors }.
 */
export const autoPlanAll = async () => {
    const response = await api.post('license-item-plans/auto-plan-all/', {});
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
    fetchItemPlans,
    bulkUpsertItemPlans,
    createItemPlan,
    updateItemPlan,
    deleteItemPlan,
    fetchNormPrefill,
};
