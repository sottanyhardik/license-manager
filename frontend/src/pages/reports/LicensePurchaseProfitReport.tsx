import { useId, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import {
    ArrowDown, ArrowDownCircle, ArrowUp, ArrowUpDown, Building2, CalendarRange, FileBarChart2, FileSpreadsheet,
    FileText, Inbox, Loader2, Receipt, RotateCcw, Search, SlidersHorizontal, Tag, TrendingUpDown, TriangleAlert, Wallet,
} from "lucide-react";
import AsyncSelectField from "@/components/AsyncSelectField";
import StatCard from "@/components/StatCard";
import { formatIndianCompact, formatIndianNumber } from "@/utils/numberFormatter";
import { formatDate } from "@/utils/dateFormatter";
import { useLicensePurchaseProfitReportFilters, LICENSE_PURCHASE_PROFIT_NORM_OPTIONS } from "./licensePurchaseProfitReport/useLicensePurchaseProfitReportFilters";
import { useLicensePurchaseProfitReportData } from "./licensePurchaseProfitReport/useLicensePurchaseProfitReportData";
import ExcludeLicenseNumberInput from "./licensePurchaseProfitReport/ExcludeLicenseNumberInput";
import ItemUtilizationMatrix, { type ItemMatrixCell, type ItemMatrixRow } from "./licensePurchaseProfitReport/ItemUtilizationMatrix";

/** Parses defensively before formatting/arithmetic — the API emits plain
 * JSON numbers, but this stays resilient to a stray string slipping through. */
function toNum(value: unknown): number {
    const num = Number(value);
    return Number.isFinite(num) ? num : 0;
}

function money(value: unknown): string {
    return formatIndianNumber(toNum(value), 2);
}

export type LicenseSummaryRow = {
    license_number: string;
    license_date: string | null;
    expiry_date: string | null;
    exporter: string;
    norms: string[];
    purchase_from: string;
    purchase_amount: unknown;
    purchase_usd: unknown;
    sale_amount: unknown;
    sale_usd: unknown;
    profit_loss: unknown;
    trade_balance_usd: unknown;
};

// Matches the Display Dataset envelope convention (see
// src/types/reportEnvelope.ts / backend/apps/core/reports/envelope.py) —
// `summary` here, `licenses` as this report's own row-list key below.
type ReportSummary = {
    total_licenses: unknown;
    purchase_amount: unknown;
    purchase_usd: unknown;
    trade_balance_usd: unknown;
    total_sale_usd: unknown;
    total_sale_amount: unknown;
    total_profit_loss: unknown;
};

type ItemMatrix = {
    headers: string[];
    rows: ItemMatrixRow[];
    totals: Record<string, ItemMatrixCell>;
};

type ReportData = {
    summary: ReportSummary;
    licenses: LicenseSummaryRow[];
    item_matrix: ItemMatrix;
};

type SortKey = "license_number" | "license_date" | "expiry_date" | "exporter" | "norms" | "purchase_from" | "purchase_amount" | "purchase_usd" | "sale_amount" | "sale_usd" | "profit_loss" | "trade_balance_usd";

const COLUMNS: { key: SortKey; label: string; align?: "right" }[] = [
    { key: "license_number", label: "License No." },
    { key: "license_date", label: "License Date" },
    { key: "expiry_date", label: "Expiry Date" },
    { key: "exporter", label: "Exporter" },
    { key: "norms", label: "Norm(s)" },
    { key: "purchase_from", label: "Purchase From" },
    { key: "purchase_amount", label: "Purchase Amount", align: "right" },
    { key: "purchase_usd", label: "Purchase $", align: "right" },
    { key: "sale_amount", label: "Sale Amount", align: "right" },
    { key: "sale_usd", label: "Sale $", align: "right" },
    { key: "profit_loss", label: "Profit / Loss", align: "right" },
    { key: "trade_balance_usd", label: "Trade Balance ($)", align: "right" },
];

function sortValue(row: LicenseSummaryRow, key: SortKey): string | number {
    switch (key) {
        case "purchase_amount":
        case "purchase_usd":
        case "sale_amount":
        case "sale_usd":
        case "profit_loss":
        case "trade_balance_usd":
            return toNum(row[key]);
        case "norms":
            return row.norms.join(", ").toLowerCase();
        case "license_date":
        case "expiry_date":
            return row[key] ?? "";
        default:
            return String(row[key] ?? "").toLowerCase();
    }
}

/** Right-aligned money cell. */
function MoneyCell({ value }: { value: unknown }) {
    return <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">{money(value)}</td>;
}

function SortableHeader({ column, sortKey, sortDir, onSort }: {
    column: { key: SortKey; label: string; align?: "right" };
    sortKey: SortKey;
    sortDir: "asc" | "desc";
    onSort: (key: SortKey) => void;
}) {
    const active = sortKey === column.key;
    const Icon = active ? (sortDir === "asc" ? ArrowUp : ArrowDown) : ArrowUpDown;
    return (
        <th
            scope="col"
            className={cn(
                "sticky top-0 z-10 bg-muted px-3 py-2 text-xs font-semibold text-muted-foreground",
                column.align === "right" ? "text-right" : "text-left",
                column.key === "license_number" && "sticky left-0 z-20",
            )}
        >
            <button
                type="button"
                onClick={() => onSort(column.key)}
                className={cn(
                    "inline-flex items-center gap-1 hover:text-foreground",
                    column.align === "right" && "flex-row-reverse",
                )}
            >
                {column.label}
                <Icon className={cn("size-3.5", active ? "text-foreground" : "text-muted-foreground/50")} aria-hidden="true" />
            </button>
        </th>
    );
}

/** Compact stacked label — small, tight margin, keeps the filter grid dense. */
function FilterLabel({ htmlFor, icon: Icon, children }: { htmlFor: string; icon: typeof Tag; children: React.ReactNode }) {
    return (
        <Label htmlFor={htmlFor} className="mb-1 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
            <Icon className="size-3.5" aria-hidden="true" />
            {children}
        </Label>
    );
}

export default function LicensePurchaseProfitReport() {
    const navigate = useNavigate();

    const {
        fromDate, setFromDate, toDate, setToDate,
        norm, setNorm, licenseNumber, setLicenseNumber,
        excludeLicenseNumber, setExcludeLicenseNumber,
        exporter, handleExporterChange,
        hasActiveFilters, handleClearFilters,
        debouncedFilters,
    } = useLicensePurchaseProfitReportFilters();

    const {
        reportData, isInitialLoading, isRefetching, error, downloading, canApply,
        refetch, resetReport, exportExcel, exportPdf,
    } = useLicensePurchaseProfitReportData(debouncedFilters);

    const [tableSearch, setTableSearch] = useState("");
    const [sortKey, setSortKey] = useState<SortKey>("license_number");
    const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");

    const fromDateId = useId();
    const toDateId = useId();
    const normId = useId();
    const licenseNumberId = useId();
    const excludeLicenseNumberId = useId();

    const data = reportData as ReportData | null;
    // Stabilize the reference: `data?.licenses ?? []` would otherwise
    // create a fresh empty array every render while `data` is null, making
    // every `useMemo` below think its input changed on each render.
    const licenseSummary = useMemo(() => data?.licenses ?? [], [data]);

    // The whole point of the Builder->DTO architecture: the web UI never
    // recomputes totals the backend already computed — read them straight
    // from `reportData.summary`, falling back to 0 while there's no data.
    const totals = {
        count: toNum(data?.summary?.total_licenses),
        purchaseAmount: toNum(data?.summary?.purchase_amount),
        purchaseUsd: toNum(data?.summary?.purchase_usd),
        tradeBalanceUsd: toNum(data?.summary?.trade_balance_usd),
        totalSaleUsd: toNum(data?.summary?.total_sale_usd),
        totalSaleAmount: toNum(data?.summary?.total_sale_amount),
        totalProfitLoss: toNum(data?.summary?.total_profit_loss),
    };

    // Item Utilization Matrix — driven entirely by `reportData.item_matrix`;
    // never aggregated/recomputed client-side.
    const itemMatrix = data?.item_matrix;
    const itemMatrixHeaders = itemMatrix?.headers ?? [];
    const itemMatrixRows = itemMatrix?.rows ?? [];
    const itemMatrixTotals = itemMatrix?.totals ?? {};

    const visibleRows = useMemo(() => {
        const q = tableSearch.trim().toLowerCase();
        const filtered = q
            ? licenseSummary.filter(
                  (lic) => lic.license_number.toLowerCase().includes(q) || lic.exporter.toLowerCase().includes(q),
              )
            : licenseSummary;
        const dir = sortDir === "asc" ? 1 : -1;
        return [...filtered].sort((a, b) => {
            const av = sortValue(a, sortKey);
            const bv = sortValue(b, sortKey);
            if (av < bv) return -1 * dir;
            if (av > bv) return 1 * dir;
            return 0;
        });
    }, [licenseSummary, tableSearch, sortKey, sortDir]);

    const toggleSort = (key: SortKey) => {
        if (key === sortKey) {
            setSortDir((d) => (d === "asc" ? "desc" : "asc"));
        } else {
            setSortKey(key);
            setSortDir("asc");
        }
    };

    const handleReset = () => {
        handleClearFilters();
        resetReport();
        setTableSearch("");
    };

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
            </div>

            {/* Filter toolbar */}
            <Card className="mb-6">
                <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3">
                    <h5 className="mb-0 flex items-center gap-2 text-[14px] font-semibold">
                        <SlidersHorizontal className="size-4" aria-hidden="true" />
                        Filters
                    </h5>
                    <div className="flex items-center gap-2">
                        <Button variant="ghost" size="sm" onClick={handleReset} disabled={!hasActiveFilters}>
                            <RotateCcw className="size-3.5" aria-hidden="true" />
                            Reset
                        </Button>
                    </div>
                </div>
                <CardContent className="p-4">
                    <div className="grid grid-cols-1 gap-3 md:grid-cols-3 xl:grid-cols-5">
                        <div>
                            <FilterLabel htmlFor={fromDateId} icon={CalendarRange}>From Date</FilterLabel>
                            <Input id={fromDateId} type="date" value={fromDate} onChange={(e) => setFromDate(e.target.value)} />
                        </div>

                        <div>
                            <FilterLabel htmlFor={toDateId} icon={CalendarRange}>To Date</FilterLabel>
                            <Input id={toDateId} type="date" value={toDate} onChange={(e) => setToDate(e.target.value)} />
                        </div>

                        <div>
                            <FilterLabel htmlFor={normId} icon={Tag}>Norm</FilterLabel>
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
                            <div className="mb-1 flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
                                <Building2 className="size-3.5" aria-hidden="true" />
                                Exporter
                            </div>
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

                        <div>
                            <FilterLabel htmlFor={licenseNumberId} icon={Search}>License Number</FilterLabel>
                            <Input
                                id={licenseNumberId}
                                value={licenseNumber}
                                onChange={(e) => setLicenseNumber(e.target.value)}
                                placeholder="Search License Number..."
                            />
                        </div>

                        <div className="md:col-span-3 xl:col-span-5">
                            <FilterLabel htmlFor={excludeLicenseNumberId} icon={FileText}>Exclude License Number</FilterLabel>
                            <ExcludeLicenseNumberInput
                                id={excludeLicenseNumberId}
                                value={excludeLicenseNumber}
                                onChange={setExcludeLicenseNumber}
                            />
                        </div>
                    </div>
                </CardContent>
            </Card>

            {/* Report body */}
            {!canApply && (
                <Card>
                    <CardContent className="flex flex-col items-center gap-3 py-16 text-center">
                        <FileBarChart2 className="size-10 text-muted-foreground" aria-hidden="true" />
                        <h5 className="text-foreground">License Purchase &amp; Profit Report</h5>
                        <p className="max-w-sm text-muted-foreground">Select a date range to view the report.</p>
                    </CardContent>
                </Card>
            )}

            {canApply && isInitialLoading && (
                <Card>
                    <div className="border-b border-border px-4 py-3">
                        <h5 className="mb-0 text-[14px] font-semibold">License Summary</h5>
                    </div>
                    <CardContent className="p-0">
                        <div className="w-full overflow-auto">
                            <table className="w-full border-collapse text-sm" aria-busy="true" aria-label="Loading License Summary">
                                <thead>
                                    <tr>
                                        {COLUMNS.map((column) => (
                                            <th
                                                key={column.key}
                                                scope="col"
                                                className={cn(
                                                    "bg-muted px-3 py-2 text-left text-xs font-semibold text-muted-foreground",
                                                    column.align === "right" && "text-right",
                                                )}
                                            >
                                                {column.label}
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {Array.from({ length: 6 }).map((_, rowIdx) => (
                                        <tr key={rowIdx} className="border-b border-border/60">
                                            {COLUMNS.map((column) => (
                                                <td key={column.key} className="px-3 py-2">
                                                    <Skeleton className="h-4 w-full" />
                                                </td>
                                            ))}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    </CardContent>
                </Card>
            )}

            {canApply && !isInitialLoading && error && (
                <Card>
                    <CardContent className="flex flex-col items-center gap-3 py-16 text-center">
                        <TriangleAlert className="size-10 text-destructive" aria-hidden="true" />
                        <h5 className="text-destructive">Failed to Load Report</h5>
                        <p className="max-w-sm text-muted-foreground">{error}</p>
                        <Button onClick={refetch}>
                            <RotateCcw className="size-4" aria-hidden="true" />
                            Retry
                        </Button>
                    </CardContent>
                </Card>
            )}

            {canApply && !isInitialLoading && !error && licenseSummary.length === 0 && (
                <Card>
                    <CardContent className="py-16 text-center">
                        <Inbox className="mx-auto size-10 text-muted-foreground" aria-hidden="true" />
                        <h5 className="mt-3 text-muted-foreground">No licenses found</h5>
                        <p className="text-muted-foreground">Try adjusting your filters — a different date range, norm, license number, excluded licenses, or exporter.</p>
                    </CardContent>
                </Card>
            )}

            {canApply && !isInitialLoading && !error && licenseSummary.length > 0 && (
                <>
                    {/* Summary cards — read straight from `reportData.summary`;
                        never recomputed client-side. */}
                    <div className="mb-6 grid grid-cols-1 gap-3 md:grid-cols-4 xl:grid-cols-7">
                        <StatCard label="Total Licenses" value={totals.count} icon={FileBarChart2} tone="primary" compact />
                        <StatCard
                            label="Purchase Amount (₹)"
                            value={money(totals.purchaseAmount)}
                            secondaryValue={formatIndianCompact(totals.purchaseAmount)}
                            title={money(totals.purchaseAmount)}
                            icon={Building2}
                            tone="success"
                            compact
                        />
                        <StatCard
                            label="Purchase $"
                            value={money(totals.purchaseUsd)}
                            secondaryValue={formatIndianCompact(totals.purchaseUsd)}
                            title={money(totals.purchaseUsd)}
                            icon={Tag}
                            tone="info"
                            compact
                        />
                        <StatCard
                            label="Total Sale Amount"
                            value={money(totals.totalSaleAmount)}
                            secondaryValue={formatIndianCompact(totals.totalSaleAmount)}
                            title={money(totals.totalSaleAmount)}
                            icon={Receipt}
                            tone="neutral"
                            compact
                        />
                        <StatCard
                            label="Total Sale $"
                            value={money(totals.totalSaleUsd)}
                            secondaryValue={formatIndianCompact(totals.totalSaleUsd)}
                            title={money(totals.totalSaleUsd)}
                            icon={ArrowDownCircle}
                            tone="danger"
                            compact
                        />
                        <StatCard
                            label="Total Profit / Loss"
                            value={money(totals.totalProfitLoss)}
                            secondaryValue={formatIndianCompact(totals.totalProfitLoss)}
                            title={money(totals.totalProfitLoss)}
                            icon={TrendingUpDown}
                            tone="warning"
                            compact
                        />
                        <StatCard
                            label="Trade Balance ($)"
                            value={money(totals.tradeBalanceUsd)}
                            secondaryValue={formatIndianCompact(totals.tradeBalanceUsd)}
                            title={money(totals.tradeBalanceUsd)}
                            icon={Wallet}
                            tone="warning"
                            compact
                        />
                    </div>

                    {/* Table toolbar + License Summary */}
                    <Card>
                        {isRefetching && <div className="h-0.5 animate-pulse bg-primary" aria-hidden="true" />}
                        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-border px-4 py-3">
                            <h5 className="mb-0 text-[14px] font-semibold">License Summary</h5>
                            <div className="flex items-center gap-2">
                                <div className="relative">
                                    <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
                                    <Input
                                        value={tableSearch}
                                        onChange={(e) => setTableSearch(e.target.value)}
                                        placeholder="Search..."
                                        className="h-8 w-48 pl-8"
                                    />
                                </div>
                                <Button variant="outline" size="sm" onClick={exportExcel} disabled={downloading}>
                                    {downloading ? <Loader2 className="size-3.5 animate-spin" /> : <FileSpreadsheet className="size-3.5" />}
                                    Excel
                                </Button>
                                <Button variant="outline" size="sm" onClick={exportPdf} disabled={downloading}>
                                    {downloading ? <Loader2 className="size-3.5 animate-spin" /> : <FileText className="size-3.5" />}
                                    PDF
                                </Button>
                            </div>
                        </div>
                        <CardContent className="p-0">
                            <div className="max-h-[70vh] w-full overflow-auto">
                                <table className="w-full border-collapse text-sm">
                                    <thead>
                                        <tr>
                                            {COLUMNS.map((column) => (
                                                <SortableHeader key={column.key} column={column} sortKey={sortKey} sortDir={sortDir} onSort={toggleSort} />
                                            ))}
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {visibleRows.map((lic, idx) => (
                                            <tr
                                                key={lic.license_number}
                                                className={cn(
                                                    "border-b border-border/60 hover:bg-muted/60",
                                                    idx % 2 === 1 && "bg-muted/25",
                                                )}
                                            >
                                                <td className="sticky left-0 z-10 bg-inherit px-3 py-2 font-semibold">{lic.license_number}</td>
                                                <td className="whitespace-nowrap px-3 py-2">{formatDate(lic.license_date)}</td>
                                                <td className="whitespace-nowrap px-3 py-2">{formatDate(lic.expiry_date)}</td>
                                                <td className="max-w-[220px] truncate px-3 py-2" title={lic.exporter}>{lic.exporter}</td>
                                                <td className="px-3 py-2">
                                                    <div className="flex flex-wrap gap-1">
                                                        {lic.norms.map((n) => (
                                                            <Badge key={n} variant="secondary">{n}</Badge>
                                                        ))}
                                                    </div>
                                                </td>
                                                <td className="max-w-[220px] truncate px-3 py-2" title={lic.purchase_from}>{lic.purchase_from}</td>
                                                <MoneyCell value={lic.purchase_amount} />
                                                <MoneyCell value={lic.purchase_usd} />
                                                <MoneyCell value={lic.sale_amount} />
                                                <MoneyCell value={lic.sale_usd} />
                                                <MoneyCell value={lic.profit_loss} />
                                                <MoneyCell value={lic.trade_balance_usd} />
                                            </tr>
                                        ))}
                                    </tbody>
                                    <tfoot className="sticky bottom-0 z-20">
                                        <tr className="border-t-2 border-border bg-muted font-bold">
                                            <td colSpan={6} className="sticky left-0 z-10 bg-muted px-3 py-2 text-right">Grand Total</td>
                                            <MoneyCell value={totals.purchaseAmount} />
                                            <MoneyCell value={totals.purchaseUsd} />
                                            <MoneyCell value={totals.totalSaleAmount} />
                                            <MoneyCell value={totals.totalSaleUsd} />
                                            <MoneyCell value={totals.totalProfitLoss} />
                                            <MoneyCell value={totals.tradeBalanceUsd} />
                                        </tr>
                                    </tfoot>
                                </table>
                            </div>
                        </CardContent>
                    </Card>

                    <ItemUtilizationMatrix
                        headers={itemMatrixHeaders}
                        rows={itemMatrixRows}
                        totals={itemMatrixTotals}
                        staticTotals={{
                            purchaseAmount: totals.purchaseAmount,
                            purchaseUsd: totals.purchaseUsd,
                            saleAmount: totals.totalSaleAmount,
                            saleUsd: totals.totalSaleUsd,
                            profitLoss: totals.totalProfitLoss,
                            tradeBalanceUsd: totals.tradeBalanceUsd,
                        }}
                    />
                </>
            )}
        </div>
    );
}
