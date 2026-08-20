import type { CanonicalLedgerResponse } from '../types/canonicalLedger';

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null;
}

function normalizeText(value: unknown, fallback = ''): string {
    const normalized = String(value ?? '').trim();
    return normalized || fallback;
}

function encodeLedgerPathSegment(value: unknown): string | null {
    const normalized = normalizeText(value);
    return normalized ? encodeURIComponent(normalized) : null;
}

export function buildLedgerDetailPath(id: unknown, companyId?: unknown): string | null {
    const safeId = encodeLedgerPathSegment(id);
    if (!safeId) return null;
    const params = new URLSearchParams();
    const safeCompanyId = normalizeText(companyId);
    if (safeCompanyId) params.append('company', safeCompanyId);
    const queryString = params.toString();
    return `license-ledger/${safeId}/ledger_detail/${queryString ? `?${queryString}` : ''}`;
}

export function normalizeLedgerDetail(value: unknown): CanonicalLedgerResponse | null {
    if (!isRecord(value) || !value.license_number || !value.license_type) return null;
    return value as unknown as CanonicalLedgerResponse;
}
