import { useEffect, useId, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import StatCard from "@/components/StatCard";
import { cn } from "@/lib/utils";
import {
    Boxes, Building2, CalendarRange, CheckCircle2, ChevronDown, ChevronRight,
    CircleDollarSign, FileSpreadsheet, FileText, Inbox, Landmark, Loader2,
    Maximize2, Minimize2, ScrollText, ShoppingCart, SlidersHorizontal, Tag,
    TrendingUp, TriangleAlert, Truck, Unlock, Wallet, XCircle,
} from "lucide-react";
import DateRangeFilter from "@/components/DateRangeFilter";
import AsyncSelectField from "@/components/AsyncSelectField";
import LicenseBlock, { type LicenseRow } from "./licenseTradingRegisterReport/LicenseBlock";
import { money, pct, qty } from "./licenseTradingRegisterReport/formatters";
import {
    useLicenseTradingRegisterReportFilters,
    LICENSE_TRADING_REGISTER_NORM_OPTIONS,
    LICENSE_TRADING_REGISTER_LICENSE_TYPE_OPTIONS,
} from "./licenseTradingRegisterReport/useLicenseTradingRegisterReportFilters";
import { useLicenseTradingRegisterReportData } from "./licenseTradingRegisterReport/useLicenseTradingRegisterReportData";

export { buildLicenseTradingRegisterReportPath } from "./licenseTradingRegisterReport/buildLicenseTradingRegisterReportPath";

type Dashboard = {
    total_licenses: unknown;
    open_licenses: unknown;
    closed_licenses: unknown;
    total_purchase: unknown;
    total_sales: unknown;
    total_profit: unknown;
    overall_margin_pct: unknown;
};

type NormItemSummaryRow = {
    item: string;
    licenses: unknown;
    purchase_qty: unknown;
    sale_qty: unknown;
    purchase_value: unknown;
    sale_value: unknown;
    profit: unknown;
    margin_pct: unknown;
};

type NormSummary = {
    licenses: unknown;
    purchase: unknown;
    sales: unknown;
    profit: unknown;
    margin_pct: unknown;
};

type NormSection = {
    norm: string;
    licenses: LicenseRow[];
    summary: NormSummary;
    item_summary: NormItemSummaryRow[];
};

type GrandSummaryRow = {
    norm: string;
    licenses: unknown;
    purchase: unknown;
    sales: unknown;
    profit: unknown;
    margin_pct: unknown;
};

type GrandSummary = {
    rows: GrandSummaryRow[];
    total: GrandSummaryRow;
};

type GrandItemSummaryRow = {
    norm: string;
    item: string;
    licenses: unknown;
    purchase_qty: unknown;
    sale_qty: unknown;
    purchase_value: unknown;
    sale_value: unknown;
    profit: unknown;
};

type GrandItemSummaryTotal = {
    purchase_value: unknown;
    sale_value: unknown;
    profit: unknown;
};

type GrandItemSummary = {
    rows: GrandItemSummaryRow[];
    total: GrandItemSummaryTotal;
};

type ReportData = {
    dashboard: Dashboard;
    norms: NormSection[];
    grand_summary: GrandSummary;
    grand_item_summary: GrandItemSummary;
};

/** Right-aligned money cell — tints green/red by sign (profit-style columns). */
function SignedMoneyCell({ value }: { value: unknown }) {
    const num = Number(value);
    const negative = Number.isFinite(num) && num < 0;
    return (
        <td className={cn("text-right", negative ? "text-destructive" : "text-success")}>
            {money(value)}
        </td>
    );
}

export default function LicenseTradingRegisterReport() {
    const navigate = useNavigate();

    const {
        fromDate, setFromDate, toDate, setToDate,
        norm, setNorm, licenseType, setLicenseType, licenseNumber, setLicenseNumber,
        exporter, handleExporterChange,
        item, handleItemChange,
        customer, handleCustomerChange,
        supplier, handleSupplierChange,
        hasActiveFilters, handleClearFilters,
    } = useLicenseTradingRegisterReportFilters();

    const { reportData, loading, error, downloading, hasQuery, exportExcel, exportPdf } = useLicenseTradingRegisterReportData({
        fromDate, toDate, norm, licenseType, licenseNumber, exporter, item, customer, supplier,
    });

    const fromDateId = useId();
    const toDateId = useId();
    const normId = useId();
    const licenseTypeId = useId();
    const licenseNumberId = useId();

    const data = reportData as ReportData | null;
    const dashboard = data?.dashboard;
    const norms = data?.norms ?? [];
    const grandSummary = data?.grand_summary;
    const grandItemSummary = data?.grand_item_summary;

    // Progressive disclosure: a run can cover dozens of norms and thousands
    // of licenses, so norm sections and license blocks default collapsed —
    // except the very first of each, expanded automatically so the report
    // never lands on an entirely empty-looking page. `expandedNorms` /
    // `expandedLicenses` are re-seeded whenever a fresh response lands.
    const [expandedNorms, setExpandedNorms] = useState<Set<string>>(new Set());
    const [expandedLicenses, setExpandedLicenses] = useState<Set<string>>(new Set());

    useEffect(() => {
        const firstNorm = data?.norms?.[0];
        if (!firstNorm) {
            setExpandedNorms(new Set());
            setExpandedLicenses(new Set());
            return;
        }
        setExpandedNorms(new Set([firstNorm.norm]));
        const firstLicense = firstNorm.licenses?.[0];
        setExpandedLicenses(firstLicense ? new Set([licenseKey(firstNorm.norm, firstLicense.license_id)]) : new Set());
        // Re-seed only when a *new* report payload lands, not on every render.
    }, [data]);

    function licenseKey(normName: string, licenseId: unknown): string {
        return `${normName}::${licenseId}`;
    }

    function toggleNorm(normName: string) {
        setExpandedNorms((prev) => {
            const next = new Set(prev);
            if (next.has(normName)) next.delete(normName);
            else next.add(normName);
            return next;
        });
    }

    function toggleLicense(key: string) {
        setExpandedLicenses((prev) => {
            const next = new Set(prev);
            if (next.has(key)) next.delete(key);
            else next.add(key);
            return next;
        });
    }

    function expandAll() {
        setExpandedNorms(new Set(norms.map((n) => n.norm)));
        setExpandedLicenses(new Set(norms.flatMap((n) => n.licenses.map((lic) => licenseKey(n.norm, lic.license_id)))));
    }

    function collapseAll() {
        setExpandedNorms(new Set());
        setExpandedLicenses(new Set());
    }

    return (
        <div className="min-h-screen bg-background">
            <div className="page-header">
                <div className="min-w-0">
                    <div className="page-pretitle">
                        <a
                            href="/"
                            onClick={(e) => { e.preventDefault(); navigate('/'); }}
                            style={{ color: 'inherit', textDecoration: 'none' }}
                        >
                            Home
                        </a>
                        <span className="mx-1.5 opacity-50">/</span>
                        Reports
                        <span className="mx-1.5 opacity-50">/</span>
                        Trading Register &amp; Profit Report
                    </div>
                    <h1>License Trading Register &amp; Profit Report</h1>
                </div>
                <div className="page-actions">
                    <Button variant="outline" size="sm" onClick={exportExcel} disabled={downloading || !hasQuery}>
                        {downloading ? <Loader2 className="size-3.5 animate-spin" /> : <FileSpreadsheet className="size-3.5" />}
                        Excel
                    </Button>
                    <Button variant="outline" size="sm" onClick={exportPdf} disabled={downloading || !hasQuery}>
                        {downloading ? <Loader2 className="size-3.5 animate-spin" /> : <FileText className="size-3.5" />}
                        PDF
                    </Button>
                </div>
            </div>

            {/* Filters */}
            <div className="mb-4 max-w-[1400px] overflow-hidden rounded-xl border border-border bg-card shadow-sm">
                <div className="flex items-center justify-between border-b border-border px-4 py-3.5">
                    <h5 className="mb-0 flex items-center gap-2 text-[15px] font-semibold">
                        <SlidersHorizontal className="size-4" aria-hidden="true" />
                        Filters
                    </h5>
                    {hasActiveFilters && (
                        <button
                            type="button"
                            className="flex cursor-pointer items-center gap-1.5 rounded-md border border-border bg-card px-2.5 py-1.5 text-xs font-medium text-muted-foreground hover:bg-muted"
                            onClick={handleClearFilters}
                        >
                            <XCircle className="size-4" aria-hidden="true" />
                            Clear Filters
                        </button>
                    )}
                </div>
                <div style={{ padding: "14px 16px" }}>
                    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
                        <div className="sm:col-span-2">
                            <DateRangeFilter
                                label="Date Range"
                                icon={CalendarRange}
                                fromId={fromDateId}
                                toId={toDateId}
                                fromValue={fromDate}
                                toValue={toDate}
                                onFromChange={setFromDate}
                                onToChange={setToDate}
                                onClear={() => { setFromDate(""); setToDate(""); }}
                            />
                        </div>

                        <div>
                            <label className="form-label mb-2 flex items-center gap-2 font-bold" htmlFor={normId}>
                                <Tag className="size-4" aria-hidden="true" />
                                Norm
                            </label>
                            <select
                                id={normId}
                                className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                                value={norm}
                                onChange={(e) => setNorm(e.target.value)}
                            >
                                {LICENSE_TRADING_REGISTER_NORM_OPTIONS.map((option) => (
                                    <option key={option} value={option}>{option}</option>
                                ))}
                            </select>
                        </div>

                        <div>
                            <label className="form-label mb-2 flex items-center gap-2 font-bold" htmlFor={licenseTypeId}>
                                <Landmark className="size-4" aria-hidden="true" />
                                License Type
                            </label>
                            <select
                                id={licenseTypeId}
                                className="flex h-9 w-full rounded-md border border-input bg-card px-3 py-1 text-sm outline-none focus-visible:border-ring"
                                value={licenseType}
                                onChange={(e) => setLicenseType(e.target.value)}
                            >
                                {LICENSE_TRADING_REGISTER_LICENSE_TYPE_OPTIONS.map((option) => (
                                    <option key={option} value={option}>{option}</option>
                                ))}
                            </select>
                        </div>

                        <div>
                            <Label htmlFor={licenseNumberId} className="mb-2 flex items-center gap-2 font-bold">
                                <FileText className="size-4" aria-hidden="true" />
                                License Number
                            </Label>
                            <Input
                                id={licenseNumberId}
                                value={licenseNumber}
                                onChange={(e) => setLicenseNumber(e.target.value)}
                                placeholder="Search license number..."
                            />
                        </div>

                        <div>
                            <div className="form-label mb-2 flex items-center gap-2 font-bold">
                                <Building2 className="size-4" aria-hidden="true" />
                                Exporter
                            </div>
                            <div style={{ minHeight: "38px" }}>
                                <AsyncSelectField
                                    endpoint="masters/companies/"
                                    labelField="name"
                                    valueField="id"
                                    value={exporter}
                                    onChange={handleExporterChange}
                                    isMulti={false}
                                    placeholder="All exporters..."
                                    loadOnMount={false}
                                />
                            </div>
                        </div>

                        <div>
                            <div className="form-label mb-2 flex items-center gap-2 font-bold">
                                <Boxes className="size-4" aria-hidden="true" />
                                Item
                            </div>
                            <div style={{ minHeight: "38px" }}>
                                <AsyncSelectField
                                    endpoint="masters/item-names/"
                                    labelField="name"
                                    valueField="id"
                                    value={item}
                                    onChange={handleItemChange}
                                    isMulti={false}
                                    placeholder="All items..."
                                    loadOnMount={false}
                                />
                            </div>
                        </div>

                        <div>
                            <div className="form-label mb-2 flex items-center gap-2 font-bold">
                                <ShoppingCart className="size-4" aria-hidden="true" />
                                Customer
                            </div>
                            <div style={{ minHeight: "38px" }}>
                                <AsyncSelectField
                                    endpoint="masters/companies/"
                                    labelField="name"
                                    valueField="id"
                                    value={customer}
                                    onChange={handleCustomerChange}
                                    isMulti={false}
                                    placeholder="All customers..."
                                    loadOnMount={false}
                                />
                            </div>
                        </div>

                        <div>
                            <div className="form-label mb-2 flex items-center gap-2 font-bold">
                                <Truck className="size-4" aria-hidden="true" />
                                Supplier
                            </div>
                            <div style={{ minHeight: "38px" }}>
                                <AsyncSelectField
                                    endpoint="masters/companies/"
                                    labelField="name"
                                    valueField="id"
                                    value={supplier}
                                    onChange={handleSupplierChange}
                                    isMulti={false}
                                    placeholder="All suppliers..."
                                    loadOnMount={false}
                                />
                            </div>
                        </div>
                    </div>
                </div>
            </div>

            {/* Report body */}
            <div className="row">
                <div className="col-span-full">
                    {!hasQuery && (
                        <Card>
                            <CardContent className="py-5 text-center">
                                <CalendarRange className="size-4" aria-hidden="true" />
                                <h5 className="mt-3 text-primary">Select a Date Range to View Report</h5>
                                <p className="text-muted-foreground">Choose a From and To date to load the trading register &amp; profit data</p>
                            </CardContent>
                        </Card>
                    )}

                    {hasQuery && loading && (
                        <Card>
                            <CardContent className="flex flex-col items-center py-12 text-center">
                                <Loader2 className="mb-3 size-10 animate-spin text-primary" />
                                <h5 className="text-muted-foreground">Loading Trading Register &amp; Profit Report…</h5>
                                <p className="text-muted-foreground text-sm">Please wait while we fetch the data</p>
                            </CardContent>
                        </Card>
                    )}

                    {hasQuery && !loading && error && (
                        <Card>
                            <CardContent className="py-5 text-center">
                                <TriangleAlert className="size-4 text-destructive" aria-hidden="true" />
                                <h5 className="mt-3 text-destructive">Failed to Load Report</h5>
                                <p className="text-muted-foreground">{error}</p>
                            </CardContent>
                        </Card>
                    )}

                    {hasQuery && !loading && !error && data && norms.length === 0 && (
                        <Card>
                            <CardContent className="py-5 text-center">
                                <Inbox className="size-4" aria-hidden="true" />
                                <h5 className="mt-3 text-muted-foreground">No licenses found</h5>
                                <p className="text-muted-foreground">Try adjusting your filters — a different date range, norm, license type/number, exporter, item, customer or supplier.</p>
                            </CardContent>
                        </Card>
                    )}

                    {hasQuery && !loading && !error && data && (
                        <>
                            {/* Dashboard */}
                            {dashboard && (
                                <div className="mb-4 grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-7">
                                    <StatCard label="Total Licenses" value={String(dashboard.total_licenses ?? 0)} icon={ScrollText} tone="primary" />
                                    <StatCard label="Open Licenses" value={String(dashboard.open_licenses ?? 0)} icon={Unlock} tone="warning" />
                                    <StatCard label="Closed Licenses" value={String(dashboard.closed_licenses ?? 0)} icon={CheckCircle2} tone="success" />
                                    <StatCard label="Total Purchase" value={money(dashboard.total_purchase)} icon={Wallet} tone="info" />
                                    <StatCard label="Total Sales" value={money(dashboard.total_sales)} icon={ShoppingCart} tone="info" />
                                    <StatCard label="Total Profit" value={money(dashboard.total_profit)} icon={TrendingUp} tone={Number(dashboard.total_profit) < 0 ? "danger" : "success"} />
                                    <StatCard label="Overall Margin %" value={pct(dashboard.overall_margin_pct)} icon={CircleDollarSign} tone="primary" />
                                </div>
                            )}

                            {norms.length > 0 && (
                                <>
                                    <div className="mb-3 flex items-center justify-end gap-2">
                                        <Button variant="outline" size="sm" onClick={expandAll}>
                                            <Maximize2 className="size-3.5" aria-hidden="true" />
                                            Expand All
                                        </Button>
                                        <Button variant="outline" size="sm" onClick={collapseAll}>
                                            <Minimize2 className="size-3.5" aria-hidden="true" />
                                            Collapse All
                                        </Button>
                                    </div>

                                    {norms.map((normSection) => {
                                        const normExpanded = expandedNorms.has(normSection.norm);
                                        return (
                                            <Card key={normSection.norm} className="mb-4 overflow-hidden">
                                                <button
                                                    type="button"
                                                    onClick={() => toggleNorm(normSection.norm)}
                                                    aria-expanded={normExpanded}
                                                    className="flex w-full flex-wrap items-center justify-between gap-3 px-4 py-3.5 text-left hover:bg-muted/40"
                                                >
                                                    <span className="flex items-center gap-2">
                                                        {normExpanded ? (
                                                            <ChevronDown className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                                                        ) : (
                                                            <ChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                                                        )}
                                                        <Tag className="size-4 text-muted-foreground" aria-hidden="true" />
                                                        <span className="text-[15px] font-semibold">{normSection.norm}</span>
                                                    </span>
                                                    <span className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                                                        <span><strong className="text-foreground">{String(normSection.summary.licenses ?? 0)}</strong> licenses</span>
                                                        <span>Purchase <strong className="text-foreground">{money(normSection.summary.purchase)}</strong></span>
                                                        <span>Sales <strong className="text-foreground">{money(normSection.summary.sales)}</strong></span>
                                                        <span>Profit <strong className={Number(normSection.summary.profit) < 0 ? "text-destructive" : "text-success"}>{money(normSection.summary.profit)}</strong></span>
                                                        <span>Margin <strong className="text-foreground">{pct(normSection.summary.margin_pct)}</strong></span>
                                                    </span>
                                                </button>

                                                {normExpanded && (
                                                    <CardContent className="border-t border-border bg-muted/20 p-4">
                                                        {normSection.licenses.map((lic) => (
                                                            <LicenseBlock
                                                                key={lic.license_id}
                                                                license={lic}
                                                                expanded={expandedLicenses.has(licenseKey(normSection.norm, lic.license_id))}
                                                                onToggle={() => toggleLicense(licenseKey(normSection.norm, lic.license_id))}
                                                            />
                                                        ))}

                                                        {/* Norm Summary */}
                                                        <Card className="mb-3">
                                                            <CardHeader>
                                                                <h5 className="mb-0 text-[14px] font-semibold">Norm Summary</h5>
                                                            </CardHeader>
                                                            <CardContent className="p-0">
                                                                <div className="overflow-x-auto">
                                                                    <table className="table table-sm table-bordered mb-0">
                                                                        <thead>
                                                                            <tr className="table-light">
                                                                                <th scope="col" className="text-right">Licenses</th>
                                                                                <th scope="col" className="text-right">Purchase</th>
                                                                                <th scope="col" className="text-right">Sales</th>
                                                                                <th scope="col" className="text-right">Profit</th>
                                                                                <th scope="col" className="text-right">Margin %</th>
                                                                            </tr>
                                                                        </thead>
                                                                        <tbody>
                                                                            <tr className="font-semibold">
                                                                                <td className="text-right">{String(normSection.summary.licenses ?? 0)}</td>
                                                                                <td className="text-right">{money(normSection.summary.purchase)}</td>
                                                                                <td className="text-right">{money(normSection.summary.sales)}</td>
                                                                                <SignedMoneyCell value={normSection.summary.profit} />
                                                                                <td className="text-right">{pct(normSection.summary.margin_pct)}</td>
                                                                            </tr>
                                                                        </tbody>
                                                                    </table>
                                                                </div>
                                                            </CardContent>
                                                        </Card>

                                                        {/* Norm Item Summary */}
                                                        <Card>
                                                            <CardHeader>
                                                                <h5 className="mb-0 text-[14px] font-semibold">Norm Item Summary</h5>
                                                            </CardHeader>
                                                            <CardContent className="p-0">
                                                                <div className="overflow-x-auto">
                                                                    <table className="table table-sm table-bordered mb-0">
                                                                        <thead>
                                                                            <tr className="table-light">
                                                                                <th scope="col">Item</th>
                                                                                <th scope="col" className="text-right">Licenses</th>
                                                                                <th scope="col" className="text-right">Purchase Qty</th>
                                                                                <th scope="col" className="text-right">Sale Qty</th>
                                                                                <th scope="col" className="text-right">Purchase Value</th>
                                                                                <th scope="col" className="text-right">Sale Value</th>
                                                                                <th scope="col" className="text-right">Profit</th>
                                                                                <th scope="col" className="text-right">Margin %</th>
                                                                            </tr>
                                                                        </thead>
                                                                        <tbody>
                                                                            {(() => {
                                                                                const itemTotals = normSection.item_summary.reduce(
                                                                                    (acc, row) => {
                                                                                        acc.purchase_qty += Number(row.purchase_qty) || 0;
                                                                                        acc.sale_qty += Number(row.sale_qty) || 0;
                                                                                        acc.purchase_value += Number(row.purchase_value) || 0;
                                                                                        acc.sale_value += Number(row.sale_value) || 0;
                                                                                        acc.profit += Number(row.profit) || 0;
                                                                                        return acc;
                                                                                    },
                                                                                    { purchase_qty: 0, sale_qty: 0, purchase_value: 0, sale_value: 0, profit: 0 },
                                                                                );
                                                                                const itemMargin = itemTotals.sale_value !== 0 ? (itemTotals.profit / itemTotals.sale_value) * 100 : 0;
                                                                                return (
                                                                                    <>
                                                                                        {normSection.item_summary.map((row, idx) => (
                                                                                            <tr key={`${normSection.norm}-item-${idx}`}>
                                                                                                <td>{row.item}</td>
                                                                                                <td className="text-right">{String(row.licenses ?? 0)}</td>
                                                                                                <td className="text-right">{qty(row.purchase_qty)}</td>
                                                                                                <td className="text-right">{qty(row.sale_qty)}</td>
                                                                                                <td className="text-right">{money(row.purchase_value)}</td>
                                                                                                <td className="text-right">{money(row.sale_value)}</td>
                                                                                                <SignedMoneyCell value={row.profit} />
                                                                                                <td className="text-right">{pct(row.margin_pct)}</td>
                                                                                            </tr>
                                                                                        ))}
                                                                                        <tr className="table-secondary font-bold">
                                                                                            <td>Total</td>
                                                                                            <td className="text-right">—</td>
                                                                                            <td className="text-right">{qty(itemTotals.purchase_qty)}</td>
                                                                                            <td className="text-right">{qty(itemTotals.sale_qty)}</td>
                                                                                            <td className="text-right">{money(itemTotals.purchase_value)}</td>
                                                                                            <td className="text-right">{money(itemTotals.sale_value)}</td>
                                                                                            <SignedMoneyCell value={itemTotals.profit} />
                                                                                            <td className="text-right">{pct(itemMargin)}</td>
                                                                                        </tr>
                                                                                    </>
                                                                                );
                                                                            })()}
                                                                        </tbody>
                                                                    </table>
                                                                </div>
                                                            </CardContent>
                                                        </Card>
                                                    </CardContent>
                                                )}
                                            </Card>
                                        );
                                    })}
                                </>
                            )}

                            {/* Grand Summary */}
                            {grandSummary && (
                                <Card className="mb-4">
                                    <CardHeader className="text-primary-foreground" style={{ background: 'linear-gradient(135deg, var(--tb-brand), var(--tb-brand-hover))' }}>
                                        <h5 className="mb-0 flex items-center gap-2 font-semibold">
                                            <TrendingUp className="size-4" aria-hidden="true" />
                                            Grand Summary
                                        </h5>
                                    </CardHeader>
                                    <CardContent className="p-0">
                                        <div className="overflow-x-auto">
                                            <table className="table table-sm table-bordered mb-0">
                                                <thead>
                                                    <tr className="table-light">
                                                        <th scope="col">Norm</th>
                                                        <th scope="col" className="text-right">Licenses</th>
                                                        <th scope="col" className="text-right">Purchase</th>
                                                        <th scope="col" className="text-right">Sales</th>
                                                        <th scope="col" className="text-right">Profit</th>
                                                        <th scope="col" className="text-right">Margin %</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {grandSummary.rows.map((row) => (
                                                        <tr key={row.norm}>
                                                            <td className="font-semibold">{row.norm}</td>
                                                            <td className="text-right">{String(row.licenses ?? 0)}</td>
                                                            <td className="text-right">{money(row.purchase)}</td>
                                                            <td className="text-right">{money(row.sales)}</td>
                                                            <SignedMoneyCell value={row.profit} />
                                                            <td className="text-right">{pct(row.margin_pct)}</td>
                                                        </tr>
                                                    ))}
                                                    <tr className="table-secondary font-bold">
                                                        <td>Grand Total</td>
                                                        <td className="text-right">{String(grandSummary.total.licenses ?? 0)}</td>
                                                        <td className="text-right">{money(grandSummary.total.purchase)}</td>
                                                        <td className="text-right">{money(grandSummary.total.sales)}</td>
                                                        <SignedMoneyCell value={grandSummary.total.profit} />
                                                        <td className="text-right">{pct(grandSummary.total.margin_pct)}</td>
                                                    </tr>
                                                </tbody>
                                            </table>
                                        </div>
                                    </CardContent>
                                </Card>
                            )}

                            {/* Grand Item Summary */}
                            {grandItemSummary && (
                                <Card>
                                    <CardHeader>
                                        <h5 className="mb-0 flex items-center gap-2 font-semibold">
                                            <Boxes className="size-4" aria-hidden="true" />
                                            Grand Item Summary
                                        </h5>
                                    </CardHeader>
                                    <CardContent className="p-0">
                                        <div className="overflow-x-auto">
                                            <table className="table table-sm table-bordered mb-0">
                                                <thead>
                                                    <tr className="table-light">
                                                        <th scope="col">Norm</th>
                                                        <th scope="col">Item</th>
                                                        <th scope="col" className="text-right">Licenses</th>
                                                        <th scope="col" className="text-right">Purchase Qty</th>
                                                        <th scope="col" className="text-right">Sale Qty</th>
                                                        <th scope="col" className="text-right">Purchase Value</th>
                                                        <th scope="col" className="text-right">Sale Value</th>
                                                        <th scope="col" className="text-right">Profit</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {grandItemSummary.rows.map((row, idx) => (
                                                        <tr key={`${row.norm}-${row.item}-${idx}`}>
                                                            <td className="font-semibold">{row.norm}</td>
                                                            <td>{row.item}</td>
                                                            <td className="text-right">{String(row.licenses ?? 0)}</td>
                                                            <td className="text-right">{qty(row.purchase_qty)}</td>
                                                            <td className="text-right">{qty(row.sale_qty)}</td>
                                                            <td className="text-right">{money(row.purchase_value)}</td>
                                                            <td className="text-right">{money(row.sale_value)}</td>
                                                            <SignedMoneyCell value={row.profit} />
                                                        </tr>
                                                    ))}
                                                    <tr className="table-secondary font-bold">
                                                        <td colSpan={5}>Grand Total</td>
                                                        <td className="text-right">{money(grandItemSummary.total.purchase_value)}</td>
                                                        <td className="text-right">{money(grandItemSummary.total.sale_value)}</td>
                                                        <SignedMoneyCell value={grandItemSummary.total.profit} />
                                                    </tr>
                                                </tbody>
                                            </table>
                                        </div>
                                    </CardContent>
                                </Card>
                            )}
                        </>
                    )}
                </div>
            </div>
        </div>
    );
}
