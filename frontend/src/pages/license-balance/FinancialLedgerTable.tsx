import { Fragment, useState } from "react";
import { ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import type { FinancialLedgerChildRow, FinancialLedgerRow } from "./types";
import { financialLedgerRowClass, fmtDate, fmtInvoiceNumbers, fmtNum } from "./licenseBalanceHelpers";

interface FinancialLedgerTableProps {
    rows: FinancialLedgerRow[];
}

const HEADERS = [
    "Sr", "Date", "Type", "Doc Number", "BOE Number", "BOE Date", "Company", "Item",
    "Invoices", "Qty", "CIF USD", "CIF INR", "Credit", "Debit", "Running Balance", "Remarks",
];

/** One informational child row nested under a "boe_allocation" parent —
 * always blank Credit/Debit/Running Balance (see `types.ts`'s
 * `FinancialLedgerChildRow` docstring). */
function ChildRow({ child }: { child: FinancialLedgerChildRow }) {
    return (
        <tr className="border-t border-border/40 bg-muted/40 text-muted-foreground">
            <td className="px-3 py-1.5" />
            <td className="px-3 py-1.5" />
            <td className="whitespace-nowrap px-3 py-1.5 pl-6 italic">↳ {child.type}</td>
            <td className="px-3 py-1.5" />
            <td className="px-3 py-1.5">{child.boe_number ?? "—"}</td>
            <td className="whitespace-nowrap px-3 py-1.5">{fmtDate(child.boe_date)}</td>
            <td className="px-3 py-1.5">{child.company ?? "—"}</td>
            <td className="px-3 py-1.5">{child.item_name ?? "—"}</td>
            <td className="px-3 py-1.5">{fmtInvoiceNumbers(child.invoice_numbers)}</td>
            <td className="px-3 py-1.5 text-right">{fmtNum(child.qty)}</td>
            <td className="px-3 py-1.5 text-right">{fmtNum(child.cif_usd)}</td>
            <td className="px-3 py-1.5 text-right">{fmtNum(child.cif_inr)}</td>
            <td className="px-3 py-1.5 text-right">—</td>
            <td className="px-3 py-1.5 text-right">—</td>
            <td className="px-3 py-1.5 text-right">—</td>
            <td className="px-3 py-1.5">
                <span className="font-medium">{child.status}</span>
                {child.remarks ? ` — ${child.remarks}` : ""}
            </td>
        </tr>
    );
}

/**
 * Section 1 — Financial Ledger. Hand-rolled `<table>` (not `DataTable.tsx`,
 * which doesn't support this many custom-styled columns) — same approach as
 * `pages/reconciliation/ComparisonTab.tsx`'s row-styling pattern, adapted to
 * a plain table since every row here needs its own semantic color by
 * `row_kind`.
 *
 * "boe_allocation" rows carry a `children` array (one per underlying BOE
 * allocation) — rendered as extra `<tr>`s directly below their parent,
 * expanded by default (mirrors the PDF, which has no interactive collapse)
 * with an optional collapse toggle since this view IS interactive.
 */
export default function FinancialLedgerTable({ rows }: FinancialLedgerTableProps) {
    const [collapsed, setCollapsed] = useState<Set<number>>(new Set());

    const toggle = (sr: number) => {
        setCollapsed((prev) => {
            const next = new Set(prev);
            if (next.has(sr)) next.delete(sr);
            else next.add(sr);
            return next;
        });
    };

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
                    {rows.map((row) => {
                        const hasChildren = Boolean(row.children && row.children.length > 0);
                        const isCollapsed = collapsed.has(row.sr);
                        return (
                            <Fragment key={row.sr}>
                                <tr className={cn("border-t border-border/60", financialLedgerRowClass(row.row_kind, row.mismatched))}>
                                    <td className="px-3 py-2">{row.sr}</td>
                                    <td className="whitespace-nowrap px-3 py-2">{fmtDate(row.date)}</td>
                                    <td className="whitespace-nowrap px-3 py-2 font-medium">
                                        {hasChildren ? (
                                            <button
                                                type="button"
                                                onClick={() => toggle(row.sr)}
                                                className="inline-flex cursor-pointer items-center gap-1 hover:underline"
                                                aria-label={isCollapsed ? "Expand allocation detail" : "Collapse allocation detail"}
                                            >
                                                {isCollapsed ? (
                                                    <ChevronRight className="size-3.5" />
                                                ) : (
                                                    <ChevronDown className="size-3.5" />
                                                )}
                                                {row.type}
                                            </button>
                                        ) : (
                                            row.type
                                        )}
                                    </td>
                                    <td className="px-3 py-2">{row.document_number ?? "—"}</td>
                                    <td className="px-3 py-2" title={row.linked_boe_numbers?.join(", ")}>
                                        {row.boe_number ?? "—"}
                                    </td>
                                    <td className="whitespace-nowrap px-3 py-2">
                                        {row.boe_date_display ?? fmtDate(row.boe_date)}
                                    </td>
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
                                {hasChildren && !isCollapsed &&
                                    row.children!.map((child, idx) => (
                                        <ChildRow key={`${row.sr}-${child.allocation_id ?? idx}`} child={child} />
                                    ))}
                            </Fragment>
                        );
                    })}
                </tbody>
            </table>
        </div>
    );
}
