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
 * `GET /licenses/<id>/overview-allotments/`. Always renders a table
 * (decision D3) regardless of row count.
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
    // Display-only sums. Gross includes BOE-linked allotments (already in BOE
    // CIF); outstanding is the engine's ALLOTMENT CIF component.
    const grossCif = rows.reduce((s, a) => s + (Number(a.cif_fc) || 0), 0);
    const outstandingCif = rows.reduce((s, a) => s + (Number(a.outstanding_cif_fc) || 0), 0);

    return (
        <div>
                <div className="max-h-[calc(100vh-17rem)] overflow-auto rounded-lg border border-border/70 bg-card">
                    <table className="w-full min-w-[900px] text-sm">
                        <thead className="sticky top-0 z-[1] bg-muted/95 text-xs uppercase tracking-wide text-muted-foreground backdrop-blur">
                            <tr>
                                <SortableHeader label="Allotment Number" sortKey="allotment_number" activeKey={sort.key} direction={sort.direction} onSort={handleSort} />
                                <SortableHeader label="Date" sortKey="date" activeKey={sort.key} direction={sort.direction} onSort={handleSort} />
                                <SortableHeader label="Customer" sortKey="customer" activeKey={sort.key} direction={sort.direction} onSort={handleSort} />
                                <SortableHeader label="Product" sortKey="product" activeKey={sort.key} direction={sort.direction} onSort={handleSort} />
                                <SortableHeader label="Quantity" sortKey="quantity" activeKey={sort.key} direction={sort.direction} onSort={handleSort} align="right" />
                                <SortableHeader label="CIF" sortKey="cif_fc" activeKey={sort.key} direction={sort.direction} onSort={handleSort} align="right" />
                                <SortableHeader label="Status" sortKey="status" activeKey={sort.key} direction={sort.direction} onSort={handleSort} />
                                <th scope="col" className="whitespace-nowrap px-3 py-2 text-right font-semibold">Rate</th>
                            </tr>
                        </thead>
                        <tbody>
                            {rows.map((a) => {
                                const rate = a.quantity > 0 ? Number(a.cif_fc) / a.quantity : 0;
                                return (
                                <tr key={a.allotment_number} className="border-t border-border/60 hover:bg-muted/30">
                                    <td className="px-3 py-1.5 font-mono text-xs"><span className="inline-flex items-center gap-1.5">
                                            {a.allotment_number}
                                            <button
                                                type="button"
                                                onClick={() => copyToClipboard(a.allotment_number)}
                                                className="cursor-pointer text-muted-foreground/60 hover:text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring"
                                                title="Copy allotment number"
                                                aria-label="Copy allotment number"
                                            >
                                                <ClipboardCopy className="size-3" />
                                            </button>
                                        </span>
                                    </td>
                                    <td className="whitespace-nowrap px-3 py-1.5">{fmtDate(a.date)}</td>
                                    <td className="px-3 py-1.5">{a.customer ?? "—"}</td>
                                    <td className="px-3 py-1.5">{a.product ?? "—"}</td>
                                    <td className="px-3 py-1.5 text-right tabular-nums">{fmtNum(a.quantity)}</td>
                                    <td className="px-3 py-1.5 text-right tabular-nums">{fmtNum(a.cif_fc)}</td>
                                    <td className="px-3 py-1.5">
                                        <Badge variant={overviewAllotmentStatusVariant(a.status)}>{a.status}</Badge>
                                    </td>
                                    <td className="px-3 py-1.5 text-right tabular-nums">{rate > 0 ? fmtNum(rate) : "—"}</td>
                                </tr>
                                );
                            })}
                        </tbody>
                    </table>
                </div>

            <div className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-primary/20 bg-primary/5 px-3 py-2">
                <span className="flex items-center gap-1.5 text-xs font-bold uppercase tracking-widest text-primary">
                    <Package className="size-3.5" /> Outstanding Allotted
                </span>
                <div className="flex items-center gap-4">
                    {/* Gross qty (incl. BOE-linked); outstanding-quantity semantics await OD-QTY. */}
                    <span className="text-xs text-primary">Gross qty: <b>{fmtNum(totalQty)}</b></span>
                    <span className="text-xs text-primary">
                        Gross allotted (incl. BOE-linked): <b className="tabular-nums">{fmtNum(grossCif)}</b>
                    </span>
                    <span className="text-xs text-primary">
                        Outstanding CIF:{" "}
                        <b className="text-base tabular-nums" data-testid="allotments-outstanding-cif">{fmtNum(outstandingCif)}</b>
                    </span>
                </div>
            </div>
        </div>
    );
}
