import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from "sonner";
import api from '../api/axios';
import { formatIndianNumber } from '../utils/numberFormatter';
import {
    downloadLicenseLedgerExcel, licenseLedgerExportError, previewLicenseLedgerPdf,
} from '../services/licenseLedgerExport';
import PageHeader from '@/components/PageHeader';
import EmptyState from '@/components/EmptyState';
import AsyncSelectField from '../components/AsyncSelectField';
import DebouncedSearchInput from '../components/DebouncedSearchInput';
import DateRangeFilter from '@/components/DateRangeFilter';
import { getCurrentFinancialYearRange, getPreviousFinancialYearRange } from '../utils/dateRangePresets';
import { buildLicenseLedgerParams, defaultLicenseLedgerFilters, type LicenseLedgerFilters } from './licenseLedgerFilters';
import { normalizeLicenseWiseData, type LicenseWiseData } from './licenseLedgerData';
import { cn } from '@/lib/utils';
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import {
    ArrowDownCircle, ArrowUpCircle, BookOpen, Building2, Calendar,
    BadgeCheck, CalendarCheck, CalendarRange, FileSpreadsheet, FileText, Filter,
    Globe, Inbox, Loader2, Trophy, XCircle,
} from "lucide-react";

// ─── Types ─────────────────────────────────────────────────────────────────────


// ─── Pure utilities ────────────────────────────────────────────────────────────

function isRecord(value: unknown): value is Record<string, unknown> {
    return typeof value === 'object' && value !== null;
}

function normalizeText(value: unknown, fallback = ''): string {
    const normalized = String(value ?? '').trim();
    return normalized || fallback;
}

function getApiErrorMessage(error: unknown, fallback: string): string {
    if (isRecord(error) && isRecord(error.response) && isRecord(error.response.data)) {
        const message = error.response.data.error ?? error.response.data.detail ?? error.response.data.message;
        if (message) return normalizeText(message, fallback);
    }
    if (error instanceof Error) return normalizeText(error.message, fallback);
    return fallback;
}

// ─── LicenseWiseLedger sub-component ─────────────────────────────────────────

function TransactionLedger({ data, navigate }: { data: LicenseWiseData; navigate: ReturnType<typeof useNavigate> }) {
    const { licenses } = normalizeLicenseWiseData(data);
    const fmtInr = (value: number) => `₹${formatIndianNumber(value, 2)}`;
    const fmtFc = (value: number) => formatIndianNumber(value, 2);

    if (licenses.length === 0) {
        return <EmptyState icon={Inbox} title="No transactions found" description="No purchase or sale transactions match the current filters" />;
    }

    return (
        <div className="space-y-5 p-3" data-testid="transaction-ledger">
            {licenses.map((license) => (
                <section key={license.license_id} className="overflow-hidden rounded-md border border-border" aria-label={`Transactions for license ${license.license_number}`}>
                    <div className="flex flex-wrap items-center gap-x-5 gap-y-1 bg-primary px-4 py-2.5 text-primary-foreground">
                        <span className="font-bold">License {license.license_number}</span>
                        <span className="text-xs text-primary-foreground/80">{license.license_type}</span>
                        <span className="text-xs text-primary-foreground/80">License date: {license.license_date}</span>
                        {license.sion_norms && <span className="text-xs text-primary-foreground/80">SION: {license.sion_norms}</span>}
                        {license.transactions[0] && (
                            <button type="button" onClick={() => navigate(`/license-ledger/${license.license_id}`)} className="ml-auto text-xs font-semibold underline underline-offset-2">View details</button>
                        )}
                    </div>
                    <div className="overflow-x-auto">
                        <table className="w-full min-w-[1200px] border-collapse text-xs">
                            <thead>
                                <tr className="border-b bg-muted/70 text-left text-muted-foreground">
                                    <th className="px-3 py-2 font-semibold">Company</th><th className="px-3 py-2 font-semibold">SION</th>
                                    <th className="px-3 py-2 font-semibold">Date</th><th className="px-3 py-2 font-semibold">Counterparty</th>
                                    <th className="px-3 py-2 font-semibold">Invoice</th><th className="px-3 py-2 font-semibold">Transaction</th>
                                    <th className="px-3 py-2 font-semibold">Product</th><th className="px-3 py-2 text-right font-semibold">FC Amount</th>
                                    <th className="px-3 py-2 text-right font-semibold">INR Amount</th>
                                </tr>
                            </thead>
                            <tbody>
                                {license.transactions.map((transaction) => {
                                    const isPurchase = transaction.transaction_type === 'PURCHASE';
                                    return <tr key={`${transaction.transaction_type}-${transaction.trade_id}`} className={cn("border-b last:border-b-0", isPurchase ? "bg-success/[0.06]" : "bg-info/[0.06]")}>
                                        <td className="px-3 py-2 font-medium">{transaction.company_name}</td>
                                        <td className="px-3 py-2">{transaction.sion_norms || license.sion_norms || '—'}</td>
                                        <td className="px-3 py-2 whitespace-nowrap">{transaction.invoice_date}</td>
                                        <td className="px-3 py-2">{transaction.party_name}</td>
                                        <td className="px-3 py-2 font-medium">{transaction.invoice_number}</td>
                                        <td className="px-3 py-2"><Badge variant={isPurchase ? 'default' : 'info'} className={cn("text-[10px]", isPurchase && "bg-success hover:bg-success")}>{transaction.transaction_type}</Badge></td>
                                        <td className="px-3 py-2">{transaction.item_names.join(', ') || '—'}</td>
                                        <td className="px-3 py-2 text-right tabular-nums">{fmtFc(transaction.amount)}</td>
                                        <td className="px-3 py-2 text-right font-medium tabular-nums">{fmtInr(transaction.bill_amount)}</td>
                                    </tr>;
                                })}
                                <tr className="border-t-2 border-primary bg-primary/5 font-bold">
                                    <td colSpan={6} className="px-3 py-2 uppercase">License Total</td>
                                    <td className="px-3 py-2 text-muted-foreground">Purchase / Sale</td>
                                    <td className="px-3 py-2 text-right tabular-nums">{fmtFc(license.purchase_total)} / {fmtFc(license.sale_total)}</td>
                                    <td className={cn("px-3 py-2 text-right tabular-nums", license.profit_loss >= 0 ? "text-success" : "text-destructive")}>
                                        {fmtInr(license.purchase_bill_total)} / {fmtInr(license.sale_bill_total)} · Balance {fmtFc(license.current_balance)}
                                    </td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </section>
            ))}
        </div>
    );
}

function LicenseWiseLedger({
    data,
    navigate,
}: {
    data: LicenseWiseData;
    navigate: ReturnType<typeof useNavigate>;
}) {
    const { licenses, company_groups = [], grand_total } = normalizeLicenseWiseData(data);
    const fmt = (v: number) => `₹${formatIndianNumber(v, 2)}`;

    if (company_groups.length > 0) {
        return (
            <div className="space-y-5 p-3" data-testid="company-sion-ledger">
                {company_groups.map((company) => (
                    <section key={company.company_id} aria-label={`Company ${company.company_name}`} className="overflow-hidden rounded-md border border-border">
                        <h2 className="flex items-center gap-2 bg-primary px-4 py-3 text-sm font-bold text-primary-foreground">
                            <Building2 className="size-4" aria-hidden="true" />{company.company_name}
                        </h2>
                        <div className="space-y-4 p-3">
                            {company.sion_groups.map((sion) => (
                                <section key={sion.sion_norm || '__empty__'} aria-label={`SION ${sion.label}`} className="overflow-hidden rounded border border-border">
                                    <div className="flex flex-wrap items-center gap-x-5 gap-y-1 bg-muted px-3 py-2">
                                        <h3 className="text-sm font-bold text-foreground">SION: {sion.label}</h3>
                                        <span className="text-xs text-muted-foreground">{sion.license_count} license{sion.license_count === 1 ? '' : 's'}</span>
                                        <span className="ml-auto text-xs tabular-nums">Purchase {fmt(sion.total_purchase_bill_inr)}</span>
                                        <span className="text-xs tabular-nums">Sale {fmt(sion.total_sale_bill_inr)}</span>
                                        <span className={cn("text-xs font-semibold tabular-nums", sion.total_profit_loss_inr >= 0 ? "text-success" : "text-destructive")}>P/L {fmt(sion.total_profit_loss_inr)}</span>
                                    </div>
                                    <div className="overflow-x-auto">
                                        <table className="w-full min-w-[900px] border-collapse text-xs">
                                            <thead><tr className="border-y bg-primary/5 text-left">
                                                <th className="px-3 py-2">License Number</th><th className="px-3 py-2">Type</th>
                                                <th className="px-3 py-2">Date</th><th className="px-3 py-2">1st Purchase Date</th>
                                                <th className="px-3 py-2 text-right">Balance</th><th className="px-3 py-2 text-right">Purchase (₹)</th>
                                                <th className="px-3 py-2 text-right">Sale (₹)</th><th className="px-3 py-2 text-right">P/L (₹)</th><th className="px-3 py-2" />
                                            </tr></thead>
                                            <tbody>{sion.licenses.map((license) => (
                                                <tr key={license.license_id} className={cn("border-b last:border-b-0", !license.has_purchase_bill && "bg-destructive/10 text-destructive")}>
                                                    <td className="px-3 py-2 font-semibold">{license.license_number}{!license.has_purchase_bill && <span className="ml-2 rounded bg-destructive px-1.5 py-0.5 text-[10px] font-bold text-destructive-foreground">NO PURCHASE BILL</span>}</td><td className="px-3 py-2">{license.license_type}</td>
                                                    <td className="px-3 py-2">{license.license_date}</td><td className="px-3 py-2">{license.first_purchase_date}</td>
                                                    <td className="px-3 py-2 text-right tabular-nums">{formatIndianNumber(license.current_balance, 2)}</td>
                                                    <td className="px-3 py-2 text-right tabular-nums">{fmt(license.purchase_bill_inr)}</td>
                                                    <td className="px-3 py-2 text-right tabular-nums">{fmt(license.sale_bill_inr)}</td>
                                                    <td className={cn("px-3 py-2 text-right font-semibold tabular-nums", license.profit_loss_inr >= 0 ? "text-success" : "text-destructive")}>{fmt(license.profit_loss_inr)}</td>
                                                    <td className="px-3 py-2 text-right">
                                                        <button
                                                            type="button"
                                                            className="font-semibold text-primary hover:underline"
                                                            onClick={() => navigate(`/license-ledger/${license.license_id}/${company.company_id}`)}
                                                        >
                                                            View Ledger
                                                        </button>
                                                    </td>
                                                </tr>
                                            ))}</tbody>
                                        </table>
                                    </div>
                                </section>
                            ))}
                            <div className="flex flex-wrap justify-end gap-5 border-t-2 border-primary px-3 pt-2 text-xs font-bold">
                                <span>Company Total — {company.company_name}</span><span>Purchase {fmt(company.total_purchase_bill_inr)}</span>
                                <span>Sale {fmt(company.total_sale_bill_inr)}</span><span>P/L {fmt(company.total_profit_loss_inr)}</span>
                            </div>
                        </div>
                    </section>
                ))}
                {grand_total && company_groups.length > 1 && (
                    <div className="flex flex-wrap justify-end gap-5 rounded-md bg-primary px-4 py-3 text-xs font-bold text-primary-foreground">
                        <span>Grand Total — {grand_total.license_count} licenses</span>
                        <span>Purchase {fmt(grand_total.total_purchase_bill_inr)}</span>
                        <span>Sale {fmt(grand_total.total_sale_bill_inr)}</span>
                        <span>P/L {fmt(grand_total.total_profit_loss_inr)}</span>
                    </div>
                )}
            </div>
        );
    }

    if (licenses.length === 0) {
        return (
            <EmptyState
                icon={Inbox}
                title="No trades found"
                description="No trades match the current filters"
            />
        );
    }

    return (
        <div className="p-2">
            {licenses.map((lic) => (
                <div key={lic.license_id} className="mb-6 overflow-hidden rounded-md border border-border">
                    {/* ── License header bar ─────────────────────────── */}
                    <div className="flex flex-wrap items-center gap-5 bg-primary px-4 py-2.5">
                        <span className="flex items-center gap-1.5 text-[15px] font-bold text-primary-foreground">
                            <FileText className="size-4 shrink-0" aria-hidden="true" />
                            <span className="ml-1">{lic.license_number}</span>
                        </span>
                        <span className="flex items-center gap-1.5 text-[12.5px] text-primary-foreground/70">
                            <Calendar className="size-4 shrink-0" aria-hidden="true" />
                            <span className="ml-1">{lic.license_date}</span>
                        </span>
                        <span className={cn(
                            "rounded-md px-2 py-0.5 text-[11px] font-bold text-white",
                            lic.license_type === 'DFIA' ? "bg-info/70" : "bg-white/20",
                        )}>
                            {lic.license_type}
                        </span>
                        {lic.companies[0]?.company_id != null && (
                            <button
                                type="button"
                                onClick={() => navigate(`/license-ledger/${lic.license_id}/${lic.companies[0].company_id}`)}
                                aria-label={`View ledger for ${lic.license_number}`}
                                className="ml-auto flex cursor-pointer items-center gap-1.5 rounded-md border border-white/30 bg-white/15 px-2.5 py-1 text-[12px] font-semibold text-white transition-colors hover:bg-white/25"
                            >
                                <BookOpen className="size-4" aria-hidden="true" />View Ledger
                            </button>
                        )}
                    </div>

                    {/* ── Companies table ────────────────────────────── */}
                    <div className="overflow-x-auto" role="region" aria-label={`Companies for ${lic.license_number}`} tabIndex={0}>
                    <table className="min-w-[680px] w-full border-collapse text-[12.5px]">
                        <thead>
                            <tr className="border-b-2 border-border bg-muted/50">
                                <th scope="col" className="w-[30%] px-3 py-[7px] text-left font-bold text-foreground">Company</th>
                                <th scope="col" className="w-[15%] px-3 py-[7px] text-left font-bold text-foreground">Type</th>
                                <th scope="col" className="w-[15%] px-3 py-[7px] text-left font-bold text-foreground">Date</th>
                                <th scope="col" className="w-[20%] px-3 py-[7px] text-right font-bold text-success">Purchase (₹)</th>
                                <th scope="col" className="w-[20%] px-3 py-[7px] text-right font-bold text-destructive">Sale (₹)</th>
                            </tr>
                        </thead>
                        <tbody>
                            {lic.companies.map((company, ci) => (
                                <React.Fragment key={company.company_id}>
                                    {/* Company grouping header */}
                                    <tr className={cn(
                                        ci > 0 ? "border-t-2 border-border" : "",
                                        ci % 2 === 0 ? "bg-primary/5" : "bg-muted/40",
                                    )}>
                                        <td colSpan={5} className="px-3 py-[5px] text-[0.82rem] font-bold text-foreground">
                                            <span className="flex items-center gap-1.5">
                                                <Building2 className="size-4 shrink-0" aria-hidden="true" />
                                                <span className="ml-1">{company.company_name}</span>
                                            </span>
                                        </td>
                                    </tr>

                                    {/* Purchase rows */}
                                    {company.purchases.map((row) => (
                                        <tr key={`p-${row.trade_id}`} className="border-b border-success/20 bg-success/[0.06]">
                                            <td className="px-3 py-[4px] pl-6">
                                                <span className="flex items-center gap-1.5 text-foreground">
                                                    <ArrowDownCircle className="size-4 shrink-0" aria-hidden="true" /><span className="ml-1">Purchase</span>
                                                </span>
                                            </td>
                                            <td className="px-3 py-[4px] text-muted-foreground">{lic.license_type}</td>
                                            <td className="px-3 py-[4px] text-muted-foreground">{row.invoice_date}</td>
                                            <td className="px-3 py-[4px] text-right font-semibold text-success">{fmt(row.amount)}</td>
                                            <td className="px-3 py-[4px]" />
                                        </tr>
                                    ))}

                                    {/* Sale rows */}
                                    {company.sales.map((row) => (
                                        <tr key={`s-${row.trade_id}`} className="border-b border-destructive/20 bg-destructive/[0.06]">
                                            <td className="px-3 py-[4px] pl-6">
                                                <span className="flex items-center gap-1.5 text-foreground">
                                                    <ArrowUpCircle className="size-4 shrink-0" aria-hidden="true" /><span className="ml-1">Sale</span>
                                                </span>
                                            </td>
                                            <td className="px-3 py-[4px] text-muted-foreground">{lic.license_type}</td>
                                            <td className="px-3 py-[4px] text-muted-foreground">{row.invoice_date}</td>
                                            <td className="px-3 py-[4px]" />
                                            <td className="px-3 py-[4px] text-right font-semibold text-destructive">{fmt(row.amount)}</td>
                                        </tr>
                                    ))}

                                    {/* Company total row */}
                                    <tr className="bg-primary font-bold text-primary-foreground">
                                        <td colSpan={3} className="px-3 py-[5px] text-right text-[12px]">
                                            Total — {company.company_name}
                                        </td>
                                        <td className="px-3 py-[5px] text-right text-emerald-300">
                                            {fmt(company.purchase_total)}
                                        </td>
                                        <td className="px-3 py-[5px] text-right text-red-300">
                                            {fmt(company.sale_total)}
                                            <span className={cn(
                                                "ml-2 text-[11px]",
                                                company.profit_loss >= 0 ? "text-emerald-300" : "text-red-300",
                                            )}>
                                                P/L: {company.profit_loss >= 0 ? '+' : ''}{fmt(company.profit_loss)}
                                            </span>
                                        </td>
                                    </tr>
                                </React.Fragment>
                            ))}
                        </tbody>
                    </table>
                    </div>
                </div>
            ))}
        </div>
    );
}

// ─── Summary stat item ─────────────────────────────────────────────────────────

function SummaryItem({ label, value, tone }: { label: string; value: string; tone?: "primary" | "success" | "warning" | "danger" }) {
    const toneClass = {
        primary: "text-primary",
        success: "text-success",
        warning: "text-warning",
        danger: "text-destructive",
    }[tone ?? "primary"] ?? "text-foreground";
    return (
        <div className="py-2 text-center">
            <div className="text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">{label}</div>
            <div className={cn("text-sm font-bold tabular-nums", toneClass)}>{value}</div>
        </div>
    );
}

// ─── Main component ────────────────────────────────────────────────────────────

export default function LicenseLedger() {
    const navigate = useNavigate();
    const [summary, setSummary] = useState<Record<string, Record<string, number>> | null>(null);
    const [companyWiseData, setCompanyWiseData] = useState<LicenseWiseData | null>(null);
    const [companyWiseLoading, setCompanyWiseLoading] = useState(false);
    const [exporting, setExporting] = useState<'pdf' | 'xlsx' | null>(null);
    const [filters, setFilters] = useState<LicenseLedgerFilters>(() => defaultLicenseLedgerFilters());
    const requestVersion = useRef(0);
    const params = buildLicenseLedgerParams(filters);
    const paramsKey = params.toString();

    useEffect(() => {
        const version = ++requestVersion.current;
        setCompanyWiseLoading(true);
        Promise.all([
            api.get(`license-ledger/license-wise/?${paramsKey}`),
            api.get(`license-ledger/summary/?${paramsKey}`),
        ]).then(async ([ledgerResponse, summaryResponse]) => {
            if (version !== requestVersion.current) return;
            const rawLedger = ledgerResponse.data;
            const rawLicenses = isRecord(rawLedger) && Array.isArray(rawLedger.licenses) ? rawLedger.licenses : [];
            // A server that has not yet reloaded may still return the legacy
            // company-only collection payload. Its detail endpoint contains
            // the full canonical rows, so enrich only those affected licenses.
            const details = await Promise.allSettled(rawLicenses.flatMap((license) => {
                if (!isRecord(license) || license.license_id == null || (Array.isArray(license.transactions) && license.transactions.length > 0)) return [];
                const licenseType = encodeURIComponent(normalizeText(license.license_type, 'AUTO'));
                return [api.get(`license-ledger/${encodeURIComponent(String(license.license_id))}/?license_type=${licenseType}`)];
            }));
            if (version !== requestVersion.current) return;
            const detailByLicense = new Map(details.flatMap((result) => {
                if (result.status !== 'fulfilled' || !isRecord(result.value.data) || result.value.data.license_id == null) return [];
                return [[String(result.value.data.license_id), result.value.data] as const];
            }));
            const enrichedLedger = isRecord(rawLedger) ? {
                ...rawLedger,
                licenses: rawLicenses.map((license) => {
                    if (!isRecord(license)) return license;
                    const detail = detailByLicense.get(String(license.license_id));
                    if (!detail) return license;
                    return {
                        ...license,
                        transactions: Array.isArray(detail.display_transactions) ? detail.display_transactions : detail.transactions,
                        summary: detail.summary,
                        sion_norms: license.sion_norms ?? detail.sion_norms,
                    };
                }),
            } : rawLedger;
            setCompanyWiseData(normalizeLicenseWiseData(enrichedLedger));
            setSummary(summaryResponse.data);
        }).catch(error => {
            if (version !== requestVersion.current) return;
            toast.error(getApiErrorMessage(error, 'Failed to load License Ledger.'));
            setCompanyWiseData(null);
        }).finally(() => {
            if (version === requestVersion.current) setCompanyWiseLoading(false);
        });
    }, [paramsKey]);

    const updateFilter = <K extends keyof LicenseLedgerFilters>(key: K, value: LicenseLedgerFilters[K]) =>
        setFilters(previous => ({ ...previous, [key]: value }));

    const clearCompany = () => updateFilter('company', null);
    const clearPurchaseDates = () => setFilters(previous => ({
        ...previous, purchaseDateFrom: '', purchaseDateTo: '',
    }));
    const clearAllFilters = () => setFilters(defaultLicenseLedgerFilters());

    const runExport = async (format: 'pdf' | 'xlsx') => {
        if (exporting) return;
        setExporting(format);
        try {
            const scope = { params: new URLSearchParams(paramsKey) };
            if (format === 'pdf') await previewLicenseLedgerPdf(scope);
            else await downloadLicenseLedgerExcel(scope);
        } catch (error) {
            toast.error(licenseLedgerExportError(error, `Failed to generate ${format === 'pdf' ? 'PDF' : 'Excel'}.`));
        } finally {
            setExporting(null);
        }
    };

    const normalizedLedger = normalizeLicenseWiseData(companyWiseData);
    const visibleLicenses = normalizedLedger.licenses;
    const visibleLicenseCount = normalizedLedger.company_groups?.reduce(
        (count, company) => count + company.sion_groups.reduce((subtotal, group) => subtotal + group.licenses.length, 0), 0,
    ) ?? visibleLicenses.length;

    return (
        <>
            {/* ── Header ─────────────────────────────────────────── */}
            <PageHeader
                pretitle="Ledger"
                title="License Ledger"
                description="Track available balance for DFIA and Incentive licenses"
                actions={<div className="flex gap-2">
                    <Button variant="outline" size="sm" disabled={exporting !== null || visibleLicenseCount === 0} onClick={() => runExport('pdf')}>
                        {exporting === 'pdf' ? <Loader2 className="size-3.5 animate-spin" /> : <FileText className="size-3.5" />}Preview PDF
                    </Button>
                    <Button variant="outline" size="sm" disabled={exporting !== null || visibleLicenseCount === 0} onClick={() => runExport('xlsx')}>
                        {exporting === 'xlsx' ? <Loader2 className="size-3.5 animate-spin" /> : <FileSpreadsheet className="size-3.5" />}Download Excel
                    </Button>
                </div>}
            />

            <Card className="mb-4">
                <CardHeader className="border-b px-3 py-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                        <span className="flex items-center gap-2 text-sm font-semibold">
                            <Filter className="size-4" aria-hidden="true" /> Filters &amp; Search
                        </span>
                        <div className="flex gap-2">
                            <Button type="button" size="sm" variant="outline" onClick={clearCompany} disabled={!filters.company}>
                                <Building2 className="size-4" aria-hidden="true" />Clear Company
                            </Button>
                            <Button type="button" size="sm" variant="outline" onClick={clearAllFilters}>
                                <XCircle className="size-4" aria-hidden="true" />Clear All
                            </Button>
                        </div>
                    </div>
                </CardHeader>
                <CardContent className="space-y-4 p-3">
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-6">
                        <div className="lg:col-span-2">
                            <label id="ledger-company-label" className="mb-1.5 block text-xs font-semibold text-muted-foreground">Company Filter</label>
                            <AsyncSelectField endpoint="masters/companies/" labelField="name" valueField="id"
                                value={filters.company} onChange={(value: LicenseLedgerFilters['company']) => updateFilter('company', value)}
                                placeholder="All companies..." loadOnMount ariaLabel="Company Filter" />
                        </div>
                        <div>
                            <label htmlFor="ledger-min-balance" className="mb-1.5 block text-xs font-semibold text-muted-foreground">Min Balance</label>
                            <Input id="ledger-min-balance" type="number" min="0" step="0.01" value={filters.minBalance}
                                onChange={(event) => updateFilter('minBalance', event.target.value)} placeholder="0.00" />
                        </div>
                        <div className="lg:col-span-2">
                            <label className="mb-1.5 block text-xs font-semibold text-muted-foreground">Search</label>
                            <DebouncedSearchInput value={filters.search} onChange={(value: string) => updateFilter('search', value)}
                                placeholder="License # or exporter..." />
                        </div>
                        <div>
                            <label htmlFor="ledger-sort" className="mb-1.5 block text-xs font-semibold text-muted-foreground">Sort By</label>
                            <select id="ledger-sort" value={filters.ordering} onChange={(event) => updateFilter('ordering', event.target.value)}
                                className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm">
                                <option value="-license_date">Latest First</option>
                                <option value="license_date">Oldest First</option>
                                <option value="-balance_value">Highest Balance</option>
                                <option value="balance_value">Lowest Balance</option>
                            </select>
                        </div>
                    </div>

                    <div>
                        <label htmlFor="ledger-license-numbers" className="mb-1.5 block text-xs font-semibold text-muted-foreground">License Numbers</label>
                        <Input id="ledger-license-numbers" value={filters.licenseNumbers}
                            onChange={(event) => updateFilter('licenseNumbers', event.target.value)}
                            placeholder="Paste comma-separated license numbers, e.g. 3111004973, 3111004966" />
                        <p className="mt-1 text-[11px] text-muted-foreground">Shows only the listed licenses; spaces and duplicate numbers are ignored.</p>
                    </div>

                    <div>
                        <label htmlFor="ledger-exclude-license-numbers" className="mb-1.5 block text-xs font-semibold text-muted-foreground">Exclude License Numbers</label>
                        <Input id="ledger-exclude-license-numbers" value={filters.excludeLicenseNumbers}
                            onChange={(event) => updateFilter('excludeLicenseNumbers', event.target.value)}
                            placeholder="Paste comma-separated license numbers to exclude" />
                        <p className="mt-1 text-[11px] text-muted-foreground">Hides the listed licenses; spaces and duplicate numbers are ignored.</p>
                    </div>

                    <div className="grid grid-cols-1 gap-3 lg:grid-cols-4">
                        <div>
                            <label htmlFor="ledger-license-type" className="mb-1.5 block text-xs font-semibold text-muted-foreground">License Type</label>
                            <Select value={filters.licenseType} onValueChange={(value) => updateFilter('licenseType', value)}>
                                <SelectTrigger id="ledger-license-type" aria-label="License Type">
                                    <SelectValue placeholder="All Licenses" />
                                </SelectTrigger>
                                <SelectContent>
                                    <SelectItem value="ALL">All Licenses</SelectItem>
                                    <SelectItem value="DFIA">DFIA</SelectItem>
                                    <SelectItem value="ALL_INCENTIVE">All Incentive</SelectItem>
                                    <SelectItem value="RODTEP">RODTEP</SelectItem>
                                    <SelectItem value="ROSTL">ROSTL</SelectItem>
                                    <SelectItem value="MEIS">MEIS</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                        <div>
                            <label id="ledger-norm-label" className="mb-1.5 block text-xs font-semibold text-muted-foreground">Norm</label>
                            <AsyncSelectField endpoint="masters/sion-classes/?is_active=true" labelField="norm_class" valueField="norm_class"
                                value={filters.norm} onChange={(value: LicenseLedgerFilters['norm']) => updateFilter('norm', value)}
                                placeholder="All norms..." ariaLabel="Norm" />
                            <p className="mt-1 text-[11px] text-muted-foreground">DFIA only — hides Incentive licenses</p>
                        </div>
                        <div>
                            <label id="ledger-purchase-status-label" className="mb-1.5 block text-xs font-semibold text-muted-foreground">Purchase Status</label>
                            <AsyncSelectField endpoint="masters/purchase-statuses/?is_active=true" labelField="label" valueField="code"
                                value={filters.purchaseStatus} onChange={(value: LicenseLedgerFilters['purchaseStatus']) => updateFilter('purchaseStatus', value)}
                                placeholder="All statuses..." ariaLabel="Purchase Status" />
                            <p className="mt-1 text-[11px] text-muted-foreground">DFIA only — hides Incentive licenses</p>
                        </div>
                        <div className="flex items-center gap-2 pt-5">
                            <Switch id="ledger-active-only" checked={filters.activeOnly} onCheckedChange={(value) => updateFilter('activeOnly', value)} />
                            <label htmlFor="ledger-active-only" className="text-sm font-medium">Active Only</label>
                        </div>
                    </div>

                    <fieldset>
                        <legend className="mb-1.5 text-xs font-semibold text-muted-foreground">Purchase Bill Status</legend>
                        <div className="flex flex-wrap gap-1">
                            {[
                                ['ALL', 'All'], ['WITH_PURCHASE_BILL', 'With Purchase Bill'], ['NO_PURCHASE_BILL', 'No Purchase Bill'],
                            ].map(([value, label]) => (
                                <Button key={value} type="button" size="sm" variant={filters.purchaseBill === value ? 'default' : 'outline'}
                                    onClick={() => updateFilter('purchaseBill', value)}>{label}</Button>
                            ))}
                        </div>
                    </fieldset>

                    <div className="border-t border-border pt-3">
                        <DateRangeFilter label="Purchase Date Range" icon={CalendarRange} hint="(Defaults to current FY: Apr–Mar)"
                            fromId="ledger-purchase-from" toId="ledger-purchase-to"
                            fromValue={filters.purchaseDateFrom} toValue={filters.purchaseDateTo}
                            onFromChange={(value) => updateFilter('purchaseDateFrom', value)}
                            onToChange={(value) => updateFilter('purchaseDateTo', value)}
                            onClear={clearPurchaseDates}
                            presets={[
                                { label: 'Current FY', icon: CalendarCheck, range: getCurrentFinancialYearRange },
                                { label: 'Previous FY', icon: Calendar, range: getPreviousFinancialYearRange },
                            ]} />
                    </div>
                </CardContent>
            </Card>

            {/* ── Summary cards ──────────────────────────────────── */}
            {summary && (
                <div className="mb-4 grid grid-cols-1 gap-3 lg:grid-cols-2">
                    {/* DFIA card */}
                    <Card className="border-l-[3px] border-l-primary">
                        <CardHeader className="border-b py-2 px-3">
                            <div className="flex items-center gap-2">
                                <Globe className="size-4 text-muted-foreground" aria-hidden="true" />
                                <span className="text-[13px] font-semibold">DFIA Licenses</span>
                                <Badge variant="default" className="ml-auto text-[10.5px]">
                                    {summary.dfia?.total_licenses} active
                                </Badge>
                            </div>
                        </CardHeader>
                        <CardContent className="px-3 py-2">
                            <div className="grid grid-cols-2 divide-x divide-y divide-border text-center sm:grid-cols-4 sm:divide-y-0">
                                <SummaryItem label="Total Value" value={`$ ${formatIndianNumber(summary.dfia?.total_value_usd, 2)}`} tone="primary" />
                                <SummaryItem label="Balance" value={`$ ${formatIndianNumber(summary.dfia?.balance_value_usd, 2)}`} tone="success" />
                                <SummaryItem label="Purchase" value={`₹${formatIndianNumber(summary.dfia?.purchase_amount_inr, 0)}`} tone="warning" />
                                <SummaryItem
                                    label="P / L"
                                    value={`${summary.dfia?.profit_loss_inr >= 0 ? '+' : ''}₹${formatIndianNumber(Math.abs(summary.dfia?.profit_loss_inr), 0)}`}
                                    tone={summary.dfia?.profit_loss_inr >= 0 ? "success" : "danger"}
                                />
                            </div>
                        </CardContent>
                    </Card>

                    {/* Incentive card */}
                    <Card className="border-l-[3px] border-l-info">
                        <CardHeader className="border-b py-2 px-3">
                            <div className="flex items-center gap-2">
                                <Trophy className="size-4 text-muted-foreground" aria-hidden="true" />
                                <span className="text-[13px] font-semibold">Incentive Licenses</span>
                                <Badge variant="info" className="ml-auto text-[10.5px]">
                                    {summary.incentive?.total_licenses} active
                                </Badge>
                            </div>
                        </CardHeader>
                        <CardContent className="px-3 py-2">
                            <div className="grid grid-cols-2 divide-x divide-y divide-border text-center sm:grid-cols-4 sm:divide-y-0">
                                <SummaryItem label="Total Value" value={`₹${formatIndianNumber(summary.incentive?.total_value_inr, 2)}`} tone="primary" />
                                <SummaryItem label="Balance" value={`₹${formatIndianNumber(summary.incentive?.balance_value_inr, 2)}`} tone="success" />
                                <SummaryItem label="Purchase" value={`₹${formatIndianNumber(summary.incentive?.purchase_amount_inr, 0)}`} tone="warning" />
                                <SummaryItem
                                    label="P / L"
                                    value={`${summary.incentive?.profit_loss_inr >= 0 ? '+' : ''}₹${formatIndianNumber(Math.abs(summary.incentive?.profit_loss_inr), 0)}`}
                                    tone={summary.incentive?.profit_loss_inr >= 0 ? "success" : "danger"}
                                />
                            </div>
                        </CardContent>
                    </Card>
                </div>
            )}

            {/* ── Transaction ledger ───────────────────────────────── */}
            <Card>
                <CardHeader className="border-b py-2 px-3">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-muted-foreground">
                            Transaction Ledger — {visibleLicenseCount} license{visibleLicenseCount !== 1 ? 's' : ''}
                        </span>
                        {companyWiseLoading && (
                            <span className="text-xs text-muted-foreground">Loading…</span>
                        )}
                    </div>
                </CardHeader>
                <CardContent className="p-0">
                    {companyWiseLoading ? (
                        <div role="status" aria-live="polite" className="flex flex-col items-center gap-2 py-10 text-center">
                            <span className="inline-block size-8 animate-spin rounded-full border-2 border-primary border-t-transparent" aria-hidden="true" />
                            <p className="text-sm text-muted-foreground">Loading license-wise ledger…</p>
                        </div>
                    ) : companyWiseData ? (
                        <TransactionLedger
                            data={companyWiseData}
                            navigate={navigate}
                        />
                    ) : (
                        <EmptyState
                            icon={Building2}
                            title="No data"
                            description="No trades found for the current filters"
                        />
                    )}
                </CardContent>
            </Card>
        </>
    );
}
