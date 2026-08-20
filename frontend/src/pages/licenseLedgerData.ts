export type LedgerTransaction = {
    trade_id: string | number;
    invoice_date: string;
    amount: number;
};

export type LedgerCompany = {
    company_id: string | number;
    company_name: string;
    purchases: LedgerTransaction[];
    sales: LedgerTransaction[];
    purchase_total: number;
    sale_total: number;
    profit_loss: number;
};

export type LicenseWiseEntry = {
    license_id: string | number;
    license_number: string;
    license_date: string;
    license_type: string;
    companies: LedgerCompany[];
};

export type LedgerGroupTotals = {
    license_count: number;
    total_purchase_bill_inr: number;
    total_sale_bill_inr: number;
    total_balance: number;
    total_profit_loss_inr: number;
};

export type LedgerGroupLicense = {
    license_id: string | number;
    license_number: string;
    license_date: string;
    license_type: string;
    first_purchase_date: string;
    sion_norms: string;
    current_balance: number;
    purchase_bill_inr: number;
    sale_bill_inr: number;
    profit_loss_inr: number;
    has_purchase_bill: boolean;
};

export type LedgerSionGroup = {
    sion_norm: string;
    label: string;
    license_count: number;
    licenses: LedgerGroupLicense[];
    total_purchase_bill_inr: number;
    total_sale_bill_inr: number;
    total_balance: number;
    total_profit_loss_inr: number;
};

export type LedgerCompanyGroup = {
    company_id: string | number;
    company_name: string;
    sion_groups: LedgerSionGroup[];
    total_purchase_bill_inr: number;
    total_sale_bill_inr: number;
    total_balance: number;
    total_profit_loss_inr: number;
};

export type LicenseWiseData = {
    licenses: LicenseWiseEntry[];
    company_groups?: LedgerCompanyGroup[];
    grand_total?: LedgerGroupTotals;
};

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null;
}

function normalizeText(value: unknown, fallback = ''): string {
    const normalized = String(value ?? '').trim();
    return normalized || fallback;
}

function toFiniteNumber(value: unknown): number {
    const numberValue = Number(value);
    return Number.isFinite(numberValue) ? numberValue : 0;
}

function normalizeId(value: unknown, fallback: string | number): string | number {
    if (typeof value === 'string') return normalizeText(value, String(fallback));
    if (typeof value === 'number' && Number.isFinite(value)) return value;
    return fallback;
}

function normalizeTransactions(value: unknown): LedgerTransaction[] {
    if (!Array.isArray(value)) return [];
    return value.flatMap((row, index) => {
        if (!isRecord(row)) return [];
        return [{ trade_id: normalizeId(row.trade_id, index), invoice_date: normalizeText(row.invoice_date, '-'), amount: toFiniteNumber(row.amount) }];
    });
}

export function normalizeLicenseWiseData(value: unknown): LicenseWiseData {
    const rawLicenses = isRecord(value) && Array.isArray(value.licenses) ? value.licenses : [];
    const rawCompanyGroups = isRecord(value) && Array.isArray(value.company_groups) ? value.company_groups : [];
    const rawGrandTotal = isRecord(value) && isRecord(value.grand_total) ? value.grand_total : null;
    const company_groups = rawCompanyGroups.flatMap((company, companyIndex) => {
        if (!isRecord(company)) return [];
        const rawSionGroups = Array.isArray(company.sion_groups) ? company.sion_groups : [];
        const sion_groups = rawSionGroups.flatMap((sion) => {
            if (!isRecord(sion)) return [];
            const rawRows = Array.isArray(sion.licenses) ? sion.licenses : [];
            const licenses = rawRows.flatMap((row) => {
                if (!isRecord(row) || row.license_id == null) return [];
                return [{ license_id: normalizeId(row.license_id, 'unknown-license'), license_number: normalizeText(row.license_number, 'Unknown license'), license_date: normalizeText(row.license_date, '-'), license_type: normalizeText(row.license_type, 'UNKNOWN'), first_purchase_date: normalizeText(row.first_purchase_date, '-'), sion_norms: normalizeText(row.sion_norms), current_balance: toFiniteNumber(row.current_balance), purchase_bill_inr: toFiniteNumber(row.purchase_bill_inr), sale_bill_inr: toFiniteNumber(row.sale_bill_inr), profit_loss_inr: toFiniteNumber(row.profit_loss_inr), has_purchase_bill: row.has_purchase_bill !== false }];
            });
            const norm = normalizeText(sion.sion_norm ?? sion.sion_norms);
            return [{ sion_norm: norm, label: normalizeText(sion.sion_label ?? sion.label ?? sion.group_label, norm || 'N/A / EMPTY'), license_count: toFiniteNumber(sion.license_count) || licenses.length, licenses, total_purchase_bill_inr: toFiniteNumber(sion.total_purchase_bill_inr), total_sale_bill_inr: toFiniteNumber(sion.total_sale_bill_inr), total_balance: toFiniteNumber(sion.total_balance), total_profit_loss_inr: toFiniteNumber(sion.total_profit_loss_inr) }];
        });
        return [{ company_id: normalizeId(company.company_id, companyIndex), company_name: normalizeText(company.company_name, 'Unknown company'), sion_groups, total_purchase_bill_inr: toFiniteNumber(company.total_purchase_bill_inr), total_sale_bill_inr: toFiniteNumber(company.total_sale_bill_inr), total_balance: toFiniteNumber(company.total_balance), total_profit_loss_inr: toFiniteNumber(company.total_profit_loss_inr) }];
    });
    return {
        licenses: rawLicenses.flatMap((license) => {
            if (!isRecord(license)) return [];
            const licenseId = license.license_id ?? license.id;
            if (licenseId === null || licenseId === undefined || String(licenseId).trim() === '') return [];
            const rawCompanies = Array.isArray(license.companies) ? license.companies : [];
            const companies = rawCompanies.flatMap((company, index) => {
                if (!isRecord(company)) return [];
                return [{ company_id: normalizeId(company.company_id, index), company_name: normalizeText(company.company_name, 'Unknown company'), purchases: normalizeTransactions(company.purchases), sales: normalizeTransactions(company.sales), purchase_total: toFiniteNumber(company.purchase_total), sale_total: toFiniteNumber(company.sale_total), profit_loss: toFiniteNumber(company.profit_loss) }];
            });
            return [{ license_id: normalizeId(licenseId, 'unknown-license'), license_number: normalizeText(license.license_number, 'Unknown license'), license_date: normalizeText(license.license_date, '-'), license_type: normalizeText(license.license_type, 'UNKNOWN'), companies }];
        }), ...(rawCompanyGroups.length > 0 ? { company_groups } : {}),
        ...(rawGrandTotal ? { grand_total: { license_count: toFiniteNumber(rawGrandTotal.license_count), total_purchase_bill_inr: toFiniteNumber(rawGrandTotal.total_purchase_bill_inr), total_sale_bill_inr: toFiniteNumber(rawGrandTotal.total_sale_bill_inr), total_balance: toFiniteNumber(rawGrandTotal.total_balance), total_profit_loss_inr: toFiniteNumber(rawGrandTotal.total_profit_loss_inr) } } : {}),
    };
}
