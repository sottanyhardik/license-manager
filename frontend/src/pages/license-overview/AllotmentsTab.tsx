import { useMemo, useState } from "react";
import { AlertTriangle, ClipboardCopy, Loader2, Package } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useLicenseOverviewAllotments } from "./useLicenseOverviewAllotments";
import { extractApiError, fmtDate, fmtNum, overviewAllotmentStatusVariant, sortRows, type SortState } from "./licenseOverviewHelpers";
import SortableHeader from "./SortableHeader";
import type { LicenseOverviewAllotmentRow } from "./types";

interface AllotmentsTabProps {
    licenseId: string | number | undefined;
    isActive: boolean;
}

type SortKey = keyof LicenseOverviewAllotmentRow;

// Cards when the count is small enough to browse visually, table otherwise —
// same threshold convention as `pages/masters/tables/LedgerTab.tsx`'s
// `AllotmentSection` (`CARD_THRESHOLD = 10`).
const CARD_THRESHOLD = 10;

async function copyToClipboard(text: string) {
    try {
        await navigator.clipboard.writeText(text);
        toast.success("Copied");
    } catch {
        toast.error("Failed to copy");
    }
}

/**
 * Allotments tab — one row per allotment linked to this license, from
 * `GET /licenses/<id>/overview-allotments/`. Render pattern (cards for small
 * counts, dense table for large ones) copied from `LedgerTab.tsx`'s private
 * `AllotmentSection`, not imported from it (that component is specific to
 * the Master List's ledger tab and stays there unmodified).
 */
export default function AllotmentsTab({ licenseId, isActive }: AllotmentsTabProps) {
    const { data, isLoading, isError, error } = useLicenseOverviewAllotments(licenseId, isActive);
    const [sort, setSort] = useState<SortState<SortKey>>({ key: null, direction: "asc" });

    const handleSort = (key: SortKey) => {
        setSort((prev) => ({
            key,
            direction: prev.key === key && prev.direction === "asc" ? "desc" : "asc",
        }));
    };

    const rows = useMemo(
        () => sortRows(data ?? [], sort, (row, key) => row[key] as string | number | null),
        [data, sort]
    );

    if (!isActive) return null;

    if (isLoading) {
        return (
            <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" /> Loading allotments…
            </div>
        );
    }

    if (isError) {
        return (
            <Alert variant="destructive">
                <AlertTriangle className="size-4" />
                <AlertDescription>{extractApiError(error, "Failed to load allotments.")}</AlertDescription>
            </Alert>
        );
    }

    if (rows.length === 0) {
        return <p className="py-10 text-center text-sm text-muted-foreground">No allotments linked to this licence.</p>;
    }

    const totalQty = rows.reduce((s, a) => s + (Number(a.quantity) || 0), 0);
    const totalCif = rows.reduce((s, a) => s + (Number(a.cif_fc) || 0), 0);

    return (
        <div>
            {rows.length <= CARD_THRESHOLD ? (
                <div className="grid gap-2 sm:grid-cols-2 xl:grid-cols-3">
                    {rows.map((a) => {
                        const rate = a.quantity > 0 ? Number(a.cif_fc) / a.quantity : 0;
                        return (
                            <div key={a.allotment_number} className="group rounded-xl border border-border/60 bg-card p-3 transition-shadow hover:shadow-sm">
                                <div className="mb-2 flex items-start justify-between gap-2">
                                    <div className="flex items-center gap-1.5">
                                        <span className="font-mono text-sm font-semibold text-foreground">{a.allotment_number}</span>
                                        <button
                                            type="button"
                                            onClick={() => copyToClipboard(a.allotment_number)}
                                            className="text-muted-foreground/50 hover:text-muted-foreground cursor-pointer opacity-0 transition-opacity group-hover:opacity-100"
                                            title="Copy allotment number"
                                        >
                                            <ClipboardCopy className="size-3" />
                                        </button>
                                    </div>
                                    <Badge variant={overviewAllotmentStatusVariant(a.status)}>{a.status}</Badge>
                                </div>
                                <div className="mb-1.5 truncate text-xs text-muted-foreground" title={a.customer ?? ""}>{a.customer ?? "—"}</div>
                                <div className="mb-2 truncate text-[10.5px] text-muted-foreground/70" title={a.product ?? ""}>{a.product ?? "—"}</div>
                                <div className="flex items-center gap-2 text-[10.5px] text-muted-foreground/70">{fmtDate(a.date)}</div>
                                <div className="mt-2 grid grid-cols-2 gap-2 border-t border-border/40 pt-2">
                                    <div>
                                        <div className="text-[9.5px] font-semibold uppercase tracking-wider text-muted-foreground">Qty</div>
                                        <div className="tabular-nums text-[11.5px] font-semibold text-foreground">{fmtNum(a.quantity)}</div>
                                    </div>
                                    <div>
                                        <div className="text-[9.5px] font-semibold uppercase tracking-wider text-muted-foreground">Rate</div>
                                        <div className="tabular-nums text-[11.5px] font-semibold text-foreground">{rate > 0 ? fmtNum(rate) : "—"}</div>
                                    </div>
                                </div>
                                <div className="mt-2 flex items-center justify-between rounded-lg bg-violet-50/60 px-2 py-1 dark:bg-violet-500/10">
                                    <span className="text-[9.5px] font-semibold uppercase tracking-wider text-muted-foreground">CIF</span>
                                    <span className="tabular-nums text-[11.5px] font-bold text-violet-700 dark:text-violet-400">{fmtNum(a.cif_fc)}</span>
                                </div>
                            </div>
                        );
                    })}
                </div>
            ) : (
                <div className="max-h-[calc(100vh-17rem)] overflow-auto rounded-lg border border-border/70 bg-card">
                    <table className="w-full min-w-[800px] text-[13px]">
                        <thead className="sticky top-0 z-[1] bg-muted/95 text-[10.5px] uppercase tracking-wide text-muted-foreground backdrop-blur">
                            <tr>
                                <SortableHeader label="Allotment Number" sortKey="allotment_number" activeKey={sort.key} direction={sort.direction} onSort={handleSort} />
                                <SortableHeader label="Date" sortKey="date" activeKey={sort.key} direction={sort.direction} onSort={handleSort} />
                                <SortableHeader label="Customer" sortKey="customer" activeKey={sort.key} direction={sort.direction} onSort={handleSort} />
                                <SortableHeader label="Product" sortKey="product" activeKey={sort.key} direction={sort.direction} onSort={handleSort} />
                                <SortableHeader label="Quantity" sortKey="quantity" activeKey={sort.key} direction={sort.direction} onSort={handleSort} align="right" />
                                <SortableHeader label="CIF" sortKey="cif_fc" activeKey={sort.key} direction={sort.direction} onSort={handleSort} align="right" />
                                <SortableHeader label="Status" sortKey="status" activeKey={sort.key} direction={sort.direction} onSort={handleSort} />
                            </tr>
                        </thead>
                        <tbody>
                            {rows.map((a) => (
                            <tr key={a.allotment_number} className="border-t border-border/60 hover:bg-muted/30">
                                    <td className="px-3 py-1.5 font-mono text-xs">{a.allotment_number}</td>
                                    <td className="whitespace-nowrap px-3 py-1.5">{fmtDate(a.date)}</td>
                                    <td className="px-3 py-1.5">{a.customer ?? "—"}</td>
                                    <td className="px-3 py-1.5">{a.product ?? "—"}</td>
                                    <td className="px-3 py-1.5 text-right tabular-nums">{fmtNum(a.quantity)}</td>
                                    <td className="px-3 py-1.5 text-right tabular-nums">{fmtNum(a.cif_fc)}</td>
                                    <td className="px-3 py-1.5">
                                        <Badge variant={overviewAllotmentStatusVariant(a.status)}>{a.status}</Badge>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}

            <div className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2">
                <span className="flex items-center gap-1.5 text-[10.5px] font-bold uppercase tracking-widest text-primary">
                    <Package className="size-3.5" /> Total Allotted
                </span>
                <div className="flex items-center gap-4">
                    <span className="text-[11px] text-primary">Qty: <b>{fmtNum(totalQty)}</b></span>
                    <span className="text-base font-bold tabular-nums text-primary">{fmtNum(totalCif)}</span>
                </div>
            </div>
        </div>
    );
}
