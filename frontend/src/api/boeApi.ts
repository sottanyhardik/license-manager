/**
 * API service for Bill of Entry operations.
 *
 * Centralizes all API calls related to Bill of Entries. Request/response types
 * follow the DRF views in `backend/apps/bill_of_entry/api/views.py`; errors on
 * these endpoints are `{error}` (reconciliation uses `{detail}`), see
 * `extractBoeError`.
 */

import api from './axios';
import type {ApiId, ApiParams, ApiRecord} from '@/types/api/common';

/** Loose BOE row (BillOfEntrySerializer); values are rendered as received. */
export type BoeRecord = { id: number; [field: string]: unknown };

/** Writable BOE payload (create / PATCH); the serializer validates the fields. */
export type BoePayload = ApiRecord;

export interface BoeMergeResponse {
    success?: boolean;
    message?: string;
    /** The surviving BOE (BillOfEntrySerializer row). */
    boe?: BoeRecord;
    target_boe_id?: number;
    /** True when the server kept the source row instead of the requested target. */
    swapped?: boolean;
}

/**
 * Success text for a merge. The server may keep the source row instead of the
 * requested target (`swapped`); `target_boe_id` is then the surviving BOE.
 */
export function describeBoeMerge(resp: BoeMergeResponse | null | undefined, requestedTargetId: ApiId): string {
    const base = resp?.message || 'BOE merged successfully';
    const survivor = resp?.target_boe_id ?? resp?.boe?.id ?? requestedTargetId;
    if (resp?.swapped || String(survivor) !== String(requestedTargetId)) {
        return `${base} (kept BOE #${survivor} as the surviving record)`;
    }
    return base;
}

export interface BoeMessageResponse {
    success?: boolean;
    message?: string;
}

export interface BoeResolveDisputeResponse extends BoeMessageResponse {
    cleared?: number;
}

export interface BoeProductNameResponse extends BoeMessageResponse {
    product_name?: string;
}

export interface BoeBulkProductNamesResponse extends BoeMessageResponse {
    total?: number;
    updated?: number;
    skipped?: number;
}

export interface BoeInvoiceNoResponse {
    id: number;
    invoice_no: string;
    message?: string;
}

/** `licenses/:id/hide-boe/` and `restore-boe/` (licence-hosted; response shape is not relied on). */
export type BoeHideRestoreResponse = ApiRecord;

export interface BoeAllotmentDetails {
    exchange_rate?: string | number | null;
    product_name?: string | null;
    port?: number | string | null;
    company?: number | string | null;
    item_details?: ApiRecord[];
    [field: string]: unknown;
}

export interface BoeParsePdfLicenceRow {
    match_status?: string;
    matched_item_id?: number | null;
    [field: string]: unknown;
}

export interface BoeParsePdfResponse {
    parsed: Record<string, any>;
    prefill: Record<string, any>;
    matched_allotment_id: number | null;
    existing_boe_id: number | null;
    matched_company_id: number | null;
    company_created: boolean;
    matched_port_id: number | null;
    licences: BoeParsePdfLicenceRow[];
    /** Buyer on the PDF that matched no company; companies are never auto-created. */
    unmatched_company?: string | Record<string, unknown> | null;
    company_creation_skipped_reason?: string | null;
}

type ErrorBody = { error?: unknown; detail?: unknown; message?: unknown };

/** Server message from a failed BOE call: `{error}` first, then `{detail}`, then `{message}`. */
export function extractBoeError(err: unknown, fallback: string): string {
    const data = (err as { response?: { data?: ErrorBody } } | null | undefined)?.response?.data;
    for (const v of [data?.error, data?.detail, data?.message]) {
        if (typeof v === 'string' && v) return v;
    }
    return fallback;
}

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
export const createBOE = async <T = BoeRecord>(data: BoePayload): Promise<T> => {
    const response = await api.post('bill-of-entries/', data);
    return response.data;
};

/**
 * Update Bill of Entry
 */
export const updateBOE = async <T = BoeRecord>(id: ApiId, data: BoePayload): Promise<T> => {
    const response = await api.patch(`bill-of-entries/${id}/`, data);
    return response.data;
};

/**
 * Delete Bill of Entry
 */
export const deleteBOE = async <T = void>(id: ApiId): Promise<T> => {
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
export const mergeBOE = async <T = BoeMergeResponse>(targetId: ApiId, sourceId: ApiId): Promise<T> => {
    const response = await api.post(`bill-of-entries/${targetId}/merge/`, { source_boe_id: sourceId });
    return response.data;
};

/**
 * Inline invoice-number edit. Open to BOE_MANAGER, BOE_VIEWER (the single D2
 * write exception) and ACCOUNT_ACCESS; the server rejects hidden BOEs (D1).
 */
export const updateInvoiceNo = async (id: ApiId, invoiceNo: string): Promise<BoeInvoiceNoResponse> => {
    const response = await api.post(`bill-of-entries/${id}/update-invoice-no/`, { invoice_no: invoiceNo });
    return response.data;
};

/** Clear the dispute flag on every flagged row of one BOE. */
export const resolveDispute = async (id: ApiId): Promise<BoeResolveDisputeResponse> => {
    const response = await api.post(`bill-of-entries/${id}/resolve-dispute/`);
    return response.data;
};

/** Generate the product name of one BOE from its items (only when empty). */
export const updateProductName = async (id: ApiId): Promise<BoeProductNameResponse> => {
    const response = await api.post(`bill-of-entries/${id}/update-product-name/`);
    return response.data;
};

/** Generate product names for every BOE with an empty one (whole database). */
export const bulkUpdateProductNames = async (): Promise<BoeBulkProductNamesResponse> => {
    const response = await api.post(`bill-of-entries/bulk-update-product-names/`);
    return response.data;
};

/** Hide a BOE from one licence's balance (licence-hosted endpoint). Affects licence balances. */
export const hideBoe = async (licenceId: ApiId, boeId: ApiId): Promise<BoeHideRestoreResponse> => {
    const response = await api.post(`licenses/${licenceId}/hide-boe/`, { boe_id: boeId });
    return response.data;
};

/** Restore a previously hidden BOE (licence-hosted endpoint). Affects licence balances. */
export const restoreBoe = async (licenceId: ApiId, boeId: ApiId): Promise<BoeHideRestoreResponse> => {
    const response = await api.post(`licenses/${licenceId}/restore-boe/`, { boe_id: boeId });
    return response.data;
};

/** Item rows prefilled from one allotment (BOE form). */
export const fetchAllotmentDetails = async <T = BoeAllotmentDetails>(allotmentId: ApiId): Promise<T> => {
    const response = await api.get(`bill-of-entries/fetch-allotment-details/?allotment_id=${allotmentId}`);
    return response.data;
};

/** Parse an uploaded BOE PDF (multipart). */
export const parsePdf = async (file: Blob): Promise<BoeParsePdfResponse> => {
    const fd = new FormData();
    fd.append('file', file);
    const response = await api.post('bill-of-entries/parse-pdf/', fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
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
    exportBOEPortExcel,
    mergeBOE,
    updateInvoiceNo,
    resolveDispute,
    updateProductName,
    bulkUpdateProductNames,
    hideBoe,
    restoreBoe,
    fetchAllotmentDetails,
    parsePdf,
    extractBoeError,
};
