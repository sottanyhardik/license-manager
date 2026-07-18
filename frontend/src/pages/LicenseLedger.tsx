import React, { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { toast } from "sonner";
import api from '../api/axios';
import { formatIndianNumber } from '../utils/numberFormatter';
import { generatePDF, generateExcel } from '../utils/ledgerExport';
import AsyncSelectField from '../components/AsyncSelectField';
import PageHeader from '@/components/PageHeader';
import EmptyState from '@/components/EmptyState';
import { cn } from '@/lib/utils';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import DebouncedSearchInput from '../components/DebouncedSearchInput';
import {
    ArrowDownCircle, ArrowUpCircle, BookOpen, Building2, Calendar,
    CalendarCheck, CalendarRange, CalendarX, FileSpreadsheet, FileText,
    Filter, Globe, Inbox, Loader2, Trophy, XCircle,
} from "lucide-react";

// ─── Types ─────────────────────────────────────────────────────────────────────

type CompanyFilter = { value: string | number; label?: string } | string | null;

type LedgerFilters = {
    license_type: string;
    min_balance: string;
    search: string;
    company: CompanyFilter;
    active_only: boolean;
    ordering: string;
    purchase_date_from: string;
    purchase_date_to: string;
    no_purchases?: boolean;
};

type LedgerTransaction = {
    trade_id: string | number;
    invoice_date: string;
    amount: number;
};

type LedgerCompany = {
    company_id: string | number;
    company_name: string;
    purchases: LedgerTransaction[];
    sales: LedgerTransaction[];
    purchase_total: number;
    sale_total: number;
    profit_loss: number;
};

type LicenseWiseEntry = {
    license_id: string | number;
    license_number: string;
    license_date: string;
    license_type: string;
    companies: LedgerCompany[];
};

type LicenseWiseData = {
    licenses: LicenseWiseEntry[];
};

// ─── Constants ─────────────────────────────────────────────────────────────────

const VALID_LICENSE_TYPES = new Set(['ALL', 'DFIA', 'INCENTIVE', 'RODTEP', 'ROSTL', 'MEIS']);
const VALID_ORDERING = new Set(['-license_date', 'license_date', '-balance_value', 'balance_value']);

const LICENSE_TYPE_OPTIONS = [
    { value: 'ALL',       label: 'All Licenses',  Icon: Globe },
    { value: 'DFIA',      label: 'DFIA Only',      Icon: Globe },
    { value: 'INCENTIVE', label: 'All Incentive',  Icon: Trophy },
    { value: 'RODTEP',    label: 'RODTEP',         Icon: Trophy },
    { value: 'ROSTL',     label: 'ROSTL',          Icon: Trophy },
    { value: 'MEIS',      label: 'MEIS',           Icon: Trophy },
];

// ─── Pure utilities ────────────────────────────────────────────────────────────

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

export function getFinancialYearRange(date = new Date(), offset = 0) {
    const currentYear = date.getFullYear();
    const currentMonth = date.getMonth();
    const currentFyStartYear = currentMonth <= 2 ? currentYear - 1 : currentYear;
    const fyStartYear = currentFyStartYear + offset;
    return {
        fyStart: `${fyStartYear}-04-01`,
        fyEnd: `${fyStartYear + 1}-03-31`,
    };
}

export function normalizeMinBalance(value: unknown): string {
    const rawValue = String(value ?? '').trim();
    if (!rawValue) return '';
    const parsed = Number(rawValue);
    if (!Number.isFinite(parsed) || parsed < 0) return '';
    return String(parsed);
}

export function getCompanyFilterValue(company: CompanyFilter): string {
    if (!company) return '';
    if (typeof company === 'object') return normalizeText(company.value);
    return normalizeText(company);
}

export function buildLedgerFilterParams(filters: LedgerFilters, additionalFilters: Partial<LedgerFilters> = {}) {
    const currentFilters = { ...filters, ...additionalFilters };
    const params = new URLSearchParams();
    const licenseType = VALID_LICENSE_TYPES.has(currentFilters.license_type) ? currentFilters.license_type : 'ALL';
    const minBalance = normalizeMinBalance(currentFilters.min_balance);
    const company = getCompanyFilterValue(currentFilters.company);
    const ordering = VALID_ORDERING.has(currentFilters.ordering) ? currentFilters.ordering : '-license_date';

    params.append('license_type', licenseType);
    if (minBalance) params.append('min_balance', minBalance);
    if (currentFilters.search.trim()) params.append('search', currentFilters.search.trim());
    if (company) params.append('company', company);
    params.append('ordering', ordering);
    if (currentFilters.purchase_date_from) params.append('purchase_date_from', currentFilters.purchase_date_from);
    if (currentFilters.purchase_date_to) params.append('purchase_date_to', currentFilters.purchase_date_to);
    params.append('active_only', String(Boolean(currentFilters.active_only)));
    if (currentFilters.no_purchases) params.append('no_purchases', 'true');
    return params;
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
        }),
    };
}

export function normalizeLedgerExportDetails(value: unknown) {
    if (!isRecord(value)) return null;
    const licenseId = value.license_id ?? value.id;
    if (licenseId === null || licenseId === undefined || String(licenseId).trim() === '') return null;
    return value;
}

export function getTodayStamp(date = new Date()): string {
    return date.toISOString().slice(0, 10);
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

function LicenseWiseLedger({ data, navigate, companyId }: { data: LicenseWiseData; navigate: ReturnType<typeof useNavigate>; companyId?: string }) {
    const { licenses } = normalizeLicenseWiseData(data);
    const fmt = (v: number) => `₹${formatIndianNumber(v, 2)}`;

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
                        <button
                            type="button"
                            onClick={() => navigate(companyId ? `/license-ledger/${lic.license_id}/${companyId}` : `/license-ledger/${lic.license_id}`)}
                            aria-label={`View ledger for ${lic.license_number}`}
                            className="ml-auto flex cursor-pointer items-center gap-1.5 rounded-md border border-white/30 bg-white/15 px-2.5 py-1 text-[12px] font-semibold text-white transition-colors hover:bg-white/25"
                        >
                            <BookOpen className="size-4" aria-hidden="true" />View Ledger
                        </button>
                    </div>

                    {/* ── Companies table ────────────────────────────── */}
                    <table className="w-full border-collapse text-[12.5px]">
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
    const [pdfExporting, setPdfExporting] = useState(false);
    const [excelExporting, setExcelExporting] = useState(false);

    const { fyStart: currentFYStart, fyEnd: currentFYEnd } = getFinancialYearRange();

    const [filters, setFilters] = useState<LedgerFilters>({
        license_type: 'ALL', min_balance: '', search: '', company: null,
        active_only: true, ordering: '-license_date',
        purchase_date_from: currentFYStart, purchase_date_to: currentFYEnd,
    });

    const buildFilterParams = useCallback((additionalFilters: Partial<LedgerFilters> = {}) => {
        return buildLedgerFilterParams(filters, additionalFilters);
    }, [filters]);

    useEffect(() => {
        fetchCompanyWise();
        if (filters.company) {
            fetchSummary();
        } else {
            setSummary(null);
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [
        filters.license_type,
        filters.min_balance,
        filters.search,
        filters.company,
        filters.active_only,
        filters.ordering,
        filters.purchase_date_from,
        filters.purchase_date_to,
    ]);

    const fetchSummary = async () => {
        try {
            const params = buildFilterParams();
            const response = await api.get(`license-ledger/summary/?${params.toString()}`);
            setSummary(response.data);
        } catch (error) {
            toast.error(getApiErrorMessage(error, 'Failed to load summary data.'));
        }
    };

    const fetchCompanyWise = async () => {
        setCompanyWiseLoading(true);
        try {
            const params = buildFilterParams();
            const response = await api.get(`license-ledger/license-wise/?${params.toString()}`);
            setCompanyWiseData(normalizeLicenseWiseData(response.data));
        } catch (error) {
            toast.error(getApiErrorMessage(error, 'Failed to load company-wise ledger.'));
            setCompanyWiseData(null);
        } finally {
            setCompanyWiseLoading(false);
        }
    };

    const handleFilterChange = (field: keyof LedgerFilters, value: LedgerFilters[keyof LedgerFilters]) =>
        setFilters(prev => ({ ...prev, [field]: value }));

    const setCurrentFinancialYear = () => {
        const { fyStart, fyEnd } = getFinancialYearRange();
        setFilters(prev => ({ ...prev, purchase_date_from: fyStart, purchase_date_to: fyEnd }));
    };
    const setPreviousFinancialYear = () => {
        const { fyStart, fyEnd } = getFinancialYearRange(undefined, -1);
        setFilters(prev => ({ ...prev, purchase_date_from: fyStart, purchase_date_to: fyEnd }));
    };
    const clearDateFilter = () =>
        setFilters(prev => ({ ...prev, purchase_date_from: '', purchase_date_to: '' }));

    const clearAllFilters = () => {
        const { fyStart, fyEnd } = getFinancialYearRange();
        setFilters({
            license_type: 'ALL',
            min_balance: '',
            search: '',
            company: null,
            active_only: true,
            ordering: '-license_date',
            purchase_date_from: fyStart,
            purchase_date_to: fyEnd,
        });
    };

    const fetchFullLedgerDetails = async () => {
        const licenses = normalizeLicenseWiseData(companyWiseData).licenses;
        if (!licenses.length) return { results: [], failures: 0 };

        // When a company filter is active, pass it so the backend returns only that
        // company's transactions (build_dfia/incentive_ledger_detail already supports this).
        const companyValue = getCompanyFilterValue(filters.company);

        // Fetch all licenses in parallel — eliminates the N×latency serial bottleneck.
        // Pass license_type so the backend searches the correct table (DFIA vs Incentive)
        // and avoids false matches when both tables share the same integer PK.
        const settled = await Promise.allSettled(
            licenses.map(lic => {
                const params = new URLSearchParams({ license_type: lic.license_type });
                if (companyValue) params.set('company', companyValue);
                return api.get(`license-ledger/${lic.license_id}/ledger_detail/?${params}`)
                          .then(r => ({ data: r.data, license_id: lic.license_id }));
            })
        );

        let failures = 0;
        const results: unknown[] = [];
        for (const r of settled) {
            if (r.status === 'rejected') { failures++; continue; }
            // Defensively merge license_id in case the backend omits it
            const detail = normalizeLedgerExportDetails(
                { ...r.value.data, license_id: r.value.data.license_id ?? r.value.license_id }
            );
            if (detail) results.push(detail);
            else failures++;
        }
        return { results, failures };
    };

    const handleBulkExport = async (
        format: "pdf" | "xlsx",
        setExporting: (v: boolean) => void,
    ) => {
        if (!normalizeLicenseWiseData(companyWiseData).licenses.length) {
            toast.error("No data to export"); return;
        }
        const toastId = `bulk-${format}`;
        setExporting(true);
        try {
            toast.info("Fetching ledger details…", { duration: Infinity, id: toastId });
            const { results: allLedgers, failures } = await fetchFullLedgerDetails();
            toast.dismiss(toastId);
            if (!allLedgers.length) { toast.error("No ledger data available"); return; }
            const stamp = getTodayStamp();
            // Include the active company name in the filename when the filter is set.
            const companySegment = companyLabel
                ? `_${companyLabel.replace(/[^\w\s-]/g, '').trim().replace(/\s+/g, '_').substring(0, 40)}`
                : '';
            const fileBase = `License_Ledger_Bulk${companySegment}_${stamp}`;
            if (format === "pdf") generatePDF(allLedgers, `${fileBase}.pdf`);
            else await generateExcel(allLedgers, `${fileBase}.xlsx`);
            toast.success(`Exported ${allLedgers.length} license(s) to ${format.toUpperCase()}${failures ? `; ${failures} failed` : ""}`);
        } catch {
            toast.dismiss(toastId);
            toast.error(`Failed to generate ${format.toUpperCase()}`);
        } finally {
            setExporting(false);
        }
    };

    const anyExporting = pdfExporting || excelExporting;
    const handleBulkExportPDF   = () => handleBulkExport("pdf",  setPdfExporting);
    const handleBulkExportExcel = () => handleBulkExport("xlsx", setExcelExporting);

    const exportableLicenses = normalizeLicenseWiseData(companyWiseData).licenses;
    const companyLabel = normalizeText(
        filters.company && typeof filters.company === 'object'
            ? filters.company.label ?? filters.company.value
            : filters.company,
    );

    return (
        <>
            {/* ── Header ─────────────────────────────────────────── */}
            <PageHeader
                pretitle="Ledger"
                title="License Ledger"
                description="Track available balance for DFIA and Incentive licenses"
                actions={
                    <div className="flex gap-2">
                        <Button
                            variant="outline" size="sm"
                            onClick={handleBulkExportPDF}
                            disabled={anyExporting || exportableLicenses.length === 0}
                            aria-label="Export license ledger as PDF"
                            title={exportableLicenses.length === 0 ? 'No data to export' : undefined}
                        >
                            {pdfExporting ? <Loader2 className="size-3.5 animate-spin" /> : <FileText className="size-3.5" />}
                            Export PDF
                        </Button>
                        <Button
                            variant="outline" size="sm"
                            onClick={handleBulkExportExcel}
                            disabled={anyExporting || exportableLicenses.length === 0}
                            aria-label="Export license ledger as Excel"
                            title={exportableLicenses.length === 0 ? 'No data to export' : undefined}
                        >
                            {excelExporting ? <Loader2 className="size-3.5 animate-spin" /> : <FileSpreadsheet className="size-3.5" />}
                            Export Excel
                        </Button>
                    </div>
                }
            />

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
                            <div className="grid grid-cols-4 divide-x divide-border text-center">
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
                            <div className="grid grid-cols-4 divide-x divide-border text-center">
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

            {/* ── Filters card ───────────────────────────────────── */}
            <Card className="mb-3">
                <CardHeader className="border-b py-2 px-3">
                    <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                            <Filter className="size-4 text-muted-foreground" aria-hidden="true" />
                            <span className="text-[13px] font-semibold">Filters & Search</span>
                            {filters.company && (
                                <Badge variant="info" className="ml-1 text-[11px]">
                                    <Building2 className="size-3" aria-hidden="true" />
                                    {companyLabel}
                                </Badge>
                            )}
                        </div>
                        <div className="flex gap-2">
                            {filters.company && (
                                <Button size="sm" variant="outline" onClick={() => handleFilterChange('company', null)}>
                                    <XCircle className="size-3.5" aria-hidden="true" />Clear Company
                                </Button>
                            )}
                            <Button size="sm" variant="outline" onClick={clearAllFilters}>
                                <XCircle className="size-3.5" aria-hidden="true" />Clear All
                            </Button>
                        </div>
                    </div>
                </CardHeader>
                <CardContent className="p-3">
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-6">
                        <div className="lg:col-span-2">
                            <label id="company-filter-label" className="mb-1.5 block text-[12px] font-semibold text-muted-foreground">
                                <Building2 className="size-4" aria-hidden="true" /> Company Filter
                            </label>
                            <AsyncSelectField
                                endpoint="masters/companies/" labelField="name" valueField="id"
                                value={filters.company}
                                onChange={(value) => handleFilterChange('company', value)}
                                isMulti={false} placeholder="Select company to view their ledger..."
                                loadOnMount={false} aria-labelledby="company-filter-label"
                            />
                            <p className="mt-0.5 text-[11px] text-muted-foreground">Filter by trades with specific company</p>
                        </div>
                        <div className="lg:col-span-2">
                            <label className="mb-1.5 block text-[12px] font-semibold text-muted-foreground">License Type</label>
                            <div className="flex flex-wrap gap-1">
                                {LICENSE_TYPE_OPTIONS.map(opt => {
                                    const active = filters.license_type === opt.value;
                                    return (
                                        <button
                                            key={opt.value}
                                            type="button"
                                            aria-pressed={active}
                                            onClick={() => handleFilterChange('license_type', opt.value)}
                                            className={cn(
                                                "cursor-pointer rounded-full border px-2.5 py-1 text-xs font-semibold transition-colors",
                                                active
                                                    ? "border-primary bg-primary text-primary-foreground"
                                                    : "border-border bg-card text-muted-foreground hover:bg-muted",
                                            )}
                                        >
                                            {opt.label}
                                        </button>
                                    );
                                })}
                            </div>
                        </div>
                        <div>
                            <label htmlFor="ledger-min-balance" className="mb-1.5 block text-[12px] font-semibold text-muted-foreground">Min Balance</label>
                            <Input id="ledger-min-balance" type="number" value={filters.min_balance} onChange={(e) => handleFilterChange('min_balance', e.target.value)} placeholder="0" step="100" min="0" />
                        </div>
                        <div>
                            <label htmlFor="ledger-search" className="mb-1.5 block text-[12px] font-semibold text-muted-foreground">Search</label>
                            <DebouncedSearchInput value={filters.search} onChange={(v) => handleFilterChange('search', v)} placeholder="License # or exporter..." />
                        </div>
                    </div>

                    <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                        <div>
                            <label htmlFor="ledger-sort" className="mb-1.5 block text-[12px] font-semibold text-muted-foreground">Sort By</label>
                            <select
                                id="ledger-sort"
                                className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                                value={filters.ordering}
                                onChange={(e) => handleFilterChange('ordering', e.target.value)}
                            >
                                <option value="-license_date">Latest First</option>
                                <option value="license_date">Oldest First</option>
                                <option value="-balance_value">Highest Balance</option>
                                <option value="balance_value">Lowest Balance</option>
                            </select>
                        </div>
                        <div className="flex items-end">
                            <label className="flex cursor-pointer items-center gap-2.5 text-sm" htmlFor="activeOnly">
                                <Switch id="activeOnly" checked={filters.active_only} onCheckedChange={(v) => handleFilterChange('active_only', v)} />
                                <span className="text-xs font-semibold text-muted-foreground">Active Only</span>
                            </label>
                        </div>
                    </div>

                    {/* Purchase date range */}
                    <div className="mt-3 border-t border-border/60 pt-3">
                        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
                            <div className="flex items-center gap-2 text-[12px] font-semibold text-muted-foreground">
                                <CalendarRange className="size-4" aria-hidden="true" />
                                Purchase Date Range
                                <span className="text-[11.5px] font-normal">(Defaults to current FY: Apr-Mar)</span>
                            </div>
                            <div className="flex gap-1">
                                <Button size="sm" variant="outline" onClick={setCurrentFinancialYear}>
                                    <CalendarCheck className="size-4" aria-hidden="true" />Current FY
                                </Button>
                                <Button size="sm" variant="outline" onClick={setPreviousFinancialYear}>
                                    <Calendar className="size-4" aria-hidden="true" />Previous FY
                                </Button>
                                <Button
                                    size="sm" variant="outline"
                                    className="text-destructive hover:bg-destructive/10"
                                    onClick={clearDateFilter}
                                    disabled={!filters.purchase_date_from && !filters.purchase_date_to}
                                >
                                    <XCircle className="size-4" aria-hidden="true" />Clear
                                </Button>
                            </div>
                        </div>
                        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                            <div>
                                <label htmlFor="ledger-purchase-from" className="mb-1.5 block text-[12px] font-semibold text-muted-foreground">
                                    <CalendarCheck className="size-4" aria-hidden="true" /> From Date
                                </label>
                                <Input id="ledger-purchase-from" type="date" value={filters.purchase_date_from} onChange={(e) => handleFilterChange('purchase_date_from', e.target.value)} />
                            </div>
                            <div>
                                <label htmlFor="ledger-purchase-to" className="mb-1.5 block text-[12px] font-semibold text-muted-foreground">
                                    <CalendarX className="size-4" aria-hidden="true" /> To Date
                                </label>
                                <Input id="ledger-purchase-to" type="date" value={filters.purchase_date_to} onChange={(e) => handleFilterChange('purchase_date_to', e.target.value)} />
                            </div>
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* ── Company-wise ledger card ────────────────────────── */}
            <Card>
                <CardHeader className="border-b py-2 px-3">
                    <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold text-muted-foreground">
                            {exportableLicenses.length} license{exportableLicenses.length !== 1 ? 's' : ''}
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
                        <LicenseWiseLedger
                            data={companyWiseData}
                            navigate={navigate}
                            companyId={getCompanyFilterValue(filters.company) || undefined}
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
