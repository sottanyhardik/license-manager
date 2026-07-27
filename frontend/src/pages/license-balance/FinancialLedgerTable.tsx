import { cn } from "@/lib/utils";
import type { FinancialLedgerRow } from "./types";
import { financialLedgerRowClass, fmtDate, fmtInvoiceNumbers, fmtNum } from "./licenseBalanceHelpers";

interface FinancialLedgerTableProps {
    rows: FinancialLedgerRow[];
}

const HEADERS = [
    "Sr", "Date", "Type", "Doc Number", "BOE Number", "BOE Date", "Company", "Item",
    "Invoices", "Qty", "CIF USD", "CIF INR", "Credit", "Debit", "Running Balance", "Remarks",
];

/**
 * Section 1 — Financial Ledger. Hand-rolled `<table>` (not `DataTable.tsx`,
 * which doesn't support this many custom-styled columns) — same approach as
 * `pages/reconciliation/ComparisonTab.tsx`'s row-styling pattern, adapted to
 * a plain table since every row here needs its own semantic color by
 * `row_kind`.
 */
export default function FinancialLedgerTable({ rows }: FinancialLedgerTableProps) {
    return (
        <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
                <thead className="bg-muted/60 text-xs uppercase tracking-wide text-muted-foreground">
                    <tr>
                        {HEADERS.map((h) => (
                            <th key={h} scope="col" className="whitespace-nowrap px-3 py-2 text-left font-semibold">
                                {h}
                            </th>
                        ))}
                    </tr>
                </thead>
                <tbody>
                    {rows.length === 0 && (
                        <tr>
                            <td colSpan={HEADERS.length} className="px-3 py-6 text-center text-muted-foreground">
                                No ledger rows.
                            </td>
                        </tr>
                    )}
                    {rows.map((row) => (
                        <tr
                            key={row.sr}
                            className={cn("border-t border-border/60", financialLedgerRowClass(row.row_kind, row.mismatched))}
                        >
                            <td className="px-3 py-2">{row.sr}</td>
                            <td className="whitespace-nowrap px-3 py-2">{fmtDate(row.date)}</td>
                            <td className="whitespace-nowrap px-3 py-2 font-medium">{row.type}</td>
                            <td className="px-3 py-2">{row.document_number ?? "—"}</td>
                            <td className="px-3 py-2">{row.boe_number ?? "—"}</td>
                            <td className="whitespace-nowrap px-3 py-2">{fmtDate(row.boe_date)}</td>
                            <td className="px-3 py-2">{row.company ?? "—"}</td>
                            <td className="px-3 py-2">{row.item_name ?? "—"}</td>
                            <td className="px-3 py-2">{fmtInvoiceNumbers(row.invoice_numbers)}</td>
                            <td className="px-3 py-2 text-right">{fmtNum(row.qty)}</td>
                            <td className="px-3 py-2 text-right">{fmtNum(row.cif_usd)}</td>
                            <td className="px-3 py-2 text-right">{fmtNum(row.cif_inr)}</td>
                            <td className="px-3 py-2 text-right">{fmtNum(row.credit)}</td>
                            <td className="px-3 py-2 text-right">{fmtNum(row.debit)}</td>
                            <td className="px-3 py-2 text-right font-medium">{fmtNum(row.running_balance)}</td>
                            <td className="px-3 py-2">{row.remarks ?? "—"}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
}
