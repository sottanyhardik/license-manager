/**
 * API service for license operations.
 *
 * Centralizes all API calls related to licenses.
 */

import api from './axios';
import type {ApiId, ApiParams, ApiRecord} from '@/types/api/common';

/**
 * Fetch license list with filters
 */
export const fetchLicenseList = async <T = ApiRecord>(params: ApiParams = {}): Promise<T> => {
    const response = await api.get('licenses/', {params});
    return response.data;
};

/**
 * Fetch single license details
 */
export const fetchLicense = async <T = ApiRecord>(id: ApiId): Promise<T> => {
    const response = await api.get(`licenses/${id}/`);
    return response.data;
};

/**
 * Create new license
 */
export const createLicense = async <T = ApiRecord>(data: ApiRecord): Promise<T> => {
    const response = await api.post('licenses/', data);
    return response.data;
};

/**
 * Update license
 */
export const updateLicense = async <T = ApiRecord>(id: ApiId, data: ApiRecord): Promise<T> => {
    const response = await api.put(`licenses/${id}/`, data);
    return response.data;
};

/**
 * Delete license
 */
export const deleteLicense = async <T = ApiRecord>(id: ApiId): Promise<T> => {
    const response = await api.delete(`licenses/${id}/`);
    return response.data;
};

/**
 * Fetch license import items
 */
export const fetchLicenseImportItems = async <T = ApiRecord>(licenseId: ApiId): Promise<T> => {
    const response = await api.get(`licenses/${licenseId}/import-items/`);
    return response.data;
};

/**
 * Fetch license export items
 */
export const fetchLicenseExportItems = async <T = ApiRecord>(licenseId: ApiId): Promise<T> => {
    const response = await api.get(`licenses/${licenseId}/export-items/`);
    return response.data;
};

/**
 * Fetch license balance summary
 */
export const fetchLicenseBalance = async <T = ApiRecord>(licenseId: ApiId): Promise<T> => {
    const response = await api.get(`licenses/${licenseId}/balance/`);
    return response.data;
};

/**
 * Export license ledger to PDF
 */
export const exportLicenseLedgerPDF = async (licenseId: ApiId): Promise<Blob> => {
    const response = await api.get(`licenses/${licenseId}/ledger-pdf/`, {
        responseType: 'blob'
    });
    return response.data;
};

/**
 * Export license item report
 */
export const exportLicenseItemReport = async (licenseId: ApiId, params: ApiParams = {}): Promise<Blob> => {
    const response = await api.get(`licenses/${licenseId}/item-report/`, {
        params,
        responseType: 'blob'
    });
    return response.data;
};

/**
 * Fetch license documents
 */
export const fetchLicenseDocuments = async <T = ApiRecord>(licenseId: ApiId): Promise<T> => {
    const response = await api.get(`licenses/${licenseId}/documents/`);
    return response.data;
};

/**
 * Upload license document
 */
export const uploadLicenseDocument = async <T = ApiRecord>(licenseId: ApiId, formData: FormData): Promise<T> => {
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
export const fetchLicenseTransactions = async <T = ApiRecord>(licenseId: ApiId, params: ApiParams = {}): Promise<T> => {
    const response = await api.get(`licenses/${licenseId}/transactions/`, {params});
    return response.data;
};

/**
 * Fetch license allocations
 */
export const fetchLicenseAllocations = async <T = ApiRecord>(licenseId: ApiId, params: ApiParams = {}): Promise<T> => {
    const response = await api.get(`licenses/${licenseId}/allocations/`, {params});
    return response.data;
};

/**
 * Check license validity
 */
export const checkLicenseValidity = async <T = ApiRecord>(licenseId: ApiId): Promise<T> => {
    const response = await api.get(`licenses/${licenseId}/check-validity/`);
    return response.data;
};

/**
 * Update license flags (is_active, is_expired, etc.)
 */
export const updateLicenseFlags = async <T = ApiRecord>(licenseId: ApiId): Promise<T> => {
    const response = await api.post(`licenses/${licenseId}/update-flags/`);
    return response.data;
};

/**
 * Fetch license options/metadata
 */
export const fetchLicenseOptions = async <T = ApiRecord>(): Promise<T> => {
    const response = await api.options('/licenses/');
    return response.data;
};

// ---------------------------------------------------------------------------
// Utilization planning (per-import-item plan that caps allotment)
// ---------------------------------------------------------------------------

/**
 * Fetch all plan lines for a license.
 */
export const fetchItemPlans = async <T = ApiRecord>(licenseId: ApiId): Promise<T> => {
    const response = await api.get('license-item-plans/', {params: {license: licenseId}});
    return response.data;
};

/**
 * Create/update many plan lines for a license in one call.
 * lines = [{import_item, planned_quantity, planned_cif_fc, planned_cif_inr?, note?}]
 */
export const bulkUpsertItemPlans = async <T = ApiRecord>(licenseId: ApiId, lines: ApiRecord[]): Promise<T> => {
    const response = await api.post('license-item-plans/bulk-upsert/', {
        license: licenseId,
        lines,
    });
    return response.data;
};

/**
 * Create a single plan line.
 */
export const createItemPlan = async <T = ApiRecord>(data: ApiRecord): Promise<T> => {
    const response = await api.post('license-item-plans/', data);
    return response.data;
};

/**
 * Update a single plan line (used by the "modify plan" modal at allot time).
 */
export const updateItemPlan = async <T = ApiRecord>(planId: ApiId, data: ApiRecord): Promise<T> => {
    const response = await api.patch(`license-item-plans/${planId}/`, data);
    return response.data;
};

/**
 * Delete a single plan line.
 */
export const deleteItemPlan = async <T = ApiRecord>(planId: ApiId): Promise<T> => {
    const response = await api.delete(`license-item-plans/${planId}/`);
    return response.data;
};

/* ------------------------------------------------------------------ */
/* Grouped BOE / Allotment transactions                                */
/* `GET licenses/:id/overview-transactions/` (doc 06 §7.4)             */
/* ------------------------------------------------------------------ */

export type LicenceTransactionRecordType = 'BOE' | 'ALLOTMENT';

export interface LicenceTransactionQtyByUnit {
    /** Exact unit string of the licence import item; never converted. */
    unit: string | null;
    qty: number;
    line_count: number;
}

export interface LicenceTransactionBoeBucket {
    /** `D` (debit) or `C` (credit). Buckets are never combined. */
    transaction_type: string;
    record_count: number;
    line_count: number;
    cif_fc: number;
    qty_by_unit: LicenceTransactionQtyByUnit[];
}

export interface LicenceTransactionAllotmentBucket {
    allotment_type: string;
    allocation_basis: string;
    is_linked_to_boe: boolean;
    record_count: number;
    line_count: number;
    cif_fc: number;
    qty_by_unit: LicenceTransactionQtyByUnit[];
}

export interface LicenceTransactionSummary {
    record_count_by_type: Record<LicenceTransactionRecordType, number>;
    line_count_by_type: Record<LicenceTransactionRecordType, number>;
    boe_buckets: LicenceTransactionBoeBucket[];
    allotment_buckets: LicenceTransactionAllotmentBucket[];
    /** Raw non-hidden DEBIT cif_fc (customs basis, not allocation/SALE-netted). Not a balance figure. */
    boe_debit_cif: number;
    /** Raw cif_fc of allotment lines with no BOE link; NOT netted by BOE allocations. */
    unlinked_allotment_cif: number;
    /** Shown separately; part of neither total above. */
    linked_allotment_cif: number;
}

export interface LicenceTransactionProduct {
    /** Licence import item (SR) id. */
    product_key: number;
    serial_number: number | null;
    description: string | null;
    unit: string | null;
    product_names: { id: number; name: string }[];
    /** Canonical names joined, or "Unmapped product". */
    product_label: string;
    is_unmapped: boolean;
}

export interface LicenceTransactionSupplier {
    /** `null` = "No supplier recorded" group (send `supplier_id=null`). */
    supplier_id: number | null;
    supplier_name: string | null;
    supplier_iec: string | null;
    supplier_label: string | null;
    supplier_source: 'company';
    is_missing_supplier: boolean;
}

export interface LicenceTransactionSupplierGroup extends LicenceTransactionSupplier {
    summary: LicenceTransactionSummary;
    products: (LicenceTransactionProduct & { summary: LicenceTransactionSummary })[];
}

/** Server-provided description of how each headline CIF figure is computed. */
export interface LicenceTransactionCifBasis {
    boe_debit_cif: string;
    unlinked_allotment_cif: string;
    linked_allotment_cif: string;
    exclusions: string[];
    scope: string;
}

interface LicenceTransactionPage<T> {
    license_id: number;
    cif_basis: LicenceTransactionCifBasis;
    license_number: string;
    count: number;
    page_size: number;
    total_pages: number;
    current_page: number;
    results: T[];
}

export interface LicenceTransactionGroupsResponse extends LicenceTransactionPage<LicenceTransactionSupplierGroup> {
    totals: LicenceTransactionSummary;
}

export interface LicenceTransactionRecord {
    record_type: LicenceTransactionRecordType;
    line_id: number;
    record_id: number;
    record_number: string;
    date: string | null;
    supplier_id: number | null;
    supplier_name: string | null;
    supplier_label: string | null;
    supplier_source: 'company';
    product_key: number;
    product_label: string;
    unit: string | null;
    qty: number;
    cif_fc: number;
    status: string;
    port: string | null;
    invoice_no: string | null;
    invoice_date: string | null;
    /** BOE lines only. */
    transaction_type: string | null;
    /** Allotment lines only. */
    allotment_type: string | null;
    allocation_basis: string | null;
    is_linked_to_boe: boolean | null;
    linked_boe_numbers: string[] | null;
    allotment_item_name: string | null;
    source_row_count: number;
}

export interface LicenceTransactionRecordsResponse extends LicenceTransactionPage<LicenceTransactionRecord> {
    supplier_id: number | null;
    product: LicenceTransactionProduct;
}

export interface LicenceTransactionParams {
    page?: number;
    page_size?: number;
    search?: string;
    record_type?: LicenceTransactionRecordType;
    status?: string;
    date_from?: string;
    date_to?: string;
    ordering?: string;
}

export interface LicenceTransactionRecordParams extends LicenceTransactionParams {
    supplier_id: number | null;
    product_key: number;
}

const dropEmpty = (params: object): ApiParams =>
    Object.fromEntries(
        Object.entries(params).filter(([, v]) => v !== undefined && v !== ''),
    ) as ApiParams;

/** Supplier groups (paged) with product summaries and licence totals. */
export const fetchLicenceTransactionGroups = async (
    licenseId: ApiId,
    params: LicenceTransactionParams = {},
): Promise<LicenceTransactionGroupsResponse> => {
    const response = await api.get(`licenses/${licenseId}/overview-transactions/`, {params: dropEmpty(params)});
    return response.data;
};

/** Record lines of one supplier × product group (paged). */
export const fetchLicenceTransactionRecords = async (
    licenseId: ApiId,
    {supplier_id, ...params}: LicenceTransactionRecordParams,
): Promise<LicenceTransactionRecordsResponse> => {
    const response = await api.get(`licenses/${licenseId}/overview-transactions/`, {
        params: dropEmpty({...params, supplier_id: supplier_id === null ? 'null' : supplier_id}),
    });
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
    fetchLicenceTransactionGroups,
    fetchLicenceTransactionRecords,
};
