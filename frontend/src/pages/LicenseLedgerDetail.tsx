import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import api from '../api/axios';
import { formatIndianNumber } from '../utils/numberFormatter';
import { formatDate as formatDateUtil } from '../utils/dateFormatter';
import { generatePDF, generateExcel } from '../utils/ledgerExport';
import { cn } from '@/lib/utils';
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
    ArrowLeft, Building2, FileSpreadsheet, FileText, Loader2, TriangleAlert,
} from "lucide-react";

// ─── Types ──────────────────────────────────────────────────────────────────────

type LedgerTransaction = Record<string, unknown> & {
    type?: string;
    company_id?: string | number | null;
    company_name?: string;
};

type LedgerDetail = Record<string, unknown> & {
    license_number: string;
    license_type: string;
    transactions: LedgerTransaction[];
};

// ─── Pure utilities ─────────────────────────────────────────────────────────────

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

export function normalizeLedgerDetail(value: unknown): LedgerDetail | null {
    if (!isRecord(value)) return null;
    const transactions = Array.isArray(value.transactions)
        ? value.transactions.flatMap((transaction) => {
            if (!isRecord(transaction)) return [];
            return [{ ...transaction, type: normalizeText(transaction.type, 'UNKNOWN'), company_name: normalizeText(transaction.company_name, 'N/A') }];
        })
        : [];
    return {
        ...value,
        license_number: normalizeText(value.license_number, 'Unknown license'),
        license_type: normalizeText(value.license_type, 'UNKNOWN'),
        available_balance: toFiniteNumber(value.available_balance),
        total_value: toFiniteNumber(value.total_value),
        transactions,
    };
}

export function sanitizeLedgerFilenamePart(value: unknown): string {
    return normalizeText(value, 'license')
        .split('')
        .map((char) => {
            const code = char.charCodeAt(0);
            return code < 32 || code === 127 || '\\/:*?"<>|'.includes(char) ? '-' : char;
        })
        .join('')
        .replace(/\s+/g, '-').replace(/-+/g, '-').replace(/^-+|-+$/g, '')
        .slice(0, 120) || 'license';
}

export function getTodayStamp(date = new Date()): string {
    return date.toISOString().slice(0, 10);
}

function getApiErrorMessage(error: unknown, fallback: string): string {
    if (isRecord(error) && isRecord(error.response) && isRecord(error.response.data)) {
        const message = (error.response.data as Record<string, unknown>).error
            ?? (error.response.data as Record<string, unknown>).detail
            ?? (error.response.data as Record<string, unknown>).message;
        if (message) return normalizeText(message, fallback);
    }
    if (error instanceof Error) return normalizeText(error.message, fallback);
    return fallback;
}

export function groupTransactionsByCompany(transactions: LedgerTransaction[]) {
    const companiesMap: Record<string, { company_id: string | number | null; company_name: string; transactions: LedgerTransaction[] }> = {};
    transactions.forEach((txn, index) => {
        const key = txn.company_id != null ? String(txn.company_id) : `unknown-${index}`;
        if (!companiesMap[key]) {
            companiesMap[key] = { company_id: txn.company_id ?? key, company_name: normalizeText(txn.company_name, 'N/A'), transactions: [] };
        }
        companiesMap[key].transactions.push(txn);
    });
    return Object.values(companiesMap);
}

// ─── Main component ──────────────────────────────────────────────────────────────

export default function LicenseLedgerDetail() {
    const { id, companyId } = useParams();
    const navigate = useNavigate();
    const location = useLocation();
    const [ledger, setLedger] = useState<Record<string, unknown> | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const queryParams = new URLSearchParams(location.search);
    const licenseType = queryParams.get('license_type') || (location.state as Record<string, unknown>)?.license_type || 'DFIA';

    useEffect(() => {
        const fetchLedgerDetail = async () => {
            setLoading(true);
            setError(null);
            try {
                const url = buildLedgerDetailPath(id, companyId);
                if (!url) { setLedger(null); setError('Missing license ledger identifier'); return; }
                const response = await api.get(url);
                const normalizedLedger = normalizeLedgerDetail(response.data);
                if (!normalizedLedger) { setLedger(null); setError('Ledger details response was malformed'); return; }
                setLedger(normalizedLedger);
            } catch (err) {
                setError(getApiErrorMessage(err, 'Failed to load ledger details'));
            } finally {
                setLoading(false);
            }
        };
        fetchLedgerDetail();
    }, [id, licenseType, companyId]);

    const formatDate = (dateStr: unknown): string => {
        if (!dateStr) return '-';
        return formatDateUtil(String(dateStr)) || '-';
    };

    const formatCurrency = (value: unknown, currency = 'INR'): string => {
        if (!value && value !== 0) return '-';
        const symbol = currency === 'USD' ? '$' : '₹';
        return `${symbol}${formatIndianNumber(toFiniteNumber(value), 2)}`;
    };

    // ── Loading state ────────────────────────────────────────────────────────
    if (loading) {
        return (
            <div className="py-4">
                <div className="flex flex-col items-center gap-2 py-12 text-center">
                    <Loader2 className="size-8 animate-spin text-primary" aria-hidden="true" />
                    <span className="text-sm text-muted-foreground">Loading…</span>
                </div>
            </div>
        );
    }

    // ── Error state ──────────────────────────────────────────────────────────
    if (error) {
        return (
            <div className="py-4">
                <div className="mb-3 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-[13px] text-destructive" role="alert">
                    <TriangleAlert className="size-4 shrink-0" aria-hidden="true" />
                    {error}
                </div>
                <Button onClick={() => navigate(-1)}>
                    <ArrowLeft className="size-4" aria-hidden="true" />Go Back
                </Button>
            </div>
        );
    }

    if (!ledger) return null;

    const isDFIA = ledger.license_type === 'DFIA';
    const hasPurchases = (ledger.transactions as LedgerTransaction[] || []).some(
        t => t.type === 'PURCHASE' || t.type === 'OPENING',
    );
    const currentBalance = toFiniteNumber(ledger.available_balance);
    const isNegativeBalance = currentBalance < 0;
    const showPurchaseWarning = !hasPurchases || isNegativeBalance;

    // When the ledger was opened with a company filter (companyId in the URL),
    // include the company name in the filename so downloads are clearly scoped.
    const exportCompanyPart = companyId
        ? sanitizeLedgerFilenamePart(ledger.transactions[0]?.company_name ?? String(companyId))
        : null;

    const buildExportFilename = (ext: 'pdf' | 'xlsx') =>
        [
            'License_Ledger',
            sanitizeLedgerFilenamePart(ledger.license_number),
            exportCompanyPart,
            getTodayStamp(),
        ].filter(Boolean).join('_') + `.${ext}`;

    const handleDownloadPDF = () => {
        generatePDF([ledger], buildExportFilename('pdf'));
    };
    const handleDownloadExcel = async () => {
        await generateExcel([ledger], buildExportFilename('xlsx'));
    };

    return (
        <div className="min-h-screen bg-muted/40">
            {/* ── Tally-style toolbar ───────────────────────────── */}
            <div className="border-b-2 border-border-strong bg-foreground px-5 py-2.5">
                <div className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                        <Button variant="secondary" size="sm" onClick={() => navigate(-1)}>
                            <ArrowLeft className="size-4" aria-hidden="true" />Back
                        </Button>
                        <span className="text-[1.1rem] font-medium text-white">License Ledger</span>
                    </div>
                    <div className="flex items-center gap-2">
                        <Button variant="destructive" size="sm" onClick={handleDownloadPDF}>
                            <FileText className="size-4" aria-hidden="true" />Download PDF
                        </Button>
                        <Button size="sm" className="bg-success text-white hover:bg-success/90" onClick={handleDownloadExcel}>
                            <FileSpreadsheet className="size-4" aria-hidden="true" />Download Excel
                        </Button>
                        <span className="ml-1 text-[14.5px] text-white/70">
                            {formatDate(new Date().toISOString())}
                        </span>
                    </div>
                </div>
            </div>

            {/* ── Purchase warning ──────────────────────────────── */}
            {showPurchaseWarning && (
                <div className="flex items-center gap-4 border-l-[5px] border-warning bg-warning/10 px-5 py-3.5">
                    <TriangleAlert className="size-4 shrink-0 text-warning" aria-hidden="true" />
                    <div>
                        <strong className="mb-1 block text-sm font-semibold text-warning">⚠️ Action Required</strong>
                        <span className="text-[13px] text-warning/80">
                            {!hasPurchases && isNegativeBalance &&
                                'No purchase transactions found and balance is negative. Please add purchase entries to maintain proper accounting.'}
                            {!hasPurchases && !isNegativeBalance &&
                                'No purchase transactions found. Please add purchase entries for this license.'}
                            {hasPurchases && isNegativeBalance &&
                                `Balance is negative (${formatCurrency(currentBalance, isDFIA ? 'USD' : 'INR')}). Please add purchase transactions to cover the deficit.`}
                        </span>
                    </div>
                </div>
            )}

            {/* ── License header ────────────────────────────────── */}
            <div className="border border-t-0 border-border bg-card px-7 py-6 shadow-sm">
                <div className="grid grid-cols-1 items-center gap-4 md:grid-cols-3">
                    <div className="md:col-span-2">
                        <h4 className="mb-3.5 flex items-center gap-3 text-[1.1rem] font-semibold text-foreground">
                            {String(ledger.license_number)}
                            <Badge
                                variant={isDFIA ? "default" : "info"}
                                className="text-[12px] px-3 py-1"
                            >
                                {String(ledger.license_type)}
                            </Badge>
                        </h4>
                        <div className="grid grid-cols-1 gap-3 text-[15px] sm:grid-cols-2">
                            <div>
                                <span className="mr-2.5 text-muted-foreground">Exporter:</span>
                                <strong>{normalizeText(ledger.exporter, 'N/A')}</strong>
                            </div>
                            <div>
                                <span className="mr-2.5 text-muted-foreground">License Date:</span>
                                <strong>{formatDate(ledger.license_date)}</strong>
                            </div>
                            {isDFIA && (
                                <div>
                                    <span className="mr-2.5 text-muted-foreground">SION Norms:</span>
                                    <strong className="text-info">
                                        {(() => {
                                            const allNorms = [...new Set(
                                                (ledger.transactions as LedgerTransaction[])
                                                    .filter(t => t.sion_norms)
                                                    .flatMap(t => String(t.sion_norms).split(', '))
                                            )];
                                            return allNorms.length > 0 ? allNorms.join(', ') : 'N/A';
                                        })()}
                                    </strong>
                                </div>
                            )}
                            <div>
                                <span className="mr-2.5 text-muted-foreground">Expiry Date:</span>
                                <strong>{formatDate(ledger.expiry_date)}</strong>
                            </div>
                            <div>
                                <span className="mr-2.5 text-muted-foreground">Total Value:</span>
                                <strong className="text-primary">
                                    {formatCurrency(ledger.total_value, isDFIA ? 'USD' : 'INR')}
                                </strong>
                            </div>
                        </div>
                    </div>

                    {/* Balance panel */}
                    <div className="text-right">
                        <div className="inline-block rounded-md border-2 border-border bg-muted/60 px-5 py-5 text-right">
                            <div className="mb-2 text-[13.5px] font-medium text-muted-foreground uppercase tracking-wide">
                                CURRENT BALANCE
                            </div>
                            <div className={cn(
                                "text-[1.75rem] font-bold tabular-nums",
                                currentBalance >= 0 ? "text-success" : "text-destructive",
                            )}>
                                {formatCurrency(currentBalance, isDFIA ? 'USD' : 'INR')}
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* ── Company-grouped ledger tables ─────────────────── */}
            {(() => {
                const companiesGrouped = groupTransactionsByCompany(ledger.transactions as LedgerTransaction[]);
                const TXN_SORT_ORDER: Record<string, number> = { OPENING: 0, PURCHASE: 1, SALE: 2 };

                return companiesGrouped.map((company, ci) => {
                    const rawTxns = company.transactions;
                    const txns = [...rawTxns].sort((a, b) =>
                        ((TXN_SORT_ORDER[a.type ?? ''] ?? 1) - (TXN_SORT_ORDER[b.type ?? ''] ?? 1))
                    );

                    let companyRunning = 0;
                    const companyBalMap = new Map<LedgerTransaction, number>();
                    for (const txn of txns) {
                        if (txn.type === 'PURCHASE' || txn.type === 'OPENING') {
                            companyRunning += isDFIA ? toFiniteNumber(txn.debit_cif) : toFiniteNumber(txn.debit_license_value);
                        } else if (txn.type === 'SALE') {
                            companyRunning -= isDFIA ? toFiniteNumber(txn.credit_cif) : toFiniteNumber(txn.credit_license_value);
                        }
                        companyBalMap.set(txn, companyRunning);
                    }

                    const totalDebit = txns.reduce((s, t) => s + toFiniteNumber(t.debit_amount), 0);
                    const totalCredit = txns.reduce((s, t) => s + toFiniteNumber(t.credit_amount), 0);
                    const companyPL = totalCredit - totalDebit;

                    const marginTop = ci === 0 ? "mt-5" : "mt-3";
                    const marginBottom = ci === companiesGrouped.length - 1 ? "mb-5" : "mb-0";

                    return (
                        <div
                            key={company.company_id ?? ci}
                            className={cn(
                                "mx-5 overflow-hidden rounded-md border border-border shadow-md",
                                marginTop, marginBottom,
                            )}
                        >
                            {/* Company header */}
                            <div className="flex items-center gap-2 bg-primary px-5 py-2.5 text-[15px] font-bold text-primary-foreground">
                                <Building2 className="size-4 shrink-0" aria-hidden="true" />
                                {company.company_name}
                            </div>

                            {/* Company ledger table */}
                            <div className="overflow-x-auto">
                                <table className="w-full border-collapse bg-card text-[0.82rem]">
                                    <thead>
                                        <tr className="border-b-2 border-primary/20 bg-primary/8">
                                            <th scope="col" className="px-2.5 py-[7px] text-left font-bold text-foreground">Date</th>
                                            <th scope="col" className="px-2.5 py-[7px] text-left font-bold text-foreground">Particulars</th>
                                            {isDFIA && <th scope="col" className="px-2.5 py-[7px] text-left font-bold text-foreground">Items</th>}
                                            {isDFIA ? (
                                                <>
                                                    <th scope="col" className="px-2.5 py-[7px] text-right font-bold text-foreground">CIF $ Dr</th>
                                                    <th scope="col" className="px-2.5 py-[7px] text-right font-bold text-foreground">CIF $ Cr</th>
                                                </>
                                            ) : (
                                                <>
                                                    <th scope="col" className="px-2.5 py-[7px] text-right font-bold text-foreground">Value Dr</th>
                                                    <th scope="col" className="px-2.5 py-[7px] text-right font-bold text-foreground">Value Cr</th>
                                                </>
                                            )}
                                            <th scope="col" className="px-2.5 py-[7px] text-right font-bold text-foreground">Rate</th>
                                            <th scope="col" className="px-2.5 py-[7px] text-right font-bold text-success">Debit (₹)</th>
                                            <th scope="col" className="px-2.5 py-[7px] text-right font-bold text-destructive">Credit (₹)</th>
                                            <th scope="col" className="px-2.5 py-[7px] text-right font-bold text-foreground">
                                                {isDFIA ? 'Balance ($)' : 'Balance (₹)'}
                                            </th>
                                            <th scope="col" className="px-2.5 py-[7px] text-right font-bold text-foreground">P/L</th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {txns.map((txn, ti) => {
                                            const isPurchase = txn.type === 'PURCHASE' || txn.type === 'OPENING';
                                            const isSale = txn.type === 'SALE';
                                            const rowBal = companyBalMap.get(txn) ?? 0;
                                            const profitLoss = toFiniteNumber(txn.profit_loss);
                                            return (
                                                <tr
                                                    key={ti}
                                                    className={cn(
                                                        "border-b",
                                                        isPurchase ? "border-success/20 bg-success/[0.06]"
                                                            : isSale ? "border-destructive/20 bg-destructive/[0.06]"
                                                            : "border-border/60 bg-card",
                                                    )}
                                                >
                                                    <td className="whitespace-nowrap px-2.5 py-[5px] text-muted-foreground">
                                                        {formatDate(txn.date as string)}
                                                    </td>
                                                    <td className="px-2.5 py-[5px] text-foreground">
                                                        {String(txn.particular ?? '')}
                                                        {txn.invoice_number && (
                                                            <span className="mt-0.5 block text-[12px] text-muted-foreground">
                                                                ({String(txn.invoice_number)})
                                                            </span>
                                                        )}
                                                    </td>
                                                    {isDFIA && (
                                                        <td className="px-2.5 py-[5px] text-foreground">
                                                            {String(txn.items ?? '-')}
                                                        </td>
                                                    )}
                                                    {isDFIA ? (
                                                        <>
                                                            <td className="px-2.5 py-[5px] text-right text-success">
                                                                {txn.debit_cif ? formatIndianNumber(toFiniteNumber(txn.debit_cif), 2) : '-'}
                                                            </td>
                                                            <td className="px-2.5 py-[5px] text-right text-destructive">
                                                                {txn.credit_cif ? formatIndianNumber(toFiniteNumber(txn.credit_cif), 2) : '-'}
                                                            </td>
                                                        </>
                                                    ) : (
                                                        <>
                                                            <td className="px-2.5 py-[5px] text-right text-success">
                                                                {txn.debit_license_value ? formatIndianNumber(toFiniteNumber(txn.debit_license_value), 2) : '-'}
                                                            </td>
                                                            <td className="px-2.5 py-[5px] text-right text-destructive">
                                                                {txn.credit_license_value ? formatIndianNumber(toFiniteNumber(txn.credit_license_value), 2) : '-'}
                                                            </td>
                                                        </>
                                                    )}
                                                    <td className="px-2.5 py-[5px] text-right text-foreground">
                                                        {txn.rate ? formatIndianNumber(toFiniteNumber(txn.rate), 2) : '-'}
                                                    </td>
                                                    <td className="px-2.5 py-[5px] text-right font-semibold text-success">
                                                        {txn.debit_amount ? `₹${formatIndianNumber(toFiniteNumber(txn.debit_amount), 2)}` : '-'}
                                                    </td>
                                                    <td className="px-2.5 py-[5px] text-right font-semibold text-destructive">
                                                        {txn.credit_amount ? `₹${formatIndianNumber(toFiniteNumber(txn.credit_amount), 2)}` : '-'}
                                                    </td>
                                                    <td className={cn(
                                                        "px-2.5 py-[5px] text-right tabular-nums",
                                                        rowBal >= 0 ? "text-success" : "text-destructive",
                                                    )}>
                                                        {formatIndianNumber(rowBal, 2)}
                                                    </td>
                                                    <td className={cn(
                                                        "px-2.5 py-[5px] text-right tabular-nums",
                                                        profitLoss >= 0 ? "text-success" : "text-destructive",
                                                    )}>
                                                        {txn.type === 'SALE' && txn.profit_loss != null
                                                            ? formatIndianNumber(Math.abs(profitLoss), 2)
                                                            : '-'}
                                                    </td>
                                                </tr>
                                            );
                                        })}

                                        {/* Company total row */}
                                        <tr className="bg-primary font-bold text-primary-foreground">
                                            <td colSpan={isDFIA ? 6 : 5} className="px-2.5 py-[7px] text-right text-[12.5px]">
                                                Total — {company.company_name}
                                            </td>
                                            <td className="px-2.5 py-[7px] text-right text-emerald-300 tabular-nums">
                                                ₹{formatIndianNumber(totalDebit, 2)}
                                            </td>
                                            <td className="px-2.5 py-[7px] text-right text-red-300 tabular-nums">
                                                ₹{formatIndianNumber(totalCredit, 2)}
                                            </td>
                                            <td className="px-2.5 py-[7px] text-right tabular-nums text-white">
                                                {formatIndianNumber(companyRunning, 2)}
                                            </td>
                                            <td className={cn(
                                                "px-2.5 py-[7px] text-right tabular-nums",
                                                companyPL >= 0 ? "text-emerald-300" : "text-red-300",
                                            )}>
                                                {companyPL !== 0
                                                    ? `${companyPL >= 0 ? '+' : ''}₹${formatIndianNumber(Math.abs(companyPL), 2)}`
                                                    : '-'}
                                            </td>
                                        </tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    );
                });
            })()}
        </div>
    );
}
