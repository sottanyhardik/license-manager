import { AlertTriangle, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";
import { useLicenseOverviewInvoiceLedger } from "./useLicenseOverviewInvoiceLedger";
import { extractApiError, fmtDate, fmtNum, invoiceLedgerStatusVariant } from "./licenseOverviewHelpers";
import type { InvoiceLedgerRow } from "./types";

interface InvoiceLedgerTabProps {
    licenseId: string | number | undefined;
    isActive: boolean;
}

function InvoiceTable({ title, rows }: { title: string; rows: InvoiceLedgerRow[] }) {
    return (
        <div>
            <h3 className="mb-2 text-sm font-semibold text-foreground">{title}</h3>
            <div className="max-h-[calc(100vh-18rem)] overflow-auto rounded-lg border border-border/70 bg-card">
                <table className="w-full min-w-[760px] text-[13px]">
                    <thead className="sticky top-0 z-[1] bg-muted/95 text-[10.5px] uppercase tracking-wide text-muted-foreground backdrop-blur">
                        <tr>
                            <th scope="col" className="px-3 py-2 text-left font-semibold">Invoice Number</th>
                            <th scope="col" className="px-3 py-2 text-left font-semibold">Invoice Date</th>
                            <th scope="col" className="px-3 py-2 text-left font-semibold">Company</th>
                            <th scope="col" className="px-3 py-2 text-right font-semibold">Amount</th>
                            <th scope="col" className="px-3 py-2 text-right font-semibold">GST</th>
                            <th scope="col" className="px-3 py-2 text-right font-semibold">Total</th>
                            <th scope="col" className="px-3 py-2 text-left font-semibold">Status</th>
                        </tr>
                    </thead>
                    <tbody>
                        {rows.length === 0 && (
                            <tr>
                                <td colSpan={7} className="px-3 py-6 text-center text-muted-foreground">
                                    No invoices recorded.
                                </td>
                            </tr>
                        )}
                        {rows.map((row) => (
                            <tr key={row.invoice_number} className="border-t border-border/60 hover:bg-muted/30">
                                <td className="px-3 py-1.5 font-medium">{row.invoice_number}</td>
                                <td className="whitespace-nowrap px-3 py-1.5">{fmtDate(row.invoice_date)}</td>
                                <td className="px-3 py-1.5">{row.company_name ?? "—"}</td>
                                <td className="px-3 py-1.5 text-right tabular-nums">{fmtNum(row.amount)}</td>
                                {/* `gst` is always `null` on the wire — GST amount isn't tracked in
                                    this schema — so it is never rendered as `0` or blank. */}
                                <td className="px-3 py-1.5 text-right text-muted-foreground">Not tracked</td>
                                <td className="px-3 py-1.5 text-right font-medium tabular-nums">{fmtNum(row.total)}</td>
                                <td className="px-3 py-1.5">
                                    <Badge variant={invoiceLedgerStatusVariant(row.status)}>{row.status}</Badge>
                                </td>
                            </tr>
                        ))}
                    </tbody>
                </table>
            </div>
        </div>
    );
}

/**
 * Invoice Ledger tab — Purchase and Sale invoice tables from
 * `GET /licenses/<id>/overview-invoice-ledger/`, both already sorted
 * server-side by `invoice_date`. The warning banner is rendered only when
 * `warning.show_warning === true` (the key is always present regardless,
 * per the wire contract — `false` is explicit, never an omitted key).
 */
export default function InvoiceLedgerTab({ licenseId, isActive }: InvoiceLedgerTabProps) {
    const { data, isLoading, isError, error } = useLicenseOverviewInvoiceLedger(licenseId, isActive);

    if (!isActive) return null;

    if (isLoading) {
        return (
            <div className="flex items-center justify-center gap-2 py-16 text-sm text-muted-foreground">
                <Loader2 className="size-4 animate-spin" /> Loading invoice ledger…
            </div>
        );
    }

    if (isError || !data) {
        return (
            <Alert variant="destructive">
                <AlertTriangle className="size-4" />
                <AlertDescription>{extractApiError(error, "Failed to load invoice ledger.")}</AlertDescription>
            </Alert>
        );
    }

    return (
        <div className="space-y-3">
            {data.warning.show_warning && (
                <Alert variant="warning">
                    <AlertTriangle className="size-4" />
                    <AlertTitle>Attention</AlertTitle>
                    <AlertDescription>{data.warning.message}</AlertDescription>
                </Alert>
            )}
            <InvoiceTable title="Purchase Invoices" rows={data.purchase} />
            <InvoiceTable title="Sale Invoices" rows={data.sale} />
        </div>
    );
}
