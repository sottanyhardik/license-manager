import React, { useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import api from '../api/axios';
import { toast } from 'sonner';
import {
    downloadLicenseLedgerExcel, licenseLedgerExportError, previewLicenseLedgerPdf,
} from '../services/licenseLedgerExport';
import { formatIndianNumber } from '../utils/numberFormatter';
import { formatDate as formatDateUtil } from '../utils/dateFormatter';
import { cn } from '@/lib/utils';
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
    ArrowLeft, Building2, FileSpreadsheet, FileText, Loader2, Minus, ScrollText,
    TrendingDown, TrendingUp, TriangleAlert, Wallet,
} from "lucide-react";
import { selectLedgerDisplayRows } from '@/utils/ledgerDisplayRows';
import StatCard from '@/components/StatCard';
import type {
    CanonicalLedgerResponse, CanonicalTransaction, CompanyUtilization, LedgerSummary, ProfitState,
} from '../types/canonicalLedger';
import { buildLedgerDetailPath, normalizeLedgerDetail } from './licenseLedgerDetailUtils';

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

/**
 * THE one money formatter for this page — symbol + Indian digit grouping.
 *
 * PRESENTATION ONLY. `toFiniteNumber` exists to hand `formatIndianNumber` a
 * number to group the digits of; it is NOT arithmetic on the value. Every
 * figure arrives from the backend already correct and already quantized to 2dp,
 * and it is rendered at that same 2dp — nothing is summed, netted, converted or
 * re-rounded on the client.
 *
 * `currency` must be the currency the BACKEND declared for that specific figure
 * (`balance_currency` / `bill_currency` / `profit_currency`) — never guessed
 * from the licence type at the call site. The three are genuinely different for
 * one DFIA licence: balance in USD, bill and profit in INR.
 */
function formatMoney(value: unknown, currency = 'INR'): string {
    if (!value && value !== 0) return '-';
    const symbol = currency === 'USD' ? '$' : '₹';
    return `${symbol}${formatIndianNumber(toFiniteNumber(value), 2)}`;
}

/**
 * Presentation of the four `profit_state` values from the backend.
 *
 * Driven ENTIRELY by the backend's `profit_state` — this page never inspects the
 * sign of `total_profit_loss` to decide a colour or a label. Consequences the
 * spec requires and this table encodes:
 *   * PROFIT is green, LOSS is red, BREAK_EVEN and UNAVAILABLE are neutral.
 *   * LOSS shows the MAGNITUDE under a "LOSS" label, so "-$5,000" can never
 *     appear beneath the word "PROFIT". The direction is in the word, never in
 *     colour alone.
 *   * BREAK_EVEN reads "BREAK-EVEN" — exact zero is a real financial statement.
 *   * UNAVAILABLE shows "PROFIT / LOSS" with "N/A" instead of a figure.
 */
const PROFIT_STATE_PRESENTATION: Record<ProfitState, {
    label: string; tone: 'success' | 'danger' | 'neutral'; icon: typeof TrendingUp;
    /** Strip the sign: the label already carries the direction. */
    magnitude: boolean;
}> = {
    PROFIT: { label: 'PROFIT', tone: 'success', icon: TrendingUp, magnitude: false },
    LOSS: { label: 'LOSS', tone: 'danger', icon: TrendingDown, magnitude: true },
    BREAK_EVEN: { label: 'BREAK-EVEN', tone: 'neutral', icon: Minus, magnitude: false },
    UNAVAILABLE: { label: 'PROFIT / LOSS', tone: 'neutral', icon: Wallet, magnitude: false },
};

/**
 * The CA summary band: TOTAL CREDIT / TOTAL DEBIT / CURRENT BALANCE /
 * PROFIT-LOSS.
 *
 * Every value is a string straight from `summary` — no `reduce`, no `+`, no
 * `-`, no re-rounding, no classification. Renders nothing at all when `summary`
 * is absent (an older cached payload): showing zeros there would be inventing
 * figures.
 *
 * Credit is tinted as a gain and Debit as a reduction, matching the row tints in
 * the table below: a purchase adds licence value, a sale consumes it.
 *
 * Reuses `@/components/StatCard` (the app's existing KPI card, in `compact`
 * mode — built precisely for long currency strings). No new card component.
 */
function LedgerSummaryCards({ summary }: { summary: LedgerSummary | undefined }) {
    if (!summary) return null;

    const profit = PROFIT_STATE_PRESENTATION[summary.profit_state]
        // Unknown/newer state from the server degrades to neutral rather than
        // crashing the financial screen.
        ?? PROFIT_STATE_PRESENTATION.UNAVAILABLE;

    const profitValue = !summary.total_profit_loss && summary.total_profit_loss !== '0'
        ? 'N/A'
        : formatMoney(
            profit.magnitude
                // Sign stripped for display only — the direction is in the label,
                // so "-$46,499.94" can never sit under the word PROFIT.
                ? String(summary.total_profit_loss).replace(/^-/, '')
                : summary.total_profit_loss,
            summary.profit_currency,
        );

    return (
        <div
            data-testid="ledger-summary-cards"
            className="grid grid-cols-1 gap-2 px-3 pt-2 sm:grid-cols-2 xl:grid-cols-4"
        >
            <StatCard
                compact
                label="Total Purchase"
                value={formatMoney(summary.total_purchase, summary.balance_currency)}
                secondaryValue={`Bill ${formatMoney(summary.total_purchase_bill_inr, summary.bill_currency)}`}
                icon={Wallet}
                tone="success"
            />
            <StatCard
                compact
                label="Total Sale"
                value={formatMoney(summary.total_sale, summary.balance_currency)}
                secondaryValue={`Bill ${formatMoney(summary.total_sale_bill_inr, summary.bill_currency)}`}
                icon={Wallet}
                tone="danger"
            />
            <StatCard
                compact
                label="Current Balance"
                value={formatMoney(summary.current_balance, summary.balance_currency)}
                secondaryValue="Total Purchase − Total Sale"
                icon={ScrollText}
                tone="primary"
            />
            <StatCard
                compact
                label={profit.label}
                value={profitValue}
                icon={profit.icon}
                tone={profit.tone}
                secondaryValue="Total Purchase − Total Sale"
            />
        </div>
    );
}

function groupTransactionsByCompany(transactions: CanonicalTransaction[]) {
    const companiesMap: Record<string, { company_id: string | number | null; company_name: string; transactions: CanonicalTransaction[] }> = {};
    transactions.forEach((txn, index) => {
        const key = txn.company_id != null ? String(txn.company_id) : `unknown-${index}`;
        if (!companiesMap[key]) {
            companiesMap[key] = { company_id: txn.company_id ?? key, company_name: normalizeText(txn.company_name, '-'), transactions: [] };
        }
        companiesMap[key].transactions.push(txn);
    });
    return Object.values(companiesMap);
}

// ─── Shared ledger table chrome ─────────────────────────────────────────────────

/**
 * The one column set for the ledger table — reused by the opening starting-state
 * block and by every company group so the two always line up.
 */
function LedgerColumnHeader({ isDFIA, billCurrency }: { isDFIA: boolean; billCurrency: string }) {
    const licenceSuffix = isDFIA ? '($)' : '(₹)';
    const billSuffix = billCurrency === 'USD' ? '($)' : '(₹)';
    return (
        <thead className="sticky top-0 z-10">
            <tr className="border-b-2 border-primary/20 bg-primary/8 text-xs">
                <th scope="col" className="px-2.5 py-1 text-left font-bold text-foreground">Date</th>
                <th scope="col" className="px-2.5 py-1 text-left font-bold text-foreground">Particulars</th>
                <th scope="col" className="px-2.5 py-1 text-left font-bold text-foreground">Invoice</th>
                <th scope="col" className="px-2.5 py-1 text-left font-bold text-foreground">Type</th>
                {isDFIA && <th scope="col" className="px-2.5 py-1 text-left font-bold text-foreground">Items</th>}
                <th scope="col" className="px-2.5 py-1 text-right font-bold text-destructive">Sale {licenceSuffix}</th>
                <th scope="col" className="px-2.5 py-1 text-right font-bold text-success">Purchase {licenceSuffix}</th>
                <th scope="col" className="whitespace-nowrap px-2.5 py-1 text-right font-medium text-destructive">
                    Sale Bill {billSuffix}
                </th>
                <th scope="col" className="whitespace-nowrap px-2.5 py-1 text-right font-medium text-success">
                    Purchase Bill {billSuffix}
                </th>
            </tr>
        </thead>
    );
}

function InvoiceDocumentCell({ transaction }: { transaction: CanonicalTransaction }) {
    const document = transaction.invoice_document;
    const invoiceNumber = normalizeText(document?.invoice_number, '-');

    if (document?.document_exists && document.secure_url) {
        return (
            <td className="px-2.5 py-1 text-xs text-foreground">
                <a
                    href={document.secure_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="font-medium text-primary underline underline-offset-2 hover:text-primary/80"
                    aria-label={`Open invoice ${invoiceNumber}`}
                >
                    {invoiceNumber}
                </a>
                <span className="ml-1 whitespace-nowrap text-[9px] font-semibold text-muted-foreground">
                    {document.signed ? 'SGN' : 'UNS'}
                </span>
            </td>
        );
    }

    return (
        <td className="px-2.5 py-1 text-xs text-foreground">
            <span>{invoiceNumber}</span>
            {document?.status === 'COPY_UNAVAILABLE' && (
                <span className="ml-1 text-[9px] text-muted-foreground">unavailable</span>
            )}
        </td>
    );
}

/**
 * The Items cell — real item names, never a bare "-" placeholder when names
 * exist.
 *
 * One trade is ONE row however many items it bills, so several names are shown
 * inline with the overflow collapsed into "+N" and the full list on hover
 * (`title`) for accessibility. The row is NEVER duplicated per item.
 */
function LedgerItemsCell({ itemNames }: { itemNames: string[] | undefined }) {
    const names = (itemNames ?? []).filter(Boolean);
    if (!names.length) {
        return <td className="px-2.5 py-1 text-xs text-muted-foreground">-</td>;
    }
    const [first, ...rest] = names;
    const fullList = names.join(', ');
    return (
        <td
            className="max-w-[180px] px-2.5 py-1 text-xs text-foreground"
            title={fullList}
            aria-label={fullList}
        >
            <span className="block truncate">
                {first}
                {rest.length > 0 && (
                    <span className="ml-1 text-muted-foreground" aria-hidden="true">+{rest.length}</span>
                )}
            </span>
        </td>
    );
}

// ─── Main component ──────────────────────────────────────────────────────────────

export default function LicenseLedgerDetail() {
    const { licenseId, itemId } = useParams();
    const navigate = useNavigate();
    const location = useLocation();
    const [ledger, setLedger] = useState<CanonicalLedgerResponse | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [exporting, setExporting] = useState<'pdf' | 'xlsx' | null>(null);

    const queryParams = new URLSearchParams(location.search);
    const licenseType = queryParams.get('license_type') || (location.state as Record<string, unknown>)?.license_type || 'DFIA';

    useEffect(() => {
        const fetchLedgerDetail = async () => {
            setLoading(true);
            setError(null);
            try {
                const url = buildLedgerDetailPath(licenseId, itemId);
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
    }, [licenseId, licenseType, itemId]);

    const formatDate = (dateStr: unknown): string => {
        if (!dateStr) return '-';
        return formatDateUtil(String(dateStr)) || '-';
    };

    // Single implementation, shared with the summary cards (see `formatMoney`).
    const formatCurrency = formatMoney;

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
                <div className="mb-3 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-sm text-destructive" role="alert">
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

    const exportScope = { licenseId: licenseId!, itemId: itemId!, licenseType: ledger.license_type };
    const runExport = async (format: 'pdf' | 'xlsx') => {
        if (exporting) return;
        setExporting(format);
        try {
            if (format === 'pdf') await previewLicenseLedgerPdf(exportScope);
            else await downloadLicenseLedgerExcel(exportScope);
        } catch (exportError) {
            toast.error(licenseLedgerExportError(exportError, `Failed to generate ${format === 'pdf' ? 'PDF' : 'Excel'}.`));
        } finally {
            setExporting(null);
        }
    };

    const isDFIA = ledger.license_type === 'DFIA';
    // NOTE: not a display decision — this drives the "Action Required" banner and
    // deliberately reads the COMPLETE financial collection (`transactions`),
    // opening row included. Which rows get rendered is decided further down by
    // `selectLedgerDisplayRows`.
    const hasPurchases = ledger.has_purchase_transaction ?? false;
    // The canonical reconciliation block. Optional only for older cached
    // payloads; when absent the summary band is hidden rather than zero-filled.
    const summary = ledger.summary;
    // Currency comes from the BACKEND per figure. The `isDFIA` fallbacks exist
    // solely for pre-`summary` payloads and reproduce the old behaviour; they
    // are not a second source of truth.
    const balanceCurrency = summary?.balance_currency ?? (isDFIA ? 'USD' : 'INR');
    const billCurrency = summary?.bill_currency ?? 'INR';
    // ONE balance, ONE source: the header figure and the Current Balance card
    // both read `summary.current_balance`, so they cannot disagree.
    //
    // The `license_running_balance` fallback is ONLY for pre-`summary` cached
    // payloads. It is deliberately not the primary: it double-counts the
    // acquisition of a purchased licence (opening + the purchase that created
    // that opening), which is the very figure the summary replaces.
    const currentBalanceValue = summary?.current_balance ?? ledger.license_running_balance;
    // Numeric form used ONLY for the sign — which colour to paint, and whether
    // to raise the deficit warning. Never used to derive a displayed figure.
    const currentBalance = toFiniteNumber(currentBalanceValue);
    const isNegativeBalance = currentBalance < 0;
    const showPurchaseWarning = !hasPurchases || isNegativeBalance;

    return (
        <div className="min-h-screen bg-muted/40">
            {/* ── Toolbar (compact) ─────────────────────────────── */}
            <div className="sticky top-0 z-20 border-b border-border-strong bg-foreground px-3 py-1.5 shadow-sm sm:px-5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                        <Button variant="secondary" size="sm" onClick={() => navigate(-1)}>
                            <ArrowLeft className="size-3.5" aria-hidden="true" />
                            <span className="hidden sm:inline">Back</span>
                        </Button>
                        <span className="text-sm font-medium text-white">Ledger</span>
                    </div>
                    <div className="flex flex-wrap items-center gap-2">
                        <Button
                            variant="secondary"
                            size="sm"
                            disabled={exporting !== null}
                            onClick={() => runExport('pdf')}
                            aria-label="Export ledger as PDF"
                        >
                            {exporting === 'pdf' ? <Loader2 className="size-3.5 animate-spin" /> : <FileText className="size-3.5" />}
                            <span className="hidden sm:inline">PDF</span>
                        </Button>
                        <Button
                            variant="secondary"
                            size="sm"
                            disabled={exporting !== null}
                            onClick={() => runExport('xlsx')}
                            aria-label="Export ledger as Excel"
                        >
                            {exporting === 'xlsx' ? <Loader2 className="size-3.5 animate-spin" /> : <FileSpreadsheet className="size-3.5" />}
                            <span className="hidden sm:inline">Excel</span>
                        </Button>
                    </div>
                </div>
            </div>

            {/* ── Purchase warning ──────────────────────────────── */}
            {showPurchaseWarning && (
                <div className="mx-3 mt-2 flex items-start gap-2 rounded-md border border-warning/30 border-l-4 border-warning bg-warning/10 px-3 py-2 sm:mx-5">
                    <TriangleAlert className="size-3.5 shrink-0 text-warning mt-0.5" aria-hidden="true" />
                    <div className="flex-1">
                        <strong className="text-xs font-semibold text-warning">Action Required</strong>
                        <p className="text-xs text-warning/80 mt-0.5">
                            {!hasPurchases && isNegativeBalance &&
                                'No purchase transactions found and balance is negative.'}
                            {!hasPurchases && !isNegativeBalance &&
                                'No purchase transactions found.'}
                            {hasPurchases && isNegativeBalance &&
                                `Balance is negative (${formatCurrency(currentBalanceValue, balanceCurrency)}).`}
                        </p>
                    </div>
                </div>
            )}

            {/* ── License header ────────────────────────────────── */}
            <div className="mx-3 mt-2 rounded-lg border border-border bg-card px-3 py-2.5 shadow-sm sm:mx-5 sm:px-4">
                <div className="grid grid-cols-1 items-start gap-2 lg:grid-cols-[minmax(0,1fr)_auto] lg:items-center">
                    <div>
                        <h4 className="mb-1.5 flex flex-wrap items-center gap-2 text-sm font-semibold text-foreground">
                            {String(ledger.license_number)}
                            <Badge
                                variant={isDFIA ? "default" : "info"}
                                className="px-1.5 py-0 text-[9px]"
                            >
                                {String(ledger.license_type)}
                            </Badge>
                        </h4>
                        <div className="grid grid-cols-1 gap-x-3 gap-y-0.5 text-xs sm:grid-cols-2 lg:grid-cols-3">
                            <div>
                                <span className="text-muted-foreground">Exporter:</span>
                                <strong className="ml-1">{normalizeText(ledger.exporter_name, 'N/A')}</strong>
                            </div>
                            <div>
                                <span className="text-muted-foreground">License Date:</span>
                                <strong className="ml-1">{formatDate(ledger.license_date)}</strong>
                            </div>
                            {isDFIA && (
                                <div>
                                    <span className="text-muted-foreground">SION:</span>
                                    <strong className="ml-1 text-info">
                                        {(() => {
                                            const allNorms = [...new Set(
                                                ledger.transactions
                                                    .filter(t => t.sion_norms)
                                                    .flatMap(t => String(t.sion_norms).split(', '))
                                            )];
                                            return allNorms.length > 0 ? allNorms.join(', ') : 'N/A';
                                        })()}
                                    </strong>
                                </div>
                            )}
                            <div>
                                <span className="text-muted-foreground">Expiry:</span>
                                <strong className="ml-1">{formatDate(ledger.expiry_date)}</strong>
                            </div>
                            <div>
                                <span className="text-muted-foreground">Total Value:</span>
                                <strong className="ml-1 text-primary">
                                    {formatCurrency(ledger.totals?.total_purchases, balanceCurrency)}
                                </strong>
                            </div>
                        </div>
                    </div>

                    {/* Balance panel */}
                    <div className="rounded-md border border-border bg-muted/60 px-2.5 py-1.5 text-right">
                        <div className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
                            Balance
                        </div>
                        <div className={cn(
                            "text-lg font-bold tabular-nums",
                            currentBalance >= 0 ? "text-success" : "text-destructive",
                        )}>
                            {formatCurrency(currentBalanceValue, balanceCurrency)}
                        </div>
                    </div>
                </div>
            </div>

            {/* ── CA summary band ──────────────────────────────── */}
            <LedgerSummaryCards summary={summary} />

            {/* ── Ledger tables ─────────────────────────────────── */}
            {(() => {
                // THE DISPLAY RULE lives in `selectLedgerDisplayRows` — never
                // re-expressed here. `rows` is PURCHASE + SALE only (so the
                // synthetic OPENING row can no longer form a bogus "N/A"
                // company group); `openingRow` is the starting state, present
                // only when this licence has no purchase.
                const { rows, openingRow } = selectLedgerDisplayRows<CanonicalTransaction>(ledger);

                if (!rows.length && !openingRow) {
                    return (
                        <div className="mx-5 my-5 flex flex-col items-center gap-2 rounded-md border border-dashed border-border bg-card px-5 py-12 text-center">
                            <ScrollText className="size-8 text-muted-foreground" aria-hidden="true" />
                            <p className="text-sm font-semibold text-foreground">No transactions</p>
                            <p className="text-sm text-muted-foreground">
                                No ledger entries found for this license.
                            </p>
                        </div>
                    );
                }

                // Group ONLY the display rows by company (structure only)
                const companiesGrouped = groupTransactionsByCompany(rows);
                // Get company utilizations from canonical API (not recalculated)
                const companyUtilizations: Record<string, CompanyUtilization> = ledger.company_utilizations || {};

                const openingBlock = openingRow ? (
                    <div
                        data-testid="ledger-opening-state"
                        className={cn(
                            "mx-3 mt-2 overflow-hidden rounded-lg border border-border shadow-sm sm:mx-5",
                            companiesGrouped.length ? "mb-0" : "mb-2",
                        )}
                    >
                        {/* Starting state — deliberately NOT a company group header */}
                        <div className="flex flex-wrap items-center justify-between gap-1 border-b border-border bg-muted px-3 py-1.5">
                            <div className="flex items-center gap-2">
                                <Wallet className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
                                <span className="text-xs font-bold text-foreground">Opening Balance</span>
                            </div>
                            <span className="hidden text-xs text-muted-foreground lg:inline">
                                Starting state
                            </span>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full border-collapse bg-card text-xs">
                                <LedgerColumnHeader isDFIA={isDFIA} billCurrency={billCurrency} />
                                <tbody>
                                    <tr className="border-b border-border bg-muted/50">
                                        <td className="whitespace-nowrap px-2.5 py-1 text-muted-foreground">
                                            {formatDate(openingRow.date)}
                                        </td>
                                        <td className="px-2.5 py-1 font-medium text-foreground">Opening Balance</td>
                                        <td className="px-2.5 py-1 text-muted-foreground">-</td>
                                        <td className="px-2.5 py-1 text-foreground">
                                            <Badge variant="secondary" className="text-xs">{openingRow.type}</Badge>
                                        </td>
                                        {isDFIA && <td className="px-2.5 py-1 text-muted-foreground">-</td>}
                                        <td className="px-2.5 py-1 text-right font-semibold text-destructive">-</td>
                                        <td className="px-2.5 py-1 text-right font-semibold text-success">
                                            {formatCurrency(openingRow.purchase_amount, balanceCurrency)}
                                        </td>
                                        <td className="px-2.5 py-1 text-right text-muted-foreground">-</td>
                                        <td className="px-2.5 py-1 text-right text-muted-foreground">-</td>
                                    </tr>
                                </tbody>
                            </table>
                        </div>
                    </div>
                ) : null;

                const companyBlocks = companiesGrouped.map((company, ci) => {
                    const txns = company.transactions as CanonicalTransaction[];
                    // Get company balance from canonical API data
                    const companyUtilization = Object.values(companyUtilizations).find(
                        cu => cu.company_id === Number(company.company_id)
                    );
                    const companyBalance = companyUtilization ? toFiniteNumber(companyUtilization.utilization_balance) : 0;

                    const marginTop = ci === 0 && !openingBlock ? "mt-2" : "mt-1.5";
                    const marginBottom = ci === companiesGrouped.length - 1 ? "mb-2" : "mb-0";

                    return (
                        <div
                            key={company.company_id ?? ci}
                            data-testid="ledger-company-block"
                            className={cn(
                                "mx-3 overflow-hidden rounded-lg border border-border shadow-sm sm:mx-5",
                                marginTop, marginBottom,
                            )}
                        >
                            {/* Company header */}
                            <div className="flex flex-wrap items-center justify-between gap-1 bg-primary px-3 py-1.5 text-primary-foreground">
                                <div className="flex items-center gap-2">
                                    <Building2 className="size-3.5 shrink-0" aria-hidden="true" />
                                    <span data-testid="ledger-company-group" className="text-xs font-bold">
                                        {company.company_name}
                                    </span>
                                </div>
                                <div className="hidden text-xs text-primary-foreground/80 lg:block">
                                    Balance: <span className="font-semibold">{formatCurrency(companyBalance, balanceCurrency)}</span>
                                </div>
                            </div>

                            {/* Company ledger table */}
                            <div className="overflow-x-auto">
                                <table className="w-full border-collapse bg-card text-xs">
                                    <LedgerColumnHeader isDFIA={isDFIA} billCurrency={billCurrency} />
                                    <tbody>
                                        {txns.map((txn, ti) => {
                                            const isSale = txn.sale_amount != null;
                                            const isPurchase = txn.purchase_amount != null;
                                            const isCommission = txn.is_commission;

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
                                                    <td className="whitespace-nowrap px-2.5 py-1 text-xs text-muted-foreground">
                                                        {formatDate(txn.date)}
                                                    </td>
                                                    <td className="px-2.5 py-1 text-xs text-foreground">
                                                        {normalizeText(txn.party_name, '-')}
                                                    </td>
                                                    <InvoiceDocumentCell transaction={txn} />
                                                    <td className="px-2.5 py-1 text-foreground">
                                                        <Badge variant={isCommission ? "secondary" : "outline"} className="text-xs">
                                                            {txn.type}
                                                        </Badge>
                                                    </td>
                                                    {isDFIA && <LedgerItemsCell itemNames={txn.item_names} />}
                                                    <td className="px-2.5 py-1 text-right text-xs font-semibold text-destructive">
                                                        {formatCurrency(txn.sale_amount, balanceCurrency)}
                                                    </td>
                                                    <td className="px-2.5 py-1 text-right text-xs font-semibold text-success">
                                                        {formatCurrency(txn.purchase_amount, balanceCurrency)}
                                                    </td>
                                                    <td className="px-2.5 py-1 text-right text-xs tabular-nums text-destructive">
                                                        {formatCurrency(txn.sale_bill_amount, billCurrency)}
                                                    </td>
                                                    <td className="px-2.5 py-1 text-right text-xs tabular-nums text-success">
                                                        {formatCurrency(txn.purchase_bill_amount, billCurrency)}
                                                    </td>
                                                </tr>
                                            );
                                        })}
                                    </tbody>
                                </table>
                            </div>
                        </div>
                    );
                });

                return (
                    <>
                        {openingBlock}
                        {companyBlocks}
                    </>
                );
            })()}
        </div>
    );
}
