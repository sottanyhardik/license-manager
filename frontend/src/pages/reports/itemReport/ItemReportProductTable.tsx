import { Fragment, useId, useMemo, useState } from "react";
import { AlertTriangle, ArrowDown, ArrowUp, CheckCircle2, ChevronDown, ChevronRight } from "lucide-react";
import DataPagination from "@/components/DataPagination";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableFooter, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { cn } from "@/lib/utils";
import ProductDrilldown from "./ProductDrilldown";
import { formatDecimal, isNotAttributed } from "./productFormat";
import type { ProductMetric, ProductMetrics, ProductReconciliation, ProductRow } from "./productTypes";
import type { ReportFilterValues } from "./reportQueryString";

type SortKey = "item_name" | "sion" | "license_count" | ProductMetric;

const METRIC_COLUMNS: { key: ProductMetric; label: string }[] = [
    { key: "total_qty", label: "Total Qty" },
    { key: "total_cif", label: "Total CIF" },
    { key: "allotted_qty", label: "Allotted Qty" },
    { key: "allotted_cif", label: "Allotted CIF" },
    { key: "debited_qty", label: "Debited Qty" },
    { key: "debited_cif", label: "Debited CIF" },
    { key: "invoice_cif", label: "Invoice CIF" },
    { key: "balance_qty", label: "Balance Qty" },
    { key: "balance_cif", label: "Balance CIF" },
    { key: "planned_qty", label: "Planned Qty" },
    { key: "planned_cif", label: "Planned CIF" },
];
// expander + item + sion + hsn + licences + metrics + status
const COLUMN_COUNT = 5 + METRIC_COLUMNS.length + 1;
const INITIAL_PAGE_SIZE = 25;

function sortValue(row: ProductRow, key: SortKey): string | number | null {
    if (key === "item_name") return row.item_name.toLowerCase();
    if (key === "sion") return row.sion.toLowerCase();
    if (key === "license_count") return row.license_count;
    const raw = row[key];
    return raw === null || raw === undefined ? null : Number(raw);
}

export function ReconciliationBadge({ reconciliation }: { reconciliation: ProductReconciliation }) {
    if (reconciliation.reconciled) {
        return (
            <Badge variant="success" data-testid="reconciliation-badge">
                <CheckCircle2 aria-hidden="true" /> Reconciled with Item Pivot
            </Badge>
        );
    }
    const diffs = Object.entries(reconciliation.metrics).filter(([, m]) => m.difference !== null && Number(m.difference) !== 0);
    return (
        <div role="alert" data-testid="reconciliation-badge" className="rounded-md border border-warning/40 bg-warning/10 px-3 py-2 text-xs text-warning">
            <p className="flex items-center gap-1 font-medium"><AlertTriangle className="size-3.5" aria-hidden="true" /> Does not reconcile with Item Pivot</p>
            <ul className="mt-1 list-disc pl-5">
                {diffs.map(([metric, m]) => (
                    <li key={metric}>
                        {metric}: Item Report {formatDecimal(m.item_report)} vs Item Pivot {formatDecimal(m.item_pivot)} (difference {formatDecimal(m.difference)})
                    </li>
                ))}
            </ul>
        </div>
    );
}

type Props = {
    products: ProductRow[];
    totals: ProductMetrics;
    /** Filters forwarded to the drill-down request. */
    filters: ReportFilterValues;
};

export default function ItemReportProductTable({ products, totals, filters }: Props) {
    const baseId = useId();
    const [sort, setSort] = useState<{ key: SortKey; dir: "asc" | "desc" } | null>(null);
    const [pageState, setPageState] = useState({ page: 1, pageSize: INITIAL_PAGE_SIZE, source: products });
    const [expanded, setExpanded] = useState<Set<string>>(new Set());

    // New dataset (filters / planning status change) → page 1 and collapse drill-downs.
    // Render-time derived-state reset rather than an effect.
    let { page } = pageState;
    const { pageSize } = pageState;
    if (pageState.source !== products) {
        page = 1;
        setPageState({ page: 1, pageSize, source: products });
        setExpanded(new Set());
    }

    const sorted = useMemo(() => {
        if (!sort) return products;
        const dir = sort.dir === "asc" ? 1 : -1;
        return [...products].sort((a, b) => {
            const av = sortValue(a, sort.key);
            const bv = sortValue(b, sort.key);
            if (av === bv) return 0;
            if (av === null) return 1; // missing always last
            if (bv === null) return -1;
            return (av < bv ? -1 : 1) * dir;
        });
    }, [products, sort]);

    const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
    const currentPage = Math.min(page, totalPages);
    const pageRows = sorted.slice((currentPage - 1) * pageSize, currentPage * pageSize);

    const toggleSort = (key: SortKey) =>
        setSort((prev) => (prev?.key === key ? { key, dir: prev.dir === "asc" ? "desc" : "asc" } : { key, dir: "asc" }));
    const toggleRow = (key: string) =>
        setExpanded((prev) => {
            const next = new Set(prev);
            if (next.has(key)) next.clear(); else next.add(key);
            return next;
        });

    const sortHead = (key: SortKey, label: string, numeric: boolean) => {
        const active = sort?.key === key;
        return (
            <TableHead
                key={key}
                className={cn("px-2 py-2 text-xs", numeric && "text-right")}
                aria-sort={active ? (sort.dir === "asc" ? "ascending" : "descending") : "none"}
            >
                <button type="button" onClick={() => toggleSort(key)} className="inline-flex items-center gap-1 rounded hover:text-foreground focus-visible:outline-2 focus-visible:outline-ring">
                    {label}
                    {active && (sort.dir === "asc" ? <ArrowUp className="size-3" aria-hidden="true" /> : <ArrowDown className="size-3" aria-hidden="true" />)}
                </button>
            </TableHead>
        );
    };

    return (
        <>
            <Table>
                <TableHeader className="bg-muted/50">
                    <TableRow>
                        <TableHead className="w-8 px-2"><span className="sr-only">Expand</span></TableHead>
                        {sortHead("item_name", "Item Name", false)}
                        {sortHead("sion", "SION", false)}
                        <TableHead className="px-2 py-2 text-xs">HSN codes</TableHead>
                        {sortHead("license_count", "Licences", true)}
                        {METRIC_COLUMNS.map((c) => sortHead(c.key, c.label, true))}
                        <TableHead className="px-2 py-2 text-xs">Status</TableHead>
                    </TableRow>
                </TableHeader>
                <TableBody>
                    {pageRows.map((row) => {
                        const isOpen = expanded.has(row.key);
                        const panelId = `${baseId}-${row.key.replace(/[^a-zA-Z0-9_-]/g, "_")}`;
                        const notAttributed = isNotAttributed(row.item_name);
                        const hsn = row.hsn_codes.join(", ");
                        return (
                            <Fragment key={row.key}>
                                <TableRow className={cn(notAttributed && "bg-warning/5 italic text-muted-foreground")} data-not-attributed={notAttributed || undefined}>
                                    <TableCell className="px-2">
                                        <button
                                            type="button"
                                            aria-expanded={isOpen}
                                            aria-controls={panelId}
                                            aria-label={`${isOpen ? "Collapse" : "Expand"} ${row.item_name} ${row.sion}`}
                                            onClick={() => toggleRow(row.key)}
                                            className="rounded p-0.5 hover:bg-muted focus-visible:outline-2 focus-visible:outline-ring"
                                        >
                                            {isOpen ? <ChevronDown className="size-4" aria-hidden="true" /> : <ChevronRight className="size-4" aria-hidden="true" />}
                                        </button>
                                    </TableCell>
                                    <TableCell className="px-2 py-1.5 font-medium">
                                        <span>{row.item_name}</span>
                                        {row.units.length > 0 && <span className="ml-1 text-xs font-normal text-muted-foreground">({row.units.join(", ")})</span>}
                                        {row.mixed_units && (
                                            <Badge variant="warning" className="ml-2" title={`Quantities mix units: ${row.units.join(", ")}`}>
                                                <AlertTriangle aria-hidden="true" /> Mixed units
                                            </Badge>
                                        )}
                                    </TableCell>
                                    <TableCell className="px-2 py-1.5">{row.sion || "—"}</TableCell>
                                    <TableCell className="max-w-[160px] truncate px-2 py-1.5" title={hsn}>{hsn || "—"}</TableCell>
                                    <TableCell className="px-2 py-1.5 text-right tabular-nums">{row.license_count}</TableCell>
                                    {METRIC_COLUMNS.map((c) => (
                                        <TableCell key={c.key} className="px-2 py-1.5 text-right tabular-nums">
                                            {formatDecimal(row[c.key])}
                                        </TableCell>
                                    ))}
                                    <TableCell className="px-2 py-1.5">
                                        {notAttributed ? <Badge variant="outline">Not attributed</Badge> : row.is_planned ? <Badge variant="success">Planned</Badge> : <Badge variant="secondary">Unplanned</Badge>}
                                    </TableCell>
                                </TableRow>
                                {isOpen && (
                                    <TableRow id={panelId} className="bg-muted/20 hover:bg-muted/20">
                                        <TableCell colSpan={COLUMN_COUNT} className="px-3 py-3">
                                            <ProductDrilldown productKey={row.key} filters={filters} />
                                        </TableCell>
                                    </TableRow>
                                )}
                            </Fragment>
                        );
                    })}
                </TableBody>
                <TableFooter>
                    <TableRow data-testid="product-totals">
                        <TableCell />
                        <TableCell className="px-2 py-2" colSpan={3}>Totals</TableCell>
                        <TableCell />
                        {METRIC_COLUMNS.map((c) => (
                            <TableCell key={c.key} className="px-2 py-2 text-right tabular-nums">{formatDecimal(totals[c.key])}</TableCell>
                        ))}
                        <TableCell />
                    </TableRow>
                </TableFooter>
            </Table>
            <DataPagination
                currentPage={currentPage}
                totalPages={totalPages}
                pageSize={pageSize}
                hasNext={currentPage < totalPages}
                hasPrevious={currentPage > 1}
                totalItems={sorted.length}
                onPageChange={(p: number) => setPageState((s) => ({ ...s, page: p }))}
                onPageSizeChange={(size: number) => setPageState((s) => ({ ...s, page: 1, pageSize: size }))}
            />
        </>
    );
}
