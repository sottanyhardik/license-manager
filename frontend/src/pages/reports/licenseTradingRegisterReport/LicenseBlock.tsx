import { ChevronDown, ChevronRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import { money, pct, qty, toNum, formatSignedRupees } from "./formatters";

export type LicenseTransactionRow = {
    date: string;
    direction: string;
    invoice_number: string;
    from_company: string;
    to_company: string;
    item: string;
    purchase: unknown;
    sale: unknown;
    running_profit: unknown;
};

export type LicenseItemSummaryRow = {
    item: string;
    purchase_qty: unknown;
    sale_qty: unknown;
    purchase_value: unknown;
    sale_value: unknown;
    profit: unknown;
    margin_pct: unknown;
};

export type LicenseSummary = {
    purchase: unknown;
    sales: unknown;
    profit: unknown;
    margin_pct: unknown;
    status: string;
};

export type LicenseRow = {
    license_id: number | string;
    license_number: string;
    exporter: string;
    transactions: LicenseTransactionRow[];
    summary: LicenseSummary;
    item_summary: LicenseItemSummaryRow[];
};

/** Green "Closed" / amber "Open" pill — mirrors the size/weight of
 * `PurchaseStatusBadge` (ItemPivotReport.tsx) but reuses the shared shadcn
 * `Badge` primitive + its `success`/`warning` tone variants instead of a
 * bespoke inline-styled span, since this report has no existing bespoke
 * status-colour palette to match. */
function LicenseStatusBadge({ status }: { status: string }) {
    const closed = String(status).trim().toLowerCase() === "closed";
    return <Badge variant={closed ? "success" : "warning"}>{status || "—"}</Badge>;
}

/** Right-aligned money cell — tints green/red by sign (profit-style columns). */
function SignedMoneyCell({ value }: { value: unknown }) {
    const num = toNum(value);
    return (
        <td className={cn("text-right", num < 0 ? "text-destructive" : "text-success")}>
            {money(value)}
        </td>
    );
}

interface LicenseBlockProps {
    license: LicenseRow;
    expanded: boolean;
    onToggle: () => void;
}

/**
 * One License block within a Norm section: header (license number, exporter,
 * status badge) + chronological Transaction Register with running profit +
 * License Summary + License Item Summary (with a Totals row).
 *
 * Collapsed by default — a single report run can cover thousands of
 * licenses and tens of thousands of transactions across them, so the
 * register/summary tables are only mounted into the DOM while `expanded`,
 * not merely hidden with CSS, to keep the page responsive.
 */
export default function LicenseBlock({ license, expanded, onToggle }: LicenseBlockProps) {
    const totals = license.item_summary.reduce(
        (acc, row) => {
            acc.purchase_qty += toNum(row.purchase_qty);
            acc.sale_qty += toNum(row.sale_qty);
            acc.purchase_value += toNum(row.purchase_value);
            acc.sale_value += toNum(row.sale_value);
            acc.profit += toNum(row.profit);
            return acc;
        },
        { purchase_qty: 0, sale_qty: 0, purchase_value: 0, sale_value: 0, profit: 0 },
    );
    const totalMarginPct = totals.sale_value !== 0 ? (totals.profit / totals.sale_value) * 100 : 0;

    return (
        <Card className="mb-3 overflow-hidden">
            <button
                type="button"
                onClick={onToggle}
                aria-expanded={expanded}
                className="flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-muted/40"
            >
                <span className="flex min-w-0 items-center gap-2">
                    {expanded ? (
                        <ChevronDown className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                    ) : (
                        <ChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                    )}
                    <span className="truncate font-semibold">{license.license_number}</span>
                    <span className="truncate text-muted-foreground">{license.exporter}</span>
                </span>
                <LicenseStatusBadge status={license.summary.status} />
            </button>

            {expanded && (
                <CardContent className="border-t border-border p-0">
                    {/* Transaction Register */}
                    <div className="overflow-x-auto">
                        <table className="table table-hover table-sm table-bordered mb-0">
                            <thead>
                                <tr className="table-light">
                                    <th scope="col">Date</th>
                                    <th scope="col">Direction</th>
                                    <th scope="col">Invoice No</th>
                                    <th scope="col">From Company</th>
                                    <th scope="col">To Company</th>
                                    <th scope="col">Item</th>
                                    <th scope="col" className="text-right">Purchase</th>
                                    <th scope="col" className="text-right">Sale</th>
                                    <th scope="col" className="text-right">Running Profit</th>
                                </tr>
                            </thead>
                            <tbody>
                                {license.transactions.map((txn, idx) => (
                                    <tr key={`${license.license_id}-txn-${idx}`}>
                                        <td>{txn.date}</td>
                                        <td>{txn.direction}</td>
                                        <td>{txn.invoice_number}</td>
                                        <td>{txn.from_company}</td>
                                        <td>{txn.to_company}</td>
                                        <td>{txn.item}</td>
                                        <td className="text-right">{toNum(txn.purchase) ? money(txn.purchase) : "—"}</td>
                                        <td className="text-right">{toNum(txn.sale) ? money(txn.sale) : "—"}</td>
                                        <td
                                            className={cn(
                                                "text-right font-medium",
                                                toNum(txn.running_profit) < 0 ? "text-destructive" : "text-success",
                                            )}
                                        >
                                            {formatSignedRupees(txn.running_profit)}
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    {/* License Summary */}
                    <div className="overflow-x-auto border-t border-border">
                        <table className="table table-sm table-bordered mb-0">
                            <thead>
                                <tr className="table-light">
                                    <th scope="col" className="text-right">Purchase</th>
                                    <th scope="col" className="text-right">Sales</th>
                                    <th scope="col" className="text-right">Profit</th>
                                    <th scope="col" className="text-right">Margin %</th>
                                    <th scope="col">Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                <tr className="font-semibold">
                                    <td className="text-right">{money(license.summary.purchase)}</td>
                                    <td className="text-right">{money(license.summary.sales)}</td>
                                    <SignedMoneyCell value={license.summary.profit} />
                                    <td className="text-right">{pct(license.summary.margin_pct)}</td>
                                    <td><LicenseStatusBadge status={license.summary.status} /></td>
                                </tr>
                            </tbody>
                        </table>
                    </div>

                    {/* License Item Summary */}
                    <div className="overflow-x-auto border-t border-border">
                        <table className="table table-sm table-bordered mb-0">
                            <thead>
                                <tr className="table-light">
                                    <th scope="col">Item</th>
                                    <th scope="col" className="text-right">Purchase Qty</th>
                                    <th scope="col" className="text-right">Sale Qty</th>
                                    <th scope="col" className="text-right">Purchase Value</th>
                                    <th scope="col" className="text-right">Sale Value</th>
                                    <th scope="col" className="text-right">Profit</th>
                                    <th scope="col" className="text-right">Margin %</th>
                                </tr>
                            </thead>
                            <tbody>
                                {license.item_summary.map((row, idx) => (
                                    <tr key={`${license.license_id}-item-${idx}`}>
                                        <td>{row.item}</td>
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
                                    <td className="text-right">{qty(totals.purchase_qty)}</td>
                                    <td className="text-right">{qty(totals.sale_qty)}</td>
                                    <td className="text-right">{money(totals.purchase_value)}</td>
                                    <td className="text-right">{money(totals.sale_value)}</td>
                                    <SignedMoneyCell value={totals.profit} />
                                    <td className="text-right">{pct(totalMarginPct)}</td>
                                </tr>
                            </tbody>
                        </table>
                    </div>
                </CardContent>
            )}
        </Card>
    );
}
