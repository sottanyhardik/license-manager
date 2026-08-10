/**
 * Canonical Ledger Adapter
 *
 * Bridges between CanonicalLedgerService API and PDF/Excel export formats.
 *
 * CRITICAL CONSTRAINT:
 * - Fetches canonical data from API (single source of truth)
 * - Adapts for PDF/Excel presentation (formatting only)
 * - Must NOT recalculate balances, commissions, or totals
 * - All financial data from API, not from frontend
 */

import api from '../api/axios';

/**
 * Fetch canonical ledger data from API for a given license ID.
 *
 * @param {string | number} licenseId - The license ID or license number
 * @returns {Promise<Object>} Canonical ledger response from API
 * @throws {Error} If API call fails
 */
export async function fetchCanonicalLedger(licenseId) {
    try {
        const url = `license-ledger/${encodeURIComponent(licenseId)}/ledger_detail/`;
        const response = await api.get(url);
        return response.data;
    } catch (error) {
        console.error(`Failed to fetch canonical ledger for license ${licenseId}:`, error);
        throw new Error(`Failed to fetch ledger data: ${error.message}`);
    }
}

/**
 * Adapt canonical transaction to PDF/Excel row format.
 *
 * Maps canonical transaction structure to the format expected by PDF/Excel generation.
 * Uses canonical balance directly (no calculation).
 *
 * @param {Object} txn - Canonical transaction
 * @param {boolean} isDFIA - Whether this is a DFIA license
 * @returns {Object} Transaction adapted for PDF/Excel
 */
function adaptTransactionForExport(txn, isDFIA) {
    // The key insight: use canonical balance directly
    // No calculation, no transformation — just format for presentation
    return {
        date: txn.date || null,
        type: txn.type || 'UNKNOWN',
        company_id: txn.company_id ?? null,
        company_name: txn.company_name || 'N/A',
        particular: txn.particular || '-',
        invoice_number: txn.invoice_number || '',
        items: txn.items || '',

        // Canonical balance (DO NOT CALCULATE)
        license_running_balance: txn.license_running_balance,

        // These are 0 in canonical data (not used by PDF)
        // but included for compatibility with existing code
        debit_cif: isDFIA ? txn.amount : '0',
        credit_cif: isDFIA ? '0' : '0',
        debit_license_value: !isDFIA ? txn.amount : '0',
        credit_license_value: !isDFIA ? '0' : '0',

        debit_amount: txn.amount || '0',
        credit_amount: '0',

        rate: txn.rate || '0',
        profit_loss: txn.profit_loss ?? null,
        is_commission: txn.is_commission || false,

        _row_key: txn.id,
    };
}

/**
 * Build PDF/Excel transactions from canonical ledger data.
 *
 * Transforms canonical API response into format for PDF/Excel generation.
 * Preserves canonical balances (no recalculation).
 *
 * @param {Object} canonicalData - Response from CanonicalLedgerService API
 * @param {boolean} isDFIA - Whether this is a DFIA license
 * @returns {Array} Transactions adapted for PDF/Excel
 */
export function buildPdfTransactions(canonicalData, isDFIA) {
    if (!canonicalData.transactions || !Array.isArray(canonicalData.transactions)) {
        return [];
    }

    return canonicalData.transactions.map(txn => adaptTransactionForExport(txn, isDFIA));
}

/**
 * Adapt canonical license data to PDF/Excel format.
 *
 * Creates a license object compatible with existing PDF/Excel generation code.
 * All balances come from canonical API (no recalculation).
 *
 * @param {Object} canonicalData - Response from CanonicalLedgerService API
 * @returns {Object} License data adapted for PDF/Excel
 */
export function buildExportLicense(canonicalData) {
    const isDFIA = canonicalData.license_type === 'DFIA';

    return {
        id: canonicalData.license_id,
        license_id: canonicalData.license_id,
        license_number: canonicalData.license_number || 'N/A',
        license_type: canonicalData.license_type || 'UNKNOWN',
        license_date: canonicalData.license_date || null,
        expiry_date: canonicalData.expiry_date || null,
        exporter: canonicalData.exporter_name || 'N/A',
        total_value: canonicalData.total_value || '0',

        // Use canonical balance (no calculation)
        available_balance: canonicalData.license_running_balance,

        // Transactions adapted for export (balances from canonical API)
        transactions: buildPdfTransactions(canonicalData, isDFIA),

        // Preserve canonical metadata
        opening_balance: canonicalData.opening_balance,
        license_running_balance: canonicalData.license_running_balance,
        company_utilizations: canonicalData.company_utilizations || {},
        totals: canonicalData.totals || {},

        // Additional fields for compatibility
        sion_norms: canonicalData.sion_norms || null,
    };
}

/**
 * Fetch and adapt canonical ledger for PDF/Excel export.
 *
 * Single point of entry: fetches canonical data and adapts it for export.
 * All financial data sourced from API.
 *
 * @param {string | number} licenseId - The license ID or license number
 * @returns {Promise<Object>} License data ready for PDF/Excel generation
 * @throws {Error} If API call fails or data is invalid
 */
export async function getCanonicalLedgerForExport(licenseId) {
    try {
        const canonicalData = await fetchCanonicalLedger(licenseId);

        if (!canonicalData.license_id || !canonicalData.license_type) {
            throw new Error('Invalid canonical ledger response: missing required fields');
        }

        return buildExportLicense(canonicalData);
    } catch (error) {
        console.error(`Failed to prepare export license for ${licenseId}:`, error);
        throw error;
    }
}
