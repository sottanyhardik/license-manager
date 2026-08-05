import { useId } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import {
    Building2, CalendarRange, FileSpreadsheet, FileText, Inbox, Loader2,
    SlidersHorizontal, Tag, TrendingUp, TriangleAlert, XCircle,
} from "lucide-react";
import DateRangeFilter from "@/components/DateRangeFilter";
import AsyncSelectField from "@/components/AsyncSelectField";
import { formatIndianNumber } from "@/utils/numberFormatter";
import { useLicensePurchaseProfitReportFilters, LICENSE_PURCHASE_PROFIT_NORM_OPTIONS } from "./licensePurchaseProfitReport/useLicensePurchaseProfitReportFilters";
import { useLicensePurchaseProfitReportData } from "./licensePurchaseProfitReport/useLicensePurchaseProfitReportData";

export { buildLicensePurchaseProfitReportPath } from "./licensePurchaseProfitReport/buildLicensePurchaseProfitReportPath";

/** Numbers arrive as Decimal-safe strings from the API — never assume a
 * plain JS number, always parse defensively before formatting/arithmetic. */
function toNum(value: unknown): number {
    const num = Number(value);
    return Number.isFinite(num) ? num : 0;
}

function money(value: unknown): string {
    return formatIndianNumber(toNum(value), 2);
}

function pct(value: unknown): string {
    return `${formatIndianNumber(toNum(value), 2)}%`;
}

type LicenseSummaryRow = {
    license_id: number | string;
    license_number: string;
    exporter: string;
    purchase_cost: unknown;
    debited_cif: unknown;
    remaining_cif: unknown;
    allocated_purchase: unknown;
    realized_profit: unknown;
    profit_pct: unknown;
};

type ItemProfitRow = {
    license_id: number | string;
    license_number: string;
    item: string;
    qty_debited: unknown;
    debited_cif: unknown;
    pct_share: unknown;
    allocated_purchase: unknown;
    profit: unknown;
};

type NormSummary = {
    total_purchase: unknown;
    total_debited_cif: unknown;
    total_profit: unknown;
    margin_pct: unknown;
};

type NormSection = {
    norm: string;
    licenses: LicenseSummaryRow[];
    items: ItemProfitRow[];
    summary: NormSummary;
};

type GrandSummaryRow = {
    norm: string;
    purchase: unknown;
    debited_cif: unknown;
    profit: unknown;
    margin_pct: unknown;
};

type GrandSummary = {
    rows: GrandSummaryRow[];
    total: GrandSummaryRow;
};

type ReportData = {
    norms: NormSection[];
    grand_summary: GrandSummary;
};

/** Right-aligned money cell — profit/loss columns tint red when negative. */
function MoneyCell({ value, tint = false }: { value: unknown; tint?: boolean }) {
    const num = toNum(value);
    return (
        <td className={cn("text-right", tint && num < 0 && "text-destructive", tint && num >= 0 && "text-success")}>
            {money(value)}
        </td>
    );
}

export default function LicensePurchaseProfitReport() {
    const navigate = useNavigate();

    const {
        fromDate, setFromDate, toDate, setToDate,
        norm, setNorm, licenseNumber, setLicenseNumber,
        exporter, handleExporterChange,
        hasActiveFilters, handleClearFilters,
    } = useLicensePurchaseProfitReportFilters();

    const { reportData, loading, error, downloading, hasQuery, exportExcel, exportPdf } = useLicensePurchaseProfitReportData({
        fromDate, toDate, norm, licenseNumber, exporter,
    });

    const fromDateId = useId();
    const toDateId = useId();
    const normId = useId();
    const licenseNumberId = useId();

    const data = reportData as ReportData | null;
    const norms = data?.norms ?? [];
    const grandSummary = data?.grand_summary;

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
                        Purchase &amp; Profit Report
                    </div>
                    <h1>License Purchase &amp; Profit Report</h1>
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
                                {LICENSE_PURCHASE_PROFIT_NORM_OPTIONS.map((option) => (
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
                                <p className="text-muted-foreground">Choose a From and To date to load purchase &amp; profit data</p>
                            </CardContent>
                        </Card>
                    )}

                    {hasQuery && loading && (
                        <Card>
                            <CardContent className="flex flex-col items-center py-12 text-center">
                                <Loader2 className="mb-3 size-10 animate-spin text-primary" />
                                <h5 className="text-muted-foreground">Loading Purchase &amp; Profit Report…</h5>
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
                                <p className="text-muted-foreground">Try adjusting your filters — a different date range, norm, license number, or exporter.</p>
                            </CardContent>
                        </Card>
                    )}

                    {hasQuery && !loading && !error && data && norms.length > 0 && (
                        <>
                            {norms.map((normSection) => (
                                <div key={normSection.norm} className="mb-6">
                                    <h3 className="mb-3 flex items-center gap-2 text-lg font-semibold text-foreground">
                                        <Tag className="size-4" aria-hidden="true" />
                                        {normSection.norm}
                                    </h3>

                                    {/* License Summary */}
                                    <Card className="mb-4">
                                        <CardHeader>
                                            <h5 className="mb-0 text-[14px] font-semibold">License Summary</h5>
                                        </CardHeader>
                                        <CardContent className="p-0">
                                            <div className="overflow-x-auto">
                                                <table className="table table-hover table-sm table-bordered mb-0">
                                                    <thead>
                                                        <tr className="table-light">
                                                            <th scope="col">License</th>
                                                            <th scope="col">Exporter</th>
                                                            <th scope="col" className="text-right">Purchase Cost</th>
                                                            <th scope="col" className="text-right">Debited CIF</th>
                                                            <th scope="col" className="text-right">Remaining CIF</th>
                                                            <th scope="col" className="text-right">Allocated Purchase</th>
                                                            <th scope="col" className="text-right">Realized Profit</th>
                                                            <th scope="col" className="text-right">Profit %</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {normSection.licenses.map((lic) => (
                                                            <tr key={lic.license_id}>
                                                                <td className="font-semibold">{lic.license_number}</td>
                                                                <td>{lic.exporter}</td>
                                                                <MoneyCell value={lic.purchase_cost} />
                                                                <MoneyCell value={lic.debited_cif} />
                                                                <MoneyCell value={lic.remaining_cif} />
                                                                <MoneyCell value={lic.allocated_purchase} />
                                                                <MoneyCell value={lic.realized_profit} tint />
                                                                <td className="text-right">{pct(lic.profit_pct)}</td>
                                                            </tr>
                                                        ))}
                                                    </tbody>
                                                </table>
                                            </div>
                                        </CardContent>
                                    </Card>

                                    {/* Item-wise Profit */}
                                    <Card className="mb-4">
                                        <CardHeader>
                                            <h5 className="mb-0 text-[14px] font-semibold">Item-wise Profit</h5>
                                        </CardHeader>
                                        <CardContent className="p-0">
                                            <div className="overflow-x-auto">
                                                <table className="table table-hover table-sm table-bordered mb-0">
                                                    <thead>
                                                        <tr className="table-light">
                                                            <th scope="col">License</th>
                                                            <th scope="col">Item</th>
                                                            <th scope="col" className="text-right">Qty Debited</th>
                                                            <th scope="col" className="text-right">Debited CIF</th>
                                                            <th scope="col" className="text-right">% Share</th>
                                                            <th scope="col" className="text-right">Allocated Purchase</th>
                                                            <th scope="col" className="text-right">Profit</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        {normSection.items.map((row, idx) => (
                                                            <tr key={`${row.license_id}-${row.item}-${idx}`}>
                                                                <td>{row.license_number}</td>
                                                                <td>{row.item}</td>
                                                                <td className="text-right">{formatIndianNumber(toNum(row.qty_debited), 3)}</td>
                                                                <MoneyCell value={row.debited_cif} />
                                                                <td className="text-right">{pct(row.pct_share)}</td>
                                                                <MoneyCell value={row.allocated_purchase} />
                                                                <MoneyCell value={row.profit} tint />
                                                            </tr>
                                                        ))}
                                                    </tbody>
                                                </table>
                                            </div>
                                        </CardContent>
                                    </Card>

                                    {/* Norm Summary */}
                                    <Card>
                                        <CardHeader>
                                            <h5 className="mb-0 text-[14px] font-semibold">Norm Summary</h5>
                                        </CardHeader>
                                        <CardContent className="p-0">
                                            <div className="overflow-x-auto">
                                                <table className="table table-sm table-bordered mb-0">
                                                    <thead>
                                                        <tr className="table-light">
                                                            <th scope="col" className="text-right">Total Purchase</th>
                                                            <th scope="col" className="text-right">Total Debited CIF</th>
                                                            <th scope="col" className="text-right">Total Profit</th>
                                                            <th scope="col" className="text-right">Margin %</th>
                                                        </tr>
                                                    </thead>
                                                    <tbody>
                                                        <tr className="font-semibold">
                                                            <MoneyCell value={normSection.summary.total_purchase} />
                                                            <MoneyCell value={normSection.summary.total_debited_cif} />
                                                            <MoneyCell value={normSection.summary.total_profit} tint />
                                                            <td className="text-right">{pct(normSection.summary.margin_pct)}</td>
                                                        </tr>
                                                    </tbody>
                                                </table>
                                            </div>
                                        </CardContent>
                                    </Card>
                                </div>
                            ))}

                            {/* Grand Summary */}
                            {grandSummary && (
                                <Card>
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
                                                        <th scope="col" className="text-right">Purchase</th>
                                                        <th scope="col" className="text-right">Debited CIF</th>
                                                        <th scope="col" className="text-right">Profit</th>
                                                        <th scope="col" className="text-right">Margin %</th>
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {grandSummary.rows.map((row) => (
                                                        <tr key={row.norm}>
                                                            <td className="font-semibold">{row.norm}</td>
                                                            <MoneyCell value={row.purchase} />
                                                            <MoneyCell value={row.debited_cif} />
                                                            <MoneyCell value={row.profit} tint />
                                                            <td className="text-right">{pct(row.margin_pct)}</td>
                                                        </tr>
                                                    ))}
                                                    <tr className="table-secondary font-bold">
                                                        <td>Grand Total</td>
                                                        <MoneyCell value={grandSummary.total.purchase} />
                                                        <MoneyCell value={grandSummary.total.debited_cif} />
                                                        <MoneyCell value={grandSummary.total.profit} tint />
                                                        <td className="text-right">{pct(grandSummary.total.margin_pct)}</td>
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
