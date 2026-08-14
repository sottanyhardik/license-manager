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
    ArrowLeft, Building2, FileSpreadsheet, FileText, Loader2, Minus, ScrollText,
    TrendingDown, TrendingUp, TriangleAlert, Wallet,
} from "lucide-react";
import { isSaleRow, selectLedgerDisplayRows } from '@/utils/ledgerDisplayRows';
import StatCard from '@/components/StatCard';
import type {
    CanonicalLedgerResponse, CanonicalTransaction, CompanyUtilization, LedgerSummary, ProfitState,
} from '../types/canonicalLedger';

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

export function normalizeLedgerDetail(value: unknown): CanonicalLedgerResponse | null {
    if (!isRecord(value)) return null;

    // Validate required fields are present
    if (!value.license_number || !value.license_type) return null;

    // Canonical ledger response should provide all required fields. The double
    // assertion is required because `Record<string, unknown>` and the canonical
    // shape do not structurally overlap; the guard above is the runtime check.
    return value as unknown as CanonicalLedgerResponse;
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
            className="grid grid-cols-1 gap-3 px-5 pt-5 sm:grid-cols-2 xl:grid-cols-4"
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
    // Sale/Purchase render the LICENCE value (CIF FC for DFIA, INR otherwise), so
    // these headers must carry the same symbol their cells are formatted with.
    // They previously hardcoded "(₹)" while the cells rendered "$…" for DFIA —
    // the header contradicted the number beneath it.
    const licenceSuffix = isDFIA ? '($)' : '(₹)';
    // The BILL columns are a different quantity in a different currency (always
    // INR), so they get their own symbol from the backend's `bill_currency` —
    // never the licence suffix above.
    const billSuffix = billCurrency === 'USD' ? '($)' : '(₹)';
    return (
        <thead>
            <tr className="border-b-2 border-primary/20 bg-primary/8">
                <th scope="col" className="px-2.5 py-[7px] text-left font-bold text-foreground">Date</th>
                <th scope="col" className="px-2.5 py-[7px] text-left font-bold text-foreground">Particulars</th>
                <th scope="col" className="px-2.5 py-[7px] text-left font-bold text-foreground">Type</th>
                {/* Items is DFIA-only: incentive licences have no item link in
                    the data model, so the column would be permanently empty. */}
                {isDFIA && <th scope="col" className="px-2.5 py-[7px] text-left font-bold text-foreground">Items</th>}
                {/* Sale = SALE (consumes licence value), Purchase = PURCHASE
                    (adds it) — see `transaction_semantics.ledger_column_for`,
                    the single definition. Sale is listed first to match the
                    conventional reading order. */}
                <th scope="col" className="px-2.5 py-[7px] text-right font-bold text-destructive">Sale {licenceSuffix}</th>
                <th scope="col" className="px-2.5 py-[7px] text-right font-bold text-success">Purchase {licenceSuffix}</th>
                {/* Full-strength semantic colours (never a faded opacity) so the
                    bill columns keep WCAG AA contrast; the lighter FONT WEIGHT,
                    not a lower contrast, is what distinguishes them from the
                    licence-value columns above. */}
                <th scope="col" className="whitespace-nowrap px-2.5 py-[7px] text-right font-medium text-destructive">
                    Sale Bill {billSuffix}
                </th>
                <th scope="col" className="whitespace-nowrap px-2.5 py-[7px] text-right font-medium text-success">
                    Purchase Bill {billSuffix}
                </th>
                {/* NO per-row "License Balance" and NO "Status" column: this is a
                    transaction ledger, not a running-balance statement. A
                    per-row running balance printed a figure that double-counts a
                    purchased licence's acquisition, contradicting the Current
                    Balance card above. The balance is stated ONCE, in the
                    summary band. */}
            </tr>
        </thead>
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
        return <td className="px-2.5 py-[5px] text-muted-foreground">-</td>;
    }
    const [first, ...rest] = names;
    const fullList = names.join(', ');
    return (
        <td
            className="max-w-[220px] px-2.5 py-[5px] text-foreground"
            // `title` serves sighted mouse users; `aria-label` gives screen
            // readers the COMPLETE list rather than the truncated "Palm Oil +2",
            // so the collapsed items are not information available only on hover.
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
    const { id, companyId } = useParams();
    const navigate = useNavigate();
    const location = useLocation();
    const [ledger, setLedger] = useState<CanonicalLedgerResponse | null>(null);
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
    // NOTE: not a display decision — this drives the "Action Required" banner and
    // deliberately reads the COMPLETE financial collection (`transactions`),
    // opening row included. Which rows get rendered is decided further down by
    // `selectLedgerDisplayRows`.
    const hasPurchases = (ledger.transactions || []).some(
        t => t.type === 'PURCHASE' || t.type === 'OPENING',
    );
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

    // When the ledger was opened with a company filter (companyId in the URL),
    // include the company name in the filename so downloads are clearly scoped.
    const exportCompanyPart = companyId
        ? sanitizeLedgerFilenamePart((ledger.transactions[0] as CanonicalTransaction)?.company_name ?? String(companyId))
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
                                `Balance is negative (${formatCurrency(currentBalanceValue, balanceCurrency)}). Please add purchase transactions to cover the deficit.`}
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
                                <strong>{normalizeText(ledger.exporter_name, 'N/A')}</strong>
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
                                <span className="mr-2.5 text-muted-foreground">Expiry Date:</span>
                                <strong>{formatDate(ledger.expiry_date)}</strong>
                            </div>
                            <div>
                                <span className="mr-2.5 text-muted-foreground">Total Value:</span>
                                <strong className="text-primary">
                                    {/* The canonical contract has no `total_value`; reading it
                                        made this always render as 0. The legacy endpoint defined
                                        the field as total purchase CIF, which the canonical
                                        service already publishes as `totals.total_purchases`
                                        (Decimal, USD for DFIA / INR for incentive). */}
                                    {formatCurrency(ledger.totals?.total_purchases, balanceCurrency)}
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
                                {formatCurrency(currentBalanceValue, balanceCurrency)}
                            </div>
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
                            <p className="text-[13px] text-muted-foreground">
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
                            "mx-5 mt-5 overflow-hidden rounded-md border border-border shadow-md",
                            companiesGrouped.length ? "mb-0" : "mb-5",
                        )}
                    >
                        {/* Starting state — deliberately NOT a company group header */}
                        <div className="flex items-center justify-between border-b border-border bg-muted px-5 py-2.5">
                            <div className="flex items-center gap-2">
                                <Wallet className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                                <span className="text-[15px] font-bold text-foreground">Opening Balance</span>
                            </div>
                            <span className="text-[13px] text-muted-foreground">
                                Starting state — carried forward, not a transaction
                            </span>
                        </div>
                        <div className="overflow-x-auto">
                            <table className="w-full border-collapse bg-card text-[0.82rem]">
                                <LedgerColumnHeader isDFIA={isDFIA} billCurrency={billCurrency} />
                                <tbody>
                                    <tr className="border-b border-border bg-muted/50">
                                        <td className="whitespace-nowrap px-2.5 py-[5px] text-muted-foreground">
                                            {formatDate(openingRow.date)}
                                        </td>
                                        {/* A carried-forward state, not a trade: no counterparty,
                                            no invoice, no billed item. All three stay blank. */}
                                        <td className="px-2.5 py-[5px] font-medium text-foreground">Opening Balance</td>
                                        <td className="px-2.5 py-[5px] text-foreground">
                                            <Badge variant="secondary" className="text-[11px]">{openingRow.type}</Badge>
                                        </td>
                                        {isDFIA && <td className="px-2.5 py-[5px] text-muted-foreground">-</td>}
                                        {/* An opening balance ADDS licence value, exactly
                                            like a purchase, so it occupies the Purchase
                                            column — and is already counted in
                                            `summary.total_purchase`. */}
                                        <td className="px-2.5 py-[5px] text-right font-semibold text-destructive">-</td>
                                        <td className="px-2.5 py-[5px] text-right font-semibold text-success">
                                            {formatCurrency(openingRow.amount, balanceCurrency)}
                                        </td>
                                        <td className="px-2.5 py-[5px] text-right text-muted-foreground">-</td>
                                        <td className="px-2.5 py-[5px] text-right text-muted-foreground">-</td>
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

                    const marginTop = ci === 0 && !openingBlock ? "mt-5" : "mt-3";
                    const marginBottom = ci === companiesGrouped.length - 1 ? "mb-5" : "mb-0";

                    return (
                        <div
                            key={company.company_id ?? ci}
                            data-testid="ledger-company-block"
                            className={cn(
                                "mx-5 overflow-hidden rounded-md border border-border shadow-md",
                                marginTop, marginBottom,
                            )}
                        >
                            {/* Company header */}
                            <div className="flex items-center justify-between bg-primary px-5 py-2.5 text-primary-foreground">
                                <div className="flex items-center gap-2">
                                    <Building2 className="size-4 shrink-0" aria-hidden="true" />
                                    <span data-testid="ledger-company-group" className="text-[15px] font-bold">
                                        {company.company_name}
                                    </span>
                                </div>
                                <div className="text-[13px] text-primary-foreground/80">
                                    Company Balance: <span className="font-semibold">{formatCurrency(companyBalance, balanceCurrency)}</span>
                                </div>
                            </div>

                            {/* Company ledger table */}
                            <div className="overflow-x-auto">
                                <table className="w-full border-collapse bg-card text-[0.82rem]">
                                    <LedgerColumnHeader isDFIA={isDFIA} billCurrency={billCurrency} />
                                    <tbody>
                                        {txns.map((txn, ti) => {
                                            // `txns` is PURCHASE + SALE only (display rule), so the
                                            // amount lands in the credit column for sales and the
                                            // debit column for everything else.
                                            const isSale = isSaleRow(txn);
                                            const isPurchase = !isSale;
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
                                                    <td className="whitespace-nowrap px-2.5 py-[5px] text-muted-foreground">
                                                        {formatDate(txn.date)}
                                                    </td>
                                                    {/* Particulars = the COUNTERPARTY, not us. The
                                                        group header above already names our company;
                                                        `company_name` here would just echo it. '-'
                                                        when the party relation is genuinely absent —
                                                        never substituted with our own company. */}
                                                    <td className="px-2.5 py-[5px] text-foreground">
                                                        {normalizeText(txn.party_name, '-')}
                                                    </td>
                                                    <td className="px-2.5 py-[5px] text-foreground">
                                                        <Badge variant={isCommission ? "secondary" : "outline"} className="text-[11px]">
                                                            {txn.type}
                                                        </Badge>
                                                    </td>
                                                    {isDFIA && <LedgerItemsCell itemNames={txn.item_names} />}
                                                    {/* Licence value (USD for DFIA) — NOT the bill.
                                                        SALE → Debit (consumes licence value),
                                                        PURCHASE → Credit (adds it). Both render
                                                        `amount` as-is: the canonical service emits it
                                                        as a positive magnitude and encodes direction
                                                        in `type`, so neither side needs a sign flip. */}
                                                    <td className="px-2.5 py-[5px] text-right font-semibold text-destructive">
                                                        {isSale ? formatCurrency(txn.amount, balanceCurrency) : '-'}
                                                    </td>
                                                    <td className="px-2.5 py-[5px] text-right font-semibold text-success">
                                                        {isPurchase ? formatCurrency(txn.amount, balanceCurrency) : '-'}
                                                    </td>
                                                    {/* Bill columns: the INVOICED amount, in INR — a
                                                        different quantity and currency from the two
                                                        columns above. Never assumed equal to them.
                                                        Each bill sits under the SAME column as its own
                                                        licence value, so a sale's bill is a Sale Bill
                                                        and a purchase's bill is a Purchase Bill. */}
                                                    <td className="px-2.5 py-[5px] text-right tabular-nums text-destructive">
                                                        {isSale ? formatCurrency(txn.bill_amount, billCurrency) : '-'}
                                                    </td>
                                                    <td className="px-2.5 py-[5px] text-right tabular-nums text-success">
                                                        {isPurchase ? formatCurrency(txn.bill_amount, billCurrency) : '-'}
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
