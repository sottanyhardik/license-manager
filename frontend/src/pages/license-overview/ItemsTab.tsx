import { useMemo, useState } from "react";
import { AlertTriangle, Loader2 } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { useLicenseOverviewItems } from "./useLicenseOverviewItems";
import { extractApiError, fmtNum, sortRows, type SortState } from "./licenseOverviewHelpers";
import SortableHeader from "./SortableHeader";
import type { LicenseOverviewItemRow } from "./types";

interface ItemsTabProps {
    licenseId: string | number | undefined;
    isActive: boolean;
}

type SortKey = keyof LicenseOverviewItemRow;

/**
 * Items tab — one row per import item's balance breakdown, from
 * `GET /licenses/<id>/overview-items/`. `balance_qty`/`balance_cif` here are
 * a NEW, display-only figure (`total - debited - allotted`) that is
 * intentionally distinct from the "available"/"balance" figures shown
 * elsewhere (e.g. the license accordion row) — see `types.ts`.
 *
 * Row count is small (per-item, not per-BOE), so this always renders as a
 * plain table with client-side sort — no cards-vs-table threshold needed.
 */
export default function ItemsTab({ licenseId, isActive }: ItemsTabProps) {
    const { data, isLoading, isError, error } = useLicenseOverviewItems(licenseId, isActive);
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
                <Loader2 className="size-4 animate-spin" /> Loading items…
            </div>
        );
    }

    if (isError) {
        return (
            <Alert variant="destructive">
                <AlertTriangle className="size-4" />
                <AlertDescription>{extractApiError(error, "Failed to load items.")}</AlertDescription>
            </Alert>
        );
    }

    return (
        <div className="max-h-[calc(100vh-15rem)] overflow-auto rounded-lg border border-border/70 bg-card">
            <table className="w-full min-w-[1120px] text-[13px]">
                <thead className="sticky top-0 z-[1] bg-muted/95 text-[10.5px] uppercase tracking-wide text-muted-foreground backdrop-blur">
                    <tr>
                        <SortableHeader label="Product Description" sortKey="description" activeKey={sort.key} direction={sort.direction} onSort={handleSort} />
                        <SortableHeader label="HSN Code" sortKey="hs_code" activeKey={sort.key} direction={sort.direction} onSort={handleSort} />
                        <SortableHeader label="Unit" sortKey="unit" activeKey={sort.key} direction={sort.direction} onSort={handleSort} />
                        <SortableHeader label="Total Qty" sortKey="total_qty" activeKey={sort.key} direction={sort.direction} onSort={handleSort} align="right" />
                        <SortableHeader label="Total CIF" sortKey="total_cif" activeKey={sort.key} direction={sort.direction} onSort={handleSort} align="right" />
                        <SortableHeader label="Debited Qty" sortKey="debited_qty" activeKey={sort.key} direction={sort.direction} onSort={handleSort} align="right" />
                        <SortableHeader label="Debited CIF" sortKey="debited_cif" activeKey={sort.key} direction={sort.direction} onSort={handleSort} align="right" />
                        <SortableHeader label="Allotted Qty" sortKey="allotted_qty" activeKey={sort.key} direction={sort.direction} onSort={handleSort} align="right" />
                        <SortableHeader label="Allotted CIF" sortKey="allotted_cif" activeKey={sort.key} direction={sort.direction} onSort={handleSort} align="right" />
                        <SortableHeader label="Balance Qty" sortKey="balance_qty" activeKey={sort.key} direction={sort.direction} onSort={handleSort} align="right" />
                        <SortableHeader label="Balance CIF" sortKey="balance_cif" activeKey={sort.key} direction={sort.direction} onSort={handleSort} align="right" />
                    </tr>
                </thead>
                <tbody>
                    {rows.length === 0 && (
                        <tr>
                            <td colSpan={11} className="px-3 py-6 text-center text-muted-foreground">
                                No import items on this licence.
                            </td>
                        </tr>
                    )}
                    {rows.map((row) => (
                        <tr key={row.id} className="border-t border-border/60 hover:bg-muted/30">
                            <td className="max-w-[280px] truncate px-3 py-1.5" title={row.description ?? ""}>{row.description ?? "—"}</td>
                            <td className="px-3 py-1.5">{row.hs_code ?? "—"}</td>
                            <td className="px-3 py-1.5">{row.unit ?? "—"}</td>
                            <td className="px-3 py-1.5 text-right tabular-nums">{fmtNum(row.total_qty)}</td>
                            <td className="px-3 py-1.5 text-right tabular-nums">{fmtNum(row.total_cif)}</td>
                            <td className="px-3 py-1.5 text-right tabular-nums">{fmtNum(row.debited_qty)}</td>
                            <td className="px-3 py-1.5 text-right tabular-nums">{fmtNum(row.debited_cif)}</td>
                            <td className="px-3 py-1.5 text-right tabular-nums">{fmtNum(row.allotted_qty)}</td>
                            <td className="px-3 py-1.5 text-right tabular-nums">{fmtNum(row.allotted_cif)}</td>
                            <td className="px-3 py-1.5 text-right font-medium tabular-nums">{fmtNum(row.balance_qty)}</td>
                            <td className="px-3 py-1.5 text-right font-medium tabular-nums">{fmtNum(row.balance_cif)}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
