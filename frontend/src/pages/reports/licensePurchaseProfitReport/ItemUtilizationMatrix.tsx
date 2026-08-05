import { Fragment } from "react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { formatIndianNumber } from "@/utils/numberFormatter";
import { formatDate } from "@/utils/dateFormatter";
import type { LicenseSummaryRow } from "../LicensePurchaseProfitReport";

/** One dynamic item column's debit figures — `qty` is a physical quantity
 * (kg), never currency; `cif`/`bill` are money (USD / INR respectively). */
export type ItemMatrixCell = { qty: number; cif: number; bill: number };

/** A license row from the existing License Summary table, extended with its
 * per-Import-Item-Name debit figures. Never recomputed client-side — always
 * read verbatim off `reportData.item_matrix.rows[i]`. */
export type ItemMatrixRow = LicenseSummaryRow & { items: Record<string, ItemMatrixCell> };

/** Grand-total figures for the 6 static numeric columns (Purchase Amount
 * through Balance CIF) — the SAME `summary`-derived totals the License
 * Summary table's own footer/StatCards show, threaded down as a prop
 * rather than recomputed here. */
export type ItemMatrixStaticTotals = {
    purchaseAmount: unknown;
    purchaseUsd: unknown;
    saleAmount: unknown;
    saleUsd: unknown;
    profitLoss: unknown;
    balanceCif: unknown;
};

export interface ItemUtilizationMatrixProps {
    headers: string[];
    rows: ItemMatrixRow[];
    totals: Record<string, ItemMatrixCell>;
    staticTotals: ItemMatrixStaticTotals;
}

const EMPTY_CELL: ItemMatrixCell = { qty: 0, cif: 0, bill: 0 };

function toNum(value: unknown): number {
    const num = Number(value);
    return Number.isFinite(num) ? num : 0;
}

function money(value: unknown): string {
    return formatIndianNumber(toNum(value), 2);
}

/** Physical quantity (e.g. kg) — deliberately NOT run through the money
 * formatter above; this is a quantity, not currency. */
function qty(value: unknown): string {
    return toNum(value).toLocaleString("en-IN", { minimumFractionDigits: 3, maximumFractionDigits: 3 });
}

/**
 * Pivot-style matrix showing, per qualifying license, how much of each
 * purchased Import Item has been debited on the trade ledger (SALE-direction
 * lines). Rendered entirely from `reportData.item_matrix` — no client-side
 * aggregation of any kind; the grand-total row reads `totals` verbatim.
 *
 * Follows `ItemPivotReport.tsx`'s grouped 2-row sticky-header pattern (one
 * `<th colSpan={3}>` per item, sticky `<thead>`/first column) and
 * `ItemReportTable.tsx`'s sticky `<tfoot>` grand-total pattern.
 */
export default function ItemUtilizationMatrix({ headers, rows, totals, staticTotals }: ItemUtilizationMatrixProps) {
    if (headers.length === 0) {
        return (
            <Card>
                <div className="border-b border-border px-4 py-3">
                    <h5 className="mb-0 text-[14px] font-semibold">Item Utilization Matrix</h5>
                </div>
                <CardContent className="py-10 text-center text-muted-foreground">
                    No import items to display
                </CardContent>
            </Card>
        );
    }

    return (
        <Card className="mt-6">
            <div className="border-b border-border px-4 py-3">
                <h5 className="mb-0 text-[14px] font-semibold">Item Utilization Matrix</h5>
            </div>
            <CardContent className="p-0">
                <div className="max-h-[70vh] w-full overflow-auto">
                    <table className="w-full border-collapse text-sm">
                        <thead className="sticky top-0 z-20">
                            <tr>
                                <th rowSpan={2} scope="col" className="sticky left-0 z-30 bg-muted px-3 py-2 text-left text-xs font-semibold text-muted-foreground">License No.</th>
                                <th rowSpan={2} scope="col" className="bg-muted px-3 py-2 text-left text-xs font-semibold text-muted-foreground">License Date</th>
                                <th rowSpan={2} scope="col" className="bg-muted px-3 py-2 text-left text-xs font-semibold text-muted-foreground">Expiry Date</th>
                                <th rowSpan={2} scope="col" className="bg-muted px-3 py-2 text-left text-xs font-semibold text-muted-foreground">Exporter</th>
                                <th rowSpan={2} scope="col" className="bg-muted px-3 py-2 text-left text-xs font-semibold text-muted-foreground">Norm(s)</th>
                                <th rowSpan={2} scope="col" className="bg-muted px-3 py-2 text-left text-xs font-semibold text-muted-foreground">Purchase From</th>
                                <th rowSpan={2} scope="col" className="bg-muted px-3 py-2 text-right text-xs font-semibold text-muted-foreground">Purchase Amount</th>
                                <th rowSpan={2} scope="col" className="bg-muted px-3 py-2 text-right text-xs font-semibold text-muted-foreground">Purchase $</th>
                                <th rowSpan={2} scope="col" className="bg-muted px-3 py-2 text-right text-xs font-semibold text-muted-foreground">Sale Amount</th>
                                <th rowSpan={2} scope="col" className="bg-muted px-3 py-2 text-right text-xs font-semibold text-muted-foreground">Sale $</th>
                                <th rowSpan={2} scope="col" className="bg-muted px-3 py-2 text-right text-xs font-semibold text-muted-foreground">Profit / Loss</th>
                                <th rowSpan={2} scope="col" className="bg-muted px-3 py-2 text-right text-xs font-semibold text-muted-foreground">Balance CIF</th>
                                {headers.map((header) => (
                                    <th
                                        key={header}
                                        colSpan={3}
                                        scope="colgroup"
                                        className="border-l-2 border-border bg-muted px-3 py-2 text-center text-xs font-semibold text-muted-foreground"
                                    >
                                        {header}
                                    </th>
                                ))}
                            </tr>
                            <tr>
                                {headers.map((header) => (
                                    <Fragment key={header}>
                                        <th scope="col" className="border-l-2 border-border bg-muted px-3 py-1.5 text-right text-[11px] font-semibold text-muted-foreground">Qty</th>
                                        <th scope="col" className="bg-muted px-3 py-1.5 text-right text-[11px] font-semibold text-muted-foreground">CIF $</th>
                                        <th scope="col" className="bg-muted px-3 py-1.5 text-right text-[11px] font-semibold text-muted-foreground">Bill ₹</th>
                                    </Fragment>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {rows.map((row, idx) => (
                                <tr
                                    key={row.license_number}
                                    className={cn(
                                        "border-b border-border/60 hover:bg-muted/60",
                                        idx % 2 === 1 && "bg-muted/25",
                                    )}
                                >
                                    <td className="sticky left-0 z-10 bg-inherit px-3 py-2 font-semibold">{row.license_number}</td>
                                    <td className="whitespace-nowrap px-3 py-2">{formatDate(row.license_date)}</td>
                                    <td className="whitespace-nowrap px-3 py-2">{formatDate(row.expiry_date)}</td>
                                    <td className="max-w-[220px] truncate px-3 py-2" title={row.exporter}>{row.exporter}</td>
                                    <td className="px-3 py-2">
                                        <div className="flex flex-wrap gap-1">
                                            {row.norms.map((n) => (
                                                <Badge key={n} variant="secondary">{n}</Badge>
                                            ))}
                                        </div>
                                    </td>
                                    <td className="max-w-[220px] truncate px-3 py-2" title={row.purchase_from}>{row.purchase_from}</td>
                                    <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">{money(row.purchase_amount)}</td>
                                    <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">{money(row.purchase_usd)}</td>
                                    <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">{money(row.sale_amount)}</td>
                                    <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">{money(row.sale_usd)}</td>
                                    <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">{money(row.profit_loss)}</td>
                                    <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">{money(row.balance_cif)}</td>
                                    {headers.map((header) => {
                                        const cell = row.items[header] ?? EMPTY_CELL;
                                        return (
                                            <Fragment key={header}>
                                                <td className="whitespace-nowrap border-l-2 border-border/60 px-3 py-2 text-right tabular-nums">{qty(cell.qty)}</td>
                                                <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">{money(cell.cif)}</td>
                                                <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">{money(cell.bill)}</td>
                                            </Fragment>
                                        );
                                    })}
                                </tr>
                            ))}
                        </tbody>
                        <tfoot className="sticky bottom-0 z-20">
                            <tr className="border-t-2 border-border bg-muted font-bold">
                                <td colSpan={6} className="sticky left-0 z-10 bg-muted px-3 py-2 text-right">Grand Total</td>
                                <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">{money(staticTotals.purchaseAmount)}</td>
                                <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">{money(staticTotals.purchaseUsd)}</td>
                                <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">{money(staticTotals.saleAmount)}</td>
                                <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">{money(staticTotals.saleUsd)}</td>
                                <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">{money(staticTotals.profitLoss)}</td>
                                <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">{money(staticTotals.balanceCif)}</td>
                                {headers.map((header) => {
                                    const cell = totals[header] ?? EMPTY_CELL;
                                    return (
                                        <Fragment key={header}>
                                            <td className="whitespace-nowrap border-l-2 border-border px-3 py-2 text-right tabular-nums">{qty(cell.qty)}</td>
                                            <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">{money(cell.cif)}</td>
                                            <td className="whitespace-nowrap px-3 py-2 text-right tabular-nums">{money(cell.bill)}</td>
                                        </Fragment>
                                    );
                                })}
                            </tr>
                        </tfoot>
                    </table>
                </div>
            </CardContent>
        </Card>
    );
}
