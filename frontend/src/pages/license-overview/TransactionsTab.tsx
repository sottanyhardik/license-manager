import { useState } from "react";
import { AlertTriangle, ChevronDown, ChevronRight, Loader2, RefreshCw } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import DebouncedSearchInput from "@/components/DebouncedSearchInput";
import DataPagination from "@/components/DataPagination";
import type {
    LicenceTransactionParams,
    LicenceTransactionProduct,
    LicenceTransactionQtyByUnit,
    LicenceTransactionRecord,
    LicenceTransactionRecordType,
    LicenceTransactionSummary,
    LicenceTransactionSupplierGroup,
} from "@/api/licenseApi";
import {
    useLicenseOverviewTransactionRecords,
    useLicenseOverviewTransactions,
} from "./useLicenseOverviewTransactions";
import { extractApiError, fmtDate, fmtNum } from "./licenseOverviewHelpers";

interface TransactionsTabProps {
    licenseId: string | number | undefined;
    isActive: boolean;
}

const ORDERING_OPTIONS: { value: string; label: string }[] = [
    { value: "-date", label: "Date (newest)" },
    { value: "date", label: "Date (oldest)" },
    { value: "record_number", label: "Record no. (A-Z)" },
    { value: "-record_number", label: "Record no. (Z-A)" },
    { value: "record_type", label: "Type" },
    { value: "-cif_fc", label: "CIF (high-low)" },
    { value: "cif_fc", label: "CIF (low-high)" },
    { value: "-qty", label: "Qty (high-low)" },
    { value: "qty", label: "Qty (low-high)" },
    { value: "status", label: "Status" },
];

const STATUS_OPTIONS = [
    "Dispute", "Frozen", "Reconciled", "Pending", "Linked to BOE", "Approved", "Allotted",
];

const SELECT_CLASS =
    "h-8 rounded-md border border-input bg-background px-2 text-xs focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring";

const groupKey = (supplierId: number | null, productKey: number) => `${supplierId ?? "null"}:${productKey}`;

function QtyText({ items }: { items: LicenceTransactionQtyByUnit[] }) {
    if (items.length === 0) return <>—</>;
    return <>{items.map((q) => `${fmtNum(q.qty)} ${q.unit ?? ""}`.trim()).join(", ")}</>;
}

/** Backend-computed summary shown verbatim; BOE and allotment buckets stay separate. */
function SummaryBlock({ summary }: { summary: LicenceTransactionSummary }) {
    return (
        <div className="flex flex-wrap gap-1.5 text-xs" data-testid="txn-summary">
            {summary.boe_buckets.map((b) => (
                <Badge key={`boe-${b.transaction_type}`} variant={b.transaction_type === "D" ? "warning" : "info"}>
                    BOE {b.transaction_type === "D" ? "Debit" : b.transaction_type === "C" ? "Credit" : b.transaction_type}
                    {" · "}{b.record_count} rec · CIF {fmtNum(b.cif_fc)} · <QtyText items={b.qty_by_unit} />
                </Badge>
            ))}
            {summary.allotment_buckets.map((b) => (
                <Badge
                    key={`alt-${b.allotment_type}-${b.allocation_basis}-${b.is_linked_to_boe}`}
                    variant={b.is_linked_to_boe ? "secondary" : "success"}
                >
                    Allotment {b.allotment_type}{b.is_linked_to_boe ? " (linked)" : ""}
                    {" · "}{b.record_count} rec · CIF {fmtNum(b.cif_fc)} · <QtyText items={b.qty_by_unit} />
                </Badge>
            ))}
            <Badge variant="outline">BOE debit CIF {fmtNum(summary.boe_debit_cif)}</Badge>
            <Badge variant="outline">Unlinked allotment CIF {fmtNum(summary.unlinked_allotment_cif)}</Badge>
            <Badge variant="outline">Linked allotment CIF {fmtNum(summary.linked_allotment_cif)}</Badge>
        </div>
    );
}

interface RecordsPanelProps {
    licenseId: string | number | undefined;
    supplierId: number | null;
    productKey: number;
    filters: LicenceTransactionParams;
}

function RecordsPanel({ licenseId, supplierId, productKey, filters }: RecordsPanelProps) {
    const [page, setPage] = useState(1);
    const [pageSize, setPageSize] = useState(25);
    const { data, isLoading, isError, error, refetch } = useLicenseOverviewTransactionRecords(licenseId, {
        ...filters,
        supplier_id: supplierId,
        product_key: productKey,
        page,
        page_size: pageSize,
    });

    if (isLoading) {
        return (
            <div className="flex items-center gap-2 px-3 py-3 text-xs text-muted-foreground">
                <Loader2 className="size-3.5 animate-spin" /> Loading records…
            </div>
        );
    }
    if (isError) {
        return (
            <Alert variant="destructive" className="m-2 w-auto">
                <AlertTriangle className="size-4" />
                <AlertDescription className="flex items-center justify-between gap-2">
                    {extractApiError(error, "Failed to load records.")}
                    <Button type="button" size="sm" variant="outline" onClick={() => refetch()}>Retry</Button>
                </AlertDescription>
            </Alert>
        );
    }
    const rows: LicenceTransactionRecord[] = data?.results ?? [];
    if (rows.length === 0) {
        return <p className="px-3 py-3 text-xs text-muted-foreground">No records match the filters.</p>;
    }
    return (
        <div>
            <div className="overflow-x-auto">
                <table className="w-full min-w-[760px] text-xs">
                    <thead className="bg-muted/60 uppercase tracking-wide text-muted-foreground">
                        <tr>
                            <th className="px-3 py-1.5 text-left">Type</th>
                            <th className="px-3 py-1.5 text-left">Number</th>
                            <th className="px-3 py-1.5 text-left">Date</th>
                            <th className="px-3 py-1.5 text-right">Qty</th>
                            <th className="px-3 py-1.5 text-right">CIF</th>
                            <th className="px-3 py-1.5 text-left">Status</th>
                            <th className="px-3 py-1.5 text-left">Invoice</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows.map((r) => (
                            <tr key={`${r.record_type}-${r.line_id}`} className="border-t border-border/60">
                                <td className="px-3 py-1.5">
                                    <Badge variant={r.record_type === "BOE" ? "warning" : "success"}>
                                        {r.record_type === "BOE" ? `BOE${r.transaction_type ? ` ${r.transaction_type}` : ""}` : "Allotment"}
                                    </Badge>
                                </td>
                                <td className="px-3 py-1.5 font-mono">{r.record_number || "—"}</td>
                                <td className="whitespace-nowrap px-3 py-1.5">{fmtDate(r.date)}</td>
                                <td className="whitespace-nowrap px-3 py-1.5 text-right tabular-nums">
                                    {fmtNum(r.qty)} {r.unit ?? ""}
                                </td>
                                <td className="px-3 py-1.5 text-right tabular-nums">{fmtNum(r.cif_fc)}</td>
                                <td className="px-3 py-1.5">{r.status}</td>
                                <td className="px-3 py-1.5">{r.invoice_no || "—"}</td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
            {(data?.total_pages ?? 1) > 1 || pageSize !== 25 ? (
                <div className="px-3 py-2">
                    <DataPagination
                        currentPage={data?.current_page ?? page}
                        totalPages={data?.total_pages ?? 1}
                        pageSize={pageSize}
                        totalItems={data?.count}
                        hasNext={(data?.current_page ?? page) < (data?.total_pages ?? 1)}
                        hasPrevious={(data?.current_page ?? page) > 1}
                        onPageChange={setPage}
                        onPageSizeChange={(s) => { setPageSize(s); setPage(1); }}
                    />
                </div>
            ) : null}
        </div>
    );
}

type ProductRow = LicenceTransactionSupplierGroup["products"][number];

function ProductRowItem({
    product, supplierId, expanded, onToggle, licenseId, filters,
}: {
    product: ProductRow;
    supplierId: number | null;
    expanded: boolean;
    onToggle: () => void;
    licenseId: string | number | undefined;
    filters: LicenceTransactionParams;
}) {
    const label = productLabel(product);
    return (
        <li className="border-t border-border/60">
            <button
                type="button"
                onClick={onToggle}
                aria-expanded={expanded}
                aria-label={`${expanded ? "Collapse" : "Expand"} ${label}`}
                className="flex w-full cursor-pointer flex-col gap-1.5 px-3 py-2 text-left hover:bg-muted/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
            >
                <span className="flex items-center gap-1.5 text-sm font-medium">
                    {expanded ? <ChevronDown className="size-4" aria-hidden="true" /> : <ChevronRight className="size-4" aria-hidden="true" />}
                    {product.serial_number != null && <span className="text-xs text-muted-foreground">SR {product.serial_number}</span>}
                    {label}
                </span>
                <SummaryBlock summary={product.summary} />
            </button>
            {expanded && (
                <div className="border-t border-border/60 bg-muted/10">
                    <RecordsPanel
                        licenseId={licenseId}
                        supplierId={supplierId}
                        productKey={product.product_key}
                        filters={filters}
                    />
                </div>
            )}
        </li>
    );
}

function productLabel(p: LicenceTransactionProduct): string {
    return p.product_label || p.description || "Unmapped product";
}

/**
 * Transactions tab — BOE and allotment lines grouped by supplier, then by
 * licence item. All summaries are computed by the backend
 * (`GET /licenses/<id>/overview-transactions/`) and shown verbatim; record
 * lines are fetched only when a supplier × product row is expanded.
 */
export default function TransactionsTab({ licenseId, isActive }: TransactionsTabProps) {
    const [search, setSearch] = useState("");
    const [recordType, setRecordType] = useState<LicenceTransactionRecordType | "">("");
    const [status, setStatus] = useState("");
    const [dateFrom, setDateFrom] = useState("");
    const [dateTo, setDateTo] = useState("");
    const [ordering, setOrdering] = useState("-date");
    const [page, setPage] = useState(1);
    const [pageSize, setPageSize] = useState(10);
    const [expanded, setExpanded] = useState<Set<string>>(new Set());

    const filters: LicenceTransactionParams = {
        search: search.trim() || undefined,
        record_type: recordType || undefined,
        status: status || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
        ordering,
    };

    const { data, isLoading, isError, error, refetch, isFetching } = useLicenseOverviewTransactions(
        licenseId,
        { ...filters, page, page_size: pageSize },
        isActive,
    );

    const resetPage = () => { setPage(1); setExpanded(new Set()); };
    const toggle = (key: string) =>
        setExpanded((prev) => {
            const next = new Set(prev);
            if (next.has(key)) next.delete(key);
            else next.add(key);
            return next;
        });

    if (!isActive) return null;

    const groups = data?.results ?? [];

    return (
        <div className="space-y-2">
            <div className="flex flex-wrap items-end gap-2 rounded-lg border border-border/60 bg-card px-3 py-2">
                <div className="w-full sm:w-64">
                    <DebouncedSearchInput
                        value={search}
                        onChange={(v: string) => { setSearch(v); resetPage(); }}
                        placeholder="Search number / supplier / invoice…"
                    />
                </div>
                <select aria-label="Record type" className={SELECT_CLASS} value={recordType}
                    onChange={(e) => { setRecordType(e.target.value as LicenceTransactionRecordType | ""); resetPage(); }}>
                    <option value="">All types</option>
                    <option value="BOE">BOE</option>
                    <option value="ALLOTMENT">Allotment</option>
                </select>
                <select aria-label="Status" className={SELECT_CLASS} value={status}
                    onChange={(e) => { setStatus(e.target.value); resetPage(); }}>
                    <option value="">All statuses</option>
                    {STATUS_OPTIONS.map((s) => <option key={s} value={s}>{s}</option>)}
                </select>
                <input type="date" aria-label="Date from" className={SELECT_CLASS} value={dateFrom}
                    onChange={(e) => { setDateFrom(e.target.value); resetPage(); }} />
                <input type="date" aria-label="Date to" className={SELECT_CLASS} value={dateTo}
                    onChange={(e) => { setDateTo(e.target.value); resetPage(); }} />
                <select aria-label="Order by" className={SELECT_CLASS} value={ordering}
                    onChange={(e) => { setOrdering(e.target.value); resetPage(); }}>
                    {ORDERING_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
                </select>
                {isFetching && !isLoading && <Loader2 className="size-4 animate-spin text-muted-foreground" aria-label="Refreshing" />}
            </div>

            {isLoading ? (
                <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
                    <Loader2 className="size-4 animate-spin" /> Loading transactions…
                </div>
            ) : isError ? (
                <Alert variant="destructive">
                    <AlertTriangle className="size-4" />
                    <AlertDescription className="flex items-center justify-between gap-2">
                        {extractApiError(error, "Failed to load transactions.")}
                        <Button type="button" size="sm" variant="outline" onClick={() => refetch()}>
                            <RefreshCw className="size-3.5" /> Retry
                        </Button>
                    </AlertDescription>
                </Alert>
            ) : groups.length === 0 ? (
                <p className="py-10 text-center text-sm text-muted-foreground">No transactions found for this licence.</p>
            ) : (
                <>
                    {data && (
                        <div className="rounded-lg border border-border/60 bg-card px-3 py-2">
                            <p className="mb-1 text-xs font-bold uppercase tracking-widest text-muted-foreground">Licence totals</p>
                            <SummaryBlock summary={data.totals} />
                        </div>
                    )}
                    {groups.map((g) => (
                        <section
                            key={g.supplier_id ?? "none"}
                            className="overflow-hidden rounded-lg border border-border/70 bg-card"
                            aria-label={g.supplier_label ?? "No supplier recorded"}
                        >
                            <header className="flex flex-col gap-1.5 bg-muted/40 px-3 py-2">
                                <h3 className="text-sm font-semibold">
                                    {g.supplier_label || g.supplier_name || "No supplier recorded"}
                                    {g.supplier_iec ? <span className="ml-2 text-xs font-normal text-muted-foreground">IEC {g.supplier_iec}</span> : null}
                                </h3>
                                <SummaryBlock summary={g.summary} />
                            </header>
                            <ul>
                                {g.products.map((p) => {
                                    const key = groupKey(g.supplier_id, p.product_key);
                                    return (
                                        <ProductRowItem
                                            key={key}
                                            product={p}
                                            supplierId={g.supplier_id}
                                            expanded={expanded.has(key)}
                                            onToggle={() => toggle(key)}
                                            licenseId={licenseId}
                                            filters={filters}
                                        />
                                    );
                                })}
                            </ul>
                        </section>
                    ))}
                    <DataPagination
                        currentPage={data?.current_page ?? page}
                        totalPages={data?.total_pages ?? 1}
                        pageSize={pageSize}
                        totalItems={data?.count}
                        hasNext={(data?.current_page ?? page) < (data?.total_pages ?? 1)}
                        hasPrevious={(data?.current_page ?? page) > 1}
                        onPageChange={(p) => { setPage(p); setExpanded(new Set()); }}
                        onPageSizeChange={(s) => { setPageSize(s); resetPage(); }}
                    />
                </>
            )}
        </div>
    );
}
